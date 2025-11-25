# auth_storage.py
"""
Authentication Storage Module
Manages user accounts and password verification using in-memory storage.
"""

import uuid
import hashlib
import secrets
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)

# Configuration
ALLOWED_EMAIL_DOMAIN = "@mylaurier.ca"

# In-memory storage structures
# Stores user accounts indexed by user_id
USERS_BY_ID: Dict[str, dict] = {}

# Email-to-user_id mapping for quick lookups
USERS_BY_EMAIL: Dict[str, str] = {}


# Private Helper Functions

def _hash_password(password: str) -> str:
    """
    Creates a salted hash of the password using SHA-256.
    
    Args:
        password: Plain text password
        
    Returns:
        String in format "salt:hash"
    """
    salt = secrets.token_hex(16)
    password_hash = hashlib.sha256((password + salt).encode("utf-8")).hexdigest()
    return f"{salt}:{password_hash}"


def _verify_password_hash(stored_hash: str, password: str) -> bool:
    """
    Verifies a password against a stored hash.
    Uses constant-time comparison to prevent timing attacks.
        
    Returns:
        True if password matches, False otherwise
    """
    try:
        salt, password_hash = stored_hash.split(":", 1)
        computed_hash = hashlib.sha256((password + salt).encode("utf-8")).hexdigest()
        return secrets.compare_digest(computed_hash, password_hash)
    except ValueError:
        return False


def _normalize_email(email: str) -> str:
    """
    Normalizes email to lowercase and strips whitespace.
    
    Returns:
        Normalized email address
    """
    return email.lower().strip()


def _is_laurier_email(email: str) -> bool:
    """
    Validates that the email ends with @mylaurier.ca
        
    Returns:
        True if valid Laurier email, False otherwise
    """
    return email.endswith(ALLOWED_EMAIL_DOMAIN)


# Public API Functions

def create_user(name: str, email: str, password: str) -> Optional[Dict]:
    """
    Creates a new user account if the email is valid and not already taken.
    
    Args:
        name: User's full name
        email: User's email address (must be @mylaurier.ca)
        password: User's password (must be at least 8 characters)
        
    Returns:
        User dict with 'id', 'name', 'email' if successful, None otherwise
    """
    email = _normalize_email(email)
    
    if not _is_laurier_email(email):
        raise ValueError("Email must be a @mylaurier.ca address.")
    if email in USERS_BY_EMAIL:
        raise ValueError("Email already registered.")
    if not name or not password or len(password) < 8:
        raise ValueError("Name required and password must be at least 8 characters.")
    
    user_id = str(uuid.uuid4())
    user = {
        "id": user_id,
        "name": name.strip(),
        "email": email,
        "password_hash": _hash_password(password),
    }
    
    USERS_BY_ID[user_id] = user
    USERS_BY_EMAIL[email] = user_id
    
    return {
        "id": user["id"],
        "name": user["name"],
        "email": user["email"]
    }


def get_user_by_email(email: str) -> Optional[Dict]:
    """
    Returns a user dict given an email, or None if not found.
    Returns complete user object including password_hash for verification.
        
    Returns:
        Complete user dict if found, None otherwise
    """
    email = _normalize_email(email)
    user_id = USERS_BY_EMAIL.get(email)
    
    if not user_id:
        return None
    
    return USERS_BY_ID.get(user_id)


def get_user_by_id(user_id: str) -> Optional[Dict]:
    """
    Returns a user dict given a user ID, or None if not found.
    Returns user without password hash (safe for external use).
        
    Returns:
        User dict without password_hash if found, None otherwise
    """
    user = USERS_BY_ID.get(user_id)
    if not user:
        return None
    
    return {
        "id": user["id"],
        "name": user["name"],
        "email": user["email"]
    }


def verify_user_password(user: Dict, password: str) -> bool:
    """
    Returns True if the password is correct, False otherwise.
    Uses constant-time comparison to prevent timing attacks.
      
    Returns:
        True if password matches, False otherwise
    """
    if not user or "password_hash" not in user:
        return False
    return _verify_password_hash(user["password_hash"], password)


def get_all_users_count() -> int:
    """
    Returns the total number of registered users.
    
    Returns:
        Integer count of users
    """
    return len(USERS_BY_ID)


def get_all_users() -> list:
    """
    Returns a list of all users (without password hashes).
    Useful for admin/debugging purposes.
    
    Returns:
        List of user dicts without password_hash
    """
    return [
        {
            "id": user["id"],
            "name": user["name"],
            "email": user["email"]
        }
        for user in USERS_BY_ID.values()
    ]
