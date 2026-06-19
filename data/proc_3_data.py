"""
담당자 :               (본인 이름 작성)
항목   : [데이터 전용] proc_3 - 특수선 공정 현황 (DB 버전)

수정이력:
  - SUB SYSTEM: EVENT A열(Main/Sub\nSystem) 기준으로 수정
    (C열은 CERT Y/N 이므로 A열이 실제 SUB SYSTEM 코드)
"""

import streamlit as st
import pandas as pd
import datetime
from utils.db import run_query, run_dm_query

TBL_PROGRESS = "lq_proc3_1"
TBL_VOLUME   = "lq_proc3_2"
# TBL_MC는 Azure 사용으로 불필요
TBL_EVENT    = "lq_proc3_4"
TBL_SUBSYS   = "lq_proc3_5"
TBL_DISC     = "lq_proc3_6"
TBL_GWAMYUNG = "lq_proc3_7"
TBL_BUDGET   = "lq_proc3_8"

# Azure 데이터마트 MC 테이블 설정
AZURE_MC_TABLE    = "SHIDM.CRCVW_SYARD_MC_A2_CD_CNFM"
AZURE_MC_WC_CODES = ("1J67400", "1H67400")

TABLE_GONGJON = [
    "Pipe", "Pipe Support", "Duct", "Duct Support",
    "Arch", "Insulation",
    "전장설치", "전장EQUIP", "전장배선", "전장결선",
    "도장", "선실선각",
]  # fallback용 기본값 유지

@st.cache_data(ttl=600)
def load_budget_weight(ship: str) -> dict:
    """
    공종별 가중치(E열) 로드
    PROGRESS = Σ(가중치[gj] × 항목값[gj] / 총물량[gj])
    """
    df = run_query(
        f"SELECT 공종, 가중치 FROM [{TBL_BUDGET}] WHERE 호선 = ?",
        params=(ship,)
    )
    if df.empty:
        return {}
    return dict(zip(df["공종"], df["가중치"]))

@st.cache_data(ttl=600)
def get_gongjon_list(ship: str) -> list:
    """
    DB에서 호선별 공종 목록 동적 조회
    - Progress 제외
    - MC 포함 공종 제외 (띄어쓰기 무관: 전장MC, 전장 MC 모두 제외)
    - 엑셀 순서(sort_key 기준) 유지
    """
    df = run_query(
        f"SELECT DISTINCT 공종, MIN(sort_key) as min_sort "
        f"FROM [{TBL_PROGRESS}] "
        f"WHERE 호선 = ? AND 공종 != 'Progress' "
        f"GROUP BY 공종 ORDER BY MIN(sort_key)",
        params=(ship,)
    )
    if not df.empty:
        # ★ MC 포함 공종, Progress, LQ Total Progress, ITR 제외
        _exclude = {"Progress", "LQ Total Progress", "ITR"}
        return [g for g in df["공종"].tolist()
                if "MC" not in g.replace(" ", "").upper()
                and g not in _exclude]
    return [g for g in TABLE_GONGJON
            if "MC" not in g.replace(" ", "").upper()]

@st.cache_data(ttl=600)
def get_mc_gongjon_list(ship: str) -> list:
    """
    MC 포함 공종 목록만 조회 (MC 현황 그래프용)
    - 전장MC / 전장 MC → 선실전장과
    - 나머지 MC 공종  → 선실1과
    """
    df = run_query(
        f"SELECT DISTINCT 공종, MIN(sort_key) as min_sort "
        f"FROM [{TBL_PROGRESS}] "
        f"WHERE 호선 = ? AND 공종 != 'Progress' "
        f"GROUP BY 공종 ORDER BY MIN(sort_key)",
        params=(ship,)
    )
    if df.empty:
        return []
    all_gj = df["공종"].tolist()
    # MC 포함 공종만 추출 (공백 제거 후 대문자 비교)
    return [g for g in all_gj if "MC" in g.replace(" ", "").upper()]

def get_mc_plan_weekly(ship: str, mc_gongjon_list: list, gwamyung: str = "전체") -> pd.DataFrame:
    """
    MC 공종의 주간계획/누계계획을 주차별로 집계
    - 전장MC/전장 MC → sel_gwa가 선실전장과일 때 표시
    - 나머지           → sel_gwa가 선실1과일 때 표시
    gwamyung: 선택된 과 (전체/선실1과/선실전장과)
    """
    if not mc_gongjon_list:
        return pd.DataFrame()

    # 과에 따라 필터링할 공종 결정
    if gwamyung == "전체":
        target_gj = mc_gongjon_list  # 전체: 모든 MC 공종
    else:
        target_gj = []
        for gj in mc_gongjon_list:
            gj_clean = gj.replace(" ", "").upper()
            if "전장MC" in gj_clean or "전장MC" in gj_clean:
                # 전장MC 계열 → 선실전장과
                if gwamyung == "선실전장과":
                    target_gj.append(gj)
            else:
                # 나머지 MC 공종 → 선실1과
                if gwamyung == "선실1과":
                    target_gj.append(gj)

    if not target_gj:
        return pd.DataFrame()

    # DB에서 해당 공종의 주간계획/누계계획 조회
    placeholders = ",".join(["?" for _ in target_gj])
    df = run_query(
        f"SELECT week_key, 항목, SUM(값) as 값, MIN(sort_key) as sort_key "
        f"FROM [{TBL_PROGRESS}] "
        f"WHERE 호선 = ? AND 공종 IN ({placeholders}) "
        f"AND 항목 IN ('주간계획', '누계계획') "
        f"GROUP BY week_key, 항목 "
        f"ORDER BY MIN(sort_key)",
        params=tuple([ship] + target_gj)
    )
    if df.empty:
        return pd.DataFrame()

    # 피벗: week_key × 항목(주간계획/누계계획)
    pivot = df.pivot_table(
        index=["week_key", "sort_key"],
        columns="항목",
        values="값",
        aggfunc="sum"
    ).reset_index()
    pivot.columns.name = None
    pivot = pivot.sort_values("sort_key").reset_index(drop=True)
    return pivot


def get_ship_list() -> list:
    df = run_query(f"SELECT DISTINCT 호선 FROM [{TBL_PROGRESS}] ORDER BY 호선")
    return df["호선"].tolist() if not df.empty else []

def get_mc_ship_list() -> list:
    df = run_query(f"SELECT DISTINCT 호선 FROM [{TBL_MC}] ORDER BY 호선")
    return df["호선"].tolist() if not df.empty else []

def get_event_ship_list() -> list:
    df = run_query(f"SELECT DISTINCT 호선 FROM [{TBL_EVENT}] ORDER BY 호선")
    return df["호선"].tolist() if not df.empty else []

@st.cache_data(ttl=600)
def get_gwamyung_list(ship: str) -> list:
    """과명 선택바용: proc_3_gwamyung D열(과) 기준 목록 + 전체"""
    # ★ proc_3_gwamyung 테이블의 과 컬럼(D열) 기준
    df = run_query(f"SELECT * FROM [{TBL_GWAMYUNG}]")
    # D열 = '과' 컬럼
    gwa_col = next((c for c in df.columns if c.strip() == "과"), None)
    if gwa_col and not df.empty:
        names = df[gwa_col].dropna().tolist()
        # ★ 선실2과 제외
        names = [str(n).strip() for n in names
                 if str(n).strip() and str(n).strip() != "선실2과"]
    else:
        names = []
    return ["전체"] + names

@st.cache_data(ttl=600)
def load_discipline_map() -> tuple:
    """
    Discipline 탭: B열=discipline, C열=description (MC J열 매칭)
    과 탭: B열=wc(MC Y열 매칭), D열=과명(선택바)
    """
    df_disc = run_query(f"SELECT * FROM [{TBL_DISC}]")
    df_gwa  = run_query(f"SELECT * FROM [{TBL_GWAMYUNG}]")
    return df_disc, df_gwa

