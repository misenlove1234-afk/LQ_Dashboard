import streamlit as st
import pandas as pd
import numpy as np

from data.kpi_1_data import (
    load_data, load_시수_data, load_targets,
    get_filter_options, get_능률_summary, get_실동률_summary,
    get_프로젝트별_상세, week_label
)

# ══════════════════════════════════════════════════════
# 디자인 시스템 (Gemini High-Visibility Theme)
# ══════════════════════════════════════════════════════
C_GEM_BLUE = "#60a5fa"
C_GOOD = "#00e096"
C_BAD = "#ff5252"
C_BG_HDR = "#1e293b"
C_BG_TOTAL = "#1e3a64" 
C_BORDER = "#2d3748"

# ══════════════════════════════════════════════════════
# 유틸리티 & 포매터
# ══════════════════════════════════════════════════════
def _pct(v): return f"{v * 100:.1f}%" if v is not None and not np.isnan(v) else "-"
def _num(v): return f"{v:,.1f}" if v is not None and not np.isnan(v) else "-"

def _get_status_color(val):
    """달성 여부에 따른 텍스트 색상 결정"""
    try:
        v = float(str(val).replace('%', ''))
        return C_GOOD if v >= 100 else C_BAD
    except: return "#e2e8f0"

def _build_css():
    return f"""
<style>
    .stApp {{ background-color: #080d15 !important; }}
    .kpi-table {{
        width: 100%; border-collapse: collapse; font-variant-numeric: tabular-nums;
        margin-bottom: 25px; border-radius: 8px; overflow: hidden;
    }}
    .kpi-table th {{
        background: {C_BG_HDR}; color: #94a3b8; font-size: 11px; font-weight: 700;
        text-align: right; padding: 10px; border-bottom: 2px solid {C_GEM_BLUE};
    }}
    .kpi-table td {{
        padding: 8px 12px; border-bottom: 1px solid {C_BORDER};
        color: #e2e8f0; font-size: 13px; text-align: right;
    }}
    .text-left {{ text-align: left !important; }}
    .row-total td {{ background: {C_BG_TOTAL} !important; font-weight: 800; color: #fff !important; }}
    .row-dept td {{ background: #111b2d; font-weight: 700; color: {C_GEM_BLUE}; }}
    
    /* 달성률 텍스트 강조 (테두리 제거) */
    .ach-text {{ font-weight: 800; font-size: 13px; }}
    
    .detail-section-header {{
        color: {C_GEM_BLUE}; font-size: 16px; font-weight: 800;
        padding: 15px 0; border-bottom: 1px solid {C_BORDER}; margin-top: 30px;
    }}
</style>
"""

# ══════════════════════════════════════════════════════
# KPI 테이블 렌더러
# ══════════════════════════════════════════════════════
def render_kpi_table(df_list, table_type="능률"):
    if table_type == "능률":
        headers = ["소속", "목표", "기성", "투입", "실적", "달성률", "차이"]
        keys = ["능률목표", "기성", "투입", "능률실적", "능률달성(%)", "차이"]
    else:
        headers = ["소속", "목표", "직접", "총발생", "실적", "달성률"]
        keys = ["실동률목표", "직접공수", "총발생", "실동률실적", "실동률달성(%)"]

    html = f"<table class='kpi-table'><thead><tr><th class='text-left'>{headers[0]}</th>"
    for h in headers[1:]: html += f"<th>{h}</th>"
    html += "</tr></thead><tbody>"

    for item in df_list:
        row = item['data']
        css = item.get('css_class', '')
        ach = row.get(keys[4], 0)
        color = _get_status_color(ach)

        html += f"<tr class='{css}'><td class='text-left'>{item['label']}</td>"
        html += f"<td>{_pct(row.get(keys[0]))}</td>"
        html += f"<td>{_num(row.get(keys[1]))}</td>"
        html += f"<td>{_num(row.get(keys[2]))}</td>"
        html += f"<td>{_pct(row.get(keys[3]))}</td>"
        
        # 달성률 (테두리 없이 색상만 적용)
        html += f"<td><span class='ach-text' style='color:{color};'>{ach:.1f}%</span></td>"
        
        if table_type == "능률":
            diff_val = row.get(keys[5], 0)
            html += f"<td style='color:{color}; font-weight:700;'>{_num(diff_val)}</td>"
        
        html += "</tr>"
    html += "</tbody></table>"
    st.markdown(html, unsafe_allow_html=True)

# ══════════════════════════════════════════════════════
# 프로젝트 상세 테이블 스타일 함수
# ══════════════════════════════════════════════════════
def style_project_df(df):
    def apply_color(row):
        try:
            val = float(str(row['능률달성(%)']).replace('%', ''))
            color = C_GOOD if val >= 100 else C_BAD
            # 달성률과 차이 컬럼에만 색상 적용
            styles = ['' for _ in row.index]
            for target in ['능률달성(%)', '차이']:
                if target in row.index:
                    idx = row.index.get_loc(target)
                    styles[idx] = f'color: {color}; font-weight: bold'
            return styles
        except: return ['' for _ in row.index]

    return df.style.apply(apply_color, axis=1)

