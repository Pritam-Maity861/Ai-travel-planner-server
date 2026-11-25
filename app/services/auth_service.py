from fastapi import HTTPException, status

from app.core.security import create_access_token, get_password_hash, verify_password
from app.repositories.user_repository import UserRepository
from app.schemas.user import TokenResponse, UserCreate, UserLogin, UserResponse


class AuthService:
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    async def register(self, body: UserCreate) -> TokenResponse:
        existing = await self.user_repo.get_by_email(body.email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A user with this email already exists.",
            )

        hashed_password = get_password_hash(body.password)
        user = await self.user_repo.create(
            email=body.email,
            hashed_password=hashed_password,
            name=body.name,
        )

        token = create_access_token({"sub": str(user.id), "email": user.email})
        return TokenResponse(
            access_token=token,
            token_type="bearer",
            user=UserResponse.model_validate(user),
        )

    async def login(self, body: UserLogin) -> TokenResponse:
        user = await self.user_repo.get_by_email(body.email)
        if not user or not verify_password(body.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
            )

        token = create_access_token({"sub": str(user.id), "email": user.email})
        return TokenResponse(
            access_token=token,
            token_type="bearer",
            user=UserResponse.model_validate(user),
        )