@st.cache_data(ttl=600)
def load_mc_data_by_gwa(ship: str, gwamyung: str = "전체") -> pd.DataFrame:
    """
    Azure 데이터마트에서 MC 데이터 로드
    CNST_WK_CENT IN AZURE_MC_WC_CODES 고정 필터 후 호선/과명으로 추가 필터 (Python)
    """
    wc_in = ", ".join([f"'{w}'" for w in AZURE_MC_WC_CODES])
    df = run_dm_query(f"SELECT * FROM {AZURE_MC_TABLE} WHERE CNST_WK_CENT IN ({wc_in})")

    if df.empty:
        return df

    # ★ 호선 필터: Azure 컬럼에서 호선 번호 컬럼을 찾아 필터
    ship_col = _find_col(df, ["SHIP_NO","CNST_NO","PROJ_NO","호선","SHIP","PROJECT_NO","PJT_NO","PROJ","PROJECT","계약번호"])
    if ship_col and ship:
        df = df[df[ship_col].apply(lambda v: str(v).strip() == ship if not _is_empty(v) else False)].reset_index(drop=True)

    if df.empty or gwamyung == "전체":
        return df

    # 과명 → WC 코드 목록 조회 (사내 DB)
    df_gwa  = run_query(f"SELECT * FROM [{TBL_GWAMYUNG}]")
    wc_col  = next((c for c in df_gwa.columns if c.strip().upper() == "WC"), None)
    gwa_col = next((c for c in df_gwa.columns if c.strip() == "과"), None)

    if wc_col and gwa_col and not df_gwa.empty:
        wc_list = df_gwa[df_gwa[gwa_col].apply(
            lambda v: str(v).strip() == gwamyung if not _is_empty(v) else False
        )][wc_col].dropna().tolist()
        wc_list = [str(w).strip() for w in wc_list if str(w).strip()]
        if wc_list and "CNST_WK_CENT" in df.columns:
            return df[df["CNST_WK_CENT"].isin(wc_list)].reset_index(drop=True)

    return df

def get_discipline_summary(df_mc: pd.DataFrame, df_disc: pd.DataFrame = None) -> pd.DataFrame:
    """
    DISCIPLINE별 총합/완료/잔여/완료율 집계
    ★ MC J열(OWNER DISC(I)) + K열(DISC DESC) 직접 피벗
       Discipline 파일 매칭 불필요
    """
    if df_mc is None or df_mc.empty:
        return pd.DataFrame(columns=["Discipline","Description","총합","완료","잔여","완료율(%)"])

    # ★ MC J열 = OWNER DISC(I) 탐색
    j_col = _find_col(df_mc, [
        "OWNER_DISC_I_", "OWNER_DISC_I",
        "OWNER\nDISC(I)", "OWNER DISC(I)", "OWNER DISC",
        "DISC(I)", "DISC", "discipline", "Discipline",
        "ITR구분", "ITR_GB", "INSP_TP_NM",
    ])
    if j_col is None:
        non_meta = [c for c in df_mc.columns if c.lower() not in ("id","updated_at","호선","과명")]
        j_col = non_meta[9] if len(non_meta) > 9 else None

    # ★ MC K열 = DISC DESC 탐색
    k_col = _find_col(df_mc, [
        "DISC DESC", "DISC\nDESC", "DISC_DESC", "Description",
        "SYSTEM", "MC_SYS_CD", "SYS_CD",
    ])
    if k_col is None:
        non_meta = [c for c in df_mc.columns if c.lower() not in ("id","updated_at","호선","과명")]
        k_col = non_meta[10] if len(non_meta) > 10 else None

    if j_col is None:
        return pd.DataFrame(columns=["Discipline","Description","총합","완료","잔여","완료율(%)"])

    ac_col  = _get_ac_col(df_mc)
    tag_col = _find_col(df_mc, ["TAG NO","TAG_NO","TAG_No","TAGNO","TAG","MC_CD","MC_NO","ITR_CD"])

    df_mc2 = df_mc.copy()
    df_mc2["__j"] = df_mc2[j_col].apply(
        lambda v: str(v).strip() if not _is_empty(v) else None
    )
    if k_col:
        df_mc2["__k"] = df_mc2[k_col].apply(
            lambda v: str(v).strip() if not _is_empty(v) else "-"
        )

    rows = []
    for disc_code, grp in df_mc2.dropna(subset=["__j"]).groupby("__j"):
        disc_code = str(disc_code).strip()
        if not disc_code: continue

        # K열에서 Description 추출 (그룹 내 첫 번째 유효값)
        disc_desc = "-"
        if k_col and "__k" in grp.columns:
            desc_vals = grp["__k"].dropna().tolist()
            if desc_vals:
                disc_desc = desc_vals[0]

        total = len(grp)
        done = int(grp.apply(lambda r: _mc_done(r, ac_col), axis=1).sum())
        rate = round(done / total * 100, 1) if total else 0.0
        rows.append({
            "Discipline": disc_code,
            "Description": disc_desc,
            "총합": total,
            "완료": done,
            "잔여": total - done,
            "완료율(%)": rate,
        })

    return pd.DataFrame(sorted(rows, key=lambda r: r["Discipline"]))


@st.cache_data(ttl=600)
def load_progress_data(ship: str = "") -> tuple:
    if not ship:
        ships = get_ship_list()
        if not ships:
            raise FileNotFoundError("DB에 proc_3_progress 데이터가 없습니다.")
        ship = ships[0]
    df_long = run_query(
        f"SELECT 호선, week_key, 공종, 항목, 값, sort_key "
        f"FROM [{TBL_PROGRESS}] WHERE 호선 = ? ORDER BY sort_key",
        params=(ship,)
    )
    df_tv = run_query(
        f"SELECT 공종, 총물량 FROM [{TBL_VOLUME}] WHERE 호선 = ?",
        params=(ship,)
    )
    total_volume = dict(zip(df_tv["공종"], df_tv["총물량"])) if not df_tv.empty else {}
    return df_long, total_volume


def get_week_list(df: pd.DataFrame) -> list:
    return sorted(
        df["week_key"].unique().tolist(),
        key=lambda w: df[df["week_key"] == w]["sort_key"].iloc[0]
    )

def get_latest_week(df: pd.DataFrame) -> str:
    return df.loc[df["sort_key"].idxmax(), "week_key"]

def get_current_week_key() -> str:
    d = datetime.date.today()
    return str(d.year)[-2:] + "년W" + str(d.isocalendar()[1])

def _v(sub, item):
    r = sub[sub["항목"] == item]["값"]
    v = r.iloc[0] if not r.empty else None
    return 0 if (v is None or (isinstance(v, float) and pd.isna(v))) else float(v)

def get_summary_table(df, total_volume, week_key, gj_list=None):
    if gj_list is None: gj_list = TABLE_GONGJON
    rows = []
    for gj in gj_list:
        sub = df[(df["공종"] == gj) & (df["week_key"] == week_key)]
        tv  = total_volume.get(gj, 0) or 0
        nk  = _v(sub, "누계계획"); nr = _v(sub, "누계실적")
        # ★ 누계값 없으면 주간값으로 대체 (SN2688형)
        if nk == 0: nk = _v(sub, "주간계획")
        if nr == 0: nr = _v(sub, "주간실적")
        rows.append({
            "구분": gj, "총물량": tv, "누계계획": nk, "누계실적": nr,
            "달성율": (nr / nk) if nk else 1.0,
            "진도율": (nr / tv) if tv else 0,
        })
    return pd.DataFrame(rows)

