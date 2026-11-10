import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "").strip()

if len(SECRET_KEY) < 64:
    raise RuntimeError(
        "JWT_SECRET_KEY is missing or too short. "
        "Generate it using secrets.token_hex(32)."
    )

ALGORITHM = "HS256"
ISSUER = "genaicapstone"
AUDIENCE = "genaicapstone-api"
ACCESS_TOKEN_MINUTES = 15


def create_access_token(user_id):
    now = datetime.now(timezone.utc)

    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_MINUTES),
        "iss": ISSUER,
        "aud": AUDIENCE,
        "token_use": "access",
    }

    return jwt.encode(
        payload,
        SECRET_KEY,
        algorithm=ALGORITHM,
    )


def validate_access_token(token):
    payload = jwt.decode(
        token,
        SECRET_KEY,
        algorithms=[ALGORITHM],
        issuer=ISSUER,
        audience=AUDIENCE,
        options={
            "require": [
                "sub",
                "iat",
                "exp",
                "iss",
                "aud",
                "token_use",
            ]
        },
    )

    if payload["token_use"] != "access":
        raise jwt.InvalidTokenError("Incorrect token type.")

    subject = payload["sub"]

    if not isinstance(subject, str):
        raise jwt.InvalidTokenError("Invalid token subject.")

    if (
        not subject.isascii()
        or not subject.isdecimal()
        or len(subject) > 10
    ):
        raise jwt.InvalidTokenError("Invalid token subject.")

    user_id = int(subject)

    if not 1 <= user_id <= 2147483647:
        raise jwt.InvalidTokenError("Invalid token subject.")

    return user_id