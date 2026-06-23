"""
엑셀 회의록 제거 프로젝트 — 기준정보 데이터 레이어
DB 테이블 초기화, 조회, 수정 함수 모음
"""

import logging
import traceback
import pandas as pd
import streamlit as st
from utils.db import run_query, execute_query, get_connection

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
# 초기 기준 데이터 (상수 — Streamlit 내에서 수정 가능)
# ═══════════════════════════════════════════════════════════════

# ── 30 STG 기준파일 ──────────────────────────────────────────
_INIT_30STG = [
    # vessel_type, block_no, 관철, 덕트, 전장, 도장, 배선
    ("LNG","M51NS", 0,0,0,0,0), ("LNG","M51NP", 0,0,0,0,0),
    ("LNG","M900S", 2,0,2,0,0), ("LNG","M900P", 2,0,2,0,0),
    ("LNG","M610C", 4,4,5,2,3),
    ("LNG","M510S", 4,5,6,2,6), ("LNG","M510P", 4,5,6,2,6),
    ("LNG","M410S", 4,4,6,3,2), ("LNG","M410P", 4,4,6,3,3),
    ("LNG","M31NS", 1,0,0,0,0), ("LNG","M31NP", 1,0,0,0,0),
    ("LNG","M31OS", 4,4,6,2,4), ("LNG","M31OP", 4,4,6,2,4),
    ("LNG","M220S", 4,5,7,2,3), ("LNG","M220P", 4,5,7,2,3),
    ("LNG","M210S", 4,4,4,2,5), ("LNG","M210P", 4,4,4,2,5),
    ("LNG","M120S", 4,5,5,2,4), ("LNG","M120P", 4,5,5,2,4),
    ("LNG","M110S", 4,5,7,2,4), ("LNG","M110P", 4,5,7,2,4),
    ("CONT","M940S", 1,1,0,1,1), ("CONT","M930P", 1,1,0,1,1),
    ("CONT","M920S", 3,4,2,3,4), ("CONT","M920P", 3,4,2,3,4),
    ("CONT","M910S", 3,5,5,2,3), ("CONT","M910P", 3,5,5,2,3),
    ("CONT","M900S", 3,0,2,3,6), ("CONT","M900P", 3,0,2,3,6),
    ("CONT","M710S", 5,5,4,3,4), ("CONT","M710P", 5,5,4,3,4),
    ("CONT","M610S", 5,4,5,3,4), ("CONT","M610P", 5,4,5,3,4),
    ("CONT","M510S", 4,5,5,3,4), ("CONT","M510P", 4,5,5,3,4),
    ("CONT","M410S", 3,4,4,3,4), ("CONT","M410P", 3,4,4,3,4),
    ("CONT","M320S", 3,0,1,1,0), ("CONT","M320P", 3,0,1,1,0),
    ("CONT","M310S", 4,5,5,3,5), ("CONT","M310P", 4,5,5,3,5),
    ("CONT","M220S", 4,4,2,3,0), ("CONT","M220P", 4,4,2,3,0),
    ("CONT","M210S", 5,5,6,3,5), ("CONT","M210P", 5,5,6,3,5),
    ("CONT","M120S", 2,4,2,1,0), ("CONT","M120P", 2,4,2,1,0),
    ("CONT","M110S", 5,5,6,3,3), ("CONT","M110P", 5,5,6,3,3),
]

# ── 50 STG 기준파일 ──────────────────────────────────────────
# 열 순서: vessel_type, deck, 목의화기1차, 도장PB, 도장TU, 배선, 보온,
#          목의화기2차, 피복, BP검사, 판넬설치, 결선, 가구, 장판, 스커트
_INIT_50STG = [
    ("LNG","UPP-DK", 0,2,3, 0, 0, 0,0,0, 0, 0,0,0,0),
    ("LNG","A-DK",   7,2,3, 5, 4, 2,1,1, 4, 5,1,1,1),
    ("LNG","B-DK",   6,2,3, 5, 4, 3,1,1, 4, 5,1,1,1),
    ("LNG","C-DK",   6,2,3, 5, 4, 3,1,1, 4, 5,1,1,1),
    ("LNG","D-DK",   6,2,3,15, 8, 3,1,1, 4, 5,1,1,1),
    ("LNG","NAV-DK", 4,2,3,10, 5, 0,1,1, 4, 5,1,1,1),
    ("CONT","UPP-DK", 0,2,3, 0, 0, 0,0,0, 0, 0,0,0,0),
    ("CONT","A-DK",   5,2,3, 4, 3, 2,1,1, 3, 3,2,1,1),
    ("CONT","B-DK",   5,2,3, 4, 3, 3,1,1, 3, 3,2,1,1),
    ("CONT","C-DK",   5,2,3, 4, 3, 2,1,1, 3, 3,2,1,1),
    ("CONT","D-DK",   5,2,3, 4, 3, 2,1,1, 3, 3,2,1,1),
    ("CONT","E-DK",   5,2,3, 4, 3, 3,1,1, 3, 3,2,1,1),
    ("CONT","F-DK",   5,2,3,15, 5, 3,1,1, 3, 3,2,1,1),
    ("CONT","NAV-DK", 6,2,3,10, 5, 0,1,1, 3, 3,2,1,1),
]

