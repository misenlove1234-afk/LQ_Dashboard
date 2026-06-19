# CLAUDE.md — 선실부 대시보드 프로젝트

> Claude Code가 이 프로젝트에서 작업할 때 반드시 준수해야 할 규칙과 참조 정보 모음.

---

## 1. Claude Code 기본 행동 규칙

### 언어
- 모든 응답은 **한국어**로 작성
- 질문도 한국어로 할 것

### 작업 시작 전 필수 확인
- 사용자가 작업을 시작하면 **반드시 `git pull` 여부를 먼저 확인**
- git pull을 안 했으면 먼저 하도록 안내

### 작업 완료 후 필수 행동
- 코드 수정이 완료되면 **자동으로** 아래 순서로 GitHub에 반영
  1. `git add <변경된 파일만>` — `__pycache__`, `.claude/` 폴더 제외
  2. `git commit -m "작업 내용 요약"` — 한국어로 간결하게
  3. `git push`
- 커밋 메시지는 어떤 작업을 했는지 한국어로 작성

---

## 2. 프로젝트 개요

| 항목 | 내용 |
|---|---|
| **프로젝트명** | LQ All In One (선실부 대시보드) |
| **목적** | 조선소 생산 공정 및 KPI 관리. 비전문가(생산관리자)도 사용 가능한 내부 데이터 도구 |
| **실행 방법** | `streamlit run app.py` |
| **접속 주소** | http://localhost:8501 |

---

## 3. 프로젝트 구조

```
선실부_대시보드/
├── app.py                  # 진입점 — 라우팅, 홈 대시보드, 공통 UI
├── .env                    # DB 접속 정보 (Git 제외 필수)
├── .claude/
│   ├── settings.json       # Claude Code 프로젝트 권한 설정 (공유)
│   └── settings.local.json # Claude Code 로컬 권한 설정 (Git 제외)
├── .streamlit/
│   └── config.toml         # Streamlit 테마 설정
├── assets/
│   └── gantt_editor.html   # 간트 편집 HTML 컴포넌트
├── data/                   # 데이터 처리 전용 모듈 (UI 코드 금지)
│   ├── kpi_1_data.py       # 직영 능률/실동률
│   ├── kpi_2_data.py       # 글로벌 BEP 실적
│   ├── kpi_3_data.py       # 협력사 전망/실적
│   ├── kpi_4_data.py       # 월별 기성 전망
│   ├── kpi_5_data.py       # 프로젝트 예산 현황
│   ├── kpi_6_data.py       # 프로젝트별 Punch 현황
│   ├── kpi_7_data.py       # 용접 불량률
│   ├── proc_1_data.py      # 일일 작업허가서
│   ├── proc_2_data.py      # 사곡공장 선실 제작 현황 + 간트 편집
│   ├── proc_3_data.py      # 특수선 공정 현황
│   └── proc_4_data.py      # 전장 결선 자재 현황
├── pages/                  # 화면 렌더링 전용 모듈 (render() 함수만 작성)
│   ├── kpi_1.py ~ kpi_7.py
│   └── proc_1.py ~ proc_4.py
└── utils/
    ├── db.py               # DB 연결 유틸 (SQLAlchemy / pyodbc)
    └── access_log.py       # 접속자 식별 유틸 (get_client_user)
```

### 레이어 규칙
| 레이어 | 파일 | 허용 | 금지 |
|---|---|---|---|
| 진입/라우팅 | `app.py` | 모든 것 | - |
| 화면 | `pages/xxx.py` | `st.*` UI 코드, `data.*` import | DB 직접 연결 |
| 데이터 | `data/xxx_data.py` | DB 조회, 집계, 계산 | `st.write` 등 UI 코드 |
| 유틸 | `utils/` | 공통 연결/로그 | 비즈니스 로직 |

---

## 4. 개발 환경 및 기술 스택

| 분류 | 기술 |
|---|---|
| **언어** | Python 3.12 |
| **프레임워크** | Streamlit |
| **DB** | SQL Server (사내) + Azure 데이터마트 |
| **DB 드라이버** | SQLAlchemy (읽기), pyodbc (쓰기) |
| **시각화** | Plotly |
| **데이터 처리** | pandas |
| **DRM 파일 처리** | xlwings |
| **환경변수** | python-dotenv |

