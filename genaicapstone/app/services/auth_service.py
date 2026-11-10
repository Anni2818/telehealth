import logging

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash

from app.repositories.auth_repository import (
    find_user_by_id,
    find_user_by_username,
)
from app.security.tokens import (
    ACCESS_TOKEN_MINUTES,
    create_access_token,
    validate_access_token,
)


logger = logging.getLogger(__name__)

password_hasher = PasswordHash.recommended()
dummy_hash = password_hasher.hash("unused-dummy-password")

bearer_scheme = HTTPBearer(auto_error=False)


def _unauthorized(message):
    return HTTPException(
        status_code=401,
        detail=message,
        headers={"WWW-Authenticate": "Bearer"},
    )


def login_user(username, password):
    username = username.strip()

    user = find_user_by_username(username)

    stored_hash = (
        user["password_hash"]
        if user is not None
        else dummy_hash
    )

    password_valid = password_hasher.verify(
        password,
        stored_hash,
    )

    if (
        user is None
        or not password_valid
        or not user["user_active"]
        or not user["customer_active"]
    ):
        raise _unauthorized("Invalid username or password.")

    token = create_access_token(user["user_id"])

    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_MINUTES * 60,
    }


def get_current_customer(
    credentials: HTTPAuthorizationCredentials | None = Depends(
        bearer_scheme
    ),
):
    if credentials is None:
        raise _unauthorized("Authentication required.")

    try:
        user_id = validate_access_token(
            credentials.credentials
        )
    except InvalidTokenError as error:
        raise _unauthorized(
            "Invalid or expired access token."
        ) from error

    try:
        user = find_user_by_id(user_id)
    except Exception as error:
        logger.exception("Authenticated customer lookup failed.")

        raise HTTPException(
            status_code=503,
            detail="Customer identity could not be verified.",
        ) from error

    if (
        user is None
        or not user["user_active"]
        or not user["customer_active"]
    ):
        raise _unauthorized(
            "Account is unavailable or inactive."
        )

    return {
        "user_id": user["user_id"],
        "username": user["username"],
        "customer_id": user["customer_id"],
        "customer_code": user["customer_code"],
    }