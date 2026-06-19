"""
╔══════════════════════════════════════════════════════════════════╗
║  담당자 : ___________                                            ║
║  항목   : [데이터 전용] kpi_3 - 정도율 / 인시당생산성 / 협력사BEP ║
║  작성일 : ___________                                            ║
╚══════════════════════════════════════════════════════════════════╝

【 데이터 소스 】
  lq_kpi3_1 (구 Acc_unitcost)      : 공종별 단가 (목의/선각/도장/전장/관철)
  lq_kpi3_2 (구 Acc_goal)          : 공종별 월별 인시당 목표
  lq_kpi3_3 (구 Acc_quantity)      : 호선별 공종별 단위물량
  lq_kpi3_4 (구 ACC_kpi3)          : 협력사별 호선별 기성공수(실적), 실투입공수 (년월: YYMM)
  lq_kpi3_5 (구 Acc_gisang)        : 협력사별 호선별 당월기성금액(전월 기성금 조회용, 년월: YYMM)
  lq_kpi3_6 (구 ACC_BEP)           : 협력사별 인원/단가/경비비율/상여비율/기성전망/투입전망
  lq_kpi3_7 (구 ACC_partneractual) : 일별 투입실적 (년월: 날짜 컬럼에서 집계)
  lq_kpi4_1                    : 호선별 마일스톤 (kpi_4와 동일 테이블, 프로젝트별 기성 집계용)
"""

import calendar
import datetime as _dt_mod
from datetime import date, timedelta, datetime

import pandas as pd
import streamlit as st

from utils.db import run_query, execute_query

# ── lq_kpi4_1 테이블명 ────────────────────────────────────────
_MILESTONE_TABLE = "lq_kpi4_1"

# ── 협력사 월간 전망/실적 입력 테이블 ──────────────────────────
# DDL (자동 생성됨, 수동 실행 불필요):
#   CREATE TABLE dbo.lq_kpi3_8 (
#       협력사    NVARCHAR(50) NOT NULL,
#       년도      INT          NOT NULL,
#       월        INT          NOT NULL,
#       구분      NVARCHAR(10) NOT NULL DEFAULT '전망',  -- '전망' or '실적'
#       기성      FLOAT        NULL,
#       처리물량  FLOAT        NULL,
#       투입      FLOAT        NULL,
#       입력자    NVARCHAR(50) NULL,
#       입력시각  DATETIME     NULL,
#       CONSTRAINT PK_lq_kpi3_8 PRIMARY KEY (협력사, 년도, 월, 구분)
#   );
# 기존 테이블이 구분 컬럼 없이 있으면 _ensure_forecast_table 가 자동 마이그레이션.
INPUT_FORECAST_TABLE = "dbo.lq_kpi3_8"


# ════════════════════════════════════════════════════════════════
# kpi_4_data 유틸 인라인 (import 대신 직접 정의)
# ════════════════════════════════════════════════════════════════

def _to_date(val):
    """다양한 형식의 날짜값을 Python date 객체로 변환"""
    if val is None or val == "":
        return None
    try:
        if pd.isna(val):
            return None
    except Exception:
        pass
    try:
        if isinstance(val, _dt_mod.datetime):
            return val.date()
        if isinstance(val, date):
            return val
        if isinstance(val, pd.Timestamp):
            return val.date()
        s = str(val).strip().replace("-", "").replace("/", "")
        if len(s) == 6 and s.isdigit():
            return datetime.strptime("20" + s, "%Y%m%d").date()
        if len(s) == 8 and s.isdigit():
            return datetime.strptime(s, "%Y%m%d").date()
        return pd.to_datetime(str(val)).date()
    except Exception:
        return None


def _get_next_weekday(d):
    """주말이면 직후 월요일로 이월"""
    if d is None:
        return None
    while d.weekday() > 4:
        d += timedelta(days=1)
    return d


def _wd_mon_fri(start: date, end: date) -> list[date]:
    """월~금 영업일 목록 (kpi_4 내부 기성 비율 계산용, 공휴일 미적용)"""
    if start is None or end is None or start > end:
        return []
    return [
        start + timedelta(days=i)
        for i in range((end - start).days + 1)
        if (start + timedelta(days=i)).weekday() < 5
    ]


def _parse_month_range(month_label, ref_year: int):
    """'1월','12월' 형태를 (시작일, 종료일)로 변환"""
    import re as _re
    match = _re.search(r"(\d{1,2})월", str(month_label))
    if not match:
        return None, None
    month_num = int(match.group(1))
    if not 1 <= month_num <= 12:
        return None, None
    last_day = calendar.monthrange(ref_year, month_num)[1]
    return date(ref_year, month_num, 1), date(ref_year, month_num, last_day)


@st.cache_data(ttl=600)
def _load_milestone() -> pd.DataFrame:
    """lq_kpi4_1 전체 로드"""
    df = run_query(f"SELECT * FROM [{_MILESTONE_TABLE}]")
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _auto_col(all_cols: list, keywords: list):
    for kw in keywords:
        for c in all_cols:
            if kw in str(c):
                return c
    return None


def _get_col_map(all_cols: list) -> dict:
    return {
        "gongsu":     _auto_col(all_cols, ["실행공수"]),
        "auto_prog":  _auto_col(all_cols, ["자동진도율", "진도율"]),
        "ms_start":   _auto_col(all_cols, ["마일스톤 계획_시작일", "마일스톤_계획_시작일", "마일스톤_시작일", "마일스톤 시작일"]),
        "ms_end":     _auto_col(all_cols, ["마일스톤 계획_종료일", "마일스톤_계획_종료일", "마일스톤_종료일", "마일스톤 종료일"]),
        "comp_date":  _auto_col(all_cols, ["완료절점_완료일", "완료절점", "완료일"]),
        "wanryo_amt": _auto_col(all_cols, ["완료절점 기성", "완료절점기성", "완료기성"]),
        "dept":       _auto_col(all_cols, ["작업부서명", "작업부서", "부서명", "부서", "DEPT_NM", "DEPT"]),
        "project":    _auto_col(all_cols, ["프로젝트", "호선", "PROJECT"]),
    }

# ── 협력사 목록 ───────────────────────────────────────────────────
COMPANY_LIST = ["지운", "세영", "TNC", "도선", "위드"]

# ── 협력사명 마스킹 (화면 표시용 전용) ───────────────────────────
# DB 쿼리·내부 키는 원본명 그대로 사용하되, 사용자에게 보여지는 화면에서만 치환.
# 키워드 기반이므로 DB에 "티엔씨엔지니어링" / "지운(주)" 같은 변형이 있어도 매칭됨.
COMPANY_MASK_KEYWORDS = [
    ("지운",   "A사"),
    ("위드",   "P사"),
    ("세영",   "S사"),
    ("도선",   "C사"),
    ("티엔씨", "E사"),
    ("TNC",    "E사"),
]

def mask_company(name) -> str:
    """협력사 이름을 키워드로 매칭해 마스킹 명칭 반환. 매칭 안 되면 원본 유지."""
    if name is None:
        return ""
    s = str(name)
    for kw, masked in COMPANY_MASK_KEYWORDS:
        if kw in s:
            return masked
    return s

# ── SN 특수 프로젝트 (lq_kpi3_6 개별 컬럼, 실적 전망 연장 대상) ─────
SN_PROJECTS: set[str] = {"SN2661", "SN2686", "SN2688"}

# ── 공종 매핑 ─────────────────────────────────────────────────────
COMPANY_GONGJON: dict[str, str] = {
    "지운": "목의",
    "위드": "목의",
    "세영": "선각",
    "도선": "도장",
    "TNC": "전장",
}

COMPANY_GOAL_GONGJON: dict[str, str] = {
    "지운": "선실목의",
    "위드": "선실목의",
    "세영": "선실선각",
    "도선": "선실도장",
    "TNC": "선실전장",
}

COMPANY_UNITCOST_COL: dict[str, str] = {
    "지운": "목의",
    "위드": "관철",
    "세영": "선각",
    "도선": "도장",
    "TNC": "전장",
}

COMPANY_KEYWORD: dict[str, str] = {
    "지운": "지운",
    "세영": "세영",
    "TNC": "티엔씨엔지니어링",
    "도선": "도선기업",
    "위드": "위드기업",
}

COMPANY_DEPT_KEYWORD: dict[str, str] = {
    "지운": "지운",
    "세영": "세영",
    "TNC": "티엔씨엔지니어링",
    "도선": "도선기업",
    "위드": "위드기업",
}

# ── 기타 상수 ─────────────────────────────────────────────────────
RADAR_METRICS = ["손익", "투입", "지출", "능률", "처리량", "인시당생산성", "단위물량당기성"]

# 정도율 산정 가중치 (RADAR_METRICS 중 일부만 반영, 합 = 100)
# 여기에 명시되지 않은 항목(손익, 인시당생산성)은 정도율에 영향을 주지 않음.
정도율_가중치 = {
    "투입":           30,
    "지출":           10,
    "능률":           10,
    "처리량":         25,
    "단위물량당기성": 25,
}
BEP_ITEMS     = ["기성금", "지출금", "손익", "인시당(목표)", "인시당(BEP)", "인시당(실적)"]
PERIOD_LIST   = ["전망", "실적", "잔여기간전망"]

# 4대보험 사업주 부담률 합계
_4대보험율 = 0.045 + 0.04 + 0.0115 + 0.024 + 0.0057  # 0.1262


# ════════════════════════════════════════════════════════════════
# Working Day (월~토, 공휴일 제외)
# ════════════════════════════════════════════════════════════════

# ── 추가 공휴일 상수 (법정 공휴일 외, 여기에 직접 추가) ─────────────
# 예시: date(2026, 2, 9),  # 설 연휴 임시공휴일
EXTRA_HOLIDAYS: set[date] = set()
# 추가 공휴일은 아래처럼 직접 추가:
# EXTRA_HOLIDAYS = {date(2026, 2, 9), date(2026, 9, 18)}


