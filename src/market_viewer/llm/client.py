from __future__ import annotations

import json
from typing import Any
from urllib import error, request

from market_viewer.models import LLMConfig


def send_chat_completion(config: LLMConfig, system_prompt: str, user_prompt: str) -> str:
    if not config.connection_ready:
        raise ValueError("LLM 연결 정보가 충분하지 않습니다.")

    payload = {
        "model": config.model,
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
        "stream": True,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    data = json.dumps(payload).encode("utf-8")
    url = config.base_url.rstrip("/") + "/chat/completions"

    req = request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream, application/json",
        },
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=config.timeout_seconds) as response:
            content_type = response.headers.get("Content-Type", "")
            if "text/event-stream" in content_type:
                return _read_streaming_response(response)
            raw_body = response.read()
    except error.HTTPError as exc:
        raw_error = exc.read().decode("utf-8", errors="replace")
        raise ValueError(f"LLM 요청 실패: HTTP {exc.code} - {raw_error[:500]}") from exc
    except error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        raise ValueError(f"LLM 네트워크 연결 실패: {reason}") from exc
    except TimeoutError as exc:
        raise ValueError(f"LLM 요청 시간 초과: {config.timeout_seconds}초") from exc
    except OSError as exc:
        raise ValueError(f"LLM 전송 중 시스템/소켓 오류: {exc}") from exc

    try:
        body = json.loads(raw_body.decode("utf-8", errors="replace"))
    except json.JSONDecodeError as exc:
        snippet = raw_body.decode("utf-8", errors="replace")[:500]
        raise ValueError(f"LLM JSON 응답을 해석하지 못했습니다: {snippet}") from exc
    return _extract_content_from_json(body)


def _read_streaming_response(response) -> str:
    content_parts: list[str] = []
    last_payload: dict[str, Any] | None = None
    for raw_line in response:
        line = raw_line.decode("utf-8", errors="replace").strip()
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if not data or data == "[DONE]":
            continue
        try:
            payload = json.loads(data)
        except json.JSONDecodeError:
            continue
        last_payload = payload

        text = _extract_content_from_json(payload, allow_empty=True)
        if text:
            content_parts.append(text)
    streamed = "".join(content_parts).strip()
    if streamed:
        return streamed
    if last_payload is not None:
        extracted = _extract_content_from_json(last_payload, allow_empty=True)
        if extracted:
            return extracted
    raise ValueError("LLM 스트리밍 응답에서 텍스트 콘텐츠를 추출하지 못했습니다.")


def _extract_content_from_json(body: dict[str, Any], allow_empty: bool = False) -> str:
    direct_text = body.get("output_text")
    if isinstance(direct_text, str) and direct_text.strip():
        return direct_text.strip()

    choices = body.get("choices") or []
    if not choices:
        if allow_empty:
            return ""
        raise ValueError("LLM 응답에 choices가 없습니다.")

    first_choice = choices[0]
    message = first_choice.get("message", {})
    delta = first_choice.get("delta", {})

    for content_candidate in (
        message.get("content", ""),
        delta.get("content", ""),
        first_choice.get("text", ""),
    ):
        extracted = _normalize_content(content_candidate)
        if extracted:
            return extracted

    if allow_empty:
        return ""
    raise ValueError("LLM 응답에서 텍스트 콘텐츠를 추출하지 못했습니다.")


def _normalize_content(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, dict):
                for key in ("text", "content"):
                    value = part.get(key)
                    if isinstance(value, str) and value.strip():
                        parts.append(value.strip())
                        break
        return "\n".join(parts).strip()
    return ""
