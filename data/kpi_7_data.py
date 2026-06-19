# ============================================================
# data/kpi_7_data.py  ─  데이터 처리 전용 모듈
# ============================================================
# ┌─────────────────────────────────────────────────────────┐
# │  AI 작업 가이드                                          │
# │  이 파일은 '데이터 처리 전용' 모듈입니다.                │
# │  1. st.write, st.dataframe 같은 화면 코드는 넣지 마세요. │
# │  2. DB 연결은 utils.db 의 get_engine() 을 사용하세요.   │
# │  3. 함수 위에는 @st.cache_data(ttl=600) 를 붙이세요.   │
# │  4. 최종 결과는 DataFrame 또는 dict 로 return 하세요.   │
# └─────────────────────────────────────────────────────────┘

import logging
import traceback

import pandas as pd
import streamlit as st
from utils.db import get_engine

logger = logging.getLogger(__name__)

TABLE_RAW = "dbo.lq_kpi7_1"
TABLE_TARGET = "dbo.lq_kpi7_2"
TABLE_사유 = "dbo.lq_kpi7_3"
TARGET_MAP = {"구조": 0.7, "배관": 1.4}


# ══════════════════════════════════════════════════════════
# 1. 데이터 로드
# ══════════════════════════════════════════════════════════
@st.cache_data(ttl=600)
def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    DB에서 2개 테이블 로드
    Returns: df_raw, df_target
    """
    engine = get_engine()
    with engine.connect() as conn:
        df_raw = pd.read_sql("SELECT * FROM " + TABLE_RAW, conn)
        df_target = pd.read_sql("SELECT * FROM " + TABLE_TARGET, conn)
    return df_raw, df_target


# ══════════════════════════════════════════════════════════
# 2. 목표값 조회
# ══════════════════════════════════════════════════════════
def get_target_rate(df_target: pd.DataFrame, discipline: str) -> float:
    row = df_target[df_target["구분"] == discipline]
    if not row.empty:
        return float(row["26년목표"].values[0])
    return TARGET_MAP.get(discipline, 1.0)


# ══════════════════════════════════════════════════════════
# 3. 필터 옵션
# ══════════════════════════════════════════════════════════
def get_filter_options(df_raw: pd.DataFrame) -> dict:
    years = sorted(df_raw["year"].dropna().unique().tolist(), reverse=True)
    months = sorted(df_raw["month"].dropna().unique().tolist())
    discs = sorted(df_raw["discipline"].dropna().unique().tolist())
    return {"years": years, "months": months, "disciplines": discs}


# ══════════════════════════════════════════════════════════
# 4. 필터 적용
# ══════════════════════════════════════════════════════════
def apply_filter(
    df: pd.DataFrame,
    year: int,
    months: list,
    discipline: str,
) -> pd.DataFrame:
    df_f = df[df["year"] == year].copy()
    if months:
        df_f = df_f[df_f["month"].isin(months)]
    if discipline != "전체":
        df_f = df_f[df_f["discipline"] == discipline]
    return df_f


# ══════════════════════════════════════════════════════════
# 5. 달성률 계산 (낮을수록 좋음)
# ══════════════════════════════════════════════════════════
def calc_achieve(rate: float, target: float) -> float:
    """
    불량률은 낮을수록 좋은 지표
    달성률 = (목표 / 실적) * 100, 실적 <= 목표이면 100% cap
    """
    if target <= 0:
        return 0.0
    if rate <= 0:
        return 100.0
    return min(round((target / rate) * 100, 1), 100.0)


# ══════════════════════════════════════════════════════════
# 6. 상단 KPI 요약
# ══════════════════════════════════════════════════════════
def get_summary(df_f: pd.DataFrame, df_target: pd.DataFrame, discipline: str) -> dict:
    """
    구조/배관별 KPI 집계
    반환: {
      "구조": {rate, target, achieve, insp_m, defct_m, miss_cnt, welder_detail},
      "배관": {...},
      "전체": {insp_m, defct_m}
    }
    """
    disc_list = ["구조", "배관"] if discipline == "전체" else [discipline]
    result = {}

    for disc in disc_list:
        df_d = df_f[df_f["discipline"] == disc]
        # 배관: 매수 기준 / 구조: m 기준
        if disc == "배관":
            insp  = df_d["검사매수"].sum()
            defct = df_d["불량매수"].sum()
            insp_col, defct_col = "검사매수", "불량매수"
        else:
            insp  = df_d["검사길이mm"].sum()
            defct = df_d["불량길이mm"].sum()
            insp_col, defct_col = "검사길이mm", "불량길이mm"
        rate = round(defct / insp * 100, 2) if insp > 0 else 0.0
        target = get_target_rate(df_target, disc)
        achieve = calc_achieve(rate, target)

        # 용접사별 불량률 → 목표 미달 수
        wd = df_d.groupby("용접사").agg(
            insp_m=(insp_col, "sum"),
            defct_m=(defct_col, "sum"),
        ).reset_index()
        wd["불량률"] = wd.apply(
            lambda r: round(r["defct_m"] / r["insp_m"] * 100, 2)
            if r["insp_m"] > 0 else 0.0, axis=1
        )
        miss_cnt = int((wd["불량률"] > target).sum())
        wd = wd.rename(columns={"용접사": "용접사", "insp_m": "검사(m)", "defct_m": "불량(m)"})
        wd = wd.sort_values("불량률", ascending=False).reset_index(drop=True)

        result[disc] = {
            "rate" : rate,
            "target" : target,
            "achieve" : achieve,
            "insp_m" : float(insp),
            "defct_m" : float(defct),
            "miss_cnt" : miss_cnt,
            "welder_detail" : wd,
        }

    total_insp  = df_f["검사길이mm"].sum()
    total_defct = df_f["불량길이mm"].sum()
    result["전체"] = {
        "insp_m" : float(total_insp),
        "defct_m": float(total_defct),
    }
    return result


# ══════════════════════════════════════════════════════════
# 7. 월별 추이
# ══════════════════════════════════════════════════════════
def get_monthly_trend(df_raw: pd.DataFrame, year: int, discipline: str) -> pd.DataFrame:
    df = df_raw[df_raw["year"] == year].copy()
    if discipline != "전체":
        df = df[df["discipline"] == discipline]

    rows = []
    for (month, disc), g in df.groupby(["month", "discipline"]):
        if disc == "배관":
            insp  = g["검사매수"].sum()
            defct = g["불량매수"].sum()
        else:
            insp  = g["검사길이mm"].sum()
            defct = g["불량길이mm"].sum()
        rate = round(defct / insp * 100, 2) if insp > 0 else 0.0
        rows.append({"month": month, "discipline": disc, "insp": insp, "defct": defct, "불량률": rate})
    grp = pd.DataFrame(rows)
    return grp.sort_values("month").reset_index(drop=True)


# ══════════════════════════════════════════════════════════
# 8. expander 상세 (프로젝트/소속/용접사/검사m/불량m)
# ══════════════════════════════════════════════════════════
def get_miss_detail(df_f: pd.DataFrame, df_target: pd.DataFrame, discipline: str) -> pd.DataFrame:
    """
    목표 미달 용접사 상세
    columns: 프로젝트, 부서, 과, 용접사, 검사(m), 불량(m), 불량률(%)
    """
    df_d = df_f[df_f["discipline"] == discipline].copy()
    target = get_target_rate(df_target, discipline)

    # 협력사명 파생: 워크센터 값에서 과 값을 앞에서 제거
    if "워크센터" in df_d.columns and "과" in df_d.columns:
        df_d["협력사"] = df_d.apply(
            lambda r: str(r["워크센터"]).replace(str(r["과"]), "", 1).strip()
            if pd.notna(r["워크센터"]) and pd.notna(r["과"]) else "", axis=1
        )
    else:
        df_d["협력사"] = ""

    grp_cols = []
    for c in ["프로젝트", "과", "협력사", "용접사"]:
        if c in df_d.columns:
            grp_cols.append(c)

    if not grp_cols:
        return pd.DataFrame()

    insp_col  = "검사매수"  if discipline == "배관" else "검사길이mm"
    defct_col = "불량매수" if discipline == "배관" else "불량길이mm"
    unit_label = "매" if discipline == "배관" else "m"

    grp = df_d.groupby(grp_cols).agg(
        검사m=(insp_col,  "sum"),
        불량m=(defct_col, "sum"),
    ).reset_index()

    grp["불량률(%)"] = grp.apply(
        lambda r: round(r["불량m"] / r["검사m"] * 100, 2)
        if r["검사m"] > 0 else 0.0, axis=1
    )
    grp = grp.rename(columns={
        "검사m": f"검사({unit_label})",
        "불량m": f"불량({unit_label})",
        "과": "W/C"
    })
    # 목표 미달 행만 (불량률 > 목표)
    grp = grp[grp["불량률(%)"] > target]
    grp = grp.sort_values("불량률(%)", ascending=False).reset_index(drop=True)
    return grp


# ══════════════════════════════════════════════════════════
# 9. 워크센터별 집계
# ══════════════════════════════════════════════════════════
def get_workcenter_summary(df_f: pd.DataFrame, df_target: pd.DataFrame) -> pd.DataFrame:
    # 협력사명 파생
    if "워크센터" in df_f.columns and "과" in df_f.columns:
        df_f = df_f.copy()
        df_f["협력사"] = df_f.apply(
            lambda r: str(r["워크센터"]).replace(str(r["과"]), "", 1).strip()
            if pd.notna(r["워크센터"]) and pd.notna(r["과"]) else "", axis=1
        )
        grp = df_f.groupby(["과", "협력사", "discipline"]).agg(
            검사m_구조=("검사길이mm", "sum"),
            불량m_구조=("불량길이mm", "sum"),
            검사m_배관=("검사매수",   "sum"),
            불량m_배관=("불량매수",   "sum"),
        ).reset_index()
    else:
        grp = df_f.groupby(["과", "discipline"]).agg(
            검사m_구조=("검사길이mm", "sum"),
            불량m_구조=("불량길이mm", "sum"),
            검사m_배관=("검사매수",   "sum"),
            불량m_배관=("불량매수",   "sum"),
        ).reset_index()
    # discipline에 따라 검사m/불량m 선택
    grp["검사m"] = grp.apply(
        lambda r: r["검사m_배관"] if r["discipline"] == "배관" else r["검사m_구조"], axis=1)
    grp["불량m"] = grp.apply(
        lambda r: r["불량m_배관"] if r["discipline"] == "배관" else r["불량m_구조"], axis=1)
    grp = grp.drop(columns=["검사m_구조","불량m_구조","검사m_배관","불량m_배관"])
    grp["불량률"] = grp.apply(
        lambda r: round(r["불량m"] / r["검사m"] * 100, 2) if r["검사m"] > 0 else 0.0, axis=1
    )
    grp["목표"] = grp["discipline"].apply(lambda d: get_target_rate(df_target, d))
    grp["달성률"] = grp.apply(
        lambda r: calc_achieve(r["불량률"], r["목표"]), axis=1
    )
    return grp.sort_values("불량률", ascending=False).reset_index(drop=True)


# ══════════════════════════════════════════════════════════
# 10. 프로젝트별 TOP N
# ══════════════════════════════════════════════════════════
def get_project_top(df_f: pd.DataFrame, df_target: pd.DataFrame, top_n: int = 5) -> pd.DataFrame:
    grp = df_f.groupby(["프로젝트", "discipline"]).agg(
        검사m_구조=("검사길이mm", "sum"),
        불량m_구조=("불량길이mm", "sum"),
        검사m_배관=("검사매수",   "sum"),
        불량m_배관=("불량매수",   "sum"),
    ).reset_index()
    grp["검사m"] = grp.apply(
        lambda r: r["검사m_배관"] if r["discipline"] == "배관" else r["검사m_구조"], axis=1)
    grp["불량m"] = grp.apply(
        lambda r: r["불량m_배관"] if r["discipline"] == "배관" else r["불량m_구조"], axis=1)
    grp = grp.drop(columns=["검사m_구조","불량m_구조","검사m_배관","불량m_배관"])
    grp["불량률"] = grp.apply(
        lambda r: round(r["불량m"] / r["검사m"] * 100, 2) if r["검사m"] > 0 else 0.0, axis=1
    )
    grp["목표"] = grp["discipline"].apply(lambda d: get_target_rate(df_target, d))
    grp["달성률"] = grp.apply(
        lambda r: calc_achieve(r["불량률"], r["목표"]), axis=1
    )
    return grp.sort_values("불량m", ascending=False).reset_index(drop=True)


# ══════════════════════════════════════════════════════════
# 11. 용접사별 상세
# ══════════════════════════════════════════════════════════
def get_welder_detail(df_f: pd.DataFrame, df_target: pd.DataFrame) -> pd.DataFrame:
    if "워크센터" in df_f.columns and "과" in df_f.columns:
        df_f = df_f.copy()
        df_f["협력사"] = df_f.apply(
            lambda r: str(r["워크센터"]).replace(str(r["과"]), "", 1).strip()
            if pd.notna(r["워크센터"]) and pd.notna(r["과"]) else "", axis=1
        )
    grp_cols = [c for c in ["과", "협력사", "용접사", "discipline"] if c in df_f.columns]
    grp = df_f.groupby(grp_cols).agg(
        검사m_구조=("검사길이mm", "sum"),
        불량m_구조=("불량길이mm", "sum"),
        검사m_배관=("검사매수",   "sum"),
        불량m_배관=("불량매수",   "sum"),
    ).reset_index()
    grp["검사m"] = grp.apply(
        lambda r: r["검사m_배관"] if r["discipline"] == "배관" else r["검사m_구조"], axis=1)
    grp["불량m"] = grp.apply(
        lambda r: r["불량m_배관"] if r["discipline"] == "배관" else r["불량m_구조"], axis=1)
    grp = grp.drop(columns=["검사m_구조","불량m_구조","검사m_배관","불량m_배관"])
    grp["불량률"] = grp.apply(
        lambda r: round(r["불량m"] / r["검사m"] * 100, 2) if r["검사m"] > 0 else 0.0, axis=1
    )
    grp["목표"] = grp["discipline"].apply(lambda d: get_target_rate(df_target, d))
    grp["달성률"] = grp.apply(
        lambda r: calc_achieve(r["불량률"], r["목표"]), axis=1
    )
    grp = grp.rename(columns={"과": "W/C"})
    return grp.sort_values("불량률", ascending=False).reset_index(drop=True)

# ══════════════════════════════════════════════════════════
# 12. 사유 테이블 로드
# ══════════════════════════════════════════════════════════
def load_사유() -> pd.DataFrame:
    """
    dbo.lq_kpi7_3 테이블 로드
    columns: 용접사, discipline, 프로젝트, 사유, 입력일시
    테이블이 없으면 빈 DataFrame 반환
    """
    engine = get_engine()
    try:
        with engine.connect() as conn:
            df = pd.read_sql("SELECT * FROM " + TABLE_사유, conn)
        return df
    except Exception:
        return pd.DataFrame(columns=["용접사", "discipline", "프로젝트", "사유", "입력일시"])


# ══════════════════════════════════════════════════════════
# 13. 사유 UPSERT (저장/수정)
# ══════════════════════════════════════════════════════════
def upsert_사유(용접사: str, discipline: str, 프로젝트: str, 사유: str) -> bool:
    """
    키: 용접사 + discipline + 프로젝트
    테이블 없으면 CREATE 후 INSERT, 있으면 UPSERT
    Returns: True=성공, False=실패
    """
    from datetime import datetime
    import sqlalchemy as sa

    engine = get_engine()
    now = datetime.now()

    create_sql = (
        "IF NOT EXISTS ("
        "    SELECT 1 FROM INFORMATION_SCHEMA.TABLES"
        "    WHERE TABLE_SCHEMA = 'dbo'"
        "    AND TABLE_NAME = 'lq_kpi7_3'"
        ") "
        "CREATE TABLE " + TABLE_사유 + " ("
        "    용접사 NVARCHAR(100) NOT NULL,"
        "    discipline NVARCHAR(50) NOT NULL,"
        "    프로젝트 NVARCHAR(200) NOT NULL,"
        "    사유 NVARCHAR(1000),"
        "    입력일시 DATETIME DEFAULT GETDATE(),"
        "    CONSTRAINT PK_lq_kpi7_3 PRIMARY KEY (용접사, discipline, 프로젝트)"
        ")"
    )

    upsert_sql = (
        "MERGE " + TABLE_사유 + " AS target "
        "USING (SELECT :용접사 AS 용접사, :discipline AS discipline, :프로젝트 AS 프로젝트) AS src "
        "ON target.용접사 = src.용접사 "
        "   AND target.discipline = src.discipline "
        "   AND target.프로젝트 = src.프로젝트 "
        "WHEN MATCHED THEN "
        "    UPDATE SET 사유 = :사유, 입력일시 = :now "
        "WHEN NOT MATCHED THEN "
        "    INSERT (용접사, discipline, 프로젝트, 사유, 입력일시) "
        "    VALUES (:용접사, :discipline, :프로젝트, :사유, :now);"
    )

    try:
        with engine.begin() as conn:
            conn.execute(sa.text(create_sql))
            conn.execute(sa.text(upsert_sql), {
                "용접사": 용접사, "discipline": discipline,
                "프로젝트": 프로젝트, "사유": 사유, "now": now
            })
        return True
    except Exception as e:
        logger.error("사유 저장 오류: %s\n%s", e, traceback.format_exc())
        st.error("저장 중 오류가 발생했습니다. 관리자에게 문의해 주세요.")
        return False