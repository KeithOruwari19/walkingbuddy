# auth_storage.py
import uuid
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict

SESSION_LIFETIME_HOURS = 24  # Sessions expire after 24 hours
ALLOWED_EMAIL_DOMAIN = "@mylaurier.ca"


# In-memory storage structures
# Stores user accounts using email as the key
USERS_BY_EMAIL: Dict[str, dict] = {}

# Stores session tokens mapped to user info
# Structure: { "token": {"user_id": "...", "expires_at": datetime} }
SESSIONS: Dict[str, dict] = {}



def _hash_password(password: str) -> str:
   
    salt = secrets.token_hex(16)
    password_hash = hashlib.sha256((password + salt).encode("utf-8")).hexdigest()
    return f"{salt}:{password_hash}"


def _verify_password_hash(stored_hash: str, password: str) -> bool:
    """
    Verifies a password against a stored hash.
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
    """
    return email.lower().strip()


def _is_laurier_email(email: str) -> bool:
    """
    Validates that the email ends with @mylaurier.ca
    """
    return email.endswith(ALLOWED_EMAIL_DOMAIN)


def _cleanup_expired_sessions() -> None:
    """
    Removes expired session tokens from memory.
    Should be called periodically or on each session check.
    """
    now = datetime.now()
    expired_tokens = [
        token for token, session_data in SESSIONS.items()
        if session_data["expires_at"] < now
    ]
    for token in expired_tokens:
        del SESSIONS[token]


# Public API Functions

def create_user(name: str, email: str, password: str) -> Optional[Dict]:
    """
    Creates a new user account if the email is valid and not already taken.

    Returns:
        User dict without password_hash if successful, None otherwise
    """
    email = _normalize_email(email)
    if not _is_laurier_email(email):
        return None
    if email in USERS_BY_EMAIL:
        return None
    if not name or not password or len(password) < 8:
        return None
    user_id = str(uuid.uuid4())
    user = {
        "id": user_id,
        "name": name.strip(),
        "email": email,
        "password_hash": _hash_password(password),
    }
    USERS_BY_EMAIL[email] = user
    return {
        "id": user["id"],
        "name": user["name"],
        "email": user["email"]
    }


def get_user_by_email(email: str) -> Optional[Dict]:
    """
    Returns a user dict given an email, or None if not found.
    """
    return USERS_BY_EMAIL.get(_normalize_email(email))


def verify_user_password(user: Dict, password: str) -> bool:
    """
    Returns True if the password is correct, False otherwise.
    Uses constant-time comparison to prevent timing attacks.
    """
    if not user or "password_hash" not in user:
        return False
    return _verify_password_hash(user["password_hash"], password)


def create_session(user_id: str) -> str:
    """
    Creates a session token for a user and stores it with expiration.

    Returns:
        Session token string
    """
    _cleanup_expired_sessions()
    token = secrets.token_urlsafe(32)
    SESSIONS[token] = {
        "user_id": user_id,
        "expires_at": datetime.now() + timedelta(hours=SESSION_LIFETIME_HOURS)
    }

    return token


def get_user_id_from_token(token: str) -> Optional[str]:
    """
    Returns the user_id associated with a valid session token,
    or None if the token is invalid or expired.
    """
    _cleanup_expired_sessions()

    session_data = SESSIONS.get(token)

    if not session_data:
        return None

    if session_data["expires_at"] < datetime.now():
        del SESSIONS[token]
        return None

    return session_data["user_id"]


def invalidate_session(token: str) -> bool:
    """
    Logs out a user by removing their session token.

    Returns:
        True if session was found and removed, False otherwise
    """
    if token in SESSIONS:
        del SESSIONS[token]
        return True
    return False


def get_user_by_id(user_id: str) -> Optional[Dict]:
    """
    Returns a user dict given a user ID, or None if not found.
    Returns user without password hash.
    """
    for user in USERS_BY_EMAIL.values():
        if user["id"] == user_id:
            return {
                "id": user["id"],
                "name": user["name"],
                "email": user["email"]
            }
    return None

def get_all_users_count() -> int:
    """Returns the total number of registered users."""
    return len(USERS_BY_EMAIL)


def get_active_sessions_count() -> int:
    """Returns the number of active (non-expired) sessions."""
    _cleanup_expired_sessions()
    return len(SESSIONS)
