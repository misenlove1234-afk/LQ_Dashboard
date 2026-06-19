"""
╔══════════════════════════════════════════════════════════════════╗
║  담당자 : ___________  (본인 이름 작성)                          ║
║  항목   : [데이터 전용] kpi_4 - 월별 기성 전망                   ║
║  작성일 : ___________                                            ║
╚══════════════════════════════════════════════════════════════════╝

【 🤖 AI 바이브 코딩을 위한 프롬프트 가이드 】
동료분들은 아래 내용을 복사해서 AI에게 그대로 입력하세요!

"이 파일은 Streamlit 앱의 '데이터 처리 전용' 모듈이야.
1. 절대 st.write, st.dataframe 같은 화면 UI 코드를 넣지 마.
2. utils.db 의 run_query 함수를 사용해서 DB에서 데이터를 불러와.
3. 무거운 연산을 하는 함수 위에는 반드시 @st.cache_data(ttl=600) 를 붙여.
4. 최종 결과물은 Pandas DataFrame 으로 return 해줘."
"""

import re
import calendar
import streamlit as st
import pandas as pd
import holidays as kr_holidays
from datetime import date, timedelta, datetime

from utils.db import run_query

# ──────────────────────────────────────────────
# DB 테이블명 설정 (변경 시 여기만 수정)
# ──────────────────────────────────────────────
TABLE_NAME = "lq_kpi4_1"

@st.cache_data(ttl=600)
def load_all_holidays() -> frozenset:
    """
    전체 휴일 목록 반환 (한국 공휴일 + DB 회사 휴일)
    - 한국 공휴일 : holidays 라이브러리 자동 처리 (2020~2035)
    - 회사 휴일   : dbo.lq_kpi2_3 테이블 조회
    """
    # 한국 공휴일
    kr = kr_holidays.KR(years=range(2020, 2036))
    holiday_set = set(kr.keys())

    # DB 회사 휴일
    try:
        df_hol = run_query("SELECT * FROM dbo.lq_kpi2_3")
        holiday_set |= set(pd.to_datetime(df_hol["휴일"]).dt.date)
    except Exception:
        pass

    return frozenset(holiday_set)


# ══════════════════════════════════════════════
#  1. 유틸 함수 (날짜 변환, 워킹데이)
# ══════════════════════════════════════════════
def to_date(val):
    """
    다양한 형식의 날짜값을 Python date 객체로 변환
    지원 형식: datetime, date, Timestamp, '260126'(6자리), '20260126'(8자리)
    """
    if val is None or val == '':
        return None
    try:
        if pd.isna(val):
            return None
    except Exception:
        pass
    try:
        if isinstance(val, datetime):
            return val.date()
        if isinstance(val, date):
            return val
        if isinstance(val, pd.Timestamp):
            return val.date()
        s = str(val).strip().replace('-', '').replace('/', '')
        if len(s) == 6 and s.isdigit():
            return datetime.strptime("20" + s, "%Y%m%d").date()
        if len(s) == 8 and s.isdigit():
            return datetime.strptime(s, "%Y%m%d").date()
        return pd.to_datetime(str(val)).date()
    except Exception:
        return None


def working_days_in_range(start, end, holiday_set=None) -> list:
    """
    두 날짜 사이의 워킹데이(월~금, 공휴일·회사휴일 제외) 목록 반환
    예) 2026-01-26 ~ 2026-01-30 → [01-26, 01-27, 01-28, 01-29, 01-30]
    holiday_set: 제외할 휴일 집합 (frozenset[date]), None이면 주말만 제외
    """
    if start is None or end is None or start > end:
        return []
    _holidays = holiday_set if holiday_set is not None else frozenset()
    return [
        start + timedelta(days=i)
        for i in range((end - start).days + 1)
        if (start + timedelta(days=i)).weekday() < 5
        and (start + timedelta(days=i)) not in _holidays
    ]


def get_next_weekday(d, holiday_set=None):
    """주말·공휴일이면 직후 첫 번째 워킹데이로 이월"""
    if d is None:
        return None
    _holidays = holiday_set if holiday_set is not None else frozenset()
    while d.weekday() > 4 or d in _holidays:
        d += timedelta(days=1)
    return d


