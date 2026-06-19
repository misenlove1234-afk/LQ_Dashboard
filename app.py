import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from datetime import datetime
import base64
import os
import logging
import traceback

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════
#  1. 페이지 기본 설정
# ══════════════════════════════════════════════════════════
st.set_page_config(
    page_title="LQ All In One",
    page_icon="⚓",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ══════════════════════════════════════════════════════════
#  2. 공통 유틸리티 함수 (에셋 로딩 및 포매터)
# ══════════════════════════════════════════════════════════

def get_image_base64(image_path):
    """로컬 이미지를 HTML에 넣을 수 있게 Base64로 변환하는 함수"""
    try:
        with open(image_path, "rb") as img_file:
            encoded = base64.b64encode(img_file.read()).decode()
            return encoded
    except FileNotFoundError:
        return ""

@st.cache_resource
def load_icon(name):
    """assets/ 폴더 내 아이콘을 불러옵니다. 앱 시작 시 한 번만 실행되어 캐싱됩니다."""
    base_path = "assets"
    for ext in (f"{name}.png.png", f"{name}.png"):
        path = os.path.join(base_path, ext)
        result = get_image_base64(path)
        if result:
            return result
    return ""

def safe(fn):
    try: return fn()
    except Exception as e:
        return {}

def fv(v, fmt=".1f", suffix="", na="-"):
    """None/NaN 안전하게 포맷"""
    try:
        if v is None: return na
        f = float(v)
        import math
        if math.isnan(f): return na
        return f"{f:{fmt}}{suffix}"
    except Exception: return na

def ring_svg(pct, color, icon_emoji, size=80):
    """원형 게이지 링 SVG를 반환합니다. pct: 0~100 채움률."""
    import math
    r = 28
    circ = 2 * math.pi * r
    dash = circ * max(0.0, min(float(pct), 100.0)) / 100
    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 70 70">'
        f'<circle cx="35" cy="35" r="{r}" fill="none" stroke="rgba(255,255,255,0.08)" stroke-width="6"/>'
        f'<circle cx="35" cy="35" r="{r}" fill="none" stroke="{color}" stroke-width="6" '
        f'stroke-dasharray="{dash:.1f} {circ:.1f}" stroke-linecap="round" '
        f'transform="rotate(-90 35 35)"/>'
        f'<text x="35" y="40" text-anchor="middle" font-size="20">{icon_emoji}</text>'
        f'</svg>'
    )

def color_cls(v, good_thresh, bad_thresh, invert=False):
    """값에 따라 색상 클래스 반환 (invert=True: 낮을수록 좋음)"""
    try:
        if v is None: return ""
        f = float(v)
        import math
        if math.isnan(f): return ""
        if not invert:
            return "good" if f >= good_thresh else ("bad" if f < bad_thresh else "warn")
        else:
            return "good" if f <= good_thresh else ("bad" if f > bad_thresh else "warn")
    except Exception: return ""

# ══════════════════════════════════════════════════════════
#  3. 공통 메뉴 데이터 및 사이드바 제어
# ══════════════════════════════════════════════════════════
KPI_SUBMENUS = [
    ("kpi_1", "직영 능률/실동률 실적",          "📈"),
    ("kpi_2", "글로벌 BEP 실적",                "💰"),
    ("kpi_3", "협력사 전망/실적",                 "🤝"),
    ("kpi_4", "월별 기성 전망",                  "📅"),
    ("kpi_5", "프로젝트 예산 현황",              "💼"),
    ("kpi_6", "프로젝트별 Punch 현황",            "🔍"),
    ("kpi_7", "용접 불량률(배관/구조)",          "🔧"),
]

PROCESS_SUBMENUS = [
    ("proc_1", "일일 작업허가서 현황",   "🖨️"),
    ("proc_2", "사곡 거주구 제작 현황", "🚢"),
    ("proc_3", "특수선 공정 현황",       "⚙️"),
    ("proc_4", "전장 결선 자재 현황",    "🔌"),
]

MGMT_SUBMENUS = [
    ("data_upload", "압축파일 업데이트", "📦"),
]

SIDEBAR_PAGES = {"proc_2", "proc_3", "proc_4", "kpi_1", "kpi_2", "kpi_4", "kpi_5", "kpi_6", "kpi_7"}

# ══════════════════════════════════════════════════════════
#  4. 카드 데이터 로딩 함수 (캐시 적용)
# ══════════════════════════════════════════════════════════

@st.cache_data(ttl=300)
def _card_kpi1():
    from data.kpi_1_data import (
        load_data, load_시수_data, load_targets,
        get_능률_summary, get_실동률_summary, get_current_month,
    )
    df              = load_data()
    df_직접, df_총발생 = load_시수_data()
    df_tgt          = load_targets()
    cur_month       = get_current_month()
    # 능률실적 (기성/투입 비율값)
    res_능률 = get_능률_summary(df, df_tgt, 월=[cur_month], 구분="내국인")
    능률실적 = res_능률["선실부"].get("능률실적")
    # 실동률실적 (직접공수/총발생 비율값, ×100 = %)
    res_실동 = get_실동률_summary(df_직접, df_총발생, df_tgt, 월=[cur_month], 구분="내국인")
    실동률실적 = res_실동["선실부"].get("실동률실적")
    return {"능률실적": 능률실적, "실동률실적": 실동률실적}

@st.cache_data(ttl=300)
def _card_kpi2():
    from data.kpi_2_data import get_group_kpi_summary
    grp = get_group_kpi_summary()
    return {
        "월": grp.get("월"),
        "1그룹_달성률": grp.get("1그룹"),
        "2그룹_달성률": grp.get("2그룹"),
    }

@st.cache_data(ttl=300)
def _card_kpi3():
    """협력사별 당월 정도율(가중평균) — 메인 카드용
    KPI_3 화면 방사형 그래프와 동일 가중치 사용
    (투입30/지출10/능률10/처리량25/단위물량당기성25)
    """
    from data.kpi_3_data import (
        get_jeongdoyul_data, COMPANY_LIST, RADAR_METRICS,
        정도율_가중치, mask_company,
    )
    try:
        data = get_jeongdoyul_data(month="당월")
    except Exception:
        return {"items": []}

    items = []
    for company in COMPANY_LIST:
        d = data.get(company) if isinstance(data, dict) else None
        v = None
        if d:
            실적_vals = d.get("실적", []) or []
            if len(실적_vals) == len(RADAR_METRICS):
                가중합 = sum(
                    정도율_가중치[m] * float(val)
                    for m, val in zip(RADAR_METRICS, 실적_vals)
                    if m in 정도율_가중치
                )
                가중치합 = sum(
                    정도율_가중치[m] for m in RADAR_METRICS if m in 정도율_가중치
                )
                if 가중치합 > 0:
                    v = round(가중합 / 가중치합, 1)
        items.append({"name": mask_company(company), "정도율": v})
    return {"items": items}


