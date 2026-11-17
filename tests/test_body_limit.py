import json
from collections.abc import Iterable

import pytest
from starlette.types import Message, Receive, Scope, Send

from app.core.body_limit import MAX_BODY_BYTES, BodySizeLimitMiddleware


async def asgi_request(parts: Iterable[bytes]) -> list[Message]:
    received: list[Message] = []
    pieces = list(parts)
    index = 0

    async def receive() -> Message:
        nonlocal index
        if index < len(pieces):
            body = pieces[index]
            index += 1
            return {
                "type": "http.request",
                "body": body,
                "more_body": index < len(pieces),
            }
        return {"type": "http.disconnect"}

    async def send(message: Message) -> None:
        received.append(message)

    async def inner(scope: Scope, next_receive: Receive, next_send: Send) -> None:
        data = await next_receive()
        await next_send({"type": "http.response.start", "status": 201, "headers": []})
        await next_send({"type": "http.response.body", "body": data["body"]})

    middleware = BodySizeLimitMiddleware(inner)
    scope: Scope = {"type": "http", "path": "/api/v1/licenses/activate", "headers": []}
    await middleware(scope, receive, send)
    return received


@pytest.mark.asyncio
@pytest.mark.filterwarnings("ignore:.*HTTP_413_REQUEST_ENTITY_TOO_LARGE.*")
async def test_rejects_payload_over_limit() -> None:
    messages = await asgi_request([b"x" * MAX_BODY_BYTES, b"x"])

    assert messages[0]["status"] == 413

    body = messages[1]["body"]
    assert isinstance(body, bytes)
    assert json.loads(body)["code"] == "REQUEST_TOO_LARGE"


@pytest.mark.asyncio
async def test_allows_exact_limit() -> None:
    messages = await asgi_request([b"x" * MAX_BODY_BYTES])

    assert messages[0]["status"] == 201

    body = messages[1]["body"]
    assert isinstance(body, bytes)
    assert len(body) == MAX_BODY_BYTES