def _kr_public_holidays(year: int) -> set[date]:
    """한국 법정 공휴일 고정일 기준 (음력 기반 명절은 EXTRA_HOLIDAYS로 관리)"""
    return {
        date(year, 1, 1),    # 신정
        date(year, 3, 1),    # 삼일절
        date(year, 5, 5),    # 어린이날
        date(year, 6, 6),    # 현충일
        date(year, 8, 15),   # 광복절
        date(year, 10, 3),   # 개천절
        date(year, 10, 9),   # 한글날
        date(year, 12, 25),  # 크리스마스
    }


def _all_holidays(start: date, end: date) -> set[date]:
    """기간 내 모든 공휴일 (법정 + 추가)"""
    h: set[date] = set()
    for y in range(start.year, end.year + 1):
        h |= _kr_public_holidays(y)
    return h | EXTRA_HOLIDAYS


def _working_days_with_sat(start: date, end: date) -> list[date]:
    """
    월~토 기준 영업일 목록 (공휴일 제외).
    kpi_3 전용 — kpi_4의 working_days_in_range(월~금)와 구분해서 사용.
    """
    if start is None or end is None or start > end:
        return []
    holidays = _all_holidays(start, end)
    return [
        start + timedelta(days=i)
        for i in range((end - start).days + 1)
        if (start + timedelta(days=i)).weekday() < 6          # 월(0)~토(5)
        and (start + timedelta(days=i)) not in holidays
    ]


def _get_wday_counts(yyyymm: str) -> tuple[int, int]:
    """
    해당 월의 (지난 WD 수, 남은 WD 수) 반환.
    지난 WD: 월 시작 ~ 어제
    남은 WD: 오늘 ~ 월 말
    기준: 월~토, 공휴일 제외
    """
    year  = int(yyyymm[:4])
    month = int(yyyymm[4:6])
    last  = calendar.monthrange(year, month)[1]
    month_start = date(year, month, 1)
    month_end   = date(year, month, last)
    today       = date.today()

    past_end      = min(today - timedelta(days=1), month_end)
    remain_start  = max(today, month_start)

    past_wd   = len(_working_days_with_sat(month_start, past_end))
    remain_wd = len(_working_days_with_sat(remain_start, month_end))
    return past_wd, remain_wd


# ════════════════════════════════════════════════════════════════
# 협력사 월간 전망 입력 (lq_kpi3_8) — 익월 전망 입력 / 당월 전망 조회
# ════════════════════════════════════════════════════════════════

def get_forecast_deadline(year: int, month: int) -> date:
    """입력 마감일 = (year,month)의 25일.
    25일이 토/일/공휴일이면 다음 평일까지 자동 연장.
    """
    deadline = date(year, month, 25)
    holidays = _kr_public_holidays(year) | EXTRA_HOLIDAYS
    while deadline.weekday() >= 5 or deadline in holidays:
        deadline += timedelta(days=1)
        if deadline.year != year:
            holidays |= _kr_public_holidays(deadline.year)
    return deadline


def is_forecast_input_open(target_year: int, target_month: int) -> bool:
    """익월 (target_year, target_month) 입력 가능 여부.
    그 전월 25일(휴일 보정) 까지 입력 허용.
    """
    if target_month == 1:
        prev_y, prev_m = target_year - 1, 12
    else:
        prev_y, prev_m = target_year, target_month - 1
    return date.today() <= get_forecast_deadline(prev_y, prev_m)


@st.cache_data(ttl=60)
def forecast_table_exists() -> bool:
    """lq_kpi3_8 테이블 존재 여부 (1분 캐시)."""
    from utils.db import get_engine
    table_name = INPUT_FORECAST_TABLE.split(".")[-1]
    try:
        engine = get_engine()
        with engine.connect() as conn:
            df = pd.read_sql(
                "SELECT 1 AS ok FROM INFORMATION_SCHEMA.TABLES "
                "WHERE TABLE_NAME = ?",
                conn, params=(table_name,),
            )
        return not df.empty
    except Exception:
        return False


@st.cache_data(ttl=30)
def get_partner_forecast(year: int, month: int, 구분: str = "전망") -> pd.DataFrame:
    """협력사별 (year, month, 구분) 입력값 조회.
    구분: '전망' 또는 '실적'
    반환 컬럼: 협력사, 기성, 처리물량, 투입, 입력자, 입력시각
    테이블이 없거나 SQL 오류 시 빈 DataFrame 을 조용히 반환.
    구분 컬럼이 없는 (마이그레이션 전) 테이블은 전망으로 간주.
    """
    from utils.db import get_engine
    try:
        engine = get_engine()
        with engine.connect() as conn:
            # 구분 컬럼 존재 여부 확인 후 적절한 쿼리
            try:
                col_chk = pd.read_sql(
                    "SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS "
                    "WHERE TABLE_NAME = ? AND COLUMN_NAME = '구분'",
                    conn, params=(INPUT_FORECAST_TABLE.split(".")[-1],),
                )
                has_구분 = not col_chk.empty
            except Exception:
                has_구분 = False
            if has_구분:
                return pd.read_sql(
                    f"SELECT 협력사, 기성, 처리물량, 투입, 입력자, 입력시각 "
                    f"FROM {INPUT_FORECAST_TABLE} "
                    f"WHERE 년도 = ? AND 월 = ? AND 구분 = ?",
                    conn, params=(year, month, 구분),
                )
            # 구분 없는 구버전 테이블 → 전망 요청 시에만 데이터 반환
            if 구분 != "전망":
                return pd.DataFrame()
            return pd.read_sql(
                f"SELECT 협력사, 기성, 처리물량, 투입, 입력자, 입력시각 "
                f"FROM {INPUT_FORECAST_TABLE} WHERE 년도 = ? AND 월 = ?",
                conn, params=(year, month),
            )
    except Exception:
        return pd.DataFrame()


def _ensure_forecast_table() -> tuple[bool, str]:
    """lq_kpi3_8 테이블 보장 — 없으면 신규 스키마(구분 포함)로 생성,
    있으면 구분 컬럼이 있는지 확인하고 없으면 ALTER TABLE 로 추가 + PK 재구성.
    반환: (성공여부, 메시지).
    """
    table_only = INPUT_FORECAST_TABLE.split(".")[-1]

    # ── 1) 테이블 존재 확인
    table_exists = forecast_table_exists()

    if not table_exists:
        # 신규 생성 (구분 포함)
        ddl_create = f"""
        IF NOT EXISTS (
            SELECT 1 FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_NAME = '{table_only}'
        )
        BEGIN
            CREATE TABLE {INPUT_FORECAST_TABLE} (
                [협력사]    NVARCHAR(50) NOT NULL,
                [년도]      INT          NOT NULL,
                [월]        INT          NOT NULL,
                [구분]      NVARCHAR(10) NOT NULL CONSTRAINT [DF_{table_only}_구분] DEFAULT '전망',
                [기성]      FLOAT        NULL,
                [처리물량]  FLOAT        NULL,
                [투입]      FLOAT        NULL,
                [입력자]    NVARCHAR(50) NULL,
                [입력시각]  DATETIME     NULL,
                CONSTRAINT [PK_{table_only}] PRIMARY KEY ([협력사], [년도], [월], [구분])
            );
        END
        """
        try:
            execute_query(ddl_create)
            forecast_table_exists.clear()
            return True, ""
        except Exception as e:
            return False, str(e)

    # ── 2) 테이블 존재 → 구분 컬럼 마이그레이션 확인
    from utils.db import get_engine
    try:
        engine = get_engine()
        with engine.connect() as conn:
            col_chk = pd.read_sql(
                "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
                "WHERE TABLE_NAME = ? AND COLUMN_NAME = '구분'",
                conn, params=(table_only,),
            )
        if not col_chk.empty:
            return True, ""   # 이미 구분 컬럼 있음
    except Exception as e:
        return False, f"컬럼 확인 실패: {e}"

    # ── 3) 구분 컬럼 추가 + PK 재구성
    ddl_migrate = f"""
    -- 기본값 '전망' 으로 컬럼 추가 (NOT NULL 가능)
    IF NOT EXISTS (
        SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = '{table_only}' AND COLUMN_NAME = '구분'
    )
    BEGIN
        ALTER TABLE {INPUT_FORECAST_TABLE}
            ADD [구분] NVARCHAR(10) NOT NULL CONSTRAINT [DF_{table_only}_구분] DEFAULT '전망';
    END;

    -- 기존 PK 삭제 후 (협력사,년도,월,구분) 으로 재생성
    IF EXISTS (
        SELECT 1 FROM sys.indexes
        WHERE name = 'PK_{table_only}' AND is_primary_key = 1
    )
    BEGIN
        ALTER TABLE {INPUT_FORECAST_TABLE} DROP CONSTRAINT [PK_{table_only}];
    END;
    ALTER TABLE {INPUT_FORECAST_TABLE}
        ADD CONSTRAINT [PK_{table_only}] PRIMARY KEY ([협력사], [년도], [월], [구분]);
    """
    try:
        execute_query(ddl_migrate)
        try:
            get_partner_forecast.clear()
        except Exception:
            pass
        return True, ""
    except Exception as e:
        return False, f"마이그레이션 실패: {e}"


