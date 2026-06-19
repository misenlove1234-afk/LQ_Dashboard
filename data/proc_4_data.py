"""
╔══════════════════════════════════════════════════════════════════╗
║  담당자 : ___________  (본인 이름 작성)                          ║
║  항목   : [데이터 전용] proc_4 - 선실 전장 호선별 자재 신청 현황  ║
║  작성일 : ___________                                            ║
╚══════════════════════════════════════════════════════════════════╝

【 판단 기준 】
  - 신청 완료 : 신청자 컬럼에 이름이 있는 경우
  - 신청 가능 : 신청자 컬럼이 비어 있는 경우 (아직 신청 안 됨)
  - 입고 완료 : PLT고유번호가 부여된 경우
"""

import streamlit as st
import pandas as pd

from utils.db import get_engine

TABLE = "dbo.lq_proc4_1"

_DATE_COLS = [
    "요청일", "신청일", "출고일", "Pallet확정일",
    "BOM입력일", "자재소요일", "입고예정일", "인계일",
]


def _is_신청완료(series: pd.Series) -> pd.Series:
    """신청자 컬럼에 실제 이름이 있으면 True (신청 완료)"""
    return series.notna() & (series.astype(str).str.strip() != "") & (series.astype(str).str.strip() != "nan")


def _is_입고완료(series: pd.Series) -> pd.Series:
    """PLT고유번호가 부여되어 있으면 True (입고 완료)"""
    return series.notna() & (series.astype(str).str.strip() != "") & (series.astype(str).str.strip() != "nan")


