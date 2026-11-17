"""Public API v1 and encrypted internal payload schemas."""

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")


class ActivationRequest(StrictModel):
    license_hash: str = Field(pattern=r"^[0-9a-f]{64}$", min_length=64, max_length=64)
    payload: str = Field(min_length=24, max_length=8000)


class Device(StrictModel):
    os_name: str = Field(min_length=1, max_length=100)
    cpu_arch: str = Field(min_length=1, max_length=32)
    cpu_cores: StrictInt = Field(ge=1, le=32767)
    mac_address: str = Field(min_length=1, max_length=17)
    motherboard_id: str | None = Field(..., max_length=255)

    @field_validator("os_name", "cpu_arch", "mac_address")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("blank device parameter")
        return value


class EncryptedActivation(StrictModel):
    license_key: str = Field(min_length=19, max_length=19)
    device: Device


class SuccessResponse(StrictModel):
    status: str = "success"
    message: str = "Лицензия успешно активирована"


class ErrorResponse(StrictModel):
    status: str = "error"
    code: str
    message: str
