"""
계산 엔진 — 앵커 이벤트 기반 공정 일정 자동 계산
30 STG (블럭별) → In/Outside → 50 STG (데크별) 순서로 계산 후 DB 저장
"""

import datetime
import logging
import traceback
import pandas as pd
import streamlit as st

from utils.db import execute_query, get_connection, run_query
from data.meeting_ref_data import (
    get_ref_30stg, get_ref_50stg, get_ref_inout,
    get_sequence, get_deck_order, get_calendar, get_vessels,
    get_anchor_30stg, get_anchor_50stg,
    get_block_to_deck_dict,
)

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
# DDL
# ═══════════════════════════════════════════════════════════════

_DDL_SCHEDULE = """
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='lq_meet_schedule' AND xtype='U')
CREATE TABLE lq_meet_schedule (
    id          INT IDENTITY(1,1) PRIMARY KEY,
    vessel_no   NVARCHAR(20)  NOT NULL,
    stg         NVARCHAR(5)   NOT NULL,
    area        NVARCHAR(30)  NOT NULL,
    work_code   NVARCHAR(30)  NOT NULL,
    plan_start  DATE,
    plan_end    DATE,
    calc_at     DATETIME      DEFAULT GETDATE(),
    CONSTRAINT uq_schedule UNIQUE (vessel_no, stg, area, work_code)
)
"""


def init_schedule_table() -> bool:
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(_DDL_SCHEDULE)
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error("스케줄 테이블 생성 오류: %s\n%s", e, traceback.format_exc())
        return False


# ═══════════════════════════════════════════════════════════════
# 캘린더 유틸
# ═══════════════════════════════════════════════════════════════

def _get_holiday_set() -> set:
    """DB 캘린더 테이블에서 비작업일 집합 로드"""
    try:
        df = get_calendar()
        if df.empty:
            return set()
        return {str(d)[:10] for d in df["cal_date"]}
    except Exception:
        return set()


def _to_date(val) -> datetime.date | None:
    """DB/Excel 에서 읽은 값 → datetime.date 변환"""
    if val is None:
        return None
    s = str(val).strip()
    if s in ("", "None", "NaT", "NaN"):
        return None
    if isinstance(val, datetime.datetime):
        return val.date()
    if isinstance(val, datetime.date):
        return val
    try:
        return pd.to_datetime(s).date()
    except Exception:
        return None


def is_working_day(d: datetime.date, holiday_set: set, weekday_only: bool = False) -> bool:
    """작업일 여부 (일요일·휴일 제외, weekday_only=True 이면 토요일도 제외)"""
    if d.weekday() == 6:
        return False
    if weekday_only and d.weekday() == 5:
        return False
    if str(d) in holiday_set:
        return False
    return True


def next_working_day(
    d: datetime.date,
    holiday_set: set,
    weekday_only: bool = False,
) -> datetime.date:
    """d 또는 d 이후 첫 번째 작업일 반환"""
    while not is_working_day(d, holiday_set, weekday_only):
        d += datetime.timedelta(days=1)
    return d


def add_working_days(
    start: datetime.date,
    days: int,
    holiday_set: set,
    weekday_only: bool = False,
) -> datetime.date:
    """start 당일을 1일차로 계산하여 days 작업일 후 종료일 반환
    예) start=Mon, days=3 → Wed (Mon=1, Tue=2, Wed=3)
    """
    if days <= 0:
        return start
    remaining = days - 1
    current = start
    while remaining > 0:
        current += datetime.timedelta(days=1)
        if is_working_day(current, holiday_set, weekday_only):
            remaining -= 1
    return current


def subtract_working_days(end: datetime.date, days: int, holiday_set: set) -> datetime.date:
    """end 에서 days 작업일 이전 날짜 반환 (Rule 1 offset 계산용)"""
    if days <= 0:
        return end
    remaining = days
    current = end
    while remaining > 0:
        current -= datetime.timedelta(days=1)
        if is_working_day(current, holiday_set):
            remaining -= 1
    return current


# ═══════════════════════════════════════════════════════════════
# 30 STG 계산
# ═══════════════════════════════════════════════════════════════

