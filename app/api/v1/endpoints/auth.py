from fastapi import APIRouter, Depends, status

from app.api.deps import get_auth_service, get_current_user
from app.models.user import User
from app.schemas.user import TokenResponse, UserCreate, UserLogin, UserResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: UserCreate,
    auth_service: AuthService = Depends(get_auth_service),
):
    return await auth_service.register(body)


@router.post("/login", response_model=TokenResponse)
async def login(
    body: UserLogin,
    auth_service: AuthService = Depends(get_auth_service),
):
    return await auth_service.login(body)


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
):
    return current_user

