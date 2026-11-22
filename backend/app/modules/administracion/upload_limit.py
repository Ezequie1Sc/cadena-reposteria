from tempfile import SpooledTemporaryFile

from starlette.responses import JSONResponse


class UploadLimit:
    """Limita los bytes del multipart aun con transferencia sin Content-Length."""

    limit = 6 * 1024 * 1024

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        path = scope.get("path", "")
        if (
            scope["type"] != "http"
            or not path.startswith("/administracion/")
            or scope["method"] not in {"POST", "PUT"}
        ):
            return await self.app(scope, receive, send)
        with SpooledTemporaryFile(max_size=512 * 1024) as body:
            total = 0
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                chunk = message.get("body", b"")
                total += len(chunk)
                if total > self.limit:
                    return await JSONResponse(
                        {"detail": "Petición demasiado grande"}, status_code=413
                    )(scope, receive, send)
                body.write(chunk)
                if not message.get("more_body"):
                    break
            body.seek(0)
            sent = 0

            async def replay():
                nonlocal sent
                if sent > total:
                    return await receive()
                part = body.read(65536)
                sent += len(part)
                more = sent < total
                if not more:
                    sent += 1
                return {"type": "http.request", "body": part, "more_body": more}

            await self.app(scope, replay, send)