def calc_30stg(vessel_no: str, vessel_type: str) -> dict:
    """블럭별 30 STG 공정 계산
    반환: {block_no: {work_code: (start_date, end_date)}}
    """
    holiday_set = _get_holiday_set()
    anchor_df = get_anchor_30stg(vessel_no)
    ref_df    = get_ref_30stg(vessel_type)
    seq_df    = get_sequence("30")

    if anchor_df.empty or ref_df.empty:
        return {}

    ref = {row["block_no"]: row.to_dict() for _, row in ref_df.iterrows()}
    seq = seq_df.sort_values("seq_no").to_dict("records")

    result = {}

    for _, anc in anchor_df.iterrows():
        block_no = str(anc["block_no"]).strip()
        blk_in  = _to_date(anc.get("blk_in_date"))
        blk_out = _to_date(anc.get("blk_out_date"))

        if not blk_in and not blk_out:
            continue

        blk_ref  = ref.get(block_no, {})
        exc_blocks_map = {
            s["work_code"]: [b.strip() for b in str(s.get("exception_blocks","")).split(",") if b.strip()]
            for s in seq
        }

        block_sched = {}
        prev_end = None

        for step in seq:
            work_code = step["work_code"]
            dur_type  = step["duration_type"]
            weekday_only = (step.get("cal_type", "all") == "weekday")

            # 예외 블럭 → 해당 공종 건너뜀
            if block_no in exc_blocks_map.get(work_code, []):
                continue

            if dur_type == "anchor":
                anchor_date = blk_in if work_code == "blk_in" else blk_out
                if anchor_date:
                    block_sched[work_code] = (anchor_date, anchor_date)
                    prev_end = anchor_date
                continue

            if prev_end is None:
                continue

            if dur_type == "fixed":
                days = max(step.get("fixed_days", 0), 0)
            elif dur_type == "variable":
                ref_col = step.get("ref_col", "")
                days = int(blk_ref.get(ref_col, 0)) if ref_col else 0
            else:
                days = 0

            if days == 0:
                continue

            start = next_working_day(prev_end + datetime.timedelta(days=1), holiday_set, weekday_only)
            end   = add_working_days(start, days, holiday_set, weekday_only)
            block_sched[work_code] = (start, end)
            prev_end = end

        if block_sched:
            result[block_no] = block_sched

    return result


# ═══════════════════════════════════════════════════════════════
# In/Outside 계산
# ═══════════════════════════════════════════════════════════════

_INOUT_COLS = [
    "트렁크배선","윈도우설치","윈도우검사","내부배관검사",
    "외부배관검사","외판도장","외판족장철거","FLOOR도장",
    "탑재준비","탑재사열","인양","탑재",
]


def calc_inout(vessel_no: str, vessel_type: str, anchor50: dict) -> dict:
    """In/Outside 공종 계산
    anchor50: {deck: {mount_start, insp_plan, insp_actual, wall_straight}}
    반환: {area: {work_code: (start_date, end_date)}}
    """
    holiday_set = _get_holiday_set()
    ref_df = get_ref_inout()

    if ref_df.empty:
        return {}

    # 트렁크배선 시작일 = 선각WALL곡직완료일 (LNG→D-DK, CONT→F-DK)
    trigger_deck = "D-DK" if vessel_type == "LNG" else "F-DK"
    wall_straight = None
    if trigger_deck in anchor50:
        wall_straight = _to_date(anchor50[trigger_deck].get("wall_straight"))

    result = {}

    for _, row in ref_df.iterrows():
        area = str(row["area"]).strip()
        area_sched = {}
        prev_end = None

        for col in _INOUT_COLS:
            days = int(row.get(col, 0))
            if days == 0:
                continue

            if col == "트렁크배선":
                if wall_straight is None:
                    break  # 선각WALL곡직완료일 없으면 계산 불가
                start = next_working_day(wall_straight, holiday_set)
            else:
                if prev_end is None:
                    break
                start = next_working_day(prev_end + datetime.timedelta(days=1), holiday_set)

            end = add_working_days(start, days, holiday_set)
            area_sched[col] = (start, end)
            prev_end = end

        if area_sched:
            result[area] = area_sched

    return result


# ═══════════════════════════════════════════════════════════════
# 50 STG 계산
# ═══════════════════════════════════════════════════════════════

