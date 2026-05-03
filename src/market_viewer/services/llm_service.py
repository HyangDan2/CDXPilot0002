from __future__ import annotations

import pandas as pd

from market_viewer.llm.client import send_chat_completion
from market_viewer.llm.prompt_builder import build_system_prompt, build_user_prompt
from market_viewer.llm.response_utils import normalize_analysis_response, normalize_connection_test_response
from market_viewer.models import FundamentalSnapshot, LLMConfig, StockReference


def run_connection_test(config: LLMConfig) -> str:
    response = send_chat_completion(
        config,
        "응답은 짧게 작성하라.",
        "연결 테스트입니다. OK 한 단어로만 답해줘.",
    )
    return normalize_connection_test_response(response)


def run_stock_analysis(
    *,
    config: LLMConfig,
    active_layer_ids: list[str],
    stock: StockReference,
    frame: pd.DataFrame,
    filter_prompt: str,
    user_request: str,
    fundamental_snapshot: FundamentalSnapshot | None = None,
) -> str:
    system_prompt = build_system_prompt(active_layer_ids)
    user_prompt = build_user_prompt(stock, frame, filter_prompt, user_request, fundamental_snapshot)
    response = send_chat_completion(config, system_prompt, user_prompt)
    return normalize_analysis_response(response)
