"""
╔══════════════════════════════════════════════════════════════════╗
║ 항목 : [데이터 전용] kpi_2 - 글로벌 BEP 실적 ║
║ 수정일 : 2026-04-08 ║
╚══════════════════════════════════════════════════════════════════╝

【 BEP 공식 】
  BEP = (기성합계 × 단가) / 급여합계_보정
  급여합계_보정 = 기본급합계 + 특잔업비합계 + (30 - 실제급여일수) × 마지막날인원_일기본급

【 인사이동 처리 】
  인원정보에 같은 사번 2행:
  - 이동 전 반: 퇴사일 = 이동 전날 (예: 2026-04-14)
  - 이동 후 반: 배치일_고정 = 이동일 (예: 2026-04-15), 퇴사일 = NULL
  - 이동 후 반: 개월수_보정 = 숙련도 보정 개월 (예: 6)
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import date, timedelta
from sqlalchemy import text

from utils.db import get_engine

# ══════════════════════════════════════════════════════════
# 상수
# ══════════════════════════════════════════════════════════

정상근무시간 = 8.0
최대개월차 = 52

반_표시명 = {
    "선실부선실1과설치1직2반": "설치1직2반",
    "선실부선실2과취부반": "취부반",
    "선실부선실2과곡직반": "곡직반",
    "선실부선실전장과전장1직3반": "전장1직3반",
}
반_그룹매핑 = {
    "곡직반": "1그룹", "취부반": "1그룹",
    "설치1직2반": "2그룹", "전장1직3반": "2그룹",
}
반_표시순서 = ["취부반", "곡직반", "설치1직2반", "전장1직3반"]
그룹_반목록 = {"1그룹": ["곡직반", "취부반"], "2그룹": ["설치1직2반", "전장1직3반"]}
설치1직2반_내국인비율 = 2 / 11
GLOBAL_작업부서 = set(반_표시명.keys())

# ══════════════════════════════════════════════════════════
# 내부 유틸
# ══════════════════════════════════════════════════════════

def _run_query(sql: str) -> pd.DataFrame:
    engine = get_engine()
    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn)

def _급여월(d) -> str:
    import datetime as dt
    if d is None: return None
    try:
        if pd.isna(d): return None
    except Exception:
        pass
    if not isinstance(d, dt.date):
        d = pd.to_datetime(d).date()
    if d.day >= 11:
        return f"{d.year+1}-01" if d.month == 12 else f"{d.year}-{d.month+1:02d}"
    return f"{d.year}-{d.month:02d}"

def _get_개월차(배치일, 기준일=None, 보정개월: int = 0) -> int:
    import calendar as cal, datetime as dt
    try:
        if pd.isna(배치일): return max(보정개월 if 보정개월 > 0 else 1, 1)
    except Exception:
        pass
    if 기준일 is None: 기준일 = date.today()
    if not isinstance(배치일, dt.date): 배치일 = pd.to_datetime(배치일).date()
    if not isinstance(기준일, dt.date): 기준일 = pd.to_datetime(기준일).date()
    말일 = cal.monthrange(배치일.year, 배치일.month)[1]
    if 배치일.day == 말일:
        시작월 = date(배치일.year+1, 1, 1) if 배치일.month == 12 else date(배치일.year, 배치일.month+1, 1)
    else:
        시작월 = date(배치일.year, 배치일.month, 1)
    경과개월 = (기준일.year - 시작월.year)*12 + (기준일.month - 시작월.month)
    if 보정개월 > 0:
        개월차 = 보정개월 + 경과개월
    else:
        개월차 = 경과개월 + 1
    return min(max(개월차, 1), 최대개월차)

def _사번_str(v):
    try: return str(int(float(v)))
    except: return str(v).strip()

def _월범위(월: str):
    yr, mo = int(월[:4]), int(월[5:7])
    시작 = date(yr-1, 12, 11) if mo == 1 else date(yr, mo-1, 11)
    종료 = date(yr, mo, 10)
    return 시작, 종료

def _to_date_safe(v):
    if v is None: return None
    try:
        if pd.isna(v): return None
    except Exception:
        pass
    if isinstance(v, pd.Timestamp):
        return v.date()
    import datetime as _dt
    if isinstance(v, _dt.datetime):
        return v.date()
    if isinstance(v, _dt.date):
        return v
    try:
        return pd.to_datetime(v).date()
    except Exception:
        return None

# ══════════════════════════════════════════════════════════
# 원자 로드 함수 (캐시)
# ══════════════════════════════════════════════════════════

@st.cache_data(ttl=3600)
def load_인원정보() -> pd.DataFrame:
    df = _run_query("SELECT * FROM dbo.lq_kpi2_1")
    df["배치일_고정"] = pd.to_datetime(df["배치일_고정"], errors="coerce")
    df["사번"] = df["사번"].astype(str).str.strip()
    df["퇴사일"] = pd.to_datetime(df["퇴사일"], errors="coerce")
    df["퇴사일"] = df["퇴사일"].apply(
        lambda d: None if pd.isna(d) or d.year < 2000 else d.date())
    if "급여그룹" in df.columns:
        df["급여그룹"] = df["급여그룹"].astype(str).str.strip()
    if "부서" in df.columns:
        df["부서"] = df["부서"].astype(str).str.strip()
    if "개월수_보정" in df.columns:
        df["개월수_보정"] = pd.to_numeric(df["개월수_보정"], errors="coerce").fillna(0).astype(int)
    else:
        df["개월수_보정"] = 0
    if "급여제외" in df.columns:
        df["급여제외"] = pd.to_datetime(df["급여제외"], errors="coerce")
        df["급여제외"] = df["급여제외"].apply(
            lambda d: None if pd.isna(d) else d.date())
    else:
        df["급여제외"] = None
    return df

@st.cache_data(ttl=3600)
def load_급여정보() -> pd.DataFrame:
    df = _run_query("SELECT * FROM dbo.lq_kpi2_2")
    if "그룹" in df.columns:
        df["그룹"] = df["그룹"].astype(str).str.strip()
    if "복리후생비용" not in df.columns:
        df["복리후생비용"] = 0.0
    df["복리후생비용"] = pd.to_numeric(df["복리후생비용"], errors="coerce").fillna(0.0)
    return df

@st.cache_data(ttl=3600)
def load_휴일() -> set:
    df = _run_query("SELECT * FROM dbo.lq_kpi2_3")
    return set(pd.to_datetime(df["휴일"]).dt.date)

@st.cache_data(ttl=3600)
def load_연간목표() -> pd.DataFrame:
    return _run_query("SELECT * FROM dbo.lq_kpi2_4")

@st.cache_data(ttl=3600)
def load_직종단가(기준월: str = None) -> dict:
    if 기준월 is None:
        기준월 = _급여월(date.today())

    df_단가 = _run_query("SELECT * FROM dbo.lq_kpi2_5")

    단가_쌍 = []
    for col in df_단가.columns:
        if col.endswith("년단가"):
            연도_str = col.replace("년단가", "")
            적용월_col = f"{연도_str}년적용월"
            if 적용월_col in df_단가.columns:
                단가_쌍.append((연도_str, col, 적용월_col))
    단가_쌍.sort(key=lambda x: x[0], reverse=True)

    df_연간 = load_연간목표()
    반_공종 = (df_연간[df_연간["반"].isin(반_표시명.keys())][["반","공종"]]
               .drop_duplicates().set_index("반")["공종"].to_dict())

    # 1순위: 직종단가구분 키 사전 / 2순위: 직종 키 사전
    공종_단가_primary = {}
    공종_단가_fallback = {}
    for _, row in df_단가.iterrows():
        구분키 = str(row.get("직종단가구분") or "").strip()
        직종키 = str(row.get("직종") or "").strip()
        if not 구분키 and not 직종키:
            continue

        선택단가 = None

        if 단가_쌍:
            for 연도_str, 단가_col, 적용월_col in 단가_쌍:
                적용월_raw = row.get(적용월_col)
                if 적용월_raw is None or (isinstance(적용월_raw, float) and pd.isna(적용월_raw)):
                    continue
                try:
                    if isinstance(적용월_raw, (int, float)):
                        적용월_str = str(pd.Timestamp('1899-12-30') + pd.Timedelta(days=int(적용월_raw)))[:7]
                    else:
                        적용월_str = str(pd.to_datetime(적용월_raw).date())[:7]
                except Exception:
                    적용월_str = str(적용월_raw).strip()[:7]

                if not 적용월_str or len(적용월_str) < 7 or 기준월 < 적용월_str:
                    continue
                단가_val = row.get(단가_col)
                if 단가_val is not None and not (isinstance(단가_val, float) and pd.isna(단가_val)):
                    try:
                        선택단가 = float(단가_val)
                        break
                    except Exception:
                        pass

            if 선택단가 is None:
                for _, 단가_col, _ in reversed(단가_쌍):
                    val = row.get(단가_col)
                    if val is not None and not (isinstance(val, float) and pd.isna(val)):
                        try:
                            선택단가 = float(val)
                            break
                        except Exception:
                            pass
        else:
            년단가_cols = [c for c in df_단가.columns if c.endswith("년단가")]
            년단가_cols.sort(reverse=True)
            for col in 년단가_cols:
                val = row.get(col)
                if val is not None and not (isinstance(val, float) and pd.isna(val)):
                    try:
                        선택단가 = float(val)
                        break
                    except Exception:
                        pass

        if 선택단가 is not None and 선택단가 > 0:
            if 구분키:
                공종_단가_primary[구분키] = 선택단가
            if 직종키:
                공종_단가_fallback[직종키] = 선택단가

    반_단가 = {}
    for 반명, 공종 in 반_공종.items():
        # 1순위: 직종단가구분 정확 일치
        if 공종 in 공종_단가_primary:
            반_단가[반명] = 공종_단가_primary[공종]
            continue
        # 2순위: 직종 정확 일치
        if 공종 in 공종_단가_fallback:
            반_단가[반명] = 공종_단가_fallback[공종]
            continue
        # 3순위: 부분 매칭 (직종단가구분 → 직종 순)
        매칭 = next((v for k, v in 공종_단가_primary.items() if 공종 in k or k in 공종), None)
        if 매칭 is None:
            매칭 = next((v for k, v in 공종_단가_fallback.items() if 공종 in k or k in 공종), None)
        반_단가[반명] = 매칭 if 매칭 else 0.0
    return 반_단가

@st.cache_data(ttl=3600)
def load_그룹단가() -> dict:
    반_단가 = load_직종단가()
    그룹_단가 = {}
    for 그룹명, 반_표시_목록 in 그룹_반목록.items():
        단가_list = []
        for 반_표시 in 반_표시_목록:
            반_전체명 = next((k for k,v in 반_표시명.items() if v == 반_표시), None)
            if 반_전체명 and 반_단가.get(반_전체명, 0) > 0:
                단가_list.append(반_단가[반_전체명])
        그룹_단가[그룹명] = np.mean(단가_list) if 단가_list else 0.0
    return 그룹_단가

@st.cache_data(ttl=3600)
def load_목표BEP(year: int = None) -> pd.DataFrame:
    if year is None: year = date.today().year
    df = _run_query(
        "SELECT 반, 공종, 월구분, 목표BEP FROM dbo.lq_kpi2_4 "
        "WHERE 목표BEP IS NOT NULL AND (월구분 LIKE N'%월' OR 월구분 = N'연간')")
    if df.empty: return pd.DataFrame()
    def _to_월str(v):
        v = str(v).strip()
        if v == "연간": return "ANNUAL"
        try: return f"{year}-{int(v.replace('월','').strip()):02d}"
        except: return None
    df["월_str"] = df["월구분"].apply(_to_월str)
    df = df.dropna(subset=["월_str"])
    rows = []
    for _, row in df[(df["반"].str.strip()=="선실부") & df["공종"].isin(["1그룹","2그룹"])].iterrows():
        구분 = "ANNUAL_GROUP" if row["월_str"]=="ANNUAL" else "GROUP"
        rows.append({"그룹코드": row["공종"], "구분": 구분, "월_str": row["월_str"], "목표BEP": float(row["목표BEP"])})
    for _, row in df[df["반"].isin(반_표시명.keys())].iterrows():
        반_표시 = 반_표시명.get(row["반"])
        if 반_표시:
            구분 = "ANNUAL_TEAM" if row["월_str"]=="ANNUAL" else "TEAM"
            rows.append({"그룹코드": 반_표시, "구분": 구분, "월_str": row["월_str"], "목표BEP": float(row["목표BEP"])})
    return pd.DataFrame(rows) if rows else pd.DataFrame()

@st.cache_data(ttl=3600)
def load_효율목표() -> pd.DataFrame:
    df = _run_query("SELECT * FROM dbo.lq_kpi2_6")
    df["개월차"] = pd.to_numeric(df["개월차"], errors="coerce")
    df["효율목표"] = pd.to_numeric(df["효율목표"], errors="coerce")
    return df

@st.cache_data(ttl=3600)
def load_능률목표() -> pd.DataFrame:
    df = _run_query("SELECT * FROM dbo.lq_kpi2_7")
    df["개월차"] = pd.to_numeric(df["개월차"], errors="coerce")
    df["능률목표"] = pd.to_numeric(df["능률목표"], errors="coerce")
    return df

@st.cache_data(ttl=3600)
def load_실동률목표() -> pd.DataFrame:
    df = _run_query("SELECT * FROM dbo.lq_kpi2_8")
    df["개월차"] = pd.to_numeric(df["개월차"], errors="coerce")
    df["실동률목표"] = pd.to_numeric(df["실동률목표"], errors="coerce")
    return df

@st.cache_data(ttl=3600)
def load_raw(year: int = None) -> pd.DataFrame:
    if year is None: year = date.today().year
    df = _run_query(
        f"SELECT * FROM dbo.lq_kpi2_9 "
        f"WHERE 작업일 >= '{year-1}-12-11' AND 작업일 <= '{year}-12-10'")
    df["작업일"] = pd.to_datetime(df["작업일"], errors="coerce").dt.date
    df = df.dropna(subset=["작업일"])
    df["사번"] = df["사번"].astype(str).str.strip()
    df["OP코드"] = df["OP코드"].astype(str).str.strip()
    df["MH"] = pd.to_numeric(df["MH"], errors="coerce").fillna(0)
    df["작업월"] = df["작업일"].apply(_급여월)
    return df

@st.cache_data(ttl=3600)
def load_기성(year: int = None) -> pd.DataFrame:
    if year is None: year = date.today().year
    global_wc = ("'선실부선실1과설치1직2반','선실부선실2과취부반',"
                 "'선실부선실2과곡직반','선실부선실전장과전장1직3반'")
    df = _run_query(
        f"SELECT * FROM dbo.lq_kpi1_1 "
        f"WHERE [A3 작업장 내역] IN ({global_wc}) "
        f" AND [날짜] >= '{year-1}-12-11' AND [날짜] <= '{year}-12-31'")
    df = df.rename(columns={"날짜":"날짜","A3 작업장 내역":"반","기성":"기성","투입":"투입"})
    df["날짜"] = pd.to_datetime(df["날짜"], errors="coerce").dt.date
    df["월"] = df["날짜"].apply(_급여월)
    df["주차"] = pd.to_datetime(df["날짜"]).dt.strftime("%Y-W%V")
    for col in ["기성","투입"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df

# ══════════════════════════════════════════════════════════
# 목표효율 내부 계산
# ══════════════════════════════════════════════════════════

def _calc_반별_목표효율_내부(year: int) -> pd.DataFrame:
    df_인원 = load_인원정보()
    df_효율 = load_효율목표()
    df_능률 = load_능률목표()
    df_실동률 = load_실동률목표()
    df_연간 = load_연간목표()
    반_공종 = (df_연간[["반","공종"]].drop_duplicates().set_index("반")["공종"].to_dict())
    rows = []
    for 반명, 그룹df in df_인원.groupby("부서"):
        공종 = 반_공종.get(반명)
        if not 공종: continue
        for m in range(1, 13):
            월str = f"{year}-{m:02d}"
            기준일 = date(year-1, 12, 1) if m == 1 else date(year, m-1, 1)
            월_시작 = date(year-1, 12, 11) if m == 1 else date(year, m-1, 11)
            월_종료 = date(year, m, 10)
            재직_df = 그룹df[그룹df.apply(
                lambda row: (
                    (_to_date_safe(row.get("배치일_고정")) is None or
                     _to_date_safe(row.get("배치일_고정")) <= 월_종료)
                    and
                    (row.get("퇴사일") is None or
                     (isinstance(row.get("퇴사일"), date) and row.get("퇴사일") > 월_시작))
                ), axis=1
            )]
            효율_v, 능률_v, 실동률_v = [], [], []
            for _, row in 재직_df.iterrows():
                보정개월 = int(row.get("개월수_보정", 0) or 0)
                개월차 = _get_개월차(row["배치일_고정"], 기준일, 보정개월)
                v = df_효율[(df_효율["공종"]==공종)&(df_효율["개월차"]==개월차)]["효율목표"]
                if not v.empty: 효율_v.append(float(v.iloc[0]))
                v = df_능률[(df_능률["공종"]==공종)&(df_능률["개월차"]==개월차)]["능률목표"]
                if not v.empty: 능률_v.append(float(v.iloc[0]))
                v = df_실동률[(df_실동률["공종"]==공종)&(df_실동률["개월차"]==개월차)]["실동률목표"]
                if not v.empty: 실동률_v.append(float(v.iloc[0]))
            rows.append({
                "반": 반명, "반_표시": 반_표시명.get(반명, 반명),
                "월": 월str,
                "목표효율": np.mean(효율_v) if 효율_v else np.nan,
                "목표능률": np.mean(능률_v) if 능률_v else np.nan,
                "목표실동률": np.mean(실동률_v) if 실동률_v else np.nan,
            })
    return pd.DataFrame(rows)

# ══════════════════════════════════════════════════════════
# 급여 보정 유틸
# ══════════════════════════════════════════════════════════

def _급여보정(df_반: pd.DataFrame, 반전체명: str, 기준일: date) -> float:
    df_인원 = load_인원정보()
    df_급여정보 = load_급여정보()
    급여_dict = df_급여정보.set_index("그룹")[["월급여","복리후생비용"]].to_dict("index")
    df_반인원 = df_인원[df_인원["부서"] == 반전체명]

    마지막날_일합계 = 0.0 # 기본급 + 복리후생
    for _, p in df_반인원.iterrows():
        g = str(p.get("급여그룹", "") or "").strip()
        if not g or g not in 급여_dict: continue
        퇴사일 = p.get("퇴사일")
        배치일 = _to_date_safe(p.get("배치일_고정"))
        급여제외 = p.get("급여제외")
        if 배치일 is not None and 기준일 < 배치일: continue
        if 퇴사일 is not None and 기준일 >= 퇴사일: continue
        if 급여제외 is not None and 기준일 <= 급여제외: continue
        월급여 = float(급여_dict[g].get("월급여", 0) or 0)
        복리후생 = float(급여_dict[g].get("복리후생비용", 0) or 0)
        마지막날_일합계 += (월급여 + 복리후생) / 30

    실제일수 = len(df_반["날짜"].unique()) if "날짜" in df_반.columns else 30
    보정일수 = 실제일수 - 30
    return -보정일수 * 마지막날_일합계

# ══════════════════════════════════════════════════════════
# 단일 진실 소스: build_일별_기초
# ══════════════════════════════════════════════════════════

@st.cache_data(ttl=300)
def build_일별_기초(year: int = None) -> pd.DataFrame:
    from data.kpi_4_data import (
        load_data as load_milestone_data,
        get_col_map, compute_kiseong,
    )

    if year is None: year = date.today().year
    오늘 = date.today()

    df_인원 = load_인원정보()
    df_급여정보 = load_급여정보()
    df_기성_raw = load_기성(year)
    df_raw = load_raw(year)
    휴일_set = load_휴일()
    df_효율 = load_효율목표()

    # 반 → 공종 매핑 (급여제외 인원 효율목표 조회용)
    df_연간_temp = load_연간목표()
    반_공종_dict = (df_연간_temp[["반", "공종"]].drop_duplicates()
                     .set_index("반")["공종"].to_dict())

    _모든_급여월 = [f"{year}-{m:02d}" for m in range(1, 13)]
    if year > 1900:
        _모든_급여월 = [f"{year-1}-12"] + _모든_급여월
    _반단가_by_월: dict = {}
    for _월키 in set(_모든_급여월):
        try:
            _반단가_by_월[_월키] = load_직종단가(기준월=_월키)
        except Exception:
            pass

    def _get_반단가(반전체명: str, 급여월: str) -> float:
        return float(_반단가_by_월.get(급여월, {}).get(반전체명, 0.0) or 0.0)

    df_목표 = load_목표BEP(year)
    df_효율목 = _calc_반별_목표효율_내부(year)

    급여_dict = df_급여정보.set_index("그룹")[["월급여", "잔업시급", "복리후생비용"]].to_dict("index")

    팀목표_dict = {}
    그룹목표_dict = {}
    if not df_목표.empty:
        for _, r in df_목표[df_목표["구분"]=="TEAM"].iterrows():
            팀목표_dict[(r["그룹코드"], r["월_str"])] = float(r["목표BEP"])
        for _, r in df_목표[df_목표["구분"]=="GROUP"].iterrows():
            그룹목표_dict[(r["그룹코드"], r["월_str"])] = float(r["목표BEP"])

    df_ms_all = pd.DataFrame()
    col_map_ms = {}
    dept_col_ms = None
    try:
        df_ms_all = load_milestone_data()
        if not df_ms_all.empty:
            col_map_ms = get_col_map(df_ms_all.columns.tolist())
            dept_col_ms = col_map_ms.get("dept")
    except Exception:
        pass

    rows = []

    for 반전체명, 반표시 in 반_표시명.items():
        그룹 = 반_그룹매핑.get(반표시, "")

        df_반인원 = df_인원[df_인원["부서"] == 반전체명].copy()

        인원_정보 = []
        for _, p in df_반인원.iterrows():
            g = str(p.get("급여그룹", "") or "").strip()
            if not g or g not in 급여_dict: continue
            월급여 = float(급여_dict[g].get("월급여", 0) or 0)
            잔업시급 = float(급여_dict[g].get("잔업시급", 0) or 0)
            복리후생 = float(급여_dict[g].get("복리후생비용", 0) or 0)
            배치일 = _to_date_safe(p.get("배치일_고정"))
            퇴사일 = p.get("퇴사일")
            급여제외 = p.get("급여제외")
            인원_정보.append({
                "사번": _사번_str(p["사번"]),
                "배치일": 배치일,
                "퇴사일": 퇴사일,
                "일기본급": 월급여 / 30,
                "일복리후생": 복리후생 / 30,
                "잔업시급": 잔업시급,
                "급여제외": 급여제외,
            })

        글로벌_사번 = set(p["사번"] for p in 인원_정보)

        # 급여제외 인원 정보 — 캘린더 일자별 기성 차감용
        # (사번/배치일/퇴사일/급여제외일을 묶어 보관)
        급여제외_정보: list = []
        효율_by_사번_월: dict = {} # (사번, 급여월) → 효율목표
        공종_반 = 반_공종_dict.get(반전체명, "")
        for _, p in df_반인원.iterrows():
            급여제외_v = p.get("급여제외")
            if 급여제외_v is None:
                continue
            사번_p = _사번_str(p["사번"])
            배치일_p = _to_date_safe(p.get("배치일_고정"))
            급여제외_정보.append({
                "사번": 사번_p,
                "배치일": 배치일_p,
                "퇴사일": p.get("퇴사일"),
                "급여제외": 급여제외_v,
            })
            # 월별 효율목표 — 12개월치 미리 캐시
            if 배치일_p is None:
                continue
            보정개월_p = int(p.get("개월수_보정", 0) or 0)
            for _m in range(1, 13):
                _월str = f"{year}-{_m:02d}"
                _기준일 = date(year-1, 12, 1) if _m == 1 else date(year, _m-1, 1)
                _개월차 = _get_개월차(배치일_p, _기준일, 보정개월_p)
                _v = df_효율[(df_효율["공종"] == 공종_반) &
                             (df_효율["개월차"] == _개월차)]["효율목표"]
                if not _v.empty:
                    효율_by_사번_월[(사번_p, _월str)] = float(_v.iloc[0])

        df_반raw = pd.DataFrame()
        if not df_raw.empty:
            df_반raw = df_raw[df_raw["소속부서명"] == 반전체명].copy()
            if not df_반raw.empty:
                df_반raw["_사번"] = df_반raw["사번"].apply(_사번_str)
                df_반raw_일반 = df_반raw[
                    (df_반raw["OP코드"] != "58") &
                    (df_반raw["_사번"].isin(글로벌_사번))
                ]
                df_반raw_58 = df_반raw[df_반raw["OP코드"] == "58"]
                df_반raw = pd.concat([df_반raw_일반, df_반raw_58], ignore_index=True)

        df_반기성 = pd.DataFrame()
        if not df_기성_raw.empty:
            df_반기성 = df_기성_raw[df_기성_raw["반"] == 반전체명].copy()

        전망기성_by_날짜 = {}
        if 오늘.year == year and dept_col_ms and not df_ms_all.empty:
            현재급여월 = _급여월(오늘)
            try:
                yr_c, mo_c = int(현재급여월[:4]), int(현재급여월[5:7])
                for mo in range(mo_c, 13):
                    전월 = mo - 1 if mo > 1 else 12
                    월_시작, 월_종료 = _월범위(f"{year}-{mo:02d}")
                    전망_시작 = max(오늘, 월_시작)
                    if 전망_시작 > 월_종료: continue
                    try:
                        df_ms_f = df_ms_all[df_ms_all[dept_col_ms] == 반전체명].copy()
                        if "월" in df_ms_f.columns:
                            df_ms_f = df_ms_f[df_ms_f["월"].isin([f"{전월}월", f"{mo}월"])].copy()
                        if df_ms_f.empty: continue
                        chart = compute_kiseong(df_ms_f, col_map_ms, 전망_시작, 월_종료)
                        for _, cr in chart.iterrows():
                            g_val = float(cr.get("total", 0) or 0)
                            if 반전체명 == "선실부선실1과설치1직2반":
                                g_val *= (1 - 설치1직2반_내국인비율)
                            전망기성_by_날짜[cr["date"]] = round(g_val, 2)
                    except Exception:
                        pass
            except Exception:
                pass

        d = date(year-1, 12, 11)
        while d <= date(year, 12, 10):
            급여월 = _급여월(d)
            if 급여월 is None:
                d += timedelta(days=1)
                continue

            구분 = "전망" if d >= 오늘 else "실적"
            is_휴일 = (d in 휴일_set) or (d.weekday() >= 5)
            주차 = d.strftime("%Y-W%V")

            단가 = float(_get_반단가(반전체명, 급여월) or 0)

            목표BEP = float(팀목표_dict.get((반표시, 급여월), 1.0) or 1.0)
            그_키 = "1그룹" if 그룹 == "1그룹" else "2그룹"
            그룹목표BEP = float(그룹목표_dict.get((그_키, 급여월), 1.0) or 1.0)

            재직_조건 = [
                p for p in 인원_정보
                if (p["배치일"] is None or d >= p["배치일"])
                and (p["퇴사일"] is None or d < p["퇴사일"])
                and (p["급여제외"] is None or d > p["급여제외"])
            ]
            기본급 = sum(p["일기본급"] for p in 재직_조건)
            복리후생 = sum(p["일복리후생"] for p in 재직_조건)
            인원수 = len(재직_조건)

            특근급 = 0.0
            잔업급 = 0.0
            if 구분 == "실적" and not df_반raw.empty:
                df_날짜 = df_반raw[df_반raw["작업일"] == d]
                if not df_날짜.empty:
                    df_개인 = df_날짜.groupby("_사번", as_index=False)["MH"].sum()
                    for _, pr in df_개인.iterrows():
                        p_info = next(
                            (p for p in 인원_정보
                             if p["사번"] == pr["_사번"]
                             and (p["배치일"] is None or d >= p["배치일"])
                             and (p["퇴사일"] is None or d < p["퇴사일"])
                             and (p["급여제외"] is None or d > p["급여제외"])),
                            None
                        )
                        if p_info is None: continue
                        mh = float(pr["MH"])
                        잔업_시급 = p_info["잔업시급"]
                        if is_휴일:
                            특근급 += mh * 잔업_시급
                        else:
                            잔업급 += max(mh - 정상근무시간, 0) * 잔업_시급

            특잔업비 = 특근급 + 잔업급

            기성 = 0.0
            if 구분 == "실적" and not df_반기성.empty:
                기성 = float(df_반기성[df_반기성["날짜"] == d]["기성"].sum())
                if 반전체명 == "선실부선실1과설치1직2반":
                    기성 *= (1 - 설치1직2반_내국인비율)
            elif 구분 == "전망":
                기성 = 전망기성_by_날짜.get(d, 0.0)

            # 급여제외 인원의 기성 차감 — 캘린더 일자별 일괄 차감
            # 실적/전망 구분 무관, 실제 출근/MH 무관, 그 인원이 해당 캘린더 날짜에
            # "급여제외 기간 내(배치일 ≤ d ≤ 급여제외일, d < 퇴사일)" 이면
            # 정상근무시간(8h) × 본인 직종 효율목표 만큼 일괄 차감
            기성_제외_급여 = 0.0
            if 급여제외_정보:
                for _ex in 급여제외_정보:
                    if _ex["배치일"] is not None and d < _ex["배치일"]:
                        continue
                    if _ex["퇴사일"] is not None and d >= _ex["퇴사일"]:
                        continue
                    if d > _ex["급여제외"]:
                        continue
                    _효율 = float(효율_by_사번_월.get((_ex["사번"], 급여월), 0.0) or 0.0)
                    기성_제외_급여 += 정상근무시간 * _효율
            기성 -= 기성_제외_급여

            기성_58 = 0.0
            if 구분 == "실적" and not df_반raw.empty:
                df_58날 = df_반raw[
                    (df_반raw["작업일"] == d) & (df_반raw["OP코드"] == "58")
                ]
                if not df_58날.empty:
                    목표효율 = 0.0
                    if not df_효율목.empty and "반" in df_효율목.columns and "월" in df_효율목.columns:
                        효율행 = df_효율목[
                            (df_효율목["반"] == 반전체명) & (df_효율목["월"] == 급여월)
                        ]
                        if not 효율행.empty:
                            목표효율 = float(효율행["목표효율"].iloc[0])
                    기성_58 = float(df_58날["MH"].sum()) * 목표효율

            실투 = 0.0
            제외실투 = 0.0
            if 구분 == "실적" and not df_raw.empty:
                df_반전체날 = df_raw[
                    (df_raw["소속부서명"] == 반전체명) &
                    (df_raw["작업일"] == d)
                ]
                if not df_반전체날.empty:
                    직접_코드 = {"11","12","13"}
                    제외_코드 = {
                        "12","47","55","58","59",
                        "61","62","63","66","67","68","78",
                        "70","71","72","73","74","75","76","77","79","7A","7B",
                        "81","82","83","84","88","89","90","91","92","93","94",
                        "95","96","97","98","99","9F"
                    }
                    실투 = float(df_반전체날[df_반전체날["OP코드"].isin(직접_코드)]["MH"].sum())
                    제외실투 = float(df_반전체날[~df_반전체날["OP코드"].isin(제외_코드)]["MH"].sum())

            rows.append({
                "날짜": d,
                "급여월": 급여월,
                "주차": 주차,
                "반": 반전체명,
                "반_표시": 반표시,
                "그룹": 그룹,
                "기성": round(기성, 2),
                "기성_58": round(기성_58, 2),
                "기성_제외_급여": round(기성_제외_급여, 2),
                "기성합계": round(기성 + 기성_58, 2),
                "기본급": round(기본급, 0),
                "특잔업비": round(특잔업비, 0),
                "복리후생": round(복리후생, 0),
                "급여합계": round(기본급 + 특잔업비 + 복리후생, 0),
                "실투": round(실투, 2),
                "제외실투": round(제외실투, 2),
                "단가": 단가,
                "목표BEP": 목표BEP,
                "그룹목표BEP": 그룹목표BEP,
                "인원수": 인원수,
                "구분": 구분,
                "휴일": is_휴일,
            })
            d += timedelta(days=1)

    return pd.DataFrame(rows)

# ══════════════════════════════════════════════════════════
# 집계 함수들
# ══════════════════════════════════════════════════════════

def agg_월간(df_기초: pd.DataFrame, year: int = None) -> pd.DataFrame:
    if year is None: year = date.today().year
    if df_기초 is None or df_기초.empty: return pd.DataFrame()

    df_실적 = df_기초[df_기초["구분"] == "실적"]
    _복리컬럼 = "복리후생" if "복리후생" in df_기초.columns else "기본급"
    g_실적 = df_실적.groupby(["반","반_표시","그룹","급여월"], as_index=False).agg(
        실적기성합계=("기성합계", "sum"),
        실적기본급합=("기본급", "sum"),
        실적특잔업합=("특잔업비", "sum"),
        실적복리후생합=(_복리컬럼, "sum"),
    ).rename(columns={"급여월":"월"})
    if _복리컬럼 == "기본급":
        g_실적["실적복리후생합"] = 0.0

    g = df_기초.groupby(["반","반_표시","그룹","급여월"], as_index=False).agg(
        기성 =("기성", "sum"),
        기성_58 =("기성_58", "sum"),
        기성합계 =("기성합계", "sum"),
        기본급합 =("기본급", "sum"),
        특잔업합 =("특잔업비", "sum"),
        복리후생합=(_복리컬럼, "sum"),
        단가 =("단가", "first"),
        목표BEP =("목표BEP", "first"),
        그룹목표BEP=("그룹목표BEP","first"),
        인원수 =("인원수", "max"),
        마지막날짜=("날짜", "max"),
    ).rename(columns={"급여월":"월"})
    if _복리컬럼 == "기본급":
        g["복리후생합"] = 0.0

    rows = []
    for _, r in g.iterrows():
        반전체명 = r["반"]
        월 = r["월"]
        기준일 = r["마지막날짜"]
        if not isinstance(기준일, date):
            기준일 = _to_date_safe(기준일)
        if 기준일 is None:
            기준일 = date.today()

        보정 = _급여보정(
            df_기초[(df_기초["반"]==반전체명)&(df_기초["급여월"]==월)],
            반전체명, 기준일
        )
        기본급합 = float(r["기본급합"])
        특잔업합 = float(r["특잔업합"])
        복리후생합 = float(r.get("복리후생합", 0) or 0)
        월간급여 = 기본급합 + 특잔업합 + 복리후생합 + 보정
        기성합계 = float(r["기성합계"])
        단가 = float(r["단가"])
        목표BEP = float(r["목표BEP"])

        BEP = (기성합계 * 단가) / 월간급여 if 월간급여 > 0 and 단가 > 0 else 0.0

        실적행 = g_실적[(g_실적["반"]==반전체명) & (g_실적["월"]==월)]
        if not 실적행.empty:
            실적기성합계 = float(실적행["실적기성합계"].iloc[0])
            실적기본급합 = float(실적행["실적기본급합"].iloc[0])
            실적특잔업합 = float(실적행["실적특잔업합"].iloc[0])
            실적복리후생합 = float(실적행["실적복리후생합"].iloc[0]) if "실적복리후생합" in 실적행.columns else 0.0
            실적월간급여 = 실적기본급합 + 실적특잔업합 + 실적복리후생합 + 보정
            실적BEP = (실적기성합계 * 단가) / 실적월간급여 if 실적월간급여 > 0 and 단가 > 0 else 0.0
        else:
            실적기성합계 = 0.0
            실적월간급여 = 0.0
            실적BEP = 0.0

        rows.append({
            "반": 반전체명,
            "반_표시": r["반_표시"],
            "그룹": r["그룹"],
            "월": 월,
            "최종기성": round(기성합계, 2),
            "실적기성": round(실적기성합계, 2),
            "58가상기성": round(float(r["기성_58"]), 2),
            "58MH": 0,
            "월급여": round(기본급합, 0),
            "특잔업비": round(특잔업합, 0),
            "복리후생비": round(복리후생합, 0),
            "월간급여": round(월간급여, 0),
            "실적급여": round(실적월간급여, 0),
            "단가": 단가,
            "BEP": round(실적BEP, 3),
            "전망BEP": round(BEP, 3),
            "목표BEP": round(목표BEP, 3),
            "그룹목표BEP": round(float(r["그룹목표BEP"]), 3),
            "인원수": r["인원수"],
        })

    df = pd.DataFrame(rows)
    순서_map = {반: i for i, 반 in enumerate(반_표시순서)}
    df["_순서"] = df["반_표시"].map(순서_map).fillna(99)
    return df.sort_values(["_순서","월"]).drop(columns="_순서").reset_index(drop=True)


def agg_주간(df_기초: pd.DataFrame, year: int = None) -> pd.DataFrame:
    if year is None: year = date.today().year
    if df_기초 is None or df_기초.empty: return pd.DataFrame()

    df_목표 = load_목표BEP(year)
    팀목표_dict = {}
    if not df_목표.empty:
        for _, r in df_목표[df_목표["구분"]=="TEAM"].iterrows():
            팀목표_dict[(r["그룹코드"], r["월_str"])] = float(r["목표BEP"])

    g = df_기초.groupby(["반","반_표시","그룹","주차","급여월"], as_index=False).agg(
        기성합계=("기성합계", "sum"),
        기성_58 =("기성_58", "sum"),
        기본급합=("기본급", "sum"),
        특잔업합=("특잔업비", "sum"),
        단가 =("단가", "first"),
    ).rename(columns={"급여월":"월"})

    rows = []
    for _, r in g.iterrows():
        기성합계 = float(r["기성합계"])
        주간급여 = float(r["기본급합"]) + float(r["특잔업합"])
        단가 = float(r["단가"])
        반표시 = r["반_표시"]
        월 = r["월"]
        목표BEP = float(팀목표_dict.get((반표시, 월), np.nan) or np.nan)
        BEP = (기성합계 * 단가) / 주간급여 if 주간급여 > 0 and 단가 > 0 else np.nan
        rows.append({
            "반": r["반"],
            "반_표시": 반표시,
            "그룹": r["그룹"],
            "주차": r["주차"],
            "월": 월,
            "최종기성": round(기성합계, 2),
            "58가상기성": round(float(r["기성_58"]), 2),
            "주간급여": round(주간급여, 0),
            "단가": 단가,
            "BEP": round(BEP, 3) if pd.notna(BEP) else np.nan,
            "목표BEP": 목표BEP,
        })

    df = pd.DataFrame(rows)
    순서_map = {반: i for i, 반 in enumerate(반_표시순서)}
    df["_순서"] = df["반_표시"].map(순서_map).fillna(99)
    return df.sort_values(["_순서","주차"]).drop(columns="_순서").reset_index(drop=True)


def agg_주간누적(df_주간: pd.DataFrame) -> pd.DataFrame:
    if df_주간 is None or df_주간.empty: return pd.DataFrame()
    rows = []
    for (반명, 월), 그룹 in df_주간.groupby(["반","월"]):
        그룹 = 그룹.sort_values("주차").reset_index(drop=True)
        단가 = float(그룹["단가"].iloc[0]) if "단가" in 그룹.columns else 0.0
        누적기성 = 0.0; 누적급여 = 0.0; 누적58 = 0.0
        for _, row in 그룹.iterrows():
            누적기성 += float(row.get("최종기성", 0) or 0)
            누적급여 += float(row.get("주간급여", 0) or 0)
            누적58 += float(row.get("58가상기성", 0) or 0)
            누적BEP = (누적기성 * 단가) / 누적급여 if 누적급여 > 0 and 단가 > 0 else np.nan
            rows.append({
                "반": 반명,
                "반_표시": row.get("반_표시", 반명),
                "월": 월,
                "주차": row["주차"],
                "주차라벨": _주차_라벨(row["주차"]),
                "월내주차": _월내_주차_라벨(row["주차"], 월),
                "단가": 단가,
                "누적기성": round(누적기성, 2),
                "누적급여": round(누적급여, 0),
                "누적BEP": round(누적BEP, 3) if pd.notna(누적BEP) else np.nan,
                "목표BEP": row.get("목표BEP"),
                "주간BEP": row.get("BEP"),
                "주간기성": row.get("최종기성", 0),
                "주간급여": row.get("주간급여", 0),
                "누적58가상기성": round(누적58, 2),
            })
    return pd.DataFrame(rows)


def agg_연간누적(df_월간: pd.DataFrame, year: int = None) -> pd.DataFrame:
    if year is None: year = date.today().year
    if df_월간 is None or df_월간.empty: return pd.DataFrame()

    그룹_단가 = load_그룹단가()
    df_목표 = load_목표BEP(year)

    월별목표_dict = {}
    if not df_목표.empty:
        for _, r in df_목표[df_목표["구분"]=="GROUP"].iterrows():
            월별목표_dict[(r["그룹코드"], r["월_str"])] = float(r["목표BEP"])

    rows = []
    for 그룹명 in ["1그룹","2그룹"]:
        df_그룹 = df_월간[df_월간["그룹"]==그룹명].copy()
        if df_그룹.empty: continue
        df_그룹월 = (df_그룹.groupby("월", as_index=False)
                     .agg(월기성=("최종기성","sum"), 월급여=("월간급여","sum"))
                     .sort_values("월").reset_index(drop=True))
        단가 = 그룹_단가.get(그룹명, 0.0)
        누적기성 = 0.0; 누적급여 = 0.0
        누적목표합 = 0.0; 목표월수 = 0

        for _, row in df_그룹월.iterrows():
            m_str = row["월"]
            누적기성 += float(row.get("월기성", 0) or 0)
            누적급여 += float(row.get("월급여", 0) or 0)
            누적BEP = (누적기성 * 단가) / 누적급여 if 누적급여 > 0 and 단가 > 0 else np.nan

            월목표 = 월별목표_dict.get((그룹명, m_str), np.nan)
            if pd.notna(월목표):
                누적목표합 += 월목표
                목표월수 += 1
            누적목표평균 = 누적목표합 / 목표월수 if 목표월수 > 0 else np.nan

            부족초과 = (누적기성 - (누적급여 * 누적목표평균) / 단가) if (
                pd.notna(누적목표평균) and 누적급여 > 0 and 단가 > 0) else np.nan
            달성률 = (누적BEP / 누적목표평균 * 100) if (
                pd.notna(누적BEP) and pd.notna(누적목표평균) and 누적목표평균 > 0) else np.nan

            rows.append({
                "그룹": 그룹명,
                "월": m_str,
                "월라벨": f"{int(m_str[5:7])}월",
                "월기성": round(float(row.get("월기성",0)), 2),
                "누적기성": round(누적기성, 2),
                "누적급여": round(누적급여, 0),
                "단가": round(단가, 0),
                "누적BEP": round(누적BEP, 3) if pd.notna(누적BEP) else np.nan,
                "그룹목표BEP": round(누적목표평균, 3) if pd.notna(누적목표평균) else np.nan,
                "부족초과MH": round(부족초과, 1) if pd.notna(부족초과) else np.nan,
                "달성률": round(달성률, 1) if pd.notna(달성률) else np.nan,
            })
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def agg_월말전망(df_기초: pd.DataFrame, 월: str, year: int = None) -> pd.DataFrame:
    if year is None: year = date.today().year
    if df_기초 is None or df_기초.empty: return pd.DataFrame()

    오늘 = date.today()
    월_시작, 월_종료 = _월범위(월)
    반_단가 = load_직종단가()
    df_목표 = load_목표BEP(year)
    팀목표_dict = {}
    if not df_목표.empty:
        for _, r in df_목표[df_목표["구분"]=="TEAM"].iterrows():
            팀목표_dict[(r["그룹코드"], r["월_str"])] = float(r["목표BEP"])

    총일수 = max((월_종료 - 월_시작).days, 1)
    경과일 = max((오늘 - 월_시작).days, 1)
    진행률 = min(경과일 / 총일수, 1.0)

    rows = []
    for 반전체명, 반표시 in 반_표시명.items():
        df_반 = df_기초[(df_기초["반"]==반전체명) & (df_기초["급여월"]==월)]
        if df_반.empty: continue

        df_실적 = df_반[df_반["구분"]=="실적"]
        현재기성 = float(df_실적["기성합계"].sum())
        df_전망 = df_반[df_반["구분"]=="전망"]
        전망잔여 = float(df_전망["기성합계"].sum())
        월말전망기성 = 현재기성 + 전망잔여

        현재급여 = float(df_실적["급여합계"].sum())
        월말예상급여 = (현재급여 / 진행률) if 진행률 > 0 else 현재급여

        단가 = float(반_단가.get(반전체명, 0) or 0)
        목표BEP = float(팀목표_dict.get((반표시, 월), 1.0) or 1.0)

        현재BEP = (현재기성 * 단가) / 현재급여 if 현재급여 > 0 and 단가 > 0 else 0.0
        월말전망BEP = (월말전망기성 * 단가) / 월말예상급여 if 월말예상급여 > 0 and 단가 > 0 else 0.0
        목표기성 = (월말예상급여 * 목표BEP) / 단가 if 단가 > 0 else 0.0
        전망부족MH = 월말전망기성 - 목표기성

        rows.append({
            "반_표시": 반표시,
            "전망기성": round(월말전망기성, 1),
            "현재기성": round(현재기성, 1),
            "전망잔여기성": round(전망잔여, 1),
            "월말전망기성": round(월말전망기성, 1),
            "현재급여": round(현재급여, 0),
            "월말예상급여": round(월말예상급여, 0),
            "현재BEP": round(현재BEP, 3),
            "월말전망BEP": round(월말전망BEP, 3),
            "목표BEP": round(목표BEP, 3),
            "전망부족MH": round(전망부족MH, 1),
        })
    return pd.DataFrame(rows)

# ══════════════════════════════════════════════════════════
# 상세 페이지용
# ══════════════════════════════════════════════════════════

def load_상세_일별(월: str = None, year: int = None):
    if year is None: year = date.today().year
    전체_모드 = (월 is None)
    if 월 is None: 월 = _급여월(date.today())

    df_기초 = build_일별_기초(year)
    if df_기초 is None or df_기초.empty:
        return pd.DataFrame(), pd.DataFrame()

    if 전체_모드:
        df_월 = df_기초.copy()
    else:
        df_월 = df_기초[df_기초["급여월"] == 월].copy()
    if df_월.empty:
        return pd.DataFrame(), pd.DataFrame()

    df_일별 = df_월.copy()

    월_시작, 월_종료 = _월범위(월)
    합계_rows = []
    반_단가 = load_직종단가()
    df_목표 = load_목표BEP(year)
    팀목표_dict = {}
    if not df_목표.empty:
        for _, r in df_목표[df_목표["구분"]=="TEAM"].iterrows():
            팀목표_dict[(r["그룹코드"], r["월_str"])] = float(r["목표BEP"])

    for 반전체명, 반표시 in 반_표시명.items():
        df_반 = df_월[df_월["반"] == 반전체명]
        if df_반.empty: continue

        기성합계 = float(df_반["기성합계"].sum())
        기성_58합 = float(df_반["기성_58"].sum())
        기성_실적 = float(df_반["기성"].sum())
        기본급합 = float(df_반["기본급"].sum())
        특잔업합 = float(df_반["특잔업비"].sum())
        복리후생합 = float(df_반["복리후생"].sum()) if "복리후생" in df_반.columns else 0.0

        # 보정 분리: 기본급보정 / 복리후생보정
        보정_전체 = _급여보정(df_반, 반전체명, 월_종료)
        # 기본급:복리후생 비율로 보정 분배
        기본복리합 = 기본급합 + 복리후생합
        if 기본복리합 > 0:
            기본급보정 = 보정_전체 * (기본급합 / 기본복리합)
            복리후생보정 = 보정_전체 * (복리후생합 / 기본복리합)
        else:
            기본급보정 = 보정_전체
            복리후생보정 = 0.0

        급여합계_보정 = 기본급합 + 특잔업합 + 복리후생합 + 보정_전체

        단가 = float(반_단가.get(반전체명, 0) or 0)
        목표BEP = float(팀목표_dict.get((반표시, 월), 1.0) or 1.0)
        BEP = (기성합계 * 단가) / 급여합계_보정 if 급여합계_보정 > 0 and 단가 > 0 else 0.0
        목표기성 = (급여합계_보정 * 목표BEP) / 단가 if 단가 > 0 else 0.0
        부족초과MH = 기성합계 - 목표기성

        합계_rows.append({
            "반_표시": 반표시,
            "기성합계": round(기성합계, 1),
            "기성_58합": round(기성_58합, 1),
            "기성_실적": round(기성_실적, 1),
            "기본급합계": round(기본급합, 0),
            "특잔업합계": round(특잔업합, 0),
            "복리후생합계": round(복리후생합, 0),
            "기본급보정": round(기본급보정, 0),
            "복리후생보정": round(복리후생보정, 0),
            "보정급여": round(보정_전체, 0),
            "급여합계_보정": round(급여합계_보정, 0),
            "BEP": round(BEP, 3),
            "목표BEP": round(목표BEP, 3),
            "부족초과MH": round(부족초과MH, 1),
        })

    df_합계 = pd.DataFrame(합계_rows)
    순서_map = {반: i for i, 반 in enumerate(반_표시순서)}
    for df in [df_일별, df_합계]:
        if not df.empty and "반_표시" in df.columns:
            df["_순서"] = df["반_표시"].map(순서_map).fillna(99)
            df.sort_values(["_순서","날짜"] if "날짜" in df.columns else ["_순서"],
                           inplace=True)
            df.drop(columns="_순서", inplace=True)
            df.reset_index(drop=True, inplace=True)

    return df_일별, df_합계

# ══════════════════════════════════════════════════════════
# KPI 요약 / 필터 옵션
# ══════════════════════════════════════════════════════════

def _주차_날짜범위(iso_str: str, 급여월: str):
    try:
        yr, w = int(iso_str.split("-W")[0]), int(iso_str.split("-W")[1])
        mon = pd.Timestamp.fromisocalendar(yr, w, 1).date()
        sun = pd.Timestamp.fromisocalendar(yr, w, 7).date()
        월_시작, 월_종료 = _월범위(급여월)
        return max(mon, 월_시작), min(sun, 월_종료)
    except:
        return _월범위(급여월)

def _주차_라벨(iso_str: str) -> str:
    try: return f"{int(iso_str.split('-W')[1])}주"
    except: return iso_str

def _월내_주차_라벨(iso_str: str, 급여월: str) -> str:
    try:
        yr, w = int(iso_str.split("-W")[0]), int(iso_str.split("-W")[1])
        ym = int(급여월[:4]), int(급여월[5:7])
        start = date(ym[0]-1, 12, 11) if ym[1]==1 else date(ym[0], ym[1]-1, 11)
        mon = pd.Timestamp.fromisocalendar(yr, w, 1).date()
        week_num = max((mon - start).days // 7 + 1, 1)
        return f"{ym[1]}월{week_num}주({w}주)"
    except: return iso_str

@st.cache_data(ttl=300)
def get_group_kpi_summary(year: int = None) -> dict:
    """홈 대시보드 카드용 — 그룹별 달성률(%)
    KPI_2 화면의 'YYYY-MM BEP 현황' 테이블(_calc_그룹데이터 ①path)과 동일한 계산.
    실적+전망 기준의 그룹BEP / 그룹 목표BEP × 100
    반환: {"월": "2026-04", "1그룹": 89.3, "2그룹": 95.2}
    """
    if year is None:
        year = date.today().year
    이달월 = _급여월(date.today())

    결과 = {"월": 이달월, "1그룹": None, "2그룹": None}

    df_기초 = build_일별_기초(year)
    if df_기초 is None or df_기초.empty:
        return 결과

    df_목표 = load_목표BEP(year)
    그룹_단가_default = load_그룹단가()

    for 그룹명, 반표시목록 in 그룹_반목록.items():
        반전체명목록 = [k for k, v in 반_표시명.items() if v in 반표시목록]
        df_월 = df_기초[
            (df_기초["반"].isin(반전체명목록)) &
            (df_기초["급여월"] == 이달월)
        ]
        if df_월.empty:
            continue

        # 실적+전망 합산
        기성합계 = float(df_월["기성합계"].sum())
        급여합계 = float(df_월["기본급"].sum() + df_월["특잔업비"].sum())

        # 그룹단가: 반별 기성 가중평균
        단가_df = df_월.groupby("반", as_index=False).agg(
            기성합계=("기성합계", "sum"), 단가=("단가", "first"))
        총기성 = float(단가_df["기성합계"].sum())
        if 총기성 > 0:
            그룹단가 = float((단가_df["기성합계"] * 단가_df["단가"]).sum() / 총기성)
        else:
            그룹단가 = float(그룹_단가_default.get(그룹명, 0.0) or 0.0)

        # 그룹 목표 BEP
        그룹목표 = 1.0
        if not df_목표.empty:
            행 = df_목표[
                (df_목표["구분"] == "GROUP") &
                (df_목표["그룹코드"] == 그룹명) &
                (df_목표["월_str"] == 이달월)
            ]
            if not 행.empty:
                그룹목표 = float(행["목표BEP"].iloc[0])

        그룹BEP = (기성합계 * 그룹단가) / 급여합계 if (급여합계 > 0 and 그룹단가 > 0) else 0.0
        결과[그룹명] = round(그룹BEP / 그룹목표 * 100, 1) if 그룹목표 > 0 else None

    return 결과


@st.cache_data(ttl=3600)
def get_filter_options(year: int = None) -> dict:
    if year is None: year = date.today().year
    반_list = ["전체"] + list(반_표시명.values())
    월_list = [f"{year}-{m:02d}" for m in range(1, 13)]
    현재월 = _급여월(date.today())
    df_기초 = build_일별_기초(year)
    주차_list = []
    if df_기초 is not None and not df_기초.empty and "주차" in df_기초.columns:
        주차_list = sorted(df_기초["주차"].dropna().unique().tolist())
    return {"반_list": 반_list, "월_list": 월_list, "현재월": 현재월, "주차_list": 주차_list}