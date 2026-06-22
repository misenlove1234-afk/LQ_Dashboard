"""
╔══════════════════════════════════════════════════════════════════╗
║  항목   : [데이터 전용] proc_2 - 사곡공장 선실 제작 현황         ║
║  담당자 : ___________                                            ║
║  작성일 : ___________                                            ║
║  설명   : DB 조회/계산 + 간트 편집 저장 (변경 이력 자동 기록)    ║
╚══════════════════════════════════════════════════════════════════╝

【 🤖 AI 바이브 코딩을 위한 프롬프트 가이드 】
"이 파일은 Streamlit 앱의 '데이터 처리 전용' 모듈이야.
1. 절대 st.write, st.dataframe 같은 화면 UI 코드를 넣지 마.
2. utils.db 의 run_query / execute_query 함수를 사용해서 DB에서 데이터를 불러와.
3. 무거운 연산을 하는 함수 위에는 반드시 @st.cache_data(ttl=3600, max_entries=50) 를 붙여.
4. 최종 결과물은 Pandas DataFrame 으로 return 해줘."
"""

import re
import json
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

from utils.db import run_query, execute_query


# ──────────────────────────────────────────────
# DB 테이블명 (변경 시 여기만 수정)
# ──────────────────────────────────────────────
TABLE_PROCESS  = "lq_proc2_1"          # 공정 현황 테이블
TABLE_CHG_LOG  = "lq_proc2_2"          # ★ 공정 변경 이력 (없으면 자동 생성)
TABLE_AUTH     = "lq_proc2_3"          # ★ 간트 편집 권한 테이블 (없으면 자동 생성)
TABLE_SUNPYO   = "dbo.lq_kpi5_1"      # 선표 (탑재착수 등 마일스톤 조회)


# ══════════════════════════════════════════════
#  1. 공정 데이터 로드 (기존)
# ══════════════════════════════════════════════
@st.cache_data(ttl=3600, max_entries=50)
def load_data() -> pd.DataFrame:
    """
    운반선 공정 현황 원본 데이터 로드
    - lq_proc2_1 테이블에서 전체 데이터 조회
    - 컬럼명 정규화 및 날짜 형변환 포함
    """
    df = run_query(f"SELECT * FROM [{TABLE_PROCESS}]")

    # 컬럼명 정규화
    def _norm(col):
        c = re.sub(r'[\s()]+', '_', col.strip())
        return re.sub(r'_+', '_', c).strip('_')
    df.columns = [_norm(c) for c in df.columns]

    # 컬럼 표준화
    column_mapping = {
        'STAGE':      'STG',
        '실적_C_완료': '실적_C_종료',
    }
    rename_dict = {k: v for k, v in column_mapping.items() if k in df.columns}
    df = df.rename(columns=rename_dict)
    # 작업내용이 없으면 중분류를 복사해 사용 (중분류 원본은 그대로 보존 →
    # 30STG 구역 판정(중분류 기준)에 활용)
    if '작업내용' not in df.columns and '중분류' in df.columns:
        df['작업내용'] = df['중분류']

    # 날짜 컬럼 변환
    date_cols = [
        '초기_계획_A_착수', '초기_계획_A_완료',
        '변경_계획_B_착수', '변경_계획_B_완료',
        '실적_C_착수',      '실적_C_종료'
    ]
    for col in date_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce').dt.normalize()

    required_cols = [
        '프로젝트', 'STG', '대분류', '중분류', '작업내용', '공종', '점유율',
        '초기_계획_A_착수', '초기_계획_A_완료',
        '변경_계획_B_착수', '변경_계획_B_완료',
        '실적_C_착수',      '실적_C_종료'
    ]
    # 작업ID(PK)가 있으면 포함, 없으면 생략
    if '작업ID' in df.columns:
        required_cols = ['작업ID'] + required_cols
    if '선종' in df.columns:
        required_cols = ['선종'] + required_cols
    # 간트 표시여부 컬럼이 있으면 보존 (Y 만 화면/인쇄에 출력)
    if '표시여부' in df.columns:
        required_cols.append('표시여부')
    # 간트 시각화 보조 컬럼 (있으면 포함 — 없으면 조용히 생략)
    for col in ['내외구분', '담당자', '진행상태']:
        if col in df.columns:
            required_cols.append(col)

    existing_cols = [col for col in required_cols if col in df.columns]
    df = df[existing_cols]
    df = df.loc[:, ~df.columns.duplicated()]

    return df


