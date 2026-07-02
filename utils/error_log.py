"""
오류 로그 유틸리티
- DB 연결이 끊긴 상황에서도 기록되도록 파일 기반(logs/error_log.jsonl)으로 구현
- 화면(일반 사용자)에는 짧은 오류코드만 노출하고,
  실제 예외 메시지·트레이스백은 관리자 전용 조회 화면에서만 확인 가능
"""

import json
import logging
import os
import random
import string
import traceback
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

_LOG_DIR  = Path(__file__).parent.parent / "logs"
_LOG_FILE = _LOG_DIR / "error_log.jsonl"

_CODE_CHARS = string.ascii_uppercase + string.digits


def mask_secrets(text: str) -> str:
    """.env에 등록된 비밀번호 값이 예외 메시지에 섞여 있으면 마스킹."""
    if not text:
        return text
    pw = os.getenv("PASSWORD")
    if pw and pw in text:
        text = text.replace(pw, "********")
    return text


def log_error(context: str, exc: Exception, user: str = "") -> str:
    """예외를 서버 로그 + 파일(logs/error_log.jsonl)에 기록하고 짧은 오류코드를 반환.

    Parameters
    ----------
    context : 오류가 발생한 위치 설명 (예: "공정 페이지 렌더링 오류 (proc_2)")
    exc     : 발생한 예외
    user    : 접속자 식별값 (있으면 기록)

    Returns
    -------
    str  화면에 노출해도 안전한 짧은 오류코드
    """
    code = (
        datetime.now().strftime("%m%d-%H%M%S") + "-"
        + "".join(random.choices(_CODE_CHARS, k=4))
    )
    tb = mask_secrets(traceback.format_exc())
    msg = mask_secrets(str(exc))

    logger.error("[%s] %s: %s\n%s", code, context, msg, tb)

    entry = {
        "code":       code,
        "time":       datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "context":    context,
        "user":       user,
        "error_type": type(exc).__name__,
        "message":    msg,
        "traceback":  tb,
    }
    try:
        _LOG_DIR.mkdir(parents=True, exist_ok=True)
        with open(_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        logger.error("오류 로그 파일 기록 실패", exc_info=True)

    return code


def read_error_logs(limit: int = 200):
    """최근 오류 로그를 최신순으로 반환 (관리자 조회 화면용)."""
    import pandas as pd

    columns = ["code", "time", "context", "user", "error_type", "message", "traceback"]
    if not _LOG_FILE.exists():
        return pd.DataFrame(columns=columns)

    rows = []
    with open(_LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue

    df = pd.DataFrame(rows, columns=columns)
    if df.empty:
        return df
    return df.sort_values("time", ascending=False).head(limit).reset_index(drop=True)