# ══════════════════════════════════════════════
#  2. DB 데이터 로드 및 컬럼 매핑
# ══════════════════════════════════════════════
@st.cache_data(ttl=600)
def load_data() -> pd.DataFrame:
    """
    lq_kpi4_1 테이블 전체 로드
    컬럼명 앞뒤 공백 제거 포함
    """
    df = run_query(f"SELECT * FROM [{TABLE_NAME}]")
    df.columns = [str(c).strip() for c in df.columns]
    return df


def auto_col(all_cols: list, keywords: list):
    """
    키워드 목록으로 컬럼명 자동 추론
    매핑 성공 시 컬럼명(str) 반환, 실패 시 None 반환
    """
    for kw in keywords:        # 키워드 우선순위 순서로 (구체적인 것 먼저)
        for c in all_cols:     # 해당 키워드를 포함하는 컬럼 탐색
            if kw in str(c):
                return c
    return None


def get_col_map(all_cols: list) -> dict:
    """
    DataFrame 컬럼명으로 자동 매핑 딕셔너리 생성
    """
    return {
        'gongsu':     auto_col(all_cols, ['실행공수']),
        'auto_prog':  auto_col(all_cols, ['자동진도율', '진도율']),
        'ms_start':   auto_col(all_cols, ['마일스톤 계획_시작일', '마일스톤_계획_시작일', '마일스톤_시작일', '마일스톤 시작일']),
        'ms_end':     auto_col(all_cols, ['마일스톤 계획_종료일', '마일스톤_계획_종료일', '마일스톤_종료일', '마일스톤 종료일']),
        'comp_date':  auto_col(all_cols, ['완료절점_완료일', '완료절점', '완료일']),
        'wanryo_amt':  auto_col(all_cols, ['완료절점 기성', '완료절점기성', '완료기성']),
        'dept':        auto_col(all_cols, ['작업부서명', '작업부서', '부서명', '부서', 'DEPT_NM', 'DEPT']),
        'project':     auto_col(all_cols, ['프로젝트', '호선', 'PROJECT']),
        'numsil_prev': auto_col(all_cols, ['누계실적(조회일자기준)_전월']),
        'actual_date': auto_col(all_cols, ['완료일']),
    }


# ══════════════════════════════════════════════
#  3. 기성 계산 (핵심 비즈니스 로직)
# ══════════════════════════════════════════════
def _parse_month_range(month_label: str, ref_year: int):
    """
    '월' 컬럼 값(예: '1월', '12월')을 파싱해서 해당 월의 (시작일, 종료일) 반환
    """
    import calendar
    match = re.search(r'(\d{1,2})월', str(month_label))
    if not match:
        return None, None
    month_num = int(match.group(1))
    if not 1 <= month_num <= 12:
        return None, None
    last_day = calendar.monthrange(ref_year, month_num)[1]
    return date(ref_year, month_num, 1), date(ref_year, month_num, last_day)


