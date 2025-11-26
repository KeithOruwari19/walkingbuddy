# auth_routes.py
"""
Authentication Routes Module
Handles user signup, login, logout, and session verification.

API Endpoints:
- POST /auth/signup - Register a new user
- POST /auth/login - Login existing user
- POST /auth/logout - Logout current user
- GET /auth/verify - Verify current session
- GET /auth/me - Get current user info
"""
from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional, List, Dict

from backend.auth import auth_storage

router = APIRouter(prefix="/auth", tags=["authentication"])


class SignupRequest(BaseModel):
    """Data sent by the frontend when a user signs up."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "John Doe",
                "email": "john@mylaurier.ca",
                "password": "securepassword123"
            }
        }
    )
    
    name: str = Field(..., min_length=1, max_length=100, description="User's full name")
    email: EmailStr = Field(..., description="Laurier email address (@mylaurier.ca)")
    password: str = Field(..., min_length=8, max_length=128, description="User password (min 8 characters)")


class LoginRequest(BaseModel):
    """Data sent by the frontend when a user logs in."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "john@mylaurier.ca",
                "password": "securepassword123"
            }
        }
    )
    
    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., description="User's password")


class AuthResponse(BaseModel):
    """Data returned to the frontend after successful login or signup."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user_id": "550e8400-e29b-41d4-a716-446655440000",
                "name": "John Doe",
                "email": "john@mylaurier.ca",
                "message": "Login successful"
            }
        }
    )
    
    user_id: str = Field(..., description="Unique user identifier")
    name: str = Field(..., description="User's display name")
    email: EmailStr = Field(..., description="User's email address")
    message: str = Field(..., description="Status message")


class UserResponse(BaseModel):
    """User information without sensitive data."""
    user_id: str = Field(..., description="Unique user identifier")
    name: str = Field(..., description="User's display name")
    email: EmailStr = Field(..., description="User's email address")
    authenticated: bool = Field(True, description="Authentication status")


class MessageResponse(BaseModel):
    """Generic message response."""
    message: str = Field(..., description="Response message")


@router.post(
    "/signup",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Create a new user account with a Laurier email address and establish a session"
)
async def signup(body: SignupRequest, request: Request):
    user = auth_storage.create_user(body.name, body.email, body.password)
    
    if user is None:
        if not body.email.lower().endswith("@mylaurier.ca"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Laurier email (@mylaurier.ca) required."
            )
        
        existing_user = auth_storage.get_user_by_email(body.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered."
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must be at least 8 characters long."
            )

    request.session["user_id"] = user["id"]
    
    return AuthResponse(
        user_id=user["id"],
        name=user["name"],
        email=user["email"],
        message="Signup successful. Session created."
    )


@router.post(
    "/login",
    response_model=AuthResponse,
    status_code=status.HTTP_200_OK,
    summary="Login an existing user",
    description="Authenticate a user and establish a session"
)
async def login(body: LoginRequest, request: Request):
    user = auth_storage.get_user_by_email(body.email)
    
    if user is None or not auth_storage.verify_user_password(user, body.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password."
        )
    
    request.session["user_id"] = user["id"]
    
    return AuthResponse(
        user_id=user["id"],
        name=user["name"],
        email=user["email"],
        message="Login successful. Session created."
    )


@router.post(
    "/logout",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Logout user",
    description="Clear the current session"
)
async def logout(request: Request):
    request.session.clear()
    return MessageResponse(message="Successfully logged out. Session cleared.")


@router.get(
    "/verify",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify session",
    description="Check if user has a valid session and get user information"
)
async def verify_session(request: Request):
    user_id = request.session.get("user_id")
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No active session found. Please login."
        )
    
    user = auth_storage.get_user_by_id(user_id)
    
    if not user:
        request.session.clear()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found. Session cleared."
        )
    
    return UserResponse(
        user_id=user["id"],
        name=user["name"],
        email=user["email"],
        authenticated=True
    )


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current user",
    description="Get information about the currently logged-in user"
)
async def get_current_user(request: Request):
    return await verify_session(request)



def get_session_user_id(request: Request) -> str:
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Please login."
        )
    return user_id


def get_session_user_id_optional(request: Request) -> Optional[str]:
    return request.session.get("user_id")


user_router = APIRouter(prefix="/api/users", tags=["users"])

@user_router.get("/{user_id}")
def get_user(user_id: str):
    user = auth_storage.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"user_id": user["id"], "name": user["name"], "email": user["email"]}

@user_router.post("/batch")
def batch_users(ids: List[str]):
    out: Dict[str, Optional[Dict]] = {}
    for uid in ids:
        u = auth_storage.get_user_by_id(uid)
        if u:
            out[uid] = {"user_id": u["id"], "name": u["name"], "email": u["email"]}
        else:
            out[uid] = None
    return out