# ══════════════════════════════════════════════
#  2. 프로젝트 필터링 (기존)
# ══════════════════════════════════════════════
def get_filtered_projects(
    df: pd.DataFrame,
    start_date, end_date,
    stgs_filter: list,
    include_completed: bool,
    use_all_period: bool,
) -> list:
    """조회 기간 + 완료 프로젝트 포함 여부에 따라 표시할 프로젝트 목록 반환"""
    today = pd.Timestamp(datetime.now().date())
    date_filter_cols = [
        '초기_계획_A_착수', '초기_계획_A_완료',
        '변경_계획_B_착수', '변경_계획_B_완료',
        '실적_C_착수',      '실적_C_종료'
    ]

    if use_all_period:
        base_projects = sorted(df['프로젝트'].unique())
    else:
        period_start = pd.Timestamp(start_date)
        period_end   = pd.Timestamp(end_date)
        in_period    = pd.Series([False] * len(df), index=df.index)
        for col in [c for c in date_filter_cols if c in df.columns]:
            in_period = in_period | (
                df[col].notna() &
                (df[col] >= period_start) &
                (df[col] <= period_end)
            )
        base_projects = sorted(df.loc[in_period, '프로젝트'].unique())

    if include_completed:
        return base_projects

    final_projects = []
    has_30 = '30' in stgs_filter
    has_50 = '50' in stgs_filter

    for proj in base_projects:
        proj_df = df[df['프로젝트'] == proj]
        has_30_in_proj = '30' in proj_df['STG'].astype(str).values
        has_50_in_proj = '50' in proj_df['STG'].astype(str).values

        m610c_done = False
        if has_30_in_proj:
            m610c_data = proj_df[proj_df['대분류'] == 'M610C']
            if not m610c_data.empty and m610c_data['실적_C_종료'].notna().any():
                m610c_done = True

        living_q_done = False
        if has_50_in_proj:
            living_q = proj_df[proj_df['작업내용'] == '거주구 인양']
            if not living_q.empty and (living_q['실적_C_종료'].dropna() <= today).any():
                living_q_done = True

        hide = False
        if has_30 and not has_50:
            if has_30_in_proj and m610c_done: hide = True
        elif has_50 and not has_30:
            if has_50_in_proj and living_q_done: hide = True
        elif has_30 and has_50:
            hide_30 = m610c_done   if has_30_in_proj else True
            hide_50 = living_q_done if has_50_in_proj else True
            if hide_30 and hide_50: hide = True

        if not hide:
            final_projects.append(proj)

    return final_projects


# ══════════════════════════════════════════════
#  3. 공정 진도율 계산 (기존)
# ══════════════════════════════════════════════
def compute_progress(filtered_df: pd.DataFrame, start_date, end_date) -> dict:
    """S-Curve 및 KPI 지표 계산"""
    today       = pd.Timestamp(datetime.now().date())
    chart_dates = pd.date_range(start=start_date, end=end_date, freq='D')
    progress_df = pd.DataFrame(index=chart_dates)
    total_weight = filtered_df['점유율'].sum()

    def cumulative_series(df, date_col, weight_col):
        return (df.groupby(date_col)[weight_col]
                  .sum().reindex(chart_dates, fill_value=0).cumsum())

    cum_a   = cumulative_series(filtered_df, '초기_계획_A_완료', '점유율')
    cum_b   = cumulative_series(filtered_df, '변경_계획_B_완료', '점유율')
    cum_act = cumulative_series(filtered_df, '실적_C_종료',      '점유율')

    if total_weight > 0:
        progress_df['초기 계획'] = (cum_a   / total_weight) * 100
        progress_df['변경 계획'] = (cum_b   / total_weight) * 100
        progress_df['실적']      = (cum_act / total_weight) * 100
    else:
        progress_df['초기 계획'] = progress_df['변경 계획'] = progress_df['실적'] = 0

    def _safe_get(col):
        if today in progress_df.index: return progress_df.loc[today, col]
        return progress_df[col].iloc[-1] if not progress_df.empty else 0

    curr_a   = _safe_get('초기 계획')
    curr_b   = _safe_get('변경 계획')
    curr_act = _safe_get('실적')

    progress_df.loc[progress_df.index > today, '실적'] = None
    curr_act = 0 if pd.isna(curr_act) else curr_act

    target      = filtered_df[filtered_df['변경_계획_B_완료'] <= today]
    plan_w      = target['점유율'].sum()
    compliant_w = target[target['실적_C_종료'].notna()]['점유율'].sum()
    adherence   = (compliant_w / plan_w) * 100 if plan_w > 0 else 0

    return {
        'progress_df':    progress_df,
        'curr_prog_a':    curr_a,
        'curr_prog_b':    curr_b,
        'curr_prog_act':  curr_act,
        'adherence_rate': adherence,
    }


