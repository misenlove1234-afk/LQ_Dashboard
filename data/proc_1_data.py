"""
╔══════════════════════════════════════════════════════════════════╗
║  항목 : [데이터 전용] proc_1 - PTW 미출력 현황                  ║
║  백데이터 : proc_1_dummy.xlsx                               ║
╚══════════════════════════════════════════════════════════════════╝
"""

import streamlit as st
import pandas as pd

from utils.db import get_engine

TABLE = "dbo.lq_proc1_1"


@st.cache_data(ttl=1800, max_entries=50)
def load_data() -> pd.DataFrame:
    """DB에서 lq_proc1_1 테이블 로드 및 전처리"""
    engine = get_engine()
    with engine.connect() as conn:
        df = pd.read_sql("SELECT * FROM " + TABLE, conn)
    df.columns = [str(c).strip() for c in df.columns]

    # 날짜 파싱
    for col in ["시작일시", "종료일시"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], format="%y/%m/%d %H:%M", errors="coerce")

    if "혼재승인일시" in df.columns:
        df["혼재승인일시"] = pd.to_datetime(df["혼재승인일시"], errors="coerce")

    # 출력여부 정규화: '출력XXXX-XXXXX' 등 '출력'으로 시작하는 값 → '출력' 통일
    col_permit = "출력여부(Permit No)"
    if col_permit in df.columns:
        df[col_permit] = df[col_permit].astype(str).str.strip()
        df.loc[df[col_permit].str.startswith("출력"), col_permit] = "출력"

    # 호선 → 문자열
    if "호선" in df.columns:
        df["호선"] = df["호선"].astype(str)

    # 투입인원 → 정수
    if "투입인원" in df.columns:
        df["투입인원"] = pd.to_numeric(df["투입인원"], errors="coerce").fillna(0).astype(int)

    return df


def get_summary(df: pd.DataFrame) -> dict:
    """KPI 요약 지표 계산"""
    total = len(df)
    # 작업취소된 항목은 미출력 카운트에서 제외
    취소_mask = df.get("결재", pd.Series(dtype=str)) == "작업취소"
    not_printed = ((df["출력여부(Permit No)"] == "미출력") & ~취소_mask).sum()
    printed = (df["출력여부(Permit No)"] == "출력").sum()
    confined_total = (df["밀폐여부"] == "밀폐").sum()
    confined_not_printed = (
        (df["밀폐여부"] == "밀폐") & (df["출력여부(Permit No)"] == "미출력") & ~취소_mask
    ).sum()
    print_rate = round(printed / total * 100, 1) if total > 0 else 0.0

    return {
        "total": int(total),
        "not_printed": int(not_printed),
        "printed": int(printed),
        "print_rate": print_rate,
        "confined_total": int(confined_total),
        "confined_not_printed": int(confined_not_printed),
    }


def filter_data(
    df: pd.DataFrame,
    vessels: list,
    depts: list,
    categories: list,
    date_range: tuple,
) -> pd.DataFrame:
    """사이드바 필터 적용"""
    fdf = df.copy()

    if vessels:
        fdf = fdf[fdf["호선"].isin(vessels)]
    if depts:
        fdf = fdf[fdf["소속(팀)"].isin(depts)]
    if categories:
        fdf = fdf[fdf["구분"].isin(categories)]

    start_dt, end_dt = date_range
    if start_dt and "시작일시" in fdf.columns:
        fdf = fdf[fdf["시작일시"].dt.date >= start_dt]
    if end_dt and "시작일시" in fdf.columns:
        fdf = fdf[fdf["시작일시"].dt.date <= end_dt]

    return fdf