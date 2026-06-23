"""
기준정보 탭 렌더링 — 관리자 전용
30 STG / 50 STG / In·Outside 소요일, 비작업일 캘린더, 로직 규칙 관리
"""

import logging
import traceback
import datetime
import pandas as pd
import streamlit as st

from data.meeting_ref_data import (
    init_tables,
    get_ref_30stg, save_ref_30stg, default_30stg_df,
    get_ref_50stg, save_ref_50stg, default_50stg_df,
    get_ref_inout, save_ref_inout, default_inout_df,
    get_logic_rules, save_logic_rules, default_rules_df,
    get_calendar, add_calendar_date, delete_calendar_date,
)

logger = logging.getLogger(__name__)

# ── 서브탭 레이블 ────────────────────────────────────────────────
_SUBTABS = [
    "30 STG 소요일",
    "50 STG 소요일",
    "In/Outside 소요일",
    "비작업일 캘린더",
    "로직 규칙",
]


# ═══════════════════════════════════════════════════════════════
# 공통 헬퍼
# ═══════════════════════════════════════════════════════════════

def _load_safe(fetch_fn, fallback_fn, *args):
    """DB 조회 실패 시 기본값 반환"""
    try:
        df = fetch_fn(*args)
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
    """LNG / CONT 라디오 토글 → 선택 문자열 반환"""
    return st.radio(
        "선종",
        options=["LNG", "CONT"],
        horizontal=True,
        key=key,
    )


# ═══════════════════════════════════════════════════════════════
# 서브탭 1: 30 STG 소요일
# ═══════════════════════════════════════════════════════════════

def _tab_30stg():
    vtype = _vessel_toggle("ref_30stg_vessel")
    df = _load_safe(get_ref_30stg, default_30stg_df, vtype)

    # 표시 열: block_no + 공종 소요일
    display_cols = ["block_no", "관철", "덕트", "전장", "도장", "배선"]
    edit_df = df[display_cols].copy()

    st.caption("0 = 해당 블럭에 작업 없음 / 숫자 = 실작업일(일요일·공휴일 제외)")

    col_cfg = {
        "block_no": st.column_config.TextColumn("블럭번호", disabled=True, width="medium"),
        "관철":     st.column_config.NumberColumn("관철(일)", min_value=0, max_value=30, step=1),
        "덕트":     st.column_config.NumberColumn("덕트(일)", min_value=0, max_value=30, step=1),
        "전장":     st.column_config.NumberColumn("전장(일)", min_value=0, max_value=30, step=1),
        "도장":     st.column_config.NumberColumn("도장(일)", min_value=0, max_value=30, step=1),
        "배선":     st.column_config.NumberColumn("배선(일)", min_value=0, max_value=30, step=1),
    }

    edited = st.data_editor(
        edit_df,
        column_config=col_cfg,
        use_container_width=True,
        hide_index=True,
        key=f"ref30_editor_{vtype}",
    )

    if st.button("저장", key=f"ref30_save_{vtype}", type="primary"):
        save_df = df.copy()
        for col in ["관철", "덕트", "전장", "도장", "배선"]:
            save_df[col] = edited[col].values
        _save_result(save_ref_30stg(save_df))


# ═══════════════════════════════════════════════════════════════
# 서브탭 2: 50 STG 소요일
# ═══════════════════════════════════════════════════════════════

def _tab_50stg():
    vtype = _vessel_toggle("ref_50stg_vessel")
    df = _load_safe(get_ref_50stg, default_50stg_df, vtype)

    work_cols = ["목의화기1차", "도장PB", "도장TU", "배선", "보온",
                 "목의화기2차", "피복", "BP검사", "판넬설치", "결선", "가구", "장판", "스커트"]
    display_cols = ["deck"] + work_cols
    edit_df = df[display_cols].copy()

    st.caption("0 = 해당 데크에 작업 없음 / 숫자 = 실작업일")

    col_cfg = {"deck": st.column_config.TextColumn("데크", disabled=True, width="small")}
    for c in work_cols:
        col_cfg[c] = st.column_config.NumberColumn(c, min_value=0, max_value=60, step=1)

    edited = st.data_editor(
        edit_df,
        column_config=col_cfg,
        use_container_width=True,
        hide_index=True,
        key=f"ref50_editor_{vtype}",
    )

    if st.button("저장", key=f"ref50_save_{vtype}", type="primary"):
        save_df = df.copy()
        for col in work_cols:
            save_df[col] = edited[col].values
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

    edited = st.data_editor(
        edit_df,
        column_config=col_cfg,
        use_container_width=True,
        hide_index=True,
        key="ref_inout_editor",
    )

    if st.button("저장", key="ref_inout_save", type="primary"):
        save_df = df.copy()
        for col in work_cols:
            save_df[col] = edited[col].values
        _save_result(save_ref_inout(save_df))