def compute_kiseong(
    df: pd.DataFrame,
    col_map: dict,
    query_start: date,
    query_end: date,
) -> pd.DataFrame:
    """
    일별 공정진도 기성 + 완료절점 기성 계산
    """
    holiday_set   = load_all_holidays()
    query_wd_list = working_days_in_range(query_start, query_end, holiday_set)
    query_wd_set  = set(query_wd_list)

    has_month_col = '월' in df.columns

    daily_gongjeong: dict = {}
    daily_wanryo:    dict = {}

    ms_start_col = col_map.get('ms_start')
    ms_end_col   = col_map.get('ms_end')
    comp_col     = col_map.get('comp_date')
    gongsu_col   = col_map.get('gongsu')
    prog_col     = col_map.get('auto_prog')
    wanryo_col   = col_map.get('wanryo_amt')
    numsil_col   = col_map.get('numsil_prev')
    actual_col   = col_map.get('actual_date')

    # 조회기간 전월 말일
    prev_m = query_start.month - 1
    prev_y = query_start.year
    if prev_m == 0:
        prev_m = 12
        prev_y -= 1
    prev_month_last = date(prev_y, prev_m, calendar.monthrange(prev_y, prev_m)[1])

    for _, row in df.iterrows():

        ms_start      = to_date(row[ms_start_col])  if ms_start_col  else None
        ms_end        = to_date(row[ms_end_col])     if ms_end_col    else None
        comp_date_raw = to_date(row[comp_col])       if comp_col      else None
        comp_date     = get_next_weekday(comp_date_raw, holiday_set)

        try:
            gongsu        = float(row[gongsu_col]  or 0) if gongsu_col  else 0.0
            auto_prog_raw = float(row[prog_col]    or 0) if prog_col    else 0.0
            wanryo_val    = float(row[wanryo_col]  or 0) if wanryo_col  else 0.0

            if auto_prog_raw == 0:
                auto_prog = 0.0
            elif 0 < auto_prog_raw <= 1.0:
                auto_prog = auto_prog_raw
            else:
                auto_prog = auto_prog_raw / 100.0
        except (ValueError, TypeError):
            continue

        # 전월누계 파싱 (null/변환 실패 → None, 조건 미적용)
        numsil_prev = None
        if numsil_col:
            try:
                val = row[numsil_col]
                if val is not None and not (isinstance(val, float) and pd.isna(val)):
                    numsil_prev = float(val)
            except (ValueError, TypeError):
                pass

        ref_year = query_start.year
        if has_month_col:
            month_label = row.get('월', None)
            m_start, m_end = _parse_month_range(month_label, ref_year)
            if m_start and m_end:
                effective_start = max(m_start, query_start)
                effective_end   = min(m_end,   query_end)
                if effective_start > effective_end:
                    continue
                effective_wd_set = set(working_days_in_range(effective_start, effective_end, holiday_set))
            else:
                effective_wd_set = query_wd_set
        else:
            effective_wd_set = query_wd_set

        # ── 공정진도 기성 ──
        if ms_start and ms_end and gongsu > 0:
            total_wd_list   = working_days_in_range(ms_start, ms_end, holiday_set)
            total_wd        = len(total_wd_list)
            ms_start_before = ms_start < query_start
            ms_end_before   = ms_end   < query_start
            comp_before     = comp_date is not None and comp_date < query_start

            # 조건 1: ms_start·ms_end·완료절점_완료일 모두 조회기간 이전, 전월누계 = 0
            # → 완료일 기준으로 실행공수 100% 일괄 발생 (완료일 없으면 당일)
            if (ms_start_before and ms_end_before and comp_before
                    and numsil_prev is not None and numsil_prev == 0.0):
                actual_dt = to_date(row[actual_col]) if actual_col else None
                actual_dt = get_next_weekday(actual_dt, holiday_set) if actual_dt else None
                target_dt = actual_dt if actual_dt else get_next_weekday(date.today(), holiday_set)
                if target_dt in query_wd_set:
                    daily_gongjeong[target_dt] = daily_gongjeong.get(target_dt, 0) + gongsu

            # 조건 2: ms_start만 조회기간 이전, 전월누계 = 0
            # → ms_start~전월 말일 발생분을 조회기간 첫 워킹데이에 일괄 + 이후 3-B
            elif (ms_start_before and not ms_end_before
                      and numsil_prev is not None and numsil_prev == 0.0
                      and total_wd > 0):
                dg = gongsu * auto_prog / total_wd
                past_end = min(prev_month_last, ms_end)
                if past_end >= ms_start:
                    past_lump = dg * len(working_days_in_range(ms_start, past_end, holiday_set))
                    if past_lump > 0 and query_wd_list:
                        first_day = query_wd_list[0]
                        daily_gongjeong[first_day] = daily_gongjeong.get(first_day, 0) + past_lump
                wd_set = set(total_wd_list)
                for d in effective_wd_set:
                    if d in wd_set:
                        daily_gongjeong[d] = daily_gongjeong.get(d, 0) + dg

            # 기존 로직 (3-A / 3-B)
            elif total_wd > 0:
                dg = gongsu * auto_prog / total_wd

                if comp_date and ms_start <= comp_date < ms_end:
                    wd_set   = set(working_days_in_range(ms_start, comp_date, holiday_set))
                    rem_days = len(working_days_in_range(comp_date + timedelta(days=1), ms_end, holiday_set))

                    for d in effective_wd_set:
                        if d in wd_set:
                            daily_gongjeong[d] = daily_gongjeong.get(d, 0) + dg

                    if has_month_col:
                        _, comp_month_end = _parse_month_range(row.get('월', ''), ref_year)
                        lump_allowed = (comp_month_end is not None
                                        and comp_date.month == comp_month_end.month
                                        and comp_date.year  == comp_month_end.year)
                    else:
                        lump_allowed = True

                    if lump_allowed and comp_date in query_wd_set:
                        lump_val = dg * rem_days
                        daily_gongjeong[comp_date] = daily_gongjeong.get(comp_date, 0) + lump_val
                else:
                    wd_set = set(total_wd_list)
                    for d in effective_wd_set:
                        if d in wd_set:
                            daily_gongjeong[d] = daily_gongjeong.get(d, 0) + dg

        # ── 완료절점 기성 ──
        if comp_date and comp_date in query_wd_set and wanryo_val > 0:
            daily_wanryo[comp_date] = daily_wanryo.get(comp_date, 0) + wanryo_val

    chart_df = pd.DataFrame({
        'date':      query_wd_list,
        'gongjeong': [daily_gongjeong.get(d, 0) for d in query_wd_list],
        'wanryo':    [daily_wanryo.get(d, 0)    for d in query_wd_list],
        'total':     [daily_gongjeong.get(d, 0) + daily_wanryo.get(d, 0) for d in query_wd_list],
    })
    chart_df['cumulative'] = chart_df['total'].cumsum()

    return chart_df


