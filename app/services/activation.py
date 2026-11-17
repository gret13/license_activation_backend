from dataclasses import dataclass

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas import ActivationRequest, EncryptedActivation
from app.core.crypto import InvalidCiphertext, decrypt_payload
from app.db.models import Activation
from app.domain.fingerprint import fingerprint, normalize_device
from app.domain.licensing import license_hash, valid_license
from app.repositories.licenses import LicenseRepository


@dataclass(frozen=True)
class ActivationOutcome:
    license_id: int
    activation_id: int
    fingerprint: str


class ActivationRejected(Exception):
    def __init__(self, reason: str, license_id: int | None = None,
                 fingerprint: str | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.license_id = license_id
        self.fingerprint = fingerprint


class ActivationService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = LicenseRepository(session)
        self.session = session

    async def activate(self, request: ActivationRequest) -> ActivationOutcome:
        async with self.session.begin():
            license_record = await self.repository.locked_by_hash(request.license_hash)
            if license_record is None:
                raise ActivationRejected("LICENSE_UNKNOWN")
            if not license_record.is_active:
                raise ActivationRejected("LICENSE_INACTIVE", license_record.id)
            try:
                raw = decrypt_payload(license_record.license_key, request.payload)
                data = EncryptedActivation.model_validate(raw)
                if not valid_license(data.license_key):
                    raise ActivationRejected("INVALID_LICENSE", license_record.id)
                if (data.license_key != license_record.license_key
                        or license_hash(data.license_key) != request.license_hash):
                    raise ActivationRejected("LICENSE_MISMATCH", license_record.id)
                normalized = normalize_device(data.device)
            except (InvalidCiphertext, ValidationError, ValueError) as exc:
                raise ActivationRejected("INVALID_PAYLOAD", license_record.id) from exc

            device_fingerprint = fingerprint(normalized)
            if await self.repository.has_activation(license_record.id, device_fingerprint):
                raise ActivationRejected("DUPLICATE_FINGERPRINT", license_record.id,
                                         device_fingerprint)
            count = await self.repository.count_activations(license_record.id)
            if count >= license_record.max_activations:
                raise ActivationRejected("LIMIT_REACHED", license_record.id,
                                         device_fingerprint)

            activation_id = await self.repository.add_activation(
                Activation(
                    license_id=license_record.id,
                    fingerprint=device_fingerprint,
                    os_name=normalized.os_name,
                    cpu_arch=normalized.cpu_arch,
                    cpu_cores=normalized.cpu_cores,
                    mac_address=normalized.mac_address,
                    motherboard_id=normalized.motherboard_id,
                )
            )
        return ActivationOutcome(license_record.id, activation_id, device_fingerprint)
