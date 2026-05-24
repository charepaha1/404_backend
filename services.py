from __future__ import annotations

import sqlite3
from typing import Any

from auth import hash_password, read_token, sign_token, verify_password
from database import one
from errors import ApiError
from schemas import event_dto, order_dto, ticket_dto, user_dto
from utils import make_code, now_iso


def user_from_token(
    conn: sqlite3.Connection,
    token: str | None,
    required: bool = True,
    admin: bool = False,
) -> sqlite3.Row | None:
    payload = read_token(token)
    user_id = payload.get("sub") if payload else None
    user = one(conn, "SELECT * FROM users WHERE id = ?", (user_id,)) if user_id else None
    if required and not user:
        raise ApiError(401, "Unauthorized")
    if admin and (not user or user["role"] != "ADMIN"):
        raise ApiError(403, "Admin role required")
    return user


def public_events(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute("SELECT * FROM events WHERE status != 'HIDDEN' ORDER BY start_at").fetchall()
    return [event_dto(row) for row in rows]


def create_order(conn: sqlite3.Connection, payload: dict[str, Any], user: sqlite3.Row | None) -> dict[str, Any]:
    event = one(conn, "SELECT * FROM events WHERE id = ?", (payload.get("eventId"),))
    if not event:
        raise ApiError(404, "Event not found")
    if event["status"] != "ACTIVE":
        raise ApiError(409, "Event is not available for purchase")

    first_name = str(payload.get("firstName", "")).strip()
    last_name = str(payload.get("lastName", "")).strip()
    quantity = int(payload.get("quantity") or 1)
    if not first_name or not last_name:
        raise ApiError(400, "First name and last name are required")
    if quantity < 1 or quantity > 5:
        raise ApiError(400, "Quantity must be between 1 and 5")

    order_code = make_code("O")
    created_at = now_iso()
    conn.execute(
        """
        INSERT INTO orders
        (order_code, event_id, user_id, customer_first_name, customer_last_name, customer_email,
         customer_phone, telegram_username, ticket_count, total_amount, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'AWAITING_PAYMENT', ?)
        """,
        (
            order_code,
            event["id"],
            user["id"] if user else None,
            first_name,
            last_name,
            payload.get("email") or None,
            payload.get("phone") or None,
            payload.get("telegramUsername") or None,
            quantity,
            int(event["price"]) * quantity,
            created_at,
        ),
    )
    order = one(conn, "SELECT * FROM orders WHERE order_code = ?", (order_code,))
    for _ in range(quantity):
        conn.execute(
            "INSERT INTO tickets (ticket_code, order_id, status, created_at) VALUES (?, ?, 'AWAITING_PAYMENT', ?)",
            (make_code("T"), order["id"], created_at),
        )
    return order_dto(conn, order)


def mark_paid(conn: sqlite3.Connection, order_code: str, payload: dict[str, Any]) -> dict[str, Any]:
    order = one(conn, "SELECT * FROM orders WHERE order_code = ?", (order_code,))
    if not order:
        raise ApiError(404, "Order not found")
    if order["status"] != "AWAITING_PAYMENT":
        raise ApiError(409, "Order cannot be marked as paid")

    conn.execute(
        "UPDATE orders SET status = 'PENDING_CONFIRMATION', payment_comment = ? WHERE id = ?",
        (payload.get("comment") or "", order["id"]),
    )
    conn.execute("UPDATE tickets SET status = 'PENDING_CONFIRMATION' WHERE order_id = ?", (order["id"],))
    return order_dto(conn, one(conn, "SELECT * FROM orders WHERE id = ?", (order["id"],)))


def login(conn: sqlite3.Connection, payload: dict[str, Any]) -> dict[str, Any]:
    user = one(conn, "SELECT * FROM users WHERE lower(email) = lower(?)", (payload.get("email") or "",))
    if not user or not verify_password(str(payload.get("password") or ""), user["password_hash"]):
        raise ApiError(401, "Invalid email or password")
    return {"token": sign_token(user["id"]), "user": user_dto(user)}


def register(conn: sqlite3.Connection, payload: dict[str, Any]) -> dict[str, Any]:
    email = str(payload.get("email") or "").strip().lower()
    password = str(payload.get("password") or "")
    full_name = str(payload.get("fullName") or "").strip()
    if not email or "@" not in email or len(password) < 4 or not full_name:
        raise ApiError(400, "Email, password and full name are required")
    try:
        conn.execute(
            """
            INSERT INTO users (email, password_hash, full_name, phone, role, created_at)
            VALUES (?, ?, ?, ?, 'USER', ?)
            """,
            (email, hash_password(password), full_name, payload.get("phone") or None, now_iso()),
        )
    except sqlite3.IntegrityError:
        raise ApiError(409, "User already exists")

    user = one(conn, "SELECT * FROM users WHERE email = ?", (email,))
    return {"token": sign_token(user["id"]), "user": user_dto(user)}


def user_orders(conn: sqlite3.Connection, user: sqlite3.Row) -> list[dict[str, Any]]:
    rows = conn.execute("SELECT * FROM orders WHERE user_id = ? ORDER BY id DESC", (user["id"],)).fetchall()
    return [order_dto(conn, row) for row in rows]


def admin_events(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute("SELECT * FROM events ORDER BY start_at").fetchall()
    return [event_dto(row) for row in rows]


def admin_orders(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute("SELECT * FROM orders ORDER BY id DESC").fetchall()
    return [order_dto(conn, row) for row in rows]


def validate_event_payload(payload: dict[str, Any]) -> dict[str, Any]:
    required = ["title", "venue", "city", "startAt", "price"]
    if any(not str(payload.get(field, "")).strip() for field in required):
        raise ApiError(400, "Title, venue, city, startAt and price are required")
    return payload


def save_event(conn: sqlite3.Connection, payload: dict[str, Any]) -> dict[str, Any]:
    payload = validate_event_payload(payload)
    conn.execute(
        """
        INSERT INTO events
        (title, subtitle, description, venue, city, start_at, price, currency, payment_details, poster_url, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            payload.get("title"),
            payload.get("subtitle") or None,
            payload.get("description") or None,
            payload.get("venue"),
            payload.get("city"),
            payload.get("startAt"),
            int(payload.get("price")),
            payload.get("currency") or "KZT",
            payload.get("paymentDetails") or None,
            payload.get("posterUrl") or None,
            payload.get("status") or "ACTIVE",
            now_iso(),
        ),
    )
    event_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    return event_dto(one(conn, "SELECT * FROM events WHERE id = ?", (event_id,)))


def update_event(conn: sqlite3.Connection, event_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    if not one(conn, "SELECT * FROM events WHERE id = ?", (event_id,)):
        raise ApiError(404, "Event not found")

    payload = validate_event_payload(payload)
    conn.execute(
        """
        UPDATE events
        SET title = ?, subtitle = ?, description = ?, venue = ?, city = ?, start_at = ?,
            price = ?, currency = ?, payment_details = ?, poster_url = ?, status = ?
        WHERE id = ?
        """,
        (
            payload.get("title"),
            payload.get("subtitle") or None,
            payload.get("description") or None,
            payload.get("venue"),
            payload.get("city"),
            payload.get("startAt"),
            int(payload.get("price")),
            payload.get("currency") or "KZT",
            payload.get("paymentDetails") or None,
            payload.get("posterUrl") or None,
            payload.get("status") or "ACTIVE",
            event_id,
        ),
    )
    return event_dto(one(conn, "SELECT * FROM events WHERE id = ?", (event_id,)))


def set_order_status(conn: sqlite3.Connection, order_code: str, status: str) -> dict[str, Any]:
    order = one(conn, "SELECT * FROM orders WHERE order_code = ?", (order_code,))
    if not order:
        raise ApiError(404, "Order not found")

    conn.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order["id"]))
    conn.execute("UPDATE tickets SET status = ? WHERE order_id = ?", (status, order["id"]))
    return order_dto(conn, one(conn, "SELECT * FROM orders WHERE id = ?", (order["id"],)))


def check_in(conn: sqlite3.Connection, ticket_code: str) -> dict[str, Any]:
    ticket = one(conn, "SELECT * FROM tickets WHERE ticket_code = ?", (ticket_code,))
    if not ticket:
        raise ApiError(404, "Ticket not found")
    if ticket["status"] != "CONFIRMED" or ticket["checked_in_at"]:
        raise ApiError(409, "Ticket is not confirmed or already checked in")

    conn.execute("UPDATE tickets SET status = 'CHECKED_IN', checked_in_at = ? WHERE id = ?", (now_iso(), ticket["id"]))
    ticket = one(conn, "SELECT * FROM tickets WHERE id = ?", (ticket["id"],))
    order = one(conn, "SELECT * FROM orders WHERE id = ?", (ticket["order_id"],))
    event = one(conn, "SELECT * FROM events WHERE id = ?", (order["event_id"],))
    return ticket_dto(ticket, order, event)