def get_progress_trend(df, week_key, n_weeks=5, total_volume=None):
    sub = df[
        (~df["공종"].isin(["Progress","LQ Total Progress"])) &
        (~df["공종"].apply(lambda g: "MC" in str(g).replace(" ","").upper()))
    ].copy()
    wks = sorted(sub["week_key"].unique().tolist(),
                 key=lambda w: sub[sub["week_key"] == w]["sort_key"].iloc[0])
    idx = wks.index(week_key) if week_key in wks else len(wks) - 1
    sel = wks[max(0, idx - n_weeks + 1): idx + 1]

    # ★ 카드와 동일: 전체합산 / 전체총물량
    _total_tv = sum(v for k, v in (total_volume or {}).items()
                    if "MC" not in str(k).replace(" ","").upper()) if total_volume else None

    rows = []
    for wk in sel:
        s = sub[sub["week_key"] == wk]
        result = {"week_key": wk, "주간계획": 0.0, "주간실적": 0.0,
                  "누계계획": 0.0, "누계실적": 0.0}
        for 항목 in ["주간계획","주간실적","누계계획","누계실적"]:
            val = s[s["항목"]==항목]["값"].sum()
            if _total_tv:
                result[항목] = val / _total_tv
            else:
                result[항목] = val
        rows.append(result)
    return pd.DataFrame(rows)

def get_weekly_summary(df, week_key, gj_list=None):
    if gj_list is None: gj_list = TABLE_GONGJON
    rows = []
    for gj in gj_list:
        sub = df[(df["공종"] == gj) & (df["week_key"] == week_key)]
        wk = _v(sub, "주간계획"); wr = _v(sub, "주간실적")
        rows.append({"구분": gj, "주간계획": wk, "주간실적": wr,
                     "달성율": (wr / wk) if wk else 1.0})
    return pd.DataFrame(rows)

def get_total_summary(df, week_key, gj_list=None):
    if gj_list is None: gj_list = TABLE_GONGJON
    rows = []
    for gj in gj_list:
        sub = df[(df["공종"] == gj) & (df["week_key"] == week_key)]
        nk = _v(sub, "누계계획"); nr = _v(sub, "누계실적")
        # ★ 누계값 없으면 주간값으로 대체 (SN2688형)
        if nk == 0: nk = _v(sub, "주간계획")
        if nr == 0: nr = _v(sub, "주간실적")
        rows.append({"구분": gj, "누계계획": nk, "누계실적": nr,
                     "달성율": (nr / nk) if nk else 1.0})
    return pd.DataFrame(rows)

def get_trend(df, gongjon, total_volume=None):
    # ★ Progress 공종 요청 시 가중치 기반 계산
    # PROGRESS = Σ(가중치[gj] × 항목값[gj] / 총물량[gj])
    if gongjon == "Progress":
        # 호선 추출
        ship = df["호선"].iloc[0] if "호선" in df.columns and not df.empty else None
        budget = load_budget_weight(ship) if ship else {}

        sub = df[
            (~df["공종"].isin(["Progress","LQ Total Progress"])) &
            (~df["공종"].apply(lambda g: "MC" in str(g).replace(" ","").upper()))
        ].copy()
        if sub.empty:
            return pd.DataFrame()

        # ★ 카드와 동일: 전체합산 / 전체총물량
        total_tv = sum(v for k, v in (total_volume or {}).items()
                       if "MC" not in str(k).replace(" ","").upper()) or 1.0

        wks = sorted(sub["week_key"].unique().tolist(),
                     key=lambda w: sub[sub["week_key"] == w]["sort_key"].iloc[0])
        rows = []
        for wk in wks:
            s = sub[sub["week_key"] == wk]
            result = {"week_key": wk, "누계계획": 0.0, "누계실적": 0.0,
                      "주간계획": 0.0, "주간실적": 0.0}
            for 항목 in ["누계계획","누계실적","주간계획","주간실적"]:
                val = s[s["항목"]==항목]["값"].sum()
                result[항목] = val / total_tv
            rows.append(result)
        return pd.DataFrame(rows)

    # ★ LQ Total Progress는 Progress와 동일하게 합산 계산
    if gongjon == "LQ Total Progress":
        gongjon = "Progress"
    sub  = df[df["공종"] == gongjon].copy()
    wks  = sorted(sub["week_key"].unique().tolist(),
                  key=lambda w: sub[sub["week_key"] == w]["sort_key"].iloc[0])
    rows = []
    for wk in wks:
        s = sub[sub["week_key"] == wk]
        rows.append({
            "week_key": wk,
            "누계계획": _v(s, "누계계획"), "누계실적": _v(s, "누계실적"),
            "주간계획": _v(s, "주간계획"), "주간실적": _v(s, "주간실적"),
        })
    return pd.DataFrame(rows)


# ──────────────────────────────────────────
# MC
# ──────────────────────────────────────────
@st.cache_data(ttl=600)
def load_mc_data(ship: str = "") -> pd.DataFrame:
    """Azure 데이터마트에서 MC 데이터 로드 (호선 필터 적용)"""
    wc_in = ", ".join([f"'{w}'" for w in AZURE_MC_WC_CODES])
    df = run_dm_query(f"SELECT * FROM {AZURE_MC_TABLE} WHERE CNST_WK_CENT IN ({wc_in})")
    if df.empty or not ship:
        return df
    # ★ 호선 필터
    ship_col = _find_col(df, ["SHIP_NO","CNST_NO","PROJ_NO","호선","SHIP","PROJECT_NO","PJT_NO","PROJ","PROJECT","계약번호"])
    if ship_col:
        df = df[df[ship_col].apply(lambda v: str(v).strip() == ship if not _is_empty(v) else False)].reset_index(drop=True)
    return df


@st.cache_data(ttl=600)
def load_mc_data_all_wc(ship: str = "") -> pd.DataFrame:
    """Azure 데이터마트에서 호선 기준 전체 MC 데이터 로드 (WC코드 제한 없음)"""
    ship_col_name = "계약번호"  # 호선 컬럼명
    if ship:
        df = run_dm_query(f"SELECT * FROM {AZURE_MC_TABLE} WHERE {ship_col_name} = '{ship}'")
    else:
        df = run_dm_query(f"SELECT * FROM {AZURE_MC_TABLE}")
    return df

def _find_col(df, candidates):
    upper_map = {str(c).strip().upper(): c for c in df.columns}
    for cand in candidates:
        if cand in df.columns: return cand
        if cand.upper() in upper_map: return upper_map[cand.upper()]
    # ★ 부분 일치: 후보 키워드가 컬럼명에 포함되어 있으면 매칭
    for cand in candidates:
        cu = cand.upper().replace(" ","").replace("\n","").replace("_","")
        for orig_col in df.columns:
            ou = str(orig_col).strip().upper().replace(" ","").replace("\n","").replace("_","")
            if cu and cu == ou:
                return orig_col
    return None

def _get_ac_col(df):
    col = _find_col(df, [
        "RESULT","MC RESULT","MC_RESULT","AC",
        "완료여부","완료유무","완료","COMPLETE","MC완료",
        "CNFM_YN","MC_CNFM_YN","INSP_RSLT_NM",
    ])
    if col is None and len(df.columns) > 28: col = df.columns[28]
    return col

def _get_subsys_col(df):
    col = _find_col(df, [
        "SUB SYSTEM","SUB_SYSTEM","Sub System","SUBSYSTEM",
        "Syb-System","Sub-System","SYSTEM",
        "MC_SYS_CD","SYS_CD",
    ])
    if col is None and len(df.columns) > 19: col = df.columns[19]
    return col

def _week_key_to_end_date(week_key: str):
    """주차 키 → 해당 주 일요일(종료일) 반환"""
    try:
        yr = int(week_key.split("년")[0]) + 2000
        wn = int(week_key.upper().split("W")[1])
        return datetime.date.fromisocalendar(yr, wn, 7)  # 일요일
    except:
        return None

