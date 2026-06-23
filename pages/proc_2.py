"""
╔══════════════════════════════════════════════════════════════════╗
║  항목   : [화면 전용] proc_2 - 사곡공장 선실 제작 현황           ║
║  담당자 : ___________                                            ║
║  작성일 : ___________                                            ║
║  설명   : 기존 대시보드 + 엑셀식 간트 편집 컴포넌트              ║
╚══════════════════════════════════════════════════════════════════╝

【 🤖 AI 바이브 코딩 가이드 】
"이 파일은 '화면 렌더링 전용' 파일이야.
1. DB 접속이나 무거운 데이터 연산은 절대 하지 마.
2. 데이터는 반드시 data.proc_2_data 모듈을 import 해서 받아와.
3. 모든 UI 코드는 def render(): 함수 안에 작성해.
4. st.set_page_config()는 쓰면 안 돼.
5. 위젯 key는 반드시 'proc2_' 로 시작."
"""

import os
import io
import json
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import logging
import traceback
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

from data.proc_2_data import (
    load_data,
    get_filtered_projects,
    compute_progress,
    compute_delays,
    get_gantt_data,
    save_gantt_changes,
    check_gantt_permission,
    get_auth_list,
    add_auth_user,
    remove_auth_user,
    add_new_task,
    generate_gantt_print_html,
    load_tapjae_dates,
    # ★ 신규
    add_memo, get_memos, delete_memo, get_memo_photo,
    get_manager, save_manager,
    get_project_date_range,
    get_all_tapjae_status, set_tapjae_status,
)
from utils.access_log import get_client_user


# ══════════════════════════════════════════════
#  선박 배치도 (기존)
# ══════════════════════════════════════════════
LNG_LAYOUT = [
    {'area': 'M110P', 'x': 0,  'y': 11.5, 'w': 1, 'h': 1},
    {'area': 'M110S', 'x': 1,  'y': 11.5, 'w': 1, 'h': 1},
    {'area': 'M120P', 'x': 0,  'y': 10.0, 'w': 1, 'h': 1},
    {'area': 'M120S', 'x': 1,  'y': 10.0, 'w': 1, 'h': 1},
    {'area': 'M210P', 'x': 3,  'y': 11.5, 'w': 1, 'h': 1},
    {'area': 'M210S', 'x': 4,  'y': 11.5, 'w': 1, 'h': 1},
    {'area': 'M220P', 'x': 3,  'y': 10.0, 'w': 1, 'h': 1},
    {'area': 'M220S', 'x': 4,  'y': 10.0, 'w': 1, 'h': 1},
    {'area': 'M310P', 'x': 6,  'y': 10.5, 'w': 1, 'h': 1},
    {'area': 'M310S', 'x': 7,  'y': 10.5, 'w': 1, 'h': 1},
    {'area': 'M410P', 'x': 9,  'y': 10.5, 'w': 1, 'h': 1},
    {'area': 'M410S', 'x': 10, 'y': 10.5, 'w': 1, 'h': 1},
    {'area': 'M900P', 'x': 12, 'y': 10.5, 'w': 1, 'h': 1},
    {'area': 'M510P', 'x': 13, 'y': 10.5, 'w': 1, 'h': 1},
    {'area': 'M510S', 'x': 14, 'y': 10.5, 'w': 1, 'h': 1},
    {'area': 'M900S', 'x': 15, 'y': 10.5, 'w': 1, 'h': 1},
    {'area': 'M610C', 'x': 17, 'y': 10.5, 'w': 1, 'h': 1},
    {'area': 'UPP-DK','x': 4,  'y': 0,   'w': 8, 'h': 1},
    {'area': 'A-DK',  'x': 4,  'y': 1,   'w': 8, 'h': 1},
    {'area': 'B-DK',  'x': 4,  'y': 2,   'w': 8, 'h': 1},
    {'area': 'C-DK',  'x': 4,  'y': 3,   'w': 8, 'h': 1},
    {'area': 'D-DK',  'x': 2,  'y': 4,   'w': 12,'h': 1},
    {'area': 'NAV-DK','x': 6,  'y': 5,   'w': 4, 'h': 1},
]

CONT_LAYOUT = [
    {'area': 'M120P', 'x': 0,  'y': 11.5, 'w': 1, 'h': 1},
    {'area': 'M110P', 'x': 1,  'y': 11.5, 'w': 1, 'h': 1},
    {'area': 'M110S', 'x': 2,  'y': 11.5, 'w': 1, 'h': 1},
    {'area': 'M120S', 'x': 3,  'y': 11.5, 'w': 1, 'h': 1},
    {'area': 'M220P', 'x': 0,  'y': 10.0, 'w': 1, 'h': 1},
    {'area': 'M210P', 'x': 1,  'y': 10.0, 'w': 1, 'h': 1},
    {'area': 'M210S', 'x': 2,  'y': 10.0, 'w': 1, 'h': 1},
    {'area': 'M220S', 'x': 3,  'y': 10.0, 'w': 1, 'h': 1},
    {'area': 'M310P', 'x': 5,  'y': 11.5, 'w': 1, 'h': 1},
    {'area': 'M310S', 'x': 6,  'y': 11.5, 'w': 1, 'h': 1},
    {'area': 'M410P', 'x': 5,  'y': 10.0, 'w': 1, 'h': 1},
    {'area': 'M410S', 'x': 6,  'y': 10.0, 'w': 1, 'h': 1},
    {'area': 'M510P', 'x': 8,  'y': 11.5, 'w': 1, 'h': 1},
    {'area': 'M510S', 'x': 9,  'y': 11.5, 'w': 1, 'h': 1},
    {'area': 'M610P', 'x': 8,  'y': 10.0, 'w': 1, 'h': 1},
    {'area': 'M610S', 'x': 9,  'y': 10.0, 'w': 1, 'h': 1},
    {'area': 'M900P', 'x': 11, 'y': 11.5, 'w': 1, 'h': 1},
    {'area': 'M710P', 'x': 12, 'y': 11.5, 'w': 1, 'h': 1},
    {'area': 'M710S', 'x': 13, 'y': 11.5, 'w': 1, 'h': 1},
    {'area': 'M900S', 'x': 14, 'y': 11.5, 'w': 1, 'h': 1},
    {'area': 'M920P', 'x': 11, 'y': 10.0, 'w': 1, 'h': 1},
    {'area': 'M910P', 'x': 12, 'y': 10.0, 'w': 1, 'h': 1},
    {'area': 'M910S', 'x': 13, 'y': 10.0, 'w': 1, 'h': 1},
    {'area': 'M920S', 'x': 14, 'y': 10.0, 'w': 1, 'h': 1},
    {'area': 'UPP-DK','x': 3,  'y': 0,   'w': 10,'h': 1},
    {'area': 'A-DK',  'x': 3,  'y': 1,   'w': 10,'h': 1},
    {'area': 'B-DK',  'x': 3,  'y': 2,   'w': 10,'h': 1},
    {'area': 'C-DK',  'x': 5,  'y': 3,   'w': 6, 'h': 1},
    {'area': 'D-DK',  'x': 5,  'y': 4,   'w': 6, 'h': 1},
    {'area': 'E-DK',  'x': 5,  'y': 5,   'w': 6, 'h': 1},
    {'area': 'F-DK',  'x': 3,  'y': 6,   'w': 10,'h': 1},
    {'area': 'NAV-DK','x': 6,  'y': 7,   'w': 4, 'h': 1},
]


def _get_area_color(delay: float) -> str:
    if delay <= 0: return "#2ECC71"
    if delay < 7:  return "#F1C40F"
    return "#E74C3C"


def _draw_ship_layout(layout_list, delay_by_area, title, is_split=False):
    shapes, annotations, sx, sy, stext, sc, sdata = [], [], [], [], [], [], []
    xs = [item['x'] for item in layout_list] + [item['x'] + item['w'] for item in layout_list]
    ys = [item['y'] for item in layout_list] + [item['y'] + item['h'] for item in layout_list]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    fs = 8 if is_split else 11

    for item in layout_list:
        area  = item['area']
        match = delay_by_area[delay_by_area['AREA'] == area]
        delay = match['Calculated_Delay'].values[0] if not match.empty else 0
        color = _get_area_color(delay)
        shapes.append(dict(type="rect",
            x0=item['x'], y0=item['y'], x1=item['x']+item['w'], y1=item['y']+item['h'],
            line=dict(color="white", width=1), fillcolor=color))
        annotations.append(dict(x=item['x']+item['w']/2, y=item['y']+item['h']/2,
            text=f"<b>{area}</b><br>({int(delay)})",
            showarrow=False, font=dict(size=fs, color="black")))
        sx.append(item['x']+item['w']/2); sy.append(item['y']+item['h']/2)
        stext.append(f"{area} ({int(delay)})"); sc.append(color); sdata.append(area)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=sx, y=sy, mode='markers',
        marker=dict(size=40, color=sc, opacity=0),
        customdata=sdata, hoverinfo='text', hovertext=stext, name='AREA'))
    fig.update_layout(
        title=dict(text=title, x=0.5, xanchor='center', font=dict(color="white")),
        shapes=shapes, annotations=annotations,
        xaxis=dict(visible=False, range=[min_x-0.2, max_x+0.2], fixedrange=True),
        yaxis=dict(visible=False, range=[min_y-0.2, max_y+0.2], fixedrange=True,
                   scaleanchor="x", scaleratio=1),
        height=350 if is_split else 500, margin=dict(l=0,r=0,t=30,b=0),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        clickmode='event+select', showlegend=False)
    return fig, sdata


