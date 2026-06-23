"""
[화면 전용] 공정회의록 탭 — 호선별 계산 일정 열람 + 원클릭 재계산
"""

import datetime
import logging
import traceback
import pandas as pd
import streamlit as st

from data.meeting_ref_data import (
    get_vessels, get_anchor_30stg, get_anchor_50stg,
    get_deck_order, get_block_deck_map, init_tables,
)
from data.meeting_calc import get_schedule, init_schedule_table

logger = logging.getLogger(__name__)

# ─── 표시할 공종 코드 목록 ─────────────────────────────────────
_30STG_CODES = ["blk_in","족장설치","관철","덕트","전장","도장","배선","뒤집기","blk_out"]
_30STG_LABEL = {
    "blk_in": "블럭\n입고", "족장설치": "족장\n설치", "관철": "관철", "덕트": "덕트",
    "전장": "전장", "도장": "선도장", "배선": "배선", "뒤집기": "뒤집기", "blk_out": "블럭\n탑재",
}
_50STG_CODES = [
    "목의화기1차","도장PB","도장TU","배선","보온",
    "목의화기2차","피복","BP검사","판넬설치","결선","가구","장판","스커트",
]
_INOUT_CODES = [
    "트렁크배선","윈도우설치","윈도우검사","내부배관검사",
    "외부배관검사","외판도장","외판족장철거","FLOOR도장",
    "탑재준비","탑재사열","인양","탑재",
]


# ─── 날짜 포맷 헬퍼 ──────────────────────────────────────────

def _safe_date(val) -> datetime.date | None:
    if val is None:
        return None
    try:
        s = str(val)[:10]
        if s in ("", "None", "NaT", "NaN", "nat"):
            return None
        return datetime.date.fromisoformat(s)
    except Exception:
        return None


def _md(d: datetime.date | None) -> str:
    """date → 'M/D'"""
    return f"{d.month}/{d.day}" if d else ""


def _cell_html(start_str, end_str) -> tuple[str, str]:
    """(표시 텍스트, 배경색 CSS) 반환"""
    today = datetime.date.today()
    s = _safe_date(start_str)
    e = _safe_date(end_str)
    if not s:
        return "-", ""
    text = f"{_md(s)}<br>~{_md(e)}" if e and s != e else _md(s)
    if e and e < today:
        bg = "background:#1a2535;"
    elif s and s <= today and (not e or e >= today):
        bg = "background:#1e3a5f;"
    else:
        bg = ""
    return text, bg


# ─── HTML 테이블 빌더 ─────────────────────────────────────────

def _html_table(col_headers: list[str], rows: list[dict]) -> str:
    """rows 구조:
      - 구분선: {"_sep": True, "_label": str, "_colspan": int}
      - 데이터행: {"_label": str, col_name: {"text": str, "bg": str}, ...}
    """
    th = "".join(
        f'<th style="white-space:nowrap;font-size:0.75rem;padding:0.4rem 0.5rem;">{h}</th>'
        for h in col_headers
    )
    body = ""
    for row in rows:
        if row.get("_sep"):
            cs = row.get("_colspan", len(col_headers))
            body += (
                f'<tr><td colspan="{cs}" style="'
                "background:#0a1628;color:#7dd3fc;font-weight:600;"
                "padding:0.25rem 0.6rem;font-size:0.78rem;"
                f'border-bottom:1px solid rgba(56,189,248,0.3);">{row["_label"]}</td></tr>'
            )
            continue
        tds = (
            f'<td style="font-weight:600;white-space:nowrap;'
            f'font-size:0.78rem;padding:0.35rem 0.5rem;">'
            f'{row.get("_label","")}</td>'
        )
        for h in col_headers[1:]:
            cell = row.get(h, {})
            text = cell.get("text", "-") if isinstance(cell, dict) else str(cell)
            bg   = cell.get("bg", "")   if isinstance(cell, dict) else ""
            tds += (
                f'<td style="text-align:center;font-size:0.73rem;'
                f'white-space:nowrap;padding:0.3rem 0.4rem;{bg}">{text}</td>'
            )
        body += f"<tr>{tds}</tr>"
    return (
        '<div class="dark-html-table-wrap" style="max-height:520px;overflow:auto;">'
        f'<table class="dark-html-table">'
        f"<thead><tr>{th}</tr></thead>"
        f"<tbody>{body}</tbody></table></div>"
    )