@st.cache_data(ttl=1800, max_entries=50)
def load_data() -> pd.DataFrame:
    """DB에서 lq_proc4_1 테이블 로드 → 타입 정리 → 파생 컬럼 추가 후 DataFrame 반환"""
    engine = get_engine()
    with engine.connect() as conn:
        df = pd.read_sql("SELECT * FROM " + TABLE, conn)
    df.columns = [str(c).strip() for c in df.columns]

    # 호선 문자열 통일
    df["호선"] = df["호선"].astype(str).str.strip()

    # 날짜 컬럼 변환
    for col in _DATE_COLS:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    # 숫자 컬럼 결측값 0으로 보정 (명시적 float 변환)
    for col in ["BOM수량", "불출요청수량", "출고수량", "Pallet확정수량", "신청가능수량"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(float)

    # 빈 문자열 → NaN 정규화 (텍스트 컬럼이므로 pd.NA 사용 가능)
    for col in ["신청자", "PLT고유번호"]:
        if col in df.columns:
            df[col] = df[col].replace({"": pd.NA, "nan": pd.NA, "-": pd.NA, " ": pd.NA})

    # 지연일 파생 컬럼 (조회일(오늘) - 요청일, 단위: 일)
    if "요청일" in df.columns:
        조회일 = pd.to_datetime('today').normalize() # 오늘 날짜 기준 자정
        # dt.days는 NaN이 있을 수 있으므로 연산 후 0으로 채우고 int 변환
        df["지연일"] = (조회일 - df["요청일"]).dt.days
        df["지연일"] = df["지연일"].fillna(0).clip(lower=0).astype(int)

    return df


def calc_kpi(df: pd.DataFrame) -> dict:
    """
    KPI 지표 계산
    - 자재입고율 : PLT고유번호 부여 건수 / 신청자 이름 있는 건수 × 100
    - 자재신청율 : 신청자 이름 있는 건수 / 전체 건수 × 100
    """
    total = len(df)
    if total == 0:
        return {"total": 0, "신청_cnt": 0, "입고_cnt": 0, "입고율": 0.0, "신청율": 0.0}

    입고_mask = _is_입고완료(df["PLT고유번호"])
    신청_mask = _is_신청완료(df["신청자"])
    신청_cnt  = int(신청_mask.sum())
    입고_cnt  = int(입고_mask.sum())
    return {
        "total":    total,
        "신청_cnt": 신청_cnt,
        "입고_cnt": 입고_cnt,
        "입고율":   round(입고_cnt / 신청_cnt * 100, 1) if 신청_cnt > 0 else 0.0,
        "신청율":   round(신청_cnt / total * 100, 1),
    }


def agg_by_activity(df: pd.DataFrame) -> pd.DataFrame:
    """
    액티비티별 집계
    컬럼: 액티비티 | 신청율(%) | 입고율(%) | 입고수량 | (합계 행 포함)
    """
    입고_mask = _is_입고완료(df["PLT고유번호"])
    신청_mask = _is_신청완료(df["신청자"])

    grp = df.groupby("액티비티", sort=False)
    result = pd.DataFrame({
        "액티비티":  grp["액티비티"].first().index,
        "전체건수":   grp.size(),
        "_신청":      grp["신청자"].apply(lambda s: _is_신청완료(s).sum()),
        "_입고":      grp["PLT고유번호"].apply(lambda s: _is_입고완료(s).sum()),
        "입고수량":    grp.apply(lambda x: x.loc[_is_입고완료(x["PLT고유번호"]), "Pallet확정수량"].sum(), include_groups=False),
    }).reset_index(drop=True)

    # pandas object 에러 방지를 위해 명시적 astype(float) 추가 및 pd.NA 대신 float('nan') 적용
    result["신청율(%)"] = (result["_신청"] / result["전체건수"] * 100).round(1).astype(float)
    result["입고율(%)"] = (result["_입고"] / result["_신청"].replace(0, float('nan')) * 100).round(1).fillna(0.0).astype(float)
    
    result = result[["액티비티", "신청율(%)", "입고율(%)", "입고수량"]]

    # 합계 행 (float로 강제 캐스팅)
    total = len(df)
    신청_cnt = int(신청_mask.sum())
    sum_row = pd.DataFrame([{
        "액티비티":  "합계",
        "신청율(%)": float(round(신청_cnt / total * 100, 1) if total else 0.0),
        "입고율(%)": float(round(입고_mask.sum() / 신청_cnt * 100, 1) if 신청_cnt > 0 else 0.0),
        "입고수량":  float(df.loc[입고_mask, "Pallet확정수량"].sum()),
    }])
    
    return pd.concat([result, sum_row], ignore_index=True)


def agg_by_maker(df: pd.DataFrame) -> pd.DataFrame:
    """
    제작회사별 집계
    컬럼: 제작회사 | BOM수량합계 | 입고율(%) | 입고수량 | 평균지연일
    """
    입고_mask = _is_입고완료(df["PLT고유번호"])

    grp = df.groupby("제작회사", sort=False)

    result = pd.DataFrame({
        "제작회사":    grp["제작회사"].first().index,
        "전체건수":    grp.size(),
        "BOM수량합계": grp["BOM수량"].sum().astype(float),
        "_신청":       grp["신청자"].apply(lambda s: _is_신청완료(s).sum()),
        "_입고":       grp["PLT고유번호"].apply(lambda s: _is_입고완료(s).sum()),
        "입고수량":     grp.apply(lambda x: x.loc[_is_입고완료(x["PLT고유번호"]), "Pallet확정수량"].sum(), include_groups=False).astype(float),
        "평균지연일":   grp["지연일"].mean().round(1) if "지연일" in df.columns else 0.0,
    }).reset_index(drop=True)

    # object 에러 방지를 위해 명시적 astype(float) 추가 및 pd.NA 대신 float('nan') 적용
    result["입고율(%)"] = (result["_입고"] / result["_신청"].replace(0, float('nan')) * 100).round(1).fillna(0.0).astype(float)
    
    # 평균지연일도 확실하게 float 처리
    result["평균지연일"] = result["평균지연일"].fillna(0.0).astype(float)

    return result[["제작회사", "BOM수량합계", "입고율(%)", "입고수량", "평균지연일"]]