def save_partner_forecast(company: str, year: int, month: int,
                          기성, 처리물량, 투입, 입력자: str,
                          구분: str = "전망") -> tuple[bool, str]:
    """협력사 전망/실적 UPSERT (DELETE + INSERT).
    구분 = '전망' or '실적'. 테이블 없으면 자동 생성, 구분 컬럼 없으면 자동 마이그레이션.
    반환: (성공여부, 메시지).
    """
    ok_table, err_table = _ensure_forecast_table()
    if not ok_table:
        return False, f"테이블 생성/마이그레이션 실패: {err_table}"

    now = _dt_mod.datetime.now()
    try:
        execute_query(
            f"DELETE FROM {INPUT_FORECAST_TABLE} "
            f"WHERE 협력사 = ? AND 년도 = ? AND 월 = ? AND 구분 = ?",
            params=(company, year, month, 구분),
        )
        execute_query(
            f"INSERT INTO {INPUT_FORECAST_TABLE} "
            f"(협력사, 년도, 월, 구분, 기성, 처리물량, 투입, 입력자, 입력시각) "
            f"VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            params=(company, year, month, 구분,
                    float(기성 or 0), float(처리물량 or 0), float(투입 or 0),
                    입력자, now),
        )
    except Exception as e:
        return False, f"저장 실패: {e}"
    # 캐시 무효화 — 입력값을 사용하는 함수들 모두
    for _fn in (get_partner_forecast, get_jeongdoyul_data):
        try:
            _fn.clear()
        except Exception:
            pass
    return True, ""


# ════════════════════════════════════════════════════════════════
# 날짜 유틸
# ════════════════════════════════════════════════════════════════

def _month_info(year: int, month: int) -> dict:
    if month < 1:
        month += 12; year -= 1
    elif month > 12:
        month -= 12; year += 1
    yy = str(year)[2:]
    return {
        "yyyymm": f"{year}{month:02d}",
        "yymm":   f"{yy}{month:02d}",
        "월":     month,
        "label":  f"{month}월",
    }


def get_month_labels() -> dict[str, dict]:
    t = date.today()
    return {
        "전월": _month_info(t.year, t.month - 1),
        "당월": _month_info(t.year, t.month),
        "익월": _month_info(t.year, t.month + 1),
    }


def get_bep_month_labels() -> list[str]:
    lbs = get_month_labels()
    return [lbs["전월"]["label"], lbs["당월"]["label"], lbs["익월"]["label"]]


# ════════════════════════════════════════════════════════════════
# 개별 테이블 조회 함수
# ════════════════════════════════════════════════════════════════

@st.cache_data(ttl=600)
def get_unitcost(yyyymm: str = None) -> dict[str, float]:
    """
    공종별 단가 조회 (lq_kpi3_1).
    - 해당월 컬럼(YYYYMM)이 일치하는 행을 우선 사용
    - 없으면 ≤ yyyymm 중 가장 최근 월(MAX(해당월))로 fallback
    - yyyymm=None 이면 단가표 전체 중 가장 최근 월 사용
    """
    cols = ["목의", "선각", "도장", "전장", "관철"]
    empty = {k: 0.0 for k in cols}

    # 1) 해당월 정확 매칭
    if yyyymm:
        df = run_query(
            "SELECT 목의, 선각, 도장, 전장, 관철 FROM lq_kpi3_1 WHERE 해당월 = ?",
            params=(yyyymm,)
        )
        if not df.empty:
            row = df.iloc[0]
            return {c: float(row[c] or 0) for c in cols}

    # 2) 이전 월 fallback — ≤ yyyymm 중 MAX(해당월)
    if yyyymm:
        df = run_query(
            "SELECT TOP 1 목의, 선각, 도장, 전장, 관철 "
            "FROM lq_kpi3_1 WHERE 해당월 <= ? ORDER BY 해당월 DESC",
            params=(yyyymm,)
        )
    else:
        df = run_query(
            "SELECT TOP 1 목의, 선각, 도장, 전장, 관철 "
            "FROM lq_kpi3_1 ORDER BY 해당월 DESC",
        )
    if df.empty:
        return empty
    row = df.iloc[0]
    return {c: float(row[c] or 0) for c in cols}


@st.cache_data(ttl=600)
def get_goal_data() -> pd.DataFrame:
    sql = """
    SELECT 공종, 구분,
           [1월],[2월],[3월],[4월],[5월],[6월],
           [7월],[8월],[9월],[10월],[11월],[12월]
    FROM lq_kpi3_2
    """
    return run_query(sql)


def get_goal_distinct() -> pd.DataFrame:
    """lq_kpi3_2 테이블의 실제 공종/구분 값 확인용 (진단 전용)"""
    sql = "SELECT DISTINCT 공종, 구분 FROM lq_kpi3_2 ORDER BY 공종, 구분"
    return run_query(sql)


@st.cache_data(ttl=600)
def get_quantity_data() -> pd.DataFrame:
    sql = """
    SELECT 프로젝트,
           목의_단위물량, 선각_단위물량,
           도장_단위물량, 전장_단위물량
    FROM lq_kpi3_3
    """
    return run_query(sql)


@st.cache_data(ttl=600)
def get_kpi3_actual(yymm: str) -> pd.DataFrame:
    sql = """
    SELECT 협력사명, 프로젝트,
           기성공수, 실투입공수, 년월
    FROM lq_kpi3_4
    WHERE 년월 = ?
    """
    return run_query(sql, params=(yymm,))
@st.cache_data(ttl=600)
def get_gisang_data(yymm: str) -> pd.DataFrame:
    # yymm "2603" → 년도=2026, 월=3 (lq_kpi3_5 는 년도/월 컬럼이 분리되어 있음)
    년도 = 2000 + int(yymm[:2])
    월 = int(yymm[2:])
    sql = """
    SELECT 협력사, 프로젝트,
           당월기성금액 AS 기성금액, 년도, 월
    FROM lq_kpi3_5
    WHERE 년도 = ? AND 월 = ?
    """
    return run_query(sql, params=(년도, 월))


@st.cache_data(ttl=600)
def get_bep_raw(company: str, yyyymm: str) -> dict[str, float]:
    sql = """
    SELECT 구분, 항목, 값
    FROM lq_kpi3_6
    WHERE 협력사 = ? AND 년월 = ?
    """
    df = run_query(sql, params=(company, yyyymm))
    if df.empty:
        return {}
    # "구분_항목" 형태(예: 기성전망_운반선)와 "항목" 단독(예: 시급_내국인_인원) 두 키를 모두 저장
    result: dict[str, float] = {}
    for _, row in df.iterrows():
        구분 = str(row["구분"]).strip()
        항목 = str(row["항목"]).strip()
        값   = float(row["값"] or 0)
        result[f"{구분}_{항목}"] = 값
        result[항목]             = 값
    return result


@st.cache_data(ttl=600)
def get_partneractual_monthly(company: str, yyyymm: str) -> float:
    keyword = COMPANY_DEPT_KEYWORD.get(company, company)
    sql = """
    SELECT SUM(전체) AS 투입실적누계
    FROM lq_kpi3_7
    WHERE 부서 LIKE ?
      AND FORMAT(날짜, 'yyyyMM') = ?
    """
    df = run_query(sql, params=(f"%{keyword}%", yyyymm))
    if df.empty or df.iloc[0]["투입실적누계"] is None:
        return 0.0
    return float(df.iloc[0]["투입실적누계"])


# ════════════════════════════════════════════════════════════════
# lq_kpi4_1 → 프로젝트별 기성공수 집계 (kpi_3 전용)
# ════════════════════════════════════════════════════════════════

@st.cache_data(ttl=600)
def _get_milestone_kiseong_by_project(company: str, yyyymm: str) -> dict[str, float]:
    """
    lq_kpi4_1 에서 협력사·월 기준 프로젝트별 기성공수(실행공수 기반) 집계.
    kpi_4_data.compute_kiseong 과 동일 로직, 부서 대신 프로젝트로 그룹핑.
    Returns: {"프로젝트명": 기성공수_합계, ...}
    """
    dept_kw  = COMPANY_DEPT_KEYWORD.get(company, company)
    year     = int(yyyymm[:4])
    month    = int(yyyymm[4:6])
    last_day = calendar.monthrange(year, month)[1]
    query_start = date(year, month, 1)
    query_end   = date(year, month, last_day)

    # lq_kpi4_1 로드 (kpi_4_data.load_data 재사용)
    df = _load_milestone()

    # 협력사(부서) 필터
    col_map  = _get_col_map(df.columns.tolist())
    dept_col = col_map.get("dept")
    proj_col = col_map.get("project")

    if dept_col:
        df = df[df[dept_col].str.contains(dept_kw, na=False)]

    if df.empty:
        return {}

    query_wd_list = _wd_mon_fri(query_start, query_end)   # 내부 기성 계산은 월~금 유지
    query_wd_set  = set(query_wd_list)
    has_month_col = "월" in df.columns

    ms_start_col = col_map.get("ms_start")
    ms_end_col   = col_map.get("ms_end")
    comp_col     = col_map.get("comp_date")
    gongsu_col   = col_map.get("gongsu")
    prog_col     = col_map.get("auto_prog")
    wanryo_col   = col_map.get("wanryo_amt")

    proj_gongjeong: dict[str, float] = {}
    proj_wanryo:    dict[str, float] = {}

    for _, row in df.iterrows():
        proj = str(row.get(proj_col, "미분류")).strip() if proj_col else "미분류"

        ms_start      = _to_date(row[ms_start_col]) if ms_start_col else None
        ms_end        = _to_date(row[ms_end_col])   if ms_end_col   else None
        comp_date_raw = _to_date(row[comp_col])     if comp_col     else None
        comp_date     = _get_next_weekday(comp_date_raw)

        try:
            gongsu        = float(row[gongsu_col] or 0) if gongsu_col else 0.0
            auto_prog_raw = float(row[prog_col]   or 0) if prog_col   else 0.0
            wanryo_val    = float(row[wanryo_col] or 0) if wanryo_col else 0.0

            if auto_prog_raw == 0:
                auto_prog = 0.0
            elif 0 < auto_prog_raw <= 1.0:
                auto_prog = auto_prog_raw
            else:
                auto_prog = auto_prog_raw / 100.0
        except (ValueError, TypeError):
            continue

        ref_year = query_start.year
        if has_month_col:
            m_start, m_end = _parse_month_range(row.get("월"), ref_year)
            if m_start and m_end:
                eff_start = max(m_start, query_start)
                eff_end   = min(m_end,   query_end)
                if eff_start > eff_end:
                    continue
                eff_wd_set = set(_wd_mon_fri(eff_start, eff_end))
            else:
                eff_wd_set = query_wd_set
        else:
            eff_wd_set = query_wd_set

        # 공정진도 기성
        row_gong = 0.0
        if ms_start and ms_end and gongsu > 0:
            total_wd_list = _wd_mon_fri(ms_start, ms_end)
            total_wd      = len(total_wd_list)
            if total_wd > 0:
                dg = gongsu * auto_prog / total_wd
                if comp_date and ms_start <= comp_date < ms_end:
                    wd_set   = set(_wd_mon_fri(ms_start, comp_date))
                    rem_days = len(_wd_mon_fri(comp_date + timedelta(days=1), ms_end))
                    row_gong = sum(dg for d in eff_wd_set if d in wd_set)
                    if has_month_col:
                        _, comp_m_end = _parse_month_range(row.get("월"), ref_year)
                        lump_ok = (
                            comp_m_end is not None
                            and comp_date.month == comp_m_end.month
                            and comp_date.year  == comp_m_end.year
                        )
                    else:
                        lump_ok = True
                    if lump_ok and comp_date in query_wd_set:
                        row_gong += dg * rem_days
                else:
                    wd_set   = set(total_wd_list)
                    row_gong = sum(dg for d in eff_wd_set if d in wd_set)

        proj_gongjeong[proj] = proj_gongjeong.get(proj, 0.0) + row_gong

        # 완료절점 기성
        if comp_date and comp_date in query_wd_set and wanryo_val > 0:
            proj_wanryo[proj] = proj_wanryo.get(proj, 0.0) + wanryo_val

    all_projs = set(proj_gongjeong) | set(proj_wanryo)
    return {p: proj_gongjeong.get(p, 0.0) + proj_wanryo.get(p, 0.0) for p in all_projs}