def get_mc_kpi_by_week(df_mc: pd.DataFrame, week_key: str = None) -> dict:
    """
    기준주차 반영 MC KPI 집계 (행 단위)
    - 총합: 전체 행 수
    - 완료: RESULT가 완료인 행 수 (기준주차 반영 시 COMPLETE DATE ≤ 기준주차 종료일)
    """
    result_col = _get_ac_col(df_mc)
    total = len(df_mc)

    if not week_key:
        completed = int(df_mc.apply(lambda r: _mc_done(r, result_col), axis=1).sum())
        return {"MC 총합": total, "MC 완료": completed,
                "MC 잔여": total - completed,
                "완료율": (completed / total * 100) if total else 0.0}

    # ★ 기준주차 종료일 계산
    week_end = _week_key_to_end_date(week_key)
    if week_end is None:
        completed = int(df_mc.apply(lambda r: _mc_done(r, result_col), axis=1).sum())
        return {"MC 총합": total, "MC 완료": completed,
                "MC 잔여": total - completed,
                "완료율": (completed / total * 100) if total else 0.0}

    # ★ COMPLETE DATE 컬럼 탐색
    complete_col = _find_col(df_mc, [
        "COMPLETE\nDATE", "COMPLETE DATE", "COMPLETE_DATE",
        "CompleteDate", "완료일", "완료날짜", "완료일자",
        "검사일", "INSP_DT", "CNFM_DT", "MC_CNFM_DT",
    ])
    if complete_col is None and len(df_mc.columns) > 36:
        non_meta = [c for c in df_mc.columns if c.lower() not in ("id","updated_at","호선","과명")]
        complete_col = non_meta[36] if len(non_meta) > 36 else None

    def _parse_date(v):
        if v is None or str(v).strip() in ("","None","nan"): return None
        try: return datetime.date.fromisoformat(str(v)[:10])
        except: return None

    # ★ 완료 = COMPLETE DATE ≤ 기준주차 종료일 AND RESULT 완료
    if complete_col:
        df2 = df_mc.copy()
        df2["__cd"] = df2[complete_col].apply(_parse_date)
        df2["__done"] = df2.apply(lambda r: _mc_done(r, result_col), axis=1)
        completed = int(((df2["__cd"].notna()) & (df2["__cd"] <= week_end) & df2["__done"]).sum())
    else:
        completed = int(df_mc.apply(lambda r: _mc_done(r, result_col), axis=1).sum())

    return {"MC 총합": total, "MC 완료": completed,
            "MC 잔여": total - completed,
            "완료율": (completed / total * 100) if total else 0.0}
    if complete_col and tag_col:
        df_mc["__cd"] = df_mc[complete_col].apply(_parse_date)
        df_mc["__cd_ok"] = df_mc["__cd"].apply(lambda d: d is not None and d <= week_end)
        tag_cd = df_mc.groupby(tag_col)["__cd_ok"].all()
        completed = int(tag_cd.sum())
    elif complete_col:
        completed = 0
        for _, row in df_mc.iterrows():
            cd = _parse_date(row.get(complete_col))


def filter_mc_by_week(df_mc: pd.DataFrame, week_key: str) -> pd.DataFrame:
    """
    기준주차까지 완료된 항목 기준으로 df_mc 필터
    COMPLETE DATE ≤ 기준주차 종료일(일요일) → 완료 처리
    단, 총합은 유지하되 완료 여부만 기준주차로 재계산하기 위해
    df_mc 의 RESULT 컬럼을 기준주차 기준으로 재설정한 복사본 반환
    """
    if df_mc is None or df_mc.empty or not week_key:
        return df_mc

    week_end = _week_key_to_end_date(week_key)
    if week_end is None:
        return df_mc

    # COMPLETE DATE 컬럼 탐색
    complete_col = _find_col(df_mc, [
        "COMPLETE\nDATE", "COMPLETE DATE", "COMPLETE_DATE",
        "CompleteDate", "완료일", "완료날짜", "완료일자",
        "검사일", "INSP_DT", "CNFM_DT", "MC_CNFM_DT",
    ])
    if complete_col is None:
        non_meta = [c for c in df_mc.columns if c.lower() not in ("id","updated_at","호선","과명")]
        complete_col = non_meta[36] if len(non_meta) > 36 else None

    if complete_col is None:
        return df_mc

    def _parse_date(v):
        if v is None or str(v).strip() in ("","None","nan"): return None
        try: return datetime.date.fromisoformat(str(v)[:10])
        except: return None

    # RESULT 컬럼 탐색
    result_col = _get_ac_col(df_mc)

    df_mc2 = df_mc.copy()
    df_mc2["__cd"] = df_mc2[complete_col].apply(_parse_date)

    # ★ 기준주차 이후 완료된 항목의 RESULT를 None으로 초기화
    # → 집계 시 완료로 카운트 안 됨
    if result_col:
        mask_after = df_mc2["__cd"].apply(
            lambda d: d is None or d > week_end
        )
        df_mc2.loc[mask_after, result_col] = None

    return df_mc2.drop(columns=["__cd"]).reset_index(drop=True)


def _mc_done(row, result_col) -> bool:
    if result_col is None or result_col not in row.index: return False
    v = row[result_col]
    if v is None: return False
    s = str(v).strip()
    if s in ("", "None", "nan"): return False
    # "미완료" 는 완료가 아님
    if s == "미완료": return False
    return True

def get_mc_kpi(df: pd.DataFrame) -> dict:
    result_col = _get_ac_col(df)
    total = len(df)
    completed = int(df.apply(lambda r: _mc_done(r, result_col), axis=1).sum())
    return {"MC 총합": total, "MC 완료": completed,
            "MC 잔여": total - completed,
            "완료율": (completed / total * 100) if total else 0.0}

def get_mc_subsys_map(df_mc: pd.DataFrame) -> dict:
    subsys_col = _get_subsys_col(df_mc)
    ac_col     = _get_ac_col(df_mc)
    if subsys_col is None: return {}
    sys_series = df_mc[subsys_col]
    if isinstance(sys_series, pd.DataFrame): sys_series = sys_series.iloc[:, 0]
    df2 = df_mc.copy()
    df2["__s"] = sys_series.apply(
        lambda v: str(v).strip() if v is not None and str(v).strip() not in ("","None","nan") else None
    )
    result = {}
    for val, grp in df2.dropna(subset=["__s"]).groupby("__s"):
        total = len(grp)
        done = int(grp.apply(lambda r: _mc_done(r, ac_col), axis=1).sum())
        result[val] = {"total": total, "done": done}
    return result

def get_mc_weekly(df_mc: pd.DataFrame) -> pd.DataFrame:
    ac_col = _get_ac_col(df_mc)
    ak_col = _find_col(df_mc, [
        "COMPLETE DATE","COMPLETE_DATE","CompleteDate",
        "완료일","완료날짜","완료일자",
        "검사일","INSP_DT","CNFM_DT","MC_CNFM_DT",
    ])
    if ak_col is None and len(df_mc.columns) > 36: ak_col = df_mc.columns[36]
    if ak_col is None: return pd.DataFrame(columns=["week_key","week_sort","MC완료"])
    done = df_mc[df_mc.apply(lambda r: _mc_done(r, ac_col), axis=1)].copy() if ac_col else df_mc.copy()
    if done.empty: return pd.DataFrame(columns=["week_key","week_sort","MC완료"])
    dc = done[ak_col]
    if isinstance(dc, pd.DataFrame): dc = dc.iloc[:, 0]
    def _safe_date(v):
        if v is None: return None
        if isinstance(v, (datetime.datetime, datetime.date)):
            return v.date() if isinstance(v, datetime.datetime) else v
        try: return pd.to_datetime(str(v)).date()
        except: return None
    done["_date"] = dc.apply(_safe_date)
    done = done.dropna(subset=["_date"])
    if done.empty: return pd.DataFrame(columns=["week_key","week_sort","MC완료"])
    done["week_key"]  = done["_date"].apply(lambda d: str(d.year)[-2:] + "년W" + str(d.isocalendar()[1]))
    done["week_sort"] = done["_date"].apply(lambda d: int(str(d.year)[-2:]) * 100 + d.isocalendar()[1])
    df_result = (done.groupby(["week_sort","week_key"]).size()
                 .reset_index(name="MC완료").sort_values("week_sort").reset_index(drop=True))
    # ★ get_mc_kpi 와 동일한 방식으로 total 계산 (TAG NO 기준)
    tag_col  = _find_col(df_mc, ["TAG NO","TAG_NO","TAG_No","TAGNO","TAG","MC_CD","MC_NO","ITR_CD"])
    # ★ 중복 TAG NO 제거 (전체 선택 시 과명별 중복 방지)
    total_mc = int(df_mc[tag_col].dropna().shape[0]) if tag_col else len(df_mc)
    df_result["누적완료"] = df_result["MC완료"].cumsum()
    df_result["완료율"]   = (df_result["누적완료"] / total_mc * 100).round(1) if total_mc else 0.0
    return df_result

