from __future__ import annotations

from typing import Any

from pymongo.errors import DuplicateKeyError

from auth import hash_password, read_token, sign_token, verify_password
from database import next_id
from errors import ApiError
from schemas import event_dto, order_dto, ticket_dto, user_dto
from telegram_notify import notify_payment_claim
from utils import make_code, now_iso


def user_from_token(
    conn: Any,
    token: str | None,
    required: bool = True,
    admin: bool = False,
) -> dict[str, Any] | None:
    payload = read_token(token)
    user_id = payload.get("sub") if payload else None
    user = conn.users.find_one({"id": int(user_id)}) if user_id else None
    if required and not user:
        raise ApiError(401, "Unauthorized")
    if admin and (not user or user["role"] != "ADMIN"):
        raise ApiError(403, "Admin role required")
    return user


def public_events(conn: Any) -> list[dict[str, Any]]:
    rows = conn.events.find({"status": {"$ne": "HIDDEN"}}).sort("start_at", 1)
    return [event_dto(row) for row in rows]


def get_event(conn: Any, event_id: int) -> dict[str, Any]:
    event = conn.events.find_one({"id": event_id})
    if not event:
        raise ApiError(404, "Event not found")
    return event_dto(event)


def _unique_code(conn: Any, collection: str, field: str, prefix: str) -> str:
    for _ in range(20):
        code = make_code(prefix)
        if not conn[collection].find_one({field: code}):
            return code
    raise ApiError(500, "Could not generate unique code")


def create_order(conn: Any, payload: dict[str, Any], user: dict[str, Any] | None) -> dict[str, Any]:
    # Public purchase flow: validate event/customer data, then create one order and its tickets.
    event = conn.events.find_one({"id": int(payload.get("eventId") or 0)})
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

    order = _insert_order(
        conn,
        event=event,
        first_name=first_name,
        last_name=last_name,
        quantity=quantity,
        status="AWAITING_PAYMENT",
        user_id=user["id"] if user else None,
        customer_email=payload.get("email") or None,
        customer_phone=payload.get("phone") or None,
        telegram_id=payload.get("telegramId"),
        telegram_username=payload.get("telegramUsername") or None,
        payment_comment=None,
    )
    return order_dto(conn, order)


def _insert_order(
    conn: Any,
    *,
    event: dict[str, Any],
    first_name: str,
    last_name: str,
    quantity: int,
    status: str,
    user_id: int | None = None,
    customer_email: str | None = None,
    customer_phone: str | None = None,
    telegram_id: int | None = None,
    telegram_username: str | None = None,
    payment_comment: str | None = None,
    ticket_code: str | None = None,
) -> dict[str, Any]:
    # Shared order creation helper used by normal purchases and manual/admin tickets.
    created_at = now_iso()
    order = {
        "id": next_id(conn, "orders"),
        "order_code": _unique_code(conn, "orders", "order_code", "O"),
        "event_id": event["id"],
        "user_id": user_id,
        "customer_first_name": first_name,
        "customer_last_name": last_name,
        "customer_email": customer_email,
        "customer_phone": customer_phone,
        "telegram_id": int(telegram_id) if telegram_id not in {None, ""} else None,
        "telegram_username": telegram_username,
        "ticket_count": quantity,
        "total_amount": int(event.get("price", 0)) * quantity,
        "status": status,
        "payment_comment": payment_comment,
        "created_at": created_at,
    }
    conn.orders.insert_one(order)

    for index in range(quantity):
        code = ticket_code if index == 0 and ticket_code else _unique_code(conn, "tickets", "ticket_code", "T")
        conn.tickets.insert_one(
            {
                "id": next_id(conn, "tickets"),
                "ticket_code": code,
                "order_id": order["id"],
                "status": status,
                "checked_in_at": None,
                "created_at": created_at,
            }
        )
    return order


def mark_paid(conn: Any, order_code: str, payload: dict[str, Any]) -> dict[str, Any]:
    # Customer says payment was sent; admin still has to confirm it later.
    order = conn.orders.find_one({"order_code": order_code})
    if not order:
        raise ApiError(404, "Order not found")
    if order["status"] != "AWAITING_PAYMENT":
        raise ApiError(409, "Order cannot be marked as paid")

    conn.orders.update_one(
        {"id": order["id"]},
        {"$set": {"status": "PENDING_CONFIRMATION", "payment_comment": payload.get("comment") or ""}},
    )
    conn.tickets.update_many({"order_id": order["id"]}, {"$set": {"status": "PENDING_CONFIRMATION"}})
    updated_order = conn.orders.find_one({"id": order["id"]})
    if payload.get("notifyAdmins", True):
        notify_payment_claim(conn, updated_order)
    return order_dto(conn, updated_order)