@st.cache_data(ttl=300)
def _card_kpi4():
    from data.kpi_4_data import load_data, get_col_map, compute_kiseong
    from datetime import date
    df = load_data()
    col_map = get_col_map(df.columns.tolist())
    today = date.today()
    chart_df = compute_kiseong(df, col_map, today, today)
    total = int(chart_df["total"].sum()) if not chart_df.empty else 0
    return {"total": total}

@st.cache_data(ttl=300)
def _card_kpi5():
    from data.kpi_5_data import load_data, preprocess_sunpyo, preprocess_gongsu, get_ship_display
    df_s, df_g = load_data()
    df_s = preprocess_sunpyo(df_s)
    df_g = preprocess_gongsu(df_g)
    urgent_projs = df_s[df_s["인도임박"] == "임박"]["프로젝트"].unique().tolist()
    if not urgent_projs:
        urgent_projs = df_s["프로젝트"].unique().tolist()
    df_disp, _ = get_ship_display(df_s, df_g, urgent_projs)
    projects = [
        {"프로젝트": r["프로젝트"], "Progress(%)": r.get("Progress(%)", 0)}
        for _, r in df_disp.iterrows()
    ]
    return {"projects": projects}

@st.cache_data(ttl=300)
def _card_kpi6():
    from data.kpi_6_data import load_data, get_summary, get_delivery_soon_projects
    df = load_data()
    proj_list = get_delivery_soon_projects(df)
    # 인도임박 호선의 잔여 punch만 집계
    df_urgent = df[df["프로젝트"].isin(proj_list)] if proj_list else df
    remain_urgent = get_summary(df_urgent)["remain"]
    return {"remain": remain_urgent, "proj_cnt": len(proj_list)}

@st.cache_data(ttl=300)
def _card_kpi7():
    from data.kpi_7_data import load_data, apply_filter, get_summary, get_target_rate
    import pandas as pd
    df_raw, df_target = load_data()
    cur_year = pd.Timestamp.now().year
    df_f = apply_filter(df_raw, cur_year, [], "전체")
    res  = get_summary(df_f, df_target, "전체")
    return {
        "구조_rate":   res.get("구조", {}).get("rate",   0.0),
        "배관_rate":   res.get("배관", {}).get("rate",   0.0),
        "구조_target": res.get("구조", {}).get("target", 0.7),
        "배관_target": res.get("배관", {}).get("target", 1.4),
    }

@st.cache_data(ttl=300)
def _card_proc1():
    from data.proc_1_data import load_data, get_summary
    df = load_data()
    summary = get_summary(df)
    return {"not_printed": summary["not_printed"], "total": summary["total"]}

@st.cache_data(ttl=300)
def _card_proc2():
    from data.proc_2_data import load_data
    import pandas as pd
    df = load_data()
    today = pd.Timestamp.now().normalize()
    if "변경 계획(B)_완료" in df.columns and "실적(C)_종료" in df.columns:
        delay_mask = (
            df["변경 계획(B)_완료"].notna() &
            (df["변경 계획(B)_완료"] < today) &
            df["실적(C)_종료"].isna()
        )
        delay_count = int(delay_mask.sum())
    else:
        delay_count = 0
    return {"delay_count": delay_count}

@st.cache_data(ttl=300)
def _card_proc2_delays():
    """공정 지연 작업 목록 — 메인 카드용 (4 컬럼: 프로젝트/AREA/공종/작업내용).
    proc_2 화면의 '공정 지연 리스트(전체)' 와 동일한 판정 기준 (지연일수 내림차순).
    """
    from data.proc_2_data import load_data
    import pandas as pd
    df = load_data()
    if df is None or df.empty:
        return pd.DataFrame()
    if "변경_계획_B_착수" not in df.columns or "변경_계획_B_완료" not in df.columns:
        return pd.DataFrame()

    today = pd.Timestamp.now().normalize()
    mask = (
        ((df["변경_계획_B_착수"] < today) & df["실적_C_착수"].isna()) |
        ((df["변경_계획_B_완료"] < today) & df["실적_C_종료"].isna())
    )
    delayed = df.loc[mask].copy()
    if delayed.empty:
        return pd.DataFrame()

    # 지연일수 (정렬용)
    def _delay_days(row):
        if pd.isna(row.get("실적_C_종료")) and row.get("변경_계획_B_완료") < today:
            return (today - row["변경_계획_B_완료"]).days
        if pd.isna(row.get("실적_C_착수")) and row.get("변경_계획_B_착수") < today:
            return (today - row["변경_계획_B_착수"]).days
        return 0
    delayed["_지연일수"] = delayed.apply(_delay_days, axis=1)
    delayed = delayed.sort_values("_지연일수", ascending=False)

    if "대분류" in delayed.columns:
        delayed = delayed.rename(columns={"대분류": "AREA"})
    cols = [c for c in ["프로젝트", "AREA", "공종", "작업내용"] if c in delayed.columns]
    return delayed[cols].reset_index(drop=True)

@st.cache_data(ttl=300)
def _card_proc3():
    """
    각 호선의 최신 주차 LQ Total Progress 달성율 조회
    proc_3 화면과 동일한 계산 방식:
      Progress / LQ Total Progress / MC 포함 공종 제외 후
      모든 공종의 누계실적 합 / 누계계획 합 = 달성율
    """
    from utils.db import get_engine
    from sqlalchemy import text
    import pandas as pd

    engine = get_engine()
    # Progress, LQ Total Progress, MC 포함 공종 제외 → 최신 주차(week_key) 전체 집계
    # max_sort 행의 week_key를 구한 뒤, 해당 week_key의 모든 공종 합산
    sql = text("""
        WITH max_sort AS (
            SELECT 호선, MAX(sort_key) AS ms
            FROM [lq_proc3_1]
            WHERE 공종 NOT IN ('Progress', 'LQ Total Progress')
              AND REPLACE(UPPER(공종), ' ', '') NOT LIKE '%MC%'
            GROUP BY 호선
        ),
        latest_week AS (
            SELECT DISTINCT p2.호선, p2.week_key
            FROM [lq_proc3_1] p2
            JOIN max_sort mx ON p2.호선 = mx.호선 AND p2.sort_key = mx.ms
        )
        SELECT p.호선, p.항목, SUM(p.값) AS 합계
        FROM [lq_proc3_1] p
        JOIN latest_week lw ON p.호선 = lw.호선 AND p.week_key = lw.week_key
        WHERE p.공종 NOT IN ('Progress', 'LQ Total Progress')
          AND REPLACE(UPPER(p.공종), ' ', '') NOT LIKE '%MC%'
          AND p.항목 IN ('누계계획', '누계실적', '주간계획', '주간실적')
        GROUP BY p.호선, p.항목
    """)
    with engine.connect() as conn:
        df = pd.read_sql(sql, conn)
    if df.empty:
        return {"ships": []}
    result = []
    for ship, grp in df.groupby("호선"):
        nk = float(grp[grp["항목"] == "누계계획"]["합계"].sum())
        nr = float(grp[grp["항목"] == "누계실적"]["합계"].sum())
        # 누계값 없으면 주간값으로 대체 (SN2688형 단일주차 파일)
        if nk == 0:
            nk = float(grp[grp["항목"] == "주간계획"]["합계"].sum())
        if nr == 0:
            nr = float(grp[grp["항목"] == "주간실적"]["합계"].sum())
        if nk > 0:
            result.append({"호선": ship, "달성율": round(nr / nk * 100, 1)})
    return {"ships": result}