def get_mc_signal(plan_date_str, rate, today=None) -> str:
    if today is None: today = datetime.date.today()
    if not plan_date_str or str(plan_date_str).strip() in ("-","","None","nan"): return "GRAY"
    try: plan = datetime.date.fromisoformat(str(plan_date_str)[:10])
    except: return "GRAY"
    diff = (today - plan).days
    left = (plan - today).days
    if rate >= 100:             return "GREEN"
    if diff >= 4:               return "RED"
    if diff >= 1:               return "YELLOW"
    if left <= 7 and rate < 90: return "RED"
    if left <= 30:
        if rate >= 70: return "GREEN"
        if rate >= 60: return "YELLOW"
        return "RED"
    return "GREEN"


# ──────────────────────────────────────────
# EVENT
# ──────────────────────────────────────────
@st.cache_data(ttl=600)
def load_event_data(ship: str = "") -> tuple:
    if not ship:
        ships = get_event_ship_list()
        if not ships: raise FileNotFoundError("DB에 proc_3_event 데이터가 없습니다.")
        ship = ships[0]
    df_event  = run_query(f"SELECT * FROM [{TBL_EVENT}] WHERE 호선 = ?", params=(ship,))
    df_subsys = run_query(f"SELECT * FROM [{TBL_SUBSYS}] WHERE 호선 = ?", params=(ship,))
    return df_event, df_subsys

def _is_empty(v) -> bool:
    if v is None: return True
    if isinstance(v, float) and pd.isna(v): return True
    return str(v).strip() in ("","None","nan")

def _get_ev_subsys_col(df_event) -> str:
    """
    EVENT 파일의 SUB SYSTEM 코드 컬럼 탐색
    확인된 컬럼명: 'Main/Sub\nSystem' (A열, index 0)
    """
    # 먼저 알려진 컬럼명으로 탐색
    candidates = [
        "Main/Sub\nSystem", "Main/SubSystem", "MAIN/SUBSYSTEM",
        "Sub-System", "SUB SYSTEM", "SUB_SYSTEM", "SUBSYSTEM", "System",
    ]
    for cand in candidates:
        if cand in df_event.columns:
            return cand
    # 없으면 메타 컬럼 제외 첫 번째 컬럼 (A열)
    non_meta = [c for c in df_event.columns if c not in ("호선","id","updated_at")]
    return non_meta[0] if non_meta else df_event.columns[0]

def _get_ev_main_event_col(df_event) -> str:
    """MAIN EVENT 컬럼 탐색"""
    candidates = ["MAIN EVENT","MAIN_EVENT","Main Event","EVENT","Event"]
    for cand in candidates:
        if cand in df_event.columns:
            return cand
    non_meta = [c for c in df_event.columns if c not in ("호선","id","updated_at")]
    return non_meta[7] if len(non_meta) > 7 else non_meta[-1]

def get_event_summary(df_event, df_subsys, df_mc=None) -> pd.DataFrame:
    """MAIN EVENT 기준 현황"""
    cols_ss = list(df_subsys.columns)
    ev_sys_col   = _get_ev_subsys_col(df_event)
    ev_event_col = _get_ev_main_event_col(df_event)
    ss_sub_col   = _find_col(df_subsys, ["Syb-System","Sub-System","SUB SYSTEM","SUB_SYSTEM","SUBSYSTEM"]) or (cols_ss[2] if len(cols_ss) > 2 else None)
    ss_date_col  = _find_col(df_subsys, ["완료일자","완료 일자","완료일","COMPLETE DATE","COMPLETE_DATE"]) or (cols_ss[4] if len(cols_ss) > 4 else None)

    if ev_sys_col is None or ev_event_col is None:
        return pd.DataFrame(columns=["MAIN EVENT","완료계획일","MC 총합","MC완료","완료율(%)","신호등"])

    # SUB SYSTEM → 완료계획일 맵
    subsys_date_map = {}
    if ss_sub_col and ss_date_col:
        for _, row in df_subsys.iterrows():
            code = str(row[ss_sub_col]).strip() if not _is_empty(row[ss_sub_col]) else None
            try: dt = datetime.date.fromisoformat(str(row[ss_date_col])[:10])
            except: dt = None
            if code and dt:
                if code not in subsys_date_map or dt < subsys_date_map[code]:
                    subsys_date_map[code] = dt

    mc_subsys_map = get_mc_subsys_map(df_mc) if df_mc is not None else {}
    today = datetime.date.today()
    rows  = []

    ev_col_s   = df_event[ev_event_col]
    sys_col_s  = df_event[ev_sys_col]
    if isinstance(ev_col_s,  pd.DataFrame): ev_col_s  = ev_col_s.iloc[:, 0]
    if isinstance(sys_col_s, pd.DataFrame): sys_col_s = sys_col_s.iloc[:, 0]

    df_ev2 = df_event.copy()
    df_ev2["__event"] = ev_col_s.apply(lambda v: str(v).strip() if not _is_empty(v) else None)
    df_ev2["__sys"]   = sys_col_s.apply(lambda v: str(v).strip() if not _is_empty(v) else None)

    for main_event, grp in df_ev2.dropna(subset=["__event"]).groupby("__event"):
        subsys_codes  = [r for r in grp["__sys"].dropna().tolist() if r]
        matched_dates = [subsys_date_map[c] for c in subsys_codes if c in subsys_date_map]
        plan_date_str = min(matched_dates).strftime("%Y-%m-%d") if matched_dates else "-"
        mc_total_sum = 0; mc_done_sum = 0; matched_mc = False
        for code in subsys_codes:
            if code in mc_subsys_map:
                mc_total_sum += mc_subsys_map[code]["total"]
                mc_done_sum  += mc_subsys_map[code]["done"]
                matched_mc    = True
        mc_rate = round(mc_done_sum / mc_total_sum * 100, 1) if mc_total_sum else 0.0
        rows.append({
            "MAIN EVENT": main_event,
            "완료계획일": plan_date_str,
            "MC 총합": mc_total_sum if matched_mc else "-",
            "MC완료":  mc_done_sum  if matched_mc else "-",
            "완료율(%)": mc_rate if matched_mc else 0.0,
            "신호등": get_mc_signal(plan_date_str, mc_rate, today),
        })
    return pd.DataFrame(sorted(rows, key=lambda r: r["완료계획일"]))


