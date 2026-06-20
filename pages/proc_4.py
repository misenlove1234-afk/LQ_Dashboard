"""
╔══════════════════════════════════════════════════════════════════╗
║  담당자 : ___________  (본인 이름 작성)                          ║
║  항목   : [화면 전용] proc_4 - 선실 전장 호선별 자재 신청 현황   ║
║  작성일 : ___________                                            ║
╚══════════════════════════════════════════════════════════════════╝
"""

import re
import io
import logging
import traceback
import streamlit as st
import pandas as pd
import streamlit.components.v1 as components
from datetime import datetime

logger = logging.getLogger(__name__)

from data.proc_4_data import (
    load_data, calc_kpi, agg_by_activity, agg_by_maker,
    _is_신청완료, _is_입고완료,
)

# ══════════════════════════════════════════════════════════
#  CSS
# ══════════════════════════════════════════════════════════
_CSS = """
<style>
/* ── 사이드바 다크 네이비 ── */
[data-testid="stSidebar"] { background-color: #0d1b2e !important; min-width: 280px; }
[data-testid="stSidebar"] * { color: #e2e8f0 !important; }
[data-testid="stSidebar"] div[data-baseweb="select"] > div,
[data-testid="stSidebar"] div[data-baseweb="base-input"] > input {
    background-color: #1e293b !important;
    color: #ffffff !important;
    -webkit-text-fill-color: #ffffff !important;
    border-color: #334155 !important;
}
[data-testid="stSidebar"] span[data-baseweb="tag"] {
    background-color: #1d4ed8 !important; color: #ffffff !important;
}
[data-testid="stSidebar"] .stButton button {
    background-color: #1e3a5f !important;
    border: 1px solid #3b82f6 !important; color: #7dd3fc !important;
    margin-top: 10px; /* 초기화 버튼 상단 여유 공간 약간 추가 */
}
[data-testid="stSidebar"] .stButton button:hover {
    background-color: #1d4ed8 !important; color: #ffffff !important;
}

/* ── 메인 ── */
h1, h2, h3, h4, h5, h6, p, label { color: #ffffff !important; }

/* ── KPI 카드 ── */
.kpi-card {
    background: #1e293b; border-radius: 12px; padding: 18px 22px;
    box-shadow: 0 4px 6px rgba(0,0,0,0.35); border-left: 5px solid #3b82f6;
    margin-bottom: 6px;
}
.kpi-card.green  { border-left-color: #22c55e; }
.kpi-card.orange { border-left-color: #f97316; }
.kpi-label { font-size: 13px; color: #cbd5e1 !important; font-weight: 500; margin-bottom: 4px; }
.kpi-value { font-size: 28px; font-weight: 700; color: #ffffff !important; }
.kpi-sub   { font-size: 12px; color: #94a3b8 !important; margin-top: 4px; }

/* ── 입고율 카드 클릭 버튼 ── */
button[data-testid="baseButton-secondary"].kpi-btn {
    background: transparent !important;
    border: none !important; color: #38bdf8 !important;
    font-size: 12px !important; padding: 2px 0 0 !important;
    text-decoration: underline !important; cursor: pointer !important;
}

/* ── 섹션 타이틀 ── */
.section-title {
    font-size: 15px; font-weight: 700; color: #ffffff !important;
    border-bottom: 2px solid #3b82f6; padding-bottom: 6px;
    margin-bottom: 14px; margin-top: 18px;
}
/* ── 데이터프레임 다크모드 ── */
[data-testid="stDataFrame"] { background-color: #1e293b !important; }
[data-testid="stDataFrame"] * { color: #e2e8f0 !important; }
</style>
"""

# 다크모드 표 공통 스타일
_DARK_PROPS = {
    "background-color": "#1e293b",
    "color": "#e2e8f0",
    "border-color": "#334155",
}


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]*>", "", text).strip()


def _clean(key: str, valid: list) -> None:
    """연쇄 필터: 유효하지 않은 이전 선택값 제거"""
    prev = st.session_state.get(key, [])
    cleaned = [v for v in prev if v in valid]
    if cleaned != prev:
        st.session_state[key] = cleaned


