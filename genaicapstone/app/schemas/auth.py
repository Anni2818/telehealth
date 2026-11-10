from pydantic import BaseModel, ConfigDict, Field, SecretStr


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=1, max_length=50)
    password: SecretStr = Field(min_length=1, max_length=256)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int


class CurrentCustomerResponse(BaseModel):
    user_id: int
    username: str
    customer_id: int
    customer_code: str