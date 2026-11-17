"""ASGI application: API endpoints, lifespan resources and safe error responses."""

import ipaddress
import logging
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from importlib.metadata import PackageNotFoundError, version
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.exc import (
    InterfaceError,
    OperationalError,
    SQLAlchemyError,
)
from sqlalchemy.exc import (
    TimeoutError as DbTimeout,
)

from app.api.v1.schemas import ActivationRequest, SuccessResponse
from app.core.body_limit import BodySizeLimitMiddleware
from app.core.config import Settings, get_settings
from app.core.logging import log_event, pseudonym, setup_logging
from app.core.rate_limit import RedisUnavailable, TokenBucketLimiter
from app.db.session import make_sessionmaker
from app.services.activation import ActivationRejected, ActivationService


def failure(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"status": "error", "code": code, "message": message},
    )


def is_loopback(request: Request) -> bool:
    if request.client is None:
        return False

    try:
        return ipaddress.ip_address(request.client.host).is_loopback
    except ValueError:
        return False


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or get_settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncGenerator[None]:
        setup_logging()
        application.state.sessionmaker = make_sessionmaker(config)
        application.state.redis = Redis.from_url(
            config.redis_url,
            socket_connect_timeout=config.redis_connect_timeout,
            socket_timeout=config.redis_socket_timeout,
            decode_responses=False,
        )
        application.state.limiter = TokenBucketLimiter(application.state.redis)
        try:
            yield
        finally:
            await application.state.redis.aclose()
            await application.state.sessionmaker.kw["bind"].dispose()

    def is_production() -> bool:
        return config.app_env.lower() == "production"

    production = is_production()
    try:
        app_version = version("license-activation-backend")
    except PackageNotFoundError:
        app_version = "0.0.0.0"
    application = FastAPI(
        title="License Activation API",
        version=app_version,
        lifespan=lifespan,
        docs_url=None if production else "/docs",
        redoc_url=None if production else "/redoc",
        openapi_url=None if production else "/openapi.json",
    )
    application.state.settings = config
    application.add_middleware(BodySizeLimitMiddleware)

    @application.get("/health/live")
    async def live(request: Request) -> JSONResponse:
        if not is_loopback(request):
            return failure(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Not found")
        return JSONResponse({"status": "ok"})

    @application.get("/health/ready")
    async def ready(request: Request) -> JSONResponse:
        if not is_loopback(request):
            return failure(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Not found")
        try:
            async with application.state.sessionmaker() as session:
                await session.execute(text("SELECT 1"))
            return JSONResponse({"status": "ok"})
        except SQLAlchemyError:
            return failure(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "SERVICE_UNAVAILABLE",
                "Сервис временно недоступен",
            )

    @application.post("/api/v1/licenses/activate", status_code=201)
    async def activate(request: Request) -> JSONResponse:
        request_id = str(uuid.uuid4())
        ip = request.client.host if request.client else "unknown"
        ip_id = pseudonym(config.log_hmac_secret.get_secret_value(), ip)
        context: dict[str, Any] = {
            "request_id": request_id,
            "client_ip_id": ip_id,
            "path": "/api/v1/licenses/activate",
        }
        try:
            allowed = await application.state.limiter.allowed(ip)
        except RedisUnavailable:
            log_event(
                logging.ERROR,
                "REDIS_UNAVAILABLE",
                **context,
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                reason="REDIS_TIMEOUT_EXCEEDED"
            )
            return failure(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "SERVICE_UNAVAILABLE",
                "Сервис временно недоступен",
            )
        if not allowed:
            log_event(
                logging.WARNING,
                "RATE_LIMITED",
                **context,
                status_code=status.HTTP_429_TOO_MANY_REQUESTS
            )
            return failure(
                status.HTTP_429_TOO_MANY_REQUESTS,
                "RATE_LIMITED",
                "Слишком много запросов. Повторите позже",
            )
        try:
            data = ActivationRequest.model_validate(await request.json())
        except (ValueError, ValidationError):
            log_event(
                logging.WARNING,
                "ACTIVATION_REJECTED",
                **context,
                reason="INVALID_REQUEST",
                status_code=status.HTTP_400_BAD_REQUEST
            )
            return failure(
                status.HTTP_400_BAD_REQUEST,
                "ACTIVATION_FAILED",
                "Не удалось активировать лицензию",
            )
        try:
            async with application.state.sessionmaker() as session:
                result = await ActivationService(session).activate(data)
        except ActivationRejected as exc:
            context["license_id"] = exc.license_id
            if exc.fingerprint is not None:
                context["device_id"] = pseudonym(
                    config.log_hmac_secret.get_secret_value(), exc.fingerprint
                )
            log_event(
                logging.WARNING,
                "ACTIVATION_REJECTED",
                **context,
                reason=exc.reason,
                status_code=status.HTTP_400_BAD_REQUEST
            )
            return failure(
                status.HTTP_400_BAD_REQUEST,
                "ACTIVATION_FAILED",
                "Не удалось активировать лицензию",
            )
        except (OperationalError, InterfaceError, DbTimeout):
            log_event(
                logging.ERROR,
                "DATABASE_UNAVAILABLE",
                **context,
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                reason="DATABASE_CONNECTION_FAILED"
            )
            return failure(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "SERVICE_UNAVAILABLE",
                "Сервис временно недоступен",
            )
        except SQLAlchemyError:
            log_event(
                logging.ERROR,
                "DATABASE_ERROR",
                **context,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                reason="DATABASE_OPERATION_FAILED"
            )
            return failure(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                "INTERNAL_ERROR",
                "Внутренняя ошибка сервера",
            )
        log_event(
            logging.INFO,
            "ACTIVATION_SUCCESS",
            **context,
            license_id=result.license_id,
            activation_id=result.activation_id,
            device_id=pseudonym(
                config.log_hmac_secret.get_secret_value(), result.fingerprint
            ),
            status_code=status.HTTP_201_CREATED
        )
        return JSONResponse(
            status_code=status.HTTP_201_CREATED, content=SuccessResponse().model_dump()
        )

    @application.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        log_event(
            logging.ERROR,
            "UNHANDLED_ERROR",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            reason="UNEXPECTED",
        )
        return failure(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "INTERNAL_ERROR",
            "Внутренняя ошибка сервера",
        )

    return application


app = create_app()