@st.cache_data(ttl=300)
def _card_proc4():
    from data.proc_4_data import load_data, calc_kpi
    df = load_data()
    return calc_kpi(df)

# ══════════════════════════════════════════════════════════
#  5. 공통 UI (CSS + 네비게이션 바)
# ══════════════════════════════════════════════════════════
WEEKDAY_KR = ["월", "화", "수", "목", "금", "토", "일"]

def render_navbar(current_url_path: str = ""):
    """상단 네비게이션 바와 우측 시계를 렌더링.
    시계는 클라이언트 측 JS(setInterval)로 갱신 — 서버 rerun 없음.
    SIDEBAR_PAGES 에서는 좌측에 사이드바 토글(햄버거) 버튼을 함께 노출.
    """
    kpi_links  = "\n".join(
        f'<a href="/{k}" target="_self">{n}</a>'
        for k, n, i in KPI_SUBMENUS
    )
    proc_links = "\n".join(
        f'<a href="/{k}" target="_self">{n}</a>'
        for k, n, i in PROCESS_SUBMENUS
    )

    # 사이드바 토글 버튼 — Streamlit 내장 사이드바 버튼을 JS 로 트리거
    toggle_html = ""
    if current_url_path in SIDEBAR_PAGES:
        toggle_html = (
            '<button id="lq-sidebar-toggle" class="lq-sidebar-toggle"'
            ' title="사이드바 토글" type="button">☰</button>'
        )

    st.html(f"""
    <div class="navbar-wrap">
        <div style="display: flex; align-items: center; gap: 1.0rem;">
            {toggle_html}
            <a href="/" class="nav-logo" target="_self"><span style="color:#fff;">L</span><span style="color:#fff;">Q</span> <span style="color:#38BDF8;">A</span><span style="color:#fff;">ll</span> <span style="color:#38BDF8;">I</span><span style="color:#fff;">n</span> <span style="color:#fff;">O</span><span style="color:#fff;">ne</span></a>
            <nav class="nav-links">
                <div class="nav-dropdown">
                    <span class="nav-item">KPI 지표 ▾</span>
                    <div class="nav-dropdown-menu">
                        {kpi_links}
                    </div>
                </div>
                <div class="nav-dropdown">
                    <span class="nav-item">공정 관리 ▾</span>
                    <div class="nav-dropdown-menu">
                        {proc_links}
                    </div>
                </div>
            </nav>
        </div>

        <div style="display:flex; align-items:center; gap:1rem; margin-left:auto; border-left:1px solid rgba(255,255,255,0.1); padding-left:1.2rem; flex-shrink:0;">
            <div id="lq-nav-date" style="color:#CBD5E1; font-size:0.9rem; font-weight:500; white-space:nowrap;"></div>
            <div id="lq-nav-time" style="font-size:1.5rem; font-weight:700; color:#38BDF8; font-family:'Consolas','Courier New',monospace; letter-spacing:0.05em; line-height:1; white-space:nowrap;"></div>
        </div>
    </div>
    """)

    # 클라이언트 측 시계 갱신 (서버 rerun 없음 — st.navigation race 회피)
    components.html(
        """<script>
        (function() {
            var doc;
            try { doc = (window.top && window.top.document) || document; }
            catch(e) { doc = document; }
            var WEEKDAY = ["일","월","화","수","목","금","토"];
            function tick() {
                var dEl = doc.getElementById('lq-nav-date');
                var tEl = doc.getElementById('lq-nav-time');
                if (!dEl || !tEl) return;
                var n = new Date();
                var y = n.getFullYear();
                var mo = String(n.getMonth()+1).padStart(2,'0');
                var d = String(n.getDate()).padStart(2,'0');
                var w = WEEKDAY[n.getDay()];
                var hh = String(n.getHours()).padStart(2,'0');
                var mm = String(n.getMinutes()).padStart(2,'0');
                dEl.textContent = y+"."+mo+"."+d+" ("+w+")";
                tEl.textContent = hh+" : "+mm;
            }
            tick();
            if (!window.__lqNavClockTimer) {
                window.__lqNavClockTimer = setInterval(tick, 1000);
            }
        })();
        </script>""",
        height=0,
    )

