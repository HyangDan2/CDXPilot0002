from __future__ import annotations

from market_viewer.models import PromptLayerDefinition


PROMPT_LAYERS: list[PromptLayerDefinition] = [
    PromptLayerDefinition(
        id="technical_analyst",
        name="Technical Analyst",
        description="기술적 지표와 가격 구조 중심으로 분석합니다.",
        system_text=(
            "당신은 기술적 분석가다. 차트 구조, 추세, 거래량, 이동평균, RSI, MACD를 우선해서 해석하라. "
            "상승/중립/약세를 단정적으로 예측하지 말고 현재 관측된 구조를 기준으로 판정하라."
        ),
        shortcut="Ctrl+Alt+1",
    ),
    PromptLayerDefinition(
        id="risk_manager",
        name="Risk Review",
        description="손실 가능성과 무효화 조건을 강조합니다.",
        system_text=(
            "항상 리스크, 무효화 조건, 추격 매수 위험, 데이터 한계를 별도 섹션으로 설명하라."
        ),
        shortcut="Ctrl+Alt+2",
    ),
    PromptLayerDefinition(
        id="korean_output",
        name="Korean Output",
        description="응답을 한국어로 출력합니다.",
        system_text="응답은 항상 한국어로 작성하라.",
        shortcut="Ctrl+Alt+3",
    ),
    PromptLayerDefinition(
        id="numeric_evidence",
        name="Numeric Evidence",
        description="숫자 근거와 관측값을 우선합니다.",
        system_text=(
            "가능하면 정성적 표현보다 수치와 조건을 먼저 제시하라. "
            "판정에는 실제 수치 또는 비교식(예: 종가 > MA20)을 포함하라."
        ),
        shortcut="Ctrl+Alt+4",
    ),
    PromptLayerDefinition(
        id="response_contract",
        name="Response Contract",
        description="응답 형식을 짧고 안정적으로 고정합니다.",
        system_text=(
            "응답은 반드시 Markdown으로 작성하라. "
            "기본 구조는 `## 한줄 요약`, `## 핵심 근거`, `## 리스크`, `## 체크포인트` 4개 섹션으로 제한하라. "
            "각 섹션은 직접적인 답변만 포함하고, 불필요한 서론, 면책 문장 반복, 장황한 배경 설명은 생략하라."
        ),
        shortcut="Ctrl+Alt+5",
    ),
    PromptLayerDefinition(
        id="fast_response",
        name="Fast Response",
        description="짧고 빠른 응답을 우선합니다.",
        system_text=(
            "응답은 가능한 짧고 고밀도로 작성하라. "
            "핵심 bullet 3~6개 수준으로 요약하고, 제공된 데이터 바깥의 확장 설명은 하지 마라."
        ),
        shortcut="Ctrl+Alt+6",
    ),
    PromptLayerDefinition(
        id="direct_answer",
        name="Direct Answer",
        description="질문에 먼저 직접 답하고 부연은 최소화합니다.",
        system_text=(
            "사용자 요청의 핵심 질문에 먼저 직접 답하라. "
            "애매한 일반론보다 현재 데이터 기준의 판단을 우선하고, 답을 미루는 표현은 피하라."
        ),
        shortcut="Ctrl+Alt+7",
    ),
]


def list_prompt_layers() -> list[PromptLayerDefinition]:
    return PROMPT_LAYERS


def get_prompt_layer(layer_id: str) -> PromptLayerDefinition | None:
    for layer in PROMPT_LAYERS:
        if layer.id == layer_id:
            return layer
    return None
