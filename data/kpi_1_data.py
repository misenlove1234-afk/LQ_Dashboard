"""
[ 🤖 AI 바이브 코딩을 위한 프롬프트 가이드 ]
"이 파일은 Streamlit 앱의 '데이터 처리 전용' 모듈이야.
1. 절대 st.write, st.dataframe 같은 화면 UI 코드를 넣지 마.
2. DB는 이 파일 내 _run_query 함수로 읽어.
3. 무거운 연산을 하는 함수 위에는 반드시 @st.cache_data(ttl=600, max_entries=50) 를 달어.
4. 최종 결과물은 Pandas DataFrame 으로 return 해줘."
"""

import streamlit as st
import pandas as pd
import numpy as np
from sqlalchemy import text
from dotenv import load_dotenv
from utils.db import get_engine

load_dotenv("/etc/lq/.env.dev")

_TABLE = {
    "기성":   "lq_kpi1_1",
    "직접":   "lq_kpi1_2",
    "총발생": "lq_kpi1_3",
}

GLOBAL_작업장 = {
    "선실부선실1과설치1직2반",
    "선실부선실2과취부반",
    "선실부선실2과곡직반",
    "선실부선실전장과전장1직3반",
}


# ══════════════════════════════════════════════════════
# 내부 유틸
# ══════════════════════════════════════════════════════

def _run_query(sql: str) -> pd.DataFrame:
    """utils/db.py의 get_engine()을 통해 쿼리 실행"""
    engine = get_engine()
    with engine.connect() as conn:
        df = pd.read_sql(text(sql), conn)
    return df


def _add_period(df: pd.DataFrame, col: str = "날짜") -> pd.DataFrame:
    """
    날짜 컬럼으로 '월'·'주차' 컬럼을 추가한다.
    - 컬럼이 없으면 빈 컬럼을 만들고 반환 (KeyError 방지)
    - 숫자형(Excel 시리얼 날짜)이면 올바른 단위로 변환
      · 값이 100,000 미만 → Excel 시리얼 (일수, origin='1899-12-30')
      · 값이 100,000 이상 · 10억 미만 → Unix 초
      · 10억 이상 → Unix 밀리초
    - 문자열·datetime형은 pd.to_datetime 기본 변환 사용
    """
    df = df.copy()

    if col not in df.columns:
        df["월"]  = pd.NA
        df["주차"] = pd.NA
        return df

    raw = df[col]

    if pd.api.types.is_numeric_dtype(raw):
        sample = raw.dropna()
        if sample.empty:
            df[col] = pd.NaT
        else:
            med = float(sample.median())
            if med < 100_000:
                # Excel 시리얼 날짜 (단위: 일)
                df[col] = pd.to_datetime(raw, unit="D", origin="1899-12-30", errors="coerce")
            elif med < 1_000_000_000:
                # Unix 타임스탬프 (단위: 초)
                df[col] = pd.to_datetime(raw, unit="s", errors="coerce")
            else:
                # Unix 타임스탬프 (단위: 밀리초)
                df[col] = pd.to_datetime(raw, unit="ms", errors="coerce")
    else:
        df[col] = pd.to_datetime(raw, errors="coerce")

    df = df.dropna(subset=[col])
    df["월"]  = df[col].dt.to_period("M").astype(str)
    df["주차"] = df[col].dt.strftime("%Y-W%V")
    return df


def week_label(iso_str: str) -> str:
    try:
        year, w = iso_str.split("-W")
        mon = pd.Timestamp.fromisocalendar(int(year), int(w), 1)
        return f"{mon.month}월 {(mon.day-1)//7+1}주"
    except Exception:
        return iso_str


def get_current_week() -> str:
    """오늘 날짜의 주차 반환 (YYYY-Www 형식)"""
    return pd.Timestamp.now().strftime("%Y-W%V")


def get_current_month() -> str:
    """오늘 날짜의 월 반환 (YYYY-MM 형식)"""
    return pd.Timestamp.now().strftime("%Y-%m")


def _strip(v):
    return str(v).strip() if v is not None else ""


# ══════════════════════════════════════════════════════
# 데이터 로드
# ══════════════════════════════════════════════════════