def inject_common_ui(current_url_path: str = ""):
    # ── 사이드바 CSS ──
    # SIDEBAR_PAGES: 자동생성 nav 만 숨김 (사이드바 자체는 사용)
    # 그 외:           사이드바 + 헤더 모두 숨김
    # 펼치기는 navbar 의 자체 햄버거 버튼(render_navbar) 이 담당하므로
    # Streamlit 내장 펼치기 버튼은 모든 페이지에서 숨겨도 무방
    if current_url_path in SIDEBAR_PAGES:
        sidebar_css = (
            "[data-testid='stSidebarNav'] { display: none !important; }"
            " [data-testid='stSidebarCollapsedControl'],"
            " [data-testid='collapsedControl'] { display: none !important; }"
        )
        main_css    = ""
    else:
        sidebar_css = (
            "[data-testid='stSidebarNav'], [data-testid='stSidebar'],"
            " [data-testid='stSidebarCollapseButton'],"
            " [data-testid='stSidebarCollapsedControl'],"
            " [data-testid='collapsedControl'] { display: none !important; }"
        )
        main_css = (
            "[data-testid='stMain']"
            " { margin-left: 0 !important; width: 100% !important; padding-left: 1.5rem !important; }"
        )

    st.html(f"""
    <style>
    .stApp {{ background: #0A0F1D !important; color: #E2E8F0; }}
    {sidebar_css}
    {main_css}
    /* Streamlit 기본 헤더 숨김 — 자체 navbar 사용 */
    [data-testid="stHeader"] {{ display: none !important; }}
    [data-testid="stToolbar"] {{ display: none !important; }}
    [data-testid="stDecoration"] {{ display: none !important; }}
    [data-testid="stMain"] .block-container {{ max-width: 100% !important; padding-top: 0 !important; }}

    html, body, [class*="css"] {{ font-family:"Malgun Gothic","맑은 고딕",sans-serif; }}

    [data-testid="stPageLink"] button, header button[kind="secondary"] {{
        background: rgba(56,189,248,0.08) !important; border: 1px solid rgba(56,189,248,0.3) !important;
        color: #7dd3fc !important; border-radius: 20px !important; transition: all 0.2s;
    }}
    [data-testid="stPageLink"] button:hover, header button[kind="secondary"]:hover {{
        background: rgba(56,189,248,0.18) !important; border-color: rgba(56,189,248,0.55) !important;
    }}

    /* ── 카드 클릭 영역 확보: Streamlit wrapper height 상속 ── */
    [data-testid="stMarkdownContainer"],
    [data-testid="stMarkdownContainer"] > p,
    [data-testid="stMarkdownContainer"] > div {{
        height: 100% !important;
        display: block !important;
    }}
    a.card-link {{
        text-decoration: none !important;
        display: block !important;
        height: 100% !important;
        cursor: pointer !important;
    }}

    .neo-card {{
        background: linear-gradient(145deg, rgba(30,41,59,0.5), rgba(15,23,42,0.8));
        border: 1px solid rgba(255,255,255,0.05); border-radius: 20px;
        padding: 1.5rem; height: 100%; min-height: 175px;
        position: relative; overflow: hidden; transition: all 0.3s ease;
        backdrop-filter: blur(4px); display: flex; flex-direction: column;
        pointer-events: auto; cursor: pointer !important;
    }}
    .neo-card:hover {{
        border-color: rgba(255,255,255,0.15); transform: translateY(-4px);
    }}
    /* 카드 내부 자식 요소가 클릭 이벤트 막지 않도록 */
    .neo-card * {{ pointer-events: none; }}

    .glow-green {{ box-shadow: 0 8px 32px rgba(16,185,129,0.1); border-right: 2px solid rgba(16,185,129,0.5); }}
    .glow-orange {{ box-shadow: 0 8px 32px rgba(245,158,11,0.1); border-right: 2px solid rgba(245,158,11,0.5); }}
    .glow-red {{ box-shadow: 0 8px 32px rgba(239,68,68,0.1); border-right: 2px solid rgba(239,68,68,0.5); }}
    .glow-blue {{ box-shadow: 0 8px 32px rgba(14,165,233,0.1); border-right: 2px solid rgba(14,165,233,0.5); }}
    .glow-cyan {{ box-shadow: 0 8px 32px rgba(6,182,212,0.1); border-right: 2px solid rgba(6,182,212,0.5); }}

    .top-card-flex {{ display: flex; justify-content: space-between; align-items: flex-start; flex: 1; }}
    .top-card-title {{ font-size: 0.9rem; color: #CBD5E1; font-weight: 500; margin-bottom: 0.6rem; }}
    .top-card-value {{ font-size: 2.5rem; font-weight: 800; color: #FFF; line-height: 1.1; font-family: 'Segoe UI',sans-serif; }}
    .top-card-sub {{ font-size: 0.75rem; font-weight: 600; margin-top: 0.5rem; color: #64748B; }}
    .top-card-delta {{
        font-size: 0.75rem; color: #64748B; margin-top: 0.8rem;
        padding-top: 0.6rem; border-top: 1px solid rgba(255,255,255,0.05);
    }}
    .delta-up   {{ color: #10B981; font-weight: 700; }}
    .delta-down {{ color: #EF4444; font-weight: 700; }}
    .delta-neutral {{ color: #64748B; font-weight: 600; }}

    .text-green {{ color: #10B981; }}
    .text-orange {{ color: #F59E0B; }}
    .text-red {{ color: #EF4444; }}
    .text-blue {{ color: #0EA5E9; }}

    .section-title {{ font-size: 1rem; font-weight: 700; color: #FFF; margin-bottom: 1.5rem; display:flex; align-items:center; gap:0.5rem; }}
    .footer {{ text-align:center; color:rgba(100,116,139,0.45); font-size:0.75rem; margin-top:4rem; padding-bottom:2rem; letter-spacing:0.1em; border-top:1px solid rgba(255,255,255,0.05); padding-top:1.5rem; }}

    /* ── 네비게이션바 스타일 ── */
    .navbar-wrap {{
        background: rgba(8,18,42,0.92);
        border-bottom: 1px solid rgba(56,189,248,0.2);
        padding: 1rem 1.2rem;
        margin: 0 0 1.5rem 0;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 1rem;
        position: sticky;
        top: 0;
        z-index: 999;
        backdrop-filter: blur(12px);
        overflow: visible;
        line-height: 1.3;
    }}
    .nav-logo {{
        font-size: 1.9rem; font-weight: 900; color: #38BDF8;
        font-family: 'Segoe UI', Arial, sans-serif;
        letter-spacing: -0.01em;
        text-decoration: none; white-space: nowrap; flex-shrink: 0;
    }}
    .nav-links {{ display: flex; gap: 0.2rem; align-items: center; flex-wrap: nowrap; }}
    .nav-dropdown {{ position: relative; }}
    .nav-item {{
        color: #CBD5E1; font-size: 0.88rem; font-weight: 500;
        padding: 0.45rem 0.7rem; border-radius: 8px;
        cursor: pointer; transition: all 0.2s;
        display: block; white-space: nowrap; user-select: none;
    }}
    .nav-item:hover {{ color: #38BDF8; background: rgba(56,189,248,0.1); }}
    .nav-dropdown-menu {{
        display: none; position: absolute; top: 100%; left: 0;
        background: rgba(10,18,40,0.98); border: 1px solid rgba(56,189,248,0.2);
        border-radius: 0 0 12px 12px; padding: 0.3rem 0.4rem 0.4rem;
        min-width: 220px; z-index: 1000; backdrop-filter: blur(20px);
        box-shadow: 0 8px 32px rgba(0,0,0,0.5);
        /* 공백 없이 연결 — 마우스가 nav-item에서 메뉴로 넘어올 때 gap 없음 */
    }}
    /* nav-item 하단에 투명 패딩으로 hover 영역 연결 */
    .nav-item {{ padding-bottom: 0.9rem; }}
    .nav-dropdown:hover .nav-dropdown-menu {{ display: block; }}
    .nav-dropdown-menu a {{
        display: block; color: #CBD5E1; text-decoration: none;
        padding: 0.45rem 0.8rem; border-radius: 8px; font-size: 0.85rem;
        transition: all 0.15s; white-space: nowrap;
    }}
    .nav-dropdown-menu a:hover {{ color: #38BDF8; background: rgba(56,189,248,0.1); }}

    /* ── 사이드바 토글 햄버거 버튼 ── */
    .lq-sidebar-toggle {{
        background: rgba(56,189,248,0.10);
        border: 1px solid rgba(56,189,248,0.35);
        color: #7dd3fc;
        border-radius: 8px;
        padding: 0.35rem 0.65rem;
        font-size: 1.05rem;
        font-weight: 700;
        cursor: pointer;
        transition: all 0.2s;
        flex-shrink: 0;
        line-height: 1;
        height: 2rem;
    }}
    .lq-sidebar-toggle:hover {{
        background: rgba(56,189,248,0.22);
        border-color: rgba(56,189,248,0.65);
        color: #fff;
    }}
    </style>
    """)

    # 네비게이션 바 + 시계 렌더링 호출 (사이드바 토글 버튼 표시 여부 판단용 path 전달)
    render_navbar(current_url_path)

    # ── 햄버거 버튼 클릭 위임 바인딩 ──
    # render_navbar 는 fragment(60s) 라 매번 버튼 DOM 이 새로 그려지므로
    # body 에 한 번만 click delegate 를 걸어 둠. components.html(iframe) 안의
    # script 는 무조건 실행되므로 st.html 의 sanitize 영향 없음.
    if current_url_path in SIDEBAR_PAGES:
        components.html(
            """<script>
            (function(){
                var doc;
                try { doc = (window.top && window.top.document) || document; }
                catch(e) { doc = document; }
                if (doc.body.dataset.lqToggleBound === '1') return;
                doc.body.dataset.lqToggleBound = '1';
                doc.body.addEventListener('click', function(ev){
                    var hit = ev.target && ev.target.closest && ev.target.closest('#lq-sidebar-toggle');
                    if (!hit) return;
                    ev.preventDefault(); ev.stopPropagation();
                    var t = doc.querySelector('[data-testid="stSidebarCollapseButton"]')
                         || doc.querySelector('[data-testid="stSidebarCollapsedControl"]')
                         || doc.querySelector('[data-testid="collapsedControl"]')
                         || doc.querySelector('[data-testid="stSidebar"] button[kind="header"]')
                         || doc.querySelector('[data-testid="stSidebar"] button');
                    if (t) {
                        var c = (t.tagName === 'BUTTON') ? t : (t.querySelector('button') || t);
                        c.click();
                    } else {
                        console.warn('[LQ] 사이드바 토글 대상 버튼을 찾지 못함');
                    }
                }, true);
            })();
            </script>""",
            height=0,
        )

    # ── 사이드바 자동 열기/닫기: 페이지 이동 시에만 실행 ──
    _prev = st.session_state.get("_sidebar_prev_page", None)
    if _prev != current_url_path:
        st.session_state["_sidebar_prev_page"] = current_url_path
        if current_url_path in SIDEBAR_PAGES:
            # 사이드바 있는 페이지 → 자동 열기
            components.html(
                """<script>
                setTimeout(function(){
                    var btn = window.parent.document.querySelector('[data-testid="stSidebarCollapsedControl"]')
                           || window.parent.document.querySelector('[data-testid="collapsedControl"]');
                    if (btn) btn.click();
                }, 300);
                </script>""",
                height=0,
            )
        else:
            # 사이드바 없는 페이지 → 열려 있으면 닫기
            components.html(
                """<script>
                setTimeout(function(){
                    var btn = window.parent.document.querySelector('[data-testid="stSidebarCollapseButton"]')
                           || window.parent.document.querySelector('[data-testid="collapsedControl"]');
                    // 사이드바가 펼쳐진 상태일 때만 닫기
                    var sidebar = window.parent.document.querySelector('[data-testid="stSidebar"]');
                    if (sidebar && sidebar.getAttribute("aria-expanded") === "true" && btn) btn.click();
                }, 300);
                </script>""",
                height=0,
            )

