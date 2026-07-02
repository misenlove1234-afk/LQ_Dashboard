"""
관리자 로그인 공통 유틸
- proc_2 계열 여러 페이지(사곡 거주구 제작 현황, 기준정보, 공정회의록, 간트차트)가
  동일한 관리자 비밀번호/세션 상태(st.session_state["is_admin"])를 공유하기 위한 헬퍼
"""

import os
import streamlit as st


def render_admin_login(key_prefix: str, label: str = "🔐 관리자") -> None:
    """사이드바 등에서 호출 — 관리자 비밀번호 입력 위젯을 렌더링하고
    st.session_state["is_admin"]을 갱신한다.

    key_prefix: 위젯 key 접두사 (페이지별로 달라야 함, 예: "proc2", "ref", "gantt")
    label: 입력창 위에 표시할 안내 문구 (호출부에서 번호 등을 붙이고 싶으면 직접 지정)
    """
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin1234")
    st.write(label)
    admin_input = st.text_input("비밀번호", type="password", key=f"{key_prefix}_admin_pw")
    if admin_input == ADMIN_PASSWORD:
        st.session_state["is_admin"] = True
        st.success("✅ 관리자 모드")
    elif admin_input:
        st.session_state["is_admin"] = False
        st.error("❌ 비밀번호 오류")
    else:
        st.session_state.setdefault("is_admin", False)