# ── In/Outside 기준파일 ──────────────────────────────────────
# 열 순서: area, 트렁크배선, 윈도우설치, 윈도우검사, 내부배관검사,
#          외부배관검사, 외판도장, 외판족장철거, FLOOR도장, 탑재준비, 탑재사열, 인양, 탑재
_INIT_INOUT = [
    ("In/Outside", 5,3,1,1,1,40,3,4,2,1,1,1),
    ("Elevator",   3,0,0,0,0, 0,0,0,0,0,0,0),
]

# ── 로직 규칙 ────────────────────────────────────────────────
_INIT_RULES = [
    # rule_id, vessel_type, rule_name,
    # pre_area, pre_work, pre_event, offset_days,
    # suc_area, suc_work, is_active
    (1,"ALL","화기→도장 리드",
     "lower_deck","목의화기1차","END",-2,
     "upper_deck","도장PB",1),
    (2,"ALL","트렁크→배선",
     "in_outside","트렁크배선","END",0,
     "all_deck","배선",1),
    (3,"ALL","선각검사→의장",
     "deck","선각검사","END",0,
     "deck","목의화기1차",1),
    (4,"ALL","계단식 배치",
     "lower_deck","same","END",0,
     "upper_deck","same",1),
    (5,"LNG","D-DK WALL→트렁크(LNG)",
     "D-DK","선각WALL","END",0,
     "in_outside","트렁크배선",1),
    (6,"CONT","F-DK WALL→트렁크(CONT)",
     "F-DK","선각WALL","END",0,
     "in_outside","트렁크배선",1),
]

# ═══════════════════════════════════════════════════════════════
# 테이블 초기화 (IF NOT EXISTS)
# ═══════════════════════════════════════════════════════════════

_DDL_30STG = """
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='lq_meet_ref_30stg' AND xtype='U')
CREATE TABLE lq_meet_ref_30stg (
    id          INT IDENTITY(1,1) PRIMARY KEY,
    vessel_type NVARCHAR(10)  NOT NULL,
    block_no    NVARCHAR(20)  NOT NULL,
    관철         INT DEFAULT 0,
    덕트         INT DEFAULT 0,
    전장         INT DEFAULT 0,
    도장         INT DEFAULT 0,
    배선         INT DEFAULT 0,
    updated_at  DATETIME DEFAULT GETDATE(),
    CONSTRAINT uq_30stg UNIQUE (vessel_type, block_no)
)
"""

_DDL_50STG = """
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='lq_meet_ref_50stg' AND xtype='U')
CREATE TABLE lq_meet_ref_50stg (
    id          INT IDENTITY(1,1) PRIMARY KEY,
    vessel_type NVARCHAR(10)  NOT NULL,
    deck        NVARCHAR(20)  NOT NULL,
    목의화기1차   INT DEFAULT 0,
    도장PB       INT DEFAULT 0,
    도장TU       INT DEFAULT 0,
    배선         INT DEFAULT 0,
    보온         INT DEFAULT 0,
    목의화기2차   INT DEFAULT 0,
    피복         INT DEFAULT 0,
    BP검사       INT DEFAULT 0,
    판넬설치      INT DEFAULT 0,
    결선         INT DEFAULT 0,
    가구         INT DEFAULT 0,
    장판         INT DEFAULT 0,
    스커트        INT DEFAULT 0,
    updated_at  DATETIME DEFAULT GETDATE(),
    CONSTRAINT uq_50stg UNIQUE (vessel_type, deck)
)
"""

