# auth_routes.py
from fastapi import APIRouter, HTTPException, Header, status
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional

import auth_storage


router = APIRouter()


class SignupRequest(BaseModel):
    """
    Data sent by the frontend when a user signs up.
    """
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
    """
    Data sent by the frontend when a user logs in.
    """
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
    """
    Data returned to the frontend after successful login or signup.
    """
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "token": "abc123xyz789...",
                "user_id": "550e8400-e29b-41d4-a716-446655440000",
                "name": "John Doe",
                "email": "john@mylaurier.ca"
            }
        }
    )

    token: str = Field(..., description="Session token for authentication")
    user_id: str = Field(..., description="Unique user identifier")
    name: str = Field(..., description="User's display name")
    email: EmailStr = Field(..., description="User's email address")


class UserResponse(BaseModel):
    """
    User information without sensitive data.
    """
    user_id: str
    name: str
    email: EmailStr


class MessageResponse(BaseModel):
    """
    Generic message response.
    """
    message: str

# Authentication Routes
@router.post(
    "/signup",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Create a new user account with a Laurier email address"
)
async def signup(body: SignupRequest):
    """
    Handle new user registration.

    Steps:
    1. Validate input (handled by Pydantic)
    2. Try to create the user (includes Laurier email validation)
    3. If success, create a session token and return it

    Raises:
        HTTPException 400: Invalid input data
        HTTPException 403: Non-Laurier email address
        HTTPException 409: Email already registered
    """
    # Try to create the user in storage
    # auth_storage.create_user already validates Laurier email and password strength
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

    token = auth_storage.create_session(user["id"])
    return AuthResponse(
        token=token,
        user_id=user["id"],
        name=user["name"],
        email=user["email"],
    )


@router.post(
    "/login",
    response_model=AuthResponse,
    status_code=status.HTTP_200_OK,
    summary="Login an existing user",
    description="Authenticate a user and receive a session token"
)
async def login(body: LoginRequest):
    """
    Handle existing user login.

    Steps:
    1. Look up the user by email
    2. Verify the password
    3. If success, create a session token and return it

    Raises:
        HTTPException 401: Invalid credentials
    """
    # Look up user
    user = auth_storage.get_user_by_email(body.email)

    # If no user or wrong password → same 401 error 
    if user is None or not auth_storage.verify_user_password(user, body.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password."
        )
    token = auth_storage.create_session(user["id"])

    return AuthResponse(
        token=token,
        user_id=user["id"],
        name=user["name"],
        email=user["email"],
    )


@router.post(
    "/logout",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Logout user",
    description="Invalidate the current session token"
)
async def logout(authorization: Optional[str]=Header(None)):
    """
    Handle user logout by invalidating their session token.

    The token should be sent in the Authorization header as:
    Authorization: Bearer <token>

    Raises:
        HTTPException 401: No token provided or invalid format
    """
    # Extract token from Authorization header
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No authorization token provided."
        )

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format. Use: Bearer <token>"
        )

    token = parts[1]
    success = auth_storage.invalidate_session(token)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token."
        )

    return MessageResponse(message="Successfully logged out.")


@router.get(
    "/verify",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify session token",
    description="Check if a session token is valid and get user information"
)
async def verify_token(authorization: Optional[str]=Header(None)):
    """
    Verify if a session token is still valid and return user information.

    The token should be sent in the Authorization header as:
    Authorization: Bearer <token>

    Raises:
        HTTPException 401: No token, invalid format, or expired token
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No authorization token provided."
        )
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format. Use: Bearer <token>"
        )

    token = parts[1]
    user_id = auth_storage.get_user_id_from_token(token)

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token."
        )

    user = auth_storage.get_user_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found."
        )

    return UserResponse(
        user_id=user["id"],
        name=user["name"],
        email=user["email"]
    )


# Helper Functions for Other Routes

def get_current_user_id(authorization: Optional[str]=Header(None)) -> str:
    """
    Dependency function to extract and verify user ID from token.

    Raises:
        HTTPException 401: Invalid or missing token
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required."
        )

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format."
        )

    token = parts[1]
    user_id = auth_storage.get_user_id_from_token(token)

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token."
        )

    return user_id
