"""
기준정보 탭 렌더링 — 관리자 전용
30 STG / 50 STG / In·Outside 소요일, 공종 순서, 데크 순서, 비작업일 캘린더, 로직 규칙 관리
"""

import logging
import traceback
import datetime
import pandas as pd
import streamlit as st

from data.meeting_ref_data import (
    init_tables,
    get_ref_30stg,   save_ref_30stg,   default_30stg_df,
    get_ref_50stg,   save_ref_50stg,   default_50stg_df,
    get_ref_inout,   save_ref_inout,   default_inout_df,
    get_sequence,    save_sequence,    default_sequence_df,
    get_deck_order,                    default_deck_order_df,
    get_logic_rules, save_logic_rules, default_rules_df,
    get_calendar,    add_calendar_date, delete_calendar_date,
    generate_anchor_template,
    get_vessels,     get_anchor_30stg, get_anchor_50stg,
    upload_anchor_excel,
    save_vessel_direct, save_anchor_30stg_direct, save_anchor_50stg_direct,
    get_block_deck_map,
)

logger = logging.getLogger(__name__)

_SUBTABS = [
    "📦 30 STG 소요일",
    "🏗️ 50 STG 소요일",
    "🔌 In/Outside 소요일",
    "🔢 공종 순서",
    "📐 데크 순서",
    "📅 비작업일 캘린더",
    "📋 로직 규칙",
    "📥 앵커 양식 다운로드",
]


# ═══════════════════════════════════════════════════════════════
# 공통 헬퍼
# ═══════════════════════════════════════════════════════════════

def _load_safe(fetch_fn, fallback_fn, *args):
    try:
        df = fetch_fn(*args) if args else fetch_fn()
        if df is None or df.empty:
            return fallback_fn(*args) if args else fallback_fn()
        return df
    except Exception as e:
        logger.error("기준정보 조회 오류: %s\n%s", e, traceback.format_exc())
        return fallback_fn(*args) if args else fallback_fn()


def _save_result(ok: bool):
    if ok:
        st.success("저장되었습니다.")
    else:
        st.error("오류가 발생했습니다. 관리자에게 문의해 주세요.")


def _vessel_toggle(key: str) -> str:
    return st.radio("선종", options=["LNG", "CONT"], horizontal=True, key=key)


# ═══════════════════════════════════════════════════════════════
# 서브탭 1: 30 STG 소요일
# ═══════════════════════════════════════════════════════════════

def _tab_30stg():
    vtype = _vessel_toggle("ref_30stg_vessel")
    df = _load_safe(get_ref_30stg, default_30stg_df, vtype)

    display_cols = ["block_no", "관철", "덕트", "전장", "도장", "배선"]
    edit_df = df[display_cols].copy()

    st.caption("0 = 해당 블럭 작업 없음 / 숫자 = 실작업일 (일요일·공휴일 제외)")

    col_cfg = {
        "block_no": st.column_config.TextColumn("블럭번호", disabled=True, width="medium"),
        "관철":     st.column_config.NumberColumn("관철(일)", min_value=0, max_value=30, step=1),
        "덕트":     st.column_config.NumberColumn("덕트(일)", min_value=0, max_value=30, step=1),
        "전장":     st.column_config.NumberColumn("전장(일)", min_value=0, max_value=30, step=1),
        "도장":     st.column_config.NumberColumn("도장(일)", min_value=0, max_value=30, step=1),
        "배선":     st.column_config.NumberColumn("배선(일)", min_value=0, max_value=30, step=1),
    }

    edited = st.data_editor(edit_df, column_config=col_cfg,
                             use_container_width=True, hide_index=True,
                             key=f"ref30_editor_{vtype}")

    if st.button("저장", key=f"ref30_save_{vtype}", type="primary"):
        save_df = df.copy()
        for col in ["관철", "덕트", "전장", "도장", "배선"]:
            save_df[col] = edited[col].values
        _save_result(save_ref_30stg(save_df))


