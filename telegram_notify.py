from __future__ import annotations

import html
import urllib.parse
import urllib.request
from typing import Any

from config import ADMIN_IDS, TELEGRAM_BOT_TOKEN
from schemas import order_dto


def _send_message(chat_id: int, text: str) -> None:
    if not TELEGRAM_BOT_TOKEN:
        return

    data = urllib.parse.urlencode(
        {
            "chat_id": str(chat_id),
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": "true",
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
        data=data,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        response.read()


def notify_payment_claim(conn: Any, order: dict[str, Any]) -> None:
    if not ADMIN_IDS or not TELEGRAM_BOT_TOKEN:
        return

    payload = order_dto(conn, order)
    tickets = payload.get("tickets", [])
    ticket_lines = "\n".join(
        f"• <code>#{html.escape(str(ticket.get('ticketCode') or ''))}</code>"
        for ticket in tickets
    )
    comment = str(payload.get("paymentComment") or "").strip()
    comment_block = (
        f"\n\n🛰 <b>Комментарий к оплате</b>\n<i>{html.escape(comment)}</i>"
        if comment
        else "\n\nКомментарий к оплате: <i>без комментария</i>"
    )
    contact_parts = [
        payload.get("customerPhone"),
        payload.get("customerEmail"),
        payload.get("telegramUsername"),
    ]
    contact = " / ".join(str(part) for part in contact_parts if part)

    text = (
        "<pre>ROOT // SITE PAYMENT PING</pre>\n"
        f"⌁ Заказ: <code>#{html.escape(str(payload.get('orderCode') or ''))}</code>\n"
        f"⌁ Пользователь: <b>{html.escape(str(payload.get('customerFirstName') or ''))} "
        f"{html.escape(str(payload.get('customerLastName') or ''))}</b>\n"
        f"⌁ Контакт: <b>{html.escape(contact or 'не указан')}</b>\n"
        f"⌁ Событие: <b>{html.escape(str((payload.get('event') or {}).get('title') or ''))}</b>\n"
        f"⌁ Билетов: <b>{len(tickets)}</b>\n\n"
        "ID для подтверждения:\n"
        f"{ticket_lines}"
        f"{comment_block}"
    )

    for admin_id in ADMIN_IDS:
        try:
            _send_message(admin_id, text)
        except Exception:
            continue