# ══════════════════════════════════════════════
#  4. 지연 분석 (기존)
# ══════════════════════════════════════════════
def compute_delays(filtered_df: pd.DataFrame) -> dict:
    """공종별/구역별 누적 지연일수 계산"""
    today = pd.Timestamp(datetime.now().date())
    df    = filtered_df.copy()

    def _calc_delay(row):
        if pd.notnull(row['실적_C_종료']) and pd.notnull(row['변경_계획_B_완료']):
            return (row['실적_C_종료'] - row['변경_계획_B_완료']).days
        if pd.isna(row['실적_C_종료']) and pd.notnull(row['변경_계획_B_완료']):
            if row['변경_계획_B_완료'] < today:
                return (today - row['변경_계획_B_완료']).days
        return 0

    df['Calculated_Delay'] = df.apply(_calc_delay, axis=1)

    delay_by_gongjong = (df.groupby('공종')['Calculated_Delay']
                          .sum().reset_index()
                          .rename(columns={'Calculated_Delay': '누적 지연일수'})
                          .sort_values('누적 지연일수', ascending=False))
    delay_by_area = (df.groupby('대분류')['Calculated_Delay']
                       .sum().reset_index()
                       .rename(columns={'대분류': 'AREA'}))

    return {
        'delay_by_gongjong':   delay_by_gongjong,
        'delay_by_area':       delay_by_area,
        'filtered_with_delay': df,
    }


# ══════════════════════════════════════════════════════
#  ★ 5. 간트 차트용 데이터 변환  (신규)
# ══════════════════════════════════════════════════════
def sort_areas(areas: list) -> list:
    """
    Y축(구역) 정렬 규칙:
      1) NAV-DK 최상단
      2) 일반 DK (F→E→D→C→B→A 알파벳 역순)
      3) UPP-DK
      4) M블럭 (숫자 오름차순, 같은 숫자 내 P→C→S 순)
      5) 기타 (맨 아래, 알파벳순)
    """
    SIDE_ORDER = {'P': 0, 'C': 1, 'S': 2}

    def sort_key(name: str):
        if name == 'NAV-DK':           cat = 0
        elif name == 'UPP-DK':         cat = 2
        elif name.endswith('-DK'):     cat = 1
        elif re.match(r'^M\d+', name): cat = 3
        else:                          cat = 4

        if cat == 1:  # DK 알파벳 역순
            return (cat, -ord(name[0]), name)
        if cat == 3:  # M블럭: 숫자↑, P/C/S 순
            m = re.match(r'^M(\d+)([A-Z]?)', name)
            num  = int(m.group(1)) if m else 99999
            side = m.group(2) if m else ''
            return (cat, num, SIDE_ORDER.get(side, 9), name)
        return (cat, 0, 0, name)

    return sorted(areas, key=sort_key)


# 차트 조회 기준 → (착수컬럼, 완료컬럼) 매핑
GANTT_BASIS_COLS = {
    "변경 계획": ('변경_계획_B_착수', '변경_계획_B_완료'),
    "초기 계획": ('초기_계획_A_착수', '초기_계획_A_완료'),
    "실적":     ('실적_C_착수',     '실적_C_종료'),
}