# ══════════════════════════════════════════════════════
# render() - 메인 진입점
# ══════════════════════════════════════════════════════
def render():
    st.markdown(_build_css(), unsafe_allow_html=True)
    df, df_tgt = load_data(), load_targets()
    df_직접, df_총발생 = load_시수_data()
    opts = get_filter_options(df, df_직접, df_총발생)

    with st.sidebar:
        st.markdown("<h3 style='color:#60a5fa;'>조회 필터</h3>", unsafe_allow_html=True)
        조회유형 = st.radio("기간 구분", ["월별", "주차별"], horizontal=True)
        sel_월 = st.multiselect("월 선택", opts["months"], default=opts["months"][-1:]) if 조회유형 == "월별" else None
        sel_주차 = None
        if 조회유형 == "주차별":
            wlabels = [week_label(w) for w in opts["weeks"]]
            sel_w = st.multiselect("주차 선택", wlabels, default=wlabels[-1:])
            sel_주차 = [dict(zip(wlabels, opts["weeks"]))[l] for l in sel_w]
        월_list = sel_월 if sel_월 else []

    tab_ko, tab_gl = st.tabs(["📊 내국인 실적", "🌏 글로벌 실적"])

    # --- 1. 내국인 탭 ---
    with tab_ko:
        res_n = get_능률_summary(df, df_tgt, sel_월, sel_주차, "내국인")
        res_s = get_실동률_summary(df_직접, df_총발생, df_tgt, sel_월, sel_주차, "내국인", "전체")

        st.subheader("⚡ 내국인 능률 실적")
        rows_n = [{'label': '◆ 선실부 전체', 'data': res_n["선실부"], 'css_class': 'row-total'}]
        for _, r in res_n["과별"].iterrows():
            rows_n.append({'label': f"■ {r['과']}", 'data': r, 'css_class': 'row-dept'})
            for _, br in res_n["직반별"][res_n["직반별"]['과'] == r['과']].iterrows():
                rows_n.append({'label': f"&nbsp;&nbsp;&nbsp;· {br['작업장']}", 'data': br})
        render_kpi_table(rows_n, "능률")

        st.subheader("⏱️ 내국인 실동률 실적")
        rows_s = [{'label': '◆ 선실부 전체', 'data': res_s["선실부"], 'css_class': 'row-total'}]
        for _, r in res_s["과별"].iterrows():
            rows_s.append({'label': f"■ {r['과']}", 'data': r, 'css_class': 'row-dept'})
            for _, br in res_s["직반별"][res_s["직반별"]['과'] == r['과']].iterrows():
                rows_s.append({'label': f"&nbsp;&nbsp;&nbsp;· {br['W/C명']}", 'data': br})
        render_kpi_table(rows_s, "실동률")

        # 프로젝트 상세 구역
        st.markdown("<div class='detail-section-header'>🔍 능률 프로젝트별 상세 분석</div>", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1: target_과 = st.selectbox("과 선택", res_n["과별"]["과"].unique(), key="sel_ko_dept")
        with c2: target_반 = st.selectbox("직반 선택", res_n["직반별"][res_n["직반별"]["과"] == target_과]["작업장"].unique(), key="sel_ko_ban")
        
        df_p = get_프로젝트별_상세(res_n["_원본"], target_반, df_tgt, "내국인", 월_list)
        if not df_p.empty:
            df_p_disp = df_p.copy()
            for col in ['능률목표', '능률실적']: df_p_disp[col] = df_p_disp[col].apply(lambda x: f"{x*100:.1f}%")
            df_p_disp['능률달성(%)'] = df_p_disp['능률달성(%)'].apply(lambda x: f"{x:.1f}%")
            df_p_disp['차이'] = df_p_disp['차이'].apply(lambda x: f"{x:,.1f}")
            st.dataframe(style_project_df(df_p_disp), use_container_width=True, hide_index=True)

    # --- 2. 글로벌 탭 ---
    with tab_gl:
        res_gn = get_능률_summary(df, df_tgt, sel_월, sel_주차, "글로벌")
        res_gs = get_실동률_summary(df_직접, df_총발생, df_tgt, sel_월, sel_주차, "글로벌", "전체")

        st.subheader("⚡ 글로벌 능률 실적")
        rows_gn = [{'label': '◆ 선실부 전체', 'data': res_gn["선실부"], 'css_class': 'row-total'}]
        for _, br in res_gn["직반별"].iterrows():
            rows_gn.append({'label': f"👷 {br['작업장']}", 'data': br})
        render_kpi_table(rows_gn, "능률")

        st.subheader("⏱️ 글로벌 실동률 실적")
        rows_gs = [{'label': '◆ 선실부 전체', 'data': res_gs["선실부"], 'css_class': 'row-total'}]
        for _, br in res_gs["직반별"].iterrows():
            rows_gs.append({'label': f"👷 {br['W/C명']}", 'data': br})
        render_kpi_table(rows_gs, "실동률")

        # 프로젝트 상세 구역
        st.markdown("<div class='detail-section-header'>🔍 글로벌 프로젝트별 상세 분석</div>", unsafe_allow_html=True)
        target_반_gl = st.selectbox("글로벌 직반 선택", res_gn["직반별"]["작업장"].unique(), key="sel_gl_ban")
        df_pg = get_프로젝트별_상세(res_gn["_원본"], target_반_gl, df_tgt, "글로벌", 월_list)
        if not df_pg.empty:
            df_pg_disp = df_pg.copy()
            for col in ['능률목표', '능률실적']: df_pg_disp[col] = df_pg_disp[col].apply(lambda x: f"{x*100:.1f}%")
            df_pg_disp['능률달성(%)'] = df_pg_disp['능률달성(%)'].apply(lambda x: f"{x:.1f}%")
            df_pg_disp['차이'] = df_pg_disp['차이'].apply(lambda x: f"{x:,.1f}")
            st.dataframe(style_project_df(df_pg_disp), use_container_width=True, hide_index=True)