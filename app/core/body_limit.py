import json

from fastapi import status
from starlette.types import ASGIApp, Message, Receive, Scope, Send

MAX_BODY_BYTES = 8192


class BodySizeLimitMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("path") != "/api/v1/licenses/activate":
            await self.app(scope, receive, send)
            return

        async def rejected() -> None:
            payload = json.dumps(
                {
                    "status": "error",
                    "code": "REQUEST_TOO_LARGE",
                    "message": "Слишком большой запрос",
                }
            ).encode("utf-8")
            headers = [
                (b"content-type", b"application/json; charset=utf-8"),
                (b"content-length", str(len(payload)).encode("ascii")),
            ]
            await send(
                {
                    "type": "http.response.start",
                    "status": status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    "headers": headers,
                }
            )
            await send({"type": "http.response.body", "body": payload})

        for key, value in scope.get("headers", []):
            if key.lower() == b"content-length":
                try:
                    if int(value) > MAX_BODY_BYTES:
                        await rejected()
                        return
                except ValueError:
                    pass

        buffered = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            buffered.extend(message.get("body", b""))
            if len(buffered) > MAX_BODY_BYTES:
                await rejected()
                return
            if not message.get("more_body", False):
                break
        delivered = False

        async def replay() -> Message:
            nonlocal delivered
            if not delivered:
                delivered = True
                return {
                    "type": "http.request",
                    "body": bytes(buffered),
                    "more_body": False,
                }
            return await receive()

        await self.app(scope, replay, send)