def get_gantt_data(filtered_df: pd.DataFrame, basis: str = "변경 계획") -> list:
    """
    필터링된 공정 DataFrame → 간트 HTML 컴포넌트용 JSON 리스트

    basis: 간트 막대 기준일
      - "변경 계획" (기본) : 변경_계획_B_착수 / 변경_계획_B_완료
      - "초기 계획"        : 초기_계획_A_착수 / 초기_계획_A_완료
      - "실적"             : 실적_C_착수     / 실적_C_종료

    출력 구조 (HTML 컴포넌트가 기대하는 포맷):
    [
      { id, proj, area, gj, task, s, e, stg, shipType },
      ...
    ]
    """
    s_col, e_col = GANTT_BASIS_COLS.get(basis, GANTT_BASIS_COLS["변경 계획"])

    df = filtered_df.copy()

    # 선택된 기준일이 없는 행은 간트에서 제외
    if s_col not in df.columns or e_col not in df.columns:
        return []
    df = df.dropna(subset=[s_col, e_col])

    # 표시여부가 없는 행은 'Y' 로 간주 — JS에서 showFlag 기준으로 숨김 처리
    # (여기서 필터링하지 않고 전체 전달, 숨기기 버튼으로 클라이언트 측 토글)

    tasks = []
    for idx, row in df.iterrows():
        # 30STG는 구역 기준이 '중분류', 그 외는 '대분류' (중분류 비어 있으면 대분류 폴백)
        stg_str = str(row.get('STG', '')).strip().upper()
        is_30stg = stg_str in ('30STG', '30')
        _area_val = row.get('중분류') if (is_30stg and pd.notna(row.get('중분류'))) else row.get('대분류', '')

        # 표시여부 — Y/N 그대로 전달 (없으면 'Y' 기본)
        show_flag = 'Y'
        if '표시여부' in df.columns:
            raw_flag = str(row.get('표시여부', '') or '').strip().upper()
            show_flag = raw_flag if raw_flag in ('Y', 'N') else 'Y'

        # 실적_C_착수 값 존재 여부 → 착수 완료 체크 아이콘 표시용
        started = False
        if '실적_C_착수' in df.columns:
            started = pd.notna(row.get('실적_C_착수'))

        tasks.append({
            'id':       str(row.get('작업ID', f'ROW_{idx}')),
            'proj':     str(row['프로젝트']),
            'area':     str(_area_val or ''),
            'gj':       str(row.get('공종', '')),
            'task':     str(row.get('작업내용', '')),
            's':        row[s_col].strftime('%Y-%m-%d'),
            'e':        row[e_col].strftime('%Y-%m-%d'),
            'stg':      str(row.get('STG', '')),
            'shipType': str(row.get('선종', '')),
            'inOut':    str(row.get('내외구분', '') or '').strip(),
            'manager':  str(row.get('담당자',   '') or '').strip(),
            'status':   str(row.get('진행상태', '') or '').strip(),
            'showFlag': show_flag,
            'started':  started,
        })
    return tasks


# ══════════════════════════════════════════════════════
#  ★ 6. 간트 편집 저장 - 변경 이력 테이블 자동 생성
# ══════════════════════════════════════════════════════
def ensure_chg_log_table() -> bool:
    """
    변경 이력 테이블(lq_proc2_2)이 없으면 생성.
    이미 존재하면 아무 동작 없음 (idempotent - 여러 번 호출해도 안전).
    """
    ddl = f"""
    IF OBJECT_ID('{TABLE_CHG_LOG}', 'U') IS NULL
    BEGIN
        CREATE TABLE [{TABLE_CHG_LOG}] (
            변경ID       INT IDENTITY(1,1) PRIMARY KEY,
            작업ID       NVARCHAR(50)    NULL,
            프로젝트     NVARCHAR(20)    NOT NULL,
            대분류       NVARCHAR(30)    NULL,
            공종         NVARCHAR(20)    NULL,
            작업내용     NVARCHAR(200)   NULL,
            변경전_착수  DATE            NULL,
            변경전_완료  DATE            NULL,
            변경후_착수  DATE            NULL,
            변경후_완료  DATE            NULL,
            변경구분     NVARCHAR(20)    NULL,
            변경자       NVARCHAR(50)    NULL,
            변경일시     DATETIME        DEFAULT GETDATE(),
            회의메모     NVARCHAR(300)   NULL
        );
        CREATE INDEX IX_lq_proc2_2_프로젝트  ON [{TABLE_CHG_LOG}](프로젝트);
        CREATE INDEX IX_lq_proc2_2_변경일시  ON [{TABLE_CHG_LOG}](변경일시 DESC);
        CREATE INDEX IX_lq_proc2_2_작업ID    ON [{TABLE_CHG_LOG}](작업ID);
    END
    """
    return execute_query(ddl)