# ══════════════════════════════════════════════════════════
#  미입고 자재 다이얼로그
# ══════════════════════════════════════════════════════════
@st.dialog("📦 미입고 자재 목록", width="large")
def _dialog_미입고(df: pd.DataFrame):
    """신청일이 있고 PLT고유번호가 없는 자재 = 신청했으나 아직 미입고 자재 목록"""
    mask = df["신청일"].notna() & ~_is_입고완료(df["PLT고유번호"])
    df_미입고 = df[mask].copy()
    total = len(df_미입고)

    st.markdown(
        f"<p style='color:#94a3b8; font-size:13px;'>"
        f"현재 조회 조건 기준 <b style='color:#f97316;'>{total:,}건</b> 미입고 "
        f"(PLT고유번호 미부여)</p>",
        unsafe_allow_html=True,
    )

    show_cols = [
        "액티비티", "자재번호", "자재내역", "자재내역상세",
        "Elem.번호", "TAG번호", "신청일", "요청일",
        "신청자", "지연일", "조달담당자", "현물담당자", "구매담당자",
    ]
    show_cols = [c for c in show_cols if c in df_미입고.columns]
    detail = df_미입고[show_cols].copy()

    for dc in ["자재소요일", "입고예정일"]:
        if dc in detail.columns:
            detail[dc] = pd.to_datetime(detail[dc], errors="coerce").dt.strftime("%Y-%m-%d")

    fmt = {"BOM수량": "{:,.0f}"}
    if "지연일" in detail.columns:
        fmt["지연일"] = "{:.0f}"

    # 지연일 기준 내림차순 정렬
    if "지연일" in detail.columns:
        detail = detail.sort_values("지연일", ascending=False)

    # 엑셀 다운로드 버튼
    _xls_buf = io.BytesIO()
    with pd.ExcelWriter(_xls_buf, engine='openpyxl') as _w:
        detail.to_excel(_w, sheet_name='미입고자재', index=False)
    st.download_button(
        "📥 엑셀 다운로드",
        data=_xls_buf.getvalue(),
        file_name=f"미입고자재목록_{datetime.now().strftime('%Y%m%d')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="proc4_미입고_xls_dl",
    )

    def _row_color(row):
        if "지연일" in row.index and pd.notna(row["지연일"]) and row["지연일"] > 0:
            return ["background-color:#3b1f1f; color:#fca5a5"] * len(row)
        return [f"background-color:{_DARK_PROPS['background-color']}; color:{_DARK_PROPS['color']}"] * len(row)

    st.dataframe(
        detail.style.apply(_row_color, axis=1).format(fmt),
        use_container_width=True,
        hide_index=True,
        height=500,
    )


