import logging

from fastapi import APIRouter, Depends, HTTPException

from app.schemas.auth import (
    CurrentCustomerResponse,
    LoginRequest,
    TokenResponse,
)
from app.services.auth_service import (
    get_current_customer,
    login_user,
)


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest):
    try:
        return login_user(
            username=request.username,
            password=request.password.get_secret_value(),
        )

    except HTTPException:
        raise

    except Exception as error:
        logger.exception("Login operation failed.")

        raise HTTPException(
            status_code=503,
            detail="Login could not be completed.",
        ) from error


@router.get("/me", response_model=CurrentCustomerResponse)
def read_current_customer(
    current_customer: dict = Depends(get_current_customer),
):
    return current_customer