def _classify_change(old_s, old_e, new_s, new_e) -> str:
    """변경 유형 분류 - 이력 테이블의 '변경구분' 값"""
    s_changed = str(old_s) != str(new_s)
    e_changed = str(old_e) != str(new_e)
    if s_changed and e_changed:
        try:
            old_dur = (pd.Timestamp(old_e) - pd.Timestamp(old_s)).days
            new_dur = (pd.Timestamp(new_e) - pd.Timestamp(new_s)).days
            return '이동' if old_dur == new_dur else '전체변경'
        except Exception:
            return '전체변경'
    if s_changed: return '시작일조정'
    if e_changed: return '종료일조정'
    return '변경없음'


def save_gantt_changes(
    changes: list,
    user_name: str,
    memo: str = None,
) -> dict:
    """
    드래그 편집된 공정 일정을 DB에 일괄 반영

    Parameters
    ----------
    changes : list[dict]
        HTML 컴포넌트가 내보낸 JSON. 각 원소:
        { task_id, project, area, gongjong, task_name,
          old_start, old_end, new_start, new_end }
    user_name : str
        변경자 (예: os.getlogin())
    memo : str, optional
        회의 메모

    Returns
    -------
    dict  { 'success': int, 'failed': int, 'errors': list[dict] }
    """
    ensure_chg_log_table()
    success, failed, errors = 0, 0, []

    for c in changes:
        try:
            chg_type = _classify_change(
                c['old_start'], c['old_end'],
                c['new_start'], c['new_end']
            )
            if chg_type == '변경없음':
                continue

            # (1) 이력 테이블 INSERT
            execute_query(
                f"INSERT INTO [{TABLE_CHG_LOG}] "
                f"(작업ID, 프로젝트, 대분류, 공종, 작업내용, "
                f" 변경전_착수, 변경전_완료, 변경후_착수, 변경후_완료, "
                f" 변경구분, 변경자, 회의메모) "
                f"VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    c.get('task_id'), c['project'], c.get('area'),
                    c.get('gongjong'), c.get('task_name'),
                    c['old_start'], c['old_end'],
                    c['new_start'], c['new_end'],
                    chg_type, user_name, memo,
                )
            )

            # (2) 실제 공정 테이블 UPDATE
            # ⚠️ lq_proc2_1에 작업ID(PK)가 있으면 그걸로 UPDATE, 없으면 복합 조건
            if c.get('task_id'):
                execute_query(
                    f"UPDATE [{TABLE_PROCESS}] "
                    f"SET 변경_계획_B_착수=?, 변경_계획_B_완료=? "
                    f"WHERE 작업ID=?",
                    (c['new_start'], c['new_end'], c['task_id'])
                )
            else:
                execute_query(
                    f"UPDATE [{TABLE_PROCESS}] "
                    f"SET 변경_계획_B_착수=?, 변경_계획_B_완료=? "
                    f"WHERE 프로젝트=? AND 대분류=? AND 작업내용=?",
                    (c['new_start'], c['new_end'],
                     c['project'], c.get('area'), c.get('task_name'))
                )
            success += 1

        except Exception as e:
            failed += 1
            errors.append({
                'task_id': c.get('task_id'),
                'project': c.get('project'),
                'task':    c.get('task_name'),
                'error':   str(e),
            })

    return {'success': success, 'failed': failed, 'errors': errors}


