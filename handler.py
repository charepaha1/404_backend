from __future__ import annotations

import json
import mimetypes
import uuid
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import services
from config import BOT_TOKEN, ROOT
from database import db
from errors import ApiError
from schemas import user_dto

UPLOAD_ROOT = ROOT / "uploads"
POSTER_ROOT = UPLOAD_ROOT / "posters"
MAX_POSTER_BYTES = 8 * 1024 * 1024
POSTER_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


class Handler(BaseHTTPRequestHandler):
    server_version = "Python404Backend/1.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"{self.address_string()} - {fmt % args}")

    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Bot-Token")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, PATCH, DELETE, OPTIONS")
        super().end_headers()

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.end_headers()

    def do_GET(self) -> None:
        self.handle_request("GET")

    def do_POST(self) -> None:
        self.handle_request("POST")

    def do_PUT(self) -> None:
        self.handle_request("PUT")

    def do_PATCH(self) -> None:
        self.handle_request("PATCH")

    def do_DELETE(self) -> None:
        self.handle_request("DELETE")

    def handle_request(self, method: str) -> None:
        try:
            if method == "GET" and self.send_static_upload():
                return
            self.send_json(self.route(method))
        except ApiError as exc:
            self.send_json({"error": exc.message}, exc.status)
        except Exception as exc:
            print(f"Unhandled error: {exc}")
            self.send_json({"error": "Internal server error"}, 500)

    def send_json(self, data: Any, status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_static_upload(self) -> bool:
        parsed = urlparse(self.path)
        if not parsed.path.startswith("/uploads/"):
            return False

        relative = unquote(parsed.path.removeprefix("/uploads/")).replace("\\", "/")
        target = (UPLOAD_ROOT / relative).resolve()
        upload_root = UPLOAD_ROOT.resolve()
        if not str(target).startswith(str(upload_root)) or not target.is_file():
            raise ApiError(404, "File not found")

        body = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(target.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "public, max-age=31536000")
        self.end_headers()
        self.wfile.write(body)
        return True

    def read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length == 0:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except json.JSONDecodeError:
            raise ApiError(400, "Invalid JSON")

    def token(self) -> str | None:
        auth = self.headers.get("Authorization", "")
        return auth.removeprefix("Bearer ").strip() if auth.startswith("Bearer ") else None

    def bot_authorized(self) -> bool:
        token = (
            self.headers.get("X-Bot-Token")
            or self.headers.get("X-BOT-TOKEN")
            or self.headers.get("x-bot-token")
            or ""
        )
        return bool(BOT_TOKEN and (token.strip() == BOT_TOKEN or BOT_TOKEN in str(self.headers)))

    def route(self, method: str) -> Any:
        # Main API router: maps an HTTP method + /api/... path to business logic.
        route = self.api_route()
        with db() as conn:
            if method == "GET" and route == ["events"]:
                return services.public_events(conn)

            if method == "GET" and len(route) == 2 and route[0] == "events":
                return services.get_event(conn, int(route[1]))

            if method == "GET" and len(route) == 2 and route[0] == "tickets":
                return services.get_ticket(conn, route[1])

            if method == "POST" and route == ["orders"]:
                user = services.user_from_token(conn, self.token(), required=False)
                return services.create_order(conn, self.read_json(), user)

            if method == "POST" and len(route) == 3 and route[0] == "orders" and route[2] == "paid":
                return services.mark_paid(conn, route[1], self.read_json())

            if method == "POST" and route == ["auth", "login"]:
                return services.login(conn, self.read_json())

            if method == "POST" and route == ["auth", "register"]:
                return services.register(conn, self.read_json())

            if method == "GET" and route == ["auth", "me"]:
                user = services.user_from_token(conn, self.token())
                return user_dto(user)

            if method == "GET" and route == ["me", "orders"]:
                user = services.user_from_token(conn, self.token())
                return services.user_orders(conn, user)

            if route[:1] == ["admin"]:
                return self.admin_route(conn, method, route[1:])

        raise ApiError(404, "Not found")

    def admin_route(self, conn: Any, method: str, route: list[str]) -> Any:
        # Admin endpoints are protected either by an ADMIN user token or by the bot token.
        if not self.bot_authorized():
            services.user_from_token(conn, self.token(), admin=True)

        if method == "GET" and route == ["events"]:
            return services.admin_events(conn)

        if method == "POST" and route == ["events"]:
            return services.save_event(conn, self.read_json())

        if method == "PUT" and len(route) == 2 and route[0] == "events":
            return services.update_event(conn, int(route[1]), self.read_json())

        if method == "DELETE" and len(route) == 2 and route[0] == "events":
            return services.delete_event(conn, int(route[1]))

        if method == "PATCH" and len(route) == 3 and route[0] == "events" and route[2] == "poster":
            return services.update_event_poster(conn, int(route[1]), self.read_json().get("posterUrl"))

        if method == "POST" and route == ["uploads", "poster"]:
            return self.save_poster_upload()

        if method == "GET" and route == ["orders"]:
            return services.admin_orders(conn)

        if method == "POST" and route == ["manual-tickets"]:
            return services.create_manual_tickets(conn, self.read_json())

        if method == "POST" and route == ["pass-ticket"]:
            return services.create_manual_tickets(conn, self.read_json(), pass_ticket=True)

        if method == "PATCH" and len(route) == 3 and route[0] == "orders" and route[2] in {"confirm", "cancel"}:
            status = "CONFIRMED" if route[2] == "confirm" else "CANCELLED"
            return services.set_order_status(conn, route[1], status)

        if method == "POST" and len(route) == 3 and route[0] == "tickets" and route[2] == "check-in":
            return services.check_in(conn, route[1])

        if method == "DELETE" and len(route) == 2 and route[0] == "tickets":
            return services.delete_ticket(conn, route[1])

        if method == "DELETE" and route == ["tickets"]:
            return services.clear_tickets(conn)

        raise ApiError(404, "Not found")

    def save_poster_upload(self) -> dict[str, str]:
        content_type = (self.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
        if content_type not in POSTER_TYPES:
            raise ApiError(400, "Only JPEG, PNG, WEBP and GIF images are allowed")

        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            raise ApiError(400, "Poster file is required")
        if length > MAX_POSTER_BYTES:
            raise ApiError(400, "Poster file is too large")

        POSTER_ROOT.mkdir(parents=True, exist_ok=True)
        filename = f"{uuid.uuid4().hex}{POSTER_TYPES[content_type]}"
        target = POSTER_ROOT / filename
        target.write_bytes(self.rfile.read(length))

        path = f"/uploads/posters/{filename}"
        host = self.headers.get("Host") or f"localhost:{self.server.server_port}"
        return {"posterUrl": f"http://{host}{path}"}

    def api_route(self) -> list[str]:
        parsed = urlparse(self.path)
        parts = [part for part in parsed.path.strip("/").split("/") if part]
        if not parts or parts[0] != "api":
            raise ApiError(404, "Not found")
        return parts[1:]