---

## 5. 코딩 컨벤션 및 아키텍처 규칙

- **모든 주석은 한국어**로 작성
- 비전문가 팀원을 위해 **코드 상단에 설정 변수 집중** (토글/상수 방식)
- deprecated pandas 메서드 사용 금지 — `append` → `pd.concat`
- DB 접속 정보는 반드시 `.env`에서 로드 (**하드코딩 절대 금지**)
- 읽기: `SQLAlchemy` / 쓰기: `pyodbc`
- 페이지 위젯 key는 반드시 `페이지명_` 접두사 사용 (예: `proc2_date`)
- `st.set_page_config()`는 `app.py`에서만 호출 — 하위 페이지에서 호출 금지
- 캐시 전략:
  - `@st.cache_resource` — DB 엔진, 이미지 등 앱 수명 동안 1회
  - `@st.cache_data(ttl=300)` — 쿼리/집계 결과 5분 갱신

### 자주 쓰는 패턴

#### DB 연결 (읽기)
```python
from utils.db import get_engine
engine = get_engine()
df = pd.read_sql("SELECT * FROM [테이블명]", engine)
```

#### DB 연결 (쓰기)
```python
from utils.db import execute_query
execute_query(
    "INSERT INTO 게시판 (제목, 작성자) VALUES (?, ?)",
    ("제목", "홍길동")
)
```

#### run_query 편의 함수 (5분 캐시 자동 적용)
```python
from utils.db import run_query
df = run_query("SELECT * FROM [lq_proc2_1]")
df = run_query("SELECT * FROM 게시판 WHERE 게시판구분 = ?", params=("proc2_main",))
```

#### DRM 파일 처리
```python
import xlwings as xw
app = xw.App(visible=False)
wb = app.books.open(filepath)
```

---

## 6. 보안 체크리스트

### Git 커밋 전 확인
- [ ] `.env` 파일이 스테이징에 포함되지 않았는가?
- [ ] DB 접속 정보(서버명, 계정, 비밀번호)가 코드에 하드코딩되어 있지 않은가?
- [ ] NAS 경로가 코드에 직접 작성되어 있지 않은가?
- [ ] `__pycache__/`, `*.pyc` 파일이 포함되지 않았는가?
- [ ] 외부 URL로 폰트/CSS/JS를 불러오는 코드가 없는가?

### 외부 리소스 로드 금지 (사내망 보안)

사내망 환경에서는 외부 서버(Google Fonts, CDN 등)로 나가는 요청이 차단되므로, 모든 리소스는 **시스템 폰트 또는 로컬 파일**만 사용한다.

```python
# ❌ 절대 금지 — 외부 서버 요청 발생
"@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR');"
'<link href="https://cdn.jsdelivr.net/..." rel="stylesheet">'

# ✅ 시스템 폰트 사용
"font-family: 'Malgun Gothic', '맑은 고딕', sans-serif;"   # 한글
"font-family: 'Segoe UI', sans-serif;"                     # 숫자/영문 강조
"font-family: 'Consolas', 'Courier New', monospace;"        # 고정폭
```

**승인된 시스템 폰트 목록**

| 용도 | 폰트 |
|---|---|
| 한글 본문 | `"Malgun Gothic"`, `"맑은 고딕"` |
| 숫자/KPI 강조 | `"Segoe UI"` |
| 고정폭(코드/수치) | `"Consolas"`, `"Courier New"` |

### SQL Injection 방지

```python
# ❌ 절대 금지 — f-string으로 쿼리 생성
query = f"SELECT * FROM 직원 WHERE 이름 = '{user_input}'"

# ✅ 파라미터 바인딩 필수
df = run_query("SELECT * FROM 직원 WHERE 이름 = ?", params=(user_input,))
```

### 예외처리 — 소스코드 유출 방지