def load_change_history(
    task_id: str = None,
    project: str = None,
    days: int = 30,
) -> pd.DataFrame:
    """
    변경 이력 조회
    - task_id 지정: 특정 작업의 전체 이력
    - project 지정: 특정 호선의 최근 N일 이력
    - 둘 다 None: 최근 N일 전체 이력
    - 테이블 미존재 시 빈 DataFrame 반환
    """
    exists = run_query(
        f"SELECT COUNT(*) AS cnt FROM sys.tables WHERE name = '{TABLE_CHG_LOG}'"
    )
    if exists.empty or int(exists.iloc[0]['cnt']) == 0:
        return pd.DataFrame()

    if task_id:
        return run_query(
            f"SELECT * FROM [{TABLE_CHG_LOG}] WHERE 작업ID=? "
            f"ORDER BY 변경일시 DESC", (task_id,))
    if project:
        return run_query(
            f"SELECT * FROM [{TABLE_CHG_LOG}] "
            f"WHERE 프로젝트=? AND 변경일시 >= DATEADD(day, -?, GETDATE()) "
            f"ORDER BY 변경일시 DESC", (project, days))
    return run_query(
        f"SELECT * FROM [{TABLE_CHG_LOG}] "
        f"WHERE 변경일시 >= DATEADD(day, -?, GETDATE()) "
        f"ORDER BY 변경일시 DESC", (days,))


# ══════════════════════════════════════════════
#  ★ 7. 간트 편집 권한 관리
# ══════════════════════════════════════════════
def ensure_auth_table() -> bool:
    """lq_proc2_3 테이블이 없으면 자동 생성 (idempotent)."""
    ddl = f"""
    IF OBJECT_ID('{TABLE_AUTH}', 'U') IS NULL
    BEGIN
        CREATE TABLE [{TABLE_AUTH}] (
            ID        INT IDENTITY(1,1) PRIMARY KEY,
            사용자ID  NVARCHAR(100) NOT NULL UNIQUE,
            이름      NVARCHAR(50)  NOT NULL,
            등록자    NVARCHAR(50)  NULL,
            등록일시  DATETIME      DEFAULT GETDATE(),
            만료일    DATE          NULL
        );
    END
    """
    return execute_query(ddl)


def check_gantt_permission(user_id: str) -> bool:
    """현재 사용자의 간트 편집 권한 여부 확인 (만료일 자동 체크)."""
    if not user_id:
        return False
    try:
        ensure_auth_table()
        df = run_query(
            f"SELECT COUNT(*) AS cnt FROM [{TABLE_AUTH}] "
            f"WHERE 사용자ID = ? AND (만료일 IS NULL OR 만료일 >= CAST(GETDATE() AS DATE))",
            params=(user_id,)
        )
        return not df.empty and int(df.iloc[0]["cnt"]) > 0
    except Exception:
        return False


def get_auth_list() -> pd.DataFrame:
    """권한자 목록 조회."""
    try:
        ensure_auth_table()
        return run_query(f"SELECT * FROM [{TABLE_AUTH}] ORDER BY 등록일시 DESC")
    except Exception:
        return pd.DataFrame()


def add_auth_user(user_id: str, name: str, registrant: str, expire_date=None) -> bool:
    """권한자 추가 — 이미 있으면 이름/만료일 업데이트 (MERGE)."""
    ensure_auth_table()
    return execute_query(
        f"MERGE [{TABLE_AUTH}] AS t "
        f"USING (SELECT ? AS uid) AS s ON t.사용자ID = s.uid "
        f"WHEN MATCHED THEN UPDATE SET 이름=?, 등록자=?, 만료일=? "
        f"WHEN NOT MATCHED THEN INSERT (사용자ID, 이름, 등록자, 만료일) VALUES (?, ?, ?, ?);",
        (user_id, name, registrant, expire_date, user_id, name, registrant, expire_date)
    )


def remove_auth_user(user_id: str) -> bool:
    """권한자 삭제."""
    return execute_query(
        f"DELETE FROM [{TABLE_AUTH}] WHERE 사용자ID = ?",
        (user_id,)
    )


