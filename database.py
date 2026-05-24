from __future__ import annotations

import sqlite3
from typing import Any

from auth import hash_password
from config import DATA_DIR, DB_PATH
from utils import now_iso


def db() -> sqlite3.Connection:
    DATA_DIR.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def one(conn: sqlite3.Connection, query: str, args: tuple[Any, ...] = ()) -> sqlite3.Row | None:
    return conn.execute(query, args).fetchone()


def init_db() -> None:
    with db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              email TEXT NOT NULL UNIQUE,
              password_hash TEXT NOT NULL,
              full_name TEXT NOT NULL,
              phone TEXT,
              telegram_id INTEGER,
              telegram_username TEXT,
              role TEXT NOT NULL DEFAULT 'USER',
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS events (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              title TEXT NOT NULL,
              subtitle TEXT,
              description TEXT,
              venue TEXT NOT NULL,
              city TEXT NOT NULL,
              start_at TEXT NOT NULL,
              price INTEGER NOT NULL,
              currency TEXT NOT NULL DEFAULT 'KZT',
              payment_details TEXT,
              poster_url TEXT,
              status TEXT NOT NULL DEFAULT 'ACTIVE',
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS orders (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              order_code TEXT NOT NULL UNIQUE,
              event_id INTEGER NOT NULL REFERENCES events(id),
              user_id INTEGER REFERENCES users(id),
              customer_first_name TEXT NOT NULL,
              customer_last_name TEXT NOT NULL,
              customer_email TEXT,
              customer_phone TEXT,
              telegram_id INTEGER,
              telegram_username TEXT,
              ticket_count INTEGER NOT NULL,
              total_amount INTEGER NOT NULL,
              status TEXT NOT NULL DEFAULT 'AWAITING_PAYMENT',
              payment_comment TEXT,
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS tickets (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              ticket_code TEXT NOT NULL UNIQUE,
              order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
              status TEXT NOT NULL DEFAULT 'AWAITING_PAYMENT',
              checked_in_at TEXT,
              created_at TEXT NOT NULL
            );
            """
        )

        if not one(conn, "SELECT id FROM users WHERE email = ?", ("admin@404.local",)):
            conn.execute(
                """
                INSERT INTO users (email, password_hash, full_name, role, created_at)
                VALUES (?, ?, ?, 'ADMIN', ?)
                """,
                ("admin@404.local", hash_password("admin404"), "404 Admin", now_iso()),
            )

        if not one(conn, "SELECT id FROM events"):
            conn.execute(
                """
                INSERT INTO events
                (title, subtitle, description, venue, city, start_at, price, currency, payment_details, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "404 Launch Night",
                    "First Python-backed event",
                    "Demo event seeded by the Python backend.",
                    "Warehouse 404",
                    "Almaty",
                    "2026-06-14T23:00:00",
                    3000,
                    "KZT",
                    "Kaspi: +7 700 000 00 00\nComment: order code",
                    "ACTIVE",
                    now_iso(),
                ),
            )
