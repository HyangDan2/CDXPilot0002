from __future__ import annotations

import json
from urllib import error, parse, request

from market_viewer.models import TelegramConfig


def send_telegram_report(config: TelegramConfig, title: str, markdown: str) -> int:
    if not config.connection_ready:
        raise ValueError("Telegram Bot Token과 Chat ID를 먼저 설정하세요.")

    message = _build_message(title, markdown)
    sent = 0
    for chunk in _split_message(message):
        _send_message_chunk(config, chunk)
        sent += 1
    return sent


def _send_message_chunk(config: TelegramConfig, text: str) -> None:
    url = f"https://api.telegram.org/bot{config.bot_token}/sendMessage"
    payload = parse.urlencode(
        {
            "chat_id": config.chat_id,
            "text": text,
            "disable_web_page_preview": "true",
        }
    ).encode("utf-8")
    req = request.Request(url, data=payload, method="POST")
    try:
        with request.urlopen(req, timeout=30) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise ValueError(f"Telegram 전송 실패: HTTP {exc.code} - {detail[:400]}") from exc

    body = json.loads(raw)
    if not body.get("ok"):
        raise ValueError(f"Telegram 전송 실패: {body}")


def _build_message(title: str, markdown: str) -> str:
    cleaned_markdown = markdown.strip() or "내용이 없습니다."
    return f"{title}\n\n{cleaned_markdown}".strip()


def _split_message(text: str, limit: int = 3800) -> list[str]:
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    current = text
    while len(current) > limit:
        split_at = current.rfind("\n", 0, limit)
        if split_at <= 0:
            split_at = limit
        chunks.append(current[:split_at].strip())
        current = current[split_at:].strip()
    if current:
        chunks.append(current)
    return chunks
