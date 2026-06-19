"""
╔══════════════════════════════════════════════════════════════════╗
║  담당자 : ___________  (본인 이름 작성)                          ║
║  항목   : [화면 전용] kpi_4 - 월별 기성 전망                   ║
║  작성일 : ___________                                            ║
╚══════════════════════════════════════════════════════════════════╝

【 🤖 AI 바이브 코딩을 위한 프롬프트 가이드 】
동료분들은 아래 내용을 복사해서 AI에게 그대로 입력하세요!

"이 파일은 Streamlit 앱의 '화면 전용' 모듈이야.
1. 모든 DB 처리·계산 함수는 data/proc_5_data.py 에 있어. 직접 SQL 쓰지 마.
2. 화면에서 쓰는 key 값은 반드시 'kpi4_' 로 시작해야 해.
3. 이 파일에서 수정할 건 UI 배치, 색깔, 텍스트뿐이야. 계산 로직은 건드리지 마.
4. render() 함수 안에 모든 코드를 넣어."
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import date
import io

from data.kpi_4_data import (
    load_data,
    get_col_map,
    compute_kiseong,
    compute_kiseong_by_dept,
)


# ══════════════════════════════════════════════
#  화면 렌더링 메인 함수
# ══════════════════════════════════════════════
def render():

    # ── 다크모드 CSS ──
    st.markdown("""
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

        /* ── 메인 영역 ── */
        h1, h2, h3, h4, h5, h6, p, label { color: #ffffff !important; }

        div[data-baseweb="select"] > div,
        div[data-baseweb="base-input"] > input,
        div[data-baseweb="input"] {
            background-color: #1e293b !important;
            color: #ffffff !important;
            -webkit-text-fill-color: #ffffff !important;
            border-color: #475569 !important;
        }
        span[data-baseweb="tag"] {
            background-color: #3b82f6 !important;
            color: #ffffff !important;
        }
        .kpi-card {
            background: #1e293b;
            border-radius: 12px; padding: 20px 24px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
            border-left: 5px solid #3b82f6; margin-bottom: 10px;
        }
        .kpi-card.green  { border-left-color: #22c55e; }
        .kpi-card.orange { border-left-color: #f97316; }
        .kpi-card.purple { border-left-color: #8b5cf6; }
        .kpi-label { font-size: 13px; color: #cbd5e1 !important; font-weight: 500; margin-bottom: 4px; }
        .kpi-value { font-size: 26px; font-weight: 700; color: #ffffff !important; }
        .kpi-sub   { font-size: 12px; color: #94a3b8 !important; margin-top: 4px; }
        .section-title {
            font-size: 16px; font-weight: 700; color: #ffffff !important;
            border-bottom: 2px solid #3b82f6;
            padding-bottom: 6px; margin-bottom: 16px; margin-top: 20px;
        }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("<hr style='border-color:#475569;'>", unsafe_allow_html=True)

    # ── 데이터 로드 (사이드바 렌더링 전에 수행, 오류 시 사이드바에도 표시) ──
    df_raw  = load_data()
    data_ok = df_raw is not None and not df_raw.empty

    if data_ok:
        all_cols = list(df_raw.columns)
        col_map  = get_col_map(all_cols)

    # ══════════════════════════════════════════
    #  사이드바 — 데이터 오류 여부와 무관하게 항상 렌더링
    # ══════════════════════════════════════════
    with st.sidebar:
        st.markdown("<h3 style='color:#ffffff;'>🔎 조회 조건</h3>", unsafe_allow_html=True)

        if not data_ok:
            st.error("⚠️ 데이터 로드 실패\nDB 연결 상태를 확인해주세요.")
        else:
            import calendar
            today       = date.today()
            month_last  = calendar.monthrange(today.year, today.month)[1]
            query_start = st.date_input("📅 시작일", value=date(today.year, today.month, 1), key="kpi4_start_date")
            query_end   = st.date_input("📅 종료일", value=date(today.year, today.month, month_last), key="kpi4_end_date")

            if query_start > query_end:
                st.error("종료일이 시작일보다 앞설 수 없습니다.")

            dept_vals      = sorted(df_raw[col_map['dept']].dropna().astype(str).unique()) if col_map['dept'] else []
            selected_depts = st.multiselect("🏢 부서 선택 (미선택=전체)", dept_vals, key="kpi4_depts")

            proj_vals      = sorted(df_raw[col_map['project']].dropna().astype(str).unique()) if col_map['project'] else []
            selected_projs = st.multiselect("📋 프로젝트 선택 (미선택=전체)", proj_vals, key="kpi4_projs")

            st.markdown("<hr style='border-color:#1a2a44;margin:8px 0'>", unsafe_allow_html=True)
            if st.button("🔄 필터 초기화", key="kpi4_reset", use_container_width=True):
                for k in ["kpi4_start_date", "kpi4_end_date", "kpi4_depts", "kpi4_projs"]:
                    st.session_state.pop(k, None)
                st.rerun()

    # ── 데이터 없으면 메인 영역에 안내 후 종료 ──
    if not data_ok:
        st.warning("⚠️ 데이터가 없습니다. DB 연결 상태와 테이블명을 확인해주세요.")
        return

    # ── 날짜 범위 오류 시 종료 ──
    if query_start > query_end:
        return

    # ── 필터링 (부서+프로젝트 동시 적용) ──
    df = df_raw.copy()
    if selected_depts and col_map['dept']:
        df = df[df[col_map['dept']].astype(str).isin(selected_depts)]
    if selected_projs and col_map['project']:
        df = df[df[col_map['project']].astype(str).isin(selected_projs)]

    if df.empty:
        st.warning("⚠️ 선택한 조건에 맞는 데이터가 없습니다.")
        return

    # ── 매핑 실패 항목 경고 ──
    failed = [k for k, v in col_map.items() if v is None]
    if failed:
        st.warning(f"⚠️ 컬럼 자동 매핑 실패 항목: {failed}  →  DB 컬럼명을 확인하세요.")

    # ── 기성 계산 ──
    with st.spinner(f"기성 전망 계산 중... ({len(df):,}건)"):
        chart_df = compute_kiseong(df, col_map, query_start, query_end)

    if chart_df.empty:
        st.warning("⚠️ 조회기간 내 워킹데이(월~금)가 없습니다.")
        return

    # ══════════════════════════════════════════
    #  KPI 카드
    # ══════════════════════════════════════════
    total_kiseong  = chart_df['total'].sum()
    total_gongjeong = chart_df['gongjeong'].sum()
    total_wanryo   = chart_df['wanryo'].sum()

    has_data = total_kiseong > 0
    if has_data:
        peak_idx = chart_df['total'].idxmax()
        peak_day = chart_df.loc[peak_idx, 'date']
        peak_val = chart_df.loc[peak_idx, 'total']
    else:
        peak_day = '-'
        peak_val = 0.0

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">📌 기간 기성 전망 합계</div>
            <div class="kpi-value">{total_kiseong:,.1f}</div>
            <div class="kpi-sub">공정진도 + 완료절점 기성</div>
        </div>""", unsafe_allow_html=True)
    with k2:
        st.markdown(f"""
        <div class="kpi-card green">
            <div class="kpi-label">🔄 공정진도 기성</div>
            <div class="kpi-value">{total_gongjeong:,.1f}</div>
            <div class="kpi-sub">자동진도율 × 실행공수 분산</div>
        </div>""", unsafe_allow_html=True)
    with k3:
        st.markdown(f"""
        <div class="kpi-card orange">
            <div class="kpi-label">✅ 완료절점 기성</div>
            <div class="kpi-value">{total_wanryo:,.1f}</div>
            <div class="kpi-sub">조회기간 완료절점 발생분</div>
        </div>""", unsafe_allow_html=True)
    with k4:
        st.markdown(f"""
        <div class="kpi-card purple">
            <div class="kpi-label">📈 일 최대 기성</div>
            <div class="kpi-value">{peak_val:,.1f}</div>
            <div class="kpi-sub">최대 발생일: {peak_day}</div>
        </div>""", unsafe_allow_html=True)

    if not has_data:
        st.warning("⚠️ 조회기간 내 계산된 기성이 없습니다.")
        return

    # ══════════════════════════════════════════
    #  차트
    # ══════════════════════════════════════════
    st.markdown('<div class="section-title">📉 일별 기성 발생 현황</div>', unsafe_allow_html=True)
    date_labels = [d.strftime("%m/%d") for d in chart_df['date']]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=date_labels, y=chart_df['gongjeong'],
        name='공정진도 기성', marker_color='#3b82f6', opacity=0.85,
    ))
    fig.add_trace(go.Bar(
        x=date_labels, y=chart_df['wanryo'],
        name='완료절점 기성', marker_color='#f97316', opacity=0.85,
    ))
    fig.add_trace(go.Scatter(
        x=date_labels, y=chart_df['cumulative'],
        name='누적 기성', mode='lines+markers',
        line=dict(color='#a855f7', width=2.5),
        marker=dict(size=5), yaxis='y2',
    ))
    fig.update_layout(
        barmode='stack',
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#ffffff', family='sans-serif'),
        height=420,
        legend=dict(
            orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1,
            font=dict(color='#ffffff', size=13),
            bgcolor='rgba(30,41,59,0.8)',
            bordercolor='#475569',
            borderwidth=1,
        ),
        xaxis=dict(
            tickangle=-45, gridcolor='#334155',
            tickfont=dict(color='#ffffff'),
            title_font=dict(color='#ffffff'),
        ),
        yaxis=dict(
            title='일별 기성', gridcolor='#334155', tickformat=',',
            tickfont=dict(color='#ffffff'),
            title_font=dict(color='#ffffff'),
        ),
        yaxis2=dict(
            title='누적 기성', overlaying='y', side='right', showgrid=False, tickformat=',',
            tickfont=dict(color='#ffffff'),
            title_font=dict(color='#ffffff'),
        ),
        margin=dict(t=40, b=60, l=60, r=60),
        hovermode='x unified',
    )
    st.plotly_chart(fig, use_container_width=True)


    # ══════════════════════════════════════════
    #  조직별 기간 기성 현황
    # ══════════════════════════════════════════
    st.markdown('<div class="section-title">🏢 조직별 기간 기성 현황</div>', unsafe_allow_html=True)

    dept_df = compute_kiseong_by_dept(df, col_map, query_start, query_end)

    if dept_df.empty:
        st.info("부서 정보가 없어 조직별 현황을 표시할 수 없습니다.")
    else:
        # 합계 행 강조를 위해 마지막 행 여부 판단
        def _highlight_total(row):
            if row['부서'] == '합계':
                return ['background-color:#2d3f5c; font-weight:700; color:#ffffff'] * len(row)
            return ['background-color:#1e293b; color:#ffffff'] * len(row)

        st.dataframe(
            dept_df.style
                .apply(_highlight_total, axis=1)
                .format({
                    '공정진도 기성': '{:,.2f}',
                    '완료절점 기성': '{:,.2f}',
                    '합계':        '{:,.2f}',
                })
                .set_properties(**{'border-color': '#334155'}),
            use_container_width=True,
            hide_index=True,
        )

    # ══════════════════════════════════════════
    #  데이터 테이블 & 엑셀 다운로드
    # ══════════════════════════════════════════
    st.markdown('<div class="section-title">📋 일별 기성 상세</div>', unsafe_allow_html=True)

    table_df = chart_df.copy()
    table_df['date'] = table_df['date'].astype(str)
    table_df.columns = ['날짜', '공정진도 기성', '완료절점 기성', '일 합계', '누적 기성']

    hide_zero = st.checkbox("기성 없는 날짜 숨기기", value=True, key="kpi4_hide_zero")
    if hide_zero:
        table_df = table_df[table_df['일 합계'] > 0]

    st.dataframe(
        table_df.style.format({
            '공정진도 기성': '{:,.2f}',
            '완료절점 기성': '{:,.2f}',
            '일 합계':      '{:,.2f}',
            '누적 기성':    '{:,.2f}',
        }).set_properties(**{
            'background-color': '#1e293b',
            'color':            '#ffffff',
            'border-color':     '#334155',
        }),
        use_container_width=True,
        hide_index=True,
    )

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        table_df.to_excel(writer, index=False, sheet_name='기성전망')

    st.download_button(
        label="⬇️ 엑셀 다운로드",
        data=buffer.getvalue(),
        file_name=f"기성전망_{query_start}_{query_end}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="kpi4_download_btn",
    )