def render_back_button(target_page_obj):
    if st.button("← 뒤로가기", type="secondary"):
        st.switch_page(target_page_obj)

# ══════════════════════════════════════════════════════════
#  6. 홈 화면 렌더링
# ══════════════════════════════════════════════════════════
def render_home():
    st.html(f"""
    <style>
    /* ── 핵심 수정: 프로그레스 바 CSS ── */
    .prog-row {{ display: flex; align-items: center; margin-bottom: 0.5rem; gap: 1rem; }}
    .prog-label {{ width: 55px; font-size: 0.75rem; color: #CBD5E1; text-align: left; flex-shrink: 0; }}
    .prog-bar-bg {{ flex: 1; height: 10px; background: rgba(255,255,255,0.08); border-radius: 6px; overflow: hidden; }}
    .prog-bar-fill {{ height: 100%; background: linear-gradient(90deg, #0284C7, #38BDF8); border-radius: 6px; box-shadow: 0 0 10px rgba(56,189,248,0.5); }}
    .prog-val {{ width: 45px; font-size: 0.8rem; font-weight: 700; color: #FFF; text-align: right; flex-shrink: 0; }}

    .status-item {{ display:flex; justify-content:space-between; margin-bottom:1.2rem; align-items:center; }}
    .status-label {{ color:#CBD5E1; font-size:0.9rem; }}
    .status-val-wrap {{ display:flex; align-items:baseline; gap:0.2rem; }}
    .status-val {{ font-weight:800; font-size: 1.1rem; }}
    .status-na {{ color:rgba(148,163,184,0.45); font-weight:500; }}

    .btn-card-flex {{
        display: flex; flex-direction: column; justify-content: space-around;
        align-items: center; text-align: center; height: 100%; flex: 1;
    }}
    .ready-btn {{
        background: rgba(14,165,233,0.15); border: 1px solid #0EA5E9;
        color: #0EA5E9; padding: 0.7rem 2.5rem; border-radius: 25px;
        font-weight: 700; font-size:0.9rem; margin-top: 1rem; transition: all 0.2s;
    }}
    .ready-btn:hover {{ background: rgba(14,165,233,0.25); box-shadow: 0 0 15px rgba(14,165,233,0.4); }}
    </style>
    """)

    # ── 에셋 로딩 ──
    check_icon_b64 = load_icon("check")

    # ── 데이터 로딩 ──
    d1   = safe(_card_kpi1)
    d2   = safe(_card_kpi2)
    d3   = safe(_card_kpi3)
    d4   = safe(_card_kpi4)
    d5   = safe(_card_kpi5)
    d6   = safe(_card_kpi6)
    d7   = safe(_card_kpi7)
    dp1  = safe(_card_proc1)
    dp3  = safe(_card_proc3)
    dp4  = safe(_card_proc4)
    dp2i = safe(_card_proc2_delays)

    능률실적  = d1.get("능률실적")
    실동률실적 = d1.get("실동률실적")

    # ══════════════════════════════════════════════════════════
    #  [1행] 4칸 균등: kpi_1 / kpi_6 / kpi_2 / kpi_3(준비중)
    # ══════════════════════════════════════════════════════════
    row1 = st.columns(4)

    with row1[0]:
        # ① 능률실적·실동률실적 모두 ×100 → XX.X% 소수점 1자리, 나란히 같은 폰트
        능률_pct = (능률실적 * 100) if 능률실적 is not None else None
        실동률_pct = (실동률실적 * 100) if 실동률실적 is not None else None
        능률_str = fv(능률_pct, ".1f")
        실동_str = fv(실동률_pct, ".1f")
        _val_style = "font-size:2.2rem; font-weight:800; color:#10B981; font-family:'Segoe UI',sans-serif; line-height:1.1;"
        _lbl_style = "font-size:0.72rem; color:#94A3B8; font-weight:500; margin-bottom:0.25rem;"
        _unit_style = "font-size:1.1rem; color:#64748B; font-weight:600;"
        st.html(
            f'<a href="/kpi_1" target="_self" class="card-link" style="display:block; height:100%;">'
            f'<div class="neo-card glow-green">'
            f'<div class="top-card-title" style="margin-bottom:0.8rem;">직영 능률/실동률 현황</div>'
            f'<div style="display:flex; gap:1.5rem; align-items:flex-end; flex:1;">'
            f'  <div>'
            f'    <div style="{_lbl_style}">능 률</div>'
            f'    <div style="{_val_style}">{능률_str}<span style="{_unit_style}">%</span></div>'
            f'  </div>'
            f'  <div style="width:1px; background:rgba(255,255,255,0.08); align-self:stretch;"></div>'
            f'  <div>'
            f'    <div style="{_lbl_style}">실동률</div>'
            f'    <div style="{_val_style}">{실동_str}<span style="{_unit_style}">%</span></div>'
            f'  </div>'
            f'</div>'
            f'</div></a>'
        )

    with row1[1]:
        # ② 인도임박 호선 수 / 잔여 punch 수 나란히 같은 폰트
        remain   = d6.get("remain", 0)
        proj_cnt = d6.get("proj_cnt", 0)
        _val_o = "font-size:2.2rem; font-weight:800; color:#F59E0B; font-family:'Segoe UI',sans-serif; line-height:1.1;"
        _lbl_o = "font-size:0.72rem; color:#94A3B8; font-weight:500; margin-bottom:0.25rem;"
        _unit_o = "font-size:1.1rem; color:#64748B; font-weight:600;"
        st.html(
            f'<a href="/kpi_6" target="_self" class="card-link" style="display:block; height:100%;">'
            f'<div class="neo-card glow-orange">'
            f'<div class="top-card-title" style="margin-bottom:0.8rem;">인도호선 punch 현황</div>'
            f'<div style="display:flex; gap:1.5rem; align-items:flex-end; flex:1;">'
            f'  <div>'
            f'    <div style="{_lbl_o}">인도임박 호선</div>'
            f'    <div style="{_val_o}">{proj_cnt:,}<span style="{_unit_o}">척</span></div>'
            f'  </div>'
            f'  <div style="width:1px; background:rgba(255,255,255,0.08); align-self:stretch;"></div>'
            f'  <div>'
            f'    <div style="{_lbl_o}">잔여 Punch</div>'
            f'    <div style="{_val_o}">{remain:,}<span style="{_unit_o}">건</span></div>'
            f'  </div>'
            f'</div>'
            f'</div></a>'
        )

    with row1[2]:
        # ③ kpi_2: 글로벌 BEP 실적 — KPI_2 화면의 'YYYY-MM BEP 현황' 테이블 달성률
        g1 = d2.get("1그룹_달성률")
        g2 = d2.get("2그룹_달성률")
        bep_월 = d2.get("월") or ""

        g1_str = fv(g1, ".1f")
        g2_str = fv(g2, ".1f")

        def _달성률_색(v):
            try:
                f = float(v)
                return "#10B981" if f >= 100 else ("#F59E0B" if f >= 90 else "#EF4444")
            except Exception:
                return "#94A3B8"

        g1_c = _달성률_색(g1)
        g2_c = _달성률_색(g2)

        _lbl_b = "font-size:0.72rem; color:#94A3B8; font-weight:500; margin-bottom:0.25rem;"
        _unit_b = "font-size:1.1rem; font-weight:600;"
        _타이틀 = f"📊 {bep_월} BEP 현황" if bep_월 else "📊 BEP 현황"

        st.html(
            f'<a href="/kpi_2" target="_self" class="card-link" style="display:block; height:100%;">'
            f'<div class="neo-card glow-blue">'
            f'<div class="top-card-title" style="margin-bottom:0.8rem;">{_타이틀}</div>'
            f'<div style="display:flex; gap:1.5rem; align-items:flex-end; flex:1;">'
            f'  <div>'
            f'    <div style="{_lbl_b}">1그룹 달성률</div>'
            f'    <div style="font-size:2.2rem; font-weight:800; color:{g1_c}; font-family:\'Segoe UI\',sans-serif; line-height:1.1;">'
            f'      {g1_str}<span style="{_unit_b} color:{g1_c};">%</span>'
            f'    </div>'
            f'  </div>'
            f'  <div style="width:1px; background:rgba(255,255,255,0.08); align-self:stretch;"></div>'
            f'  <div>'
            f'    <div style="{_lbl_b}">2그룹 달성률</div>'
            f'    <div style="font-size:2.2rem; font-weight:800; color:{g2_c}; font-family:\'Segoe UI\',sans-serif; line-height:1.1;">'
            f'      {g2_str}<span style="{_unit_b} color:{g2_c};">%</span>'
            f'    </div>'
            f'  </div>'
            f'</div>'
            f'</div></a>'
        )

    with row1[3]:
        # ④ kpi_3: 협력사 정도율 — KPI_3 방사형 그래프와 동일한 가중평균
        items = d3.get("items", []) if isinstance(d3, dict) else []

        def _정도율_색(v):
            try:
                f = float(v)
                return "#10B981" if f >= 100 else ("#F59E0B" if f >= 90 else "#EF4444")
            except Exception:
                return "#94A3B8"

        cells_html = ""
        for idx, it in enumerate(items):
            name  = it.get("name") or "-"
            v     = it.get("정도율")
            v_str = fv(v, ".1f")
            c     = _정도율_색(v)
            if idx > 0:
                cells_html += (
                    '<div style="width:1px; background:rgba(255,255,255,0.08); '
                    'align-self:stretch;"></div>'
                )
            cells_html += (
                f'<div style="flex:1; min-width:0; text-align:center;">'
                f'  <div style="font-size:0.7rem; color:#94A3B8; font-weight:500;'
                f' margin-bottom:0.25rem;">{name}</div>'
                f'  <div style="font-size:1.4rem; font-weight:800; color:{c};'
                f" font-family:'Segoe UI',sans-serif; line-height:1.1;\">"
                f'    {v_str}<span style="font-size:0.8rem; font-weight:600;">%</span>'
                f'  </div>'
                f'</div>'
            )

        if not cells_html:
            cells_html = (
                '<div style="flex:1; text-align:center; color:#94A3B8;'
                ' font-size:0.85rem;">데이터 없음</div>'
            )

        st.html(
            f'<a href="/kpi_3" target="_self" class="card-link" style="display:block; height:100%;">'
            f'<div class="neo-card glow-cyan">'
            f'<div class="top-card-title" style="margin-bottom:0.8rem;">🤝 협력사 실적 예측 정도율</div>'
            f'<div style="display:flex; gap:0.6rem; align-items:flex-end; flex:1;">'
            f'{cells_html}'
            f'</div>'
            f'</div></a>'
        )

    st.html("<div style='height:1.5rem;'></div>")

    # ══════════════════════════════════════════════════════════
    #  [2행] 5:3:4 비율: kpi_5 / kpi_7 / proc_2(금주 운반선 주요 검사)
    # ══════════════════════════════════════════════════════════
    row2 = st.columns(3)

    with row2[0]:
        # ④ 섹션 타이틀: 인도임박 호선 공수 Progress
        projs = d5.get("projects", [])
        display_projs = projs[:4]
        bars_html = ""
        for i in range(4):
            if i < len(display_projs):
                p = display_projs[i]
                prog = float(p.get("Progress(%)", 0))
                bars_html += (
                    f'<div class="prog-row">'
                    f'<span class="prog-label">{p["프로젝트"]}</span>'
                    f'<div class="prog-bar-bg"><div class="prog-bar-fill" style="width:{prog:.1f}%;"></div></div>'
                    f'<span class="prog-val">{prog:.1f}%</span>'
                    f'</div>'
                )
            else:
                bars_html += (
                    '<div class="prog-row">'
                    '<span class="prog-label">선번 대기</span>'
                    '<div class="prog-bar-bg"></div>'
                    '<span class="prog-val">-</span>'
                    '</div>'
                )

        st.html(
            f'<a href="/kpi_5" target="_self" class="card-link" style="display:block; height:100%;">'
            f'<div class="neo-card" style="min-height:auto; justify-content:flex-start; padding:1.5rem 1.8rem;">'
            f'<div class="section-title">📋 인도임박 호선 공수 Progress</div>'
            f'<div style="margin-top:0.8rem;">{bars_html}</div>'
            f'</div></a>'
        )

    with row2[1]:
        # 특수선 Total Progress 달성율 (호선 수에 따라 유동)
        ships = dp3.get("ships", [])
        bars_html = ""
        if ships:
            for s in ships:
                prog = float(s.get("달성율", 0))
                bars_html += (
                    f'<div class="prog-row">'
                    f'<span class="prog-label">{s["호선"]}</span>'
                    f'<div class="prog-bar-bg"><div class="prog-bar-fill" style="width:{min(prog, 100):.1f}%;"></div></div>'
                    f'<span class="prog-val">{prog:.1f}%</span>'
                    f'</div>'
                )
        else:
            bars_html = '<div style="color:#64748B; font-size:0.85rem; padding:1rem 0;">데이터 없음</div>'

        st.html(
            f'<a href="/proc_3" target="_self" class="card-link" style="display:block; height:100%;">'
            f'<div class="neo-card" style="min-height:auto; justify-content:flex-start; padding:1.5rem 1.8rem;">'
            f'<div class="section-title">⚙️ 특수선 Total Progress 달성률</div>'
            f'<div style="margin-top:0.8rem;">{bars_html}</div>'
            f'</div></a>'
        )

    with row2[2]:
        # ⑤ 섹션: 지연 작업 현황 — proc_2 '공정 지연 리스트(전체)' 와 동일 판정
        import pandas as pd
        df_week = dp2i if isinstance(dp2i, pd.DataFrame) else pd.DataFrame()

        if df_week.empty:
            table_html = (
                '<div style="text-align:center; color:#64748B; font-size:0.85rem;'
                ' padding:2rem 0;">✅ 지연된 작업이 없습니다.</div>'
            )
        else:
            thead = "".join(
                f'<th style="background:rgba(56,189,248,0.15); color:#38BDF8;'
                f' font-size:0.75rem; padding:0.3rem 0.5rem; font-weight:600;'
                f' text-align:left; white-space:nowrap;">{label}</th>'
                for label in df_week.columns
            )
            tbody = ""
            for idx, (_, row) in enumerate(df_week.iterrows()):
                bg = "rgba(255,255,255,0.03)" if idx % 2 == 0 else "transparent"
                cells = ""
                for col in df_week.columns:
                    val = row[col]
                    val_str = "-" if pd.isna(val) else str(val)
                    cells += (
                        f'<td style="padding:0.3rem 0.5rem; font-size:0.75rem;'
                        f' color:#CBD5E1; background:{bg}; white-space:nowrap;">'
                        f'{val_str}</td>'
                    )
                tbody += f"<tr>{cells}</tr>"

            # 헤더 sticky, 본문 스크롤. 높이는 부모 flex 가 결정 (max-height 고정값 미사용)
            # pointer-events:auto 로 .neo-card * 의 none 을 해제 (스크롤 가능)
            table_html = (
                f'<div class="proc2-delay-scroll" style="height:100%;'
                f' overflow-y:auto; overflow-x:auto; pointer-events:auto;'
                f' border:1px solid rgba(255,255,255,0.05); border-radius:8px;">'
                f'<table style="width:100%; border-collapse:collapse;'
                f' pointer-events:auto;">'
                f'<thead style="position:sticky; top:0; z-index:1;'
                f' background:rgba(15,23,42,0.95); backdrop-filter:blur(8px);'
                f' pointer-events:auto;">'
                f'<tr>{thead}</tr></thead>'
                f'<tbody style="pointer-events:auto;">{tbody}</tbody>'
                f'</table></div>'
            )

        # 행 수 표시 (지연 건수)
        _row_cnt = len(df_week) if not df_week.empty else 0
        _cnt_badge = (
            f'<span style="margin-left:0.5rem; padding:0.1rem 0.5rem;'
            f' background:rgba(239,68,68,0.15); color:#FCA5A5;'
            f' border-radius:10px; font-size:0.7rem; font-weight:700;">{_row_cnt:,}건</span>'
            if _row_cnt > 0 else ''
        )

        st.html(
            f'<a href="/proc_2" target="_self" class="card-link" style="display:block; height:100%;">'
            f'<div class="neo-card" style="max-height:280px; overflow:hidden;'
            f' justify-content:flex-start; display:flex; flex-direction:column;">'
            f'<div class="section-title" style="flex-shrink:0;">'
            f'⚠️ 지연 작업 현황{_cnt_badge}</div>'
            f'<div style="margin-top:0.5rem; flex:1 1 auto; min-height:0;'
            f' overflow:hidden;">{table_html}</div>'
            f'</div></a>'
        )

    st.html("<div style='height:1.5rem;'></div>")

    # ══════════════════════════════════════════════════════════
    #  [3행] 4칸 균등: proc_1 / proc_3(준비중) / kpi_4 / proc_4
    # ══════════════════════════════════════════════════════════
    row3 = st.columns(4)

    with row3[0]:
        # ⑥ 서브타이틀: 일일 작업허가서 미출력 현황
        not_printed = dp1.get("not_printed", 0)
        c_val = "text-red" if not_printed > 0 else "text-green"
        st.html(
            f'<a href="/proc_1" target="_self" class="card-link" style="display:block; height:100%;">'
            f'<div class="neo-card" style="flex-direction:row; justify-content:space-between; align-items:center;">'
            f'<div style="text-align:left;">'
            f'<div class="section-title" style="margin-bottom:0.5rem;">📝 일일 작업허가서 미출력 현황</div>'
            f'</div>'
            f'<div class="{c_val}" style="font-size:3.5rem; font-weight:800; line-height:1; font-family:\'Segoe UI\',sans-serif;">{not_printed}</div>'
            f'</div></a>'
        )

    with row3[1]:
        # 용접 불량률 (row2에서 이동)
        구조_r = fv(d7.get("구조_rate"), ".2f", na="Na")
        배관_r = fv(d7.get("배관_rate"), ".2f", na="Na")
        check_img_html = f'<img src="data:image/png;base64,{check_icon_b64}" width="16" alt="✓">' if check_icon_b64 else "🔸"

        st.html(
            f'<a href="/kpi_7" target="_self" class="card-link" style="display:block; height:100%;">'
            f'<div class="neo-card" style="min-height:auto; justify-content:flex-start;">'
            f'<div class="section-title">🔧 용접 불량률</div>'
            f'<div style="margin-top:1rem;">'
            f'<div class="status-item"><span class="status-label">{check_img_html} 구조</span>'
            f'<div class="status-val-wrap text-green"><span class="status-val">{구조_r}</span>'
            f'<span style="font-size:0.8rem; font-weight:500;">%</span></div></div>'
            f'<div class="status-item"><span class="status-label">{check_img_html} 배관</span>'
            f'<div class="status-val-wrap text-green"><span class="status-val">{배관_r}</span>'
            f'<span style="font-size:0.8rem; font-weight:500;">%</span></div></div>'
            f'</div></div></a>'
        )

    with row3[2]:
        # ⑦ 서브타이틀: 당일 마일스톤 기성 전망
        val = d4.get("total", 0)
        val_str = fv(val, ",.0f")
        st.html(
            f'<a href="/kpi_4" target="_self" class="card-link" style="display:block; height:100%;">'
            f'<div class="neo-card" style="flex-direction:row; justify-content:space-between; align-items:center;">'
            f'<div style="text-align:left;">'
            f'<div class="section-title" style="margin-bottom:0.5rem;">📅 당일 마일스톤 기성 전망</div>'
            f'</div>'
            f'<div style="font-size:2.8rem; font-weight:800; color:#FFF; line-height:1; font-family:\'Segoe UI\',sans-serif;">'
            f'{val_str}<span style="font-size:1.2rem; color:#64748B;">MH</span></div>'
            f'</div></a>'
        )

    with row3[3]:
        # ⑧ 서브타이틀: 자재 입고율 / 데이터: dp4 입고율(%)
        입고율  = float(dp4.get("입고율", 0.0))
        입고_cnt = dp4.get("입고_cnt", 0)
        신청_cnt = dp4.get("신청_cnt", 0)
        svg_proc4 = ring_svg(min(입고율, 100.0), "#0EA5E9", "📦")
        st.html(
            f'<a href="/proc_4" target="_self" class="card-link" style="display:block; height:100%;">'
            f'<div class="neo-card glow-blue">'
            f'<div class="top-card-flex">'
            f'<div><div class="top-card-title">전장 결선 자재 입고율</div>'
            f'<div class="top-card-value text-blue">{입고율:.1f}<span style="font-size:1.5rem;color:#64748B;">%</span></div>'
            f'<div class="top-card-sub">{입고_cnt:,} / {신청_cnt:,}건 입고 완료</div>'
            f'</div>'
            f'{svg_proc4}</div>'
            f'</div></a>'
        )

    st.html('<div class="footer"><span style="color:#fff;">L</span><span style="color:#fff;">Q</span> <span style="color:#38BDF8;">A</span><span style="color:#fff;">ll</span> <span style="color:#38BDF8;">I</span><span style="color:#fff;">n</span> <span style="color:#fff;">O</span><span style="color:#fff;">ne</span> v2.0 &nbsp;|&nbsp; Living Quarter Department</div>')


