from __future__ import annotations

import re


REQUIRED_HEADINGS = [
    "## 한줄 요약",
    "## 핵심 근거",
    "## 리스크",
    "## 체크포인트",
]


def normalize_analysis_response(text: str) -> str:
    cleaned = _strip_code_fences(text)
    cleaned = cleaned.strip()
    if not cleaned:
        return "## 한줄 요약\n데이터 부족\n\n## 핵심 근거\n- 응답이 비어 있습니다.\n\n## 리스크\n- LLM 응답이 비어 있습니다.\n\n## 체크포인트\n- 다시 시도해 주세요."

    first_heading_index = _find_first_required_heading(cleaned)
    if first_heading_index is not None:
        cleaned = cleaned[first_heading_index:].strip()

    sections = _extract_required_sections(cleaned)
    if sections:
        return "\n\n".join(sections).strip()
    return cleaned


def normalize_connection_test_response(text: str) -> str:
    upper_text = text.strip().upper()
    if upper_text == "OK":
        return "OK"
    if re.search(r"\bOK\b", upper_text):
        return "OK"
    return text.strip() or "응답 없음"


def _strip_code_fences(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned


def _find_first_required_heading(text: str) -> int | None:
    positions = [text.find(heading) for heading in REQUIRED_HEADINGS if heading in text]
    valid_positions = [position for position in positions if position >= 0]
    if not valid_positions:
        return None
    return min(valid_positions)


def _extract_required_sections(text: str) -> list[str]:
    sections: list[str] = []
    for index, heading in enumerate(REQUIRED_HEADINGS):
        start = text.find(heading)
        if start < 0:
            continue
        end = len(text)
        for next_heading in REQUIRED_HEADINGS[index + 1 :]:
            next_pos = text.find(next_heading, start + len(heading))
            if next_pos >= 0:
                end = min(end, next_pos)
        section = text[start:end].strip()
        if section:
            sections.append(section)
    return sections
