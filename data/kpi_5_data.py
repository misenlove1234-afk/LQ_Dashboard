import pandas as pd
import streamlit as st
from datetime import date
from utils.db import get_engine

# ── 테이블명 설정 ──────────────────────────────────────────
TABLE_SUNPYO = "dbo.lq_kpi5_1"
TABLE_GONGSU = "dbo.lq_kpi5_2"

# ── 실행과 코드 → 한글 이름 ────────────────────────────────
GWA_MAP = {
    "1H67400": "선실1과",
    "1H67500": "선실2과",
    "1J67400": "선실전장과",
}

BIMOK_ORDER = ['정상', '비물량', '현장추가', '효율저하']


# ── 유틸 함수 ──────────────────────────────────────────────
def gwa_label(code: str) -> str:
    return GWA_MAP.get(str(code), str(code))


def fmt(v) -> str:
    try:
        return f"{float(v):,.1f}"
    except Exception:
        return "-"


def calc_stage(row) -> str:
    today = pd.Timestamp(date.today())
    try:
        start = pd.Timestamp(row['착수일자'])
        mount = pd.Timestamp(row['탑재착수'])
        lc = pd.Timestamp(row['L/C'])
        dl = pd.Timestamp(row['D/L'])
        if any(pd.isna(x) for x in [start, mount, lc, dl]):
            return '-'
    except Exception:
        return '-'
    if today < start: return '30'
    if mount > lc: return '50' if today < mount else '70'
    if today < mount: return '50'
    elif today < lc: return '60'
    else: return '70'


def calc_urgent(row) -> str:
    try:
        dl = pd.Timestamp(row['D/L'])
        if pd.isna(dl): return '정상'
        days_left = (dl - pd.Timestamp(date.today())).days
        if days_left <= 0: return '인도완료'
        elif days_left <= 60: return '임박'
        else: return '정상'
    except Exception:
        return '정상'


# ── 데이터 로드 ────────────────────────────────────────────
@st.cache_data(ttl=600)
def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    engine = get_engine()
    with engine.connect() as conn:
        df_s = pd.read_sql("SELECT * FROM " + TABLE_SUNPYO, conn)
        df_g = pd.read_sql("SELECT * FROM " + TABLE_GONGSU, conn)
    return df_s, df_g


def preprocess_sunpyo(df_sunpyo: pd.DataFrame) -> pd.DataFrame:
    df = df_sunpyo.copy()
    for col in ['착수일자', '완료일자', '탑재착수', 'L/C', 'D/L']:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')
    df['Stage'] = df.apply(calc_stage, axis=1)
    df['인도임박'] = df.apply(calc_urgent, axis=1)
    return df


def preprocess_gongsu(df_gongsu: pd.DataFrame) -> pd.DataFrame:
    df = df_gongsu.copy()
    for col in ['목표예산', '계약', '미계약', '누계기성', '잔여']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    if '실행과' in df.columns:
        df['실행과명'] = df['실행과'].apply(gwa_label)
    return df


def get_filter_options(df_gongsu: pd.DataFrame) -> dict:
    projects = sorted(df_gongsu['프로젝트'].dropna().unique().tolist())
    disc_options = sorted(df_gongsu['Discipline'].dropna().unique().tolist())
    bimok_options = [b for b in BIMOK_ORDER if b in df_gongsu['비목'].unique()]
    stage_options = ['30', '50', '60', '70']
    gwa_codes = sorted(df_gongsu['실행과'].dropna().unique().tolist()) if '실행과' in df_gongsu.columns else []
    gwa_display = [gwa_label(c) for c in gwa_codes]
    gwa_rev = {gwa_label(c): c for c in gwa_codes}
    return {
        'projects' : projects,
        'disc_options' : disc_options,
        'bimok_options': bimok_options,
        'stage_options': stage_options,
        'gwa_codes' : gwa_codes,
        'gwa_display' : gwa_display,
        'gwa_rev' : gwa_rev,
    }