_DDL_INOUT = """
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='lq_meet_ref_inout' AND xtype='U')
CREATE TABLE lq_meet_ref_inout (
    id           INT IDENTITY(1,1) PRIMARY KEY,
    area         NVARCHAR(30) NOT NULL UNIQUE,
    트렁크배선    INT DEFAULT 0,
    윈도우설치    INT DEFAULT 0,
    윈도우검사    INT DEFAULT 0,
    내부배관검사  INT DEFAULT 0,
    외부배관검사  INT DEFAULT 0,
    외판도장      INT DEFAULT 0,
    외판족장철거  INT DEFAULT 0,
    FLOOR도장     INT DEFAULT 0,
    탑재준비      INT DEFAULT 0,
    탑재사열      INT DEFAULT 0,
    인양         INT DEFAULT 0,
    탑재         INT DEFAULT 0,
    updated_at   DATETIME DEFAULT GETDATE()
)
"""

_DDL_RULES = """
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='lq_meet_logic_rules' AND xtype='U')
CREATE TABLE lq_meet_logic_rules (
    rule_id      INT PRIMARY KEY,
    vessel_type  NVARCHAR(10)  NOT NULL,
    rule_name    NVARCHAR(100) NOT NULL,
    pre_area     NVARCHAR(50)  NOT NULL,
    pre_work     NVARCHAR(50)  NOT NULL,
    pre_event    NVARCHAR(10)  NOT NULL,
    offset_days  INT           NOT NULL DEFAULT 0,
    suc_area     NVARCHAR(50)  NOT NULL,
    suc_work     NVARCHAR(50)  NOT NULL,
    is_active    INT           NOT NULL DEFAULT 1,
    updated_at   DATETIME      DEFAULT GETDATE()
)
"""

_DDL_CALENDAR = """
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='lq_meet_calendar' AND xtype='U')
CREATE TABLE lq_meet_calendar (
    id         INT IDENTITY(1,1) PRIMARY KEY,
    cal_date   DATE         NOT NULL UNIQUE,
    reason     NVARCHAR(50) NOT NULL
)
"""


def init_tables() -> bool:
    """DB 테이블이 없으면 생성하고 초기 데이터를 INSERT"""
    try:
        conn = get_connection()
        cur = conn.cursor()

        for ddl in [_DDL_30STG, _DDL_50STG, _DDL_INOUT, _DDL_RULES, _DDL_CALENDAR]:
            cur.execute(ddl)
        conn.commit()

        # 초기 데이터 삽입 (이미 존재하면 건너뜀)
        _seed_30stg(cur)
        _seed_50stg(cur)
        _seed_inout(cur)
        _seed_rules(cur)
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error("테이블 초기화 오류: %s\n%s", e, traceback.format_exc())
        return False


def _seed_30stg(cur):
    for row in _INIT_30STG:
        cur.execute("""
            IF NOT EXISTS (SELECT 1 FROM lq_meet_ref_30stg WHERE vessel_type=? AND block_no=?)
            INSERT INTO lq_meet_ref_30stg (vessel_type,block_no,관철,덕트,전장,도장,배선)
            VALUES (?,?,?,?,?,?,?)
        """, (row[0], row[1], row[0], row[1], row[2], row[3], row[4], row[5], row[6]))


def _seed_50stg(cur):
    for row in _INIT_50STG:
        cur.execute("""
            IF NOT EXISTS (SELECT 1 FROM lq_meet_ref_50stg WHERE vessel_type=? AND deck=?)
            INSERT INTO lq_meet_ref_50stg
              (vessel_type,deck,목의화기1차,도장PB,도장TU,배선,보온,
               목의화기2차,피복,BP검사,판넬설치,결선,가구,장판,스커트)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (row[0],row[1], row[0],row[1],row[2],row[3],row[4],row[5],row[6],
              row[7],row[8],row[9],row[10],row[11],row[12],row[13],row[14]))


def _seed_inout(cur):
    for row in _INIT_INOUT:
        cur.execute("""
            IF NOT EXISTS (SELECT 1 FROM lq_meet_ref_inout WHERE area=?)
            INSERT INTO lq_meet_ref_inout
              (area,트렁크배선,윈도우설치,윈도우검사,내부배관검사,외부배관검사,
               외판도장,외판족장철거,FLOOR도장,탑재준비,탑재사열,인양,탑재)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (row[0], row[0],row[1],row[2],row[3],row[4],row[5],
              row[6],row[7],row[8],row[9],row[10],row[11],row[12]))