# ─── 공정표 생성 ─────────────────────────────────────────────

def _make_30stg_table(vessel_no: str, vessel_type: str, sched_df: pd.DataFrame) -> str:
    bdm = get_block_deck_map(vessel_type)
    dk_order_df = get_deck_order(vessel_type)
    dk_order = {r["deck"]: r["order_no"] for _, r in dk_order_df.iterrows()}

    if not bdm.empty:
        bdm = bdm.copy()
        bdm["_ord"] = bdm["deck"].map(dk_order).fillna(99)
        bdm = bdm.sort_values(["_ord", "block_no"])
        blocks = list(bdm["block_no"])
        deck_of = dict(zip(bdm["block_no"], bdm["deck"]))
    else:
        blocks = []
        deck_of = {}

    sched: dict[str, dict] = {}
    if not sched_df.empty:
        for _, r in sched_df[sched_df["stg"] == "30"].iterrows():
            sched.setdefault(str(r["area"]), {})[str(r["work_code"])] = (
                str(r["plan_start"])[:10] if r["plan_start"] else None,
                str(r["plan_end"])[:10]   if r["plan_end"]   else None,
            )

    headers = ["블럭"] + [_30STG_LABEL.get(c, c) for c in _30STG_CODES]
    rows: list[dict] = []
    cur_dk = None

    for blk in blocks:
        dk = deck_of.get(blk, "")
        if dk != cur_dk:
            rows.append({"_sep": True, "_label": f"▶ {dk}", "_colspan": len(headers)})
            cur_dk = dk
        row: dict = {"_label": blk}
        bs = sched.get(blk, {})
        for code in _30STG_CODES:
            lbl = _30STG_LABEL.get(code, code)
            val = bs.get(code)
            if val and val[0]:
                text, bg = _cell_html(val[0], val[1])
                row[lbl] = {"text": text, "bg": bg}
            else:
                row[lbl] = {"text": "-", "bg": ""}
        rows.append(row)

    return _html_table(headers, rows)


def _make_50stg_table(vessel_no: str, vessel_type: str, sched_df: pd.DataFrame) -> str:
    dk_order_df = get_deck_order(vessel_type)
    decks = list(dk_order_df.sort_values("order_no")["deck"])

    sched: dict[str, dict] = {}
    if not sched_df.empty:
        for _, r in sched_df[sched_df["stg"] == "50"].iterrows():
            sched.setdefault(str(r["area"]), {})[str(r["work_code"])] = (
                str(r["plan_start"])[:10] if r["plan_start"] else None,
                str(r["plan_end"])[:10]   if r["plan_end"]   else None,
            )

    anc50 = get_anchor_50stg(vessel_no)
    anc_map: dict[str, dict] = {}
    if not anc50.empty:
        for _, r in anc50.iterrows():
            anc_map[str(r["deck"])] = {
                "insp": _safe_date(r.get("inspection_date")),
            }

    headers = ["데크", "선각검사"] + _50STG_CODES
    rows: list[dict] = []

    for dk in decks:
        row: dict = {"_label": dk}
        # 선각검사 (앵커 기반)
        insp = anc_map.get(dk, {}).get("insp")
        row["선각검사"] = {"text": _md(insp) if insp else "-", "bg": _cell_html(insp, insp)[1] if insp else ""}

        # UPP-DK 는 의장 없음
        ds = sched.get(dk, {})
        for code in _50STG_CODES:
            if dk == "UPP-DK":
                row[code] = {"text": "—", "bg": "background:#111827;"}
                continue
            val = ds.get(code)
            if val and val[0]:
                text, bg = _cell_html(val[0], val[1])
                row[code] = {"text": text, "bg": bg}
            else:
                row[code] = {"text": "-", "bg": ""}
        rows.append(row)

    return _html_table(headers, rows)


