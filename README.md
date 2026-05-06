# Multi-Market Screener

PySide6 기반으로 Kiwoom REST API에서 `KOSPI`, `KOSDAQ` 종목을 조회하고, 가격/거래량/재무 스냅샷 기반 스크리너와 LLM 분석 결과를 표시하는 데스크톱 앱입니다. 차트는 메인 화면에서 분리된 별도 창으로 표시합니다.

## Features

- Kiwoom REST API 기반 KOSPI / KOSDAQ / KRX ALL 시장 목록 로딩
- DataFrame-backed `QTableView` 종목 목록으로 KRX ALL 같은 대량 목록 렌더링 지연 최소화
- 종목명/코드 검색 및 Enter 기반 차트 갱신
- 메뉴바 기반 스크리너 조건 설정 / 적용 / 초기화
- VSPilot0023 스타일 조건식 테이블 기반 가격/거래량/이동평균/재무 스냅샷 스크리닝
- 키움 `ka10001` 기본정보 기반 PER / PBR / ROE / EPS / BPS / 매출액 / 영업이익 / 순이익 표시
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
- worker는 plain Python 데이터만 계산하고, 모든 Qt UI와 차트 상태 갱신은 메인 GUI 스레드에서만 수행합니다.
- 종목 목록 UI는 `QTableWidgetItem` 대량 생성 대신 `QAbstractTableModel`이 화면에 필요한 셀만 제공하는 구조입니다.
- 차트는 QtCharts 대신 `QWidget.paintEvent()` 기반 QPainter 렌더러로 직접 그립니다.
- 차트 갱신은 plain Python OHLCV 데이터를 위젯 상태로 교체한 뒤 `update()`로 repaint합니다.
- X축은 실제 달력 간격 대신 `거래일 인덱스` 기준으로 압축해 렌더링하고, 축 라벨만 실제 날짜 문자열로 표시합니다.
- hover 갱신은 차트 위젯 내부 mouse event 상태만 바꾸고 직접 repaint합니다.
- 종료 시에는 차트 타이머를 멈추고, worker queue를 비우고, 대기 후 창을 닫도록 정리했습니다.
- 차트 창은 앱 시작 시 즉시 만들지 않고, 종목 선택/차트 열기 시점에 parent 없는 별도 top-level window로 lazy 생성합니다.
- 데이터 backend는 Kiwoom REST API를 사용합니다.
- 종목 목록은 `ka10099`, 일봉 차트는 `ka10081`, 기본정보/재무 스냅샷은 `ka10001`을 사용합니다.
- `ka10001` 재무 필드는 상세 재무제표가 아니라 키움 기본정보 스냅샷입니다. 문서상 일부 필드는 외부 벤더 제공 데이터이며 실시간 갱신값이 아닐 수 있습니다.
- Kiwoom REST backend 전환 이후 현재 지원 시장은 국내 주식 `KOSPI`, `KOSDAQ`, `KRX_ALL`입니다.
- 상장 목록은 `Code`와 `Name`이 있는 종목을 기준으로 유지합니다.
- 가격 조회 실패 종목은 현재 목록에서 제외됩니다.
- 세션 저장에는 `PyYAML`이 필요합니다.
- LLM은 개별 종목 분석에만 사용하며, 스크리너 조건 해석에는 사용하지 않습니다.
- LLM은 OpenAI 호환 `chat/completions` 엔드포인트를 가정합니다.
- LLM / Telegram 설정은 루트 `config.yaml`에 저장되며, 저장소에는 `config.example.yaml`만 포함합니다.
- Kiwoom appkey / secretkey도 루트 `config.yaml`의 `kiwoom` 섹션에 저장합니다. `config.example.yaml`은 포맷과 빈 값만 포함하고, `config.yaml`은 git 추적 대상이 아닙니다.
- LLM 네트워크 오류는 `HTTPError`, `URLError`, timeout, `OSError`를 읽기 쉬운 메시지로 정규화합니다.

## Kiwoom REST

```yaml
kiwoom:
  enabled: true
  mock: false
  base_url: "https://api.kiwoom.com"
  mock_base_url: "https://mockapi.kiwoom.com"
  websocket_url: "wss://api.kiwoom.com:10000"
  mock_websocket_url: "wss://mockapi.kiwoom.com:10000"
  appkey: "YOUR_KIWOOM_APPKEY"
  secretkey: "YOUR_KIWOOM_SECRETKEY"
  token_cache_enabled: true
```

- `Market > Kiwoom REST 설정`에서 저장할 수 있습니다.
- `Market > Kiwoom REST 연결 테스트`는 토큰 발급 후 KOSPI 종목 목록 `ka10099`를 호출합니다.
- 접근토큰은 설정 파일에 저장하지 않고 런타임 메모리에만 보관합니다.

## Telegram

- 메뉴바:
  - `Telegram > Telegram 설정`
  - `Telegram > 세션 리포트 발송`
  - `Telegram > LLM 결과 발송`
- 우측 UI:
  - `세션 요약과 기술 리포트` 탭의 `Telegram 발송`
  - `LLM 프롬프트와 Markdown` 탭의 `Telegram 발송`

## Screening Conditions

- `Screening > 조건 설정`에서 조건 행 테이블을 편집합니다.
- 조건 행은 사용 여부, 조건명, `AND/OR`, `MA 정배열`, `MA 비교`, PER/PBR/ROE/EPS/BPS, 매출액/영업이익/순이익, 시가총액/외인비율, 거래량/거래량MA20/거래량배율을 지원합니다.
- 지표 칸은 `<5`, `>10`, `>=0`, `<=100000`, `>2,<10` 형식을 지원합니다.
- `Screening > 조건 적용`으로 현재 시장 목록에 적용합니다.
- 왼쪽 패널에는 `처리/전체`, 매칭 수, 실패 수, 진행률, 경과 시간, 예상 남은 시간이 표시됩니다.
- `Stop` 버튼으로 현재 종목 처리 후 스크리닝을 중지하고, 지금까지 매칭된 결과를 표시합니다.
- `Screening > 스크리너 초기화`로 전체 목록으로 되돌립니다.

## LLM Notes

- OpenAI 호환 API 호출은 기본적으로 `stream: true`로 전송합니다.
- 서버가 `text/event-stream`을 반환하면 줄 단위 스트리밍 파싱을 사용합니다.
- 일반 JSON 응답도 fallback 처리합니다.
- 스크리닝은 메뉴 조건창에서 선택한 로컬 조건만 사용합니다.
- 분석 LLM 응답은 `한줄 요약 / 핵심 근거 / 리스크 / 체크포인트` 구조로 정리합니다.

## Status

- 현재 구현 상태와 최근 구조 변경은 [Current_Status.md](/Users/jaehyukshim/Documents/CODEX/CDXPilot0002/Current_Status.md) 에 기록합니다.