@st.cache_data(ttl=600, max_entries=50)
def load_data() -> pd.DataFrame:
    df = _run_query("SELECT * FROM dbo.[" + _TABLE['기성'] + "]")
    rename = {
        "날짜":           "날짜",
        "프로젝트":       "프로젝트",
        "시공 W/C 내역":  "과",
        "A3 작업장 내역": "작업장",
        "기성":           "기성",
        "투입":           "투입",
    }
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
    df = _add_period(df)
    for c in ["기성", "투입"]:
        df[c] = pd.to_numeric(df.get(c, 0), errors="coerce").fillna(0)
    if "작업장" in df.columns:
        df["구분"] = df["작업장"].apply(
            lambda x: "글로벌" if _strip(x) in GLOBAL_작업장 else "내국인"
        )
    return df


@st.cache_data(ttl=600, max_entries=50)
def load_시수_data() -> tuple:
    def _read(table, val_col):
        df = _run_query("SELECT * FROM dbo.[" + table + "]")
        rename = {
            "날짜":    "날짜",
            "W/C명":   "W/C명",
            "Value":   val_col,
            "FORE_YN": "FORE_YN",
        }
        df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
        df = _add_period(df)
        df[val_col] = pd.to_numeric(df.get(val_col, 0), errors="coerce").fillna(0)
        if "W/C명" in df.columns:
            df["작업장_글로벌"] = df["W/C명"].apply(lambda x: _strip(x) in GLOBAL_작업장)
            fore = df["FORE_YN"].astype(str).str.strip().str.upper()
            df["구분"]     = np.where(df["작업장_글로벌"] & (fore == "Y"), "글로벌", "내국인")
            df["직반포함"] = ~(df["작업장_글로벌"] & (fore == "N"))
        return df
    return _read(_TABLE["직접"], "직접공수"), _read(_TABLE["총발생"], "총발생")


@st.cache_data(ttl=600, max_entries=50)
def load_글로벌_월별목표(year: int = None) -> pd.DataFrame:
    """
    kpi_2 방식으로 글로벌 직반별 월별 능률/실동률 목표 계산.
    - 기준일: 당월 1일 (kpi_1 기준 — 당월 1일~말일)
    - 재직자 필터: 배치일 <= 당월 말일, 퇴사일 없거나 당월 1일 이후
    """
    import calendar as _cal
    from datetime import date as _date
    from data.kpi_2_data import (
        load_인원정보, load_능률목표 as _load_능률목표,
        load_실동률목표 as _load_실동률목표,
        load_연간목표, _get_개월차, _to_date_safe, 반_표시명,
    )

    if year is None:
        year = pd.Timestamp.now().year

    df_인원  = load_인원정보()
    df_능률  = _load_능률목표()
    df_실동  = _load_실동률목표()
    df_연간  = load_연간목표()
    반_공종  = (df_연간[["반", "공종"]].drop_duplicates()
                .set_index("반")["공종"].to_dict())

    직반_rows = []
    for 반명 in 반_표시명.keys():
        공종 = 반_공종.get(반명)
        if not 공종:
            continue
        그룹df = df_인원[df_인원["부서"] == 반명]

        for m in range(1, 13):
            월str   = f"{year}-{m:02d}"
            기준일  = _date(year, m, 1)           # 당월 1일
            말일    = _cal.monthrange(year, m)[1]
            월_시작 = _date(year, m, 1)
            월_종료 = _date(year, m, 말일)

            재직_df = 그룹df[그룹df.apply(
                lambda row: (
                    (_to_date_safe(row.get("배치일_고정")) is None or
                     _to_date_safe(row.get("배치일_고정")) <= 월_종료)
                    and
                    (row.get("퇴사일") is None or
                     (isinstance(row.get("퇴사일"), _date) and
                      row.get("퇴사일") > 월_시작))
                ), axis=1
            )]

            능률_v, 실동_v = [], []
            for _, row in 재직_df.iterrows():
                보정 = int(row.get("개월수_보정", 0) or 0)
                개월차 = _get_개월차(row["배치일_고정"], 기준일, 보정)
                v = df_능률[
                    (df_능률["공종"] == 공종) & (df_능률["개월차"] == 개월차)
                ]["능률목표"]
                if not v.empty:
                    능률_v.append(float(v.iloc[0]))
                v = df_실동[
                    (df_실동["공종"] == 공종) & (df_실동["개월차"] == 개월차)
                ]["실동률목표"]
                if not v.empty:
                    실동_v.append(float(v.iloc[0]))

            직반_rows.append({
                "레벨":    "직반",
                "구분":    "글로벌",
                "과":      None,
                "작업장":  반명,
                "월":      월str,
                "능률목표":   np.mean(능률_v) if 능률_v else np.nan,
                "실동률목표": np.mean(실동_v) if 실동_v else np.nan,
            })

    df_직반 = pd.DataFrame(직반_rows)

    # 선실부 전체 레벨: 해당 월 직반들의 평균
    부_rows = []
    for m in range(1, 13):
        월str  = f"{year}-{m:02d}"
        월_df  = df_직반[df_직반["월"] == 월str]
        부_rows.append({
            "레벨":    "선실부",
            "구분":    "글로벌",
            "과":      None,
            "작업장":  None,
            "월":      월str,
            "능률목표":   월_df["능률목표"].mean(),
            "실동률목표": 월_df["실동률목표"].mean(),
        })

    return pd.concat([pd.DataFrame(부_rows), df_직반], ignore_index=True)


