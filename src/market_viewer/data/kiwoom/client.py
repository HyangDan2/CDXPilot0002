from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import json
from urllib import request
from urllib.error import HTTPError, URLError

from market_viewer.data.kiwoom import endpoints
from market_viewer.data.kiwoom.errors import KiwoomApiError, KiwoomAuthError, KiwoomConfigError, KiwoomSchemaError
from market_viewer.models import KiwoomConfig


@dataclass(slots=True)
class KiwoomResponse:
    payload: dict
    cont_yn: str = "N"
    next_key: str = ""


class KiwoomRestClient:
    def __init__(self, config: KiwoomConfig, timeout_seconds: int = 12) -> None:
        self._config = config
        self._timeout_seconds = timeout_seconds
        self._token = ""
        self._token_expires_at: datetime | None = None

    def test_connection(self) -> str:
        self._ensure_token()
        response = self.post(endpoints.API_STOCK_LIST, endpoints.STOCK_INFO, {"mrkt_tp": "0"})
        count = len(response.payload.get("list", []))
        mode = "모의투자" if self._config.mock else "운영"
        return f"키움 REST 연결 확인 완료 ({mode}, KOSPI 종목 {count}개 응답)"

    def post(self, api_id: str, path: str, body: dict, *, cont_yn: str = "N", next_key: str = "") -> KiwoomResponse:
        token = self._ensure_token()
        headers = {
            "Content-Type": "application/json;charset=UTF-8",
            "Accept": "application/json",
            "api-id": api_id,
            "authorization": f"Bearer {token}",
            "cont-yn": cont_yn,
            "next-key": next_key,
        }
        payload, response_headers = self._post_json(path, body, headers)
        self._raise_for_return_code(payload)
        return KiwoomResponse(
            payload=payload,
            cont_yn=response_headers.get("cont-yn", payload.get("cont_yn", "N")),
            next_key=response_headers.get("next-key", payload.get("next_key", "")),
        )

    def post_all_pages(self, api_id: str, path: str, body: dict, *, list_key: str, max_pages: int = 20) -> list[dict]:
        rows: list[dict] = []
        cont_yn = "N"
        next_key = ""
        for _ in range(max_pages):
            response = self.post(api_id, path, body, cont_yn=cont_yn, next_key=next_key)
            candidate = response.payload.get(list_key, [])
            if not isinstance(candidate, list):
                raise KiwoomSchemaError(f"{api_id} 응답에서 {list_key} 목록을 찾지 못했습니다.")
            rows.extend(row for row in candidate if isinstance(row, dict))
            if response.cont_yn != "Y" or not response.next_key:
                break
            cont_yn = "Y"
            next_key = response.next_key
        return rows

    def _ensure_token(self) -> str:
        if not self._config.connection_ready:
            raise KiwoomConfigError("키움 REST appkey/secretkey 또는 base URL 설정이 필요합니다.")
        if self._token and self._token_expires_at and datetime.now() < self._token_expires_at - timedelta(minutes=5):
            return self._token
        self._issue_token()
        return self._token

    def _issue_token(self) -> None:
        headers = {
            "Content-Type": "application/json;charset=UTF-8",
            "Accept": "application/json",
            "api-id": endpoints.API_TOKEN,
        }
        body = {
            "grant_type": "client_credentials",
            "appkey": self._config.appkey,
            "secretkey": self._config.secretkey,
        }
        payload, _ = self._post_json(endpoints.TOKEN, body, headers)
        self._raise_for_return_code(payload)
        token = str(payload.get("token") or "").strip()
        if not token:
            raise KiwoomAuthError("키움 접근토큰 응답에 token이 없습니다.")
        self._token = token
        self._token_expires_at = self._parse_expiry(str(payload.get("expires_dt") or ""))

    def _post_json(self, path: str, body: dict, headers: dict[str, str]) -> tuple[dict, dict[str, str]]:
        url = self._config.rest_base_url.rstrip("/") + path
        raw_body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        req = request.Request(url, data=raw_body, headers=headers, method="POST")
        try:
            with request.urlopen(req, timeout=self._timeout_seconds) as response:
                raw = response.read().decode("utf-8", errors="replace")
                response_headers = {key.lower(): value for key, value in response.headers.items()}
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise KiwoomApiError(f"키움 REST HTTP {exc.code}: {detail}") from exc
        except URLError as exc:
            raise KiwoomApiError(f"키움 REST 네트워크 오류: {exc.reason}") from exc
        except OSError as exc:
            raise KiwoomApiError(f"키움 REST 호출 실패: {exc}") from exc
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise KiwoomSchemaError(f"키움 REST 응답이 JSON이 아닙니다: {raw[:300]}") from exc
        if not isinstance(payload, dict):
            raise KiwoomSchemaError("키움 REST 응답 payload가 object가 아닙니다.")
        return payload, response_headers

    @staticmethod
    def _raise_for_return_code(payload: dict) -> None:
        code = payload.get("return_code", 0)
        if str(code) not in {"0", ""}:
            message = str(payload.get("return_msg") or "알 수 없는 오류")
            raise KiwoomApiError(f"키움 REST 오류 {code}: {message}")

    @staticmethod
    def _parse_expiry(value: str) -> datetime:
        try:
            return datetime.strptime(value, "%Y%m%d%H%M%S")
        except ValueError:
            return datetime.now() + timedelta(hours=12)
