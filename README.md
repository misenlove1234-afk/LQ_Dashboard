# 선실부 현황 대시보드 v2.0

## 📁 폴더 구조

```
선실부_대시보드/
├── app.py                  ← 라우팅 전용 (건드리지 마세요)
├── .env                    ← DB 연결 정보 (git 제외!)
├── .env.example            ← .env 작성 양식
├── requirements.txt
│
├── utils/
│   ├── __init__.py
│   └── db.py               ← SQL Server 연결 공통 함수
│
├── data/                   ← 🔴 데이터 처리 전용 (UI 코드 금지)
│   ├── kpi_1_data.py ~ kpi_6_data.py
│   └── proc_1_data.py ~ proc_6_data.py
│
└── pages/                  ← 🔵 화면 렌더링 전용 (DB 직접 접근 금지)
    ├── kpi_1.py ~ kpi_6.py
    └── proc_1.py ~ proc_6.py
```

## ▶️ 실행 방법

```bash
# 1. 의존성 설치
pip install -r requirements.txt

# 2. .env 파일 생성
cp .env.example .env
# .env 파일을 열어 DB 정보 입력

# 3. 앱 실행
streamlit run app.py
```

## 📝 새 메뉴 작업 순서

1. `data/메뉴명_data.py` 에서 DB 쿼리 & 계산 로직 작성
2. `pages/메뉴명.py` 에서 `render()` 함수 안에 UI 작성
3. `app.py` 는 수정하지 않아도 됩니다

## ⚠️ 규칙 요약

| 파일 위치 | 할 수 있는 것 | 하면 안 되는 것 |
|---|---|---|
| `data/` | run_query, 계산, DataFrame 반환 | st.write, st.chart 등 UI |
| `pages/` | st.* UI 코드, 차트, 테이블 | run_query, for문 연산 |
| `utils/db.py` | DB 연결, 쿼리 실행 | 비즈니스 로직, UI |
| `app.py` | 라우팅, 네비게이션 | 직접 데이터 처리 |