@st.cache_data(ttl=600, max_entries=50)
def load_targets(year: int = None) -> pd.DataFrame:
    """DB에서 lq_kpi1_4 로드 (내국인) + 글로벌 목표는 kpi_2 방식으로 계산 대체"""
    df = _run_query("SELECT * FROM dbo.[lq_kpi1_4]")
    rename = {
        "월":            "월",
        "레벨":          "레벨",
        "시공 W/C 내역": "과",
        "A3 작업장 내역":"작업장",
        "구분":          "구분",
        "능률목표":      "능률목표",
        "실동률목표":    "실동률목표",
    }
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
    for col in ["레벨", "구분", "과", "작업장"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()
    df["월"] = df["월"].astype(str).str[:7]
    for c in ["능률목표", "실동률목표"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    # 글로벌 행은 kpi_2 계산 방식으로 대체
    if year is None:
        year = pd.Timestamp.now().year
    df_내국인 = df[df["구분"] != "글로벌"].copy()
    df_글로벌 = load_글로벌_월별목표(year)

    return pd.concat([df_내국인, df_글로벌], ignore_index=True)


# ══════════════════════════════════════════════════════
# 필터 옵션
# ══════════════════════════════════════════════════════

def get_filter_options(df: pd.DataFrame,
                       df_직접: pd.DataFrame = None,
                       df_총발생: pd.DataFrame = None) -> dict:
    """
    기성·직접공수·총발생 세 테이블의 날짜 합집합으로 필터 옵션 생성.
    어느 한 테이블에만 있는 월/주차도 선택 가능하게 함.
    """
    def _extract(src, col):
        if src is None or col not in src.columns:
            return set()
        return {v for v in src[col].dropna().unique() if str(v) != "NaT"}

    all_월  = _extract(df, "월")  | _extract(df_직접, "월")  | _extract(df_총발생, "월")
    all_주차 = _extract(df, "주차") | _extract(df_직접, "주차") | _extract(df_총발생, "주차")

    months = sorted(all_월)
    weeks  = sorted(all_주차)
    과_list = (["전체"] + sorted(df["과"].dropna().unique().tolist())) \
              if df is not None and "과" in df.columns else ["전체"]
    return {"months": months, "weeks": weeks, "과_list": 과_list}


# ══════════════════════════════════════════════════════
# 목표값 조회
# ══════════════════════════════════════════════════════

def _get_target(df_tgt, 레벨, 구분, 월_list, 과=None, 작업장=None):
    d = df_tgt[df_tgt["레벨"] == 레벨.strip()].copy()
    d = d[d["구분"] == 구분.strip()]
    if 월_list: d = d[d["월"].isin(월_list)]
    if 과      and "과"    in d.columns: d = d[d["과"]    == _strip(과)]
    if 작업장  and "작업장" in d.columns: d = d[d["작업장"] == _strip(작업장)]
    능률  = d["능률목표"].mean()  if "능률목표"  in d.columns and not d.empty else np.nan
    실동률 = d["실동률목표"].mean() if "실동률목표" in d.columns and not d.empty else np.nan
    return {"능률목표": 능률, "실동률목표": 실동률}


def _목표_wc목록(df_tgt, 구분, 월_list):
    d = df_tgt[df_tgt["레벨"] == "직반"].copy()
    d = d[d["구분"] == 구분.strip()]
    if 월_list: d = d[d["월"].isin(월_list)]
    return set(d["작업장"].dropna().astype(str).str.strip().unique()) \
           if "작업장" in d.columns else set()


# ══════════════════════════════════════════════════════
# 능률 집계
# ══════════════════════════════════════════════════════

def get_능률_summary(df, df_tgt, 월=None, 주차=None, 구분="내국인"):
    d = df.copy()
    if 월:   d = d[d["월"].isin(월)]
    if 주차: d = d[d["주차"].isin(주차)]
    d = d[d["구분"] == 구분]
    월_list = 월 or sorted(d["월"].unique().tolist())

    def _row(기성, 투입, 목표_능률):
        능률실적 = 기성 / 투입 if 투입 > 0 else np.nan
        달성 = 능률실적 / 목표_능률 * 100 \
               if (목표_능률 and not np.isnan(목표_능률) and not np.isnan(능률실적)) else np.nan
        목표기성 = 투입 * 목표_능률 if (목표_능률 and not np.isnan(목표_능률)) else np.nan
        차이 = 기성 - 목표기성 if (목표기성 is not None and not np.isnan(목표기성)) else np.nan
        return {"기성": 기성, "투입": 투입,
                "능률목표": 목표_능률, "능률실적": 능률실적,
                "능률달성(%)": 달성, "목표기성": 목표기성, "차이": 차이}

    tgt_부 = _get_target(df_tgt, "선실부", 구분, 월_list)
    선실부  = _row(d["기성"].sum(), d["투입"].sum(), tgt_부["능률목표"])
    선실부["레벨"] = "선실부 전체"

    과별_rows = []
    for 과명, grp in d.groupby("과"):
        tgt = _get_target(df_tgt, "과별", 구분, 월_list, 과=과명)
        row = _row(grp["기성"].sum(), grp["투입"].sum(), tgt["능률목표"])
        row["과"] = 과명
        과별_rows.append(row)
    df_과별 = pd.DataFrame(과별_rows)

    허용_작업장 = _목표_wc목록(df_tgt, 구분, 월_list)
    직반_rows = []
    if "작업장" in d.columns:
        for (과명, 작업장명), grp in d.groupby(["과", "작업장"]):
            if _strip(작업장명) not in 허용_작업장:
                continue
            # 글로벌은 목표 데이터에 과가 None으로 저장되므로 과 필터 제외
            _필터과 = None if 구분 == "글로벌" else 과명
            tgt = _get_target(df_tgt, "직반", 구분, 월_list, 과=_필터과, 작업장=작업장명)
            row = _row(grp["기성"].sum(), grp["투입"].sum(), tgt["능률목표"])
            row["과"] = 과명
            row["작업장"] = 작업장명
            직반_rows.append(row)
    df_직반 = pd.DataFrame(직반_rows)

    return {"선실부": 선실부, "과별": df_과별, "직반별": df_직반, "_원본": d}


# ══════════════════════════════════════════════════════
# 프로젝트별 상세 (직반 클릭 시)
# ══════════════════════════════════════════════════════

def get_프로젝트별_상세(df_원본: pd.DataFrame, 작업장명: str,
                       df_tgt, 구분, 월_list) -> pd.DataFrame:
    """특정 직반의 프로젝트별 기성/투입/능률 반환"""
    d = df_원본[df_원본["작업장"] == 작업장명].copy()
    if d.empty or "프로젝트" not in d.columns:
        return pd.DataFrame()

    tgt = _get_target(df_tgt, "직반", 구분, 월_list, 작업장=작업장명)
    목표_능률 = tgt["능률목표"]

    rows = []
    for 프로젝트명, grp in d.groupby("프로젝트"):
        기성 = grp["기성"].sum()
        투입 = grp["투입"].sum()
        능률실적 = 기성 / 투입 if 투입 > 0 else np.nan
        달성 = 능률실적 / 목표_능률 * 100 \
               if (목표_능률 and not np.isnan(목표_능률) and not np.isnan(능률실적)) else np.nan
        목표기성 = 투입 * 목표_능률 if (목표_능률 and not np.isnan(목표_능률)) else np.nan
        차이 = 기성 - 목표기성 if (목표기성 is not None and not np.isnan(목표기성)) else np.nan
        rows.append({
            "프로젝트": 프로젝트명,
            "기성": 기성, "투입": 투입,
            "능률목표": 목표_능률, "능률실적": 능률실적,
            "능률달성(%)": 달성, "차이": 차이,
        })
    return pd.DataFrame(rows)


# ══════════════════════════════════════════════════════
# 실동률 집계
# ══════════════════════════════════════════════════════

def get_실동률_summary(df_직접, df_총발생, df_tgt,
                      월=None, 주차=None, 구분="내국인", sel_과="전체"):

    def _filter(df, val_col, 직반=False):
        d = df.copy()
        if 월:   d = d[d["월"].isin(월)]
        if 주차: d = d[d["주차"].isin(주차)]
        d = d[d["구분"] == 구분]
        if 직반: d = d[d["직반포함"]]
        return d

    월_list = 월 or sorted(set(
        df_직접["월"].dropna().unique().tolist() +
        df_총발생["월"].dropna().unique().tolist()
    ))

    def _calc(d직, d총):
        s직 = d직["직접공수"].sum() if "직접공수" in d직.columns else 0
        s총 = d총["총발생"].sum()   if "총발생"   in d총.columns else 0
        return s직, s총, (s직 / s총 if s총 > 0 else np.nan)

    허용_wc = _목표_wc목록(df_tgt, 구분, 월_list)

    d직_부 = _filter(df_직접,   "직접공수", 직반=False)
    d총_부 = _filter(df_총발생, "총발생",   직반=False)

    # 선실부 전체
    s직_부, s총_부, 실적_부 = _calc(d직_부, d총_부)
    tgt_부  = _get_target(df_tgt, "선실부", 구분, 월_list)
    달성_부 = 실적_부 / tgt_부["실동률목표"] * 100 \
              if (tgt_부["실동률목표"] and not np.isnan(실적_부)
                  and not np.isnan(tgt_부["실동률목표"])) else np.nan
    선실부 = {
        "레벨": "선실부 전체", "과": None,
        "직접공수": s직_부, "총발생": s총_부,
        "실동률목표": tgt_부["실동률목표"],
        "실동률실적": 실적_부, "실동률달성(%)": 달성_부,
    }

    # 직반별
    d직_직반 = _filter(df_직접,   "직접공수", 직반=True)
    d총_직반 = _filter(df_총발생, "총발생",   직반=True)

    직반_rows = []
    for wc명, grp직 in d직_직반.groupby("W/C명"):
        if _strip(wc명) not in 허용_wc:
            continue
        grp총 = d총_직반[d총_직반["W/C명"] == wc명]
        s직, s총, 실적 = _calc(grp직, grp총)
        tgt = _get_target(df_tgt, "직반", 구분, 월_list, 작업장=wc명)
        달성 = 실적 / tgt["실동률목표"] * 100 \
               if (tgt["실동률목표"] and not np.isnan(실적)
                   and not np.isnan(tgt["실동률목표"])) else np.nan
        tgt_과행 = df_tgt[
            (df_tgt["레벨"] == "직반") &
            (df_tgt["구분"] == 구분) &
            (df_tgt["작업장"].astype(str).str.strip() == _strip(wc명))
        ]
        과명 = tgt_과행["과"].iloc[0] if not tgt_과행.empty and "과" in tgt_과행.columns else "기타"
        직반_rows.append({
            "과": 과명, "W/C명": wc명,
            "직접공수": s직, "총발생": s총,
            "실동률목표": tgt["실동률목표"],
            "실동률실적": 실적, "실동률달성(%)": 달성,
        })
    df_직반 = pd.DataFrame(직반_rows)

    # ★ 과 필터링 적용
    if sel_과 != "전체" and not df_직반.empty and "과" in df_직반.columns:
        df_직반 = df_직반[df_직반["과"] == sel_과]

    # 과별 소계
    과별_rows = []
    if not df_직반.empty and "과" in df_직반.columns:
        for 과명, grp in df_직반.groupby("과"):
            s직_과 = grp["직접공수"].sum()
            s총_과 = grp["총발생"].sum()
            실적_과 = s직_과 / s총_과 if s총_과 > 0 else np.nan
            tgt_과 = _get_target(df_tgt, "과별", 구분, 월_list, 과=과명)
            달성_과 = 실적_과 / tgt_과["실동률목표"] * 100 \
                      if (tgt_과["실동률목표"] and not np.isnan(실적_과)
                          and not np.isnan(tgt_과["실동률목표"])) else np.nan
            과별_rows.append({
                "과": 과명, "W/C명": f"■ {과명}",
                "직접공수": s직_과, "총발생": s총_과,
                "실동률목표": tgt_과["실동률목표"],
                "실동률실적": 실적_과, "실동률달성(%)": 달성_과,
                "_소계": True,
            })
    df_과별 = pd.DataFrame(과별_rows)

    return {"선실부": 선실부, "과별": df_과별, "직반별": df_직반}
