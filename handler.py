from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler
from typing import Any
from urllib.parse import urlparse

import services
from database import db
from errors import ApiError
from schemas import user_dto


class Handler(BaseHTTPRequestHandler):
    server_version = "Python404Backend/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"{self.address_string()} - {fmt % args}")

    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
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

    def handle_request(self, method: str) -> None:
        try:
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

    def route(self, method: str) -> Any:
        route = self.api_route()
        with db() as conn:
            if method == "GET" and route == ["events"]:
                return services.public_events(conn)

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
        services.user_from_token(conn, self.token(), admin=True)

        if method == "GET" and route == ["events"]:
            return services.admin_events(conn)

        if method == "POST" and route == ["events"]:
            return services.save_event(conn, self.read_json())

        if method == "PUT" and len(route) == 2 and route[0] == "events":
            return services.update_event(conn, int(route[1]), self.read_json())

        if method == "GET" and route == ["orders"]:
            return services.admin_orders(conn)

        if method == "PATCH" and len(route) == 3 and route[0] == "orders" and route[2] in {"confirm", "cancel"}:
            status = "CONFIRMED" if route[2] == "confirm" else "CANCELLED"
            return services.set_order_status(conn, route[1], status)

        if method == "POST" and len(route) == 3 and route[0] == "tickets" and route[2] == "check-in":
            return services.check_in(conn, route[1])

        raise ApiError(404, "Not found")

    def api_route(self) -> list[str]:
        parsed = urlparse(self.path)
        parts = [part for part in parsed.path.strip("/").split("/") if part]
        if not parts or parts[0] != "api":
            raise ApiError(404, "Not found")
        return parts[1:]
