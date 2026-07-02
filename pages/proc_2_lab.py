"""
[화면 전용] 실험실 — 기준정보 / 공정회의록 작성·수정 / 간트차트를
관리자 전용으로 한 화면에 탭으로 모아 제공
"""

import streamlit as st

from utils.access_log import get_client_user
from utils.admin import render_admin_login


def render():
    current_user = get_client_user()

    with st.sidebar:
        st.markdown("<h3 style='color:#ffffff;'>🧪 실험실</h3>", unsafe_allow_html=True)
        render_admin_login(key_prefix="lab")

    if not st.session_state.get("is_admin"):
        st.warning("⚠️ 관리자 권한이 필요합니다. 사이드바에서 관리자 비밀번호를 입력해 주세요.")
        return

    st.markdown("##### 🧪 실험실 (관리자 전용)")
    st.caption("기준정보 · 공정회의록 작성/수정 · 간트차트를 한 화면에서 관리합니다.")

    tabs = st.tabs(["⚙️ 기준정보", "🖩 공정회의록 작성, 수정", "📅 간트차트"])

    with tabs[0]:
        from pages.proc_2_ref import render_ref_tab
        render_ref_tab()
        st.caption(f"💡 현재 접속자 ID: `{current_user}` — 이 값을 사용자ID에 입력하면 현재 접속자에게 권한 부여")

    with tabs[1]:
        from pages.proc_2_meeting import render_meeting_tab
        render_meeting_tab(current_user=current_user, is_admin=True)

    with tabs[2]:
        from pages.proc_2_gantt import render_gantt_tab
        render_gantt_tab(current_user=current_user, is_admin=True)
