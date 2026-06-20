"""
╔══════════════════════════════════════════════════════════════════╗
║  항목 : [화면 전용] proc_1 - 일일 작업허가서 현황               ║
║  백데이터 : hwagi_dummy_1000.xlsx                               ║
╚══════════════════════════════════════════════════════════════════╝
"""

import logging
import traceback

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from data.proc_1_data import filter_data, get_summary, load_data
from utils.db import run_query

logger = logging.getLogger(__name__)

# ── 공통 스타일 ───────────────────────────────────────────────────
_CSS = """
<style>
/* ── 사이드바 다크모드 ── */
[data-testid="stSidebar"] {
    background-color: #0d1b2e !important;
}
[data-testid="stSidebar"] * {
    color: #ffffff !important;
}
[data-testid="stSidebar"] .stButton button {
    background-color: #1d4ed8 !important;
    border: none !important;
    color: #ffffff !important;
}
[data-testid="stSidebar"] .stButton button:hover {
    background-color: #2563eb !important;
}
[data-testid="stSidebar"] div[data-baseweb="select"] > div,
[data-testid="stSidebar"] div[data-baseweb="base-input"] > input {
    background-color: #1e293b !important;
    color: #ffffff !important;
    -webkit-text-fill-color: #ffffff !important;
    border-color: #334155 !important;
}
[data-testid="stSidebar"] .streamlit-expanderHeader {
    background-color: #1e293b !important;
    color: #ffffff !important;
}
[data-testid="stSidebar"] .streamlit-expanderContent {
    background-color: #0f172a !important;
}
[data-testid="stMetricValue"] { font-size:1.6rem; color:#e2e8f0; }
[data-testid="stMetricLabel"] { font-size:0.82rem; color:#94a3b8; }
[data-testid="metric-container"] {
    padding:0.6rem 0.9rem;
    background:rgba(15,35,65,0.65);
    border-radius:10px;
    border:1px solid rgba(56,189,248,0.22);
}
.stTabs [data-baseweb="tab-list"] { background-color:transparent; }
.stTabs [data-baseweb="tab"]      { color:#94a3b8; font-size:0.95rem; }
.stTabs [aria-selected="true"]    { color:#38bdf8 !important; }
h3, h4 { color:#ffffff !important; }
.dark-html-table { width:100%; border-collapse:collapse; font-size:0.83rem; }
.dark-html-table th {
    background:#0a1628 !important; color:#7dd3fc !important;
    padding:0.5rem 0.75rem; border-bottom:1px solid rgba(56,189,248,0.3);
    text-align:left; font-weight:600;
}
.dark-html-table td {
    background:#0d1f3c !important; color:#e2e8f0 !important;
    padding:0.45rem 0.75rem; border-bottom:1px solid rgba(56,189,248,0.08);
}
.dark-html-table tr:hover td { background:rgba(56,189,248,0.13) !important; }
.dark-html-table-wrap {
    border:1px solid rgba(56,189,248,0.2); border-radius:8px;
    overflow:auto; max-height:420px; background:#0d1f3c;
}
.badge-red   { background:#ef4444; color:#fff; padding:2px 8px; border-radius:12px; font-size:0.78rem; }
.badge-green { background:#22c55e; color:#fff; padding:2px 8px; border-radius:12px; font-size:0.78rem; }
.badge-blue  { background:#3b82f6; color:#fff; padding:2px 8px; border-radius:12px; font-size:0.78rem; }
.badge-gray  { background:#64748b; color:#fff; padding:2px 8px; border-radius:12px; font-size:0.78rem; }
</style>
"""

# ── 색상 팔레트 ───────────────────────────────────────────────────
_COLORS = {
    "미출력": "#ef4444",
    "출력": "#22c55e",
    "밀폐": "#f59e0b",
    "일반": "#38bdf8",
    "화기": "#f43f5e",
    "고소": "#a78bfa",
    "화기/밀폐": "#fb923c",
    "화기/고소": "#e879f9",
}
_PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="white"),
    margin=dict(l=0, r=0, t=36, b=0),
)