def get_summary(df_f: pd.DataFrame) -> dict:
    """
    KPI 집계:
      A = 총 목표예산
      B = 총 계약
      C = 총 누계기성
      BC = B - C (총 잔여)
      AB = A - B (총 미계약)
    """
    A = df_f['목표예산'].sum()
    B = df_f['계약'].sum()
    C = df_f['누계기성'].sum()
    BC = B - C
    AB = A - B
    prog = (C / A * 100) if A > 0 else 0.0
    return {
        'A' : A,
        'B' : B,
        'C' : C,
        'BC' : BC,
        'AB' : AB,
        'prog': prog,
    }


def get_ship_display(
    df_sunpyo: pd.DataFrame,
    df_f: pd.DataFrame,
    sel_project: list,
) -> tuple[pd.DataFrame, list]:
    df_sv = df_sunpyo[df_sunpyo['프로젝트'].isin(sel_project)].copy()

    prog_df = df_f.groupby('프로젝트').agg(
        목표합=('목표예산', 'sum'),
        기성합=('누계기성', 'sum')
    ).reset_index()
    prog_df['Progress(%)'] = prog_df.apply(
        lambda r: round(r['기성합'] / r['목표합'] * 100, 1) if r['목표합'] > 0 else 0.0,
        axis=1
    )
    rem_df = df_f.groupby('프로젝트')['잔여'].sum().reset_index()
    rem_df.columns = ['프로젝트', '잔여합계']

    df_sv = df_sv.merge(prog_df[['프로젝트', 'Progress(%)']], on='프로젝트', how='left')
    df_sv = df_sv.merge(rem_df, on='프로젝트', how='left')
    df_sv['잔여합계'] = df_sv['잔여합계'].fillna(0)
    df_sv['Progress(%)'] = df_sv['Progress(%)'].fillna(0)

    sort_order = {'인도완료': 0, '임박': 1, '정상': 2}
    df_sv['정렬순서'] = df_sv['인도임박'].map(sort_order)
    df_sv = df_sv.sort_values(
        by=['정렬순서', 'D/L'], ascending=[True, True]
    ).drop(columns=['정렬순서']).reset_index(drop=True)

    # Stage 색상 정보도 함께 반환 (HTML 테이블용)
    stage_colors = {'30': '#94a3b8', '50': '#60a5fa', '60': '#f59e0b', '70': '#00c48c'}

    return df_sv, stage_colors


def get_pivot_data(
    df_f: pd.DataFrame,
    df_sunpyo: pd.DataFrame,
    sel_project: list,
    sel_disc: list,
    bimok_show: list,
) -> list:
    """
    공수현황 피벗 데이터를 row dict 리스트로 반환합니다.
    (HTML 테이블 렌더링용)
    """
    stage_map = df_sunpyo.set_index('프로젝트')['Stage'].to_dict()

    pivot_rows = []
    for proj in sel_project:
        for disc in sel_disc:
            stage_str = stage_map.get(proj, '-')
            row_d = {'프로젝트': proj, 'Discipline': disc, 'Stage': stage_str}
            has = False
            for bm in bimok_show:
                sub = df_f[
                    (df_f['프로젝트'] == proj) &
                    (df_f['Discipline'] == disc) &
                    (df_f['비목'] == bm)
                ]
                if not sub.empty:
                    has = True
                row_d[f'{bm}_목표'] = float(sub['목표예산'].sum()) if not sub.empty else 0.0
                row_d[f'{bm}_계약'] = float(sub['계약'].sum()) if not sub.empty else 0.0
                row_d[f'{bm}_잔여'] = float(sub['잔여'].sum()) if not sub.empty else 0.0
                row_d[f'{bm}_미계약'] = float(sub['미계약'].sum()) if not sub.empty else 0.0
            if has:
                pivot_rows.append(row_d)

    return pivot_rows