# ═══════════════════════════════════════════════════════════════
# 서브탭 2: 50 STG 소요일 (선각 + 의장)
# ═══════════════════════════════════════════════════════════════

def _tab_50stg():
    vtype = _vessel_toggle("ref_50stg_vessel")
    df = _load_safe(get_ref_50stg, default_50stg_df, vtype)

    sunggak_cols = ["선각취부", "선각용접", "선각FLOOR곡직", "선각WALL곡직"]
    work_cols    = ["목의화기1차", "도장PB", "도장TU", "배선", "보온",
                    "목의화기2차", "피복", "BP검사", "판넬설치", "결선", "가구", "장판", "스커트"]
    all_work = sunggak_cols + work_cols
    edit_df = df[["deck"] + all_work].copy()

    st.caption("선각 소요일은 파일 수신 후 입력 / 0 = 작업 없음")

    col_cfg = {"deck": st.column_config.TextColumn("데크", disabled=True, width="small")}

    st.markdown("**선각 작업** &nbsp; *(블럭탑재 종료 → 선각검사 완료)*")
    sg_display = edit_df[["deck"] + sunggak_cols].copy()
    sg_display["선각작업일"] = sg_display[sunggak_cols].fillna(0).sum(axis=1).astype(int)
    sg_edit = st.data_editor(
        sg_display,
        column_config={
            **col_cfg,
            **{c: st.column_config.NumberColumn(c, min_value=0, max_value=60, step=1)
               for c in sunggak_cols},
            "선각작업일": st.column_config.NumberColumn(
                "선각작업일(합계)", disabled=True,
                help="선각취부+용접+FLOOR곡직+WALL곡직 자동 합산"),
        },
        use_container_width=True, hide_index=True,
        key=f"ref50_sg_editor_{vtype}",
    )

    st.markdown("**의장 · 가구 작업**")
    wk_edit = st.data_editor(
        edit_df[["deck"] + work_cols],
        column_config={**col_cfg,
                       **{c: st.column_config.NumberColumn(c, min_value=0, max_value=60, step=1)
                          for c in work_cols}},
        use_container_width=True, hide_index=True,
        key=f"ref50_wk_editor_{vtype}",
    )

    if st.button("저장", key=f"ref50_save_{vtype}", type="primary"):
        save_df = df.copy()
        for col in sunggak_cols:
            save_df[col] = sg_edit[col].values
        for col in work_cols:
            save_df[col] = wk_edit[col].values
        _save_result(save_ref_50stg(save_df))


# ═══════════════════════════════════════════════════════════════
# 서브탭 3: In/Outside 소요일
# ═══════════════════════════════════════════════════════════════

def _tab_inout():
    df = _load_safe(get_ref_inout, default_inout_df)

    io_cols = [c for c in [
        "트렁크배선","윈도우설치","윈도우검사","내부배관검사","외부배관검사",
        "외판도장","외판족장철거","FLOOR도장","목의장비탑재","목의장비설치",
        "탑재준비","탑재사열","인양","탑재",
    ] if c in df.columns]
    su_cols = [c for c in [
        "도장PB","도장TU","보온","판넬설치","결선","장판","스커트","배선","족장철거",
    ] if c in df.columns]

    col_cfg_base = {"area": st.column_config.TextColumn("구역", disabled=True, width="small")}

    st.caption("0 = 해당 구역 작업 없음 / 숫자 = 실작업일")
    st.markdown("**In/Outside · Elevator 공종**")
    io_edited = st.data_editor(
        df[["area"] + io_cols].copy(),
        column_config={**col_cfg_base,
                       **{c: st.column_config.NumberColumn(c, min_value=0, max_value=90, step=1)
                          for c in io_cols}},
        use_container_width=True, hide_index=True, key="ref_inout_io_editor",
    )

    if su_cols:
        st.markdown("**STAIRWAY · UPP-DK 공종**")
        su_edited = st.data_editor(
            df[["area"] + su_cols].copy(),
            column_config={**col_cfg_base,
                           **{c: st.column_config.NumberColumn(c, min_value=0, max_value=90, step=1)
                              for c in su_cols}},
            use_container_width=True, hide_index=True, key="ref_inout_su_editor",
        )
    else:
        su_edited = None

    if st.button("저장", key="ref_inout_save", type="primary"):
        save_df = df.copy()
        for col in io_cols:
            save_df[col] = io_edited[col].values
        if su_edited is not None:
            for col in su_cols:
                save_df[col] = su_edited[col].values
        _save_result(save_ref_inout(save_df))


