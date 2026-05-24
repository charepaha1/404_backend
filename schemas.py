from __future__ import annotations

import sqlite3
from typing import Any

from database import one


def user_dto(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "email": row["email"],
        "fullName": row["full_name"],
        "phone": row["phone"],
        "telegramId": row["telegram_id"],
        "telegramUsername": row["telegram_username"],
        "role": row["role"],
    }


def event_dto(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "title": row["title"],
        "subtitle": row["subtitle"],
        "description": row["description"],
        "venue": row["venue"],
        "city": row["city"],
        "startAt": row["start_at"],
        "price": row["price"],
        "currency": row["currency"],
        "paymentDetails": row["payment_details"],
        "posterUrl": row["poster_url"],
        "status": row["status"],
    }


def ticket_dto(ticket: sqlite3.Row, order: sqlite3.Row, event: sqlite3.Row) -> dict[str, Any]:
    return {
        "ticketCode": ticket["ticket_code"],
        "orderCode": order["order_code"],
        "eventId": event["id"],
        "eventTitle": event["title"],
        "firstName": order["customer_first_name"],
        "lastName": order["customer_last_name"],
        "telegramId": order["telegram_id"],
        "username": order["telegram_username"],
        "status": ticket["status"],
        "checkedInAt": ticket["checked_in_at"],
        "createdAt": ticket["created_at"],
    }


def order_dto(conn: sqlite3.Connection, order: sqlite3.Row) -> dict[str, Any]:
    event = one(conn, "SELECT * FROM events WHERE id = ?", (order["event_id"],))
    tickets = conn.execute("SELECT * FROM tickets WHERE order_id = ? ORDER BY id", (order["id"],)).fetchall()
    return {
        "orderCode": order["order_code"],
        "event": event_dto(event),
        "customerFirstName": order["customer_first_name"],
        "customerLastName": order["customer_last_name"],
        "customerEmail": order["customer_email"],
        "customerPhone": order["customer_phone"],
        "telegramId": order["telegram_id"],
        "telegramUsername": order["telegram_username"],
        "ticketCount": order["ticket_count"],
        "totalAmount": order["total_amount"],
        "status": order["status"],
        "paymentComment": order["payment_comment"],
        "createdAt": order["created_at"],
        "tickets": [ticket_dto(ticket, order, event) for ticket in tickets],
    }