# ══════════════════════════════════════════════
#  ★ 8. 새 작업 추가 (간트 차트 신규 등록)
# ══════════════════════════════════════════════
def add_new_task(
    project: str,
    ship_type: str,
    stg: str,
    area: str,
    gongjong: str,
    task_name: str,
    weight: float,
    plan_start,
    plan_end,
    user_name: str,
    memo: str = None,
) -> bool:
    """
    새 작업을 lq_proc2_1에 INSERT 하고 변경 이력에 '신규등록' 기록.
    - 초기 계획(A) = 변경 계획(B)로 동일 적용
    - 실적(C) 는 NULL (미완료 상태)
    - 실패 시 서버 로그에만 상세 기록, 호출측은 bool만 받음

    Returns
    -------
    bool  성공 여부
    """
    import logging, traceback
    logger = logging.getLogger(__name__)
    try:
        # (1) lq_proc2_1 INSERT
        execute_query(
            f"INSERT INTO [{TABLE_PROCESS}] "
            f"(프로젝트, 선종, STG, 대분류, 공종, 작업내용, 점유율, "
            f" 초기_계획_A_착수, 초기_계획_A_완료, "
            f" 변경_계획_B_착수, 변경_계획_B_완료) "
            f"VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                project, ship_type or None, stg, area, gongjong, task_name, weight,
                plan_start, plan_end, plan_start, plan_end,
            )
        )

        # (2) 이력 테이블에 '신규등록' 기록
        ensure_chg_log_table()
        execute_query(
            f"INSERT INTO [{TABLE_CHG_LOG}] "
            f"(프로젝트, 대분류, 공종, 작업내용, "
            f" 변경후_착수, 변경후_완료, 변경구분, 변경자, 회의메모) "
            f"VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                project, area, gongjong, task_name,
                plan_start, plan_end, '신규등록', user_name, memo,
            )
        )
        return True
    except Exception as e:
        logger.error("새 작업 등록 실패: %s\n%s", e, traceback.format_exc())
        return False


# ══════════════════════════════════════════════
#  9. 간트 인쇄용 HTML 생성 (화면과 동일 스타일)
# ══════════════════════════════════════════════
def _row_to_print_task(row, fallback_id: str = "ROW") -> dict | None:
    """공정 한 행 → 인쇄 템플릿용 task dict. 날짜 결측 시 None.
    30STG 구역은 '중분류' 기준, 그 외는 '대분류'."""
    s = row.get('변경_계획_B_착수')
    e = row.get('변경_계획_B_완료')
    if pd.isna(s) or pd.isna(e):
        return None
    stg_str = str(row.get('STG', '')).strip().upper()
    is_30stg = stg_str in ('30STG', '30')
    _area_val = row.get('중분류') if (is_30stg and pd.notna(row.get('중분류'))) else row.get('대분류', '')
    return {
        "id":   str(row.get('작업ID', fallback_id)),
        "proj": str(row.get('프로젝트', '') or ''),
        "area": str(_area_val or ''),
        "gj":   str(row.get('공종', '') or ''),
        "task": str(row.get('작업내용', '') or ''),
        "s":    s.strftime('%Y-%m-%d'),
        "e":    e.strftime('%Y-%m-%d'),
    }