# ═══════════════════════════════════════════════════════════════
# 서브탭 4: 공종 순서
# ═══════════════════════════════════════════════════════════════

def _tab_sequence():
    stg = st.radio("STG", ["30", "50"], horizontal=True, key="ref_seq_stg")
    df = _load_safe(get_sequence, default_sequence_df, stg)

    st.caption(
        "duration_type: anchor=수기입력 기준점 / fixed=고정일수 / variable=기준파일 소요일  |  "
        "cal_type: all=월~토 / weekday=월~금 전용  |  "
        "exception_blocks: 해당 공종을 건너뛸 블럭 (쉼표 구분)"
    )

    editable_cols = ["work_name", "duration_type", "fixed_days",
                     "exception_blocks", "cal_type", "ref_col", "is_active"]
    readonly_cols = ["stg", "seq_no", "work_code"]

    col_cfg = {
        "stg":              st.column_config.TextColumn("STG",         disabled=True, width="small"),
        "seq_no":           st.column_config.NumberColumn("순서",       disabled=True, width="small"),
        "work_code":        st.column_config.TextColumn("코드",         disabled=True, width="medium"),
        "work_name":        st.column_config.TextColumn("공종명",        width="medium"),
        "duration_type":    st.column_config.SelectboxColumn(
                                "소요일 유형", options=["anchor","fixed","variable"]),
        "fixed_days":       st.column_config.NumberColumn("고정일수",    min_value=0, max_value=10, step=1),
        "exception_blocks": st.column_config.TextColumn("제외 블럭",     width="large"),
        "cal_type":         st.column_config.SelectboxColumn(
                                "캘린더",     options=["all","weekday"]),
        "ref_col":          st.column_config.TextColumn("참조 컬럼",     width="medium"),
        "is_active":        st.column_config.NumberColumn("활성",        min_value=0, max_value=1, step=1),
    }

    display_cols = readonly_cols + editable_cols
    edited = st.data_editor(df[display_cols], column_config=col_cfg,
                             use_container_width=True, hide_index=True,
                             key=f"ref_seq_editor_{stg}")

    if st.button("저장", key=f"ref_seq_save_{stg}", type="primary"):
        _save_result(save_sequence(edited))


# ═══════════════════════════════════════════════════════════════
# 서브탭 5: 데크 순서
# ═══════════════════════════════════════════════════════════════

def _tab_deck_order():
    st.caption("order_no: 1=UPP-DK(하부) → 최대=NAV-DK(상부) / 계단식 배치 계산에 사용")

    col1, col2 = st.columns(2)
    for vtype, col in [("LNG", col1), ("CONT", col2)]:
        df = _load_safe(get_deck_order, default_deck_order_df, vtype)
        with col:
            st.markdown(f"**{vtype}**")
            st.dataframe(
                df[["deck", "order_no"]].rename(columns={"deck":"데크","order_no":"순서"}),
                use_container_width=True, hide_index=True,
            )
    st.info("데크 순서는 고정값입니다. 변경이 필요하면 개발자에게 문의하세요.")


# ═══════════════════════════════════════════════════════════════
# 서브탭 6: 비작업일 캘린더
# ═══════════════════════════════════════════════════════════════