# 선각 관련 공종 — 수기 관리 대상으로 계산 엔진에서 제외
_SKIP_50STG = {"블럭탑재","선각취부","선각용접","선각FLOOR곡직","선각WALL곡직","선각검사"}


def calc_50stg(
    vessel_no: str,
    vessel_type: str,
    anchor50: dict,
    inout_sched: dict,
) -> dict:
    """데크별 50 STG 공종(의장) 계산
    anchor50: {deck: {insp_plan, insp_actual, ...}}
    inout_sched: calc_inout() 결과
    반환: {deck: {work_code: (start_date, end_date)}}
    """
    holiday_set  = _get_holiday_set()
    ref_df       = get_ref_50stg(vessel_type)
    deck_order_df = get_deck_order(vessel_type)
    seq_df       = get_sequence("50")

    if ref_df.empty or deck_order_df.empty:
        return {}

    decks = list(deck_order_df.sort_values("order_no")["deck"])  # [UPP-DK, A-DK, ...]

    ref = {str(row["deck"]).strip(): row.to_dict() for _, row in ref_df.iterrows()}
    seq = [s for s in seq_df.sort_values("seq_no").to_dict("records")
           if s["work_code"] not in _SKIP_50STG]

    # 트렁크배선 완료일 (Rule 2: 배선 선행 조건)
    trunk_end = None
    inout_io = inout_sched.get("In/Outside", {})
    if inout_io.get("트렁크배선"):
        trunk_end = inout_io["트렁크배선"][1]

    # 데크별 이전 공종 완료일 (순차 제약 추적)
    prev_end_by_deck: dict[str, datetime.date | None] = {d: None for d in decks}
    for deck in decks:
        if deck == "UPP-DK":
            continue
        insp = _get_inspection_date(anchor50.get(deck, {}))
        if insp:
            prev_end_by_deck[deck] = insp

    result: dict[str, dict] = {d: {} for d in decks}

    # 공종 순서대로 → 각 공종 내에서 하부(A-DK)부터 상부(NAV-DK) 순으로 처리
    for step in seq:
        work_code    = step["work_code"]
        weekday_only = (step.get("cal_type", "all") == "weekday")
        ref_col      = step.get("ref_col", "")

        for i, deck in enumerate(decks):
            if deck == "UPP-DK":
                continue

            days = int(ref.get(deck, {}).get(ref_col, 0)) if ref_col else 0
            if days == 0:
                continue

            if prev_end_by_deck[deck] is None:
                continue  # 선각검사일 없음 → 해당 데크 계산 불가

            # ── 제약 수집 (배타적: start > date) ─────────────────
            excl = [prev_end_by_deck[deck]]  # 동일 데크 이전 공종 완료

            # Cascade (Rule 4): 하부 데크 동일 공종 완료
            lower_deck = _lower_non_upp(decks, i)
            if lower_deck:
                lrange = result[lower_deck].get(work_code)
                if lrange:
                    excl.append(lrange[1])

            # Rule 2: 배선 → 트렁크배선 완료 후
            if work_code == "배선" and trunk_end:
                excl.append(trunk_end)

            # ── 제약 수집 (포함적: start >= date) ────────────────
            incl: list[datetime.date] = []

            # Rule 1: 도장PB — 상부 데크 목의화기1차 종료 2일 전부터 착수 가능
            if work_code == "도장PB" and i + 1 < len(decks):
                upper_deck = decks[i + 1]
                upper_hwa = result[upper_deck].get("목의화기1차")
                if upper_hwa:
                    incl.append(subtract_working_days(upper_hwa[1], 2, holiday_set))

            # ── 시작일 결정 ──────────────────────────────────────
            cand_excl = next_working_day(
                max(excl) + datetime.timedelta(days=1), holiday_set, weekday_only
            )
            if incl:
                cand_incl = next_working_day(max(incl), holiday_set, weekday_only)
                start = max(cand_excl, cand_incl)
            else:
                start = cand_excl

            end = add_working_days(start, days, holiday_set, weekday_only)
            result[deck][work_code] = (start, end)
            prev_end_by_deck[deck] = end

    return result