# ═══════════════════════════════════════════════════════════════
# 서브탭 4: 비작업일 캘린더
# ═══════════════════════════════════════════════════════════════

def _tab_calendar():
    st.caption("일요일·추석·설은 자동 제외 / 여기서는 야드 특별 비작업일만 등록")

    # 추가 폼
    with st.form("ref_cal_add_form", clear_on_submit=True):
        c1, c2 = st.columns([2, 3])
        with c1:
            new_date = st.date_input(
                "날짜",
                value=datetime.date.today(),
                key="ref_cal_date_input",
            )
        with c2:
            new_reason = st.text_input(
                "사유",
                placeholder="예) 야드정전, 태풍대피 …",
                key="ref_cal_reason_input",
            )
        submitted = st.form_submit_button("추가", type="primary")

    if submitted:
        if not new_reason.strip():
            st.warning("사유를 입력해 주세요.")
        else:
            ok = add_calendar_date(str(new_date), new_reason.strip())
            _save_result(ok)
            st.rerun()

    # 등록된 비작업일 목록
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
        del_key = f"ref_cal_del_{row['cal_date']}"
        if c3.button("삭제", key=del_key):
            ok = delete_calendar_date(str(row["cal_date"])[:10])
            _save_result(ok)
            st.rerun()


# ═══════════════════════════════════════════════════════════════
# 서브탭 5: 로직 규칙
# ═══════════════════════════════════════════════════════════════

def _tab_rules():
    df = _load_safe(get_logic_rules, default_rules_df)

    st.caption("is_active: 1=활성 / 0=비활성 | offset_days: 음수=선행 종료 전 착수 가능")

    col_cfg = {
        "rule_id":     st.column_config.NumberColumn("ID",      disabled=True, width="small"),
        "vessel_type": st.column_config.SelectboxColumn("선종",  options=["ALL","LNG","CONT"]),
        "rule_name":   st.column_config.TextColumn("규칙명",      width="medium"),
        "pre_area":    st.column_config.TextColumn("선행 구역",   width="medium"),
        "pre_work":    st.column_config.TextColumn("선행 작업",   width="medium"),
        "pre_event":   st.column_config.SelectboxColumn("기준점", options=["END","START"]),
        "offset_days": st.column_config.NumberColumn("오프셋(일)", min_value=-30, max_value=30, step=1),
        "suc_area":    st.column_config.TextColumn("후행 구역",   width="medium"),
        "suc_work":    st.column_config.TextColumn("후행 작업",   width="medium"),
        "is_active":   st.column_config.NumberColumn("활성",      min_value=0, max_value=1, step=1),
    }

    edited = st.data_editor(
        df,
        column_config=col_cfg,
        use_container_width=True,
        hide_index=True,
        key="ref_rules_editor",
    )

    if st.button("저장", key="ref_rules_save", type="primary"):
        _save_result(save_logic_rules(edited))


# ═══════════════════════════════════════════════════════════════
# 진입점
# ═══════════════════════════════════════════════════════════════

def render_ref_tab():
    """기준정보 탭 전체 렌더링 (관리자 전용 — 호출 전 권한 확인 완료 가정)"""

    # DB 테이블 자동 초기화 (최초 1회)
    if not st.session_state.get("ref_tables_init"):
        ok = init_tables()
        st.session_state["ref_tables_init"] = True
        if not ok:
            st.warning("DB 초기화에 실패했습니다. 기본값을 표시합니다.")

    tabs = st.tabs(_SUBTABS)

    with tabs[0]:
        _tab_30stg()

    with tabs[1]:
        _tab_50stg()

    with tabs[2]:
        _tab_inout()

    with tabs[3]:
        _tab_calendar()

    with tabs[4]:
        _tab_rules()