def _tab_calendar():
    st.caption("일요일·추석·설은 자동 제외 / 여기서는 야드 특별 비작업일만 등록")

    with st.form("ref_cal_add_form", clear_on_submit=True):
        c1, c2 = st.columns([2, 3])
        with c1:
            new_date = st.date_input("날짜", value=datetime.date.today(),
                                     key="ref_cal_date_input")
        with c2:
            new_reason = st.text_input("사유", placeholder="예) 야드정전, 태풍대피 …",
                                       key="ref_cal_reason_input")
        submitted = st.form_submit_button("추가", type="primary")

    if submitted:
        if not new_reason.strip():
            st.warning("사유를 입력해 주세요.")
        else:
            ok = add_calendar_date(str(new_date), new_reason.strip())
            if ok:
                st.success(f"{new_date} 등록되었습니다.")
            else:
                st.error("오류가 발생했습니다. 관리자에게 문의해 주세요.")

    try:
        cal_df = get_calendar()
    except Exception:
        cal_df = pd.DataFrame(columns=["cal_date", "reason"])

    if cal_df.empty:
        st.info("등록된 비작업일이 없습니다.")
        return

    st.markdown(f"**등록된 비작업일 {len(cal_df)}건**")
    for _, row in cal_df.iterrows():
        c1, c2, c3 = st.columns([2, 4, 1])
        c1.write(str(row["cal_date"])[:10])
        c2.write(row["reason"])
        if c3.button("삭제", key=f"ref_cal_del_{row['cal_date']}"):
            _save_result(delete_calendar_date(str(row["cal_date"])[:10]))
            st.rerun()


# ═══════════════════════════════════════════════════════════════
# 서브탭 7: 로직 규칙
# ═══════════════════════════════════════════════════════════════

def _tab_rules():
    df = _load_safe(get_logic_rules, default_rules_df)

    st.caption("is_active: 1=활성 / 0=비활성  |  offset_days: 음수=선행 종료 전 착수 가능")

    col_cfg = {
        "rule_id":     st.column_config.NumberColumn("ID",      disabled=True, width="small"),
        "vessel_type": st.column_config.SelectboxColumn("선종",  options=["ALL","LNG","CONT"]),
        "rule_name":   st.column_config.TextColumn("규칙명",      width="medium"),
        "pre_area":    st.column_config.TextColumn("선행 구역",   width="medium"),
        "pre_work":    st.column_config.TextColumn("선행 작업",   width="medium"),
        "pre_event":   st.column_config.SelectboxColumn("기준점", options=["END","START"]),
        "offset_days": st.column_config.NumberColumn("오프셋(일)",min_value=-30, max_value=30, step=1),
        "suc_area":    st.column_config.TextColumn("후행 구역",   width="medium"),
        "suc_work":    st.column_config.TextColumn("후행 작업",   width="medium"),
        "is_active":   st.column_config.NumberColumn("활성",      min_value=0, max_value=1, step=1),
    }

    edited = st.data_editor(df, column_config=col_cfg,
                             use_container_width=True, hide_index=True,
                             key="ref_rules_editor")

    if st.button("저장", key="ref_rules_save", type="primary"):
        _save_result(save_logic_rules(edited))


# ═══════════════════════════════════════════════════════════════
# 앵커 직접 입력 헬퍼
# ═══════════════════════════════════════════════════════════════

def _direct_vessel():
    """호선 직접 등록/조회"""
    # 저장 후 재렌더링 시 메시지 표시
    msg = st.session_state.pop("_vessel_save_msg", None)
    if msg:
        st.success(msg) if msg.startswith("✅") else st.error(msg)

    try:
        vdf = get_vessels()
    except Exception:
        vdf = pd.DataFrame(columns=["vessel_no", "vessel_type", "거주구탑재예정일", "비고"])

    if not vdf.empty:
        st.dataframe(
            vdf.rename(columns={"vessel_no": "호선번호", "vessel_type": "선종",
                                 "거주구탑재예정일": "거주구탑재 예정일", "비고": "비고"}),
            use_container_width=True, hide_index=True,
        )

    with st.form("direct_vessel_form", clear_on_submit=True):
        c1, c2, c3, c4 = st.columns([2, 2, 3, 3])
        with c1:
            v_no   = st.text_input("호선번호*", placeholder="예) 3001")
        with c2:
            v_type = st.selectbox("선종*", ["LNG", "CONT"])
        with c3:
            v_date = st.date_input("거주구탑재 예정일", value=None,
                                   key="direct_vessel_date")
        with c4:
            v_remark = st.text_input("비고", placeholder="선택 입력")
        submitted = st.form_submit_button("등록/수정", type="primary")

    if submitted:
        if not v_no.strip():
            st.warning("호선번호를 입력해 주세요.")
        else:
            ok = save_vessel_direct(
                v_no.strip(), v_type,
                str(v_date) if v_date else None,
                v_remark.strip() or None,
            )
            if ok:
                st.session_state["_vessel_save_msg"] = f"✅ 호선 {v_no.strip()} 등록/수정 완료."
            else:
                st.session_state["_vessel_save_msg"] = "❌ 오류가 발생했습니다. 관리자에게 문의해 주세요."
            st.rerun()