def login(conn: Any, payload: dict[str, Any]) -> dict[str, Any]:
    email = str(payload.get("email") or "").strip().lower()
    user = conn.users.find_one({"email_lc": email})
    if not user or not verify_password(str(payload.get("password") or ""), user["password_hash"]):
        raise ApiError(401, "Invalid email or password")
    return {"token": sign_token(user["id"]), "user": user_dto(user)}


def register(conn: Any, payload: dict[str, Any]) -> dict[str, Any]:
    email = str(payload.get("email") or "").strip().lower()
    password = str(payload.get("password") or "")
    full_name = str(payload.get("fullName") or "").strip()
    if not email or "@" not in email or len(password) < 4 or not full_name:
        raise ApiError(400, "Email, password and full name are required")
    try:
        user = {
            "id": next_id(conn, "users"),
            "email": email,
            "email_lc": email,
            "password_hash": hash_password(password),
            "full_name": full_name,
            "phone": payload.get("phone") or None,
            "telegram_id": payload.get("telegramId"),
            "telegram_username": payload.get("telegramUsername"),
            "role": "USER",
            "created_at": now_iso(),
        }
        conn.users.insert_one(user)
    except DuplicateKeyError:
        raise ApiError(409, "User already exists")

    return {"token": sign_token(user["id"]), "user": user_dto(user)}


def user_orders(conn: Any, user: dict[str, Any]) -> list[dict[str, Any]]:
    rows = conn.orders.find({"user_id": user["id"]}).sort("id", -1)
    return [order_dto(conn, row) for row in rows]


def admin_events(conn: Any) -> list[dict[str, Any]]:
    rows = conn.events.find({}).sort("start_at", 1)
    return [event_dto(row) for row in rows]


def admin_orders(conn: Any) -> list[dict[str, Any]]:
    rows = conn.orders.find({}).sort("id", -1)
    return [order_dto(conn, row) for row in rows]


def validate_event_payload(payload: dict[str, Any]) -> dict[str, Any]:
    required = ["title", "venue", "city", "startAt", "price"]
    if any(not str(payload.get(field, "")).strip() for field in required):
        raise ApiError(400, "Title, venue, city, startAt and price are required")
    return payload


def _event_doc(payload: dict[str, Any], existing: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "title": payload.get("title"),
        "subtitle": payload.get("subtitle") or None,
        "description": payload.get("description") or None,
        "venue": payload.get("venue"),
        "city": payload.get("city"),
        "start_at": payload.get("startAt"),
        "price": int(payload.get("price")),
        "currency": payload.get("currency") or "KZT",
        "payment_details": payload.get("paymentDetails") or None,
        "poster_url": payload.get("posterUrl") or (existing or {}).get("poster_url"),
        "status": payload.get("status") or "ACTIVE",
    }


def save_event(conn: Any, payload: dict[str, Any]) -> dict[str, Any]:
    payload = validate_event_payload(payload)
    event = {
        "id": next_id(conn, "events"),
        **_event_doc(payload),
        "created_at": now_iso(),
    }
    conn.events.insert_one(event)
    return event_dto(event)