# ══════════════════════════════════════════════
#  간트 컨트롤 행 — Streamlit 네이티브 버튼
#  iframe 외부에 배치 → 라이트/다크 테마 영향 없음
# ══════════════════════════════════════════════
def _render_gantt_ctrl_row(ss: dict):
    """간트 차트 위 컨트롤 버튼 — 카테고리별 그룹화"""
    _LBL = '<span style="font-size:0.72rem;color:#94a3b8;">'

    # ── 카테고리 레이블 행 ──
    lc = st.columns([1.25, 2.6, 1.5, 2.3])
    lc[0].markdown(f'{_LBL}📋 표시 설정</span>', unsafe_allow_html=True)
    lc[1].markdown(f'{_LBL}↔ 열 폭</span>',     unsafe_allow_html=True)
    lc[2].markdown(f'{_LBL}🔀 오버랩</span>',    unsafe_allow_html=True)
    lc[3].markdown(f'{_LBL}📍 이동</span>',      unsafe_allow_html=True)

    # ── 버튼 행 ──
    bc = st.columns([1.25, 0.86, 0.86, 0.88, 1.5, 1.15, 1.15])

    # [표시] 실적 보기
    with bc[0]:
        ac_on = ss.get('proc2_gantt_actuals', False)
        if st.button("✅ 실적 ON" if ac_on else "📊 실적보기",
                     key="proc2_btn_actuals", use_container_width=True,
                     type="primary" if ac_on else "secondary"):
            ss['proc2_gantt_actuals'] = not ac_on
            st.rerun()

    # [열 폭] 좁게 / 보통 / 넓게
    with bc[1]:
        w_on = ss.get('proc2_gantt_col_width', 24) == 16
        if st.button("좁게" + (" ✓" if w_on else ""),
                     key="proc2_btn_col_sm", use_container_width=True,
                     type="primary" if w_on else "secondary"):
            ss['proc2_gantt_col_width'] = 16
            st.rerun()
    with bc[2]:
        w_on = ss.get('proc2_gantt_col_width', 24) == 24
        if st.button("보통" + (" ✓" if w_on else ""),
                     key="proc2_btn_col_md", use_container_width=True,
                     type="primary" if w_on else "secondary"):
            ss['proc2_gantt_col_width'] = 24
            st.rerun()
    with bc[3]:
        w_on = ss.get('proc2_gantt_col_width', 24) == 36
        if st.button("넓게" + (" ✓" if w_on else ""),
                     key="proc2_btn_col_lg", use_container_width=True,
                     type="primary" if w_on else "secondary"):
            ss['proc2_gantt_col_width'] = 36
            st.rerun()

    # [오버랩] 모드 전환 (lane: 레인 재배치 / cascade: 날짜 밀기)
    with bc[4]:
        _om = ss.get('proc2_overlap_mode', 'lane')
        if st.button(
            "→ 날짜 밀기" if _om == 'cascade' else "↕ 레인 재배치",
            key="proc2_btn_overlap", use_container_width=True,
            type="primary" if _om == 'cascade' else "secondary",
            help="레인 재배치: 겹치는 작업을 아래 행으로 / 날짜 밀기: 이후 작업을 뒤로 밀기",
        ):
            ss['proc2_overlap_mode'] = 'lane' if _om == 'cascade' else 'cascade'
            st.rerun()

    # [이동] 1주 앞/뒤
    with bc[5]:
        if st.button("◀ 1주전", key="proc2_btn_prev", use_container_width=True):
            ss['proc2_gantt_week_offset'] = ss.get('proc2_gantt_week_offset', 0) - 1
            st.rerun()
    with bc[6]:
        if st.button("1주후 ▶", key="proc2_btn_next", use_container_width=True):
            ss['proc2_gantt_week_offset'] = ss.get('proc2_gantt_week_offset', 0) + 1
            st.rerun()


# ══════════════════════════════════════════════
#  ★ 간트 HTML 컴포넌트 렌더링 (신규)
# ══════════════════════════════════════════════
def _render_gantt_component(tasks: list, is_editable: bool = False,
                             current_user: str = "", height: int = 900,
                             row_mode: str = "area",
                             wrap_max_height: str = "520px",
                             template: str = "gantt_editor.html",
                             show_hidden: bool = False,
                             col_width: int = 24,
                             light_theme: bool = False,
                             show_actuals: bool = False,
                             week_offset: int = 0,
                             overlap_mode: str = "lane"):
    """간트 HTML 템플릿에 데이터를 주입해 컴포넌트로 렌더링
    row_mode: 'area' (구역별) | 'ship' (호선별)
    wrap_max_height: .gantt-wrap 영역 최대 높이 CSS 값 (기본 520px, 최대화 시 viewport 기준)
    template: 사용할 HTML 파일명 (기본 gantt_editor.html, 공정회의 모드는 gantt_meeting.html)
    show_hidden/col_width/light_theme/show_actuals/week_offset: Streamlit 컨트롤 상태
    """
    html_path = Path(__file__).parent.parent / "assets" / template
    if not html_path.exists():
        st.error(f"❌ 간트 HTML 템플릿을 찾을 수 없습니다: {html_path}")
        return

    html_template = html_path.read_text(encoding='utf-8')
    today_str     = datetime.now().strftime('%Y-%m-%d')

    # Python → JavaScript 데이터 주입
    html_content = (
        html_template
        .replace('/*__GANTT_DATA__*/[]',   json.dumps(tasks, ensure_ascii=False))
        .replace('__TODAY_DATE__',          today_str)
        .replace('__IS_EDITABLE__',         'true' if is_editable else 'false')
        .replace('__CURRENT_USER__',        current_user)
        .replace('__ROW_MODE__',            row_mode)
        .replace('__INIT_SHOW_HIDDEN__',    'true' if show_hidden else 'false')
        .replace('__INIT_COL_WIDTH__',      str(col_width))
        .replace('__INIT_LIGHT_THEME__',    'true' if light_theme else 'false')
        .replace('__INIT_SHOW_ACTUALS__',   'true' if show_actuals else 'false')
        .replace('__INIT_WEEK_OFFSET__',    str(week_offset))
        .replace('__INIT_OVERLAP_MODE__',   overlap_mode)
    )
    # gantt-wrap 최대 높이 동적 치환 (템플릿 하드코딩 520px → 파라미터)
    if wrap_max_height != "520px":
        html_content = html_content.replace("max-height: 520px;", f"max-height: {wrap_max_height};")
    components.html(html_content, height=height, scrolling=True)


# ══════════════════════════════════════════════
#  탭 상수
# ══════════════════════════════════════════════
TAB_OPTIONS = ["종합 공정 현황", "구역별 상세 현황", "기준정보"]


# ══════════════════════════════════════════════
#  PDF 일괄 출력 다이얼로그 — 호선/STG/기간/공종 선택 → 인쇄 페이지 렌더
# ══════════════════════════════════════════════
@st.dialog("📄 간트 PDF 일괄 출력", width="large")
def _proc2_pdf_dialog(df_raw,
                       default_ships, default_stgs,
                       default_start, default_end,
                       default_gjs):
    st.caption(
        "호선 × STG 조합별로 1페이지씩 A3 가로로 생성되며, **화면 간트와 동일한 스타일**로 출력됩니다. "
        "STG 일정이 없는 조합은 자동 생략됩니다."
    )

    all_ships = sorted(df_raw['프로젝트'].dropna().unique().tolist())
    all_stgs  = sorted(df_raw['STG'].astype(str).unique().tolist())
    all_gjs   = sorted(df_raw['공종'].dropna().unique().tolist())

    sel_ships = st.multiselect(
        "호선 선택", all_ships,
        default=[s for s in default_ships if s in all_ships],
        key="proc2_pdf_ships",
        help="기본값은 사이드바에서 표시 중인 진행 호선",
    )
    sel_stgs = st.multiselect(
        "STG (미선택 시 전체)", all_stgs,
        default=[s for s in default_stgs if s in all_stgs],
        key="proc2_pdf_stgs",
    )
    sel_dates = st.date_input(
        "기간", value=[default_start, default_end], key="proc2_pdf_date",
    )
    sel_gjs = st.multiselect(
        "공종 (미선택 시 전체)", all_gjs,
        default=[g for g in default_gjs if g in all_gjs],
        key="proc2_pdf_gjs",
    )

    if isinstance(sel_dates, (list, tuple)) and len(sel_dates) == 2:
        d_start, d_end = sel_dates
    else:
        d_start = d_end = sel_dates if not isinstance(sel_dates, (list, tuple)) else sel_dates[0]

    st.divider()

    if sel_ships:
        _est_df = df_raw[df_raw['프로젝트'].isin(sel_ships)]
        if sel_stgs:
            _est_df = _est_df[_est_df['STG'].astype(str).isin([str(s) for s in sel_stgs])]
        page_count = (
            _est_df.groupby('프로젝트')['STG']
            .apply(lambda s: s.astype(str).nunique()).sum()
        )
        st.caption(f"📄 예상 페이지 수: 최대 **{int(page_count)}** 쪽")
    else:
        st.warning("⚠️ 호선을 1개 이상 선택해 주세요.")
        return

    if st.button("🛠 인쇄 페이지 생성", type="primary",
                 use_container_width=True, key="proc2_pdf_gen"):
        try:
            html = generate_gantt_print_html(
                df_raw,
                ships=sel_ships,
                stages=sel_stgs if sel_stgs else None,
                date_start=d_start, date_end=d_end,
                gongjongs=sel_gjs if sel_gjs else None,
                # row_mode 생략 → 공종이 1개면 자동으로 'ship'(한 장에 통합)
            )
            st.session_state["proc2_pdf_html"] = html
        except Exception as e:
            import logging, traceback
            logging.getLogger(__name__).error(
                "인쇄 HTML 생성 실패: %s\n%s", e, traceback.format_exc()
            )
            st.error("생성 중 오류가 발생했습니다. 관리자에게 문의해 주세요.")
            st.session_state.pop("proc2_pdf_html", None)

    html_ = st.session_state.get("proc2_pdf_html")
    if html_:
        st.info(
            "👇 아래 영역 상단 **🖨 브라우저 인쇄** 버튼 → **대상: PDF로 저장** 선택. "
            "배경 그래픽 옵션을 켜야 간트 색상이 보존됩니다."
        )
        components.html(html_, height=720, scrolling=True)