def get_subsystem_summary(df_event, df_subsys, df_mc=None) -> pd.DataFrame:
    """
    SUB SYSTEM 기준 현황
    ★ MC 파일 SUB\nSYSTEM 컬럼(index 19) 피벗 기준
      → 과 필터 적용된 df_mc 에서 SUB SYSTEM 목록 추출
      → SUBSYS 파일에서 완료계획일 조회
      → MC 데이터 기준 총합/완료/잔여/완료율 계산
    """
    if df_mc is None or df_mc.empty:
        return pd.DataFrame(columns=["SUB SYSTEM","완료계획일","MC 총합","MC완료","완료율(%)","신호등"])

    # ── MC SUB SYSTEM 컬럼 탐색 ──────────────────────────
    mc_ss_col = _find_col(df_mc, [
        "SUB\nSYSTEM", "SUB SYSTEM", "SUB_SYSTEM", "SUBSYSTEM",
        "SYSTEM", "System"
    ])
    if mc_ss_col is None:
        # index 19 fallback
        non_meta = [c for c in df_mc.columns if c.lower() not in ("id","updated_at","호선","과명")]
        mc_ss_col = non_meta[19] if len(non_meta) > 19 else None
    if mc_ss_col is None:
        return pd.DataFrame(columns=["SUB SYSTEM","완료계획일","MC 총합","MC완료","완료율(%)","신호등"])

    # ── SUBSYS 파일에서 완료계획일 맵 ────────────────────
    cols_ss   = list(df_subsys.columns)
    ss_sub_col  = _find_col(df_subsys, ["Syb-System","Sub-System","SUB SYSTEM","SUB_SYSTEM","SUBSYSTEM"]) or (cols_ss[2] if len(cols_ss) > 2 else None)
    ss_date_col = _find_col(df_subsys, ["완료일자","완료 일자","완료일","COMPLETE DATE","COMPLETE_DATE"]) or (cols_ss[4] if len(cols_ss) > 4 else None)

    subsys_date_map = {}
    if ss_sub_col and ss_date_col:
        for _, row in df_subsys.iterrows():
            code = str(row[ss_sub_col]).strip() if not _is_empty(row[ss_sub_col]) else None
            if not code: continue
            try: dt = datetime.date.fromisoformat(str(row[ss_date_col])[:10])
            except: dt = None
            if dt:
                if code not in subsys_date_map or dt < subsys_date_map[code]:
                    subsys_date_map[code] = dt

    # ── MC 기준 완료 컬럼 ────────────────────────────────
    ac_col  = _get_ac_col(df_mc)
    tag_col = _find_col(df_mc, ["TAG NO","TAG_NO","TAG_No","TAGNO","TAG","MC_CD","MC_NO","ITR_CD"])
    today   = datetime.date.today()
    rows    = []

    # ── MC SUB SYSTEM 피벗 ───────────────────────────────
    ss_series = df_mc[mc_ss_col]
    if isinstance(ss_series, pd.DataFrame): ss_series = ss_series.iloc[:, 0]

    # SUB SYSTEM별 MC 집계
    df_mc2 = df_mc.copy()
    df_mc2["__ss"] = ss_series.apply(
        lambda v: str(v).strip() if not _is_empty(v) else None
    )

    for code, grp in df_mc2.dropna(subset=["__ss"]).groupby("__ss"):
        code = str(code).strip()
        if not code: continue

        # TAG NO 기준 총합
        if tag_col:
            tc = grp[tag_col]
            if isinstance(tc, pd.DataFrame): tc = tc.iloc[:, 0]
            mc_total = int(tc.dropna().shape[0])
        else:
            mc_total = len(grp)

        mc_done = int(grp.apply(lambda r: _mc_done(r, ac_col), axis=1).sum())
        mc_rate = round(mc_done / mc_total * 100, 1) if mc_total else 0.0

        # SUBSYS 파일에서 완료계획일 조회
        plan_date_str = subsys_date_map[code].strftime("%Y-%m-%d") if code in subsys_date_map else "-"

        rows.append({
            "SUB SYSTEM": code,
            "완료계획일": plan_date_str,
            "MC 총합": mc_total,
            "MC완료":  mc_done,
            "완료율(%)": mc_rate,
            "신호등": get_mc_signal(plan_date_str, mc_rate, today),
        })

    # ★ 완료계획일 정렬: 금일 기준 최신 날짜 위, 날짜 없는 항목 맨 아래
    def _sort_key(r):
        d = r["완료계획일"]
        if d == "-" or not d:
            return (1, "9999-99-99")   # 날짜 없으면 맨 마지막
        try:
            dt = datetime.date.fromisoformat(str(d)[:10])
            diff = abs((dt - today).days)
            return (0, diff)           # 금일 기준 가장 가까운 날짜 먼저
        except:
            return (1, "9999-99-99")

    return pd.DataFrame(sorted(rows, key=_sort_key))


# 하위 호환
def get_mc_system_summary(df): return pd.DataFrame()
def get_mc_monthly(df): return get_mc_weekly(df)
def get_subsystem_detail(df_event, df_subsys, main_event): return pd.DataFrame()


# ──────────────────────────────────────────
# ROOM (CABLE SCH)
# ──────────────────────────────────────────
TBL_ROOM = "lq_proc3_9"

@st.cache_data(ttl=600)
def load_room_data(ship: str) -> pd.DataFrame:
    """ROOM 데이터 로드 (proc_3_room 테이블)"""
    df = run_query(
        f"SELECT * FROM [{TBL_ROOM}] WHERE 호선 = ?",
        params=(ship,)
    )
    return df if not df.empty else pd.DataFrame()


def get_room_list(df_room: pd.DataFrame) -> list:
    """ROOM NAME 목록 추출 (B열)"""
    col = _find_col(df_room, ["ROOM NAME", "ROOM_NAME", "ROOM N", "ROOM"])
    if col is None:
        non_meta = [c for c in df_room.columns if c.lower() not in ("id","updated_at","호선")]
        col = non_meta[1] if len(non_meta) > 1 else None
    if col is None:
        return []
    vals = df_room[col].dropna().unique().tolist()
    return sorted([str(v).strip() for v in vals if str(v).strip()])