# ══════════════════════════════════════════════════════════
#  7. 하위 메뉴 팩토리 함수
# ══════════════════════════════════════════════════════════
def make_kpi_page_func(key, name, icon):
    def _render():
        render_back_button(page_home_obj)
        try:
            mod = __import__(f"pages.{key}", fromlist=["render"])
            mod.render()
        except Exception as e:
            logger.error("KPI 페이지 렌더링 오류 (%s): %s\n%s", key, e, traceback.format_exc())
            st.error("오류가 발생했습니다. 관리자에게 문의해 주세요.")
    return _render

def make_proc_page_func(key, name, icon):
    def _render():
        render_back_button(page_home_obj)
        try:
            mod = __import__(f"pages.{key}", fromlist=["render"])
            mod.render()
        except Exception as e:
            logger.error("공정 페이지 렌더링 오류 (%s): %s\n%s", key, e, traceback.format_exc())
            st.error("오류가 발생했습니다. 관리자에게 문의해 주세요.")
    return _render

# ══════════════════════════════════════════════════════════
#  8. st.navigation 라우팅 구성 및 실행
# ══════════════════════════════════════════════════════════
page_home_obj = st.Page(render_home, title="홈", url_path="home", default=True)

kpi_page_objs  = [st.Page(make_kpi_page_func(k, n, i),  title=n, url_path=k) for k, n, i in KPI_SUBMENUS]
proc_page_objs = [st.Page(make_proc_page_func(k, n, i), title=n, url_path=k) for k, n, i in PROCESS_SUBMENUS]
mgmt_page_objs = [st.Page(make_proc_page_func(k, n, i), title=n, url_path=k) for k, n, i in MGMT_SUBMENUS]

pages = {
    "메인": [page_home_obj],
    "KPI 상세": kpi_page_objs,
    "공정 관리 상세": proc_page_objs,
    "데이터 관리": mgmt_page_objs,
}

pg = st.navigation(pages, position="sidebar")
inject_common_ui(current_url_path=pg.url_path)

pg.run()