def _direct_30stg():
    """30STG 앵커 직접 입력"""
    msg = st.session_state.pop("_30stg_save_msg", None)
    if msg:
        st.success(msg) if msg.startswith("✅") else st.error(msg)

    try:
        vessels = get_vessels()
    except Exception:
        vessels = pd.DataFrame(columns=["vessel_no", "vessel_type"])

    if vessels.empty:
        st.info("먼저 '호선 등록' 탭에서 호선을 등록해 주세요.")
        return

    vessel_list = vessels["vessel_no"].tolist()
    sel_vessel = st.selectbox("호선 선택", vessel_list, key="direct_30stg_vessel")
    sel_vtype  = vessels.loc[vessels["vessel_no"] == sel_vessel, "vessel_type"].iloc[0]

    # 블럭 목록 로드
    try:
        blk_df = get_block_deck_map(sel_vtype)
        blocks = blk_df["block_no"].tolist() if not blk_df.empty else []
    except Exception:
        blocks = []

    # 기존 데이터 로드
    try:
        exist = get_anchor_30stg(sel_vessel)
    except Exception:
        exist = pd.DataFrame(columns=["vessel_no", "block_no", "blk_in_date", "blk_out_date"])

    exist_map = {}
    if not exist.empty:
        for _, r in exist.iterrows():
            exist_map[r["block_no"]] = r

    rows = []
    for b in blocks:
        r = exist_map.get(b, {})
        rows.append({
            "block_no":    b,
            "blk_in_date":  str(r.get("blk_in_date", ""))[:10] if r.get("blk_in_date") else "",
            "blk_out_date": str(r.get("blk_out_date", ""))[:10] if r.get("blk_out_date") else "",
        })

    edit_df = pd.DataFrame(rows)
    st.caption(f"호선: **{sel_vessel}** ({sel_vtype}) · 블럭 {len(rows)}개")
    edited = st.data_editor(
        edit_df,
        column_config={
            "block_no":    st.column_config.TextColumn("블럭번호", disabled=True, width="small"),
            "blk_in_date": st.column_config.TextColumn("입고일 (YYYY-MM-DD)", width="medium"),
            "blk_out_date":st.column_config.TextColumn("탑재일 (YYYY-MM-DD)", width="medium"),
        },
        use_container_width=True, hide_index=True,
        key=f"direct_30stg_editor_{sel_vessel}",
    )

    if st.button("저장", key="direct_30stg_save", type="primary"):
        rows_to_save = edited.to_dict("records")
        n = save_anchor_30stg_direct(sel_vessel, rows_to_save)
        if n >= 0:
            st.session_state["_30stg_save_msg"] = f"✅ {n}건 저장 완료."
        else:
            st.session_state["_30stg_save_msg"] = "❌ 오류가 발생했습니다. 관리자에게 문의해 주세요."
        st.rerun()