def get_room_summary(df_room: pd.DataFrame, room_name: str = "전체",
                      df_mc: pd.DataFrame = None) -> pd.DataFrame:
    """
    ROOM NAME별 진행현황 집계
    총합: 엑셀(SN 기준), 완료/잔여: 마트(SN 매칭)
    """
    import datetime as _dt

    if df_room is None or df_room.empty:
        return pd.DataFrame(columns=["신호등","ROOM NAME","총합","완료","잔여","완료율(%)","RM H/O"])

    # 컬럼 탐색 (헤더명 기반 — 열 추가해도 안전)
    room_col = _find_col(df_room, ["ROOM NAME", "ROOM_NAME", "ROOM N", "ROOM"])
    tag_col_r = _find_col(df_room, ["TAG NO", "TAG_NO", "TAG_No", "TAGNO"])
    itr_col_r = _find_col(df_room, ["ITR", "ITR_CD", "ITR_NO"])
    ho_col = _find_col(df_room, ["RM H/O", "RM_H/O", "RM HO", "RM_HO", "RMHO", "RM H_O", "RM_H_O"])

    if room_col is None:
        non_meta = [c for c in df_room.columns if c.lower() not in ("id","updated_at","호선")]
        room_col = non_meta[1] if len(non_meta) > 1 else None

    if room_col is None:
        return pd.DataFrame(columns=["신호등","ROOM NAME","총합","완료","잔여","완료율(%)","RM H/O"])

    # ★ 마트 키 생성: TAG_No + ITR 합치기
    mc_key_set = set()
    mc_done_key_set = set()
    if df_mc is not None and not df_mc.empty:
        mc_tag = _find_col(df_mc, ["TAG NO","TAG_NO","TAG_No","TAGNO","TAG","MC_CD","MC_NO","ITR_CD"])
        mc_itr = _find_col(df_mc, ["ITR","ITR_CD","ITR_NO","A-ITR"])
        mc_ac = _get_ac_col(df_mc)
        if mc_tag and mc_itr:
            for _, r in df_mc.iterrows():
                t = str(r[mc_tag]).strip() if not _is_empty(r[mc_tag]) else ""
                i = str(r[mc_itr]).strip() if not _is_empty(r[mc_itr]) else ""
                key = f"{t}|{i}" if t and i else ""
                if key:
                    mc_key_set.add(key)
                    if _mc_done(r, mc_ac):
                        mc_done_key_set.add(key)

    df2 = df_room.copy()
    df2["__room"] = df2[room_col].apply(
        lambda v: str(v).strip() if not _is_empty(v) else None
    )
    # ★ 엑셀 키 생성: TAG NO(E열) + ITR(D열)
    if tag_col_r and itr_col_r:
        df2["__key"] = df2.apply(
            lambda r: f"{str(r[tag_col_r]).strip()}|{str(r[itr_col_r]).strip()}"
            if not _is_empty(r[tag_col_r]) and not _is_empty(r[itr_col_r]) else None, axis=1
        )
    else:
        df2["__key"] = None

    if room_name != "전체":
        df2 = df2[df2["__room"] == room_name]

    if df2.empty:
        return pd.DataFrame(columns=["신호등","ROOM NAME","총합","완료","잔여","완료율(%)","RM H/O"])

    today = _dt.date.today()

    def _get_ho_date(grp):
        if ho_col is None or ho_col not in grp.columns:
            return None
        dates = []
        for v in grp[ho_col].dropna():
            s = str(v).strip()
            if not s or s in ("None", "nan", "-"):
                continue
            try:
                dates.append(_dt.date.fromisoformat(s[:10]))
            except:
                try:
                    dates.append(pd.to_datetime(s).date())
                except:
                    continue
        return min(dates) if dates else None

    def _signal(rate, ho_date):
        if rate >= 100.0:
            return "🟢"
        if ho_date is None:
            return "⚪"
        days_left = (ho_date - today).days
        if days_left > 14:
            return "🟢"
        elif days_left > 7:
            return "🟡"
        else:
            return "🔴"

    rows = []
    for rname, grp in df2.dropna(subset=["__room"]).groupby("__room"):
        rname = str(rname).strip()
        if not rname: continue

        # 총합 = 엑셀 행 수
        total = len(grp)

        # 완료/잔여 = 마트 TAG NO+ITR 매칭
        if tag_col_r and itr_col_r and mc_key_set:
            key_list = grp["__key"].dropna().tolist()
            done = sum(1 for k in key_list if k in mc_done_key_set)
        else:
            # 마트 없으면 엑셀 기준 fallback
            ac_col = _find_col(df_room, ["완료유무","완료여부","RESULT","COMPLETE"])
            done = 0
            if ac_col:
                for _, r in grp.iterrows():
                    v = r.get(ac_col)
                    if v is not None and str(v).strip() not in ("","None","nan","미완료"):
                        done += 1

        rate = round(done / total * 100, 1) if total else 0.0
        ho_date = _get_ho_date(grp)
        ho_str = ho_date.strftime("%Y-%m-%d") if ho_date else "-"
        signal = _signal(rate, ho_date)

        rows.append({
            "신호등": signal,
            "ROOM NAME": rname,
            "총합": total, "완료": done, "잔여": total - done,
            "완료율(%)": rate,
            "RM H/O": ho_str,
        })

    return pd.DataFrame(rows)


def get_room_kpi(df_room: pd.DataFrame, room_name: str = "전체",
                  df_mc: pd.DataFrame = None) -> dict:
    """ROOM 전체 KPI — 총합=엑셀, 완료/잔여=마트"""
    summary = get_room_summary(df_room, room_name, df_mc)
    if summary.empty:
        return {"총합": 0, "완료": 0, "잔여": 0, "완료율": 0.0}
    total = int(summary["총합"].sum())
    done = int(summary["완료"].sum())
    return {"총합": total, "완료": done, "잔여": total - done,
            "완료율": round(done / total * 100, 1) if total else 0.0}


# ──────────────────────────────────────────
# MC 상세 리스트 (항목 선택 시)
# ──────────────────────────────────────────
def get_mc_detail_by_event(df_mc: pd.DataFrame, event_name: str,
                           df_event=None, df_subsys=None) -> pd.DataFrame:
    """MAIN EVENT 기준 MC 상세 리스트
    EVENT 테이블에서 MAIN EVENT → SUB SYSTEM 코드 목록 → MC 데이터에서 해당 항목 추출
    """
    if df_mc is None or df_mc.empty: return pd.DataFrame()

    # 방법1: MC에 MAIN EVENT 컬럼이 직접 있는 경우
    ev_col = _find_col(df_mc, ["MAIN\nEVENT","MAIN EVENT","MAIN_EVENT","MainEvent","EVENT"])
    if ev_col is not None:
        df2 = df_mc[df_mc[ev_col].apply(lambda v: str(v).strip() == event_name if not _is_empty(v) else False)]
        if not df2.empty:
            return _extract_mc_detail(df2)

    # 방법2: EVENT 테이블 경유 (get_event_summary와 동일 로직)
    if df_event is not None and not df_event.empty:
        ev_event_col = _get_ev_main_event_col(df_event)
        ev_sys_col = _get_ev_subsys_col(df_event)
        if ev_event_col and ev_sys_col:
            ev_col_s = df_event[ev_event_col]
            sys_col_s = df_event[ev_sys_col]
            if isinstance(ev_col_s, pd.DataFrame): ev_col_s = ev_col_s.iloc[:, 0]
            if isinstance(sys_col_s, pd.DataFrame): sys_col_s = sys_col_s.iloc[:, 0]

            # MAIN EVENT에 속한 SUB SYSTEM 코드 목록
            mask_ev = ev_col_s.apply(lambda v: str(v).strip() == event_name if not _is_empty(v) else False)
            sub_list = sys_col_s[mask_ev].dropna().apply(lambda v: str(v).strip()).unique().tolist()
            sub_list = [s for s in sub_list if s]

            if sub_list:
                ss_col_mc = _get_subsys_col(df_mc)
                if ss_col_mc:
                    ss_series = df_mc[ss_col_mc]
                    if isinstance(ss_series, pd.DataFrame): ss_series = ss_series.iloc[:, 0]
                    mask = ss_series.apply(lambda v: str(v).strip() in sub_list if not _is_empty(v) else False)
                    df2 = df_mc[mask]
                    if not df2.empty:
                        return _extract_mc_detail(df2)

    return pd.DataFrame()


def get_mc_detail_by_subsys(df_mc: pd.DataFrame, subsys_name: str) -> pd.DataFrame:
    """SUB SYSTEM 기준 MC 상세 리스트"""
    if df_mc is None or df_mc.empty: return pd.DataFrame()
    ss_col = _get_subsys_col(df_mc)
    if ss_col is None: return pd.DataFrame()
    ss = df_mc[ss_col]
    if isinstance(ss, pd.DataFrame): ss = ss.iloc[:, 0]
    mask = ss.apply(lambda v: str(v).strip() == subsys_name if not _is_empty(v) else False)
    return _extract_mc_detail(df_mc[mask])


