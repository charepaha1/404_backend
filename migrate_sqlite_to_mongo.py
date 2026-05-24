from __future__ import annotations

import sqlite3

from config import DB_PATH
from database import init_db, mongo


def rows(conn: sqlite3.Connection, table: str) -> list[sqlite3.Row]:
    try:
        return conn.execute(f"SELECT * FROM {table}").fetchall()
    except sqlite3.Error:
        return []


def main() -> None:
    if not DB_PATH.exists():
        print(f"SQLite file not found: {DB_PATH}")
        return

    init_db()
    target = mongo()
    source = sqlite3.connect(DB_PATH)
    source.row_factory = sqlite3.Row

    counts: dict[str, int] = {}
    for user in rows(source, "users"):
        doc = dict(user)
        doc["email_lc"] = doc["email"].lower()
        target.users.update_one({"id": doc["id"]}, {"$set": doc}, upsert=True)
        counts["users"] = counts.get("users", 0) + 1

    for event in rows(source, "events"):
        target.events.update_one({"id": event["id"]}, {"$set": dict(event)}, upsert=True)
        counts["events"] = counts.get("events", 0) + 1

    for order in rows(source, "orders"):
        target.orders.update_one({"id": order["id"]}, {"$set": dict(order)}, upsert=True)
        counts["orders"] = counts.get("orders", 0) + 1

    for ticket in rows(source, "tickets"):
        target.tickets.update_one({"id": ticket["id"]}, {"$set": dict(ticket)}, upsert=True)
        counts["tickets"] = counts.get("tickets", 0) + 1

    for name in ("users", "events", "orders", "tickets"):
        max_doc = target[name].find_one(sort=[("id", -1)])
        if max_doc:
            target.counters.update_one({"_id": name}, {"$max": {"seq": int(max_doc["id"])}}, upsert=True)

    source.close()
    print("Migrated:", counts)


if __name__ == "__main__":
    main()
