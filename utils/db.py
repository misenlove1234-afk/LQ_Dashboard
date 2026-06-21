"""
DB 연결 유틸리티 - SQL Server
.env 파일 경로를 통해 접속 정보 로드

사용법:
    from utils.db import get_engine, run_query, get_connection, execute_query
"""

import urllib.parse
import logging
import traceback
import os
from pathlib import Path

import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
import pyodbc
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# ── .env 파일 로드 (프로젝트 루트 우선, 없으면 리눅스 서버 경로) ─
_ENV_CANDIDATES = [
    Path(__file__).parent.parent / ".env",   # Windows 로컬: 프로젝트 루트
    Path("/etc/lq/.env.dev"),                 # Linux 서버
]
for _env_path in _ENV_CANDIDATES:
    if _env_path.exists():
        load_dotenv(_env_path)
        break


# ── 공통 접속 정보 ────────────────────────────────────────
def _get_credentials():
    user     = os.getenv("USER")
    password = os.getenv("PASSWORD")
    server   = os.getenv("SERVER")
    return user, password, server


def _resolve_db(database=None):
    """database 인자가 없으면 .env의 DATABASE 값 사용"""
    return database or os.getenv("DATABASE")


# ── SQLAlchemy 엔진 (pandas read_sql용) ───────────────────
@st.cache_resource
def get_engine(database=None):
    """
    SQLAlchemy 엔진 반환 - pd.read_sql() 에 사용
    인자 생략 시 .env의 DATABASE 값을 사용
    """
    user, password, server = _get_credentials()
    db = _resolve_db(database)
    return create_engine(
        f"mssql+pyodbc://{user}:{password}@{server}/{db}"
        "?driver=ODBC+Driver+18+for+SQL+Server"
        "&Encrypt=no&TrustServerCertificate=yes"
    )


# ── pyodbc 직접 연결 (INSERT/DELETE 등 쓰기 작업용) ───────
def get_connection(database=None):
    """
    pyodbc 연결 반환 - 게시판 저장/삭제 등 쓰기 작업에 사용
    사용 후 반드시 conn.close() 호출 필요
    """
    import pyodbc
    user, password, server = _get_credentials()
    db = _resolve_db(database)
    conn_str = (
        f"DRIVER={{ODBC Driver 18 for SQL Server}};"
        f"SERVER={server};DATABASE={db};"
        f"UID={user};PWD={password};"
        "Encrypt=no;TrustServerCertificate=yes;"
    )
    return pyodbc.connect(conn_str)


# ── 편의 함수: SELECT 쿼리 → DataFrame ───────────────────
@st.cache_data(ttl=300)
def run_query(sql: str, params=None, database=None):
    """
    SELECT 쿼리 실행 후 DataFrame 반환 (5분 캐시)
    인자 생략 시 .env의 DATABASE 값을 사용
    """
    try:
        engine = get_engine(database)
        with engine.connect() as conn:
            return pd.read_sql(sql, conn, params=params)
    except Exception:
        # 트랜잭션 오류 시 엔진 커넥션 풀 초기화 후 재시도
        try:
            get_engine(database).dispose()
        except Exception:
            pass
        try:
            engine = get_engine(database)
            with engine.connect() as conn:
                return pd.read_sql(sql, conn, params=params)
        except Exception as e:
            logger.error("DB 쿼리 오류: %s\n%s", e, traceback.format_exc())
            raise


# ── 편의 함수: INSERT / UPDATE / DELETE ──────────────────
def execute_query(sql: str, params: tuple = None, database=None) -> bool:
    """
    INSERT / UPDATE / DELETE 쿼리 실행
    인자 생략 시 .env의 DATABASE 값을 사용
    """
    conn = get_connection(database)
    try:
        cursor = conn.cursor()
        if params:
            cursor.execute(sql, params)
        else:
            cursor.execute(sql)
        conn.commit()
        return True
    except Exception as e:
        raise e
    finally:
        conn.close()


# ════════════════════════════════════════════════════════════
# ② Azure 데이터마트
# ════════════════════════════════════════════════════════════

def _get_dm_credentials():
    """Azure 데이터마트 접속 정보 (.env: DM_SERVER, DM_DATABASE, DM_USERNAME, DM_PASSWORD)"""
    server   = os.getenv("DM_SERVER")
    database = os.getenv("DM_DATABASE")
    username = os.getenv("DM_USERNAME")
    password = os.getenv("DM_PASSWORD")
    driver   = os.getenv("DM_DRIVER", "ODBC Driver 18 for SQL Server")
    port     = os.getenv("DM_PORT", "1433")
    return server, database, username, password, driver, port


@st.cache_resource
def get_azure_dm_engine():
    """Azure 데이터마트 SQLAlchemy 엔진 반환 (ActiveDirectoryPassword 인증)"""
    server, database, username, password, driver, port = _get_dm_credentials()
    conn_str = (
        f"DRIVER={{{driver}}};"
        f"SERVER={server},{port};"
        f"DATABASE={database};"
        f"UID={username};"
        f"PWD={password};"
        "Authentication=ActiveDirectoryPassword"
    )
    params = urllib.parse.quote_plus(conn_str)
    return create_engine(
        f"mssql+pyodbc:///?odbc_connect={params}",
        fast_executemany=True,
    )


def get_dm_connection():
    """Azure 데이터마트 pyodbc 연결 반환 (ActiveDirectoryPassword 인증)"""
    server, database, username, password, driver, port = _get_dm_credentials()
    conn_str = (
        f"DRIVER={{{driver}}};"
        f"SERVER={server};"
        f"DATABASE={database};"
        f"UID={username};"
        f"PWD={password};"
        f"PORT={port};"
        "Authentication=ActiveDirectoryPassword"
    )
    return pyodbc.connect(conn_str)


@st.cache_data(ttl=300)
def run_dm_query(sql: str) -> pd.DataFrame:
    """
    Azure 데이터마트 SELECT 쿼리 실행 후 DataFrame 반환 (5분 캐시)

    예시:
        df = run_dm_query("SELECT * FROM CRCVW_SYARD_MC_A2_CD_CNFM WHERE CNST_WK_CENT = '1J67400'")
    """
    conn = None
    try:
        conn = get_dm_connection()
        return pd.read_sql(sql, conn)
    except Exception as e:
        logger.error("Azure DM 쿼리 오류: %s\n%s", e, traceback.format_exc())
        raise
    finally:
        if conn:
            conn.close()