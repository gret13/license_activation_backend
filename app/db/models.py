from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class License(Base):
    __tablename__ = "licenses"
    __table_args__ = (CheckConstraint("max_activations >= 1", name="ck_positive_max_activations"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    license_key: Mapped[str] = mapped_column(String(19), unique=True, nullable=False)
    license_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    max_activations: Mapped[int] = mapped_column(SmallInteger, server_default="1", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Activation(Base):
    __tablename__ = "activations"
    __table_args__ = (UniqueConstraint("license_id", "fingerprint", name="uq_license_fingerprint"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    license_id: Mapped[int] = mapped_column(ForeignKey("licenses.id"), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    os_name: Mapped[str | None] = mapped_column(String(100))
    cpu_arch: Mapped[str | None] = mapped_column(String(32))
    cpu_cores: Mapped[int | None] = mapped_column(SmallInteger)
    mac_address: Mapped[str | None] = mapped_column(String(17))
    motherboard_id: Mapped[str | None] = mapped_column(String(255))
    activated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