# ══════════════════════════════════════════════════════════
#  메인 렌더링
# ══════════════════════════════════════════════════════════
def render():
    st.markdown(_CSS, unsafe_allow_html=True)

    # 사이드바 자동 확장 (첫 진입)
    if "proc4_sidebar_opened" not in st.session_state:
        st.session_state["proc4_sidebar_opened"] = True
        components.html("""
        <script>
        (function() {
            var n = 0;
            function open() {
                try {
                    var b = window.parent.document.querySelector(
                        '[data-testid="collapsedControl"] button');
                    if (b) { b.click(); return; }
                } catch(e) {}
                if (++n < 40) setTimeout(open, 100);
            }
            open();
        })();
        </script>
        """, height=1, scrolling=False)

    # 데이터 로드
    try:
        df_raw = load_data()
    except Exception as e:
        logger.error("자재 데이터 로드 실패: %s\n%s", e, traceback.format_exc())
        st.error("데이터 로드에 실패했습니다. 관리자에게 문의해 주세요.")
        return
    if df_raw is None or df_raw.empty:
        st.warning("데이터가 없습니다.")
        return

    # ══════════════════════════════════════════════════════
    #  사이드바 — 연쇄 필터
    # ══════════════════════════════════════════════════════
    with st.sidebar:
        # ① 호선 (전체 옵션 추가)
        호선_원목록 = sorted(df_raw["호선"].dropna().astype(str).unique().tolist())
        호선_목록   = ["전체"] + 호선_원목록
        # session_state 정리: 더 이상 존재하지 않는 호선/문자열 옵션 제거
        _saved = st.session_state.get("proc4_호선")
        if isinstance(_saved, str):  # 구버전(selectbox) 잔재
            st.session_state["proc4_호선"] = (
                ["전체"] if _saved == "전체" else ([_saved] if _saved in 호선_원목록 else ["전체"])
            )
        elif isinstance(_saved, list):
            st.session_state["proc4_호선"] = [
                v for v in _saved if v == "전체" or v in 호선_원목록
            ]
        sel_호선 = st.multiselect(
            "🚢 호선 (다중 선택 가능, '전체' 또는 비워두면 모든 호선)",
            호선_목록, key="proc4_호선",
        )

        # '전체' 포함 또는 빈 선택 → 모든 호선 / 그 외 → 선택된 호선만
        _전체모드 = (not sel_호선) or ("전체" in sel_호선)
        if _전체모드:
            df_c = df_raw.copy()
        else:
            df_c = df_raw[df_raw["호선"].astype(str).isin(sel_호선)].copy()

        # ② 액티비티
        act_opts = sorted(df_c["액티비티"].dropna().unique())
        _clean("proc4_activity", act_opts)
        sel_act = st.multiselect(
            f"📋 액티비티 ({len(act_opts)}개)",
            act_opts, key="proc4_activity", placeholder="검색 후 선택…",
        )
        if sel_act:
            df_c = df_c[df_c["액티비티"].isin(sel_act)]

        # ③ Elem.번호
        elem_opts = sorted(df_c["Elem.번호"].dropna().astype(str).unique())
        _clean("proc4_elem", elem_opts)
        sel_elem = st.multiselect(
            f"🔢 Elem.번호 ({len(elem_opts)}개)",
            elem_opts, key="proc4_elem", placeholder="검색 후 선택…",
        )
        if sel_elem:
            df_c = df_c[df_c["Elem.번호"].astype(str).isin(sel_elem)]

        # ④ TAG번호
        tag_opts = sorted(df_c["TAG번호"].dropna().astype(str).unique())
        _clean("proc4_tag", tag_opts)
        sel_tag = st.multiselect(
            f"🏷️ TAG번호 ({len(tag_opts)}개)",
            tag_opts, key="proc4_tag", placeholder="검색 후 선택…",
        )
        if sel_tag:
            df_c = df_c[df_c["TAG번호"].astype(str).isin(sel_tag)]

        # ⑤ 자재번호
        mat_opts = sorted(df_c["자재번호"].dropna().astype(str).unique())
        _clean("proc4_mat", mat_opts)
        sel_mat = st.multiselect(
            f"📦 자재번호 ({len(mat_opts)}개)",
            mat_opts, key="proc4_mat", placeholder="검색 후 선택…",
        )
        if sel_mat:
            df_c = df_c[df_c["자재번호"].astype(str).isin(sel_mat)]

        # ⑥ 자재내역
        raw_kw2 = st.text_input("🔍 자재내역 검색", placeholder="검색어 입력", key="proc4_keyword2")
        keyword2 = _strip_html(raw_kw2)
        if keyword2:
            df_c = df_c[df_c["자재내역"].astype(str).str.contains(keyword2, case=False, na=False)]

        # ⑦ 자재내역상세
        raw_kw = st.text_input("🔍 자재내역상세 검색", placeholder="검색어 입력", key="proc4_keyword")
        keyword = _strip_html(raw_kw)
        if keyword:
            df_c = df_c[df_c["자재내역상세"].astype(str).str.contains(keyword, case=False, na=False)]

        # ⑧ 제작회사
        maker_opts = sorted(df_c["제작회사"].dropna().astype(str).unique())
        _clean("proc4_maker", maker_opts)
        sel_maker = st.multiselect(
            f"🏭 제작회사 ({len(maker_opts)}개)",
            maker_opts, key="proc4_maker", placeholder="검색 후 선택…",
        )
        if sel_maker:
            df_c = df_c[df_c["제작회사"].astype(str).isin(sel_maker)]

        # ⑨ 신청여부
        sel_req = st.radio(
            "📌 신청여부",
            ["모두", "신청 완료", "신청 가능"],
            index=0, key="proc4_req",
        )
        if sel_req == "신청 완료":
            df_c = df_c[_is_신청완료(df_c["신청자"])]
        elif sel_req == "신청 가능":
            df_c = df_c[~_is_신청완료(df_c["신청자"])]

        # ⑩ 입고여부
        sel_recv = st.radio(
            "📦 입고여부",
            ["모두", "입고 완료", "미입고"],
            index=0, key="proc4_recv",
        )
        if sel_recv == "입고 완료":
            df_c = df_c[_is_입고완료(df_c["PLT고유번호"])]
        elif sel_recv == "미입고":
            df_c = df_c[~_is_입고완료(df_c["PLT고유번호"])]

        # ⑪ 조회 버튼
        if st.button("🔍 조회", use_container_width=True,
                     key="proc4_search", type="primary"):
            st.session_state["proc4_queried"] = True

        # ⑫ 초기화 (호선 초기화 + 조회 상태 리셋)
        if st.button("↺ 필터 초기화", use_container_width=True, key="proc4_reset"):
            st.session_state["proc4_호선"] = []
            for k in ["proc4_activity", "proc4_elem", "proc4_tag", "proc4_mat", "proc4_maker"]:
                st.session_state[k] = []
            for k in ["proc4_keyword", "proc4_keyword2"]:
                st.session_state[k] = ""
            st.session_state["proc4_req"] = "모두"
            st.session_state["proc4_recv"] = "모두"
            st.session_state["proc4_queried"] = False
            st.rerun()

        if st.session_state.get("proc4_queried", False):
            st.markdown(
                f"<p style='color:#94a3b8;font-size:12px;margin-top:8px;'>"
                f"조회 결과: <b style='color:#38bdf8;'>{len(df_c):,}건</b></p>",
                unsafe_allow_html=True,
            )

    # 조회 버튼 누르기 전: 안내 메시지만 표시
    if not st.session_state.get("proc4_queried", False):
        st.markdown(
            "<div style='text-align:center; margin-top:80px; color:#64748B;'>"
            "<div style='font-size:2.5rem;'>🔍</div>"
            "<div style='font-size:1.1rem; font-weight:600; margin-top:12px; color:#94A3B8;'>"
            "조회 조건을 설정하고<br>사이드바의 <b style='color:#38BDF8;'>조회</b> 버튼을 눌러주세요.</div>"
            "</div>",
            unsafe_allow_html=True,
        )
        return

    df = df_c

    if df.empty:
        st.warning("선택한 조건에 맞는 데이터가 없습니다.")
        return

    # ══════════════════════════════════════════════
    #  KPI 카드 3개
    # ══════════════════════════════════════════════
    kpi = calc_kpi(df)
    c1, c2, c3 = st.columns(3)

    with c1:
        # 호선 표시: 전체 모드 → "전체" / 1개 → 그대로 / 2개 이상 → "N개 호선"
        if _전체모드:
            _호선_표기 = "전체"
            _호선_sub  = f"전체 호선 {len(호선_원목록):,}개"
        elif len(sel_호선) == 1:
            _호선_표기 = sel_호선[0]
            _호선_sub  = "조회 기준 호선"
        else:
            _호선_표기 = f"{len(sel_호선)}개"
            _호선_sub  = ", ".join(sel_호선[:3]) + (" 외" if len(sel_호선) > 3 else "")
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">🚢 호선명</div>
            <div class="kpi-value">{_호선_표기}</div>
            <div class="kpi-sub">{_호선_sub}</div>
        </div>""", unsafe_allow_html=True)

    with c2:
        st.markdown(f"""
        <div class="kpi-card green">
            <div class="kpi-label">📦 자재입고율</div>
            <div class="kpi-value">{kpi['입고율']}%</div>
            <div class="kpi-sub">PLT고유번호 부여 / 신청완료 ({kpi['신청_cnt']:,}건)</div>
        </div>""", unsafe_allow_html=True)
        # 클릭 → 미입고 자재 다이얼로그
        if st.button("🔍 미입고 자재 목록 보기", key="proc4_btn_미입고",
                     use_container_width=True):
            _dialog_미입고(df)

    with c3:
        st.markdown(f"""
        <div class="kpi-card orange">
            <div class="kpi-label">📋 자재신청율</div>
            <div class="kpi-value">{kpi['신청율']}%</div>
            <div class="kpi-sub">신청자 이름 있음 / 전체</div>
        </div>""", unsafe_allow_html=True)

    # ══════════════════════════════════════════════
    #  탭 영역 구성 (종합 현황 / 최근 30일 BOM)
    # ══════════════════════════════════════════════
    tab1, tab2 = st.tabs(["📊 종합 현황", "🆕 최근 30일 BOM 입력 자재"])
    
    # ── 첫 번째 탭: 기존 집계 테이블 및 상세 내역 ──
    with tab1:
        left_col, right_col = st.columns(2)

        with left_col:
            st.markdown('<div class="section-title">📊 액티비티별 집계</div>', unsafe_allow_html=True)
            act_df = agg_by_activity(df)

            def _hi_sum(row):
                if row["액티비티"] == "합계":
                    return ["background-color:#1d4ed8;color:#fff;font-weight:700"] * len(row)
                return [f"background-color:{_DARK_PROPS['background-color']}; color:{_DARK_PROPS['color']}"] * len(row)

            st.dataframe(
                act_df.style.apply(_hi_sum, axis=1)
                      .format({"신청율(%)": "{:.1f}", "입고율(%)": "{:.1f}", "입고수량": "{:,.0f}"}),
                use_container_width=True, hide_index=True, height=320,
            )

        with right_col:
            st.markdown('<div class="section-title">🏭 제작회사별 집계</div>', unsafe_allow_html=True)
            maker_df = agg_by_maker(df)
            st.dataframe(
                maker_df.style.set_properties(**_DARK_PROPS).format({
                    "BOM수량합계": "{:,.0f}", "입고율(%)": "{:.1f}",
                    "입고수량": "{:,.0f}",   "평균지연일": "{:.1f}",
                }),
                use_container_width=True, hide_index=True, height=320,
            )

        st.markdown('<div class="section-title">📋 상세 자재 목록</div>', unsafe_allow_html=True)

        detail_cols = [
            "호선", "액티비티", "Elem.번호", "자재번호", "자재내역", "자재내역상세", "TAG번호",
            "BOM수량", "신청일", "요청일", "신청자", "요청장소_3", "인계일",
            "현물담당자", "조달담당자",
        ]
        detail_cols = [c for c in detail_cols if c in df.columns]
        detail_df   = df[detail_cols].copy()

        # 요청장소3 컬럼 → 화면 헤드명은 '요청장소'로 표시
        if "요청장소_3" in detail_df.columns:
            detail_df = detail_df.rename(columns={"요청장소_3": "요청장소"})

        # 날짜 컬럼 포맷
        for _dc in ["신청일", "요청일", "인계일"]:
            if _dc in detail_df.columns:
                detail_df[_dc] = pd.to_datetime(detail_df[_dc], errors="coerce").dt.strftime("%Y-%m-%d")

        try:
            st.dataframe(
                detail_df.style.set_properties(**_DARK_PROPS).format({"BOM수량": "{:,.0f}"}),
                use_container_width=True, hide_index=True, height=440,
            )
            st.caption(f"총 {len(df):,}건 표시 중")
        except Exception:
            st.warning(
                "📋 데이터가 너무 많아 표시할 수 없습니다.  \n"
                "사이드바에서 **호선, 액티비티, 자재번호** 등 조회 조건을 좁혀주세요."
            )

    # ── 두 번째 탭: 최근 30일 BOM 입력 자재 ──
    with tab2:
        st.markdown('<div class="section-title">🆕 최근 30일 BOM 입력 자재</div>', unsafe_allow_html=True)
        
        if "BOM입력일" in df.columns:
            # 30일 전 날짜 계산
            today = pd.to_datetime('today').normalize()
            thirty_days_ago = today - pd.Timedelta(days=30)
            
            # 30일 이내 데이터 필터링
            recent_bom_df = df[df["BOM입력일"] >= thirty_days_ago].copy()
            
            # 요청하신 컬럼 리스트
            target_cols = [
                "호선", "자재번호", "액티비티", "자재내역", "자재내역상세", 
                "Elem.번호", "TAG번호", "BOM수량", "설계담당자", "제작회사"
            ]
            
            # 실제 데이터프레임에 존재하는 컬럼만 선택
            show_cols = [c for c in target_cols if c in recent_bom_df.columns]
            
            if recent_bom_df.empty:
                st.info("최근 30일 이내에 BOM이 입력된 자재가 없습니다.")
            else:
                # BOM입력일을 기준으로 최신순 정렬
                recent_bom_df = recent_bom_df.sort_values(by="BOM입력일", ascending=False)

                try:
                    st.dataframe(
                        recent_bom_df[show_cols].style.set_properties(**_DARK_PROPS).format({"BOM수량": "{:,.0f}"}),
                        use_container_width=True, hide_index=True, height=600,
                    )
                    st.caption(f"최근 30일 이내 BOM 입력 건수: {len(recent_bom_df):,}건")
                except Exception:
                    st.warning(
                        "📋 데이터가 너무 많아 표시할 수 없습니다.  \n"
                        "사이드바에서 **호선, 액티비티, 자재번호** 등 조회 조건을 좁혀주세요."
                    )
        else:
            st.warning("데이터 원본에 'BOM입력일' 컬럼이 존재하지 않아 조회할 수 없습니다.")