```python
# ❌ 절대 금지 — 스택 트레이스, 경로, 쿼리 등이 화면에 노출됨
except Exception as e:
    st.error(e)       # 소스코드/경로 유출 위험
    st.exception(e)   # 절대 금지

# ✅ 반드시 이 패턴 사용
import logging, traceback
logger = logging.getLogger(__name__)

try:
    result = some_function()
except Exception as e:
    logger.error("오류: %s\n%s", e, traceback.format_exc())  # 서버 로그에만 기록
    st.error("오류가 발생했습니다. 관리자에게 문의해 주세요.")  # UI에는 일반 메시지만
    st.stop()
```

- `st.exception()` 사용 완전 금지
- 오류 메시지에 파일 경로·SQL 쿼리·환경변수명 포함 금지

### XSS 방지

```python
# ❌ 금지 — 사용자 입력을 HTML에 직접 삽입
st.markdown(f"<div>{user_input}</div>", unsafe_allow_html=True)

# ✅ 권장 — 입력 필드에 개인정보 경고 + 출력 시 이스케이프
st.text_input("검색어", placeholder="⚠️ 개인정보가 포함되지 않도록 주의해 주세요.")
st.text_area("내용", placeholder="⚠️ 주민등록번호, 연락처, 주소 등 개인정보를 입력하지 마세요.")
```

### 파일 다운로드 — 경로 탐색 공격 방지

```python
# ❌ 금지 — 사용자 입력을 파일 경로에 직접 사용
with open(f"./downloads/{user_input}", "rb") as f: ...

# ✅ 권장 — 메모리에서 직접 전달 (서버 경로 노출 없음)
st.download_button(
    label="다운로드",
    data=df.to_csv(index=False).encode("utf-8-sig"),
    file_name="export.csv",
    mime="text/csv",
)
```

---

## 7. .gitignore 필수 항목

```gitignore
# 환경변수 (절대 커밋 금지)
.env
.env.*

# Python 캐시
__pycache__/
*.pyc
*.pyo
*.pyd
.Python

# Claude Code 로컬 설정
.claude/settings.local.json
data/.claude/
pages/.claude/

# 접속 로그 (로컬 전용)
logs/

# IDE
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db
```

---

## 8. 자주 쓰는 명령어 레퍼런스

```bash
# 앱 실행
streamlit run app.py

# 패키지 설치
pip install -r requirements.txt

# Git 작업 흐름
git pull                            # 작업 전 최신 코드 동기화
git status                          # 변경 파일 확인
git add data/proc_2_data.py pages/proc_2.py   # 파일별 지정 추가
git commit -m "proc_2: 기능 설명"   # 한국어 커밋 메시지
git push                            # 원격 저장소 반영

# 캐시 강제 초기화 (개발 중 데이터 갱신 안 될 때)
# Streamlit 화면에서 우상단 메뉴 → Clear cache

# DB 연결 테스트
python -c "from utils.db import get_engine; e = get_engine(); print('연결 성공')"
```

---

## 9. 주의사항

- `.env` 파일은 절대 Git에 커밋하지 않을 것
- NAS 경로 하드코딩 금지 → 환경변수로 관리
- STG 분류(30STG, 50STG), 선종 매핑은 별도 참조 파일 사용
- `git add .` 사용 지양 — `__pycache__`, `.claude/` 등 불필요한 파일 포함 방지
- 개인정보(주민번호, 전화번호 등) 화면 표시 시 마스킹 처리 필수

---

## 10. Claude Code 권한 설정 안내

프로젝트 레벨 권한은 `.claude/settings.json`에서 관리합니다.

| 파일 | 용도 | Git 커밋 |
|---|---|---|
| `.claude/settings.json` | 팀 공유 권한 설정 | 포함 |
| `.claude/settings.local.json` | 개인 로컬 권한 설정 | 제외 |

### 허용 명령어 (allow)
`git`, `python`, `pip`, `ls`, `dir`, `mkdir`, `cat`, `echo`, `grep`, `awk`, `Read`, `Write`, `Edit`

### 차단 명령어 (deny)
`rm`, `del`, `rmdir`, `format`, `shutdown`, `reboot`, `sudo`, `su`, `net user`, `reg add/delete`, `sc delete/stop`, `taskkill`, `kill -9`, `pkill`

> 권한 변경이 필요하면 `.claude/settings.json`을 수정 후 팀원과 공유하세요.