# ════════════════════════════════════════════════════════════════
# 처리물량 계산 헬퍼
# ════════════════════════════════════════════════════════════════

def _get_단위물량(company: str, project: str, quantity_df: pd.DataFrame) -> float:
    col = COMPANY_GONGJON.get(company, "목의") + "_단위물량"
    row = quantity_df[quantity_df["프로젝트"] == project]
    if row.empty or col not in row.columns:
        return 0.0
    return float(row.iloc[0][col] or 0)


def _get_company_실적(
    company: str,
    yymm: str,
    yyyymm: str,
    quantity_df: pd.DataFrame,
) -> tuple[float, float]:
    """lq_kpi3_4 기반 처리물량·투입실적 (BEP / 인시당생산성 섹션 호환용)"""
    keyword = COMPANY_KEYWORD.get(company, company)
    kpi3_df = get_kpi3_actual(yymm)
    comp_df = kpi3_df[kpi3_df["협력사명"].str.contains(keyword, na=False)]

    처리물량 = sum(
        float(r["기성공수"] or 0) * _get_단위물량(company, str(r["프로젝트"]), quantity_df)
        for _, r in comp_df.iterrows()
    ) if not comp_df.empty else 0.0

    투입 = float(comp_df["실투입공수"].sum()) if not comp_df.empty else 0.0
    return 처리물량, 투입


# ════════════════════════════════════════════════════════════════
# 지출금 계산
# ════════════════════════════════════════════════════════════════

def _calc_지출금(bep_raw: dict) -> dict[str, float]:
    경비비율 = bep_raw.get("경비비율", 0) or 0
    상여비율 = bep_raw.get("상여비율", 0) or 0
    물량팀_퇴직금  = bep_raw.get("물량팀_퇴직금", 0) or 0
    물량팀_4대보험 = bep_raw.get("물량팀_4대보험", 0) or 0

    총계             = 0.0
    월급_내국인_소계 = 0.0
    간접_소계        = 0.0

    # 시급_내국인
    인원 = bep_raw.get("시급_내국인_인원", 0) or 0
    단가 = bep_raw.get("시급_내국인_단가", 0) or 0
    if 인원 > 0 and 단가 > 0:
        급여 = 인원 * 단가 * 209
        주휴 = 단가 * (52 / 12) * 8
        명절 = (단가 * 209) / 12 * 상여비율
        년불 = 단가 * 8 * 15 / 12
        base = 급여 + 주휴 + 명절 + 년불
        총계 += base + base / 12 + base * _4대보험율 + base * 경비비율

    # 시급_외국인
    인원 = bep_raw.get("시급_외국인_인원", 0) or 0
    단가 = bep_raw.get("시급_외국인_단가", 0) or 0
    if 인원 > 0 and 단가 > 0:
        급여 = 인원 * 단가 * 209
        주휴 = 단가 * (52 / 12) * 8
        명절 = (단가 * 209) / 12 * 상여비율
        년불 = 단가 * 8 * 15 / 12
        base = 급여 + 주휴 + 명절 + 년불
        총계 += base + base / 12 + base * _4대보험율 + base * 경비비율

    # 월급_내국인
    인원 = bep_raw.get("월급_내국인_인원", 0) or 0
    단가 = bep_raw.get("월급_내국인_단가", 0) or 0
    if 인원 > 0 and 단가 > 0:
        월급 = 인원 * 단가
        명절 = 월급 * 0.70 / 12 * 상여비율
        년불 = 월급 * 0.70 / 209 * 8 * 15 / 12
        base = 월급 + 명절 + 년불
        소계 = base + base / 12 + base * _4대보험율 + base * 경비비율
        총계             += 소계
        월급_내국인_소계 += 소계

    # 월급_외국인
    인원 = bep_raw.get("월급_외국인_인원", 0) or 0
    단가 = bep_raw.get("월급_외국인_단가", 0) or 0
    if 인원 > 0 and 단가 > 0:
        월급 = 인원 * 단가
        명절 = 월급 * 0.70 / 12 * 상여비율
        년불 = 월급 * 0.70 / 209 * 8 * 15 / 12
        base = 월급 + 명절 + 년불
        총계 += base + base / 12 + base * _4대보험율 + base * 경비비율

    # 간접
    인원 = bep_raw.get("간접_인원", 0) or 0
    단가 = bep_raw.get("간접_단가", 0) or 0
    if 인원 > 0 and 단가 > 0:
        월급 = 인원 * 단가
        명절 = 월급 * 0.70 / 12 * 상여비율
        년불 = 월급 * 0.70 / 209 * 8 * 15 / 12
        base = 월급 + 명절 + 년불
        소계    = base + base / 12 + base * _4대보험율 + base * 경비비율
        총계   += 소계
        간접_소계 += 소계

    # 직시급_직종1,2,3
    투입전망     = bep_raw.get("투입전망_합계", 0) or 0
    직시급총인원 = sum(bep_raw.get(f"직시급_직종{i}_인원", 0) or 0 for i in [1, 2, 3])
    wd = 209 / 8
    가급시간 = max(0.0, (투입전망 / 직시급총인원 / wd) - 8) if 직시급총인원 > 0 else 0.0

    for i in [1, 2, 3]:
        인원 = bep_raw.get(f"직시급_직종{i}_인원", 0) or 0
        단가 = bep_raw.get(f"직시급_직종{i}_단가", 0) or 0
        if 인원 > 0 and 단가 > 0:
            급여  = 인원 * 단가 * (8 + 가급시간) * wd
            퇴직  = (물량팀_퇴직금  / 직시급총인원) * 인원
            보험  = (물량팀_4대보험 / 직시급총인원) * 인원
            경비  = 급여 * 경비비율
            총계 += 급여 + 퇴직 + 보험 + 경비

    # 본공_직종1,2,3
    for i in [1, 2, 3]:
        인원 = bep_raw.get(f"본공_직종{i}_인원", 0) or 0
        단가 = bep_raw.get(f"본공_직종{i}_단가", 0) or 0
        if 인원 > 0 and 단가 > 0:
            급여 = 단가 * wd
            년불 = 단가 / 15 / 12
            base = 급여 + 년불
            총계 += 인원 * (base + base / 12 + base * 0.1262 + 급여 * 경비비율)

    return {
        "지출금_합계":      round(총계, 0),
        "월급_내국인_소계": round(월급_내국인_소계, 0),
        "간접_소계":        round(간접_소계, 0),
    }


# ════════════════════════════════════════════════════════════════
# 인시당 BEP 계산
# ════════════════════════════════════════════════════════════════

def _calc_인시당_bep(
    처리물량: float,
    투입: float,
    지출금: float,
    기성금: float,
    월급_내국인_소계: float,
    간접_소계: float,
) -> float:
    월급제총합 = 월급_내국인_소계 + 간접_소계
    try:
        if 지출금 == 0 or (지출금 - 월급제총합) == 0 or 투입 == 0:
            return 0.0
        adjusted_투입 = 투입 + (
            투입 * (지출금 - 월급제총합) / 지출금
            * (기성금 - 지출금) / (지출금 - 월급제총합)
        )
        return round(처리물량 / adjusted_투입, 3) if adjusted_투입 > 0 else 0.0
    except ZeroDivisionError:
        return 0.0


# ════════════════════════════════════════════════════════════════
# 정도율 / 정도율 계산 헬퍼
# ════════════════════════════════════════════════════════════════

def _calc_정도율(ratio_pct: float) -> float:
    if ratio_pct <= 100.0:
        return ratio_pct
    return max(0.0, 200.0 - ratio_pct)


def _safe_ratio(actual: float, forecast: float) -> float:
    if forecast == 0:
        return 100.0
    return round(actual / forecast * 100, 1)


