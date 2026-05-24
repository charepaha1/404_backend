from __future__ import annotations

from typing import Any


def user_dto(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "email": row["email"],
        "fullName": row["full_name"],
        "phone": row.get("phone"),
        "telegramId": row.get("telegram_id"),
        "telegramUsername": row.get("telegram_username"),
        "role": row["role"],
    }


def event_dto(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "title": row["title"],
        "subtitle": row.get("subtitle"),
        "description": row.get("description"),
        "venue": row["venue"],
        "city": row["city"],
        "startAt": row["start_at"],
        "price": row["price"],
        "currency": row.get("currency", "KZT"),
        "paymentDetails": row.get("payment_details"),
        "posterUrl": row.get("poster_url"),
        "status": row.get("status", "ACTIVE"),
    }


def ticket_dto(ticket: dict[str, Any], order: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    return {
        "ticketCode": ticket["ticket_code"],
        "orderCode": order["order_code"],
        "eventId": event["id"],
        "eventTitle": event["title"],
        "firstName": order["customer_first_name"],
        "lastName": order["customer_last_name"],
        "telegramId": order.get("telegram_id"),
        "username": order.get("telegram_username"),
        "status": ticket.get("status"),
        "checkedInAt": ticket.get("checked_in_at"),
        "createdAt": ticket.get("created_at"),
    }


def order_dto(conn: Any, order: dict[str, Any]) -> dict[str, Any]:
    event = conn.events.find_one({"id": order["event_id"]})
    tickets = list(conn.tickets.find({"order_id": order["id"]}).sort("id", 1))
    return {
        "orderCode": order["order_code"],
        "event": event_dto(event),
        "customerFirstName": order["customer_first_name"],
        "customerLastName": order["customer_last_name"],
        "customerEmail": order.get("customer_email"),
        "customerPhone": order.get("customer_phone"),
        "telegramId": order.get("telegram_id"),
        "telegramUsername": order.get("telegram_username"),
        "ticketCount": order["ticket_count"],
        "totalAmount": order["total_amount"],
        "status": order["status"],
        "paymentComment": order.get("payment_comment"),
        "createdAt": order["created_at"],
        "tickets": [ticket_dto(ticket, order, event) for ticket in tickets],
    }
