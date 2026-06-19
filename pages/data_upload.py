import streamlit as st
import pandas as pd
import zipfile
import io
import os
import logging
import traceback

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════
# [설정] 파일명 키워드 → (DB 테이블명, 시트명, 헤더행)
# 파일명(소문자)에 키워드가 포함되면 해당 설정으로 업데이트
# 시트명 None → 첫 번째 시트 사용, 헤더행 0 → 첫 행이 컬럼명
# ══════════════════════════════════════════════════════
TABLE_MAPPING = {
    "proc2":   ("lq_proc2_1",  None, 0),
    "proc1":   ("lq_proc1_1",  None, 0),
    "proc3":   ("lq_proc3_1",  None, 0),
    "proc4":   ("lq_proc4_1",  None, 0),
    "kpi2_1":  ("lq_kpi2_1",   None, 0),
    "kpi2_2":  ("lq_kpi2_2",   None, 0),
    "kpi2_3":  ("lq_kpi2_3",   None, 0),
    "kpi2_4":  ("lq_kpi2_4",   None, 0),
    "kpi2_5":  ("lq_kpi2_5",   None, 0),
    "kpi3":    ("lq_kpi3_1",   None, 0),
    "kpi4":    ("lq_kpi4_1",   None, 0),
    "kpi5":    ("lq_kpi5_1",   None, 0),
    "kpi6":    ("lq_kpi6_1",   None, 0),
    "kpi7":    ("lq_kpi7_1",   None, 0),
}

# 관리자 비밀번호 (.env 에 UPLOAD_ADMIN_PW=비밀번호 로 설정)
_ADMIN_PW = os.environ.get("UPLOAD_ADMIN_PW", "")

# ══════════════════════════════════════════════════════
# 내부 헬퍼 함수
# ══════════════════════════════════════════════════════

def _find_table_config(filename: str):
    """파일명에서 TABLE_MAPPING 설정을 찾아 반환. 없으면 None."""
    lower = filename.lower()
    for keyword, config in TABLE_MAPPING.items():
        if keyword.lower() in lower:
            return config
    return None


def _read_excel(data: bytes, sheet_name, header: int) -> pd.DataFrame:
    """메모리 바이트에서 Excel을 읽어 DataFrame 반환."""
    buf = io.BytesIO(data)
    df = pd.read_excel(buf, sheet_name=sheet_name, header=header)
    # 완전히 빈 행·열 제거
    df = df.dropna(how="all").dropna(axis=1, how="all")
    return df


def _update_table(df: pd.DataFrame, table_name: str):
    """기존 테이블을 새 데이터로 교체 (DROP → CREATE → INSERT)."""
    from utils.db import get_engine
    engine = get_engine()
    df.to_sql(
        name=table_name,
        con=engine,
        if_exists="replace",
        index=False,
        chunksize=500,
    )


def _build_css():
    return """
<style>
.stApp { background-color: #080d15 !important; }
.upload-section {
    background: #111827; border: 1px solid #1e293b;
    border-radius: 12px; padding: 1.5rem; margin-bottom: 1.5rem;
}
.upload-badge-ok {
    display: inline-block; background: rgba(0,224,150,0.15);
    color: #00e096; border: 1px solid rgba(0,224,150,0.3);
    border-radius: 20px; padding: 0.15rem 0.7rem;
    font-size: 0.75rem; font-weight: 700;
}
.upload-badge-skip {
    display: inline-block; background: rgba(255,82,82,0.12);
    color: #ff5252; border: 1px solid rgba(255,82,82,0.25);
    border-radius: 20px; padding: 0.15rem 0.7rem;
    font-size: 0.75rem; font-weight: 700;
}
</style>
"""


# ══════════════════════════════════════════════════════
# 메인 렌더 함수
# ══════════════════════════════════════════════════════