# ════════════════════════════════════════════════════════════════
# 정도율 방사형 그래프 데이터
# ════════════════════════════════════════════════════════════════

@st.cache_data(ttl=600)
def get_jeongdoyul_data(month: str = "당월",
                         year_int: int = None, month_int: int = None) -> dict:
    """
    협력사별 7개 지표 정도율 데이터.
    year_int, month_int 가 모두 주어지면 그 (년, 월) 로 직접 계산.
    그 외엔 month 문자열("전월"/"당월"/"익월") 기반.

    RADAR_METRICS = ["손익", "투입", "지출", "능률", "처리량", "인시당생산성", "단위물량당기성"]

    ── 전망값 ──
    손익            = (기성전망 공수 합계 × 단가 + 외주비) - 지출금
    투입            = 투입전망_합계
    지출            = _calc_지출금() 합계
    능률            = 기성전망 공수 합계 / 투입전망
    처리량          = milestone 기반(non-SN) + lq_kpi3_6 SN 전망 기반(SN)  ← 프로젝트별 × 단위물량 합산
    인시당생산성    = 처리량 / 투입
    단위물량당기성  = 기성전망 공수 합계(H) / 처리량   ← 분자는 공수 그대로

    ── 실적값 ──
    기성공수 복합식(합계 scalar):
        = kpi4_non_SN합 + kpi3_SN실적 + (kpi3_SN실적 / past_wd × remain_wd)

    손익            = 기성공수 복합식 × 단가 - 실적 지출금
    투입            = kpi3_실투입 + (kpi3_실투입 / past_wd × remain_wd)
    지출            = 전망_지출금 × 실적_투입 / 전망_투입
    능률            = 기성공수 복합식 / 실적_투입
    처리량          = 프로젝트별 (기성공수 복합식) × 단위물량 합산
    인시당생산성    = 실적_처리량 / 실적_투입
    단위물량당기성  = 기성공수 복합식(H) / 실적_처리량
    """
    if year_int is not None and month_int is not None:
        m_info = _month_info(year_int, month_int)
    else:
        labels = get_month_labels()
        m_info = labels[month]
    yymm        = m_info["yymm"]
    yyyymm      = m_info["yyyymm"]
    year_int    = int(yyyymm[:4])
    month_int   = int(yyyymm[4:6])
    unitcost    = get_unitcost(yyyymm)
    quantity_df = get_quantity_data()
    goal_df     = get_goal_data()

    # 해당 월 Working Day 카운트 (토포함, 공휴일 제외)
    past_wd, remain_wd = _get_wday_counts(yyyymm)

    # 사용자 입력 전망 (lq_kpi3_8) — 있으면 전망 분모로 덮어씀
    # 실적은 DB(lq_kpi3_4 등) 자동 계산 그대로 사용 — 수기 오버라이드 없음
    try:
        user_fc_df = get_partner_forecast(year_int, month_int, 구분="전망")
    except Exception:
        user_fc_df = pd.DataFrame()
    user_fc_dict: dict = {}
    if user_fc_df is not None and not user_fc_df.empty and "협력사" in user_fc_df.columns:
        user_fc_dict = {
            row["협력사"]: row.to_dict() for _, row in user_fc_df.iterrows()
        }

    result: dict = {}

    for company in COMPANY_LIST:
        keyword      = COMPANY_KEYWORD.get(company, company)
        단가          = unitcost.get(COMPANY_UNITCOST_COL.get(company, "목의"), 0)
        goal_gongjon = COMPANY_GOAL_GONGJON.get(company, "선실목의")
        월컬럼        = m_info["label"]

        # ── lq_kpi3_6 원천값 ────────────────────────────────────────
        bep_raw      = get_bep_raw(company, yyyymm)
        외주비        = float(bep_raw.get("기성전망_외주비", 0) or 0)
        투입전망      = float(bep_raw.get("투입전망_합계",  0) or 0)

        # ── SN 전망 공수: 컬럼 동적 체크 (없으면 0) ─────────────
        기성전망_운반선 = float(bep_raw.get("기성전망_운반선", 0) or 0)
        SN_전망_공수: dict[str, float] = {}
        for sn in SN_PROJECTS:
            SN_전망_공수[sn] = float(bep_raw.get(f"기성전망_{sn}", 0) or 0)

        기성전망_합계_공수 = 기성전망_운반선 + sum(SN_전망_공수.values())

        # ── lq_kpi4_1 프로젝트별 기성 (kpi_4 로직 재사용) ────
        milestone_by_proj = _get_milestone_kiseong_by_project(company, yyyymm)

        # ── 지출금 ────────────────────────────────────────────────
        지출_result   = _calc_지출금(bep_raw)
        전망_지출금   = 지출_result["지출금_합계"]

        # ════ 전망값 ═══════════════════════════════════════════════

        # 손익
        전망_기성금 = 기성전망_합계_공수 * 단가 + 외주비
        전망_손익   = 전망_기성금 - 전망_지출금

        # 투입
        전망_투입 = 투입전망

        # 처리량: (1) non-SN = milestone 기반  (2) SN = lq_kpi3_6 전망
        전망_처리량 = sum(
            v * _get_단위물량(company, proj, quantity_df)
            for proj, v in milestone_by_proj.items()
            if proj not in SN_PROJECTS
        ) + sum(
            SN_전망_공수[sn] * _get_단위물량(company, sn, quantity_df)
            for sn in SN_PROJECTS
        )

        # 능률 (공수/공수 비율)
        전망_능률 = (기성전망_합계_공수 / 전망_투입) if 전망_투입 > 0 else 0.0

        # 인시당생산성
        전망_인시당 = (전망_처리량 / 전망_투입) if 전망_투입 > 0 else 0.0

        # 단위물량당기성 (분자: 공수H 그대로)
        전망_단물당기성 = (기성전망_합계_공수 / 전망_처리량) if 전망_처리량 > 0 else 0.0

        # ── 사용자 입력 전망(lq_kpi3_8) 으로 분모 오버라이드 ────────────
        # 입력 항목: 기성, 처리물량, 투입 (각 항목 > 0 일 때만 덮어씀)
        # 영향: 전망_손익/투입/처리량/능률/인시당/단물당기성 (단, 지출은 미변경)
        _user_fc = user_fc_dict.get(company)
        if _user_fc:
            _u_기성 = float(_user_fc.get("기성") or 0)
            _u_처리물량 = float(_user_fc.get("처리물량") or 0)
            _u_투입 = float(_user_fc.get("투입") or 0)
            if _u_기성 > 0:
                기성전망_합계_공수 = _u_기성
                전망_기성금 = _u_기성 * 단가 + 외주비
                전망_손익   = 전망_기성금 - 전망_지출금
            if _u_투입 > 0:
                전망_투입 = _u_투입
            if _u_처리물량 > 0:
                전망_처리량 = _u_처리물량
            # 파생 재계산
            전망_능률       = (기성전망_합계_공수 / 전망_투입) if 전망_투입 > 0 else 0.0
            전망_인시당     = (전망_처리량 / 전망_투입) if 전망_투입 > 0 else 0.0
            전망_단물당기성 = (기성전망_합계_공수 / 전망_처리량) if 전망_처리량 > 0 else 0.0

        # 능률 목표 (lq_kpi3_2)
        goal_row    = goal_df[(goal_df["공종"] == goal_gongjon) & (goal_df["구분"] == "목표")]
        인시당_목표 = (
            float(goal_row.iloc[0][월컬럼])
            if not goal_row.empty and 월컬럼 in goal_row.columns
            else 전망_능률
        )

        # ════ 실적값 ═══════════════════════════════════════════════

        kpi3_df = get_kpi3_actual(yymm)
        comp_df = kpi3_df[kpi3_df["협력사명"].str.contains(keyword, na=False)]

        # SN / non-SN 분리
        if not comp_df.empty:
            mask_SN      = comp_df["프로젝트"].isin(SN_PROJECTS)
            kpi3_SN_df   = comp_df[mask_SN]
            kpi3_nonSN_df = comp_df[~mask_SN]
        else:
            kpi3_SN_df   = pd.DataFrame()
            kpi3_nonSN_df = pd.DataFrame()

        kpi3_SN_기성합  = float(kpi3_SN_df["기성공수"].sum())  if not kpi3_SN_df.empty  else 0.0
        kpi3_전체_실투입 = float(comp_df["실투입공수"].sum())   if not comp_df.empty      else 0.0

        # kpi4(milestone) non-SN 합계
        kpi4_nonSN_합 = sum(v for proj, v in milestone_by_proj.items() if proj not in SN_PROJECTS)

        # SN 전망 연장: 실적 / past_wd × remain_wd
        SN_연장 = (kpi3_SN_기성합 / past_wd * remain_wd) if past_wd > 0 else 0.0

        # 기성공수 복합식 — 스칼라
        실적_기성공수_합 = kpi4_nonSN_합 + kpi3_SN_기성합 + SN_연장

        # 실적 투입
        투입_연장  = (kpi3_전체_실투입 / past_wd * remain_wd) if past_wd > 0 else 0.0
        실적_투입  = kpi3_전체_실투입 + 투입_연장

        # 실적 지출 (투입 비율 근사)
        실적_지출금 = 전망_지출금 * (실적_투입 / 전망_투입) if 전망_투입 > 0 else 0.0

        # 실적 손익
        실적_손익 = 실적_기성공수_합 * 단가 - 실적_지출금

        # 실적 능률
        실적_능률 = (실적_기성공수_합 / 실적_투입) if 실적_투입 > 0 else 0.0

        # 실적 처리량 (프로젝트별 계산 후 합산)
        실적_처리량 = 0.0

        # non-SN: milestone 기반 프로젝트별
        for proj, v in milestone_by_proj.items():
            if proj not in SN_PROJECTS:
                실적_처리량 += v * _get_단위물량(company, proj, quantity_df)

        # SN: kpi3 실적 + 전망 연장, 프로젝트별
        for _, row in kpi3_SN_df.iterrows():
            proj       = str(row["프로젝트"])
            proj_기성   = float(row["기성공수"] or 0)
            proj_연장  = (proj_기성 / past_wd * remain_wd) if past_wd > 0 else 0.0
            실적_처리량 += (proj_기성 + proj_연장) * _get_단위물량(company, proj, quantity_df)

        # 실적 인시당생산성
        실적_인시당 = (실적_처리량 / 실적_투입) if 실적_투입 > 0 else 0.0

        # 실적 단위물량당기성 (분자: 공수H)
        실적_단물당기성 = (실적_기성공수_합 / 실적_처리량) if 실적_처리량 > 0 else 0.0

        # ── 비율 → 정도율 ─────────────────────────────────────────
        비율_vals = [
            _safe_ratio(실적_손익,          전망_손익),
            _safe_ratio(실적_투입,          전망_투입),
            _safe_ratio(실적_지출금,        전망_지출금),
            _safe_ratio(실적_능률,          인시당_목표),   # 능률: goal 목표 대비
            _safe_ratio(실적_처리량,        전망_처리량),
            _safe_ratio(실적_인시당,        전망_인시당),
            _safe_ratio(실적_단물당기성,    전망_단물당기성),
        ]
        정도율_vals = [round(_calc_정도율(r), 1) for r in 비율_vals]

        result[company] = {"전망": [100.0] * 7, "실적": 정도율_vals, "비율": 비율_vals}

    return result


