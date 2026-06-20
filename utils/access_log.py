"""
접속자 식별 유틸리티
- 클라이언트 IP / SSO 헤더를 기반으로 현재 접속자를 식별
- 간트 편집 권한, 작성자 표시 등에 사용
"""


def _get_client_ip() -> str:
    """클라이언트 IP 반환
    1순위: Streamlit 내부 API (직접 실행 환경)
    2순위: 프록시 헤더 (nginx 등 리버스 프록시 환경)
    """
    # 1순위: Streamlit 내부 WebSocket 연결에서 직접 추출
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        from streamlit.runtime import get_instance
        ctx     = get_script_run_ctx()
        runtime = get_instance()
        client  = runtime.get_client(ctx.session_id)
        ip      = client.request.remote_ip
        if ip:
            return ip
    except Exception:
        pass

    # 2순위: 리버스 프록시 헤더
    try:
        import streamlit as st
        h  = st.context.headers
        ip = h.get("X-Forwarded-For") or h.get("X-Real-Ip") or ""
        if ip:
            return ip.split(",")[0].strip()
    except Exception:
        pass

    return "unknown"


def get_client_user() -> str:
    """
    현재 접속자 식별자 반환.
    우선순위:
      1) SSO 헤더 (X-Remote-User / X-Auth-User / X-Forwarded-User / Remote-User)
         → DOMAIN\\username 형식이면 username만 추출
      2) 클라이언트 IP (fallback)
    """
    try:
        import streamlit as st
        h = st.context.headers
        for key in ("X-Remote-User", "X-Auth-User", "X-Forwarded-User", "Remote-User", "REMOTE_USER"):
            val = h.get(key, "").strip()
            if val:
                # DOMAIN\username 또는 DOMAIN/username → username만 반환
                return val.split("\\")[-1].split("/")[-1].strip()
    except Exception:
        pass
    return _get_client_ip()
