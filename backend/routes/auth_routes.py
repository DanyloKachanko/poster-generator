from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from auth import verify_password, create_token

router = APIRouter(tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/auth/login")
async def login(req: LoginRequest):
    if not verify_password(req.username, req.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_token(req.username)
    return {"token": token, "username": req.username}
