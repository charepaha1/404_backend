from __future__ import annotations

from typing import Any

from pymongo import ASCENDING, DESCENDING, MongoClient, ReturnDocument
from pymongo.database import Database

from auth import hash_password
from config import MONGO_DB, MONGO_URI
from utils import now_iso

_client: MongoClient | None = None


class MongoContext:
    def __enter__(self) -> Database:
        return mongo()

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        return None


def mongo() -> Database:
    global _client
    if _client is None:
        _client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=4000)
        _client.admin.command("ping")
    return _client[MONGO_DB]


def db() -> MongoContext:
    return MongoContext()


def next_id(conn: Database, name: str) -> int:
    max_row = conn[name].find_one(sort=[("id", DESCENDING)])
    max_id = int((max_row or {}).get("id") or 0)
    conn.counters.update_one(
        {"_id": name},
        {"$max": {"seq": max_id}},
        upsert=True,
    )
    counter = conn.counters.find_one_and_update(
        {"_id": name},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return int(counter["seq"])


def init_db() -> None:
    # Prepare MongoDB for a fresh run: indexes, default admin and a demo event.
    conn = mongo()

    conn.users.create_index([("id", ASCENDING)], unique=True)
    conn.users.create_index([("email_lc", ASCENDING)], unique=True)
    conn.events.create_index([("id", ASCENDING)], unique=True)
    conn.events.create_index([("start_at", ASCENDING)])
    conn.orders.create_index([("id", DESCENDING)], unique=True)
    conn.orders.create_index([("order_code", ASCENDING)], unique=True)
    conn.orders.create_index([("telegram_id", ASCENDING)])
    conn.tickets.create_index([("id", ASCENDING)], unique=True)
    conn.tickets.create_index([("ticket_code", ASCENDING)], unique=True)
    conn.tickets.create_index([("order_id", ASCENDING)])

    if not conn.users.find_one({"email_lc": "admin@404.local"}):
        conn.users.insert_one(
            {
                "id": next_id(conn, "users"),
                "email": "admin@404.local",
                "email_lc": "admin@404.local",
                "password_hash": hash_password("admin404"),
                "full_name": "404 Admin",
                "phone": None,
                "telegram_id": None,
                "telegram_username": None,
                "role": "ADMIN",
                "created_at": now_iso(),
            }
        )

    if conn.events.count_documents({}) == 0:
        conn.events.insert_one(
            {
                "id": next_id(conn, "events"),
                "title": "404 Launch Night",
                "subtitle": "First Mongo-backed event",
                "description": "Demo event seeded by the Python backend.",
                "venue": "Warehouse 404",
                "city": "Almaty",
                "start_at": "2026-06-14T23:00:00",
                "price": 3000,
                "currency": "KZT",
                "payment_details": "Kaspi: +7 700 000 00 00\nComment: order code",
                "poster_url": None,
                "status": "ACTIVE",
                "created_at": now_iso(),
            }
        )