def get_room_detail(df_room: pd.DataFrame, room_name: str,
                     df_mc: pd.DataFrame = None) -> pd.DataFrame:
    """ROOM NAME 기준 상세 리스트 — 마트 데이터 기반 (TAG NO + ITR 매칭)"""
    if df_room is None or df_room.empty: return pd.DataFrame()
    room_col = _find_col(df_room, ["ROOM NAME","ROOM_NAME","ROOM N","ROOM","ROOM NO"])
    tag_col_r = _find_col(df_room, ["TAG NO","TAG_NO","TAG_No","TAGNO"])
    itr_col_r = _find_col(df_room, ["ITR","ITR_CD","ITR_NO"])
    if room_col is None:
        non_meta = [c for c in df_room.columns if c.lower() not in ("id","updated_at","호선")]
        room_col = non_meta[1] if len(non_meta) > 1 else None
    if room_col is None: return pd.DataFrame()

    # 해당 ROOM의 TAG NO + ITR 키 목록 추출
    df2 = df_room[df_room[room_col].apply(lambda v: str(v).strip() == room_name if not _is_empty(v) else False)]
    if df2.empty or not tag_col_r or not itr_col_r: return pd.DataFrame()

    key_set = set()
    for _, r in df2.iterrows():
        t = str(r[tag_col_r]).strip() if not _is_empty(r[tag_col_r]) else ""
        i = str(r[itr_col_r]).strip() if not _is_empty(r[itr_col_r]) else ""
        if t and i:
            key_set.add(f"{t}|{i}")

    # 마트에서 매칭
    if df_mc is not None and not df_mc.empty and key_set:
        mc_tag = _find_col(df_mc, ["TAG NO","TAG_NO","TAG_No","TAGNO","TAG","MC_CD","MC_NO","ITR_CD"])
        mc_itr = _find_col(df_mc, ["ITR","ITR_CD","ITR_NO","A-ITR"])
        if mc_tag and mc_itr:
            df_mc2 = df_mc.copy()
            df_mc2["__key"] = df_mc2.apply(
                lambda r: f"{str(r[mc_tag]).strip()}|{str(r[mc_itr]).strip()}"
                if not _is_empty(r[mc_tag]) and not _is_empty(r[mc_itr]) else "", axis=1
            )
            matched = df_mc2[df_mc2["__key"].isin(key_set)]
            if not matched.empty:
                return _extract_mc_detail(matched)

    # fallback: 엑셀 데이터
    return _extract_room_detail(df2)


def _extract_mc_detail(df):
    """MC 데이터에서 표시할 컬럼 추출: TAG NO, 완료유무, 검사일, SUB SYSTEM, SYSTEM DESC"""
    if df.empty: return pd.DataFrame()
    tag_col = _find_col(df, ["TAG NO","TAG_NO","TAG_No","TAGNO","TAG","MC_CD","MC_NO","ITR_CD"])
    ac_col = _get_ac_col(df)
    date_col = _find_col(df, [
        "COMPLETE\nDATE","COMPLETE DATE","COMPLETE_DATE","CompleteDate",
        "완료일","완료날짜","완료일자","검사일","INSP_DT","CNFM_DT","MC_CNFM_DT",
    ])
    ss_col = _get_subsys_col(df)
    desc_col = _find_col(df, [
        "SYSTEM\nDESC","SYSTEM DESC","SYSTEM_DESC","SYS_DESC","SystemDesc",
        "DISC DESC","DISC\nDESC","DISC_DESC","Description",
    ])
    def _val(r, col):
        if col and col in r.index:
            v = r[col]
            if v is not None and str(v).strip() not in ("","None","nan"):
                return str(v).strip()
        return "-"
    rows = []
    for _, r in df.iterrows():
        rows.append({
            "TAG NO": _val(r, tag_col),
            "완료유무": _val(r, ac_col),
            "검사일": _val(r, date_col),
            "SUB SYSTEM": _val(r, ss_col),
            "SYSTEM DESC": _val(r, desc_col),
        })
    return pd.DataFrame(rows)


def _extract_room_detail(df):
    """ROOM 데이터에서 표시할 컬럼 추출"""
    if df.empty: return pd.DataFrame()
    tag_col = _find_col(df, ["TAG NO","TAG_NO","TAG_No","TAGNO","SN","TAG NO"])
    ac_col = _find_col(df, ["완료유무","완료여부","RESULT","COMPLETE","CNFM_YN"])
    date_col = _find_col(df, ["검사일","INSP_DT","CNFM_DT","완료일"])
    sys_col = _find_col(df, ["SYSTEM","MC_SYS_CD","SYS_CD","SUB SYSTEM","SUB_SYSTEM"])
    itr_col = _find_col(df, ["ITR구분","ITR_GB","ITR","ITR구분"])
    scope_col = _find_col(df, ["SCOPE","SCOPE_NM"])
    def _val(r, col):
        if col and col in r.index:
            v = r[col]
            if v is not None and str(v).strip() not in ("","None","nan"):
                return str(v).strip()
        return "-"
    rows = []
    for _, r in df.iterrows():
        rows.append({
            "TAG NO": _val(r, tag_col),
            "완료유무": _val(r, ac_col),
            "검사일": _val(r, date_col),
            "SYSTEM": _val(r, sys_col),
            "ITR구분": _val(r, itr_col),
            "SCOPE": _val(r, scope_col),
        })
    result = pd.DataFrame(rows)
    # 모든 값이 "-"인 컬럼 제거
    for c in result.columns:
        if (result[c] == "-").all():
            result = result.drop(columns=[c])
    return result


def get_room_by_gwa(df_room: pd.DataFrame, room_name: str,
                     df_mc_dict: dict = None) -> dict:
    """
    ROOM NAME 기준으로 과별 완료 현황 반환
    df_mc_dict: {"선실전장과": df_mc_전장, "선실1과": df_mc_1과, ...}
    반환: {"선실전장과": {"총합":N, "완료":N, "잔여":N, "완료율":X, "df_mc": df}, ...}
    """
    if df_room is None or df_room.empty or not df_mc_dict:
        return {}

    room_col = _find_col(df_room, ["ROOM NAME","ROOM_NAME","ROOM N","ROOM"])
    tag_col_r = _find_col(df_room, ["TAG NO","TAG_NO","TAG_No","TAGNO"])
    itr_col_r = _find_col(df_room, ["ITR","ITR_CD","ITR_NO"])
    if room_col is None:
        non_meta = [c for c in df_room.columns if c.lower() not in ("id","updated_at","호선")]
        room_col = non_meta[1] if len(non_meta) > 1 else None
    if room_col is None or not tag_col_r or not itr_col_r:
        return {}

    # 해당 ROOM의 TAG NO + ITR 키 목록
    df2 = df_room[df_room[room_col].apply(lambda v: str(v).strip() == room_name if not _is_empty(v) else False)]
    if df2.empty:
        return {}

    key_set = set()
    for _, r in df2.iterrows():
        t = str(r[tag_col_r]).strip() if not _is_empty(r[tag_col_r]) else ""
        i = str(r[itr_col_r]).strip() if not _is_empty(r[itr_col_r]) else ""
        if t and i:
            key_set.add(f"{t}|{i}")

    total = len(key_set)
    result = {}

    for gwa_name, df_mc in df_mc_dict.items():
        if df_mc is None or df_mc.empty:
            continue
        mc_tag = _find_col(df_mc, ["TAG NO","TAG_NO","TAG_No","TAGNO","TAG","MC_CD","MC_NO","ITR_CD"])
        mc_itr = _find_col(df_mc, ["ITR","ITR_CD","ITR_NO","A-ITR"])
        mc_ac = _get_ac_col(df_mc)
        if not mc_tag or not mc_itr:
            continue

        df_mc2 = df_mc.copy()
        df_mc2["__key"] = df_mc2.apply(
            lambda r: f"{str(r[mc_tag]).strip()}|{str(r[mc_itr]).strip()}"
            if not _is_empty(r[mc_tag]) and not _is_empty(r[mc_itr]) else "", axis=1
        )
        matched = df_mc2[df_mc2["__key"].isin(key_set)]
        if matched.empty:
            continue

        done = int(matched.apply(lambda r: _mc_done(r, mc_ac), axis=1).sum())
        gwa_total = len(matched)
        result[gwa_name] = {
            "총합": gwa_total,
            "완료": done,
            "잔여": gwa_total - done,
            "완료율": round(done / gwa_total * 100, 1) if gwa_total else 0.0,
            "df_mc": matched,
        }

    return result  