# ════════════════════════════════════════════════════════════════
# 인시당 생산성
# ════════════════════════════════════════════════════════════════

@st.cache_data(ttl=600)
def get_productivity_data(month: str = "당월",
                           year_int: int = None, month_int: int = None) -> pd.DataFrame:
    if year_int is not None and month_int is not None:
        m_info = _month_info(year_int, month_int)
    else:
        labels = get_month_labels()
        m_info = labels[month]
    yymm        = m_info["yymm"]
    yyyymm      = m_info["yyyymm"]
    unitcost    = get_unitcost(yyyymm)
    quantity_df = get_quantity_data()

    rows: list = []

    for company in COMPANY_LIST:
        row     = {"업체": company}
        keyword = COMPANY_KEYWORD.get(company, company)
        단가    = unitcost.get(COMPANY_UNITCOST_COL.get(company, "목의"), 0)

        bep_raw      = get_bep_raw(company, yyyymm)
        투입전망      = float(bep_raw.get("투입전망_합계", 0) or 0)

        # ── 전망 기성: (운반선 + SN들) × 단가  (외주비 미포함) ──
        기성전망_운반선 = float(bep_raw.get("기성전망_운반선", 0) or 0)
        SN_전망_공수_prod: dict[str, float] = {
            sn: float(bep_raw.get(f"기성전망_{sn}", 0) or 0) for sn in SN_PROJECTS
        }
        기성전망_합계_공수 = 기성전망_운반선 + sum(SN_전망_공수_prod.values())
        전망_기성     = 기성전망_합계_공수

        # 전망 처리물량: milestone non-SN + lq_kpi3_6 SN 전망 (정도율과 동일 로직)
        milestone_by_proj_prod = _get_milestone_kiseong_by_project(company, yyyymm)
        전망_처리물량 = round(
            sum(
                v * _get_단위물량(company, proj, quantity_df)
                for proj, v in milestone_by_proj_prod.items()
                if proj not in SN_PROJECTS
            ) + sum(
                SN_전망_공수_prod[sn] * _get_단위물량(company, sn, quantity_df)
                for sn in SN_PROJECTS
            ), 1
        )
        전망_투입     = round(투입전망, 1)
        전망_인시당   = round(전망_처리물량 / 전망_투입, 3) if 전망_투입 > 0 else 0.0

        row["전망_기성"]         = 전망_기성
        row["전망_처리물량"]     = 전망_처리물량
        row["전망_투입"]         = 전망_투입
        row["전망_인시당생산성"] = 전망_인시당

        # ── 실적: lq_kpi3_4 에서만 집계 ────────────────────────────
        kpi3_df_p = get_kpi3_actual(yymm)
        comp_df_p = kpi3_df_p[kpi3_df_p["협력사명"].str.contains(keyword, na=False)]

        # 기성: 기성공수 합계
        실적_기성 = float(comp_df_p["기성공수"].sum()) if not comp_df_p.empty else 0.0

        # 처리물량: 프로젝트별 기성공수 × 단위물량 합산
        실적_처리물량 = sum(
            float(r["기성공수"] or 0) * _get_단위물량(company, str(r["프로젝트"]), quantity_df)
            for _, r in comp_df_p.iterrows()
        ) if not comp_df_p.empty else 0.0

        # 투입: 실투입공수 합계
        실적_투입 = round(float(comp_df_p["실투입공수"].sum()) if not comp_df_p.empty else 0.0, 1)

        실적_인시당 = round(실적_처리물량 / 실적_투입, 3) if 실적_투입 > 0 else 0.0

        row["실적_기성"]         = round(실적_기성, 1)
        row["실적_처리물량"]     = round(실적_처리물량, 1)
        row["실적_투입"]         = 실적_투입
        row["실적_인시당생산성"] = 실적_인시당

        # ── 잔여기간전망 ──────────────────────────────────────────
        past_wd_r, remain_wd_r = _get_wday_counts(yyyymm)

        # non-SN: kpi4 기성 - kpi3 기성 (프로젝트별 차이)
        kpi3_nonSN_기성합 = float(
            comp_df_p[~comp_df_p["프로젝트"].isin(SN_PROJECTS)]["기성공수"].sum()
        ) if not comp_df_p.empty else 0.0
        kpi4_nonSN_합_r = sum(
            v for proj, v in milestone_by_proj_prod.items() if proj not in SN_PROJECTS
        )

        # SN: kpi3 SN합 / past_wd * remain_wd
        kpi3_SN_df_r = comp_df_p[comp_df_p["프로젝트"].isin(SN_PROJECTS)] if not comp_df_p.empty else pd.DataFrame()
        kpi3_SN_기성합_r = float(kpi3_SN_df_r["기성공수"].sum()) if not kpi3_SN_df_r.empty else 0.0
        SN_연장_r = (kpi3_SN_기성합_r / past_wd_r * remain_wd_r) if past_wd_r > 0 else 0.0

        잔여_기성 = (kpi4_nonSN_합_r - kpi3_nonSN_기성합) + SN_연장_r

        # 처리물량: non-SN은 프로젝트별 (kpi4-kpi3) × 단위물량, SN은 연장분 × 단위물량
        잔여_처리물량 = 0.0
        for proj, kpi4_val in milestone_by_proj_prod.items():
            if proj not in SN_PROJECTS:
                kpi3_val = float(
                    comp_df_p[comp_df_p["프로젝트"] == proj]["기성공수"].sum()
                ) if not comp_df_p.empty else 0.0
                잔여_처리물량 += (kpi4_val - kpi3_val) * _get_단위물량(company, proj, quantity_df)
        for _, r in kpi3_SN_df_r.iterrows():
            proj_g    = float(r["기성공수"] or 0)
            proj_연장 = (proj_g / past_wd_r * remain_wd_r) if past_wd_r > 0 else 0.0
            잔여_처리물량 += proj_연장 * _get_단위물량(company, str(r["프로젝트"]), quantity_df)

        # 투입: 실투입공수합 / past_wd * remain_wd
        kpi3_전체_투입_r = float(comp_df_p["실투입공수"].sum()) if not comp_df_p.empty else 0.0
        잔여_투입 = round((kpi3_전체_투입_r / past_wd_r * remain_wd_r) if past_wd_r > 0 else 0.0, 1)

        잔여_인시당 = round(잔여_처리물량 / 잔여_투입, 3) if 잔여_투입 > 0 else 0.0

        row["잔여기간전망_기성"]         = 잔여_기성
        row["잔여기간전망_처리물량"]     = round(잔여_처리물량, 1)
        row["잔여기간전망_투입"]         = round(잔여_투입, 1)
        row["잔여기간전망_인시당생산성"] = 잔여_인시당

        합_처리 = 실적_처리물량 + 잔여_처리물량
        합_투입 = 실적_투입     + 잔여_투입

        row["실적합계_기성"]         = 실적_기성 + 잔여_기성
        row["실적합계_처리물량"]     = round(합_처리, 1)
        row["실적합계_투입"]         = round(합_투입, 1)
        row["실적합계_인시당생산성"] = round(합_처리 / 합_투입, 3) if 합_투입 > 0 else 0.0

        rows.append(row)

    df = pd.DataFrame(rows)

    total: dict = {"업체": "합계"}
    for period in PERIOD_LIST + ["실적합계"]:
        s처리 = df[f"{period}_처리물량"].sum()
        s투입 = df[f"{period}_투입"].sum()
        total[f"{period}_기성"]         = df[f"{period}_기성"].sum()
        total[f"{period}_처리물량"]     = round(s처리, 1)
        total[f"{period}_투입"]         = round(s투입, 1)
        total[f"{period}_인시당생산성"] = round(s처리 / s투입, 3) if s투입 else 0.0

    return pd.concat([df, pd.DataFrame([total])], ignore_index=True)


# ════════════════════════════════════════════════════════════════
# 협력사 BEP
# ════════════════════════════════════════════════════════════════