def generate_gantt_print_html(
    df: pd.DataFrame,
    ships: list = None,
    stages: list = None,
    date_start=None, date_end=None,
    gongjongs: list = None,
    row_mode: str = None,
) -> str:
    """호선×STG 조합별 간트 섹션을 묶은 인쇄용 HTML 문자열 반환.

    사용 흐름: `components.html(html, ...)` 로 렌더 → 내부 버튼 클릭 →
    브라우저 인쇄 대화상자 → "대상: PDF로 저장" 선택.

    인자
    - df: 공정 원본 (load_data 결과)
    - ships/stages/gongjongs: 필터 (None/빈 리스트면 전체)
    - date_start/date_end: 두 날짜 사이에 걸치는 작업만 출력
    - row_mode: 'area' | 'ship' | None(자동). None이면 공종 1개만 남을 때
      'ship' 모드(한 장 통합, 화면 ship-mode와 동일), 아니면 'area' 모드.
    """
    from pathlib import Path
    from datetime import datetime

    work = df.copy()
    # 표시여부 == 'Y' 만 인쇄 (화면 간트와 동일 정책)
    if '표시여부' in work.columns:
        work = work[work['표시여부'].astype(str).str.strip().str.upper() == 'Y']
    if ships:
        work = work[work['프로젝트'].isin(ships)]
    if stages:
        stg_strs = [str(s) for s in stages]
        work = work[work['STG'].astype(str).isin(stg_strs)]
    if gongjongs:
        work = work[work['공종'].isin(gongjongs)]

    ts_start = pd.Timestamp(date_start) if date_start else None
    ts_end   = pd.Timestamp(date_end)   if date_end   else None
    if ts_start is not None and ts_end is not None:
        mask = (
            work['변경_계획_B_착수'].notna() &
            work['변경_계획_B_완료'].notna() &
            (work['변경_계획_B_착수'] <= ts_end) &
            (work['변경_계획_B_완료'] >= ts_start)
        )
        work = work[mask].copy()

    # 남은 공종이 1개면 화면 ship-mode와 동일하게 호선 통합(한 장)
    unique_gjs = sorted(work['공종'].dropna().unique()) if not work.empty else []
    single_gj = len(unique_gjs) == 1
    effective_row_mode = row_mode or ('ship' if single_gj else 'area')

    sections = []
    if not work.empty and single_gj:
        gj_name = unique_gjs[0]
        tasks = []
        for idx, row in work.iterrows():
            t = _row_to_print_task(row, fallback_id=f"ROW_{idx}")
            if t is not None:
                tasks.append(t)
        if tasks:
            sections.append({
                "ship": gj_name,
                "stg":  "전체 호선",
                "tasks": tasks,
            })
    elif not work.empty:
        # 호선 × STG 개별 섹션 (각자 한 페이지)
        for ship in sorted(work['프로젝트'].unique()):
            ship_df = work[work['프로젝트'] == ship]
            for stg in sorted(ship_df['STG'].astype(str).unique()):
                page_df = ship_df[ship_df['STG'].astype(str) == stg]
                tasks = []
                for idx, row in page_df.iterrows():
                    t = _row_to_print_task(row, fallback_id=f"{ship}_{stg}_{idx}")
                    if t is not None:
                        tasks.append(t)
                if tasks:
                    sections.append({"ship": ship, "stg": stg, "tasks": tasks})

    html_path = Path(__file__).parent.parent / "assets" / "gantt_print.html"
    tpl = html_path.read_text(encoding='utf-8')

    today_str = datetime.now().strftime('%Y-%m-%d')
    html = (
        tpl
        .replace('/*__SECTIONS__*/[]', json.dumps(sections, ensure_ascii=False))
        .replace('__TODAY__', today_str)
        .replace('__ROW_MODE__', effective_row_mode)
    )
    return html


# ══════════════════════════════════════════════
#  10. 탑재 일자 로드 (S-Curve 마커용)
# ══════════════════════════════════════════════
@st.cache_data(ttl=3600)
def load_tapjae_dates() -> pd.DataFrame:
    """선표 테이블에서 호선별 탑재착수 일자 반환. 컬럼: 프로젝트, 탑재착수."""
    try:
        df = run_query(f"SELECT 프로젝트, 탑재착수 FROM {TABLE_SUNPYO}")
    except Exception:
        logger.error("선표 조회 실패", exc_info=True)
        return pd.DataFrame(columns=['프로젝트', '탑재착수'])
    if df is None or df.empty:
        return pd.DataFrame(columns=['프로젝트', '탑재착수'])
    df['탑재착수'] = pd.to_datetime(df['탑재착수'], errors='coerce').dt.normalize()
    df = df.dropna(subset=['탑재착수'])
    # 호선당 1행만 (중복 시 가장 이른 날짜 유지)
    df = df.sort_values('탑재착수').drop_duplicates(subset=['프로젝트'], keep='first')
    return df[['프로젝트', '탑재착수']].reset_index(drop=True)
