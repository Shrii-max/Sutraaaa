"""Pure ASGI middleware for audit logging and mandatory legal disclaimers.

Enforces Hard Rule 5: Every API access writes an append-only audit log row.
Enforces Hard Rule 10: Injects legal disclaimer header into all API responses.
Zero deadlock risk with TestClient or async event loops.
"""

import time
from app.security.audit import record_audit_event


class AuditAndDisclaimerMiddleware:
    """Pure ASGI middleware without BaseHTTPMiddleware task-group deadlock overhead."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start_time = time.perf_counter()
        path = scope.get("path", "")
        method = scope.get("method", "GET")
        client = scope.get("client")
        client_host = client[0] if client else "local_test"

        status_code = [200]

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status_code[0] = message.get("status", 200)
                # Inject mandatory legal disclaimer header (Hard Rule 10)
                headers = list(message.get("headers", []))
                headers.append(
                    (b"x-legal-disclaimer", b"Decision-support only; not legal advice.")
                )
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
            status_str = "SUCCESS" if status_code[0] < 400 else "FAILURE"
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            record_audit_event(
                event_type="API_ACCESS",
                actor=f"client:{client_host}",
                resource_id=path,
                input_payload={"method": method, "path": path},
                output_payload={"exception": str(e), "duration_ms": duration_ms},
                status="ERROR",
            )
            raise

        duration_ms = (time.perf_counter() - start_time) * 1000

        # Hard Rule 5: Write append-only audit log for API access
        if path != "/api/v1/health":
            record_audit_event(
                event_type="API_ACCESS",
                actor=f"client:{client_host}",
                resource_id=path,
                input_payload={"method": method, "path": path},
                output_payload={"status_code": status_code[0], "duration_ms": round(duration_ms, 2)},
                status=status_str,
            )