@st.cache_data(ttl=600)
def get_bep_data(company: str, months: tuple = None) -> pd.DataFrame:
    """
    협력사 BEP 데이터.
    months: ((year, month), ...) 튜플로 전달 시 해당 월들로 컬럼 구성.
            None 이면 기본 (전월, 당월, 익월).
    각 월은 당월 yyyymm 보다 작으면 실적(lq_kpi3_5 기성금), 같거나 크면 전망(BEP) 사용.
    """
    if months is None:
        labels      = get_month_labels()
        months_info = [labels["전월"], labels["당월"], labels["익월"]]
    else:
        months_info = [_month_info(y, m) for y, m in months]

    # 당월 기준 yyyymm (실적/전망 분기)
    _today = date.today()
    curr_yyyymm = f"{_today.year:04d}{_today.month:02d}"

    goal_df     = get_goal_data()
    quantity_df = get_quantity_data()

    goal_gongjon = COMPANY_GOAL_GONGJON.get(company, "선실목의")
    keyword      = COMPANY_KEYWORD.get(company, company)

    result: dict[str, list] = {item: [] for item in BEP_ITEMS}

    for m in months_info:
        yyyymm = m["yyyymm"]
        yymm   = m["yymm"]
        월컬럼  = f"{m['월']}월"

        # 월별 단가 조회 (해당월 없으면 이전월 fallback)
        unitcost = get_unitcost(yyyymm)
        단가     = unitcost.get(COMPANY_UNITCOST_COL.get(company, "목의"), 0)

        bep_raw = get_bep_raw(company, yyyymm)

        is_past = yyyymm < curr_yyyymm    # 과거월 → 실적 기성금
        is_curr = yyyymm == curr_yyyymm   # 당월

        if is_past:
            gisang_df   = get_gisang_data(yymm)
            comp_gisang = gisang_df[gisang_df["협력사"].str.contains(keyword, na=False)]
            기성금 = float(comp_gisang["기성금액"].sum()) if not comp_gisang.empty else 0.0
        else:
            # (운반선 + SN합계) × 단가 + 외주비
            # "기성전망_운반선" 키 우선, 없으면 "운반선" fallback
            def _bep_get(key1, key2=""):
                v = bep_raw.get(key1, None)
                if v is None and key2:
                    v = bep_raw.get(key2, 0)
                return float(v or 0)

            기성전망_운반선_bep = _bep_get("기성전망_운반선", "운반선")
            SN_공수_bep = sum(
                _bep_get(f"기성전망_{sn}", sn) for sn in SN_PROJECTS
            )
            외주비 = _bep_get("기성전망_외주비", "외주비")
            기성금 = (기성전망_운반선_bep + SN_공수_bep) * 단가 + 외주비

        지출_result    = _calc_지출금(bep_raw)
        지출금         = 지출_result["지출금_합계"]
        월급내국인_소계 = 지출_result["월급_내국인_소계"]
        간접_소계      = 지출_result["간접_소계"]

        손익 = 기성금 - 지출금

        goal_row = goal_df[
            (goal_df["공종"] == goal_gongjon) & (goal_df["구분"] == "목표")
        ]
        인시당_목표 = (
            float(goal_row.iloc[0][월컬럼])
            if not goal_row.empty and 월컬럼 in goal_row.columns
            else 0.0
        )

        if is_past or is_curr:
            처리물량, 투입실적 = _get_company_실적(company, yymm, yyyymm, quantity_df)
            인시당_실적 = round(처리물량 / 투입실적, 3) if 투입실적 > 0 else 0.0
        else:
            처리물량  = 0.0
            투입실적  = 0.0
            인시당_실적 = 0.0

        기성전망_val = float(bep_raw.get("기성전망_운반선", 0) or 0)
        투입전망_val = float(bep_raw.get("투입전망_합계",  0) or 0)
        gongjon_col  = COMPANY_GONGJON.get(company, "목의") + "_단위물량"
        avg_단위물량 = (
            float(quantity_df[gongjon_col].mean())
            if not quantity_df.empty and gongjon_col in quantity_df.columns
            else 0.0
        )
        전망_처리물량 = 기성전망_val * avg_단위물량

        인시당_bep = _calc_인시당_bep(
            처리물량=전망_처리물량,
            투입=투입전망_val,
            지출금=지출금,
            기성금=기성금,
            월급_내국인_소계=월급내국인_소계,
            간접_소계=간접_소계,
        )

        result["기성금"].append(기성금)
        result["지출금"].append(지출금)
        result["손익"].append(손익)
        result["인시당(목표)"].append(인시당_목표)
        result["인시당(BEP)"].append(인시당_bep)
        result["인시당(실적)"].append(인시당_실적)

    month_labels = [m["label"] for m in months_info]
    df = pd.DataFrame(result, index=month_labels).T
    df.index.name = "항목"
    df.reset_index(inplace=True)
    return df


@st.cache_data(ttl=600)
def get_labor_data(company: str) -> pd.DataFrame:
    """
    협력사별 인건비 데이터 반환.
    카테고리별 1행, 인원/단가를 월별로 나란히 배치 (MultiIndex 컬럼).
    Columns: MultiIndex [(전월,인원),(전월,단가),(당월,인원),(당월,단가),(익월,인원),(익월,단가)]
    Rows: 카테고리 (3개월 모두 인원=0인 항목 제외)
    비율 항목(경비비율/상여비율/물량팀_퇴직금/물량팀_4대보험)은 단일값 행으로 추가
    """
    labels = get_month_labels()
    months = [labels["전월"], labels["당월"], labels["익월"]]
    month_labels_list = [m["label"] for m in months]

    # 카테고리별 인원/단가 쌍
    PAIR_CATEGORIES = [
        "시급_내국인", "시급_외국인",
        "월급_내국인", "월급_외국인",
        "간접",
        "직시급_직종1", "직시급_직종2", "직시급_직종3",
        "본공_직종1",   "본공_직종2",   "본공_직종3",
    ]
    # 단일값 항목
    SINGLE_ITEMS = ["물량팀_퇴직금", "물량팀_4대보험"]

    # 월별 bep_raw 로드
    bep_raws = {m["label"]: get_bep_raw(company, m["yyyymm"]) for m in months}

    # ── 인원/단가 병렬 행 ─────────────────────────────────────────
    pair_rows = []
    for cat in PAIR_CATEGORIES:
        row = {"구분": cat}
        all_zero = True
        for lbl in month_labels_list:
            raw = bep_raws[lbl]
            인원 = float(raw.get(f"{cat}_인원", 0) or 0)
            단가 = float(raw.get(f"{cat}_단가", 0) or 0)
            row[(lbl, "인원")] = f"{int(인원):,}" if 인원 != 0 else "-"
            row[(lbl, "단가")] = f"{단가:,.0f}" if 단가 != 0 else "-"
            if 인원 != 0:
                all_zero = False
        if not all_zero:
            pair_rows.append(row)

    # ── 단일값 행 ─────────────────────────────────────────────────
    single_rows = []
    for item in SINGLE_ITEMS:
        row = {"구분": item}
        all_zero = True
        for lbl in month_labels_list:
            raw = bep_raws[lbl]
            val = float(raw.get(item, 0) or 0)
            if item in ("경비비율", "상여비율"):
                row[(lbl, "인원")] = f"{val*100:.1f}%" if val != 0 else "-"
            else:
                row[(lbl, "인원")] = f"{val:,.0f}" if val != 0 else "-"
            row[(lbl, "단가")] = ""   # 단일값은 단가 칸 비움
            if val != 0:
                all_zero = False
        if not all_zero:
            single_rows.append(row)

    all_rows = pair_rows + single_rows
    if not all_rows:
        return pd.DataFrame()

    # MultiIndex DataFrame 생성
    mi_cols = [("", "구분")] + [(lbl, sub) for lbl in month_labels_list for sub in ["인원", "단가"]]
    flat_cols = ["구분"] + [f"{lbl}_{sub}" for lbl in month_labels_list for sub in ["인원", "단가"]]

    records = []
    for row in all_rows:
        rec = {"구분": row["구분"]}
        for lbl in month_labels_list:
            rec[f"{lbl}_인원"] = row.get((lbl, "인원"), "-")
            rec[f"{lbl}_단가"] = row.get((lbl, "단가"), "-")
        records.append(rec)

    df = pd.DataFrame(records, columns=flat_cols)
    df.columns = pd.MultiIndex.from_tuples(mi_cols)
    return df