def _make_inout_table(sched_df: pd.DataFrame) -> str:
    sched: dict[str, dict] = {}
    if not sched_df.empty:
        for _, r in sched_df[sched_df["stg"] == "inout"].iterrows():
            sched.setdefault(str(r["area"]), {})[str(r["work_code"])] = (
                str(r["plan_start"])[:10] if r["plan_start"] else None,
                str(r["plan_end"])[:10]   if r["plan_end"]   else None,
            )

    if not sched:
        return ""

    headers = ["구역"] + _INOUT_CODES
    rows: list[dict] = []
    for area, as_ in sched.items():
        row: dict = {"_label": area}
        for code in _INOUT_CODES:
            val = as_.get(code)
            if val and val[0]:
                text, bg = _cell_html(val[0], val[1])
                row[code] = {"text": text, "bg": bg}
            else:
                row[code] = {"text": "-", "bg": ""}
        rows.append(row)
    return _html_table(headers, rows)


# ─── 메인 렌더 함수 ───────────────────────────────────────────

def render_meeting_tab(current_user: str = "", is_admin: bool = False):
    """공정회의록 탭 렌더링 — proc_2.py 에서 호출"""

    st.markdown("##### 📋 공정회의록")

    # 테이블 초기화 (최초 접속 시 없으면 생성)
    try:
        init_tables()
        init_schedule_table()
    except Exception:
        pass

    # ── 호선 목록 로드 ────────────────────────────────
    try:
        vessels_df = get_vessels()
    except Exception as e:
        logger.error("호선 조회 오류: %s\n%s", e, traceback.format_exc())
        st.error("데이터 로드 오류가 발생했습니다. 관리자에게 문의해 주세요.")
        return

    if vessels_df.empty:
        st.info(
            "등록된 호선이 없습니다. "
            "**기준정보 탭 → 앵커 이벤트** 에서 호선을 먼저 등록해 주세요."
        )
        return

    vessel_no_list = list(vessels_df["vessel_no"])
    vtype_map = dict(zip(vessels_df["vessel_no"], vessels_df["vessel_type"]))

    # ── 헤더 행: 호선 선택 + 계산 버튼 ──────────────
    col_sel, col_btn = st.columns([3, 1])
    with col_sel:
        vessel_no = st.selectbox(
            "호선",
            vessel_no_list,
            key="meet_vessel_sel",
            label_visibility="collapsed",
        )
    vessel_type = vtype_map.get(vessel_no, "LNG")

    with col_btn:
        if is_admin:
            do_calc = st.button(
                "🔄 원클릭 계산",
                key="meet_calc_btn",
                type="primary",
                use_container_width=True,
                help="앵커 이벤트 기반으로 전체 공정을 자동 계산합니다.",
            )
        else:
            st.button(
                "🔒 계산 (관리자)",
                key="meet_calc_btn_locked",
                disabled=True,
                use_container_width=True,
            )
            do_calc = False

    # ── 앵커 현황 지표 ────────────────────────────────
    try:
        anc30 = get_anchor_30stg(vessel_no)
        anc50 = get_anchor_50stg(vessel_no)
        n_in   = int(anc30["blk_in_date"].notna().sum())   if not anc30.empty else 0
        n_out  = int(anc30["blk_out_date"].notna().sum())  if not anc30.empty else 0
        n_insp = int(anc50["inspection_date"].notna().sum()) if not anc50.empty else 0
        n_wall = int(anc50["wall_straight_date"].notna().sum()) if not anc50.empty else 0
    except Exception:
        anc30 = anc50 = pd.DataFrame()
        n_in = n_out = n_insp = n_wall = 0

    mc = st.columns(4)
    mc[0].metric("블럭입고 입력", f"{n_in}건")
    mc[1].metric("블럭탑재 입력", f"{n_out}건")
    mc[2].metric("선각검사 완료", f"{n_insp}건")
    mc[3].metric("WALL곡직 입력", f"{n_wall}건")

    # ── 원클릭 계산 실행 ─────────────────────────────
    if do_calc:
        with st.spinner("공정 일정 계산 중..."):
            try:
                from data.meeting_calc import calc_and_save
                res = calc_and_save(vessel_no)
            except Exception as e:
                logger.error("계산 엔진 오류: %s\n%s", e, traceback.format_exc())
                st.error("계산 중 오류가 발생했습니다. 관리자에게 문의해 주세요.")
                return
        if res["ok"]:
            st.success(
                f"✅ 계산 완료 — "
                f"30STG {res['30stg']}건 · 50STG {res['50stg']}건 · In/Out {res['inout']}건"
            )
            st.cache_data.clear()
            st.rerun()
        else:
            st.error(res.get("error", "계산 오류가 발생했습니다."))

    st.markdown('<hr style="border-color:rgba(56,189,248,0.15);">', unsafe_allow_html=True)

    # ── 계산 결과 조회 ────────────────────────────────
    try:
        sched_df = get_schedule(vessel_no)
    except Exception as e:
        logger.error("일정 조회 오류: %s\n%s", e, traceback.format_exc())
        sched_df = pd.DataFrame()

    if sched_df.empty:
        st.info(
            "💡 계산된 일정이 없습니다. "
            "앵커 이벤트를 입력한 후 **원클릭 계산** 버튼을 눌러 주세요."
        )
        if not anc30.empty or not anc50.empty:
            with st.expander("📎 입력된 앵커 이벤트", expanded=True):
                if not anc30.empty:
                    st.markdown("###### 30 STG — 블럭 입고/탑재일")
                    st.dataframe(anc30, use_container_width=True, height=200)
                if not anc50.empty:
                    st.markdown("###### 50 STG — 데크별 앵커")
                    st.dataframe(anc50, use_container_width=True, height=200)
        return

    # 마지막 계산 시각
    if "calc_at" in sched_df.columns and not sched_df["calc_at"].isna().all():
        last_calc = pd.to_datetime(sched_df["calc_at"]).max()
        st.caption(
            f"📅 마지막 계산: {last_calc.strftime('%Y-%m-%d %H:%M')} &nbsp;|&nbsp; "
            "🟦 진행 중 &nbsp; ▪ 완료 (어두운 색) &nbsp; 흰 색 예정"
        )

    # ── 서브 탭 ──────────────────────────────────────
    s30, s50, sio = st.tabs(["⚙️ 30 STG", "🏗️ 50 STG", "🔌 In/Outside"])

    with s30:
        st.markdown(f"**30 STG 공정표** — {vessel_no} · {vessel_type}")
        try:
            html = _make_30stg_table(vessel_no, vessel_type, sched_df)
            st.markdown(html, unsafe_allow_html=True)
        except Exception as e:
            logger.error("30STG 테이블 오류: %s\n%s", e, traceback.format_exc())
            st.error("테이블 생성 중 오류가 발생했습니다.")

    with s50:
        st.markdown(f"**50 STG 공정표** — {vessel_no} · {vessel_type}")
        try:
            html = _make_50stg_table(vessel_no, vessel_type, sched_df)
            st.markdown(html, unsafe_allow_html=True)
        except Exception as e:
            logger.error("50STG 테이블 오류: %s\n%s", e, traceback.format_exc())
            st.error("테이블 생성 중 오류가 발생했습니다.")

    with sio:
        st.markdown(f"**In/Outside 공정표** — {vessel_no}")
        try:
            html = _make_inout_table(sched_df)
            if not html:
                st.info(
                    "In/Outside 계산 데이터가 없습니다. "
                    "선각WALL곡직완료일이 입력되어 있는지 확인해 주세요."
                )
            else:
                st.markdown(html, unsafe_allow_html=True)
        except Exception as e:
            logger.error("In/Outside 테이블 오류: %s\n%s", e, traceback.format_exc())
            st.error("테이블 생성 중 오류가 발생했습니다.")
