from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel
from core.auth import verify_dashboard_password, create_access_token, get_current_user
from config import settings

router = APIRouter(prefix="/api/auth", tags=["Auth"])

class LoginRequest(BaseModel):
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int

@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest):
    if not verify_dashboard_password(req.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect dashboard password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(data={"sub": "admin"})
    return LoginResponse(
        access_token=token,
        expires_in_minutes=settings.JWT_EXPIRE_MINUTES
    )

@router.get("/me")
async def get_me(user: str = Depends(get_current_user)):
    return {"user": user, "authenticated": True}