def _lower_non_upp(decks: list, current_idx: int) -> str | None:
    """현재 데크 인덱스 기준으로 하부 UPP-DK 제외 첫 번째 데크 반환"""
    for j in range(current_idx - 1, -1, -1):
        if decks[j] != "UPP-DK":
            return decks[j]
    return None


def _get_inspection_date(anc_row: dict) -> datetime.date | None:
    """선각검사 완료일 반환"""
    return _to_date(anc_row.get("insp_date"))


# ═══════════════════════════════════════════════════════════════
# 앵커 딕셔너리 로드
# ═══════════════════════════════════════════════════════════════

def _load_anchor50(vessel_no: str) -> dict:
    """anchor_50stg DataFrame → {deck: {...}} 딕셔너리"""
    df = get_anchor_50stg(vessel_no)
    result = {}
    for _, row in df.iterrows():
        dk = str(row["deck"]).strip()
        result[dk] = {
            "mount_start":    _to_date(row.get("mount_start_date")),
            "attach_end":     _to_date(row.get("sunggak_attach_end")),
            "weld_end":       _to_date(row.get("sunggak_weld_end")),
            "floor_straight": _to_date(row.get("floor_straight_date")),
            "wall_straight":  _to_date(row.get("wall_straight_date")),
            "insp_date":      _to_date(row.get("inspection_date")),
        }
    return result


# ═══════════════════════════════════════════════════════════════
# 전체 계산 및 DB 저장
# ═══════════════════════════════════════════════════════════════

def calc_and_save(vessel_no: str) -> dict:
    """호선 전체 공정 계산 후 DB 저장
    반환: {"ok": bool, "30stg": int, "50stg": int, "inout": int, "error": str}
    """
    res = {"ok": False, "30stg": 0, "50stg": 0, "inout": 0, "error": ""}

    try:
        # 선종 확인
        vessels = get_vessels()
        v_row = vessels[vessels["vessel_no"] == vessel_no]
        if v_row.empty:
            res["error"] = f"호선 {vessel_no} 정보 없음"
            return res
        vessel_type = str(v_row.iloc[0]["vessel_type"]).strip()

        anchor50 = _load_anchor50(vessel_no)

        sched_30    = calc_30stg(vessel_no, vessel_type)
        sched_inout = calc_inout(vessel_no, vessel_type, anchor50)
        sched_50    = calc_50stg(vessel_no, vessel_type, anchor50, sched_inout)

        init_schedule_table()
        conn = get_connection()
        cur  = conn.cursor()

        # 이전 결과 삭제
        cur.execute("DELETE FROM lq_meet_schedule WHERE vessel_no=?", (vessel_no,))

        def _ins(stg, area, code, s, e):
            cur.execute("""
                INSERT INTO lq_meet_schedule (vessel_no,stg,area,work_code,plan_start,plan_end)
                VALUES (?,?,?,?,?,?)
            """, (vessel_no, stg, area, code, str(s), str(e)))

        for block_no, bsched in sched_30.items():
            for code, (s, e) in bsched.items():
                _ins("30", block_no, code, s, e)
                res["30stg"] += 1

        for area, asched in sched_inout.items():
            for code, (s, e) in asched.items():
                _ins("inout", area, code, s, e)
                res["inout"] += 1

        for deck, dsched in sched_50.items():
            for code, (s, e) in dsched.items():
                _ins("50", deck, code, s, e)
                res["50stg"] += 1

        conn.commit()
        conn.close()
        get_schedule.clear()
        res["ok"] = True

    except Exception as e:
        logger.error("계산 엔진 오류: %s\n%s", e, traceback.format_exc())
        res["error"] = "계산 중 오류가 발생했습니다. 관리자에게 문의해 주세요."

    return res


# ═══════════════════════════════════════════════════════════════
# 조회
# ═══════════════════════════════════════════════════════════════

@st.cache_data(ttl=60)
def get_schedule(vessel_no: str = None) -> pd.DataFrame:
    """계산된 일정 조회"""
    sql = """SELECT vessel_no,stg,area,work_code,plan_start,plan_end,calc_at
             FROM lq_meet_schedule"""
    if vessel_no:
        return run_query(
            sql + " WHERE vessel_no=? ORDER BY stg,area,work_code",
            params=(vessel_no,)
        )
    return run_query(sql + " ORDER BY vessel_no,stg,area,work_code")
