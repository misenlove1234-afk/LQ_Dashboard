"""
╔══════════════════════════════════════════════════════════════════╗
║  담당자 : ___________  (본인 이름 작성)                          ║
║  항목   : [데이터 전용] kpi_6 - 인도호선 Punch 현황             ║
║  작성일 : ___________                                            ║
╚══════════════════════════════════════════════════════════════════╝

【 데이터 구조 】
  DB 테이블: dbo.lq_kpi6_1 (메인), dbo.lq_kpi5_1 (인도일 참조)
  주요 컬럼:
    프로젝트 / 처리부서 / 발행일
    품질문제상태명 (종료 / 진행중)
    상태 (미완(미회신) / 미완(계획회신완료) / 완료(부서종결) / 완료(선주검토대기) / 취소)
  인도일: lq_kpi5_1 의 [D/L] 컬럼을 프로젝트 기준 LEFT JOIN 으로 가져옴

【 인도임박 판단 기준 】
  오늘 기준 인도일까지 남은 일수 0 ≤ days ≤ 30 인 프로젝트
"""

from datetime import date

import pandas as pd
import streamlit as st

from utils.db import get_engine

TABLE_PUNCH = "dbo.lq_kpi6_1"
TABLE_SHIP  = "dbo.lq_kpi5_1"   # 프로젝트별 인도일(D/L) 참조 — 기존 lq_kpi6_2 대체
_DATE_COLS  = ["발행일", "인도일", "완료예정일", "작업착수일", "조정계획일", "종결일"]


@st.cache_data(ttl=600, max_entries=50)
def load_data() -> pd.DataFrame:
    """
    DB에서 lq_kpi6_1 로드 후 lq_kpi5_1 의 D/L 컬럼을 프로젝트 기준으로 LEFT JOIN
    → 날짜 파싱 → 인도임박 컬럼 추가
    """
    engine = get_engine()
    with engine.connect() as conn:
        df_punch = pd.read_sql("SELECT * FROM " + TABLE_PUNCH, conn)
        df_ship  = pd.read_sql(
            f"SELECT 프로젝트, [D/L] AS 인도일 FROM {TABLE_SHIP}", conn
        )

    df_punch.columns = [str(c).strip() for c in df_punch.columns]
    df_ship.columns  = [str(c).strip() for c in df_ship.columns]

    # lq_kpi5_1 에서 프로젝트별 인도일만 추출 (중복 제거)
    if "인도일" in df_ship.columns and "프로젝트" in df_ship.columns:
        df_ship_인도일 = (
            df_ship[["프로젝트", "인도일"]]
            .drop_duplicates(subset="프로젝트")
            .rename(columns={"인도일": "_인도일_ship"})
        )
        df = df_punch.merge(df_ship_인도일, on="프로젝트", how="left")
        # punch 테이블에 인도일이 없으면 ship 테이블 값으로 채움
        if "인도일" not in df.columns:
            df["인도일"] = df["_인도일_ship"]
        else:
            df["인도일"] = df["인도일"].fillna(df["_인도일_ship"])
        df = df.drop(columns=["_인도일_ship"])
    else:
        df = df_punch.copy()

    df = df  # 컬럼명 정리 완료

    for col in _DATE_COLS:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    for col in ["프로젝트", "처리부서", "품질문제상태명", "상태", "발행위치명", "제목"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    # 인도임박 판단: 오늘 기준 0~30일 이내 인도
    today     = pd.Timestamp(date.today())
    days_left = (df["인도일"] - today).dt.days
    df["인도임박"] = (days_left >= 0) & (days_left <= 30)

    return df


def get_summary(df: pd.DataFrame) -> dict:
    """
    KPI 지표: 총수량 / 조치수량 / 총잔여 / 조치율
    - 조치수량 : 상태 컬럼에 '완료' 키워드가 있는 건수
    - 총잔여   : 상태 컬럼에 '미완' 키워드가 있는 건수
    """
    total  = len(df)
    상태_s = df["상태"].astype(str)
    done   = (상태_s.str.contains("완료", na=False) & ~상태_s.str.contains("미완", na=False)).sum()
    remain = 상태_s.str.contains("미완", na=False).sum()
    rate   = round(done / total * 100, 1) if total > 0 else 0.0
    return {"total": int(total), "done": int(done), "remain": int(remain), "rate": rate}


def get_delivery_soon_projects(df: pd.DataFrame) -> list[str]:
    """인도임박 프로젝트 목록 (인도일 오름차순)"""
    sub = (
        df[df["인도임박"]][["프로젝트", "인도일"]]
        .drop_duplicates("프로젝트")
        .sort_values("인도일")
    )
    return sub["프로젝트"].tolist()


def dept_remain(df: pd.DataFrame) -> pd.DataFrame:
    """상태 컬럼에 '미완' 키워드가 있는 건의 처리부서별 잔여 건수 (내림차순)"""
    return (
        df[df["상태"].astype(str).str.contains("미완", na=False)]
        .groupby("처리부서", as_index=False)
        .size()
        .rename(columns={"size": "잔여건수"})
        .sort_values("잔여건수", ascending=False)
        .reset_index(drop=True)
    )


def vessel_dept_chart(df: pd.DataFrame) -> pd.DataFrame:
    """호선별 × 처리부서별 건수 (stacked bar용)"""
    return (
        df.groupby(["프로젝트", "처리부서"], as_index=False)
        .size()
        .rename(columns={"size": "건수"})
        .sort_values(["프로젝트", "처리부서"])
        .reset_index(drop=True)
    )
