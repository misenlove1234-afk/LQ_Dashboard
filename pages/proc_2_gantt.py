"""
간트차트 탭 — 데이터 계산 탭의 계산 결과(lq_meet_schedule)를 간트로 시각화·편집

[데이터 분리 원칙]
  - 이 탭은 lq_meet_* 테이블만 사용 (DB 밀어넣기 방식)
  - 기존 구역별 상세 현황 탭의 생산 DB 데이터와 완전히 독립
"""

import json
import logging
import traceback

import pandas as pd
import streamlit as st

from data.meeting_calc import get_schedule
from data.meeting_ref_data import get_vessels
from utils.db import get_connection

logger = logging.getLogger(__name__)

# STG 코드 → 공종 그룹 레이블
_STG_LABEL = {"30": "30STG", "50": "50STG", "inout": "In/Out"}


def _schedule_to_tasks(vessel_no: str) -> list:
    """lq_meet_schedule → gantt_editor 요구 형식 변환
    id 형식: "vessel_no|stg|area|work_code" (저장 시 분해 키로 사용)
    """
    df = get_schedule(vessel_no)
    if df.empty:
        return []

    tasks = []
    for _, row in df.iterrows():
        s = str(row.get("plan_start") or "")[:10]
        e = str(row.get("plan_end")   or "")[:10]
        if not s or not e or s in ("None", "NaT", "nan") or e in ("None", "NaT", "nan"):
            continue
        tasks.append({
            "id":   f"{row['vessel_no']}|{row['stg']}|{row['area']}|{row['work_code']}",
            "task": str(row["work_code"]),
            "gj":   _STG_LABEL.get(str(row["stg"]), str(row["stg"])),
            "area": str(row["area"]),
            "proj": str(row["vessel_no"]),
            "s":    s,
            "e":    e,
        })
    return tasks


def _save_changes(changes: list) -> tuple:
    """JSON 변경 내역 → lq_meet_schedule UPDATE
    반환: (성공 건수, 오류 메시지 목록)
    """
    ok_count = 0
    errors   = []
    try:
        conn = get_connection()
        cur  = conn.cursor()
        for c in changes:
            try:
                task_id = c.get("task_id", "")
                parts = task_id.split("|", 3)
                if len(parts) != 4:
                    errors.append(f"잘못된 ID 형식: {task_id}")
                    continue
                vessel_no, stg, area, work_code = parts
                cur.execute("""
                    UPDATE lq_meet_schedule
                    SET plan_start=?, plan_end=?, calc_at=GETDATE()
                    WHERE vessel_no=? AND stg=? AND area=? AND work_code=?
                """, (c["new_start"], c["new_end"],
                      vessel_no, stg, area, work_code))
                ok_count += 1
            except Exception as row_e:
                errors.append(f"{c.get('task_id','?')}: {row_e}")
        conn.commit()
        conn.close()
        get_schedule.clear()
    except Exception as e:
        logger.error("스케줄 저장 오류: %s\n%s", e, traceback.format_exc())
        errors.append(str(e))
    return ok_count, errors


def render_gantt_tab(current_user: str, is_admin: bool):
    """간트차트 탭 렌더링 (lq_meet_schedule 전용)"""
    from pages.proc_2 import _render_gantt_component

    vessels_df = get_vessels()
    if vessels_df.empty:
        st.info("💡 등록된 호선이 없습니다. 좌측 메뉴의 **'기준정보' 페이지**에서 호선을 먼저 등록해 주세요.")
        return

    # ── 호선 선택 + STG 필터 ──
    col_sel, col_stg, col_info = st.columns([2, 3, 3])
    with col_sel:
        vessel_no = st.selectbox(
            "호선 선택",
            list(vessels_df["vessel_no"]),
            key="proc2_gantt_vessel",
        )
    with col_stg:
        stg_filter = st.radio(
            "공종 필터",
            ["전체", "30STG", "50STG"],
            horizontal=True,
            key="proc2_gantt_stg",
        )

    if not vessel_no:
        return

    tasks = _schedule_to_tasks(vessel_no)

    # STG 필터 적용 (50STG는 In/Out 포함)
    if stg_filter == "30STG":
        tasks = [t for t in tasks if t.get("gj") == "30STG"]
    elif stg_filter == "50STG":
        tasks = [t for t in tasks if t.get("gj") in ("50STG", "In/Out")]

    if not tasks:
        with col_info:
            st.info(
                f"**{vessel_no}** — **{stg_filter}** 에 해당하는 계산된 일정이 없습니다. "
                "좌측 메뉴의 **'공정회의록 작성, 수정' 페이지**에서 먼저 **원클릭 계산**을 실행해 주세요."
            )
        return

    with col_info:
        st.caption(
            f"📊 **{vessel_no}** / {stg_filter} — {len(tasks)}개 공정 "
            f"| {'✏️ 편집 가능 (관리자)' if is_admin else '🔒 읽기 전용'} "
            "| 막대 **드래그**=이동, **클릭**=± 날짜 조정"
        )

    # ── 간트 렌더링 (M블럭 30STG 5행 레이아웃은 gantt_editor.html이 자동 감지) ──
    _render_gantt_component(
        tasks,
        is_editable=is_admin,
        current_user=current_user,
        height=780,
        row_mode="area",
        wrap_max_height="560px",
    )

    if not is_admin:
        st.caption("🔒 일정 수정은 관리자 로그인 후 가능합니다.")
        return

    # ── 변경 저장 (JSON 다운로드 → 업로드 방식) ──
    st.markdown('<hr style="border-color:rgba(56,189,248,0.15);">', unsafe_allow_html=True)
    st.markdown("##### 💾 변경 내역 저장")
    st.caption(
        "간트에서 일정 수정 후 **[💾 저장 (JSON 다운로드)]** 버튼으로 파일을 받고, "
        "아래에 업로드하면 DB에 반영됩니다."
    )

    save_msg = st.session_state.pop("_gantt_save_msg", None)
    if save_msg:
        if save_msg.startswith("✅"):
            st.success(save_msg)
        else:
            st.warning(save_msg)

    uploaded = st.file_uploader(
        "변경 JSON 파일 업로드",
        type=["json"],
        key="proc2_gantt_upload",
        label_visibility="collapsed",
    )

    if uploaded:
        try:
            changes = json.loads(uploaded.read())
            if not isinstance(changes, list) or not changes:
                st.error("❌ 올바른 변경 내역 JSON 파일이 아닙니다.")
                return
            ok, errors = _save_changes(changes)
            if errors:
                st.session_state["_gantt_save_msg"] = (
                    f"⚠️ {ok}건 저장, {len(errors)}건 실패: "
                    + " / ".join(errors[:3])
                )
            else:
                st.session_state["_gantt_save_msg"] = f"✅ {ok}건 일정 업데이트 완료."
            st.rerun()
        except Exception as e:
            logger.error("JSON 업로드 오류: %s\n%s", e, traceback.format_exc())
            st.error("오류가 발생했습니다. 관리자에게 문의해 주세요.")


# ═══════════════════════════════════════════════════════════════
# 독립 페이지 진입점 (app.py 라우팅용)
# ═══════════════════════════════════════════════════════════════
def render():
    from utils.access_log import get_client_user
    from utils.admin import render_admin_login

    current_user = get_client_user()
    with st.sidebar:
        st.markdown("<h3 style='color:#ffffff;'>📅 간트차트</h3>", unsafe_allow_html=True)
        render_admin_login(key_prefix="gantt")

    render_gantt_tab(current_user=current_user, is_admin=st.session_state.get("is_admin", False))