def _seed_rules(cur):
    for row in _INIT_RULES:
        cur.execute("""
            IF NOT EXISTS (SELECT 1 FROM lq_meet_logic_rules WHERE rule_id=?)
            INSERT INTO lq_meet_logic_rules
              (rule_id,vessel_type,rule_name,pre_area,pre_work,pre_event,
               offset_days,suc_area,suc_work,is_active)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (row[0], row[0],row[1],row[2],row[3],row[4],row[5],
              row[6],row[7],row[8],row[9]))


# ═══════════════════════════════════════════════════════════════
# 조회 함수
# ═══════════════════════════════════════════════════════════════

@st.cache_data(ttl=300)
def get_ref_30stg(vessel_type: str = None) -> pd.DataFrame:
    sql = "SELECT vessel_type,block_no,관철,덕트,전장,도장,배선 FROM lq_meet_ref_30stg"
    if vessel_type:
        sql += " WHERE vessel_type=?"
        return run_query(sql, params=(vessel_type,))
    return run_query(sql)


@st.cache_data(ttl=300)
def get_ref_50stg(vessel_type: str = None) -> pd.DataFrame:
    sql = """SELECT vessel_type,deck,목의화기1차,도장PB,도장TU,배선,보온,
                    목의화기2차,피복,BP검사,판넬설치,결선,가구,장판,스커트
             FROM lq_meet_ref_50stg"""
    if vessel_type:
        sql += " WHERE vessel_type=?"
        return run_query(sql, params=(vessel_type,))
    return run_query(sql)


@st.cache_data(ttl=300)
def get_ref_inout() -> pd.DataFrame:
    return run_query("""SELECT area,트렁크배선,윈도우설치,윈도우검사,내부배관검사,
                               외부배관검사,외판도장,외판족장철거,FLOOR도장,
                               탑재준비,탑재사열,인양,탑재
                        FROM lq_meet_ref_inout""")


@st.cache_data(ttl=300)
def get_logic_rules() -> pd.DataFrame:
    return run_query("""SELECT rule_id,vessel_type,rule_name,pre_area,pre_work,
                               pre_event,offset_days,suc_area,suc_work,is_active
                        FROM lq_meet_logic_rules ORDER BY rule_id""")


@st.cache_data(ttl=300)
def get_calendar() -> pd.DataFrame:
    return run_query("""SELECT cal_date,reason FROM lq_meet_calendar
                        ORDER BY cal_date""")


# ═══════════════════════════════════════════════════════════════
# 저장 함수
# ═══════════════════════════════════════════════════════════════

def save_ref_30stg(df: pd.DataFrame) -> bool:
    """30 STG 기준파일 전체 덮어쓰기"""
    try:
        conn = get_connection()
        cur = conn.cursor()
        for _, row in df.iterrows():
            cur.execute("""
                UPDATE lq_meet_ref_30stg
                SET 관철=?,덕트=?,전장=?,도장=?,배선=?,updated_at=GETDATE()
                WHERE vessel_type=? AND block_no=?
            """, (int(row['관철']),int(row['덕트']),int(row['전장']),
                  int(row['도장']),int(row['배선']),
                  row['vessel_type'],row['block_no']))
        conn.commit()
        conn.close()
        get_ref_30stg.clear()
        return True
    except Exception as e:
        logger.error("30STG 저장 오류: %s\n%s", e, traceback.format_exc())
        return False


def save_ref_50stg(df: pd.DataFrame) -> bool:
    """50 STG 기준파일 전체 덮어쓰기"""
    try:
        conn = get_connection()
        cur = conn.cursor()
        cols = ['목의화기1차','도장PB','도장TU','배선','보온',
                '목의화기2차','피복','BP검사','판넬설치','결선','가구','장판','스커트']
        for _, row in df.iterrows():
            vals = [int(row[c]) for c in cols]
            cur.execute(f"""
                UPDATE lq_meet_ref_50stg
                SET {','.join(f'{c}=?' for c in cols)}, updated_at=GETDATE()
                WHERE vessel_type=? AND deck=?
            """, (*vals, row['vessel_type'], row['deck']))
        conn.commit()
        conn.close()
        get_ref_50stg.clear()
        return True
    except Exception as e:
        logger.error("50STG 저장 오류: %s\n%s", e, traceback.format_exc())
        return False


def save_ref_inout(df: pd.DataFrame) -> bool:
    """In/Outside 기준파일 전체 덮어쓰기"""
    try:
        conn = get_connection()
        cur = conn.cursor()
        cols = ['트렁크배선','윈도우설치','윈도우검사','내부배관검사','외부배관검사',
                '외판도장','외판족장철거','FLOOR도장','탑재준비','탑재사열','인양','탑재']
        for _, row in df.iterrows():
            vals = [int(row[c]) for c in cols]
            cur.execute(f"""
                UPDATE lq_meet_ref_inout
                SET {','.join(f'{c}=?' for c in cols)}, updated_at=GETDATE()
                WHERE area=?
            """, (*vals, row['area']))
        conn.commit()
        conn.close()
        get_ref_inout.clear()
        return True
    except Exception as e:
        logger.error("InOut 저장 오류: %s\n%s", e, traceback.format_exc())
        return False


def save_logic_rules(df: pd.DataFrame) -> bool:
    """로직 규칙 전체 덮어쓰기"""
    try:
        conn = get_connection()
        cur = conn.cursor()
        for _, row in df.iterrows():
            cur.execute("""
                UPDATE lq_meet_logic_rules
                SET vessel_type=?,rule_name=?,pre_area=?,pre_work=?,pre_event=?,
                    offset_days=?,suc_area=?,suc_work=?,is_active=?,updated_at=GETDATE()
                WHERE rule_id=?
            """, (row['vessel_type'],row['rule_name'],row['pre_area'],row['pre_work'],
                  row['pre_event'],int(row['offset_days']),row['suc_area'],row['suc_work'],
                  int(row['is_active']),int(row['rule_id'])))
        conn.commit()
        conn.close()
        get_logic_rules.clear()
        return True
    except Exception as e:
        logger.error("로직 규칙 저장 오류: %s\n%s", e, traceback.format_exc())
        return False


def add_calendar_date(cal_date: str, reason: str) -> bool:
    try:
        execute_query("""
            IF NOT EXISTS (SELECT 1 FROM lq_meet_calendar WHERE cal_date=?)
            INSERT INTO lq_meet_calendar (cal_date,reason) VALUES (?,?)
        """, (cal_date, cal_date, reason))
        get_calendar.clear()
        return True
    except Exception as e:
        logger.error("캘린더 추가 오류: %s\n%s", e, traceback.format_exc())
        return False


def delete_calendar_date(cal_date: str) -> bool:
    try:
        execute_query("DELETE FROM lq_meet_calendar WHERE cal_date=?", (cal_date,))
        get_calendar.clear()
        return True
    except Exception as e:
        logger.error("캘린더 삭제 오류: %s\n%s", e, traceback.format_exc())
        return False


# ═══════════════════════════════════════════════════════════════
# 기본값 DataFrame (DB 없을 때 폴백용)
# ═══════════════════════════════════════════════════════════════

def default_30stg_df(vessel_type: str) -> pd.DataFrame:
    rows = [r for r in _INIT_30STG if r[0] == vessel_type]
    return pd.DataFrame(rows, columns=['vessel_type','block_no','관철','덕트','전장','도장','배선'])


def default_50stg_df(vessel_type: str) -> pd.DataFrame:
    rows = [r for r in _INIT_50STG if r[0] == vessel_type]
    return pd.DataFrame(rows, columns=[
        'vessel_type','deck','목의화기1차','도장PB','도장TU','배선','보온',
        '목의화기2차','피복','BP검사','판넬설치','결선','가구','장판','스커트'])


def default_inout_df() -> pd.DataFrame:
    return pd.DataFrame(_INIT_INOUT, columns=[
        'area','트렁크배선','윈도우설치','윈도우검사','내부배관검사','외부배관검사',
        '외판도장','외판족장철거','FLOOR도장','탑재준비','탑재사열','인양','탑재'])


def default_rules_df() -> pd.DataFrame:
    return pd.DataFrame(_INIT_RULES, columns=[
        'rule_id','vessel_type','rule_name','pre_area','pre_work',
        'pre_event','offset_days','suc_area','suc_work','is_active'])