def _direct_50stg():
    """50STG 앵커 직접 입력 (탑재종료일 + 검사일 → 중간 날짜 자동 계산)"""
    msg = st.session_state.pop("_50stg_save_msg", None)
    if msg:
        st.success(msg) if msg.startswith("✅") else st.error(msg)

    try:
        vessels = get_vessels()
    except Exception:
        vessels = pd.DataFrame(columns=["vessel_no", "vessel_type"])

    if vessels.empty:
        st.info("먼저 '호선 등록' 탭에서 호선을 등록해 주세요.")
        return

    vessel_list = vessels["vessel_no"].tolist()
    sel_vessel = st.selectbox("호선 선택", vessel_list, key="direct_50stg_vessel")
    sel_vtype  = vessels.loc[vessels["vessel_no"] == sel_vessel, "vessel_type"].iloc[0]

    # 데크 목록 (데크 순서표 기반)
    try:
        dk_df  = get_deck_order(sel_vtype)
        decks  = dk_df.sort_values("order_no")["deck"].tolist() if not dk_df.empty else []
    except Exception:
        decks  = []

    # 기존 데이터 로드
    try:
        exist = get_anchor_50stg(sel_vessel)
    except Exception:
        exist = pd.DataFrame()

    exist_map = {}
    if not exist.empty:
        for _, r in exist.iterrows():
            exist_map[r["deck"]] = r

    rows = []
    for dk in decks:
        r = exist_map.get(dk, {})
        rows.append({
            "deck":       dk,
            "mount_end":  str(r.get("mount_start_date", ""))[:10] if r.get("mount_start_date") else "",
            "insp_end":   str(r.get("inspection_date", ""))[:10]  if r.get("inspection_date")  else "",
        })

    edit_df = pd.DataFrame(rows)
    st.caption(f"호선: **{sel_vessel}** ({sel_vtype}) · 데크 {len(rows)}개 &nbsp;|&nbsp; "
               f"취부·용접·곡직 날짜는 기준정보 소요일로 자동 계산됩니다.")
    edited = st.data_editor(
        edit_df,
        column_config={
            "deck":      st.column_config.TextColumn("데크", disabled=True, width="small"),
            "mount_end": st.column_config.TextColumn("블럭탑재 종료일 (YYYY-MM-DD)", width="medium"),
            "insp_end":  st.column_config.TextColumn("선각검사 완료일 (YYYY-MM-DD)", width="medium"),
        },
        use_container_width=True, hide_index=True,
        key=f"direct_50stg_editor_{sel_vessel}",
    )

    if st.button("저장", key="direct_50stg_save", type="primary"):
        rows_to_save = edited.to_dict("records")
        n = save_anchor_50stg_direct(sel_vessel, sel_vtype, rows_to_save)
        if n >= 0:
            st.session_state["_50stg_save_msg"] = f"✅ {n}건 저장 완료 (취부·용접·곡직 자동 계산)."
        else:
            st.session_state["_50stg_save_msg"] = "❌ 오류가 발생했습니다. 관리자에게 문의해 주세요."
        st.rerun()


# ═══════════════════════════════════════════════════════════════
# 서브탭 8: 앵커 이벤트 Excel 양식 다운로드
# ═══════════════════════════════════════════════════════════════

