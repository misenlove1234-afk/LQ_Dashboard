
"""
╔══════════════════════════════════════════════════════════════════╗
║ 담당자 : ___________ (본인 이름 작성) ║
║ 항목 : [화면 전용] kpi_2 - 글로벌 BEP 실적 ║
║ 작성일 : 2026-03-17 수정 : 2026-04-07 ║
╚══════════════════════════════════════════════════════════════════╝

【 변경이력 2026-03-19 】
  - 상단: 이달 BEP 현황 카드 (그룹별) 유지
  - 상단: ★ 연간 누적 달성현황 카드 추가 (선택월까지 누적)
  - 하단(월간): ★ 차트를 "연간 누적 BEP vs 목표" 비교 차트로 변경
  - 하단(월간): 반별 달성현황 테이블 유지

【 변경이력 2026-04-07 】
  - 상세 페이지 추가: 개인별 × 일별 급여 상세 조회
    (날짜/그룹/반 필터, 사번별 정상MH/잔업MH/급여 상세)
  - 사이드바 기준월 필터 아래 "상세 현황 보기" 버튼 추가
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import logging
import traceback
from datetime import date

logger = logging.getLogger(__name__)

from data.kpi_2_data import (
    _급여월,
    _주차_라벨,
    _월내_주차_라벨,
    build_일별_기초,
    agg_월간,
    agg_주간,
    agg_주간누적,
    agg_연간누적,
    agg_월말전망,
    load_그룹단가,
    load_상세_일별,
    get_filter_options,
    반_표시명,
    반_그룹매핑,
    반_표시순서,
    정상근무시간,
)

# ── 그룹별 소속 반 매핑 ─────────────────────────────────
그룹별_반 = {
    "1그룹 (선실2과)": ["곡직반", "취부반"],
    "2그룹 (선실1과+전장과)": ["설치1직2반", "전장1직3반"],
}

그룹_반매핑 = {
    "1그룹": ["곡직반", "취부반"],
    "2그룹": ["설치1직2반", "전장1직3반"],
}

# 그룹별 색상
그룹색상 = {
    "1그룹": "#38BDF8",
    "2그룹": "#10B981",
}

반_색상 = {
    "곡직반": "#38BDF8",
    "취부반": "#10B981",
    "설치1직2반": "#F59E0B",
    "전장1직3반": "#A78BFA",
}


# ══════════════════════════════════════════════════════════
# 내부 유틸
# ══════════════════════════════════════════════════════════

def _fv(v, fmt=".3f", suffix="", na="-"):
    try:
        if v is None: return na
        f = float(v)
        if np.isnan(f): return na
        return f"{f:{fmt}}{suffix}"
    except Exception:
        return na


def _신호등(bep, 목표bep):
    if pd.isna(bep) or pd.isna(목표bep):
        return '<span style="font-size:1.1rem;">⚫</span>'
    if bep >= 목표bep:
        return '<span style="font-size:1.1rem;">🟢</span>'
    elif bep >= 목표bep * 0.9:
        return '<span style="font-size:1.1rem;">🟡</span>'
    else:
        return '<span style="font-size:1.1rem;">🔴</span>'


def _apply_layout(fig, title, height=320):
    fig.update_layout(
        title=dict(text=title, font=dict(color="#E2E8F0", size=13)),
        paper_bgcolor="rgba(15,23,42,0.0)", plot_bgcolor="rgba(15,23,42,0.0)",
        font=dict(color="#CBD5E1"),
        legend=dict(bgcolor="rgba(10,18,40,0.8)", bordercolor="#334155", font_size=11),
        xaxis=dict(gridcolor="rgba(51,65,85,0.4)", showgrid=True),
        yaxis=dict(gridcolor="rgba(51,65,85,0.4)", showgrid=True, title="BEP"),
        height=height, margin=dict(l=10, r=20, t=36, b=10),
    )


def _월라벨(m):
    try: return f"{int(m[5:7])}월"
    except: return m


# ══════════════════════════════════════════════════════════
# ★ 신규: 연간 누적 달성현황 카드 (HTML)
# ══════════════════════════════════════════════════════════

def _html_연간누적카드(df_누적, 선택월, year):
    """
    그룹별 연간 누적 BEP 달성현황 카드
    선택월까지의 누적 실적을 보여줌
    """
    if df_누적 is None or df_누적.empty:
        return "<div style='color:#64748B; text-align:center; padding:1rem;'>누적 데이터 없음</div>"

    # 선택월까지 필터 후 각 그룹의 마지막(선택월) 누적값 사용
    df = df_누적[df_누적["월"] <= 선택월].copy()
    if df.empty:
        return "<div style='color:#64748B; text-align:center; padding:1rem;'>해당 월 데이터 없음</div>"

    # ★ 그룹별 선택월 기준 최신 누적값 (누적기성/급여/BEP)
    # 그룹목표BEP는 연간 고정값이므로 어느 행이든 동일
    df_최신 = df.sort_values("월").groupby("그룹").last().reset_index()

    th = ("padding:0.5rem 1.0rem; font-size:0.75rem; color:#A78BFA; font-weight:600; "
          "text-align:center; white-space:nowrap; background:rgba(167,139,250,0.08); "
          "border-bottom:2px solid rgba(167,139,250,0.2);")

    thead = (
        "<tr>"
        f"<th style='{th} text-align:left;'>그룹</th>"
        f"<th style='{th}'>연간 목표 BEP <span style='font-size:0.65rem; color:#64748B;'>(고정)</span></th>"
        f"<th style='{th}'>누적 실적 BEP</th>"
        f"<th style='{th}'>부족/초과 MH</th>"
        f"<th style='{th}'>달성률</th>"
        f"<th style='{th}'>누적 기성(MH)</th>"
        f"<th style='{th}'>누적 급여(원)</th>"
        f"<th style='{th}'>상태</th>"
        "</tr>"
    )

    tbody = ""
    for _, row in df_최신.iterrows():
        그룹명 = row.get("그룹", "-")
        누적BEP = row.get("누적BEP")
        목표BEP = row.get("그룹목표BEP")
        부족mh = row.get("부족초과MH")
        달성률 = row.get("달성률")
        누적기성 = row.get("누적기성", 0)
        누적급여 = row.get("누적급여", 0)

        달성 = (pd.notna(누적BEP) and pd.notna(목표BEP) and float(누적BEP) >= float(목표BEP))
        근접 = (pd.notna(누적BEP) and pd.notna(목표BEP) and float(누적BEP) >= float(목표BEP) * 0.9)
        bep_c = "#10B981" if 달성 else ("#F59E0B" if 근접 else "#EF4444")
        mh_c = "#10B981" if (pd.notna(부족mh) and 부족mh >= 0) else "#EF4444"
        아이콘 = "✅" if 달성 else ("🟡" if 근접 else "🔴")
        border = "#10B981" if 달성 else ("#F59E0B" if 근접 else "#EF4444")
        bg = "rgba(16,185,129,0.04)" if 달성 else ("rgba(245,158,11,0.04)" if 근접 else "rgba(239,68,68,0.04)")
        달성률_c = "#10B981" if 달성 else ("#F59E0B" if 근접 else "#EF4444")
        mh_str = "-" if pd.isna(부족mh) else (("+" if 부족mh >= 0 else "") + f"{부족mh:,.1f}")
        상태_str = "달성" if 달성 else "차질"
        상태_c = "#10B981" if 달성 else "#EF4444"

        그룹_c = 그룹색상.get(그룹명.split(" ")[0] if 그룹명 else "", "#38BDF8")

        td = (f"padding:0.75rem 1.0rem; font-size:0.88rem; background:{bg}; "
              "border-bottom:1px solid rgba(255,255,255,0.04);")

        tbody += (
            f"<tr style='border-left:3px solid {border};'>"
            f"<td style='{td} font-weight:700; color:{그룹_c};'>{아이콘} {그룹명}</td>"
            f"<td style='{td} text-align:center; color:#94A3B8; font-weight:600;'>{_fv(목표BEP)}</td>"
            f"<td style='{td} text-align:center; font-size:1.05rem; font-weight:800; "
            f"color:{bep_c}; font-family:Montserrat,sans-serif;'>{_fv(누적BEP)}</td>"
            f"<td style='{td} text-align:center; font-weight:700; color:{mh_c};'>{mh_str}</td>"
            f"<td style='{td} text-align:center; font-weight:700; color:{달성률_c};'>"
            f"{_fv(달성률, '.1f')}%</td>"
            f"<td style='{td} text-align:center; color:#94A3B8;'>{_fv(누적기성, ',.1f')}</td>"
            f"<td style='{td} text-align:center; color:#94A3B8;'>{_fv(누적급여, ',.0f')}</td>"
            f"<td style='{td} text-align:center; font-weight:800; color:{상태_c};'>{상태_str}</td>"
            "</tr>"
        )

    return (
        f"<div style='background:linear-gradient(145deg,rgba(30,41,59,0.5),rgba(15,23,42,0.8));"
        f" border:1px solid rgba(167,139,250,0.15); border-radius:12px; overflow:hidden; margin-bottom:1rem;'>"
        f"<div style='display:flex; justify-content:space-between; align-items:center;"
        f" padding:0.6rem 1.2rem; border-bottom:1px solid rgba(167,139,250,0.1);'>"
        f"<span style='font-size:0.85rem; font-weight:700; color:#E2E8F0;'>"
        f"📊 연간 누적 BEP 달성현황 (1월 ~ {_월라벨(선택월)})</span>"
        f"<span style='font-size:0.75rem; color:#A78BFA; font-weight:600;'>"
        f"{year}년 | 그룹별 목표기준</span>"
        f"</div>"
        f"<table style='width:100%; border-collapse:collapse;'>"
        f"<thead>{thead}</thead><tbody>{tbody}</tbody>"
        f"</table></div>"
    )


# ══════════════════════════════════════════════════════════
# ★ 신규: 연간 누적 BEP 추이 차트 (그룹별)
# ══════════════════════════════════════════════════════════

def _chart_연간누적_추이(df_누적, 선택월, title="연간 누적 BEP 추이"):
    """
    그룹별 연간 누적 BEP vs 목표 비교 차트
    - 실적: 꺾은선 (굵게)
    - 목표: 점선
    - 배경: 달성월 하이라이트
    선택월까지만 표시
    """
    fig = go.Figure()

    df = df_누적[df_누적["월"] <= 선택월].copy() if df_누적 is not None and not df_누적.empty else pd.DataFrame()

    if df.empty:
        fig.add_annotation(text="데이터 없음", x=0.5, y=0.5, showarrow=False,
                          font=dict(color="#64748B", size=14), xref="paper", yref="paper")
        _apply_layout(fig, title, height=360)
        return fig

    for 그룹명 in ["1그룹", "2그룹"]:
        df_그룹 = df[df["그룹"] == 그룹명].sort_values("월")
        if df_그룹.empty:
            continue

        c = 그룹색상.get(그룹명, "#94A3B8")
        x라벨 = df_그룹["월라벨"].tolist()

        # 실적 꺾은선
        fig.add_trace(go.Scatter(
            x=x라벨,
            y=df_그룹["누적BEP"].tolist(),
            name=f"{그룹명} 실적",
            mode="lines+markers+text",
            line=dict(color=c, width=2.5),
            marker=dict(size=8, color=c,
                       line=dict(color="rgba(15,23,42,0.8)", width=1.5)),
            text=df_그룹["누적BEP"].apply(
                lambda v: f"{v:.3f}" if pd.notna(v) else ""
            ).tolist(),
            textposition="top center",
            textfont=dict(size=9, color=c),
        ))

        # 목표 점선 (표시 기간 전체 목표 평균 → 수평선 1줄)
        목표_y = [v for v in df_그룹["그룹목표BEP"].tolist() if pd.notna(v)]
        if 목표_y:
            목표평균 = round(sum(목표_y) / len(목표_y), 3)
            fig.add_trace(go.Scatter(
                x=x라벨,
                y=[목표평균] * len(x라벨),
                name=f"{그룹명} 목표({목표평균:.3f})",
                mode="lines",
                line=dict(color=c, width=1.8, dash="dot"),
                opacity=0.7,
            ))

        # 달성/미달 배경 (월 범위로 올바르게 지정)
        for i, (_, row) in enumerate(df_그룹.iterrows()):
            bep = row.get("누적BEP")
            목표 = row.get("그룹목표BEP")
            if pd.notna(bep) and pd.notna(목표):
                달성 = bep >= 목표
                x0_val = x라벨[i - 1] if i > 0 else x라벨[i]
                x1_val = x라벨[i]
                fig.add_vrect(
                    x0=x0_val, x1=x1_val,
                    fillcolor="rgba(16,185,129,0.05)" if 달성 else "rgba(239,68,68,0.05)",
                    opacity=1, layer="below", line_width=0,
                )

    # BEP 1.0 기준선
    fig.add_hline(
        y=1.0, line_dash="dash",
        line_color="rgba(148,163,184,0.5)", line_width=1.2,
        annotation_text="BEP 1.0",
        annotation_font_color="#94A3B8",
        annotation_position="right",
    )

    fig.update_layout(
        title=dict(text=title, font=dict(color="#E2E8F0", size=13)),
        paper_bgcolor="rgba(15,23,42,0.0)",
        plot_bgcolor="rgba(15,23,42,0.0)",
        font=dict(color="#CBD5E1"),
        legend=dict(
            bgcolor="rgba(10,18,40,0.8)",
            bordercolor="#334155",
            font_size=11,
            orientation="h",
            yanchor="bottom", y=1.02,
            xanchor="right", x=1,
        ),
        xaxis=dict(
            gridcolor="rgba(51,65,85,0.4)",
            categoryorder="array",
            categoryarray=[f"{i}월" for i in range(1, 13)],
            title="급여월",
        ),
        yaxis=dict(
            gridcolor="rgba(51,65,85,0.4)",
            title="누적 BEP",
            zeroline=False,
        ),
        height=360,
        margin=dict(l=10, r=20, t=50, b=10),
        hovermode="x unified",
    )
    return fig


# ══════════════════════════════════════════════════════════
# 이달 BEP 현황 카드 (기존)
# ══════════════════════════════════════════════════════════

def _calc_반별_집계(df_월간, 선택월, ms_전망=None):
    """반별 BEP/부족MH 계산 - _table_반별과 동일 로직"""
    현재급여월 = _급여월(date.today())
    진행중 = (선택월 >= 현재급여월)
    df = df_월간[df_월간["월"] == 선택월] if "월" in df_월간.columns else df_월간
    결과 = {}
    for _, row in df.iterrows():
        반명 = row.get("반_표시", "")
        if not 반명: continue
        기성 = float(row.get("실적기성", row.get("최종기성", 0)) or 0)
        월간급여 = float(row.get("월간급여", 0) or 0)
        단가 = float(row.get("단가", 0) or 0)
        목표 = float(row.get("목표BEP", 1) or 1)
        월급여_기본 = float(row.get("월급여", 0) or 0)
        특잔업 = float(row.get("특잔업비", 0) or 0)
        전망급여 = 월급여_기본 + 특잔업
        전망잔여 = float(ms_전망.get(반명, 0)) if ms_전망 else 0
        월말전망기성 = 기성 + 전망잔여
        if 진행중:
            평가기성 = 월말전망기성
            평가급여 = 전망급여
        else:
            평가기성 = 기성
            평가급여 = 월간급여
        목표기성 = (평가급여 * 목표 / 단가) if 단가 > 0 and 평가급여 > 0 else 0
        부족mh = 평가기성 - 목표기성
        bep = (평가기성 * 단가) / 평가급여 if 평가급여 > 0 and 단가 > 0 else 0.0
        결과[반명] = {
            "기성": 평가기성, "급여": 평가급여, "단가": 단가,
            "목표": 목표, "부족mh": 부족mh, "BEP": bep,
            "그룹목표BEP": float(row.get("그룹목표BEP", 1) or 1),
        }
    return 결과


def _calc_그룹데이터(df_이달=None, 선택반="전체", 선택월=None, df_기초=None, 주차_종료일=None, ms_전망=None):
    """그룹별 BEP/부족MH - 월간: _calc_반별_집계 합산, 주간: df_기초 필터"""
    결과 = []
    for 그룹명, 반목록 in 그룹별_반.items():
        반목록_f = [r for r in 반목록 if r == 선택반] if 선택반 != "전체" else 반목록
        if not 반목록_f:
            continue

        # 주간 모드
        if 주차_종료일 is not None and df_기초 is not None and not df_기초.empty and 선택월:
            from data.kpi_2_data import 반_표시명 as _반표시명, load_목표BEP, load_그룹단가
            반전체명목록 = [k for k, v in _반표시명.items() if v in 반목록_f]
            df_f = df_기초[
                (df_기초["반"].isin(반전체명목록)) &
                (df_기초["급여월"] == 선택월) &
                (df_기초["날짜"] <= 주차_종료일)
            ]
            기성합계 = float(df_f["기성합계"].sum())
            급여합계 = float(df_f["기본급"].sum() + df_f["특잔업비"].sum())
            단가_df = df_f.groupby("반", as_index=False).agg(기성합계=("기성합계","sum"), 단가=("단가","first"))
            총기성_단가 = 단가_df["기성합계"].sum()
            그룹단가 = float((단가_df["기성합계"] * 단가_df["단가"]).sum() / 총기성_단가) if 총기성_단가 > 0 else 1.0
            year = int(선택월[:4])
            df_목표 = load_목표BEP(year)
            그룹키 = "1그룹" if "1그룹" in 그룹명 else "2그룹"
            그룹목표 = 1.0
            if not df_목표.empty:
                행 = df_목표[(df_목표["구분"]=="GROUP")&(df_목표["그룹코드"]==그룹키)&(df_목표["월_str"]==선택월)]
                if not 행.empty: 그룹목표 = float(행["목표BEP"].iloc[0])
            그룹BEP = (기성합계 * 그룹단가) / 급여합계 if 급여합계 > 0 and 그룹단가 > 0 else 0.0
            목표기성 = (급여합계 * 그룹목표) / 그룹단가 if 그룹단가 > 0 else 0.0
            결과.append({"그룹": 그룹명, "BEP": 그룹BEP, "목표": 그룹목표,
                         "부족mh": 기성합계 - 목표기성, "기성": 기성합계,
                         "급여": 급여합계, "달성률": round(그룹BEP/그룹목표*100,1) if 그룹목표>0 else 0})
            continue

        # 월간 모드 - _calc_반별_집계 합산
        if df_이달 is None or df_이달.empty:
            결과.append({"그룹": 그룹명, "BEP": None, "목표": None, "부족mh": None, "기성": 0, "급여": 0, "달성률": 0})
            continue

        반별 = _calc_반별_집계(df_이달, 선택월, ms_전망)
        총기성 = 총급여 = 총부족 = 기성_단가합 = 0.0
        그룹목표 = 1.0
        유효반 = False
        for 반표시 in 반목록_f:
            r = 반별.get(반표시)
            if not r: continue
            유효반 = True
            총기성 += r["기성"]
            총급여 += r["급여"]
            총부족 += r["부족mh"]
            기성_단가합 += r["기성"] * r["단가"]
            그룹목표 = r["그룹목표BEP"]

        if not 유효반:
            결과.append({"그룹": 그룹명, "BEP": None, "목표": None, "부족mh": None, "기성": 0, "급여": 0, "달성률": 0})
            continue

        그룹BEP = 기성_단가합 / 총급여 if 총급여 > 0 else 0.0
        달성률 = round(그룹BEP / 그룹목표 * 100, 1) if 그룹목표 > 0 else 0.0
        결과.append({"그룹": 그룹명, "BEP": 그룹BEP, "목표": 그룹목표,
                     "부족mh": 총부족, "기성": 총기성, "급여": 총급여, "달성률": 달성률})
    return 결과

def _html_그룹카드(카드데이터, 이달월):
    th = ("padding:0.5rem 1.2rem; font-size:0.75rem; color:#38BDF8; font-weight:600; "
          "text-align:center; white-space:nowrap; background:rgba(56,189,248,0.08); "
          "border-bottom:2px solid rgba(56,189,248,0.2);")
    thead = (
        "<tr>"
        f"<th style='{th} text-align:left;'>그룹</th>"
        f"<th style='{th}'>목표 BEP</th>"
        f"<th style='{th}'>현재 BEP</th>"
        f"<th style='{th}'>부족/초과 MH</th>"
        f"<th style='{th}'>달성률</th>"
        f"<th style='{th}'>차질여부</th>"
        "</tr>"
    )
    tbody = ""
    for d in 카드데이터:
        bep = d["BEP"]; 목표 = d["목표"]; mh = d["부족mh"]; 그룹명 = d["그룹"]
        달성률 = d.get("달성률", 0) or 0
        달성 = (bep is not None and 목표 is not None and bep >= 목표)
        근접 = (bep is not None and 목표 is not None and bep >= 목표 * 0.9)
        bep_c = "#10B981" if 달성 else ("#F59E0B" if 근접 else "#EF4444")
        mh_c = "#10B981" if (mh is not None and mh >= 0) else "#EF4444"
        mh_str = "-" if mh is None else (("+" if mh >= 0 else "") + f"{mh:,.1f}")
        아이콘 = "✅" if 달성 else ("🟡" if 근접 else "🔴")
        border = "#10B981" if 달성 else ("#F59E0B" if 근접 else "#EF4444")
        bg = "rgba(16,185,129,0.04)" if 달성 else ("rgba(245,158,11,0.04)" if 근접 else "rgba(239,68,68,0.04)")
        달성률_c = "#10B981" if 달성 else ("#F59E0B" if 근접 else "#EF4444")
        차질 = "달성" if 달성 else "차질"
        차질_c = "#10B981" if 달성 else "#EF4444"
        그룹_c = 그룹색상.get(그룹명.split(" ")[0] if 그룹명 else "", "#38BDF8")

        td = (f"padding:0.75rem 1.2rem; font-size:0.9rem; background:{bg}; "
              "border-bottom:1px solid rgba(255,255,255,0.04);")
        tbody += (
            f"<tr style='border-left:3px solid {border};'>"
            f"<td style='{td} font-weight:700; color:{그룹_c};'>{아이콘} {그룹명}</td>"
            f"<td style='{td} text-align:center; color:#94A3B8; font-weight:600;'>{_fv(목표)}</td>"
            f"<td style='{td} text-align:center; font-size:1.1rem; font-weight:800; "
            f"color:{bep_c}; font-family:Montserrat,sans-serif;'>{_fv(bep)}</td>"
            f"<td style='{td} text-align:center; font-weight:700; color:{mh_c};'>{mh_str}</td>"
            f"<td style='{td} text-align:center; font-weight:700; color:{달성률_c};'>{_fv(달성률, '.1f')}%</td>"
            f"<td style='{td} text-align:center; font-weight:800; color:{차질_c};'>{차질}</td>"
            "</tr>"
        )
    return (
        f"<div style='background:linear-gradient(145deg,rgba(30,41,59,0.5),rgba(15,23,42,0.8));"
        f" border:1px solid rgba(255,255,255,0.06); border-radius:12px; overflow:hidden; margin-bottom:1rem;'>"
        f"<div style='display:flex; justify-content:space-between; align-items:center;"
        f" padding:0.6rem 1.2rem; border-bottom:1px solid rgba(255,255,255,0.06);'>"
        f"<span style='font-size:0.85rem; font-weight:700; color:#E2E8F0;'>📊 {이달월} BEP 현황</span>"
        f"<span style='font-size:0.75rem; color:#38BDF8; font-weight:600;'>{이달월} 기준</span>"
        f"</div>"
        f"<table style='width:100%; border-collapse:collapse;'>"
        f"<thead>{thead}</thead><tbody>{tbody}</tbody>"
        f"</table></div>"
    )


# ══════════════════════════════════════════════════════════
# 반별 달성현황 테이블 (기존)
# ══════════════════════════════════════════════════════════

def _table_반별(df_월간, 선택월, 선택반, df_전망=None):
    df = df_월간[df_월간["월"] == 선택월].copy()
    if 선택반 != "전체":
        df = df[df["반_표시"] == 선택반]
    if df.empty:
        return "<div style='color:#64748B; text-align:center; padding:1.5rem;'>해당 월 데이터 없음</div>"

    # ★ 반 순서 고정
    순서_map = {반: i for i, 반 in enumerate(반_표시순서)}
    df["_순서"] = df["반_표시"].map(순서_map).fillna(99)
    df = df.sort_values("_순서").reset_index(drop=True)

    오늘 = date.today()
    현재급여월 = _급여월(오늘)
    진행중 = (선택월 >= 현재급여월)

    try:
        yr, mo = int(선택월[:4]), int(선택월[5:7])
        start_d = date(yr-1, 12, 11) if mo == 1 else date(yr, mo-1, 11)
        end_d = date(yr, mo, 10)
        총일수 = max((end_d - start_d).days, 1)
        경과일 = max((오늘 - start_d).days, 1)
        진행률 = min(경과일 / 총일수, 1.0)
    except Exception:
        진행률 = 0.5

    ms_전망 = {}
    if df_전망 is not None and not df_전망.empty:
        for _, r in df_전망.iterrows():
            ms_전망[r.get("반_표시", "")] = r.get("전망기성", 0)

    if 진행중:
        headers = ["반", "실적MH (58CODE)", "월간급여(원)", "목표BEP", "현재BEP",
                   "전망MH", "전망BEP", "부족/초과MH", "달성률", "차질여부"]
    else:
        headers = ["반", "실적MH (58CODE)", "월간급여(원)", "목표BEP", "현재BEP",
                   "부족/초과MH", "달성률", "차질여부"]

    th = ("padding:0.5rem 0.8rem; font-size:0.75rem; color:#38BDF8; font-weight:600; "
          "text-align:center; white-space:nowrap; background:rgba(56,189,248,0.08); "
          "border-bottom:2px solid rgba(56,189,248,0.2);")
    thead = "".join(f"<th style='{th}'>{h}</th>" for h in headers)

    tbody = ""
    for idx, (_, row) in enumerate(df.iterrows()):
        bg = "rgba(255,255,255,0.03)" if idx % 2 == 0 else "transparent"
        bep = row.get("BEP") # ★ 실적만 BEP
        목표 = row.get("목표BEP")
        기성 = row.get("실적기성", row.get("최종기성", 0)) # ★ 실적만 기성
        가상기성58 = row.get("58가상기성", 0)
        급여 = row.get("실적급여", row.get("월간급여", 0)) # ★ 실적급여 우선
        반명 = row.get("반_표시", "-")
        월급여_기본 = row.get("월급여", 0) or 0
        특잔업 = row.get("특잔업비", 0) or 0
        복리후생_v = row.get("복리후생비", 0) or 0
        전망급여 = 월급여_기본 + 특잔업 + 복리후생_v
        단가 = float(row.get("단가", 0) or 0)

        # 전망잔여기성: milestone 기반
        전망잔여 = float(ms_전망.get(반명, 0)) if ms_전망 is not None else 0

        # 월말전망기성 = 실적기성 + 잔여전망
        월말전망기성 = float(기성) + 전망잔여

        전망BEP = (월말전망기성 * 단가) / float(전망급여) if 전망급여 > 0 and 단가 > 0 else 0
        목표기성 = (float(전망급여) * float(목표) / 단가) if (목표 and pd.notna(목표) and 단가 > 0) else 0

        if 진행중:
            부족mh = 월말전망기성 - 목표기성
        else:
            현재목표기성 = (float(급여) * float(목표) / 단가) if (목표 and pd.notna(목표) and 단가 > 0) else 0
            부족mh = float(기성) - 현재목표기성

        평가bep_val = float(전망BEP) if 진행중 else (float(bep) if pd.notna(bep) else 0)
        달성률_v = round(평가bep_val / float(목표) * 100, 1) if (목표 and pd.notna(목표) and float(목표) > 0) else 0
        달성여부 = 달성률_v >= 100

        bep_c = "#10B981" if (pd.notna(bep) and pd.notna(목표) and float(bep) >= float(목표)) else "#EF4444"
        전망c = "#10B981" if (전망BEP and 목표 and 전망BEP >= float(목표)) else "#F59E0B"
        mh_c = "#10B981" if 부족mh >= 0 else "#EF4444"
        mh_str = ("+" if 부족mh >= 0 else "") + f"{부족mh:,.1f}"
        달성률_c = "#10B981" if 달성여부 else ("#F59E0B" if 달성률_v >= 90 else "#EF4444")
        차질여부_str = "달성" if 달성여부 else "차질"
        차질여부_c = "#10B981" if 달성여부 else "#EF4444"
        반_c = 반_색상.get(반명, "#38BDF8")

        기성_str = f"{_fv(기성, ',.1f')}"
        if 반명 == "취부반" and float(가상기성58) > 0:
            기성_str = (f"{_fv(기성, ',.1f')} <span style='font-size:0.72rem; "
                       f"color:#A78BFA;'>({_fv(가상기성58, ',.1f')})</span>")

        td = (f"padding:0.6rem 0.8rem; font-size:0.85rem; background:{bg}; "
              "border-bottom:1px solid rgba(255,255,255,0.04);")

        if 진행중:
            tbody += (
                "<tr>"
                f"<td style='{td} font-weight:700; color:{반_c};'>{반명}</td>"
                f"<td style='{td} text-align:center; color:#CBD5E1;'>{기성_str}</td>"
                f"<td style='{td} text-align:center; color:#CBD5E1;'>{_fv(급여, ',.0f')}</td>"
                f"<td style='{td} text-align:center; color:#94A3B8; font-weight:600;'>{_fv(목표)}</td>"
                f"<td style='{td} text-align:center; font-size:1rem; font-weight:800; "
                f"color:{bep_c}; font-family:Montserrat,sans-serif;'>{_fv(bep)}</td>"
                f"<td style='{td} text-align:center; color:#94A3B8;'>{_fv(전망잔여, ',.1f')}</td>"
                f"<td style='{td} text-align:center; font-size:1rem; font-weight:800; "
                f"color:{전망c}; font-family:Montserrat,sans-serif;'>{_fv(전망BEP)}</td>"
                f"<td style='{td} text-align:center; font-weight:700; color:{mh_c};'>{mh_str}</td>"
                f"<td style='{td} text-align:center; font-weight:700; color:{달성률_c};'>{달성률_v:.1f}%</td>"
                f"<td style='{td} text-align:center; font-weight:800; color:{차질여부_c};'>{차질여부_str}</td>"
                "</tr>"
            )
        else:
            tbody += (
                "<tr>"
                f"<td style='{td} font-weight:700; color:{반_c};'>{반명}</td>"
                f"<td style='{td} text-align:center; color:#CBD5E1;'>{기성_str}</td>"
                f"<td style='{td} text-align:center; color:#CBD5E1;'>{_fv(급여, ',.0f')}</td>"
                f"<td style='{td} text-align:center; color:#94A3B8; font-weight:600;'>{_fv(목표)}</td>"
                f"<td style='{td} text-align:center; font-size:1rem; font-weight:800; "
                f"color:{bep_c}; font-family:Montserrat,sans-serif;'>{_fv(bep)}</td>"
                f"<td style='{td} text-align:center; font-weight:700; color:{mh_c};'>{mh_str}</td>"
                f"<td style='{td} text-align:center; font-weight:700; color:{달성률_c};'>{달성률_v:.1f}%</td>"
                f"<td style='{td} text-align:center; font-weight:800; color:{차질여부_c};'>{차질여부_str}</td>"
                "</tr>"
            )
    return (f"<div style='overflow-x:auto;'><table style='width:100%; border-collapse:collapse;'>"
            f"<thead><tr>{thead}</tr></thead><tbody>{tbody}</tbody></table></div>")


# ══════════════════════════════════════════════════════════
# 주간 차트 / 테이블 (기존)
# ══════════════════════════════════════════════════════════

def _chart_주간_추이(df_누적, 선택월, title="주간 누적 BEP"):
    fig = go.Figure()
    df = df_누적[df_누적["월"] == 선택월].copy()
    반_목록 = sorted(df["반_표시"].dropna().unique())
    for i, 반 in enumerate(반_목록):
        df_반 = df[df["반_표시"] == 반].sort_values("주차")
        c = 반_색상.get(반, "#94A3B8")
        fig.add_trace(go.Scatter(
            x=df_반["월내주차"], y=df_반["누적BEP"], name=반,
            mode="lines+markers",
            line=dict(color=c, width=2.5), marker=dict(size=7),
        ))
        if "목표BEP" in df_반.columns:
            fig.add_trace(go.Scatter(
                x=df_반["월내주차"], y=df_반["목표BEP"], name=반+" 목표",
                mode="lines", line=dict(color=c, width=1.5, dash="dot"),
                showlegend=False,
            ))
    fig.add_hline(y=1.0, line_dash="dash", line_color="rgba(148,163,184,0.4)",
                  annotation_text="BEP 1.0", annotation_font_color="#94A3B8",
                  annotation_position="right")
    _apply_layout(fig, title)
    return fig


def _table_주간_누적(df_누적, 선택월, 선택주차=None, 선택반="전체", df_ms_전망=None, df_기초=None):
    """
    주간 누적 테이블 - 선택 주차 마지막날까지 기준
    전망MH/전망BEP = 선택 주차 마지막날까지의 전망 기성/급여
    """
    df = df_누적[df_누적["월"] == 선택월].copy()
    if 선택반 != "전체":
        df = df[df["반_표시"] == 선택반]
    if 선택주차:
        df = df[df["주차"] <= 선택주차]
    if df.empty:
        return "<div style='color:#64748B; text-align:center; padding:1.5rem;'>해당 월/주차 데이터 없음</div>"

    오늘 = date.today()
    현재급여월 = _급여월(오늘)
    진행중 = (선택월 >= 현재급여월)

    try:
        yr, mo = int(선택월[:4]), int(선택월[5:7])
        월_시작 = date(yr-1, 12, 11) if mo == 1 else date(yr, mo-1, 11)
        월_종료 = date(yr, mo, 10)
    except Exception:
        yr, mo = 오늘.year, 오늘.month
        월_시작 = date(yr, mo-1, 11) if mo > 1 else date(yr-1, 12, 11)
        월_종료 = 오늘

    # 선택 주차 마지막날 (일요일 기준, 급여월 종료일 초과 시 제한)
    주차_마지막날 = 월_종료
    if 선택주차:
        try:
            _yr, _w = int(선택주차.split("-W")[0]), int(선택주차.split("-W")[1])
            주차_마지막날 = min(
                pd.Timestamp.fromisocalendar(_yr, _w, 7).date(),
                월_종료
            )
        except Exception:
            주차_마지막날 = 월_종료

    # 선택 주차 마지막날까지 전망 기성/급여 계산 (df_기초 기반)
    주차전망_dict = {} # 반_표시 → (전망기성, 전망급여)
    if df_기초 is not None and not df_기초.empty:
        from data.kpi_2_data import 반_표시명 as _반표시명_주간
        for 반표시 in df_누적["반_표시"].unique():
            반전체명 = next((k for k,v in _반표시명_주간.items() if v == 반표시), None)
            if 반전체명 is None: continue
            df_반전망 = df_기초[
                (df_기초["반"] == 반전체명) &
                (df_기초["급여월"] == 선택월) &
                (df_기초["구분"] == "전망") &
                (df_기초["날짜"] <= 주차_마지막날)
            ]
            주차전망_dict[반표시] = (
                float(df_반전망["기성합계"].sum()) if not df_반전망.empty else 0.0,
                float(df_반전망["급여합계"].sum()) if not df_반전망.empty else 0.0,
            )

    # 반별 마지막(선택주차) 누계값 집계 후 순서 정렬
    df_반별 = df.sort_values("주차").groupby("반_표시", as_index=False).last()
    순서_map = {반: i for i, 반 in enumerate(반_표시순서)}
    df_반별["_순서"] = df_반별["반_표시"].map(순서_map).fillna(99)
    df_반별 = df_반별.sort_values("_순서").reset_index(drop=True)

    if 진행중:
        headers = ["반", "기준주차", "누계기성(MH)", "누계급여(원)", "목표BEP",
                   "현재BEP", "전망MH", "전망BEP", "부족/초과MH", "달성률", "차질여부"]
    else:
        headers = ["반", "기준주차", "누계기성(MH)", "누계급여(원)", "목표BEP",
                   "현재BEP", "부족/초과MH", "달성률", "차질여부"]

    th = ("padding:0.5rem 0.8rem; font-size:0.75rem; color:#38BDF8; font-weight:600; "
          "text-align:center; white-space:nowrap; background:rgba(56,189,248,0.08); "
          "border-bottom:2px solid rgba(56,189,248,0.2);")
    thead = "".join(f"<th style='{th}'>{h}</th>" for h in headers)

    tbody = ""
    for idx, (_, row) in enumerate(df_반별.iterrows()):
        bg = "rgba(255,255,255,0.03)" if idx % 2 == 0 else "transparent"
        반명 = row.get("반_표시", "-")
        누계기성 = float(row.get("누적기성", 0) or 0)
        누계급여 = float(row.get("누적급여", 0) or 0)
        누계BEP = row.get("누적BEP")
        목표BEP = row.get("목표BEP")
        단가 = float(row.get("단가", 0) or 0)
        주차라벨 = row.get("월내주차", "-")
        누계58가상기성 = float(row.get("누적58가상기성", 0) or 0)

        # 주차 마지막날까지 전망 기성/급여
        전망기성추가, 전망급여추가 = 주차전망_dict.get(반명, (0.0, 0.0))
        전망잔여 = 전망기성추가
        주차전망기성 = 누계기성 + 전망잔여
        주차전망급여 = 누계급여 + 전망급여추가

        전망BEP = (주차전망기성 * 단가) / 주차전망급여 if 주차전망급여 > 0 and 단가 > 0 else 0

        # ★ 부족/초과MH: 항상 누계 기준 (현재 주차까지 달성 여부)
        누계목표기성 = (누계급여 * float(목표BEP) / 단가) if (목표BEP and pd.notna(목표BEP) and 단가 > 0) else 0
        부족mh = 누계기성 - 누계목표기성

        # ★ 달성여부: 누계BEP vs 목표BEP
        평가BEP = float(누계BEP) if pd.notna(누계BEP) else 0

        달성률_v = round(평가BEP / float(목표BEP) * 100, 1) if (목표BEP and pd.notna(목표BEP) and float(목표BEP) > 0) else 0
        달성여부 = 달성률_v >= 100

        bep_c = "#10B981" if (pd.notna(누계BEP) and pd.notna(목표BEP) and float(누계BEP) >= float(목표BEP)) else "#EF4444"
        전망c = "#10B981" if (전망BEP and 목표BEP and 전망BEP >= float(목표BEP)) else "#F59E0B"
        mh_c = "#10B981" if 부족mh >= 0 else "#EF4444"
        mh_str = ("+" if 부족mh >= 0 else "") + f"{부족mh:,.1f}"
        달성률_c = "#10B981" if 달성여부 else ("#F59E0B" if 달성률_v >= 90 else "#EF4444")
        차질_str = "달성" if 달성여부 else "차질"
        차질_c = "#10B981" if 달성여부 else "#EF4444"
        반_c = 반_색상.get(반명, "#38BDF8")

        # ★ 58공수 있으면 누계기성 옆에 (58가상기성) 표시
        기성_str = f"{_fv(누계기성, ',.1f')}"
        if 누계58가상기성 > 0:
            기성_str = (
                f"{_fv(누계기성, ',.1f')} "
                f"<span style='font-size:0.72rem; color:#A78BFA;'>"
                f"({_fv(누계58가상기성, ',.1f')})</span>"
            )

        td = (f"padding:0.6rem 0.8rem; font-size:0.85rem; background:{bg}; "
              "border-bottom:1px solid rgba(255,255,255,0.04);")

        if 진행중:
            tbody += (
                "<tr>"
                f"<td style='{td} font-weight:700; color:{반_c};'>{반명}</td>"
                f"<td style='{td} text-align:center; color:#94A3B8; font-size:0.78rem;'>{주차라벨}</td>"
                f"<td style='{td} text-align:center; color:#CBD5E1;'>{기성_str}</td>"
                f"<td style='{td} text-align:center; color:#CBD5E1;'>{_fv(누계급여, ',.0f')}</td>"
                f"<td style='{td} text-align:center; color:#94A3B8; font-weight:600;'>{_fv(목표BEP)}</td>"
                f"<td style='{td} text-align:center; font-size:1rem; font-weight:800; "
                f"color:{bep_c}; font-family:Montserrat,sans-serif;'>{_fv(누계BEP)}</td>"
                f"<td style='{td} text-align:center; color:#94A3B8;'>{_fv(전망잔여, ',.1f')}</td>"
                f"<td style='{td} text-align:center; font-size:1rem; font-weight:800; "
                f"color:{전망c}; font-family:Montserrat,sans-serif;'>{_fv(전망BEP)}</td>"
                f"<td style='{td} text-align:center; font-weight:700; color:{mh_c};'>{mh_str}</td>"
                f"<td style='{td} text-align:center; font-weight:700; color:{달성률_c};'>{달성률_v:.1f}%</td>"
                f"<td style='{td} text-align:center; font-weight:800; color:{차질_c};'>{차질_str}</td>"
                "</tr>"
            )
        else:
            tbody += (
                "<tr>"
                f"<td style='{td} font-weight:700; color:{반_c};'>{반명}</td>"
                f"<td style='{td} text-align:center; color:#94A3B8; font-size:0.78rem;'>{주차라벨}</td>"
                f"<td style='{td} text-align:center; color:#CBD5E1;'>{기성_str}</td>"
                f"<td style='{td} text-align:center; color:#CBD5E1;'>{_fv(누계급여, ',.0f')}</td>"
                f"<td style='{td} text-align:center; color:#94A3B8; font-weight:600;'>{_fv(목표BEP)}</td>"
                f"<td style='{td} text-align:center; font-size:1rem; font-weight:800; "
                f"color:{bep_c}; font-family:Montserrat,sans-serif;'>{_fv(누계BEP)}</td>"
                f"<td style='{td} text-align:center; font-weight:700; color:{mh_c};'>{mh_str}</td>"
                f"<td style='{td} text-align:center; font-weight:700; color:{달성률_c};'>{달성률_v:.1f}%</td>"
                f"<td style='{td} text-align:center; font-weight:800; color:{차질_c};'>{차질_str}</td>"
                "</tr>"
            )

    return (f"<div style='overflow-x:auto;'><table style='width:100%; border-collapse:collapse;'>"
            f"<thead><tr>{thead}</tr></thead><tbody>{tbody}</tbody></table></div>")


# ══════════════════════════════════════════════════════════
# render()
# ══════════════════════════════════════════════════════════

def _render_급여그룹_진단():
    """급여그룹 매칭 진단 expander — lq_kpi2_1.급여그룹 ↔ lq_kpi2_2.그룹 점검.
    매칭 실패 / 그룹값 비교 / 월급여=0 케이스 한눈에 확인.
    """
    with st.expander("🔍 급여그룹 매칭 진단 (lq_kpi2_1 ↔ lq_kpi2_2)", expanded=False):
        from data.kpi_2_data import load_인원정보, load_급여정보
        try:
            df_인원 = load_인원정보()
            df_급여 = load_급여정보()
        except Exception as e:
            logger.error("급여 데이터 로드 실패: %s\n%s", e, traceback.format_exc())
            st.error("데이터 로드에 실패했습니다. 관리자에게 문의해 주세요.")
            return

        부서_list = list(반_표시명.keys())
        df_재직 = df_인원[
            df_인원["부서"].isin(부서_list) &
            (df_인원["퇴사일"].isna() |
             df_인원["퇴사일"].apply(lambda d: d is None or d > date.today()))
        ].copy()
        df_재직["급여그룹_strip"] = (
            df_재직["급여그룹"].astype(str).str.strip()
        )
        그룹_set = set(df_급여["그룹"].astype(str).str.strip().tolist())
        df_재직["매칭"] = df_재직["급여그룹_strip"].isin(그룹_set)

        # ① 매칭 실패
        st.markdown("##### 1) 매칭 실패 인원 (재직 중)")
        실패 = df_재직[~df_재직["매칭"]][
            ["사번", "부서", "급여그룹", "배치일_고정", "퇴사일"]
        ].copy()
        if 실패.empty:
            st.success(
                f"✅ 매칭 실패 없음 — 재직 인원 {len(df_재직):,}명 모두 매칭"
            )
        else:
            st.error(f"❌ 매칭 실패 {len(실패):,}명 — "
                     "이 인원은 기본급/특잔업/복리후생 합산에서 빠집니다")
            st.dataframe(실패, use_container_width=True, hide_index=True)

        # ② 양쪽 고유 그룹값 비교
        st.markdown("##### 2) 양 테이블 고유 급여그룹값 비교")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**lq_kpi2_1 (인원정보) 측 급여그룹**")
            인원_그룹 = (df_재직.groupby("급여그룹_strip", as_index=False)
                         .size().rename(columns={"size": "인원수"}))
            인원_그룹["표시"] = "[" + 인원_그룹["급여그룹_strip"].fillna("NULL") + "]"
            st.dataframe(인원_그룹[["표시", "인원수"]],
                         use_container_width=True, hide_index=True)
        with col2:
            st.markdown("**lq_kpi2_2 (급여정보) 측 그룹**")
            급여_그룹 = df_급여.copy()
            급여_그룹["표시"] = (
                "[" + 급여_그룹["그룹"].astype(str).str.strip()
                .fillna("NULL") + "]"
            )
            cols_show = [c for c in ["표시", "월급여", "복리후생비용", "잔업시급"]
                         if c in 급여_그룹.columns or c == "표시"]
            st.dataframe(급여_그룹[cols_show],
                         use_container_width=True, hide_index=True)

        # ③ 매칭은 됐지만 월급여 0/NULL
        st.markdown("##### 3) 매칭됐지만 월급여가 0/NULL 인 인원")
        df_매칭_OK = df_재직[df_재직["매칭"]].copy()
        급여_dict_dbg = (df_급여.copy().assign(
            _key=df_급여["그룹"].astype(str).str.strip()
        ).set_index("_key")[["월급여", "복리후생비용"]].to_dict("index"))
        df_매칭_OK["월급여_값"] = df_매칭_OK["급여그룹_strip"].apply(
            lambda g: float(급여_dict_dbg.get(g, {}).get("월급여", 0) or 0)
        )
        df_매칭_OK["복리후생_값"] = df_매칭_OK["급여그룹_strip"].apply(
            lambda g: float(급여_dict_dbg.get(g, {}).get("복리후생비용", 0) or 0)
        )
        영급여 = df_매칭_OK[df_매칭_OK["월급여_값"] == 0][
            ["사번", "부서", "급여그룹", "월급여_값", "복리후생_값"]
        ]
        if 영급여.empty:
            st.success("✅ 매칭 인원 중 월급여 0/NULL 인 사례 없음")
        else:
            st.error(f"⚠️ 매칭은 됐지만 월급여 = 0 인 인원 {len(영급여):,}명")
            st.dataframe(영급여, use_container_width=True, hide_index=True)

        # ④ 요약
        st.markdown("##### 📊 요약")
        n_total = len(df_재직)
        n_fail  = len(실패)
        n_match = n_total - n_fail
        n_zero  = len(영급여)
        n_ok    = n_match - n_zero
        st.markdown(
            f"- 재직 인원: **{n_total:,}명**  \n"
            f"- 매칭 실패: **{n_fail:,}명** {'❌' if n_fail else '✅'}  \n"
            f"- 매칭됐으나 월급여 0: **{n_zero:,}명** {'⚠️' if n_zero else '✅'}  \n"
            f"- 정상 합산 대상: **{n_ok:,}명** ✅"
        )


def render():
    st.html("""
    <style>
    [data-testid="stSidebar"] { background: rgba(8,18,42,0.95) !important;
        border-right: 1px solid rgba(56,189,248,0.15) !important; }
    [data-testid="stSidebar"] * { color: #CBD5E1 !important; }
    [data-testid="stSidebar"] div[data-baseweb="select"] > div {
        background: rgba(30,41,59,0.8) !important;
        border-color: rgba(56,189,248,0.2) !important; }
    </style>
    """)

    # 마지막 업로드 시간 조회 (howon_global 관련 테이블만)
    _last_update = ""
    try:
        from data.kpi_2_data import _run_query
        _df_log = _run_query(
            "SELECT TOP 1 테이블명, 업로드시간 FROM dbo.lq_업로드로그 "
            "WHERE 테이블명 LIKE 'lq_kpi2%' "
            "ORDER BY 업로드시간 DESC"
        )
        if not _df_log.empty:
            _t = _df_log.iloc[0]["업로드시간"]
            _tbl = _df_log.iloc[0]["테이블명"]
            _last_update = (f"<span style='font-size:0.75rem; color:#64748B; margin-left:1rem;'>"
                           f"🔄 최근 업로드: {_t} ({_tbl})</span>")
    except Exception:
        pass

    st.markdown(
        f"<div class='section-title' style='font-size:1.3rem; margin-bottom:1rem;'>"
        f"💰 글로벌 BEP 실적{_last_update}</div>",
        unsafe_allow_html=True,
    )

    # ── 급여그룹 매칭 진단 (collapsed expander) ─────────────
    _render_급여그룹_진단()

    현재연도 = date.today().year

    # ── 연도는 항상 먼저 (상세/메인 공통) ──────────────────
    with st.sidebar:
        st.markdown(
            "<div style='color:#38BDF8; font-weight:700; font-size:0.95rem; "
            "margin-bottom:0.8rem;'>🔎 조회 조건</div>",
            unsafe_allow_html=True,
        )
        선택연도 = st.selectbox(
            "연도", list(range(현재연도, 현재연도-3, -1)), index=0, key="kpi2_연도"
        )

    # ── 상세 페이지 조기 분기 (연도만 공유, 나머지 사이드바는 상세에서 그림) ──
    if st.session_state.get("kpi2_page") == "detail":
        _render_상세(선택연도)
        return

    # ── 메인 페이지 사이드바 나머지 ──────────────────────────
    with st.sidebar:
        보기모드 = st.radio(
            "BEP 보기 모드", ["월간", "주간"], index=0, horizontal=True, key="kpi2_보기모드"
        )

    # ── 데이터 로드 (단일 소스) ──────────────────────────
    try:
        opts = get_filter_options(선택연도)
        df_기초 = build_일별_기초(선택연도)
        df_월간 = agg_월간(df_기초, 선택연도)
        df_주간 = agg_주간(df_기초, 선택연도)
        df_누적 = agg_주간누적(df_주간)
        df_연간누적 = agg_연간누적(df_월간, 선택연도)
    except Exception as e:
        logger.error("데이터 로드 실패: %s\n%s", e, traceback.format_exc())
        st.error("데이터 로드에 실패했습니다. 관리자에게 문의해 주세요.")
        return

    if df_월간 is None or df_월간.empty:
        st.html(
            "<div class='neo-card' style='text-align:center; color:#64748B; padding:2rem;'>"
            "⚠️ 데이터가 없습니다. bep_upload.py 를 먼저 실행해 주세요.</div>"
        )
        return

    # ── 사이드바 나머지 필터 ─────────────────────────────
    with st.sidebar:
        반_options = opts.get("반_list", ["전체"])
        선택반 = st.selectbox("반 선택", 반_options, index=0, key="kpi2_반")

        if 보기모드 == "월간":
            월_options = opts.get("월_list", [])
            현재월 = opts.get("현재월", "")
            기본월_idx = 월_options.index(현재월) if 현재월 in 월_options else max(len(월_options)-1, 0)
            선택월 = st.selectbox("기준 월 (급여월)", 월_options, index=기본월_idx, key="kpi2_월")
            선택주차 = None; 선택주차_라벨 = ""
        else:
            # 주간: 월 먼저, 그 다음 주차
            월_options = opts.get("월_list", [])
            현재월 = opts.get("현재월", "")
            기본월_idx = 월_options.index(현재월) if 현재월 in 월_options else max(len(월_options)-1, 0)
            선택월 = st.selectbox("기준 월 (급여월)", 월_options, index=기본월_idx, key="kpi2_주간_월")

            # 선택월에 속하는 주차만 필터
            # 선택월에 속하는 주차: df_누적에서 직접 가져옴 (급여월 기준으로 이미 분리됨)
            df_월_누적 = df_누적[df_누적["월"] == 선택월] if df_누적 is not None and not df_누적.empty else pd.DataFrame()
            월내주차_options = sorted(df_월_누적["주차"].unique().tolist()) if not df_월_누적.empty else []
            월내주차_라벨_map = {}
            for w in 월내주차_options:
                라벨 = _월내_주차_라벨(w, 선택월)
                월내주차_라벨_map[w] = 라벨

            주차_표시 = [월내주차_라벨_map.get(w, w) for w in 월내주차_options]
            라벨_to_iso = {v: k for k, v in 월내주차_라벨_map.items()}

            현재주차 = date.today().strftime("%Y-W%V")
            기본주차_idx = (
                월내주차_options.index(현재주차)
                if 현재주차 in 월내주차_options
                else max(len(월내주차_options)-1, 0)
            )

            if 주차_표시:
                선택주차_라벨 = st.selectbox(
                    "기준 주차 (해당 월)", 주차_표시,
                    index=기본주차_idx, key="kpi2_주차"
                )
                선택주차 = 라벨_to_iso.get(선택주차_라벨)
            else:
                st.caption("해당 월 주간 데이터 없음")
                선택주차 = None
                선택주차_라벨 = ""

        st.markdown("---")
        if st.button("🔍 상세 현황 보기", key="kpi2_상세_btn", use_container_width=True):
            st.session_state["kpi2_page"] = "detail"
            st.rerun()

    # ── 반 필터 ──────────────────────────────────────────
    df_월간_f = df_월간[df_월간["반_표시"] == 선택반].copy() if 선택반 != "전체" else df_월간.copy()
    df_누적_f = df_누적[df_누적["반_표시"] == 선택반].copy() if 선택반 != "전체" else df_누적.copy()

    # ★ 연간누적: 반 선택시 해당 그룹만 표시
    if 선택반 != "전체" and not df_연간누적.empty:
        해당그룹 = 반_그룹매핑.get(선택반)
        df_연간_f = df_연간누적[df_연간누적["그룹"] == 해당그룹].copy() if 해당그룹 else df_연간누적.copy()
    else:
        df_연간_f = df_연간누적.copy()

    # ── ① 이달 BEP 현황 카드 ────────────────────────────
    if 보기모드 == "주간" and 선택주차:
        from data.kpi_2_data import _주차_날짜범위
        _주차시작, _주차종료 = _주차_날짜범위(선택주차, 선택월)
        df_이달 = df_월간[df_월간["월"] == 선택월].copy()
        카드데이터 = _calc_그룹데이터(df_이달, 선택반, 선택월,
                                      df_기초=df_기초, 주차_종료일=_주차종료)
        st.html(_html_그룹카드(카드데이터, f"{선택월} ({선택주차_라벨})"))
    else:
        df_이달 = df_월간[df_월간["월"] == 선택월].copy()
        # ★ ms_전망 미리 로드 (카드 + 반별달성현황 공유)
        현재급여월 = _급여월(date.today())
        _ms_전망_dict = None
        if 선택월 >= 현재급여월:
            try:
                df_ms_raw = agg_월말전망(df_기초, 선택월, 선택연도)
                if not df_ms_raw.empty:
                    _ms_전망_dict = {r["반_표시"]: float(r.get("전망잔여기성", 0) or 0)
                                     for _, r in df_ms_raw.iterrows()}
            except Exception:
                _ms_전망_dict = None
        카드데이터 = _calc_그룹데이터(df_이달, 선택반, 선택월,
                                      df_기초=df_기초, 주차_종료일=None, ms_전망=_ms_전망_dict)
        st.html(_html_그룹카드(카드데이터, 선택월))

    # ── ② ★ 연간 누적 달성현황 카드 ─────────────────────
    st.html(_html_연간누적카드(df_연간_f, 선택월, 선택연도))

    # ── ③ 차트 + 하단 테이블 ─────────────────────────────
    if 보기모드 == "월간":

        # ★ 연간 누적 BEP 추이 차트 (변경)
        st.html("<div class='section-title'>📈 연간 누적 BEP 추이 (그룹별)</div>")
        if df_연간_f is not None and not df_연간_f.empty:
            st.plotly_chart(
                _chart_연간누적_추이(
                    df_연간_f, 선택월,
                    f"연간 누적 BEP 실적 vs 목표 ({선택연도}년 | {_월라벨(선택월)}까지)"
                ),
                use_container_width=True,
            )
        else:
            st.html(
                "<div class='neo-card' style='text-align:center; color:#64748B; padding:2rem;'>"
                "연간 누적 데이터 없음</div>"
            )

        # 반별 달성현황 테이블
        st.html("<div style='height:0.5rem;'></div>")
        st.html(f"<div class='section-title'>📋 반별 달성 현황 ({선택월})</div>")

        df_ms_전망 = None
        if _ms_전망_dict:
            df_ms_전망 = pd.DataFrame([
                {"반_표시": k, "전망기성": v} for k, v in _ms_전망_dict.items()
            ])

        st.html(
            "<div class='neo-card' style='padding:1rem;'>"
            + _table_반별(df_월간, 선택월, 선택반, df_ms_전망) + "</div>"
        )

    else:
        # 주간 모드
        df_누적_필터 = df_누적_f.copy()
        if 선택주차:
            df_누적_필터 = df_누적_필터[df_누적_필터["주차"] <= 선택주차]
        df_누적_필터 = df_누적_필터[df_누적_필터["월"] == 선택월]

        st.html(f"<div class='section-title'>📈 주간 누적 BEP ({선택월})</div>")
        if not df_누적_필터.empty:
            st.plotly_chart(
                _chart_주간_추이(df_누적_필터, 선택월, f"주간 누적 BEP ({선택월})"),
                use_container_width=True,
            )
        else:
            st.html(
                "<div class='neo-card' style='text-align:center; color:#64748B; padding:2rem;'>"
                "해당 월 데이터 없음</div>"
            )

        # ★ 주간도 동일 소스 전망 사용
        df_ms_전망_주간 = None
        현재급여월 = _급여월(date.today())
        if 선택월 >= 현재급여월:
            try:
                df_ms_raw = agg_월말전망(df_기초, 선택월, 선택연도)
                if not df_ms_raw.empty:
                    df_ms_전망_주간 = df_ms_raw[["반_표시","전망잔여기성"]].rename(
                        columns={"전망잔여기성":"전망기성"}
                    )
            except Exception:
                df_ms_전망_주간 = None

        주차제목 = f"{선택월} | {선택주차_라벨}까지" if 선택주차_라벨 else 선택월
        st.html("<div style='height:0.5rem;'></div>")
        st.html(f"<div class='section-title'>📋 주간 누적 BEP 상세 ({주차제목})</div>")
        st.html(
            "<div class='neo-card' style='padding:1rem;'>"
            + _table_주간_누적(df_누적_f, 선택월, 선택주차, 선택반, df_ms_전망_주간, df_기초) + "</div>"
        )



# ══════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════
# 상세 현황 페이지
# ══════════════════════════════════════════════════════════

def _render_상세(선택연도: int):
    """날짜별 × 반별 기성/급여 상세 + 합계 BEP"""

    반_색상_map = {
        "취부반": "#38BDF8", "곡직반": "#10B981",
        "설치1직2반": "#F59E0B", "전장1직3반": "#A78BFA",
    }

    if st.button("← 뒤로가기", key="kpi2_상세_back"):
        st.session_state["kpi2_page"] = "main"
        st.rerun()

    st.markdown(
        "<div class='section-title' style='font-size:1.2rem;'>"
        "🔍 날짜별 급여·기성 상세 현황</div>",
        unsafe_allow_html=True,
    )

    # ── 사이드바 필터 ──
    with st.sidebar:
        st.markdown(
            "<div style='color:#38BDF8; font-weight:700; font-size:0.9rem; "
            "margin-bottom:0.5rem;'>🔎 상세 조회 조건</div>",
            unsafe_allow_html=True,
        )
        월_options = ["전체"] + [f"{선택연도}-{m:02d}" for m in range(1, 13)]
        현재급여월 = _급여월(date.today())
        기본월_idx = 월_options.index(현재급여월) if 현재급여월 in 월_options else 1
        상세_월 = st.selectbox("기준 월 (급여월)", 월_options,
                                index=기본월_idx, key="kpi2_상세_월")
        상세_그룹 = st.selectbox("그룹", ["전체", "1그룹", "2그룹"],
                                  key="kpi2_상세_그룹")
        if 상세_그룹 == "1그룹":
            반_pool = ["전체", "취부반", "곡직반"]
        elif 상세_그룹 == "2그룹":
            반_pool = ["전체", "설치1직2반", "전장1직3반"]
        else:
            반_pool = ["전체"] + list(반_표시명.values())
        상세_반 = st.selectbox("반", 반_pool, key="kpi2_상세_반")

        st.markdown("---")
        st.markdown(
            "<div style='color:#A78BFA; font-size:0.82rem; font-weight:600; "
            "margin-bottom:0.4rem;'>📅 날짜 범위 필터</div>",
            unsafe_allow_html=True,
        )
        # 기준 월이 전체면 연간 전체 범위, 특정 월이면 해당 월 범위
        if 상세_월 == "전체":
            _전체시작 = date(선택연도-1, 12, 11)
            _전체종료 = date(선택연도, 12, 10)
            _날짜기본시작 = _전체시작
            _날짜기본종료 = min(date.today(), _전체종료)
        else:
            try:
                _yr, _mo = int(상세_월[:4]), int(상세_월[5:7])
                _전체시작 = date(_yr-1, 12, 11) if _mo == 1 else date(_yr, _mo-1, 11)
                _전체종료 = date(_yr, _mo, 10)
                _날짜기본시작 = _전체시작
                _날짜기본종료 = _전체종료
            except Exception:
                _전체시작 = date.today().replace(day=1)
                _전체종료 = date.today()
                _날짜기본시작 = _전체시작
                _날짜기본종료 = _전체종료

        # ★ 기준 월이 바뀌면 날짜 범위 session_state 초기화
        _prev_월_key = "kpi2_상세_이전월"
        if st.session_state.get(_prev_월_key) != 상세_월:
            st.session_state["kpi2_상세_날짜시작"] = _날짜기본시작
            st.session_state["kpi2_상세_날짜종료"] = _날짜기본종료
            st.session_state[_prev_월_key] = 상세_월

        날짜_시작 = st.date_input("시작일",
                                   min_value=date(선택연도-1, 12, 11),
                                   max_value=date(선택연도, 12, 10),
                                   key="kpi2_상세_날짜시작")
        날짜_종료 = st.date_input("종료일",
                                   min_value=date(선택연도-1, 12, 11),
                                   max_value=date(선택연도, 12, 10),
                                   key="kpi2_상세_날짜종료")

    # ── 데이터 로드 ──
    _로드_월 = None if 상세_월 == "전체" else 상세_월
    with st.spinner("데이터 로딩 중..."):
        result = load_상세_일별(_로드_월, 선택연도)

    # ── 🔍 급여그룹별 시급 디버그 (취부/곡직 비교용) ──
    with st.expander("🔍 급여정보 확인 (취부/곡직 시급 비교)", expanded=False):
        from data.kpi_2_data import load_급여정보, load_인원정보
        df_급여_dbg = load_급여정보()
        df_인원_dbg = load_인원정보()
        st.markdown("**howon_global_급여정보 전체:**")
        st.dataframe(df_급여_dbg, hide_index=True)
        st.markdown("**반별 인원 급여그룹 현황:**")
        for 반전체명, 반표시 in 반_표시명.items():
            df_반_dbg = df_인원_dbg[df_인원_dbg["부서"] == 반전체명][["사번","급여그룹","퇴사일"]]
            st.markdown(f"**{반표시}** ({len(df_반_dbg)}명)")
            df_merged = df_반_dbg.merge(df_급여_dbg[["그룹","시급","잔업시급","월급여"]],
                                         left_on="급여그룹", right_on="그룹", how="left")
            st.dataframe(df_merged, hide_index=True)

    if result is None or len(result) != 2:
        st.warning("데이터가 없습니다.")
        return
    df_일별_전체, df_합계_원본 = result # ← df_합계를 버리지 않음

    if df_일별_전체 is None or df_일별_전체.empty:
        st.info("데이터가 없습니다.")
        return

    # ── 반 필터 ──
    if 상세_반 != "전체":
        df_일별_전체 = df_일별_전체[df_일별_전체["반_표시"] == 상세_반].copy()
        df_합계_원본 = df_합계_원본[df_합계_원본["반_표시"] == 상세_반].copy() if not df_합계_원본.empty else df_합계_원본
    elif 상세_그룹 != "전체":
        반_in_그룹 = [v for k, v in 반_표시명.items()
                      if 반_그룹매핑.get(v) == 상세_그룹]
        df_일별_전체 = df_일별_전체[df_일별_전체["반_표시"].isin(반_in_그룹)].copy()
        df_합계_원본 = df_합계_원본[df_합계_원본["반_표시"].isin(반_in_그룹)].copy() if not df_합계_원본.empty else df_합계_원본

    if df_일별_전체.empty:
        st.info("조건에 맞는 데이터가 없습니다.")
        return

    # ── 날짜 필터 (표시용) ──
    df_일별 = df_일별_전체[
        (df_일별_전체["날짜"] >= 날짜_시작) &
        (df_일별_전체["날짜"] <= 날짜_종료)
    ].copy()

    if df_일별.empty:
        st.info("선택 날짜 범위에 데이터가 없습니다.")
        return

    반_list = [r for r in 반_표시순서 if r in df_일별["반_표시"].unique()]
    모든날짜 = sorted(df_일별["날짜"].unique())
    오늘 = date.today()

    # ── 합계: load_상세_일별 결과를 그대로 사용 (중복 계산 제거) ──
    # df_합계_원본은 급여월 기준 합계이므로, 날짜 필터 기간 기준 재계산
    # 날짜 필터된 df_일별에서 직접 집계
    from data.kpi_2_data import load_직종단가, load_목표BEP, _급여보정, _to_date_safe, load_인원정보, load_급여정보
    반_단가 = load_직종단가()
    df_목표 = load_목표BEP(선택연도)
    df_인원_합계 = load_인원정보()
    df_급여_합계 = load_급여정보()
    급여_dict_합계 = df_급여_합계.set_index("그룹")[["월급여","복리후생비용"]].to_dict("index")
    팀목표_dict = {}
    if not df_목표.empty:
        for _, r in df_목표[df_목표["구분"] == "TEAM"].iterrows():
            팀목표_dict[(r["그룹코드"], r["월_str"])] = float(r["목표BEP"])
    필터일수 = (날짜_종료 - 날짜_시작).days + 1

    합계_rows = []
    for 반전체명, 반표시 in 반_표시명.items():
        if 반표시 not in 반_list: continue
        df_반 = df_일별[df_일별["반_표시"] == 반표시]
        if df_반.empty: continue

        기성합계 = float(df_반["기성합계"].sum())
        기성_58합 = float(df_반["기성_58"].sum())
        기성_실적 = float(df_반["기성"].sum())
        기본급합계 = float(df_반["기본급"].sum())
        특잔업합계 = float(df_반["특잔업비"].sum())
        복리후생합계 = float(df_반["복리후생"].sum()) if "복리후생" in df_반.columns else 0.0

        # 보정: 마지막날 재직인원 기본급+복리후생 일할
        df_반인원 = df_인원_합계[df_인원_합계["부서"] == 반전체명]
        마지막날_일기본급 = 0.0
        마지막날_일복리 = 0.0
        for _, p in df_반인원.iterrows():
            g = str(p.get("급여그룹","") or "").strip()
            if not g or g not in 급여_dict_합계: continue
            퇴사일 = p.get("퇴사일")
            배치일_d = _to_date_safe(p.get("배치일_고정"))
            급여제외 = p.get("급여제외")
            if 퇴사일 is not None and 날짜_종료 >= 퇴사일: continue
            if 배치일_d is not None and 날짜_종료 < 배치일_d: continue
            if 급여제외 is not None and 날짜_종료 <= 급여제외: continue
            마지막날_일기본급 += float(급여_dict_합계[g].get("월급여", 0) or 0) / 30
            마지막날_일복리 += float(급여_dict_합계[g].get("복리후생비용", 0) or 0) / 30

        보정일수 = 필터일수 - 30
        기본급보정 = -보정일수 * 마지막날_일기본급
        복리후생보정 = -보정일수 * 마지막날_일복리
        보정급여 = 기본급보정 + 복리후생보정
        급여합계_보정 = 기본급합계 + 특잔업합계 + 복리후생합계 + 보정급여

        단가 = float(반_단가.get(반전체명, 0) or 0)
        목표BEP = float(팀목표_dict.get((반표시, 상세_월), 1.0) or 1.0)
        BEP = (기성합계 * 단가) / 급여합계_보정 if 급여합계_보정 > 0 and 단가 > 0 else 0.0
        목표기성 = (급여합계_보정 * 목표BEP) / 단가 if 단가 > 0 else 0.0

        합계_rows.append({
            "반_표시": 반표시,
            "기성합계": round(기성합계, 1),
            "기성_58합": round(기성_58합, 1),
            "기성_실적": round(기성_실적, 1),
            "기본급합계": round(기본급합계, 0),
            "특잔업합계": round(특잔업합계, 0),
            "복리후생합계": round(복리후생합계, 0),
            "기본급보정": round(기본급보정, 0),
            "복리후생보정": round(복리후생보정, 0),
            "보정급여": round(보정급여, 0),
            "급여합계_보정": round(급여합계_보정, 0),
            "BEP": round(BEP, 3),
            "목표BEP": round(목표BEP, 3),
            "부족초과MH": round(기성합계 - 목표기성, 1),
        })

    df_합계 = pd.DataFrame(합계_rows)

    # ── 헤더 구성 (BEP/부족MH 제거) ──
    th = ("padding:0.42rem 0.6rem; font-size:0.70rem; color:#38BDF8; font-weight:600; "
          "text-align:center; background:rgba(56,189,248,0.08); "
          "border-bottom:2px solid rgba(56,189,248,0.2); white-space:nowrap;")
    th_l = th.replace("text-align:center", "text-align:left")

    반_headers = ""
    for 반 in 반_list:
        c = 반_색상_map.get(반, "#94A3B8")
        반_headers += (
            f"<th style='{th} color:{c};'>{반}<br><span style='font-weight:400;font-size:0.63rem;'>기성</span></th>"
            f"<th style='{th} color:{c};'>{반}<br><span style='font-weight:400;font-size:0.63rem;'>58기성</span></th>"
            f"<th style='{th} color:{c};'>{반}<br><span style='font-weight:400;font-size:0.63rem;'>기성합계</span></th>"
            f"<th style='{th} color:{c};'>{반}<br><span style='font-weight:400;font-size:0.63rem;'>기본급</span></th>"
            f"<th style='{th} color:{c};'>{반}<br><span style='font-weight:400;font-size:0.63rem;'>특/잔업비</span></th>"
            f"<th style='{th} color:{c};'>{반}<br><span style='font-weight:400;font-size:0.63rem;'>복리후생</span></th>"
            f"<th style='{th} color:{c};'>{반}<br><span style='font-weight:400;font-size:0.63rem;'>급여합계</span></th>"
            f"<th style='{th} color:{c};'>{반}<br><span style='font-weight:400;font-size:0.63rem;'>실투</span></th>"
            f"<th style='{th} color:{c};'>{반}<br><span style='font-weight:400;font-size:0.63rem;'>제외실투</span></th>"
        )

    thead = (
        f"<th style='{th_l}'>날짜</th>"
        f"<th style='{th}'>구분</th>"
        + 반_headers
    )

    # ── 날짜별 행 ──
    요일_map = {0: "월", 1: "화", 2: "수", 3: "목", 4: "금", 5: "토", 6: "일"}
    tbody = ""
    for 날짜 in 모든날짜:
        df_날짜 = df_일별[df_일별["날짜"] == 날짜]
        구분 = df_날짜["구분"].iloc[0] if not df_날짜.empty else "실적"
        is_전망 = (구분 == "전망")
        is_오늘 = (날짜 == 오늘)
        is_휴일 = bool(df_날짜["휴일"].iloc[0]) if not df_날짜.empty else False

        요일 = 요일_map[날짜.weekday()]
        is_주말 = 날짜.weekday() >= 5
        if is_휴일 and not is_주말:
            날짜_표시 = f"{날짜} <span style='color:#EF4444; font-size:0.7rem;'>(휴일)</span>"
        elif is_주말:
            주말_c = "#EF4444" if 날짜.weekday() == 6 else "#F59E0B"
            날짜_표시 = f"{날짜} <span style='color:{주말_c}; font-size:0.7rem;'>({요일})</span>"
        else:
            날짜_표시 = f"{날짜} <span style='color:#64748B; font-size:0.7rem;'>({요일})</span>"

        구분_c = "#F59E0B" if is_전망 else "#64748B"
        구분_lbl = "전망" if is_전망 else "실적"

        if is_오늘: bg = "rgba(56,189,248,0.06)"
        elif is_휴일: bg = "rgba(239,68,68,0.03)"
        elif is_전망: bg = "rgba(245,158,11,0.03)"
        else: bg = "transparent"

        td = (f"padding:0.35rem 0.55rem; font-size:0.77rem; background:{bg}; "
              "border-bottom:1px solid rgba(255,255,255,0.03);")

        row = (
            f"<tr>"
            f"<td style='{td} color:#CBD5E1; white-space:nowrap;'>"
            f"{'<b>' if is_오늘 else ''}{날짜_표시}{'</b>' if is_오늘 else ''}</td>"
            f"<td style='{td} text-align:center; color:{구분_c}; font-size:0.72rem;'>{구분_lbl}</td>"
        )
        for 반 in 반_list:
            c = 반_색상_map.get(반, "#94A3B8")
            df_반날 = df_날짜[df_날짜["반_표시"] == 반]
            기성_v = float(df_반날["기성"].sum()) if not df_반날.empty else 0.0
            기성58_v = float(df_반날["기성_58"].sum()) if not df_반날.empty else 0.0
            기성합_v = float(df_반날["기성합계"].sum()) if not df_반날.empty else 0.0
            특잔_v = float(df_반날["특잔업비"].sum()) if not df_반날.empty else 0.0
            기본_v = float(df_반날["기본급"].sum()) if not df_반날.empty else 0.0
            복리_v = float(df_반날["복리후생"].sum()) if not df_반날.empty and "복리후생" in df_반날.columns else 0.0
            급여_v = float(df_반날["급여합계"].sum()) if not df_반날.empty else 0.0
            실투_v = float(df_반날["실투"].sum()) if not df_반날.empty else 0.0
            제외_v = float(df_반날["제외실투"].sum()) if not df_반날.empty else 0.0

            def _n(v, fmt=",.1f"):
                try:
                    fv = float(v)
                except Exception:
                    return "—"
                if fv == 0:
                    return "—"
                return f"{fv:{fmt}}"

            row += (
                f"<td style='{td} text-align:right; color:{c};'>{_n(기성_v)}</td>"
                f"<td style='{td} text-align:right; color:#A78BFA;'>{_n(기성58_v)}</td>"
                f"<td style='{td} text-align:right; color:{c}; font-weight:{'700' if 기성합_v != 0 else '400'};'>{_n(기성합_v)}</td>"
                f"<td style='{td} text-align:right; color:#94A3B8;'>{int(기본_v):,}</td>"
                f"<td style='{td} text-align:right; color:#F59E0B;'>{_n(특잔_v, ',.0f') if 특잔_v>0 else '—'}</td>"
                f"<td style='{td} text-align:right; color:#6EE7B7;'>{_n(복리_v, ',.0f') if 복리_v>0 else '—'}</td>"
                f"<td style='{td} text-align:right; color:#CBD5E1;'>{int(급여_v):,}</td>"
                f"<td style='{td} text-align:right; color:#38BDF8;'>{_n(실투_v)}</td>"
                f"<td style='{td} text-align:right; color:#64748B;'>{_n(제외_v)}</td>"
            )
        row += "</tr>"
        tbody += row

    # ── 합계 행 (BEP/부족MH 없이) ──
    th_s = ("padding:0.48rem 0.55rem; font-size:0.76rem; font-weight:700; "
            "background:rgba(56,189,248,0.12); border-top:2px solid rgba(56,189,248,0.3);")

    합계행 = (
        f"<tr>"
        f"<td style='{th_s} text-align:left; color:#38BDF8;'>합계</td>"
        f"<td style='{th_s}'></td>"
    )
    for 반 in 반_list:
        c = 반_색상_map.get(반, "#94A3B8")
        df_반합 = df_합계[df_합계["반_표시"] == 반]
        if df_반합.empty:
            합계행 += f"<td style='{th_s}' colspan='9'>—</td>"
            continue
        r = df_반합.iloc[0]
        기성합 = float(r["기성합계"])
        기성58합 = float(r["기성_58합"])
        기성실적 = float(r["기성_실적"])
        기본합 = float(r["기본급합계"])
        특잔합 = float(r["특잔업합계"])
        복리합 = float(r.get("복리후생합계", 0) or 0)
        기본급보정 = float(r.get("기본급보정", 0) or 0)
        복리보정 = float(r.get("복리후생보정", 0) or 0)
        급여보정 = float(r["급여합계_보정"])
        기본보정_str = ("−" if 기본급보정 < 0 else "+") + f"{abs(int(기본급보정)):,}"
        복리보정_str = ("−" if 복리보정 < 0 else "+") + f"{abs(int(복리보정)):,}"
        df_반일별 = df_일별[(df_일별["반_표시"] == 반) & (df_일별["구분"] == "실적")]
        실투합 = float(df_반일별["실투"].sum()) if not df_반일별.empty and "실투" in df_반일별.columns else 0.0
        제외실투합 = float(df_반일별["제외실투"].sum()) if not df_반일별.empty and "제외실투" in df_반일별.columns else 0.0
        합계행 += (
            f"<td style='{th_s} text-align:right; color:{c};'>{기성실적:,.1f}</td>"
            f"<td style='{th_s} text-align:right; color:#A78BFA;'>{기성58합:,.1f}</td>"
            f"<td style='{th_s} text-align:right; color:{c};'>{기성합:,.1f}</td>"
            f"<td style='{th_s} text-align:right; color:#94A3B8;'>"
            f"{int(기본합):,}<br>"
            f"<span style='font-size:0.65rem;color:#64748B;'>보정{기본보정_str}</span></td>"
            f"<td style='{th_s} text-align:right; color:#F59E0B;'>{int(특잔합):,}</td>"
            f"<td style='{th_s} text-align:right; color:#6EE7B7;'>"
            f"{int(복리합):,}<br>"
            f"<span style='font-size:0.65rem;color:#64748B;'>보정{복리보정_str}</span></td>"
            f"<td style='{th_s} text-align:right; color:#10B981;'>{int(급여보정):,}</td>"
            f"<td style='{th_s} text-align:right; color:#38BDF8;'>{실투합:,.1f}</td>"
            f"<td style='{th_s} text-align:right; color:#64748B;'>{제외실투합:,.1f}</td>"
        )
    합계행 += "</tr>"

    st.html(
        "<div style='overflow-x:auto; background:rgba(15,23,42,0.6); "
        "border:1px solid rgba(255,255,255,0.07); border-radius:12px; overflow:hidden;'>"
        f"<table style='width:100%; border-collapse:collapse;'>"
        f"<thead><tr>{thead}</tr></thead>"
        f"<tbody>{tbody}{합계행}</tbody>"
        f"</table></div>"
    )

    # ══════════════════════════════════════════
    # ── 하단 지표 테이블: 기성 | 실투입 | 능률 | 실동률 | 효율 | BEP | 부족MH ──
    # ══════════════════════════════════════════
    st.markdown(
        "<div style='color:#A78BFA; font-weight:700; font-size:0.95rem; "
        "margin:1.2rem 0 0.5rem;'>📊 주요 지표</div>",
        unsafe_allow_html=True,
    )

    # 실투입: 필터 기간 raw MH 합계
    from data.kpi_2_data import load_raw, 반_표시명 as _반표시명
    df_raw_지표 = load_raw(선택연도)

    th2 = ("padding:0.45rem 0.7rem; font-size:0.75rem; font-weight:600; "
           "text-align:center; background:rgba(56,189,248,0.1); "
           "border-bottom:2px solid rgba(56,189,248,0.25); white-space:nowrap; color:#38BDF8;")
    th2_l = th2.replace("text-align:center", "text-align:left")
    td2_base = "padding:0.42rem 0.7rem; font-size:0.82rem; text-align:right; border-bottom:1px solid rgba(255,255,255,0.04);"

    thead2 = (
        f"<th style='{th2_l}'>반</th>"
        f"<th style='{th2}'>기성 (MH)</th>"
        f"<th style='{th2}'>실투입 (MH)</th>"
        f"<th style='{th2}'>능률</th>"
        f"<th style='{th2}'>실동률</th>"
        f"<th style='{th2}'>효율</th>"
        f"<th style='{th2}'>BEP</th>"
        f"<th style='{th2}'>부족/초과MH</th>"
    )

    # 목표 능률/실동률/효율 로드
    from data.kpi_2_data import _calc_반별_목표효율_내부
    df_효율목표 = _calc_반별_목표효율_내부(선택연도)

    tbody2 = ""
    for 반 in 반_list:
        c = 반_색상_map.get(반, "#94A3B8")
        df_반합 = df_합계[df_합계["반_표시"] == 반]
        if df_반합.empty: continue
        r = df_반합.iloc[0]

        기성합계 = float(r["기성합계"])
        급여보정 = float(r["급여합계_보정"])
        bep = float(r["BEP"])
        목표bep = float(r["목표BEP"])
        부족mh = float(r["부족초과MH"])
        bep_c = "#10B981" if bep >= 목표bep else "#EF4444"
        mh_c = "#10B981" if 부족mh >= 0 else "#EF4444"
        mh_str = ("+" if 부족mh >= 0 else "") + f"{부족mh:,.1f}"

        # 제외 OP코드 정의
        제외_코드 = {
            "12","47","55","58","59",
            "61","62","63","66","67","68","78",
            "70","71","72","73","74","75","76","77","79","7A","7B",
            "81","82","83","84","88","89","90","91","92","93","94",
            "95","96","97","98","99","9F"
        }
        직접_코드 = {"11","12","13"} # 직접공수: 11+12+13

        실투입 = 0.0 # 직접공수 (11+12+13)
        총발생시수_제외 = 0.0 # 전체 - 제외코드
        반전체명_지표 = None

        if not df_raw_지표.empty:
            반전체명_지표 = next((k for k,v in _반표시명.items() if v == 반), None)
            if 반전체명_지표:
                df_반f = df_raw_지표[
                    (df_raw_지표["소속부서명"] == 반전체명_지표) &
                    (df_raw_지표["작업일"] >= 날짜_시작) &
                    (df_raw_지표["작업일"] <= 날짜_종료)
                ].copy()
                if not df_반f.empty:
                    # 직접공수: 11+12+13
                    실투입 = float(df_반f[df_반f["OP코드"].isin(직접_코드)]["MH"].sum())
                    # 총발생시수(제외): 제외코드 빼고 합산
                    총발생시수_제외 = float(df_반f[~df_반f["OP코드"].isin(제외_코드)]["MH"].sum())

        능률 = round(기성합계 / 실투입, 3) if 실투입 > 0 else 0.0
        실동률 = round(실투입 / 총발생시수_제외, 3) if 총발생시수_제외 > 0 else 0.0
        효율 = round(능률 * 실동률, 3)

        # 목표 능률/실동률/효율 (해당 월 기준)
        목표능률 = 목표실동률 = 목표효율 = None
        if not df_효율목표.empty and 반전체명_지표:
            효율행 = df_효율목표[
                (df_효율목표["반"] == 반전체명_지표) &
                (df_효율목표["월"] == 상세_월)
            ]
            if not 효율행.empty:
                목표능률 = 효율행["목표능률"].iloc[0]
                목표실동률 = 효율행["목표실동률"].iloc[0]
                목표효율 = 효율행["목표효율"].iloc[0]

        def _목표_str(실적, 목표):
            실적_pct = 실적 * 100
            if 목표 is None or pd.isna(목표):
                return f"{실적_pct:.1f}%"
            목표_pct = 목표 * 100
            c_v = "#10B981" if 실적 >= 목표 else "#EF4444"
            return (f"<span style='color:{c_v};font-weight:700;'>{실적_pct:.1f}%</span>"
                    f"<br><span style='font-size:0.65rem;color:#64748B;'>목표 {목표_pct:.1f}%</span>")

        tbody2 += (
            f"<tr>"
            f"<td style='{td2_base} text-align:left; color:{c}; font-weight:700;'>{반}</td>"
            f"<td style='{td2_base} color:{c};'>{기성합계:,.1f}</td>"
            f"<td style='{td2_base} color:#94A3B8;'>{실투입:,.1f}</td>"
            f"<td style='{td2_base} color:#38BDF8;'>{_목표_str(능률, 목표능률)}</td>"
            f"<td style='{td2_base} color:#64748B;'>{_목표_str(실동률, 목표실동률)}</td>"
            f"<td style='{td2_base} color:#A78BFA;'>{_목표_str(효율, 목표효율)}</td>"
            f"<td style='{td2_base} color:{bep_c}; font-weight:700;'>"
            f"{bep:.3f}<br><span style='font-size:0.65rem;color:#64748B;'>목표 {목표bep:.3f}</span></td>"
            f"<td style='{td2_base} color:{mh_c}; font-weight:700;'>{mh_str}</td>"
            f"</tr>"
        )

    st.html(
        "<div style='overflow-x:auto; background:rgba(15,23,42,0.6); "
        "border:1px solid rgba(255,255,255,0.07); border-radius:12px; overflow:hidden; margin-top:0.5rem;'>"
        f"<table style='width:100%; border-collapse:collapse;'>"
        f"<thead><tr>{thead2}</tr></thead>"
        f"<tbody>{tbody2}</tbody>"
        f"</table></div>"
    )