def _calc_지출금_detail(bep_raw: dict) -> list[dict]:
    """
    지출금 항목별 세부 분해 (급여/퇴직금/보험/경비/소계).
    0인 항목은 포함하되 get_expense_data에서 필터링.
    """
    경비비율 = bep_raw.get("경비비율", 0) or 0
    상여비율 = bep_raw.get("상여비율", 0) or 0
    물량팀_퇴직금  = bep_raw.get("물량팀_퇴직금", 0) or 0
    물량팀_4대보험 = bep_raw.get("물량팀_4대보험", 0) or 0

    rows: list[dict] = []
    총급여 = 총퇴직 = 총보험 = 총경비 = 0.0

    def _add(항목, 급여, 퇴직, 보험, 경비):
        nonlocal 총급여, 총퇴직, 총보험, 총경비
        소계 = 급여 + 퇴직 + 보험 + 경비
        rows.append({"항목": 항목, "급여": round(급여), "퇴직금": round(퇴직),
                     "보험": round(보험), "경비": round(경비), "소계": round(소계)})
        총급여 += 급여; 총퇴직 += 퇴직; 총보험 += 보험; 총경비 += 경비

    # 시급_내국인
    인원 = bep_raw.get("시급_내국인_인원", 0) or 0
    단가 = bep_raw.get("시급_내국인_단가", 0) or 0
    if 인원 > 0 and 단가 > 0:
        base = 인원 * 단가 * 209 + 단가 * (52/12) * 8 + (단가 * 209) / 12 * 상여비율 + 단가 * 8 * 15 / 12
        _add("시급_내국인", base, base/12, base*_4대보험율, base*경비비율)

    # 시급_외국인
    인원 = bep_raw.get("시급_외국인_인원", 0) or 0
    단가 = bep_raw.get("시급_외국인_단가", 0) or 0
    if 인원 > 0 and 단가 > 0:
        base = 인원 * 단가 * 209 + 단가 * (52/12) * 8 + (단가 * 209) / 12 * 상여비율 + 단가 * 8 * 15 / 12
        _add("시급_외국인", base, base/12, base*_4대보험율, base*경비비율)

    # 월급_내국인
    인원 = bep_raw.get("월급_내국인_인원", 0) or 0
    단가 = bep_raw.get("월급_내국인_단가", 0) or 0
    if 인원 > 0 and 단가 > 0:
        월급 = 인원 * 단가
        base = 월급 + 월급 * 0.70 / 12 * 상여비율 + 월급 * 0.70 / 209 * 8 * 15 / 12
        _add("월급_내국인", base, base/12, base*_4대보험율, base*경비비율)

    # 월급_외국인
    인원 = bep_raw.get("월급_외국인_인원", 0) or 0
    단가 = bep_raw.get("월급_외국인_단가", 0) or 0
    if 인원 > 0 and 단가 > 0:
        월급 = 인원 * 단가
        base = 월급 + 월급 * 0.70 / 12 * 상여비율 + 월급 * 0.70 / 209 * 8 * 15 / 12
        _add("월급_외국인", base, base/12, base*_4대보험율, base*경비비율)

    # 간접
    인원 = bep_raw.get("간접_인원", 0) or 0
    단가 = bep_raw.get("간접_단가", 0) or 0
    if 인원 > 0 and 단가 > 0:
        월급 = 인원 * 단가
        base = 월급 + 월급 * 0.70 / 12 * 상여비율 + 월급 * 0.70 / 209 * 8 * 15 / 12
        _add("간접", base, base/12, base*_4대보험율, base*경비비율)

    # 직시급_직종1,2,3
    투입전망     = bep_raw.get("투입전망_합계", 0) or 0
    직시급총인원 = sum(bep_raw.get(f"직시급_직종{i}_인원", 0) or 0 for i in [1, 2, 3])
    wd = 209 / 8
    가급 = max(0.0, (투입전망 / 직시급총인원 / wd) - 8) if 직시급총인원 > 0 else 0.0
    for i in [1, 2, 3]:
        인원 = bep_raw.get(f"직시급_직종{i}_인원", 0) or 0
        단가 = bep_raw.get(f"직시급_직종{i}_단가", 0) or 0
        if 인원 > 0 and 단가 > 0:
            급여 = 인원 * 단가 * (8 + 가급) * wd
            퇴직 = (물량팀_퇴직금  / 직시급총인원) * 인원 if 직시급총인원 > 0 else 0
            보험 = (물량팀_4대보험 / 직시급총인원) * 인원 if 직시급총인원 > 0 else 0
            _add(f"직시급_직종{i}", 급여, 퇴직, 보험, 급여*경비비율)

    # 본공_직종1,2,3
    for i in [1, 2, 3]:
        인원 = bep_raw.get(f"본공_직종{i}_인원", 0) or 0
        단가 = bep_raw.get(f"본공_직종{i}_단가", 0) or 0
        if 인원 > 0 and 단가 > 0:
            급여 = 단가 * wd
            base = 급여 + 단가 / 15 / 12
            _add(f"본공_직종{i}", 인원*base, 인원*base/12, 인원*base*0.1262, 인원*급여*경비비율)

    # 합계 행
    rows.append({"항목": "지출금 합계", "급여": round(총급여), "퇴직금": round(총퇴직),
                 "보험": round(총보험), "경비": round(총경비),
                 "소계": round(총급여 + 총퇴직 + 총보험 + 총경비)})
    return rows


@st.cache_data(ttl=600)
def get_expense_data(company: str) -> list[dict]:
    """
    협력사별 지출금 세부 분해 데이터 반환.
    Returns: 그룹 구조 리스트
    [
        {
            "group": "시급_내국인",
            "소계": {"전월": "1,234,567", "당월": "...", "익월": "..."},
            "detail": [
                {"항목": "급여",   "전월": "...", "당월": "...", "익월": "..."},
                {"항목": "퇴직금", ...},
                {"항목": "보험",   ...},
                {"항목": "경비",   ...},
            ]
        },
        ...
        {"group": "지출금 합계", "소계": {...}, "detail": []}
    ]
    3개월 모두 0인 그룹은 제외
    """
    labels = get_month_labels()
    months = [labels["전월"], labels["당월"], labels["익월"]]
    month_labels_list = [m["label"] for m in months]

    month_details: dict[str, list[dict]] = {
        m["label"]: _calc_지출금_detail(get_bep_raw(company, m["yyyymm"]))
        for m in months
    }

    # 항목 순서 수집 (합계 제외)
    all_items: list[str] = []
    for lbl in month_labels_list:
        for r in month_details[lbl]:
            if r["항목"] not in all_items and r["항목"] != "지출금 합계":
                all_items.append(r["항목"])

    def _fmt(val: float) -> str:
        return f"{val:,.0f}" if val != 0 else "-"

    groups: list[dict] = []

    for 항목 in all_items:
        # 소계값 수집
        소계_vals = {}
        for lbl in month_labels_list:
            detail = next((r for r in month_details[lbl] if r["항목"] == 항목), None)
            소계_vals[lbl] = _fmt(detail["소계"] if detail else 0)

        # 3개월 모두 "-"면 제외
        if all(v == "-" for v in 소계_vals.values()):
            continue

        # 세부 항목
        sub_rows = []
        for sub in ["급여", "퇴직금", "보험", "경비"]:
            row = {"항목": sub}
            all_zero = True
            for lbl in month_labels_list:
                detail = next((r for r in month_details[lbl] if r["항목"] == 항목), None)
                val = detail[sub] if detail else 0
                row[lbl] = _fmt(val)
                if val != 0:
                    all_zero = False
            if not all_zero:
                sub_rows.append(row)

        groups.append({"group": 항목, "소계": 소계_vals, "detail": sub_rows})

    # 지출금 합계 행 추가
    합계_vals = {}
    for lbl in month_labels_list:
        detail = next((r for r in month_details[lbl] if r["항목"] == "지출금 합계"), None)
        합계_vals[lbl] = _fmt(detail["소계"] if detail else 0)
    groups.append({"group": "지출금 합계", "소계": 합계_vals, "detail": []})

    return groups


@st.cache_data(ttl=600)
def get_labor_expense_data(company: str, months: tuple = None) -> list[dict]:
    """
    인건비 + 지출금 상세 통합 데이터.
    months: ((year, month), ...) 튜플로 전달 시 해당 월들로 구성. None 이면 전월/당월/익월.
    Returns list of groups, each:
        {"group": str, "type": "pair"|"single"|"total",
         "months": {lbl: {"인원":str,"단가":str,"소계":str}},
         "detail": [{"항목":str, lbl:str, ...}]}
    """
    if months is None:
        labels = get_month_labels()
        months_info = [labels["전월"], labels["당월"], labels["익월"]]
    else:
        months_info = [_month_info(y, m) for y, m in months]
    mlabels = [m["label"] for m in months_info]

    PAIR_CATS = [
        "시급_내국인", "시급_외국인",
        "월급_내국인", "월급_외국인",
        "간접",
        "직시급_직종1", "직시급_직종2", "직시급_직종3",
        "본공_직종1",   "본공_직종2",   "본공_직종3",
    ]
    SINGLE_ITEMS = ["물량팀_퇴직금", "물량팀_4대보험"]

    bep_raws = {m["label"]: get_bep_raw(company, m["yyyymm"]) for m in months_info}
    exp_dets = {m["label"]: _calc_지출금_detail(bep_raws[m["label"]]) for m in months_info}

    def _n(v):  return f"{v:,.0f}" if v != 0 else "-"
    def _p(v):  return f"{v*100:.1f}%" if v != 0 else "-"
    def _sub(lbl, cat, key):
        d = next((r for r in exp_dets[lbl] if r["항목"] == cat), None)
        return _n(d[key] if d else 0)

    groups = []

    for cat in PAIR_CATS:
        mdata, all_zero = {}, True
        for lbl in mlabels:
            raw  = bep_raws[lbl]
            인원  = float(raw.get(f"{cat}_인원", 0) or 0)
            단가  = float(raw.get(f"{cat}_단가", 0) or 0)
            d    = next((r for r in exp_dets[lbl] if r["항목"] == cat), None)
            소계  = d["소계"] if d else 0
            mdata[lbl] = {"인원": f"{int(인원):,}" if 인원 else "-", "단가": _n(단가), "소계": _n(소계)}
            if 인원: all_zero = False
        if all_zero: continue
        detail = []
        for sub in ["급여", "퇴직금", "보험", "경비"]:
            vals = {lbl: _sub(lbl, cat, sub) for lbl in mlabels}
            if all(v == "-" for v in vals.values()): continue
            detail.append({"항목": sub, **vals})
        groups.append({"group": cat, "type": "pair", "months": mdata, "detail": detail})

    for item in SINGLE_ITEMS:
        mdata, all_zero = {}, True
        for lbl in mlabels:
            val = float(bep_raws[lbl].get(item, 0) or 0)
            fmt = _n(val)
            mdata[lbl] = {"인원": fmt, "단가": "", "소계": ""}
            if val: all_zero = False
        if all_zero: continue
        groups.append({"group": item, "type": "single", "months": mdata, "detail": []})

    total = {}
    for lbl in mlabels:
        d = next((r for r in exp_dets[lbl] if r["항목"] == "지출금 합계"), None)
        total[lbl] = {"인원": "", "단가": "", "소계": _n(d["소계"] if d else 0)}
    groups.append({"group": "지출금 합계", "type": "total", "months": total, "detail": []})

    return groups