def update_event(conn: Any, event_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    existing = conn.events.find_one({"id": event_id})
    if not existing:
        raise ApiError(404, "Event not found")

    payload = validate_event_payload(payload)
    update = _event_doc(payload, existing)
    conn.events.update_one({"id": event_id}, {"$set": update})
    return event_dto(conn.events.find_one({"id": event_id}))


def delete_event(conn: Any, event_id: int) -> dict[str, Any]:
    event = conn.events.find_one({"id": event_id})
    if not event:
        raise ApiError(404, "Event not found")
    orders = list(conn.orders.find({"event_id": event_id}, {"id": 1}))
    order_ids = [order["id"] for order in orders]
    if order_ids:
        conn.tickets.delete_many({"order_id": {"$in": order_ids}})
        conn.orders.delete_many({"id": {"$in": order_ids}})
    conn.events.delete_one({"id": event_id})
    return event_dto(event)


def update_event_poster(conn: Any, event_id: int, poster_url: str | None) -> dict[str, Any]:
    event = conn.events.find_one({"id": event_id})
    if not event:
        raise ApiError(404, "Event not found")
    conn.events.update_one({"id": event_id}, {"$set": {"poster_url": poster_url}})
    return event_dto(conn.events.find_one({"id": event_id}))


def set_order_status(conn: Any, order_code: str, status: str) -> dict[str, Any]:
    # Admin status change keeps order and all related tickets synchronized.
    order = conn.orders.find_one({"order_code": order_code})
    if not order:
        raise ApiError(404, "Order not found")

    conn.orders.update_one({"id": order["id"]}, {"$set": {"status": status}})
    conn.tickets.update_many({"order_id": order["id"]}, {"$set": {"status": status}})
    return order_dto(conn, conn.orders.find_one({"id": order["id"]}))


def get_ticket(conn: Any, ticket_code: str) -> dict[str, Any]:
    ticket = conn.tickets.find_one({"ticket_code": ticket_code.strip().lstrip("#").upper()})
    if not ticket:
        raise ApiError(404, "Ticket not found")
    order = conn.orders.find_one({"id": ticket["order_id"]})
    event = conn.events.find_one({"id": order["event_id"]})
    return ticket_dto(ticket, order, event)


def check_in(conn: Any, ticket_code: str) -> dict[str, Any]:
    # Entrance control: only confirmed, not-yet-used tickets can be checked in.
    ticket = conn.tickets.find_one({"ticket_code": ticket_code.strip().lstrip("#").upper()})
    if not ticket:
        raise ApiError(404, "Ticket not found")
    if ticket["status"] != "CONFIRMED" or ticket.get("checked_in_at"):
        raise ApiError(409, "Ticket is not confirmed or already checked in")

    conn.tickets.update_one(
        {"id": ticket["id"]},
        {"$set": {"status": "CHECKED_IN", "checked_in_at": now_iso()}},
    )
    ticket = conn.tickets.find_one({"id": ticket["id"]})
    order = conn.orders.find_one({"id": ticket["order_id"]})
    event = conn.events.find_one({"id": order["event_id"]})
    return ticket_dto(ticket, order, event)


def create_manual_tickets(conn: Any, payload: dict[str, Any], pass_ticket: bool = False) -> list[dict[str, Any]]:
    event = _event_for_manual_ticket(conn, payload)
    quantity = 1 if pass_ticket else max(1, min(int(payload.get("quantity") or 1), 5))
    first_name = str(payload.get("firstName") or "").strip()
    last_name = str(payload.get("lastName") or "").strip()
    if not first_name or not last_name:
        raise ApiError(400, "First name and last name are required")

    username = payload.get("groupName") if pass_ticket else payload.get("username")
    status = "PASS" if pass_ticket else "CONFIRMED"
    order = _insert_order(
        conn,
        event=event,
        first_name=first_name,
        last_name=last_name,
        quantity=quantity,
        status=status,
        telegram_username=username or "manual",
        payment_comment="manual",
    )
    return order_dto(conn, order)["tickets"]


def _event_for_manual_ticket(conn: Any, payload: dict[str, Any]) -> dict[str, Any]:
    event_id = payload.get("eventId")
    event = conn.events.find_one({"id": int(event_id)}) if event_id not in {None, ""} else None
    if not event:
        event_name = str(payload.get("eventName") or "").strip()
        event = conn.events.find_one({"title": event_name}) if event_name else None
    if not event:
        raise ApiError(404, "Event not found")
    return event


def delete_ticket(conn: Any, ticket_code: str) -> dict[str, Any]:
    normalized = ticket_code.strip().lstrip("#").upper()
    ticket = conn.tickets.find_one({"ticket_code": normalized})
    if not ticket:
        raise ApiError(404, "Ticket not found")
    order = conn.orders.find_one({"id": ticket["order_id"]})
    event = conn.events.find_one({"id": order["event_id"]})
    result = ticket_dto(ticket, order, event)
    conn.tickets.delete_one({"id": ticket["id"]})
    remaining = conn.tickets.count_documents({"order_id": order["id"]})
    if remaining == 0:
        conn.orders.delete_one({"id": order["id"]})
    else:
        conn.orders.update_one(
            {"id": order["id"]},
            {"$set": {"ticket_count": remaining, "total_amount": int(event.get("price", 0)) * remaining}},
        )
    return result


def clear_tickets(conn: Any) -> dict[str, int]:
    ticket_count = conn.tickets.count_documents({})
    order_count = conn.orders.count_documents({})
    conn.tickets.delete_many({})
    conn.orders.delete_many({})
    return {"tickets": ticket_count, "orders": order_count}
