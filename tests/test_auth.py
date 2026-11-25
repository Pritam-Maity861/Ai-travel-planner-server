import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import (
    create_access_token,
    decode_access_token,
    get_password_hash,
    verify_password,
)
from app.main import create_app


def test_password_hashing():
    pwd = "MySecretPassword123!"
    hashed = get_password_hash(pwd)
    assert hashed != pwd
    assert verify_password(pwd, hashed) is True
    assert verify_password("WrongPassword", hashed) is False


def test_jwt_token_generation_and_decoding():
    user_id = str(uuid.uuid4())
    token = create_access_token({"sub": user_id, "email": "traveler@test.com"})
    assert isinstance(token, str)

    payload = decode_access_token(token)
    assert payload is not None
    assert payload["sub"] == user_id
    assert payload["email"] == "traveler@test.com"


@pytest.mark.asyncio
async def test_auth_endpoints_lifecycle():
    app = create_app()
    # Use lifespan so db pool is available
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            unique_email = f"test_{uuid.uuid4().hex[:8]}@example.com"
            # 1. Register
            reg_resp = await client.post(
                "/api/v1/auth/register",
                json={
                    "email": unique_email,
                    "password": "Password123!",
                    "name": "Alex Traveler",
                },
            )
            assert reg_resp.status_code == 201
            reg_data = reg_resp.json()
            assert "access_token" in reg_data
            assert reg_data["user"]["email"] == unique_email
            assert reg_data["user"]["name"] == "Alex Traveler"
            token = reg_data["access_token"]

            # 2. Duplicate email should fail
            dup_resp = await client.post(
                "/api/v1/auth/register",
                json={
                    "email": unique_email,
                    "password": "Password123!",
                    "name": "Alex Duplicate",
                },
            )
            assert dup_resp.status_code == 409

            # 3. Login with wrong password should fail
            bad_login = await client.post(
                "/api/v1/auth/login",
                json={"email": unique_email, "password": "WrongPassword"},
            )
            assert bad_login.status_code == 401

            # 4. Login with correct credentials
            login_resp = await client.post(
                "/api/v1/auth/login",
                json={"email": unique_email, "password": "Password123!"},
            )
            assert login_resp.status_code == 200
            assert "access_token" in login_resp.json()

            # 5. Access /me with token
            me_resp = await client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert me_resp.status_code == 200
            assert me_resp.json()["email"] == unique_email

            # 6. Access /me without token should fail
            unauth_resp = await client.get("/api/v1/auth/me")
            assert unauth_resp.status_code == 401