def render():
    st.markdown(_build_css(), unsafe_allow_html=True)
    st.markdown("## 📦 압축파일 자동 업데이트")

    # ── 관리자 비밀번호 미설정 안내 ──
    if not _ADMIN_PW:
        st.error("관리자 비밀번호가 설정되지 않았습니다. .env 파일에 UPLOAD_ADMIN_PW=비밀번호 를 추가해 주세요.")
        return

    # ── 관리자 인증 ──
    if not st.session_state.get("upload_admin_ok"):
        st.info("이 페이지는 관리자 전용입니다.")
        pw = st.text_input("관리자 비밀번호", type="password", key="upload_pw_input")
        if st.button("확인", key="upload_pw_btn"):
            if pw == _ADMIN_PW:
                st.session_state["upload_admin_ok"] = True
                st.rerun()
            else:
                st.error("비밀번호가 올바르지 않습니다.")
        return

    if st.button("🔓 로그아웃", key="upload_logout_btn"):
        st.session_state["upload_admin_ok"] = False
        st.rerun()

    st.markdown("---")
    st.markdown(
        "ZIP 파일 안에 있는 **Excel 파일**을 자동으로 감지하여 해당 DB 테이블을 교체합니다.\n\n"
        "> ⚠️ 업데이트를 실행하면 **기존 테이블 데이터가 모두 삭제**되고 새 데이터로 교체됩니다."
    )

    # ── 매핑 규칙 안내 ──
    with st.expander("📋 파일명-테이블 매핑 규칙 보기"):
        mapping_rows = [
            {"파일명 키워드": k, "DB 테이블": v[0], "시트": v[1] if v[1] else "첫 번째"}
            for k, v in TABLE_MAPPING.items()
        ]
        st.dataframe(pd.DataFrame(mapping_rows), use_container_width=True, hide_index=True)
        st.caption("파일명(소문자)에 키워드가 포함되어 있으면 해당 테이블로 업데이트됩니다.")

    # ── 파일 업로더 ──
    uploaded = st.file_uploader(
        "ZIP 파일 선택 (.zip)",
        type=["zip"],
        key="upload_zip_file",
    )

    if not uploaded:
        return

    # ── ZIP 파싱 ──
    try:
        zip_bytes = uploaded.read()
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
        excel_names = [
            n for n in zf.namelist()
            if n.lower().endswith((".xlsx", ".xls"))
            and not os.path.basename(n).startswith(("~$", ".", "__"))
            and "__MACOSX" not in n
        ]
    except Exception as e:
        logger.error("ZIP 파싱 오류: %s\n%s", e, traceback.format_exc())
        st.error("ZIP 파일을 읽는 중 오류가 발생했습니다. 관리자에게 문의해 주세요.")
        return

    if not excel_names:
        st.warning("ZIP 파일 안에 Excel 파일(.xlsx / .xls)이 없습니다.")
        return

    # ── 파일별 매핑 분류 ──
    file_configs = []
    for zip_path in excel_names:
        basename = os.path.basename(zip_path)
        config = _find_table_config(basename)
        file_configs.append({
            "zip_path": zip_path,
            "filename": basename,
            "table":    config[0] if config else None,
            "sheet":    config[1] if config else None,
            "header":   config[2] if config else 0,
            "matched":  config is not None,
        })

    matched   = [f for f in file_configs if f["matched"]]
    unmatched = [f for f in file_configs if not f["matched"]]

    st.markdown(
        f"**ZIP 내 Excel {len(excel_names)}개 발견** &nbsp;·&nbsp; "
        f"<span class='upload-badge-ok'>업데이트 대상 {len(matched)}개</span> &nbsp; "
        f"<span class='upload-badge-skip'>건너뜀 {len(unmatched)}개</span>",
        unsafe_allow_html=True,
    )

    if unmatched:
        with st.expander(f"⚠️ 매핑 없는 파일 {len(unmatched)}개 (건너뜀)"):
            for f in unmatched:
                st.markdown(f"- `{f['filename']}` — 파일명에 매핑 키워드가 없음")

    if not matched:
        st.warning("업데이트할 수 있는 파일이 없습니다. 파일명과 매핑 규칙을 확인해 주세요.")
        return

    # ── 미리보기 로드 ──
    st.markdown("### 📊 업데이트 대상 파일 미리보기")
    previews: dict[str, pd.DataFrame | None] = {}

    for fc in matched:
        try:
            data = zf.read(fc["zip_path"])
            df   = _read_excel(data, fc["sheet"], fc["header"])
            previews[fc["zip_path"]] = df
            with st.expander(
                f"📄 **{fc['filename']}** → `{fc['table']}` &nbsp;&nbsp;"
                f"({len(df):,}행 × {len(df.columns)}열)"
            ):
                st.dataframe(df.head(10), use_container_width=True, hide_index=True)
        except Exception as e:
            logger.error("Excel 미리보기 오류 (%s): %s\n%s", fc["filename"], e, traceback.format_exc())
            st.error(f"**{fc['filename']}**: 파일을 읽는 중 오류가 발생했습니다.")
            previews[fc["zip_path"]] = None

    valid_configs = [fc for fc in matched if previews.get(fc["zip_path"]) is not None]

    if not valid_configs:
        st.error("읽을 수 있는 파일이 없습니다.")
        return

    # ── 최종 확인 및 업데이트 실행 ──
    st.markdown("---")
    st.warning(
        f"⚠️ 아래 **{len(valid_configs)}개 테이블**의 기존 데이터가 모두 삭제되고 새 데이터로 교체됩니다.",
        icon="⚠️",
    )
    for fc in valid_configs:
        df = previews[fc["zip_path"]]
        st.markdown(f"- `{fc['table']}` ← **{fc['filename']}** ({len(df):,}행 삽입)")

    col_btn, _ = st.columns([1, 4])
    with col_btn:
        confirmed = st.button(
            "✅ 업데이트 실행",
            type="primary",
            key="upload_confirm_btn",
            use_container_width=True,
        )

    if not confirmed:
        return

    # ── 업데이트 실행 ──
    progress_bar = st.progress(0, text="업데이트 준비 중...")
    success_count = 0

    for i, fc in enumerate(valid_configs):
        df = previews[fc["zip_path"]]
        progress_bar.progress(
            i / len(valid_configs),
            text=f"업데이트 중... {fc['table']} ({i+1}/{len(valid_configs)})",
        )
        try:
            _update_table(df, fc["table"])
            st.success(f"✓ `{fc['table']}` — {len(df):,}행 업데이트 완료")
            success_count += 1
        except Exception as e:
            logger.error("테이블 업데이트 오류 (%s): %s\n%s", fc["table"], e, traceback.format_exc())
            st.error(f"`{fc['table']}` 업데이트 중 오류가 발생했습니다. 관리자에게 문의해 주세요.")

    progress_bar.progress(1.0, text="완료!")

    if success_count == len(valid_configs):
        st.balloons()
        st.success(f"🎉 전체 업데이트 완료! ({success_count}/{len(valid_configs)}개 테이블)")
    else:
        st.warning(f"일부 업데이트 실패 ({success_count}/{len(valid_configs)}개 성공)")

    # 캐시 초기화 (홈 대시보드 카드 등 즉시 반영)
    st.cache_data.clear()
    st.info("💡 캐시가 초기화되었습니다. 새로 고침하면 최신 데이터가 반영됩니다.")