# ══════════════════════════════════════════════
#  메인 렌더링 함수
# ══════════════════════════════════════════════
def render():
    # ── CSS (기존) ───────────────────────────────
    st.markdown("""
    <style>
    [data-testid="stSidebar"] { background-color: #0d1b2e !important; }
    [data-testid="stSidebar"] * { color: #ffffff !important; }
    [data-testid="stSidebar"] .stButton button {
        background-color: #1d4ed8 !important; border: none !important; color: #ffffff !important;
    }
    [data-testid="stSidebar"] .stButton button:hover { background-color: #2563eb !important; }
    [data-testid="stSidebar"] div[data-baseweb="select"] > div,
    [data-testid="stSidebar"] div[data-baseweb="base-input"] > input {
        background-color: #1e293b !important; color: #ffffff !important;
        -webkit-text-fill-color: #ffffff !important; border-color: #334155 !important;
    }
    [data-testid="stMetricValue"] { font-size:1.5rem; color:#e2e8f0; }
    [data-testid="stMetricLabel"] { font-size:0.85rem; color:#94a3b8; }
    [data-testid="metric-container"] {
        padding:0.5rem 0.8rem; background:rgba(15,35,65,0.6);
        border-radius:8px; border:1px solid rgba(56,189,248,0.2);
    }
    .stTabs [data-baseweb="tab-list"] { background-color:transparent; }
    .stTabs [data-baseweb="tab"]      { color:#94a3b8; }
    .stTabs [aria-selected="true"]    { color:#38bdf8 !important; }
    /* radio를 탭 스타일로 표시 (rerun 시 탭 유지 목적) */
    section[data-testid="stMain"] div[data-testid="stRadio"] > div[role="radiogroup"] {
        display: flex; flex-direction: row; gap: 0;
        border-bottom: 2px solid rgba(56,189,248,0.2);
        margin-bottom: 1rem;
    }
    section[data-testid="stMain"] div[data-testid="stRadio"] > div[role="radiogroup"] > label {
        padding: 0.6rem 1.4rem; margin: 0 !important;
        background: transparent; cursor: pointer;
        border-bottom: 3px solid transparent;
        color: #94a3b8; margin-bottom: -2px !important;
        font-size: 0.95rem;
    }
    section[data-testid="stMain"] div[data-testid="stRadio"] > div[role="radiogroup"] > label:has(input:checked) {
        color: #38bdf8 !important; border-bottom: 3px solid #38bdf8;
        font-weight: 600;
    }
    section[data-testid="stMain"] div[data-testid="stRadio"] > div[role="radiogroup"] > label > div:first-child {
        display: none;
    }
    h3, h5 { color:#ffffff !important; }
    p, label { color:#ffffff !important; }
    .dark-html-table { width:100%; border-collapse:collapse; font-size:0.85rem; }
    .dark-html-table th {
        background-color:#0a1628 !important; color:#7dd3fc !important;
        padding:0.5rem 0.7rem; border-bottom:1px solid rgba(56,189,248,0.3);
        text-align:left; font-weight:600; position:sticky; top:0; z-index:1;
    }
    .dark-html-table td {
        background-color:#0d1f3c !important; color:#e2e8f0 !important;
        padding:0.45rem 0.7rem; border-bottom:1px solid rgba(56,189,248,0.08);
    }
    .dark-html-table tr:hover td { background-color:rgba(56,189,248,0.15) !important; }
    .dark-html-table-wrap {
        border:1px solid rgba(56,189,248,0.2); border-radius:8px;
        overflow:auto; max-height:400px; background-color:#0d1f3c;
    }
    </style>
    """, unsafe_allow_html=True)

    # ── 데이터 로드 ──────────────────────────────
    try:
        df_raw = load_data()
    except Exception as e:
        logger.error("공정 데이터 로드 실패: %s\n%s", e, traceback.format_exc())
        st.error("데이터 로드에 실패했습니다. 관리자에게 문의해 주세요.")
        return

    today = pd.Timestamp(datetime.now().date())
    ADMIN_PASSWORD  = os.getenv("ADMIN_PASSWORD", "admin1234")
    current_user    = get_client_user()
    is_editable     = check_gantt_permission(current_user)

    # ── 사이드바 (기존) ──────────────────────────
    with st.sidebar:
        st.markdown("<h3 style='color:#ffffff;'>🔍 조회 조건 설정</h3>", unsafe_allow_html=True)

        valid_dates = pd.concat([
            df_raw.get('초기_계획_A_착수', pd.Series()),
            df_raw.get('변경_계획_B_완료', pd.Series())
        ]).dropna()
        if not valid_dates.empty:
            min_d, max_d = valid_dates.min().date(), valid_dates.max().date()
        else:
            from datetime import date as _date
            min_d = max_d = _date.today()

        start_date, end_date = st.date_input("1. 조회 기간", [min_d, max_d], key="proc2_date")
        use_all_period = st.checkbox("전체 기간", value=False, key="proc2_all_period")

        # 선종
        st.write("2. 선종 선택")
        ship_types_filter = []
        if '선종' in df_raw.columns:
            all_ship_types = sorted(df_raw['선종'].dropna().unique())
            cols_ship = st.columns(min(3, len(all_ship_types)))
            for idx, st_val in enumerate(all_ship_types):
                with cols_ship[idx % len(cols_ship)]:
                    if st.checkbox(str(st_val), value=False, key=f"proc2_ship_{st_val}"):
                        ship_types_filter.append(st_val)
            if not ship_types_filter:
                ship_types_filter = list(all_ship_types)

        # STG
        st.write("3. STG (미선택 시 전체)")
        if 'STG' in df_raw.columns:
            all_stgs = sorted(df_raw['STG'].astype(str).unique())
            selected_stgs = []
            cols_stg = st.columns(min(4, len(all_stgs)))
            for idx, stg in enumerate(all_stgs):
                with cols_stg[idx % len(cols_stg)]:
                    if st.checkbox(stg, value=False, key=f"proc2_stg_{stg}"):
                        selected_stgs.append(stg)
            stgs_filter = selected_stgs if selected_stgs else all_stgs
        else:
            all_stgs = []
            stgs_filter = []

        # 완료 포함
        st.write("4. 프로젝트 조회 기준")
        include_completed = st.checkbox("완료 프로젝트 포함", value=False, key="proc2_include_comp")

        all_projects = get_filtered_projects(
            df_raw, start_date, end_date, stgs_filter, include_completed, use_all_period
        )

        selected_projects = st.multiselect(
            "5. 프로젝트 (미선택 시 전체)", all_projects,
            default=[],
            key="proc2_proj")
        projects_filter = selected_projects if selected_projects else all_projects

        all_gongjongs = sorted(df_raw['공종'].dropna().unique())
        selected_gongjongs = st.multiselect(
            "6. 공종 (미선택 시 전체)", all_gongjongs, default=[], key="proc2_gongjong")
        gongjongs_filter = selected_gongjongs if selected_gongjongs else all_gongjongs

        # 차트 조회 기준
        st.write("7. 차트 조회 기준")
        view_options   = ["초기 계획", "변경 계획", "실적"]
        selected_views = []
        cols_view      = st.columns(3)
        for idx, view in enumerate(view_options):
            with cols_view[idx]:
                if st.checkbox(view, value=True, key=f"proc2_view_{view}"):
                    selected_views.append(view)

        # 관리자
        st.divider()
        st.write("8. 🔐 관리자")
        admin_input = st.text_input("비밀번호", type="password", key="proc2_admin_pw")
        if admin_input == ADMIN_PASSWORD:
            st.session_state["is_admin"] = True
            st.success("✅ 관리자 모드")
        elif admin_input:
            st.session_state["is_admin"] = False
            st.error("❌ 비밀번호 오류")
        else:
            st.session_state.setdefault("is_admin", False)

        st.divider()
        # PDF 일괄 출력 — 진행 중 호선(현재 화면 필터 기준)을 기본값으로 다이얼로그 오픈
        if st.button("📄 PDF 일괄 출력", key="proc2_pdf_open", use_container_width=True):
            # 버튼 클릭마다 기본 기간을 '해당월 1일 ~ +3개월 말일'로 초기화
            _pdf_ps = pd.Timestamp.now().normalize().replace(day=1)
            _pdf_pe = (_pdf_ps + pd.DateOffset(months=3)) - pd.Timedelta(days=1)
            _pdf_ps_d, _pdf_pe_d = _pdf_ps.date(), _pdf_pe.date()
            st.session_state["proc2_pdf_date"] = (_pdf_ps_d, _pdf_pe_d)
            _proc2_pdf_dialog(
                df_raw,
                default_ships=(selected_projects if selected_projects else all_projects),
                default_stgs=(selected_stgs if selected_stgs else []),
                default_start=_pdf_ps_d, default_end=_pdf_pe_d,
                default_gjs=(selected_gongjongs if selected_gongjongs else []),
            )

        st.divider()
        if st.button("🔄 필터 초기화", key="proc2_reset", use_container_width=True):
            static_keys = ["proc2_date", "proc2_all_period", "proc2_include_comp",
                           "proc2_proj", "proc2_gongjong", "proc2_admin_pw",
                           "proc2_mtg_proj_idx", "proc2_mtg_stg_sel", "proc2_mtg_last_proj"]
            dynamic_prefixes = ("proc2_ship_", "proc2_stg_", "proc2_view_", "proc2_mtg_")
            for k in list(st.session_state.keys()):
                if k in static_keys or k.startswith(dynamic_prefixes):
                    st.session_state.pop(k, None)
            st.rerun()

    # ── 데이터 필터링 ────────────────────────────
    if '선종' in df_raw.columns and ship_types_filter:
        filtered_df = df_raw[
            df_raw['선종'].isin(ship_types_filter) &
            df_raw['프로젝트'].isin(projects_filter) &
            df_raw['STG'].astype(str).isin(stgs_filter) &
            df_raw['공종'].isin(gongjongs_filter)
        ].copy()
    else:
        filtered_df = df_raw[
            df_raw['프로젝트'].isin(projects_filter) &
            df_raw['STG'].astype(str).isin(stgs_filter) &
            df_raw['공종'].isin(gongjongs_filter)
        ].copy()

    # ── 데이터 연산 ──────────────────────────────
    progress_result = compute_progress(filtered_df, start_date, end_date)
    delay_result    = compute_delays(filtered_df)

    progress_df       = progress_result['progress_df']
    curr_prog_a       = progress_result['curr_prog_a']
    curr_prog_b       = progress_result['curr_prog_b']
    curr_prog_act     = progress_result['curr_prog_act']
    adherence_rate    = progress_result['adherence_rate']
    delay_by_gongjong = delay_result['delay_by_gongjong']
    delay_by_area     = delay_result['delay_by_area']
    filtered_df       = delay_result['filtered_with_delay']

    # ── 간트 기준일 결정 ─────────────────────────
    # 사이드바 '차트 조회 기준' 다중선택 중 우선순위 1개만 간트에 적용 (변경 > 초기 > 실적).
    # 아무것도 선택되지 않은 경우 기본값 '변경 계획'.
    _gantt_basis_priority = ["변경 계획", "초기 계획", "실적"]
    gantt_basis = next(
        (b for b in _gantt_basis_priority if b in selected_views),
        "변경 계획",
    )
    # 편집은 변경 계획 표시 중일 때만 허용 (저장 로직이 B 컬럼만 갱신하기 때문)
    effective_editable = is_editable and (gantt_basis == "변경 계획")

    # ── 간트 컨트롤 세션 상태 초기화 ─────────────────
    _ss = st.session_state
    if 'proc2_gantt_col_width'   not in _ss: _ss['proc2_gantt_col_width']   = 24
    if 'proc2_gantt_actuals'     not in _ss: _ss['proc2_gantt_actuals']     = False
    if 'proc2_gantt_week_offset' not in _ss: _ss['proc2_gantt_week_offset'] = 0
    if 'proc2_overlap_mode'      not in _ss: _ss['proc2_overlap_mode']      = 'lane'

    # ══════════════════════════════════════════════
    #  간트 최대화 모드 — 사이드바는 유지, 메인 영역만 풀 너비
    # ══════════════════════════════════════════════
    if st.session_state.get("proc2_gantt_maximized", False):
        # 메인 영역 풀 너비 + 여백 최소화 + iframe을 viewport 높이에 맞춤
        st.markdown("""
        <style>
        section[data-testid="stMain"] .block-container {
            max-width: 100% !important;
            padding-left: 1rem !important;
            padding-right: 1rem !important;
            padding-top: 0.5rem !important;
            padding-bottom: 0.25rem !important;
        }
        /* 간트 iframe을 화면 높이에 맞춤 (header/버튼 영역 제외) */
        section[data-testid="stMain"] iframe {
            height: calc(100vh - 150px) !important;
            min-height: 500px !important;
        }
        </style>
        """, unsafe_allow_html=True)

        col_hdr, col_btn = st.columns([6, 1])
        with col_hdr:
            perm_icon = "✅" if effective_editable else "🔒"
            if effective_editable:
                perm_text = "편집 가능"
            elif is_editable and gantt_basis != "변경 계획":
                perm_text = f"읽기 전용 ({gantt_basis} 보기 — 편집은 변경 계획 모드에서만)"
            else:
                perm_text = "읽기 전용"
            st.markdown(f"##### 📅 공정 타임라인 — {gantt_basis} (최대화)")
            st.caption(f"{perm_icon} **접속자:** `{current_user}` &nbsp;|&nbsp; {perm_text}")
        with col_btn:
            if st.button("↙️ 원래 크기", key="proc2_gantt_restore", use_container_width=True):
                st.session_state["proc2_gantt_maximized"] = False
                # 복귀 시 탭을 '구역별 상세 현황'으로 유지
                st.session_state["proc2_tab_choice"] = TAB_OPTIONS[1]
                st.rerun()

        # ── 간트 컨트롤 행 (Streamlit 네이티브) ──
        _render_gantt_ctrl_row(_ss)

        has_filter = bool(selected_projects) or bool(selected_gongjongs)
        if not has_filter:
            st.info("💡 사이드바에서 **호선** 또는 **공종**을 먼저 선택하세요.")
        else:
            row_mode = "ship" if (bool(selected_gongjongs) and not selected_projects) else "area"
            gantt_tasks = get_gantt_data(filtered_df, basis=gantt_basis)
            if not gantt_tasks:
                st.warning(f"⚠️ 선택한 조건에 해당하는 작업이 없습니다. ({gantt_basis} 기준 일자가 있는 행만 표시)")
            else:
                _render_gantt_component(gantt_tasks, is_editable=effective_editable,
                                        current_user=current_user, height=1200,
                                        row_mode=row_mode,
                                        wrap_max_height="calc(100vh - 140px)",
                                        show_hidden=False,
                                        col_width=_ss['proc2_gantt_col_width'],
                                        light_theme=False,
                                        show_actuals=_ss['proc2_gantt_actuals'],
                                        week_offset=_ss['proc2_gantt_week_offset'],
                                        overlap_mode=_ss.get('proc2_overlap_mode', 'lane'))
        return

    # ── 상단 정보 ──────────────────────────────────
    disp_proj = ', '.join(selected_projects) if selected_projects else "전체"
    st.markdown(
        f'<p style="color:#94a3b8; font-size:1rem; margin-bottom:1rem;">'
        f'<strong>조회 기간:</strong> {start_date} ~ {end_date} &nbsp;|&nbsp; '
        f'<strong>선택된 프로젝트:</strong> {disp_proj}</p>',
        unsafe_allow_html=True
    )

    # ── KPI 지표 ──────────────────────────────────
    kpi_cols = st.columns(4)
    with kpi_cols[0]: st.metric("초기 계획 진도율",  f"{curr_prog_a:.2f}%")
    with kpi_cols[1]: st.metric("변경 계획 진도율",  f"{curr_prog_b:.2f}%")
    with kpi_cols[2]:
        delta = curr_prog_act - curr_prog_b
        st.metric("실적 진도율", f"{curr_prog_act:.2f}%", f"{delta:.2f}% (vs 변경)")
    with kpi_cols[3]: st.metric("공정 준수율", f"{adherence_rate:.2f}%")

    st.markdown('<hr style="border-color:rgba(56,189,248,0.15);">', unsafe_allow_html=True)

    # st.tabs()는 rerun 시 선택이 초기화되므로 radio + session_state로 대체.
    # 위젯을 조건부로 렌더링하면 widget key가 정리될 수 있으므로 위젯 key와
    # 영속 key(proc2_tab_choice)를 분리한다.
    def _sync_proc2_tab():
        st.session_state["proc2_tab_choice"] = st.session_state["proc2_tab_widget"]

    try:
        _tab_idx = TAB_OPTIONS.index(st.session_state.get("proc2_tab_choice", TAB_OPTIONS[0]))
    except ValueError:
        _tab_idx = 0

    tab_choice = st.radio(
        "탭 선택",
        TAB_OPTIONS,
        index=_tab_idx,
        horizontal=True,
        label_visibility="collapsed",
        key="proc2_tab_widget",
        on_change=_sync_proc2_tab,
    )
    tab_options = TAB_OPTIONS  # 아래 기존 코드 호환용

    # ══════════════════════════════════════════════
    #  Tab 1: 종합 공정 현황 (기존)
    # ══════════════════════════════════════════════
    if tab_choice == tab_options[0]:
        col_chart1, col_chart2 = st.columns([2, 1])
        with col_chart1:
            st.subheader("📈 공정 진도율 추이 (S-Curve)")
            fig_s = go.Figure()
            if not selected_views:
                fig_s.add_annotation(text="사이드바에서 '차트 조회 기준'을 선택하세요.",
                    showarrow=False, font=dict(color="white"))
            else:
                color_map = {"초기 계획": ('#94a3b8', 'dot'),
                             "변경 계획": ('#38bdf8', 'solid'),
                             "실적":     ('#f43f5e', 'solid')}
                for view in selected_views:
                    c, dash = color_map[view]
                    fig_s.add_trace(go.Scatter(
                        x=progress_df.index, y=progress_df[view],
                        mode='lines', name=view,
                        line=dict(color=c, dash=dash, width=3 if view=="실적" else 2)))

                # ── 호선별 탑재착수 마커 (노란 별) ───────────────
                try:
                    tapjae_df = load_tapjae_dates()
                    if projects_filter:
                        tapjae_df = tapjae_df[tapjae_df['프로젝트'].isin(projects_filter)]
                    if not tapjae_df.empty and not progress_df.empty:
                        mx, my, mtxt, mhover = [], [], [], []
                        for _, r in tapjae_df.iterrows():
                            d = r['탑재착수']
                            # 차트 X 범위 밖이면 생략
                            if d < progress_df.index.min() or d > progress_df.index.max():
                                continue
                            # 변경 계획 곡선 Y값을 기준 (없으면 0)
                            try:
                                y_col = "변경 계획" if "변경 계획" in progress_df.columns else progress_df.columns[0]
                                y_val = float(progress_df.loc[progress_df.index.asof(d), y_col])
                            except Exception:
                                y_val = 0.0
                            mx.append(d); my.append(y_val)
                            mtxt.append(str(r['프로젝트']))
                            mhover.append(f"{r['프로젝트']}<br>탑재착수 {d.strftime('%Y-%m-%d')}<br>변경 계획 {y_val:.2f}%")
                        if mx:
                            fig_s.add_trace(go.Scatter(
                                x=mx, y=my, mode='markers+text', name='탑재착수',
                                marker=dict(symbol='star', size=14, color='#fbbf24',
                                            line=dict(color='#92400e', width=1)),
                                text=mtxt, textposition='top center',
                                textfont=dict(color='#fbbf24', size=10),
                                hovertext=mhover, hoverinfo='text',
                            ))
                except Exception:
                    import logging, traceback
                    logging.getLogger(__name__).error(
                        "탑재 마커 렌더 실패:\n%s", traceback.format_exc()
                    )

            fig_s.update_layout(
                height=400, xaxis_title="날짜", yaxis_title="누적 진도율 (%)",
                hovermode="x unified", legend=dict(orientation="h", y=1.1),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="white"))
            fig_s.update_xaxes(showgrid=True, gridcolor='rgba(255,255,255,0.1)')
            fig_s.update_yaxes(showgrid=True, gridcolor='rgba(255,255,255,0.1)')
            st.plotly_chart(fig_s, use_container_width=True)

        selected_craft_filter = None
        with col_chart2:
            st.subheader("📊 공종별 누적 지연일수")
            st.caption("막대를 **클릭**하면 아래 리스트가 필터링됩니다.")
            if not delay_by_gongjong.empty:
                colors = delay_by_gongjong['누적 지연일수'].apply(
                    lambda x: '#f43f5e' if x > 0 else '#38bdf8')
                fig_bar = px.bar(delay_by_gongjong, x='공종', y='누적 지연일수', text_auto=True)
                fig_bar.update_traces(marker_color=colors, textfont_color="white")
                fig_bar.update_layout(
                    height=400, xaxis_title=None, showlegend=False,
                    clickmode='event+select',
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="white"))
                fig_bar.update_yaxes(showgrid=True, gridcolor='rgba(255,255,255,0.1)')
                event = st.plotly_chart(fig_bar, use_container_width=True,
                    on_select="rerun", selection_mode="points", key="proc2_craft_bar")
                if event and event['selection']['points']:
                    selected_craft_filter = delay_by_gongjong.iloc[
                        event['selection']['points'][0]['point_index']]['공종']
            else:
                st.info("데이터가 없습니다.")

        st.markdown('<hr style="border-color:rgba(56,189,248,0.15);">', unsafe_allow_html=True)

        # 프로젝트별 진도율
        st.subheader("🎯 프로젝트별 진도율 현황")
        project_progress = []
        for project in projects_filter:
            proj_df = filtered_df[filtered_df['프로젝트'] == project]
            tw = proj_df['점유율'].sum()
            if tw > 0:
                project_progress.append({
                    '프로젝트': project,
                    '계획 진도율': (proj_df[proj_df['변경_계획_B_완료'] <= today]['점유율'].sum() / tw) * 100,
                    '실적 진도율': (proj_df[proj_df['실적_C_종료'].notna()]['점유율'].sum() / tw) * 100,
                })
        if project_progress:
            ppdf = pd.DataFrame(project_progress).sort_values('계획 진도율').reset_index(drop=True)
            fig_proj = go.Figure()
            fig_proj.add_trace(go.Bar(name='계획 진도율',
                x=ppdf['프로젝트'], y=ppdf['계획 진도율'],
                marker=dict(color='rgba(56,189,248,0.7)'),
                text=ppdf['계획 진도율'].round(1), textposition='outside',
                texttemplate='%{text}%', textfont=dict(size=14, color='white')))
            fig_proj.add_trace(go.Scatter(name='실적 진도율',
                x=ppdf['프로젝트'], y=ppdf['실적 진도율'],
                mode='lines+markers+text', line=dict(color='#f43f5e', width=3),
                marker=dict(size=12), text=ppdf['실적 진도율'].round(1),
                textposition='top center', texttemplate='%{text}%',
                textfont=dict(size=14, color='#fca5a5')))
            fig_proj.update_layout(
                height=450, xaxis_title="프로젝트", yaxis_title="진도율 (%)",
                legend=dict(orientation="h", y=1.15, x=0.5, xanchor='center'),
                yaxis=dict(range=[0, 110]), hovermode='x unified',
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="white"))
            st.plotly_chart(fig_proj, use_container_width=True)
        else:
            st.info("프로젝트 데이터가 없습니다.")

        st.markdown('<hr style="border-color:rgba(56,189,248,0.15);">', unsafe_allow_html=True)

        # 지연/검사 리스트 (세로 와이드 레이아웃)
        list_df = filtered_df[filtered_df['공종'] == selected_craft_filter].copy() \
                  if selected_craft_filter else filtered_df.copy()
        suffix  = f" - {selected_craft_filter}" if selected_craft_filter else " (전체)"

        # ── 금주 주요 검사 일정 (상단, 와이드) ──
        st.subheader(f"📅 금주 주요 검사 일정{suffix}")
        insp_df = list_df[
            list_df['작업내용'].str.contains('선각검사|B/P 검사', na=False) &
            (list_df['변경_계획_B_완료'] >= today) &
            (list_df['변경_계획_B_완료'] <= today + timedelta(days=7))
        ][['프로젝트','STG','대분류','작업내용','변경_계획_B_완료']].sort_values('변경_계획_B_완료').copy()
        insp_df['변경_계획_B_완료'] = insp_df['변경_계획_B_완료'].dt.strftime('%Y-%m-%d')
        insp_df.rename(columns={'변경_계획_B_완료':'검사 예정일','대분류':'AREA'}, inplace=True)
        if not insp_df.empty:
            st.markdown(
                f'<div class="dark-html-table-wrap">'
                f'{insp_df.to_html(index=False, classes="dark-html-table", border=0)}'
                f'</div>', unsafe_allow_html=True)
        else:
            st.info("📭 금주 예정된 검사가 없습니다.")

        st.markdown('<hr style="border-color:rgba(56,189,248,0.15); margin:1.2rem 0;">',
                    unsafe_allow_html=True)

        # ── 공정 지연 리스트 (하단, 와이드) ──
        st.subheader(f"⚠️ 공정 지연 리스트{suffix}")
        delayed_df = list_df[
            ((list_df['변경_계획_B_착수'] < today) & list_df['실적_C_착수'].isna()) |
            ((list_df['변경_계획_B_완료'] < today) & list_df['실적_C_종료'].isna())
        ].copy()
        if not delayed_df.empty:
            def _status(row):
                if pd.isna(row['실적_C_종료']) and row['변경_계획_B_완료'] < today:
                    return "완료 지연", (today - row['변경_계획_B_완료']).days
                if pd.isna(row['실적_C_착수']) and row['변경_계획_B_착수'] < today:
                    return "착수 지연", (today - row['변경_계획_B_착수']).days
                return "-", 0
            delayed_df[['상태','지연일수']] = delayed_df.apply(
                lambda x: pd.Series(_status(x)), axis=1)
            show_cols = ['프로젝트','STG','대분류','공종','작업내용','상태','지연일수',
                         '변경_계획_B_착수','변경_계획_B_완료']
            delayed_df = delayed_df[[c for c in show_cols if c in delayed_df.columns]]\
                .sort_values('지연일수', ascending=False)
            for c in ['변경_계획_B_착수','변경_계획_B_완료']:
                if c in delayed_df.columns:
                    delayed_df[c] = delayed_df[c].dt.strftime('%Y-%m-%d')
            delayed_df.rename(columns={'변경_계획_B_착수':'착수','변경_계획_B_완료':'완료','대분류':'AREA'}, inplace=True)

            # 엑셀 다운로드 버튼 (메모리에서 직접 생성)
            _xls_buf = io.BytesIO()
            with pd.ExcelWriter(_xls_buf, engine='openpyxl') as _w:
                delayed_df.to_excel(_w, sheet_name='지연리스트', index=False)
            st.download_button(
                "📥 엑셀 다운로드",
                data=_xls_buf.getvalue(),
                file_name=f"공정지연리스트_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="proc2_delayed_xls_dl",
            )

            st.markdown(
                f'<div class="dark-html-table-wrap">'
                f'{delayed_df.to_html(index=False, classes="dark-html-table", border=0)}'
                f'</div>', unsafe_allow_html=True)
        else:
            st.success("지연된 항목이 없습니다!")

    # ══════════════════════════════════════════════
    #  Tab 2: 구역별 상세 현황 (기존)
    # ══════════════════════════════════════════════
    elif tab_choice == tab_options[1]:
        st.markdown("##### 🏗️ 구역(AREA) 배치도")
        st.caption("구역을 **클릭**하면 하단에 해당 구역의 **모든 작업 현황**이 표시됩니다.")

        available_types = filtered_df['선종'].dropna().unique() \
                          if '선종' in filtered_df.columns else []
        lng_matches  = [x for x in available_types if 'LNG'  in str(x).upper()]
        cont_matches = [x for x in available_types if 'CONT' in str(x).upper()]
        has_lng  = len(lng_matches)  > 0
        has_cont = len(cont_matches) > 0

        selected_area_filter = None
        selected_ship_group  = None

        if has_lng and has_cont:
            c_lng, c_cont = st.columns(2)
            with c_lng:
                st.markdown("#### 🛳️ LNG")
                fig_lng, sdata_lng = _draw_ship_layout(LNG_LAYOUT, delay_by_area, "", is_split=True)
                ev_lng = st.plotly_chart(fig_lng, use_container_width=True,
                    on_select="rerun", selection_mode="points", key="proc2_chart_lng")
                if ev_lng and ev_lng.get('selection', {}).get('points'):
                    selected_area_filter = sdata_lng[ev_lng['selection']['points'][0]['point_index']]
                    selected_ship_group  = "LNG"
            with c_cont:
                st.markdown("#### 🚢 CONT")
                fig_cont, sdata_cont = _draw_ship_layout(CONT_LAYOUT, delay_by_area, "", is_split=True)
                ev_cont = st.plotly_chart(fig_cont, use_container_width=True,
                    on_select="rerun", selection_mode="points", key="proc2_chart_cont")
                if ev_cont and ev_cont.get('selection', {}).get('points'):
                    selected_area_filter = sdata_cont[ev_cont['selection']['points'][0]['point_index']]
                    selected_ship_group  = "CONT"
        elif has_lng:
            fig_lng, sdata_lng = _draw_ship_layout(LNG_LAYOUT, delay_by_area, "🛳️ LNG")
            ev = st.plotly_chart(fig_lng, use_container_width=True,
                on_select="rerun", selection_mode="points", key="proc2_chart_lng_single")
            if ev and ev.get('selection', {}).get('points'):
                selected_area_filter = sdata_lng[ev['selection']['points'][0]['point_index']]
                selected_ship_group  = "LNG"
        elif has_cont:
            fig_cont, sdata_cont = _draw_ship_layout(CONT_LAYOUT, delay_by_area, "🚢 CONT")
            ev = st.plotly_chart(fig_cont, use_container_width=True,
                on_select="rerun", selection_mode="points", key="proc2_chart_cont_single")
            if ev and ev.get('selection', {}).get('points'):
                selected_area_filter = sdata_cont[ev['selection']['points'][0]['point_index']]
                selected_ship_group  = "CONT"
        else:
            st.info("선택된 조회 조건에서 표시할 선종 데이터(LNG/CONT)가 없습니다.")

        st.markdown('<hr style="border-color:rgba(56,189,248,0.15);">', unsafe_allow_html=True)

        # ══════════════════════════════════════════════
        #  공정 타임라인 (배치도 구역 클릭 연동)
        # ══════════════════════════════════════════════
        # 구역 클릭 시 해당 구역만, 없으면 전체
        if selected_area_filter:
            _cond_area = filtered_df['대분류'] == selected_area_filter
            if selected_ship_group and '선종' in filtered_df.columns:
                _ship_matches = lng_matches if selected_ship_group == "LNG" else cont_matches
                _cond_ship    = filtered_df['선종'].isin(_ship_matches)
            else:
                _cond_ship = pd.Series([True] * len(filtered_df), index=filtered_df.index)
            gantt_df    = filtered_df[_cond_area & _cond_ship]
            gantt_label = f"[{selected_ship_group}] {selected_area_filter}" if selected_ship_group else selected_area_filter
        else:
            gantt_df    = filtered_df
            gantt_label = "전체"

        # ── ① 거주구 탑재완료 관리 ─────────────────────────
        _all_projs_raw = sorted(filtered_df['프로젝트'].dropna().unique().tolist()) \
                         if not filtered_df.empty else []

        # 탑재완료 상태: 세션당 1회 DB 조회 후 session_state에서 관리
        # (run_query 5분 캐시 우회 — 저장 즉시 드롭다운에 반영)
        if 'proc2_tapjae_state' not in _ss:
            _ss['proc2_tapjae_state'] = get_all_tapjae_status()
        _tapjae_status: dict = _ss['proc2_tapjae_state']

        with st.expander("🚢 거주구 탑재 완료 관리", expanded=False):
            if _all_projs_raw:
                st.caption("체크 후 **저장** 버튼을 누르면 드롭다운에서 즉시 제외됩니다.")
                _tj_ncols = min(5, max(1, len(_all_projs_raw)))
                _tj_cols  = st.columns(_tj_ncols)
                for _tj_i, _tj_pj in enumerate(_all_projs_raw):
                    with _tj_cols[_tj_i % _tj_ncols]:
                        st.checkbox(
                            _tj_pj,
                            value=_tapjae_status.get(_tj_pj, False),
                            key=f"proc2_tapjae_{_tj_pj}",
                        )
                if st.button("💾 탑재완료 저장", key="proc2_tapjae_save", type="primary"):
                    _new_state = dict(_tapjae_status)
                    _all_ok = True
                    for _tj_pj in _all_projs_raw:
                        _wval = bool(_ss.get(f"proc2_tapjae_{_tj_pj}",
                                             _tapjae_status.get(_tj_pj, False)))
                        _new_state[_tj_pj] = _wval
                        if _wval != _tapjae_status.get(_tj_pj, False):
                            if not set_tapjae_status(_tj_pj, _wval):
                                _all_ok = False
                    if _all_ok:
                        _ss['proc2_tapjae_state'] = _new_state
                        st.toast("✅ 저장했습니다.")
                        st.rerun()
                    else:
                        st.error("저장 중 오류가 발생했습니다. 관리자에게 문의해 주세요.")
            else:
                st.caption("표시할 프로젝트가 없습니다.")

        # ── ② 프로젝트 드롭다운 + 탐색 버튼 + 담당자 칸 ──────
        # 사이드바 미선택 시에도 전체 프로젝트 목록 사용 (df_raw 기반)
        _all_projs_in_gantt = sorted(
            df_raw['프로젝트'].dropna().unique().tolist()
        ) if not df_raw.empty else []
        # 탑재완료 저장된 프로젝트 드롭다운 제외
        _projs_active = [p for p in _all_projs_in_gantt if not _tapjae_status.get(p, False)]

        # 사이드바 1개 선택 시 간트 드롭다운 자동 동기화
        if len(selected_projects) == 1 and selected_projects[0] in _projs_active:
            _sidebar_proj = selected_projects[0]
            if _ss.get('proc2_gantt_proj') != _sidebar_proj:
                _ss['proc2_gantt_proj'] = _sidebar_proj
                _ps, _pe = get_project_date_range(filtered_df, _sidebar_proj)
                _ss['proc2_gantt_proj_start'] = _ps
                _ss['proc2_gantt_proj_end']   = _pe

        def _nav_to_proj(pj: str):
            _ss['proc2_gantt_proj'] = pj
            _ps2, _pe2 = get_project_date_range(df_raw, pj)
            _ss['proc2_gantt_proj_start'] = _ps2
            _ss['proc2_gantt_proj_end']   = _pe2
            st.rerun()

        _curr_pj    = _ss.get('proc2_gantt_proj', "(전체)")
        _curr_pi    = _projs_active.index(_curr_pj) if _curr_pj in _projs_active else -1

        col_prev, col_pj, col_next, col_mgr_lbl, col_mgr_val, col_mgr_btn = \
            st.columns([0.35, 2.2, 0.35, 0.55, 1.7, 0.75])

        with col_prev:
            if st.button("◀", key="proc2_btn_proj_prev", use_container_width=True,
                         help="이전 프로젝트") and _projs_active:
                _prev_i = (_curr_pi - 1) % len(_projs_active)
                _nav_to_proj(_projs_active[_prev_i])
        with col_next:
            if st.button("▶", key="proc2_btn_proj_next", use_container_width=True,
                         help="다음 프로젝트") and _projs_active:
                _next_i = (_curr_pi + 1) % len(_projs_active)
                _nav_to_proj(_projs_active[_next_i])

        with col_pj:
            _gantt_proj_opts = ["(전체)"] + _projs_active
            _gantt_proj_prev = _ss.get('proc2_gantt_proj', "(전체)")
            _gantt_proj_idx  = _gantt_proj_opts.index(_gantt_proj_prev) \
                               if _gantt_proj_prev in _gantt_proj_opts else 0
            _gantt_proj = st.selectbox(
                "프로젝트", _gantt_proj_opts,
                index=_gantt_proj_idx, key="proc2_gantt_proj_sel",
                label_visibility="collapsed",
            )
            if _gantt_proj != _ss.get('proc2_gantt_proj'):
                _ss['proc2_gantt_proj'] = _gantt_proj
                if _gantt_proj != "(전체)":
                    _ps, _pe = get_project_date_range(df_raw, _gantt_proj)
                    _ss['proc2_gantt_proj_start'] = _ps
                    _ss['proc2_gantt_proj_end']   = _pe
                else:
                    _ss.pop('proc2_gantt_proj_start', None)
                    _ss.pop('proc2_gantt_proj_end', None)
                st.rerun()

        # ③ 선택된 프로젝트의 기간 배지 표시
        if _ss.get('proc2_gantt_proj_start') and _ss.get('proc2_gantt_proj_end'):
            _ps_d = _ss['proc2_gantt_proj_start']
            _pe_d = _ss['proc2_gantt_proj_end']
            st.caption(f"📅 {_gantt_proj} 기간: **{_ps_d}** ~ **{_pe_d}**")

        # ④ 담당자 칸
        _sel_proj_for_mgr = _gantt_proj if _gantt_proj != "(전체)" else \
                             (selected_projects[0] if len(selected_projects) == 1 else "")
        with col_mgr_lbl:
            st.markdown('<p style="margin:0;padding:6px 0 0 0;font-size:0.85rem;color:#94a3b8;">담당자</p>',
                        unsafe_allow_html=True)
        with col_mgr_val:
            _mgr_default = get_manager(_sel_proj_for_mgr) if _sel_proj_for_mgr else ""
            _mgr_input = st.text_input(
                "담당자입력", value=_mgr_default,
                key=f"proc2_mgr_input_{_sel_proj_for_mgr or 'all'}",
                placeholder="담당자 이름",
                label_visibility="collapsed",
            )
        with col_mgr_btn:
            if st.button("저장", key="proc2_mgr_save", use_container_width=True):
                if _sel_proj_for_mgr and _mgr_input.strip():
                    try:
                        save_manager(_sel_proj_for_mgr, _mgr_input.strip())
                        st.toast("✅ 담당자가 저장되었습니다.")
                    except Exception:
                        logger.error("담당자 저장 실패", exc_info=True)
                        st.error("저장 중 오류가 발생했습니다.")
                else:
                    st.warning("프로젝트와 담당자를 입력해 주세요.")

        # 프로젝트 필터 적용:
        # 사이드바 필터(STG·공종 등)를 유지하면서 해당 프로젝트만 추출
        _page_proj = _ss.get('proc2_gantt_proj', "(전체)")
        if _page_proj != "(전체)":
            gantt_df = filtered_df[filtered_df['프로젝트'] == _page_proj].copy()
            gantt_label = _page_proj
        else:
            # 기존 로직 유지 (사이드바 필터 적용된 gantt_df)
            if _ss.get('proc2_gantt_proj', "(전체)") != "(전체)":
                gantt_df = gantt_df[gantt_df['프로젝트'] == _page_proj]
                gantt_label = _page_proj

        # row_mode: 공종만 필터(프로젝트·구역 미선택) → 호선별, 아니면 구역별
        row_mode = "ship" if (
            bool(selected_gongjongs)
            and not selected_projects
            and not selected_area_filter
            and _page_proj == "(전체)"
        ) else "area"

        mode_text = "호선별" if row_mode == "ship" else "구역별"
        col_gh, col_gb = st.columns([6, 1])
        with col_gh:
            st.markdown(f"##### 📅 공정 타임라인 — {gantt_label} ({mode_text} 뷰 · {gantt_basis})")
            _ro_note = "  🔒 읽기 전용" if not effective_editable else ""
            st.caption(f"접속자: `{current_user}`{_ro_note}")
        with col_gb:
            if st.button("⛶ 최대화", key="proc2_gantt_maximize", use_container_width=True):
                st.session_state["proc2_gantt_maximized"] = True
                st.rerun()

        # ── 간트 컨트롤 행 (Streamlit 네이티브) ──
        _render_gantt_ctrl_row(_ss)

        # 페이지 드롭다운 또는 사이드바 필터 중 하나라도 있으면 간트 표시
        has_filter = (bool(selected_projects) or bool(selected_gongjongs)
                      or _page_proj != "(전체)")
        if not has_filter:
            st.info("💡 위 드롭다운에서 **프로젝트**를 선택하거나, 사이드바에서 **호선/공종**을 선택하세요.")
        else:
            gantt_tasks = get_gantt_data(gantt_df, basis=gantt_basis)
            if not gantt_tasks:
                st.warning(f"⚠️ 선택한 조건에 해당하는 작업이 없습니다. ({gantt_basis} 기준 일자가 있는 행만 표시)")
            else:
                _render_gantt_component(gantt_tasks, is_editable=effective_editable,
                                        current_user=current_user, height=1400,
                                        row_mode=row_mode,
                                        show_hidden=False,
                                        col_width=_ss['proc2_gantt_col_width'],
                                        light_theme=False,
                                        show_actuals=_ss['proc2_gantt_actuals'],
                                        week_offset=_ss['proc2_gantt_week_offset'],
                                        overlap_mode=_ss.get('proc2_overlap_mode', 'lane'))

        st.markdown('<hr style="border-color:rgba(56,189,248,0.15);">', unsafe_allow_html=True)
        st.subheader("📋 구역별 상세 작업 현황")

        has_sidebar_filter = bool(selected_gongjongs) or bool(selected_projects)

        def _full_status(row):
            if pd.notnull(row['실적_C_종료']):
                return "지연 완료" if row['실적_C_종료'] > row['변경_계획_B_완료'] else "완료"
            if row['변경_계획_B_완료'] < today: return "완료 지연"
            if pd.isna(row['실적_C_착수']) and row['변경_계획_B_착수'] < today: return "착수 지연"
            if pd.notnull(row['실적_C_착수']): return "진행 중"
            return "진행 예정"

        def _render_area_table(df_to_show: pd.DataFrame):
            if df_to_show.empty:
                st.warning("⚠️ 해당 조건에 대한 상세 데이터가 없습니다.")
                return
            df_to_show = df_to_show.copy()
            df_to_show['현재상태'] = df_to_show.apply(_full_status, axis=1)
            show_cols = [c for c in [
                '프로젝트','STG','대분류','공종','작업내용','현재상태',
                '변경_계획_B_착수','변경_계획_B_완료','실적_C_착수','실적_C_종료'
            ] if c in df_to_show.columns]
            df_to_show = df_to_show[show_cols].sort_values('변경_계획_B_완료')
            for c in ['변경_계획_B_착수','변경_계획_B_완료','실적_C_착수','실적_C_종료']:
                if c in df_to_show.columns:
                    df_to_show[c] = df_to_show[c].dt.strftime('%Y-%m-%d')
            st.markdown(
                f'<div class="dark-html-table-wrap">'
                f'{df_to_show.to_html(index=False, classes="dark-html-table", border=0)}'
                f'</div>', unsafe_allow_html=True)

        if selected_area_filter and selected_ship_group:
            st.info(f"📍 선택된 구역: **[{selected_ship_group}] {selected_area_filter}**")
            cond_area = filtered_df['대분류'] == selected_area_filter
            if '선종' in filtered_df.columns:
                cond_ship = filtered_df['선종'].isin(lng_matches) \
                            if selected_ship_group == "LNG" \
                            else filtered_df['선종'].isin(cont_matches)
            else:
                cond_ship = pd.Series([True]*len(filtered_df), index=filtered_df.index)
            _render_area_table(filtered_df[cond_area & cond_ship])
        elif has_sidebar_filter:
            filter_desc = []
            if selected_gongjongs: filter_desc.append(f"공종: {', '.join(selected_gongjongs)}")
            if selected_projects:  filter_desc.append(f"프로젝트: {', '.join(selected_projects)}")
            st.info(f"📊 전체 구역 작업 현황 ({' | '.join(filter_desc)})")
            _render_area_table(filtered_df)
        else:
            st.info("💡 위 배치도에서 구역을 클릭하면 상세 작업 내역이 표시됩니다.")

        # 변경 내역 DB 반영 (편집 권한자만)
        if is_editable:
            st.markdown('<hr style="border-color:rgba(56,189,248,0.15);">', unsafe_allow_html=True)
            with st.expander("📥 변경 내역 DB 반영", expanded=False):
                st.caption("간트에서 [💾 저장] 시 다운로드된 JSON 파일을 여기에 업로드하세요.")
                col_a, col_b = st.columns([2, 1])
                with col_a:
                    uploaded = st.file_uploader(
                        "변경 JSON 업로드", type=['json'], key="proc2_gantt_upload"
                    )
                with col_b:
                    memo_input = st.text_input(
                        "회의 메모", key="proc2_gantt_memo",
                        placeholder="예: 4/23 공정회의"
                    )
                if uploaded and st.button("💾 DB 반영", key="proc2_gantt_apply", type="primary"):
                    try:
                        changes = json.load(uploaded)
                        if not isinstance(changes, list) or not changes:
                            st.warning("⚠️ 업로드된 파일에 변경 내역이 없습니다.")
                        else:
                            with st.spinner(f"{len(changes)}건 저장 중..."):
                                result = save_gantt_changes(
                                    changes=changes,
                                    user_name=current_user,
                                    memo=memo_input or None,
                                )
                            if result['failed'] == 0:
                                st.success(
                                    f"✅ {result['success']}건 저장 완료! "
                                    f"(lq_proc2_2 이력 기록 포함)"
                                )
                                st.cache_data.clear()
                                st.rerun()
                            else:
                                st.warning(
                                    f"⚠️ 성공 {result['success']}건 / 실패 {result['failed']}건"
                                )
                                st.json(result['errors'])
                    except Exception as e:
                        logger.error("JSON 파싱 오류: %s\n%s", e, traceback.format_exc())
                        st.error("저장 데이터 처리 중 오류가 발생했습니다.")

            # ── 새 작업 추가 (DB INSERT) ──
            with st.expander("➕ 새 작업 추가", expanded=False):
                st.caption("간트 차트에 표시할 새 작업을 lq_proc2_1 테이블에 등록합니다.")

                # 기존 값 목록 (selectbox 옵션)
                _projs = sorted(df_raw['프로젝트'].dropna().unique().tolist())
                _ships = (sorted(df_raw['선종'].dropna().unique().tolist())
                          if '선종' in df_raw.columns else [])
                _stgs  = sorted(df_raw['STG'].astype(str).unique().tolist())
                _areas = sorted(df_raw['대분류'].dropna().unique().tolist())
                _gjs   = sorted(df_raw['공종'].dropna().unique().tolist())

                # 사이드바 선택값이 있으면 기본값으로 사용
                _default_proj = (selected_projects[0]
                                 if selected_projects and selected_projects[0] in _projs else _projs[0])
                _default_area = (selected_area_filter
                                 if selected_area_filter and selected_area_filter in _areas else _areas[0])

                with st.form(key="proc2_newtask_form", clear_on_submit=True):
                    fc1, fc2, fc3 = st.columns(3)
                    new_proj = fc1.selectbox("프로젝트", _projs,
                                             index=_projs.index(_default_proj),
                                             key="proc2_newtask_proj")
                    new_ship = fc2.selectbox("선종", [""] + _ships,
                                             key="proc2_newtask_ship")
                    new_stg  = fc3.selectbox("STG", _stgs, key="proc2_newtask_stg")

                    fc1, fc2, fc3 = st.columns(3)
                    new_area = fc1.selectbox("구역(대분류)", _areas,
                                             index=_areas.index(_default_area),
                                             key="proc2_newtask_area")
                    new_gj   = fc2.selectbox("공종", _gjs, key="proc2_newtask_gj")
                    new_weight = fc3.number_input(
                        "점유율", min_value=0.0, value=1.0, step=0.1,
                        key="proc2_newtask_weight"
                    )

                    new_task_name = st.text_input(
                        "작업내용", key="proc2_newtask_name",
                        placeholder="⚠️ 개인정보가 포함되지 않도록 주의해 주세요."
                    )

                    fc1, fc2 = st.columns(2)
                    new_start = fc1.date_input("계획 착수일", key="proc2_newtask_start")
                    new_end   = fc2.date_input("계획 완료일", key="proc2_newtask_end")

                    new_memo = st.text_input(
                        "회의 메모 (선택)", key="proc2_newtask_memo",
                        placeholder="예: 4/23 공정회의"
                    )

                    submitted = st.form_submit_button("➕ 등록", type="primary")
                    if submitted:
                        if not new_task_name.strip():
                            st.warning("작업내용을 입력해주세요.")
                        elif new_start > new_end:
                            st.warning("착수일이 완료일보다 늦을 수 없습니다.")
                        else:
                            ok = add_new_task(
                                project=new_proj,
                                ship_type=new_ship,
                                stg=new_stg,
                                area=new_area,
                                gongjong=new_gj,
                                task_name=new_task_name.strip(),
                                weight=float(new_weight),
                                plan_start=new_start,
                                plan_end=new_end,
                                user_name=current_user,
                                memo=(new_memo.strip() or None),
                            )
                            if ok:
                                st.success(f"✅ 새 작업 등록 완료: {new_task_name}")
                                st.cache_data.clear()
                                st.rerun()
                            else:
                                st.error("오류가 발생했습니다. 관리자에게 문의해 주세요.")

        # 관리자 전용: 편집 권한 관리 패널
        if st.session_state.get("is_admin"):
            st.markdown('<hr style="border-color:rgba(56,189,248,0.15);">', unsafe_allow_html=True)
            with st.expander("🔐 간트 편집 권한 관리 (관리자)", expanded=False):
                df_auth = get_auth_list()
                st.markdown(f"**현재 권한자 목록** ({len(df_auth)}명)")
                if not df_auth.empty:
                    for _, row in df_auth.iterrows():
                        c1, c2, c3, c4 = st.columns([3, 2, 2, 1])
                        c1.code(str(row["사용자ID"]))
                        c2.write(str(row["이름"]))
                        expire = row.get("만료일")
                        c3.write("무기한" if pd.isna(expire) else str(expire))
                        if c4.button("삭제", key=f"proc2_auth_del_{row['사용자ID']}"):
                            remove_auth_user(str(row["사용자ID"]))
                            st.cache_data.clear()
                            st.rerun()
                else:
                    st.info("등록된 권한자가 없습니다.")
                st.markdown("---")
                st.markdown("**권한자 추가**")
                c1, c2, c3 = st.columns([3, 2, 1])
                new_uid  = c1.text_input(
                    "사용자ID", key="proc2_auth_uid",
                    placeholder="⚠️ 개인정보가 포함되지 않도록 주의해 주세요."
                )
                new_name = c2.text_input(
                    "이름", key="proc2_auth_name",
                    placeholder="예: 홍길동"
                )
                if c3.button("추가", key="proc2_auth_add", type="primary"):
                    if new_uid and new_name:
                        add_auth_user(new_uid.strip(), new_name.strip(), current_user)
                        st.success(f"✅ {new_name}({new_uid}) 권한 추가 완료")
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.warning("사용자ID와 이름을 모두 입력해주세요.")
                st.caption(f"💡 현재 접속자 ID: `{current_user}` — 이 값을 사용자ID에 입력하면 현재 접속자에게 권한 부여")

        # ══════════════════════════════════════════════
        #  📝 공정 메모 섹션
        # ══════════════════════════════════════════════
        st.markdown('<hr style="border-color:rgba(56,189,248,0.15);">', unsafe_allow_html=True)
        st.subheader("📝 공정 메모")

        _memo_proj = _ss.get('proc2_gantt_proj', "(전체)")
        _memo_proj_filter = None if _memo_proj == "(전체)" else _memo_proj

        with st.expander("✏️ 새 메모 작성", expanded=False):
            with st.form(key="proc2_memo_form", clear_on_submit=True):
                fm1, fm2 = st.columns(2)
                memo_org    = fm1.text_input(
                    "조직", key="proc2_memo_org",
                    placeholder="예: 선실공사팀"
                )
                memo_author = fm2.text_input(
                    "작성자", value=current_user, key="proc2_memo_author"
                )
                memo_proj_input = st.text_input(
                    "프로젝트 (선택)", value=_memo_proj_filter or "",
                    key="proc2_memo_proj_input",
                    placeholder="예: H1234"
                )
                memo_text = st.text_area(
                    "메모 내용",
                    key="proc2_memo_text",
                    placeholder="공정회의 내용, 변경사항 등을 입력하세요.",
                    height=120,
                )
                memo_photo = st.file_uploader(
                    "사진 첨부 (선택)", type=["jpg", "jpeg", "png", "bmp"],
                    key="proc2_memo_photo"
                )
                submitted_memo = st.form_submit_button("💾 저장", type="primary")
                if submitted_memo:
                    if not memo_org.strip():
                        st.warning("조직을 입력해주세요.")
                    elif not memo_author.strip():
                        st.warning("작성자를 입력해주세요.")
                    elif not memo_text.strip():
                        st.warning("메모 내용을 입력해주세요.")
                    else:
                        _photo_bytes = memo_photo.read() if memo_photo else None
                        _photo_name  = memo_photo.name  if memo_photo else None
                        try:
                            _ok_memo = add_memo(
                                조직=memo_org.strip(),
                                작성자=memo_author.strip(),
                                메모=memo_text.strip(),
                                사진_bytes=_photo_bytes,
                                파일명=_photo_name,
                                프로젝트=memo_proj_input.strip() or None,
                            )
                            if _ok_memo:
                                st.success("✅ 메모가 저장되었습니다.")
                                st.rerun()
                            else:
                                st.error("저장 중 오류가 발생했습니다. 관리자에게 문의해 주세요.")
                        except Exception:
                            logger.error("메모 저장 실패", exc_info=True)
                            st.error("저장 중 오류가 발생했습니다.")

        # 메모 목록
        _memos_df = get_memos(프로젝트=_memo_proj_filter, limit=50)
        if _memos_df is not None and not _memos_df.empty:
            st.caption(
                f"최근 메모 {len(_memos_df)}건" +
                (f" — 프로젝트: **{_memo_proj_filter}**" if _memo_proj_filter else " (전체)")
            )
            for _, _mrow in _memos_df.iterrows():
                _mid      = int(_mrow['메모ID'])
                _mproj    = _mrow.get('프로젝트') or ""
                _morg     = _mrow.get('조직', "")
                _mauth    = _mrow.get('작성자', "")
                _mdate    = _mrow.get('등록일시')
                _mdate_s  = _mdate.strftime('%Y-%m-%d %H:%M') if pd.notnull(_mdate) else ""
                _mtext    = _mrow.get('메모', "")
                _mfile    = _mrow.get('파일명') or ""
                with st.container():
                    mc1, mc2 = st.columns([10, 1])
                    with mc1:
                        _proj_badge = f"`{_mproj}` &nbsp;" if _mproj else ""
                        st.markdown(
                            f"{_proj_badge}**{_morg}** · {_mauth}"
                            f"&nbsp;&nbsp;<span style='color:#94a3b8;font-size:0.82rem;'>{_mdate_s}</span>",
                            unsafe_allow_html=True,
                        )
                        st.write(_mtext)
                        if _mfile:
                            _pdata = get_memo_photo(_mid)
                            if _pdata:
                                with st.expander(f"📷 사진 보기 ({_mfile})"):
                                    st.image(_pdata, use_container_width=True)
                    with mc2:
                        if st.button("🗑️", key=f"proc2_memo_del_{_mid}", help="이 메모 삭제"):
                            try:
                                delete_memo(_mid)
                                st.rerun()
                            except Exception:
                                logger.error("메모 삭제 실패", exc_info=True)
                                st.error("삭제 중 오류가 발생했습니다.")
                    st.markdown(
                        '<hr style="border-color:rgba(56,189,248,0.08);margin:4px 0;">',
                        unsafe_allow_html=True,
                    )
        else:
            st.caption("저장된 메모가 없습니다.")

    # ══════════════════════════════════════════════
    #  Tab 3: 기준정보 (관리자 전용 통합 포인트)
    # ══════════════════════════════════════════════
    elif tab_choice == tab_options[2]:
        st.markdown("##### 🗂️ 기준정보 관리")
        if not st.session_state.get("is_admin"):
            st.warning("⚠️ 관리자 권한이 필요합니다. 사이드바에서 관리자 비밀번호를 입력해 주세요.")
        else:
            # TODO: 기준정보 브랜치 통합 시 여기에 컴포넌트 삽입
            st.info("기준정보 관리 기능은 준비 중입니다. (별도 브랜치 통합 후 제공 예정)")

    # ══════════════════════════════════════════════
