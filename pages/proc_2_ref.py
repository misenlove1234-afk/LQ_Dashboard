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
    get_vessels, get_anchor_30stg, get_anchor_50stg,
    upload_anchor_excel,
)

logger = logging.getLogger(__name__)

_SUBTABS = [
    "30 STG 소요일",
    "50 STG 소요일",
    "In/Outside 소요일",
    "공종 순서",
    "데크 순서",
    "비작업일 캘린더",
    "로직 규칙",
    "앵커 양식 다운로드",
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

    st.markdown("**선각 작업**")
    sg_edit = st.data_editor(
        edit_df[["deck"] + sunggak_cols],
        column_config={**col_cfg,
                       **{c: st.column_config.NumberColumn(c, min_value=0, max_value=60, step=1)
                          for c in sunggak_cols}},
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

    work_cols = ["트렁크배선", "윈도우설치", "윈도우검사", "내부배관검사", "외부배관검사",
                 "외판도장", "외판족장철거", "FLOOR도장", "탑재준비", "탑재사열", "인양", "탑재"]
    edit_df = df[["area"] + work_cols].copy()

    col_cfg = {"area": st.column_config.TextColumn("구역", disabled=True, width="small")}
    for c in work_cols:
        col_cfg[c] = st.column_config.NumberColumn(c, min_value=0, max_value=90, step=1)

    edited = st.data_editor(edit_df, column_config=col_cfg,
                             use_container_width=True, hide_index=True,
                             key="ref_inout_editor")

    if st.button("저장", key="ref_inout_save", type="primary"):
        save_df = df.copy()
        for col in work_cols:
            save_df[col] = edited[col].values
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
            _save_result(ok)
            st.rerun()

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
# 서브탭 8: 앵커 이벤트 Excel 양식 다운로드
# ═══════════════════════════════════════════════════════════════

def _tab_anchor_template():
    st.markdown("#### 앵커 이벤트 양식 — 다운로드 · 업로드")
    st.markdown(
        "매주 변경되는 **블럭입고일 · 블럭탑재일 · 선각검사일 · 거주구탑재일**을 "
        "이 양식에 입력하여 업로드하면 DB에 반영됩니다."
    )

    # ── 양식 다운로드 ────────────────────────────────────────────
    col_dl, col_info = st.columns([1, 2])
    with col_dl:
        try:
            xlsx_bytes = generate_anchor_template()
            st.download_button(
                label="📥 양식 다운로드 (.xlsx)",
                data=xlsx_bytes,
                file_name="앵커이벤트_입력양식.xlsx",
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
| 30STG_앵커 | 블럭별 입고일 · 탑재일 |
| 50STG_앵커 | 데크별 탑재시작일 · 선각검사 계획/실적 |
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
                st.info("저장된 데이터가 없습니다. 양식을 작성하여 업로드해 주세요.")
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
