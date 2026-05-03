# Multi-Market Screener

PySide6 기반으로 `KOSPI`, `KOSDAQ`, `TSE` 종목을 조회하고, 가격/거래량 기반 스크리너와 LLM 분석 결과를 표시하는 데스크톱 앱입니다. 차트는 메인 화면에서 분리된 별도 창으로 표시합니다.

## Features

- KOSPI / KOSDAQ / TSE / ALL 시장 목록 로딩
- 종목 검색
- 메뉴바 기반 스크리너 조건 설정 / 적용 / 초기화
- 가격/거래량/이동평균 기반 하드코딩 스크리닝
- 일봉 OHLCV 조회
- 별도 차트 창의 캔들스틱 차트 + 종가 선 그래프
- 이동평균선 5/20/60/224
- 차트 드래그/휠 줌/더블클릭 리셋
- 거래일 압축 축으로 주말/휴장일 빈칸 제거
- 하단 거래량 오버레이
- hover 시 OHLCV / 거래량 / 전일대비 표시
- 세션 요약 Markdown + 정량 리포트 테이블
- LLM 분석 요청/결과 Markdown
- Telegram 리포트 발송
- YAML 세션 저장/불러오기

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

If your local environment already has an older PySide build, reinstall the pinned runtime:

```bash
pip install --upgrade --force-reinstall PySide6==6.11.0 shiboken6==6.11.0
```

## Run

```bash
PYTHONPATH=src python -m market_viewer.main
```

## Notes

- `PySide6` / `shiboken6`는 2026-05-01 기준 PyPI 최신 릴리스인 `6.11.0`에 맞춰 고정했습니다.
- 현재 로컬 런타임이 다른 버전이면, `requirements.txt`를 바꿔도 실제 실행 환경은 자동으로 바뀌지 않으므로 위 재설치 명령으로 맞춰야 합니다.
- worker는 plain Python 데이터만 계산하고, 모든 Qt UI/QtCharts 갱신은 메인 GUI 스레드에서만 수행합니다.
- 차트는 `QChart / QLineSeries / QCandlestickSeries / QValueAxis`를 매번 재생성하지 않고, `self` 속성으로 오래 유지한 뒤 데이터만 교체합니다.
- 차트 갱신은 직접 즉시 반영하지 않고, 메인 스레드 `QTimer` 배치 flush를 통해 제한된 주기로 적용합니다.
- X축은 실제 달력 간격 대신 `거래일 인덱스` 기준으로 압축해 렌더링하고, 축 라벨만 실제 날짜 문자열로 표시합니다.
- hover 갱신도 별도 메인 스레드 타이머로 coalescing 하여, repaint/hover/series update가 같은 이벤트 루프에서 과도하게 충돌하지 않도록 줄였습니다.
- 종료 시에는 차트 타이머를 멈추고, worker queue를 비우고, 대기 후 창을 닫도록 정리했습니다.
- 재무지표/재무제표 조회는 현재 앱 범위에서 제거했습니다. `pykrx` 기반 재무 API와 KRX 로그인 환경변수 경로를 호출하지 않습니다.
- `TSE` 시장은 목록 로드 직후 자동 가격 조회를 하지 않으며, 사용자가 종목을 선택했을 때만 가격을 조회합니다.
- 상장 목록은 `Code`와 `Name`이 있는 종목을 기준으로 유지합니다.
- 가격 조회 실패 종목은 현재 목록에서 제외됩니다.
- 세션 저장에는 `PyYAML`이 필요합니다.
- LLM은 개별 종목 분석에만 사용하며, 스크리너 조건 해석에는 사용하지 않습니다.
- LLM은 OpenAI 호환 `chat/completions` 엔드포인트를 가정합니다.
- LLM / Telegram 설정은 루트 `config.yaml`에 저장되며, 저장소에는 `config.example.yaml`만 포함합니다.
- LLM 네트워크 오류는 `HTTPError`, `URLError`, timeout, `OSError`를 읽기 쉬운 메시지로 정규화합니다.

## Telegram

- 메뉴바:
  - `Telegram > Telegram 설정`
  - `Telegram > 세션 리포트 발송`
  - `Telegram > LLM 결과 발송`
- 우측 UI:
  - `세션 요약과 기술 리포트` 탭의 `Telegram 발송`
  - `LLM 프롬프트와 Markdown` 탭의 `Telegram 발송`

## Screening Conditions

- `Screening > 조건 설정`에서 정배열, 역배열, MA 크로스, MA224 상단, 거래량 비율, 60일 신고가 조건을 조합합니다.
- `Screening > 조건 적용`으로 현재 시장 목록에 적용합니다.
- `Screening > 스크리너 초기화`로 전체 목록으로 되돌립니다.

## LLM Notes

- OpenAI 호환 API 호출은 기본적으로 `stream: true`로 전송합니다.
- 서버가 `text/event-stream`을 반환하면 줄 단위 스트리밍 파싱을 사용합니다.
- 일반 JSON 응답도 fallback 처리합니다.
- 스크리닝은 메뉴 조건창에서 선택한 로컬 조건만 사용합니다.
- 분석 LLM 응답은 `한줄 요약 / 핵심 근거 / 리스크 / 체크포인트` 구조로 정리합니다.

## Status

- 현재 구현 상태와 최근 구조 변경은 [Current_Status.md](/Users/jaehyukshim/Documents/CODEX/CDXPilot0002/Current_Status.md) 에 기록합니다.