def _bar_chart(df_group: pd.DataFrame, x: str, y: str, color_col: str | None = None,
               title: str = "", height: int = 340) -> go.Figure:
    """공통 가로/세로 막대 차트 생성"""
    if color_col:
        colors = df_group[color_col].map(lambda v: _COLORS.get(v, "#38bdf8"))
    else:
        colors = "#38bdf8"

    fig = go.Figure(go.Bar(
        x=df_group[x], y=df_group[y],
        marker_color=colors,
        text=df_group[y], textposition="outside",
        textfont=dict(color="white", size=12),
    ))
    fig.update_layout(title=dict(text=title, x=0.5, font=dict(size=14)),
                      height=height, **_PLOTLY_LAYOUT)
    fig.update_xaxes(showgrid=False, tickfont=dict(color="#cbd5e1"))
    fig.update_yaxes(showgrid=True, gridcolor="rgba(255,255,255,0.08)")
    return fig


def _pie_chart(labels: list, values: list, title: str = "", height: int = 320) -> go.Figure:
    colors = [_COLORS.get(l, "#38bdf8") for l in labels]
    fig = go.Figure(go.Pie(
        labels=labels, values=values,
        marker=dict(colors=colors, line=dict(color="rgba(0,0,0,0.4)", width=2)),
        textfont=dict(size=13, color="white"),
        hole=0.38,
    ))
    fig.update_layout(title=dict(text=title, x=0.5, font=dict(size=14)),
                      height=height, showlegend=True,
                      legend=dict(font=dict(color="white")),
                      **_PLOTLY_LAYOUT)
    return fig


def _html_table(df: pd.DataFrame) -> str:
    return (
        f'<div class="dark-html-table-wrap">'
        f'{df.to_html(index=False, classes="dark-html-table", border=0, escape=False)}'
        f'</div>'
    )


def _badge(text: str) -> str:
    cls = {
        "미출력": "badge-red",
        "출력": "badge-green",
        "밀폐": "badge-blue",
        "일반": "badge-gray",
        "완결": "badge-green",
        "진행중": "badge-blue",
        "반려": "badge-red",
    }.get(text, "badge-gray")
    return f'<span class="{cls}">{text}</span>'