def _tab_anchor_template():
    st.markdown("#### 앵커 이벤트 양식 — 다운로드 · 업로드")
    st.markdown(
        "선종을 선택하면 해당 선종의 블럭번호·데크가 미리 채워진 양식을 다운로드합니다. "
        "작성 후 업로드하면 DB에 반영됩니다."
    )

    # ── 선종 선택 + 양식 다운로드 ────────────────────────────────
    vtype_dl = st.radio(
        "선종 선택",
        options=["LNG", "CONT"],
        horizontal=True,
        key="ref_anchor_vtype",
    )

    col_dl, col_info = st.columns([1, 2])
    with col_dl:
        try:
            xlsx_bytes = generate_anchor_template(vtype_dl)
            st.download_button(
                label=f"📥 {vtype_dl} 양식 다운로드 (.xlsx)",
                data=xlsx_bytes,
                file_name=f"앵커이벤트_입력양식_{vtype_dl}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
            )
        except Exception as e:
            logger.error("양식 생성 오류: %s\n%s", e, traceback.format_exc())
            st.error("오류가 발생했습니다. 관리자에게 문의해 주세요.")
    with col_info:
        st.markdown("""
| 시트 | 입력 내용 |
|---|---|
| 입력안내 | 작성 방법 안내 |
| 호선정보 | 호선번호 · 선종 · 거주구탑재예정일 |
| 30STG_앵커 | 블럭별 **입고일 · 탑재일** (블럭번호 미리 채워짐) |
| 50STG_앵커 | 데크별 **탑재시작일 · 선각취부/용접/FLOOR/WALL곡직/검사 완료일** (데크 미리 채워짐) |
        """)

    st.markdown("---")

    # ── 양식 업로드 ──────────────────────────────────────────────
    st.markdown("#### 업로드 (작성 완료 파일)")
    uploaded = st.file_uploader(
        "작성된 양식 파일을 업로드하세요 (.xlsx)",
        type=["xlsx"],
        key="ref_anchor_upload",
    )

    if uploaded:
        st.caption(f"파일명: `{uploaded.name}` · {uploaded.size:,} bytes")
        if st.button("DB에 반영", key="ref_anchor_upload_btn", type="primary"):
            with st.spinner("업로드 중…"):
                try:
                    res = upload_anchor_excel(uploaded.read())
                    if res["errors"]:
                        for err in res["errors"]:
                            st.warning(err)
                    st.success(
                        f"완료 — 호선 {res['vessel']}건 · "
                        f"30 STG {res['anchor30']}건 · "
                        f"50 STG {res['anchor50']}건 저장"
                    )
                except Exception as e:
                    logger.error("업로드 오류: %s\n%s", e, traceback.format_exc())
                    st.error("오류가 발생했습니다. 관리자에게 문의해 주세요.")

    st.markdown("---")

    # ── 직접 입력 ─────────────────────────────────────────────────
    st.markdown("#### ✏️ 직접 입력 (Excel 없이 입력)")
    st.caption("Excel 업로드 없이 직접 데이터를 입력·저장할 수 있습니다.")

    direct_tab = st.radio(
        "입력 대상", ["🚢 호선 등록", "📦 30STG 앵커", "🏗️ 50STG 앵커"],
        horizontal=True, key="ref_anchor_direct_tab",
    )

    if direct_tab == "🚢 호선 등록":
        _direct_vessel()
    elif direct_tab == "📦 30STG 앵커":
        _direct_30stg()
    else:
        _direct_50stg()

    st.markdown("---")

    # ── 현재 저장된 앵커 데이터 조회 ────────────────────────────
    with st.expander("현재 저장된 데이터 조회", expanded=False):
        sub = st.radio("조회 대상", ["호선정보", "30 STG 앵커", "50 STG 앵커"],
                       horizontal=True, key="ref_anchor_view_tab")
        try:
            if sub == "호선정보":
                df = get_vessels()
            elif sub == "30 STG 앵커":
                df = get_anchor_30stg()
            else:
                df = get_anchor_50stg()

            if df is None or df.empty:
                st.info("저장된 데이터가 없습니다.")
            else:
                st.dataframe(df, use_container_width=True, hide_index=True)
        except Exception:
            st.info("DB에 접근할 수 없습니다.")


# ═══════════════════════════════════════════════════════════════
# 진입점
# ═══════════════════════════════════════════════════════════════

def render_ref_tab():
    """기준정보 탭 전체 렌더링 (관리자 전용)"""

    if not st.session_state.get("ref_tables_init"):
        ok = init_tables()
        st.session_state["ref_tables_init"] = True
        if not ok:
            st.warning("DB 초기화에 실패했습니다. 기본값을 표시합니다.")

    tabs = st.tabs(_SUBTABS)

    with tabs[0]: _tab_30stg()
    with tabs[1]: _tab_50stg()
    with tabs[2]: _tab_inout()
    with tabs[3]: _tab_sequence()
    with tabs[4]: _tab_deck_order()
    with tabs[5]: _tab_calendar()
    with tabs[6]: _tab_rules()
    with tabs[7]: _tab_anchor_template()