def compute_kiseong_by_dept(
    df: pd.DataFrame,
    col_map: dict,
    query_start: date,
    query_end: date,
) -> pd.DataFrame:
    """
    부서별 조회 기간 내 공정진도 기성 / 완료절점 기성 / 합계 집계
    단일 패스로 계산하여 성능 최적화
    """
    dept_col = col_map.get('dept')
    if not dept_col:
        return pd.DataFrame(columns=['부서', '공정진도 기성', '완료절점 기성', '합계'])

    holiday_set   = load_all_holidays()
    query_wd_list = working_days_in_range(query_start, query_end, holiday_set)
    query_wd_set  = set(query_wd_list)
    has_month_col = '월' in df.columns

    ms_start_col = col_map.get('ms_start')
    ms_end_col   = col_map.get('ms_end')
    comp_col     = col_map.get('comp_date')
    gongsu_col   = col_map.get('gongsu')
    prog_col     = col_map.get('auto_prog')
    wanryo_col   = col_map.get('wanryo_amt')
    numsil_col   = col_map.get('numsil_prev')
    actual_col   = col_map.get('actual_date')

    # 조회기간 전월 말일
    prev_m = query_start.month - 1
    prev_y = query_start.year
    if prev_m == 0:
        prev_m = 12
        prev_y -= 1
    prev_month_last = date(prev_y, prev_m, calendar.monthrange(prev_y, prev_m)[1])

    dept_gongjeong: dict = {}
    dept_wanryo:    dict = {}

    for _, row in df.iterrows():
        dept = str(row.get(dept_col, '미분류')).strip() or '미분류'

        ms_start      = to_date(row[ms_start_col])  if ms_start_col else None
        ms_end        = to_date(row[ms_end_col])     if ms_end_col   else None
        comp_date_raw = to_date(row[comp_col])       if comp_col     else None
        comp_date     = get_next_weekday(comp_date_raw, holiday_set)

        try:
            gongsu        = float(row[gongsu_col]  or 0) if gongsu_col else 0.0
            auto_prog_raw = float(row[prog_col]    or 0) if prog_col   else 0.0
            wanryo_val    = float(row[wanryo_col]  or 0) if wanryo_col else 0.0

            if auto_prog_raw == 0:
                auto_prog = 0.0
            elif 0 < auto_prog_raw <= 1.0:
                auto_prog = auto_prog_raw
            else:
                auto_prog = auto_prog_raw / 100.0
        except (ValueError, TypeError):
            continue

        # 전월누계 파싱 (null/변환 실패 → None, 조건 미적용)
        numsil_prev = None
        if numsil_col:
            try:
                val = row[numsil_col]
                if val is not None and not (isinstance(val, float) and pd.isna(val)):
                    numsil_prev = float(val)
            except (ValueError, TypeError):
                pass

        ref_year = query_start.year
        if has_month_col:
            month_label = row.get('월', None)
            m_start, m_end = _parse_month_range(month_label, ref_year)
            if m_start and m_end:
                effective_start = max(m_start, query_start)
                effective_end   = min(m_end,   query_end)
                if effective_start > effective_end:
                    continue
                effective_wd_set = set(working_days_in_range(effective_start, effective_end, holiday_set))
            else:
                effective_wd_set = query_wd_set
        else:
            effective_wd_set = query_wd_set

        # ── 공정진도 기성 ──
        row_gong = 0.0
        if ms_start and ms_end and gongsu > 0:
            total_wd_list   = working_days_in_range(ms_start, ms_end, holiday_set)
            total_wd        = len(total_wd_list)
            ms_start_before = ms_start < query_start
            ms_end_before   = ms_end   < query_start
            comp_before     = comp_date is not None and comp_date < query_start

            # 조건 1: ms_start·ms_end·완료절점_완료일 모두 조회기간 이전, 전월누계 = 0
            if (ms_start_before and ms_end_before and comp_before
                    and numsil_prev is not None and numsil_prev == 0.0):
                actual_dt = to_date(row[actual_col]) if actual_col else None
                actual_dt = get_next_weekday(actual_dt, holiday_set) if actual_dt else None
                target_dt = actual_dt if actual_dt else get_next_weekday(date.today(), holiday_set)
                if target_dt in query_wd_set:
                    row_gong = gongsu

            # 조건 2: ms_start만 조회기간 이전, 전월누계 = 0
            elif (ms_start_before and not ms_end_before
                      and numsil_prev is not None and numsil_prev == 0.0
                      and total_wd > 0):
                dg = gongsu * auto_prog / total_wd
                past_end = min(prev_month_last, ms_end)
                if past_end >= ms_start:
                    row_gong += dg * len(working_days_in_range(ms_start, past_end, holiday_set))
                wd_set = set(total_wd_list)
                row_gong += sum(dg for d in effective_wd_set if d in wd_set)

            # 기존 로직 (3-A / 3-B)
            elif total_wd > 0:
                dg = gongsu * auto_prog / total_wd
                if comp_date and ms_start <= comp_date < ms_end:
                    wd_set   = set(working_days_in_range(ms_start, comp_date, holiday_set))
                    rem_days = len(working_days_in_range(comp_date + timedelta(days=1), ms_end, holiday_set))
                    row_gong = sum(dg for d in effective_wd_set if d in wd_set)
                    if has_month_col:
                        _, comp_month_end = _parse_month_range(row.get('월', ''), ref_year)
                        lump_allowed = (comp_month_end is not None
                                        and comp_date.month == comp_month_end.month
                                        and comp_date.year  == comp_month_end.year)
                    else:
                        lump_allowed = True
                    if lump_allowed and comp_date in query_wd_set:
                        row_gong += dg * rem_days
                else:
                    wd_set   = set(total_wd_list)
                    row_gong = sum(dg for d in effective_wd_set if d in wd_set)
        dept_gongjeong[dept] = dept_gongjeong.get(dept, 0.0) + row_gong

        # ── 완료절점 기성 ──
        if comp_date and comp_date in query_wd_set and wanryo_val > 0:
            dept_wanryo[dept] = dept_wanryo.get(dept, 0.0) + wanryo_val

    all_depts = sorted(set(list(dept_gongjeong.keys()) + list(dept_wanryo.keys())))
    rows = []
    for d in all_depts:
        g = dept_gongjeong.get(d, 0.0)
        w = dept_wanryo.get(d, 0.0)
        rows.append({'부서': d, '공정진도 기성': g, '완료절점 기성': w, '합계': g + w})

    if not rows:
        return pd.DataFrame(columns=['부서', '공정진도 기성', '완료절점 기성', '합계'])

    result_df = pd.DataFrame(rows).sort_values('합계', ascending=False).reset_index(drop=True)
    total_row = pd.DataFrame([{
        '부서':       '합계',
        '공정진도 기성': result_df['공정진도 기성'].sum(),
        '완료절점 기성': result_df['완료절점 기성'].sum(),
        '합계':       result_df['합계'].sum(),
    }])
    return pd.concat([result_df, total_row], ignore_index=True)