# ══════════════════════════════════════════════════════════════════
#  메인 렌더링 함수
# ══════════════════════════════════════════════════════════════════
def render():
    st.markdown(_CSS, unsafe_allow_html=True)

    # ── 데이터 로드 ──────────────────────────────────────────────
    try:
        df_raw = load_data()
    except Exception as e:
        logger.error("작업허가서 데이터 로드 실패: %s\n%s", e, traceback.format_exc())
        st.error("데이터 로드에 실패했습니다. 관리자에게 문의해 주세요.")
        return

    if df_raw.empty:
        st.warning("⚠️ 데이터가 없습니다.")
        return

    # ── 사이드바 필터 ────────────────────────────────────────────
    with st.sidebar:
        st.markdown("<h3 style='color:#ffffff;'>🔎 조회 조건</h3>", unsafe_allow_html=True)

        all_vessels = sorted(df_raw["호선"].unique())
        sel_vessels = st.multiselect(
            "호선 (미선택 시 전체)", all_vessels,
            default=[], key="proc1_vessels"
        )

        all_depts = sorted(df_raw["소속(팀)"].dropna().unique())
        sel_depts = st.multiselect(
            "소속(팀) (미선택 시 전체)", all_depts,
            default=[], key="proc1_depts"
        )

        all_cats = sorted(df_raw["구분"].dropna().unique())
        sel_cats = st.multiselect(
            "구분 (미선택 시 전체)", all_cats,
            default=[], key="proc1_cats"
        )

        valid_dates = df_raw["시작일시"].dropna()
        min_d = valid_dates.min().date() if not valid_dates.empty else None
        max_d = valid_dates.max().date() if not valid_dates.empty else None

        if min_d and max_d:
            date_range = st.date_input(
                "기간 (시작일시 기준)", [min_d, max_d],
                min_value=min_d, max_value=max_d,
                key="proc1_date"
            )
            if len(date_range) == 2:
                start_d, end_d = date_range
            else:
                start_d, end_d = min_d, max_d
        else:
            start_d, end_d = None, None

    # ── 필터 적용 ────────────────────────────────────────────────
    df = filter_data(
        df_raw,
        vessels=sel_vessels or all_vessels,
        depts=sel_depts or all_depts,
        categories=sel_cats or all_cats,
        date_range=(start_d, end_d),
    )

    if df.empty:
        st.warning("⚠️ 조회 조건에 해당하는 데이터가 없습니다.")
        return

    summary = get_summary(df)

    # ── DB 업로드 시간 ────────────────────────────────────────────
    try:
        _df_log = run_query(
            "SELECT TOP 1 업로드시간 FROM dbo.lq_업로드로그 "
            "WHERE 테이블명 = 'lq_proc1_1' "
            "ORDER BY 업로드시간 DESC"
        )
        if not _df_log.empty:
            _t = _df_log.iloc[0]["업로드시간"]
            st.markdown(
                f"<div style='font-size:0.75rem; color:#64748B; margin-bottom:0.5rem;'>"
                f"🔄 최근 업로드: {_t} (lq_proc1_1)</div>",
                unsafe_allow_html=True,
            )
    except Exception:
        pass

    # ── KPI 카드 ─────────────────────────────────────────────────
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.metric("전체 건수", f"{summary['total']:,}건")
    with c2:
        delta_pct = f"-{100 - summary['print_rate']:.1f}%p 미출력"
        st.metric("출력", f"{summary['printed']:,}건",
                  delta=delta_pct, delta_color="inverse")
    with c3:
        st.metric("미출력", f"{summary['not_printed']:,}건",
                  delta=f"출력률 {summary['print_rate']}%", delta_color="off")
    with c4:
        st.metric("밀폐작업 건수", f"{summary['confined_total']:,}건")
    with c5:
        st.metric("밀폐 미출력", f"{summary['confined_not_printed']:,}건",
                  delta="위험" if summary['confined_not_printed'] > 0 else "양호",
                  delta_color="inverse" if summary['confined_not_printed'] > 0 else "normal")

    st.markdown('<hr style="border-color:rgba(56,189,248,0.15); margin:0.6rem 0 1rem;">', unsafe_allow_html=True)

    # ── 탭 ───────────────────────────────────────────────────────
    tab_print, tab_confined = st.tabs(["🖨️ 출력 여부 현황", "🔒 밀폐작업 현황"])

    # ════════════════════════════════════════
    #  Tab 1 : 출력 여부 현황
    # ════════════════════════════════════════
    with tab_print:

        # ① 미출력 상세 목록 (최상단)
        # 표시 컬럼: 소속(팀)·시작/종료일시·결재·투입인원 제외
        st.subheader("📋 미출력 상세 목록")
        # 작업취소된 항목은 미출력 목록에서 제외
        _취소 = df.get("결재", pd.Series(dtype=str)) == "작업취소"
        np_df = df[(df["출력여부(Permit No)"] == "미출력") & ~_취소].copy()
        disp_cols = ["호선", "신청부서", "관리자", "구분", "밀폐여부", "작업장소", "작업명"]
        disp_cols = [c for c in disp_cols if c in np_df.columns]
        np_disp = np_df[disp_cols].copy()

        for col in ["밀폐여부"]:
            if col in np_disp.columns:
                np_disp[col] = np_disp[col].map(lambda v: _badge(str(v)) if pd.notna(v) else "")

        st.markdown(_html_table(np_disp.reset_index(drop=True)), unsafe_allow_html=True)
        st.caption(f"총 {len(np_df):,}건")

        st.markdown('<hr style="border-color:rgba(56,189,248,0.10); margin:1rem 0;">', unsafe_allow_html=True)

        # ② 출력 여부 파이차트 + 신청부서별 미출력 건수
        col_pie, col_dept = st.columns([1, 2])

        with col_pie:
            print_counts = df[~_취소]["출력여부(Permit No)"].value_counts()
            fig_pie = _pie_chart(
                labels=print_counts.index.tolist(),
                values=print_counts.values.tolist(),
                title="출력 여부 비율",
                height=300,
            )
            st.plotly_chart(fig_pie, use_container_width=True)

        with col_dept:
            dept_np = (
                df[(df["출력여부(Permit No)"] == "미출력") & ~_취소]
                .groupby("신청부서", as_index=False)
                .size()
                .rename(columns={"size": "미출력 건수"})
                .sort_values("미출력 건수", ascending=False)
            )
            fig_dept = _bar_chart(dept_np, x="신청부서", y="미출력 건수",
                                  title="신청부서별 미출력 건수", height=300)
            fig_dept.update_traces(marker_color="#f97316")
            st.plotly_chart(fig_dept, use_container_width=True)

    # ════════════════════════════════════════
    #  Tab 2 : 밀폐작업 현황
    # ════════════════════════════════════════
    with tab_confined:

        # ① 밀폐작업 상세 목록 (최상단)
        # 표시 컬럼: 소속(팀)·결재 제외
        st.subheader("📋 밀폐작업 상세 목록")
        conf_df = df[df["밀폐여부"] == "밀폐"].copy()
        disp_cols2 = ["호선", "신청부서", "관리자", "구분", "출력여부(Permit No)",
                      "안전N점검", "시작일시", "종료일시", "작업장소", "작업명",
                      "투입인원", "돌관작업사유"]
        disp_cols2 = [c for c in disp_cols2 if c in conf_df.columns]
        conf_disp = conf_df[disp_cols2].copy()

        for col in ["시작일시", "종료일시"]:
            if col in conf_disp.columns:
                conf_disp[col] = conf_disp[col].dt.strftime("%Y-%m-%d %H:%M").fillna("-")

        for col in ["출력여부(Permit No)", "안전N점검"]:
            if col in conf_disp.columns:
                conf_disp[col] = conf_disp[col].map(
                    lambda v: _badge(str(v)) if pd.notna(v) else ""
                )

        conf_disp["돌관작업사유"] = conf_disp.get("돌관작업사유", pd.Series()).fillna("-")

        st.markdown(_html_table(conf_disp.reset_index(drop=True)), unsafe_allow_html=True)
        st.caption(f"총 {len(conf_df):,}건")

        st.markdown('<hr style="border-color:rgba(56,189,248,0.10); margin:1rem 0;">', unsafe_allow_html=True)

        # ② 호선별 밀폐작업 건수 + 밀폐작업 구분별 출력 여부 크로스
        col_vc, col_cross = st.columns(2)

        with col_vc:
            vessel_conf = (
                df[df["밀폐여부"] == "밀폐"]
                .groupby("호선", as_index=False)
                .size()
                .rename(columns={"size": "밀폐작업 건수"})
                .sort_values("호선")
            )
            fig_vc = _bar_chart(vessel_conf, x="호선", y="밀폐작업 건수",
                                title="호선별 밀폐작업 건수", height=330)
            fig_vc.update_traces(marker_color="#f59e0b")
            st.plotly_chart(fig_vc, use_container_width=True)

        with col_cross:
            cross = (
                df[df["밀폐여부"] == "밀폐"]
                .groupby(["구분", "출력여부(Permit No)"], as_index=False)
                .size()
                .rename(columns={"size": "건수"})
            )
            if not cross.empty:
                fig_cross = px.bar(
                    cross, x="구분", y="건수", color="출력여부(Permit No)",
                    color_discrete_map=_COLORS,
                    barmode="group", text_auto=True,
                    height=330,
                )
                fig_cross.update_layout(
                    title=dict(text="밀폐작업 구분별 출력 여부", x=0.5, font=dict(size=14)),
                    legend=dict(orientation="h", y=1.1, font=dict(color="white")),
                    **_PLOTLY_LAYOUT,
                )
                fig_cross.update_traces(textfont_color="white")
                fig_cross.update_xaxes(tickfont=dict(color="#cbd5e1"))
                st.plotly_chart(fig_cross, use_container_width=True)
