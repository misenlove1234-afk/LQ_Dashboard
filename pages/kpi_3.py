"""
╔══════════════════════════════════════════════════════════════════╗
║  담당자 : ___________  (본인 이름 작성)                          ║
║  항목   : [화면 전용] kpi_3 - 정도율 / 인시당생산성 / 협력사BEP  ║
║  작성일 : ___________                                            ║
╚══════════════════════════════════════════════════════════════════╝

【 AI 바이브 코딩을 위한 프롬프트 가이드 】
"이 파일은 '화면 렌더링 전용' 파일이야.
1. DB 접속이나 무거운 데이터 연산은 절대 하지 마.
2. 데이터는 반드시 data.kpi_3_data 모듈을 import 해서 받아와.
3. 모든 UI 코드는 def render(): 함수 안에 작성해.
4. st.set_page_config() 는 쓰면 안 돼.
5. 위젯 key 값은 반드시 'kpi3_' 로 시작하게 해줘."
"""

from __future__ import annotations

import datetime
import os
import logging
import traceback
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import plotly.graph_objects as go

logger = logging.getLogger(__name__)
from data.kpi_3_data import (
    COMPANY_LIST,
    RADAR_METRICS,
    정도율_가중치,
    BEP_ITEMS,
    COMPANY_GOAL_GONGJON,
    mask_company,
    get_jeongdoyul_data,
    get_productivity_data,
    get_bep_data,
    get_labor_data,
    get_expense_data,
    get_labor_expense_data,
    get_partner_forecast,
    save_partner_forecast,
    get_forecast_deadline,
    is_forecast_input_open,
    forecast_table_exists,
)

# ── CSS (다크 네이비 테마) ─────────────────────────────────────────
_CSS = """
<style>
.stApp, [data-testid="stAppViewContainer"] {
    background-color: #0e1117 !important;
}
[data-testid="stSidebar"] {
    background-color: #161b2e !important;
    border-right: 1px solid #2a3050;
}
[data-testid="stSidebar"] * { color: #c8cfe0 !important; }
[data-testid="stMain"] { background-color: #0e1117 !important; }
[data-testid="stDataFrame"] { border-radius: 10px !important; overflow: hidden !important; }
.section-title {
    font-size: 13px; font-weight: 700; color: #8896b3;
    margin: 20px 0 10px 0; padding: 5px 12px;
    background: #161b2e; border-left: 3px solid #4a90d9;
    border-radius: 0 6px 6px 0; text-transform: uppercase;
    letter-spacing: 0.08em;
}
.legend-box {
    display: flex; gap: 20px; align-items: center;
    padding: 6px 14px; background: #161b2e;
    border-radius: 8px; border: 1px solid #2a3050;
    margin-bottom: 8px; width: fit-content;
}
.legend-item { display: flex; align-items: center; gap: 6px; font-size: 12px; color: #c8cfe0; }
.legend-line-dash { width: 28px; height: 2px; border-top: 2px dashed #4a90d9; }
.legend-line-solid { width: 28px; height: 2px; background: #00e096; }
</style>
"""

_BEP_인시당_항목: set[str] = {item for item in BEP_ITEMS if item.startswith('인시당')}

# 정도율 그래프 색상
_COLOR_FORECAST = "#4a90d9"   # 전망 (파란색)
_COLOR_ACTUAL   = "#00e096"   # 실적 (초록색)

# 기간별 배경 팔레트 (MultiIndex 테이블 색상) — 표시 순서와 동일
_PERIOD_PALETTES = [
    ("#0f2244", "#132a52"),   # 전망
    ("#0d2010", "#112614"),   # 실적합계 (진초록)
    ("#1a1232", "#1e173c"),   # 실적
    ("#0f2035", "#13253f"),   # 잔여기간전망
]

_DISPLAY_PERIODS_당월 = ["전망", "실적", "잔여기간전망", "실적합계"]
_DISPLAY_PERIODS_전월 = ["전망", "실적"]
_DISPLAY_PERIODS_익월 = ["전망"]
_DISPLAY_PERIODS = _DISPLAY_PERIODS_당월  # 하위 호환용
# 월별 배경 팔레트 (BEP 테이블)
_MONTH_PALETTES = [
    ("#0f2244", "#132a52"),   # 직전월
    ("#1a1232", "#1e173c"),   # 당월
    ("#0f2035", "#13253f"),   # 다음달
]
_FIXED_BG = "#0b1525"   # 고정 컬럼 배경
_TOTAL_BG = "#0a1520"   # 합계 행 배경


# ── 1. 정도율 방사형 그래프 ───────────────────────────────────────

def _draw_radar_charts(jeongdoyul: dict, tab_key: str = "") -> None:
    """
    협력사별 전망 정도율 방사형 그래프 5개를 1행으로 나란히 표시.
    tab_key: 탭별 위젯 key 중복 방지용 접두어 (예: "당월", "전월")
    """
    # 범례 (공통)
    st.markdown(
        "<div class='legend-box'>"
        "<div class='legend-item'><div class='legend-line-dash'></div>전망 (100% 기준)</div>"
        "<div class='legend-item'><div class='legend-line-solid'></div>실적 정도율</div>"
        "</div>",
        unsafe_allow_html=True,
    )

    cols = st.columns(5)
    # 방사형 닫기 위해 첫 번째 항목 반복 추가
    theta = RADAR_METRICS + [RADAR_METRICS[0]]

    for i, company in enumerate(COMPANY_LIST):
        data       = jeongdoyul[company]
        실적_vals  = data["실적"]   # 정도율 (대칭 공식 적용)
        비율_vals  = data["비율"]   # 실제 실적/전망 비율 (호버용)

        # 방사형 닫기: 마지막에 첫 항목 반복
        전망_r = data["전망"] + [data["전망"][0]]
        실적_r = 실적_vals + [실적_vals[0]]
        비율_r = 비율_vals + [비율_vals[0]]

        # 꼭짓점 텍스트: 정도율% 표기 (마지막 닫기 포인트는 빈 문자열)
        실적_text = [f"{v:.0f}%" for v in 실적_vals] + [""]

        # 마커 색상: 정도율 90% 이상=초록, 미만=빨강
        marker_colors = [
            "#00e096" if v >= 90 else "#ff5252"
            for v in (실적_vals + [실적_vals[0]])
        ]

        # 정도율 (제목 아래 표시) — 가중평균 (투입30/지출10/능률10/처리량25/단위물량당기성25)
        가중합  = sum(정도율_가중치[m] * v
                       for m, v in zip(RADAR_METRICS, 실적_vals)
                       if m in 정도율_가중치)
        가중치합 = sum(정도율_가중치[m]
                       for m in RADAR_METRICS
                       if m in 정도율_가중치)
        정도율_v   = round(가중합 / 가중치합, 1) if 가중치합 > 0 else 0.0
        avg_color  = "#00e096" if 정도율_v >= 90 else "#ff5252"

        # 호버 텍스트: 정도율 + 실제 비율 함께 표시
        hover_text = [
            f"<b>{m}</b><br>정도율: {d:.1f}%<br>(실적/전망: {r:.1f}%)"
            for m, d, r in zip(theta, 실적_r, 비율_r)
        ]

        fig = go.Figure()

        # 전망 기준선 (100%, 파란 점선) — 텍스트 없음
        fig.add_trace(go.Scatterpolar(
            r=전망_r,
            theta=theta,
            mode="lines",
            fill="toself",
            fillcolor="rgba(74,144,217,0.06)",
            line=dict(color=_COLOR_FORECAST, width=1.5, dash="dash"),
            showlegend=False,
            hoverinfo="skip",
        ))

        # 실적 정도율 (실선 + 마커 + 텍스트)
        fig.add_trace(go.Scatterpolar(
            r=실적_r,
            theta=theta,
            mode="lines+markers+text",
            fill="toself",
            fillcolor="rgba(0,224,150,0.12)",
            line=dict(color=_COLOR_ACTUAL, width=1.8),
            marker=dict(color=marker_colors, size=5),
            text=실적_text,
            textfont=dict(size=7, color="#e2e8f0"),
            textposition="top center",
            showlegend=False,
            hovertext=hover_text,
            hoverinfo="text",
        ))

        fig.update_layout(
            polar=dict(
                bgcolor="rgba(0,0,0,0)",
                # 방사형 영역을 아래로 내려 타이틀 공간 확보
                domain=dict(x=[0, 1], y=[0, 0.84]),
                radialaxis=dict(
                    visible=True,
                    range=[0, 115],
                    tickfont=dict(color="#8896b3", size=7),
                    gridcolor="#1e2a3a",
                    linecolor="#2e3a5a",
                    tickvals=[50, 100],
                    ticktext=["50%", "100%"],
                    showticklabels=True,
                ),
                angularaxis=dict(
                    direction="clockwise",
                    rotation=90,
                    tickfont=dict(color="#c8cfe0", size=9),
                    gridcolor="#1e2a3a",
                    linecolor="#2e3a5a",
                ),
            ),
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#c8cfe0"),
            title=dict(
                text=f"{mask_company(company)}<br><span style='font-size:10px;color:{avg_color};'>"
                     f"정도율 {정도율_v}%</span>",
                font=dict(size=11, color="#e2e8f0"),
                x=0.5,
                xanchor="center",
                y=0.97,
            ),
            showlegend=False,
            margin=dict(l=15, r=15, t=60, b=10),
            height=300,
        )

        with cols[i]:
            st.plotly_chart(fig, use_container_width=True, key=f"kpi3_radar_{tab_key}_{i}")


# ── 2. 인시당 생산성 테이블 ──────────────────────────────────────

def _make_productivity_mi(
    df: pd.DataFrame,
    display_periods: list[str] = _DISPLAY_PERIODS,
) -> pd.DataFrame:
    """
    인시당 생산성 DataFrame을 MultiIndex 컬럼 형태로 변환.
    display_periods: 표시할 기간 목록 (순서 포함)
    """
    mi_tuples = [("", "업체")]
    flat_cols = ["업체"]
    for period in display_periods:
        for metric in ["기성", "처리물량", "투입", "인시당생산성"]:
            mi_tuples.append((period, metric))
            flat_cols.append(f"{period}_{metric}")

    out = df[flat_cols].copy()
    # 업체 컬럼 마스킹 (합계 행은 mask_company에서 원본 반환되므로 영향 없음)
    out["업체"] = out["업체"].apply(mask_company)
    out.columns = pd.MultiIndex.from_tuples(mi_tuples)
    return out


def _style_productivity(
    df_mi: pd.DataFrame,
    display_periods: list[str] = _DISPLAY_PERIODS,
) -> pd.io.formats.style.Styler:
    """인시당 생산성 MultiIndex 테이블 스타일 적용"""
    # 기간 컬럼 → 팔레트 인덱스 매핑 (display_periods 순서와 동일)
    col_palette_idx: dict = {}
    for j, period in enumerate(display_periods):
        for metric in ["기성", "처리물량", "투입", "인시당생산성"]:
            col_palette_idx[(period, metric)] = j

    cell_styles = pd.DataFrame("", index=df_mi.index, columns=df_mi.columns)

    for i in range(len(df_mi)):
        is_합계 = str(df_mi.iloc[i, 0]) == "합계"
        for j_pos, col in enumerate(df_mi.columns):
            if j_pos == 0:  # 업체 컬럼
                style = f"background-color:{_FIXED_BG};color:#e2e8f0;font-weight:700;text-align:left;"
                if is_합계:
                    style += "border-top:2px solid #4a90d9;"
            elif is_합계:
                style = (
                    f"background-color:{_TOTAL_BG};color:#c8cfe0;"
                    "text-align:right;border-top:2px solid #4a90d9;font-weight:700;"
                )
            else:
                p_idx = col_palette_idx.get(col, 0)
                palette = _PERIOD_PALETTES[p_idx]
                bg = palette[i % 2]
                style = f"background-color:{bg};color:#c8cfe0;text-align:right;"

            # 인시당생산성 컬럼 강조 (하늘색)
            if isinstance(col, tuple) and col[1] == "인시당생산성":
                style += "color:#38bdf8;font-weight:600;"

            cell_styles.iloc[i, j_pos] = style

    # 포맷 딕셔너리
    fmt: dict = {}
    for period in display_periods:
        fmt[(period, "기성")]        = "{:,.0f}"
        fmt[(period, "처리물량")]    = "{:,.1f}"
        fmt[(period, "투입")]        = "{:,.1f}"
        fmt[(period, "인시당생산성")] = "{:.3f}"

    return (
        df_mi.style
        .apply(lambda _: cell_styles, axis=None)
        .format(fmt, na_rep="-")
        .set_table_styles([
            {"selector": "thead th", "props": [
                ("background-color", "#0a1525"),
                ("color", "#8896b3"),
                ("font-size", "10px"),
                ("padding", "6px 10px"),
                ("border-bottom", "2px solid #2e3a5a"),
                ("text-align", "center"),
            ]},
        ])
    )


# ── 3. 협력사 BEP 테이블 ─────────────────────────────────────────

# get_bep_data 반환 구조:
#   columns = ["항목", 전월label, 당월label, 익월label]
#   rows    = BEP_ITEMS (기성금/지출금/손익/인시당목표/인시당BEP/인시당실적)

_BEP_인시당_항목 = {"인시당(목표)", "인시당(BEP)", "인시당(실적)"}


def _make_bep_mi(df: pd.DataFrame, month_labels: list[str]) -> pd.DataFrame:
    """
    협력사 BEP DataFrame을 표시용 형태로 변환.
    get_bep_data 반환: columns = ["항목"] + month_labels
    행별 포맷:
      - 기성금/지출금/손익 → 천 단위 쉼표 정수 (예: 12,000,000)
      - 인시당(목표/BEP/실적) → 소수점 3자리 (예: 0.420)
    """
    flat_cols = ["항목"] + [lbl for lbl in month_labels if lbl in df.columns]
    out = df[flat_cols].copy()

    for lbl in month_labels:
        if lbl not in out.columns:
            continue
        for i, row in out.iterrows():
            항목명 = str(row["항목"])
            val = row[lbl]
            try:
                fval = float(val)
                if 항목명 in _BEP_인시당_항목:
                    out.at[i, lbl] = f"{fval:.3f}"
                else:
                    out.at[i, lbl] = f"{fval:,.0f}"
            except (ValueError, TypeError):
                out.at[i, lbl] = "-"

    return out


def _style_bep(df: pd.DataFrame, month_labels: list[str]) -> pd.io.formats.style.Styler:
    """협력사 BEP 테이블 스타일 적용"""
    cell_styles = pd.DataFrame("", index=df.index, columns=df.columns)
    항목_list = df["항목"].tolist()

    for i in range(len(df)):
        항목명 = str(항목_list[i])
        for j_pos, col in enumerate(df.columns):
            if col == "항목":
                style = (
                    f"background-color:{_FIXED_BG};color:#e2e8f0;"
                    "font-weight:700;text-align:left;"
                )
            else:
                try:
                    m_idx = month_labels.index(col)
                except ValueError:
                    m_idx = 0
                palette = _MONTH_PALETTES[min(m_idx, len(_MONTH_PALETTES) - 1)]
                bg = palette[i % 2]
                style = f"background-color:{bg};color:#c8cfe0;text-align:right;"

                if 항목명 in _BEP_인시당_항목:
                    style += "color:#38bdf8;font-weight:600;"
                elif 항목명 == "손익":
                    try:
                        clean = str(df.iloc[i, j_pos]).replace(",", "")
                        fval = float(clean)
                        color = "#00e096" if fval >= 0 else "#ff5252"
                        style += f"color:{color};font-weight:600;"
                    except Exception:
                        pass

            cell_styles.iloc[i, j_pos] = style

    return (
        df.style
        .apply(lambda _: cell_styles, axis=None)
        .set_table_styles([
            {"selector": "thead th", "props": [
                ("background-color", "#0a1525"),
                ("color", "#8896b3"),
                ("font-size", "10px"),
                ("padding", "6px 10px"),
                ("border-bottom", "2px solid #2e3a5a"),
                ("text-align", "center"),
            ]},
        ])
    )



def _style_labor(df_mi: pd.DataFrame) -> pd.io.formats.style.Styler:
    """인건비 MultiIndex 테이블 스타일 적용"""
    month_labels_mi = list(dict.fromkeys(c[0] for c in df_mi.columns if c[0]))
    col_palette_idx: dict = {}
    for j, lbl in enumerate(month_labels_mi):
        for sub in ["인원", "단가"]:
            col_palette_idx[(lbl, sub)] = j

    cell_styles = pd.DataFrame("", index=df_mi.index, columns=df_mi.columns)
    for i in range(len(df_mi)):
        for col in df_mi.columns:
            if col[0] == "":
                style = f"background-color:{_FIXED_BG};color:#e2e8f0;font-weight:700;text-align:left;"
            else:
                p_idx = col_palette_idx.get(col, 0)
                palette = _PERIOD_PALETTES[min(p_idx, len(_PERIOD_PALETTES) - 1)]
                bg = palette[i % 2]
                style = f"background-color:{bg};color:#c8cfe0;text-align:right;"
                if col[1] == "단가":
                    style += "color:#38bdf8;"
            cell_styles.at[i, col] = style

    fmt = {col: "{}" for col in df_mi.columns if col[0]}
    return (
        df_mi.style
        .apply(lambda _: cell_styles, axis=None)
        .format(fmt, na_rep="-")
        .set_table_styles([
            {"selector": "thead tr:first-child th", "props": [
                ("background-color", "#0a1525"), ("color", "#4a90d9"),
                ("font-size", "11px"), ("padding", "5px 10px"),
                ("border-bottom", "1px solid #2e3a5a"), ("text-align", "center"),
            ]},
            {"selector": "thead tr:last-child th", "props": [
                ("background-color", "#0a1525"), ("color", "#8896b3"),
                ("font-size", "10px"), ("padding", "4px 10px"),
                ("border-bottom", "2px solid #2e3a5a"), ("text-align", "center"),
            ]},
        ])
    )


def _render_expense_table(groups: list, month_labels: list) -> str:
    """지출금 상세 - 버튼 클릭으로 세부 행 토글"""
    th_cols = "".join(
        "<th style='text-align:right;padding:8px 14px;min-width:130px;'>" + lbl + "</th>"
        for lbl in month_labels
    )
    rows_html = ""
    for idx, grp in enumerate(groups):
        is_합계  = grp["group"] == "지출금 합계"
        has_det  = bool(grp["detail"])
        gid      = "g" + str(idx)

        m_cells = "".join(
            "<td style='text-align:right;padding:8px 14px;font-size:13px;font-weight:600;"
            + ("color:#4a90d9;" if is_합계 else "color:#e2e8f0;")
            + "'>" + grp["소계"].get(lbl, "-") + "</td>"
            for lbl in month_labels
        )

        if is_합계:
            rows_html += (
                "<tr style='background:#0d1e38;border-top:2px solid #4a90d9;"
                "border-bottom:2px solid #4a90d9;'>"
                "<td style='padding:8px 14px;color:#4a90d9;font-size:13px;"
                "font-weight:700;text-align:left;'>합 계</td>"
                + m_cells + "</tr>"
            )
        else:
            if has_det:
                btn = (
                    '<button onclick="toggleGrp(\'' + gid + '\')" '
                    'style="background:#1a3050;border:none;border-radius:4px;'
                    'color:#4a90d9;font-size:13px;width:22px;height:22px;'
                    'cursor:pointer;margin-right:8px;padding:0;'
                    'line-height:22px;text-align:center;" '
                    'id="btn_' + gid + '">&#9658;</button>'
                )
            else:
                btn = "<span style='display:inline-block;width:30px;'></span>"

            rows_html += (
                "<tr style='background:#0f2244;border-bottom:1px solid #1e3058;'>"
                "<td style='padding:8px 14px;text-align:left;"
                "color:#c8cfe0;font-size:12px;font-weight:600;'>"
                + btn + grp["group"] + "</td>"
                + m_cells + "</tr>"
            )
            for d_idx, detail in enumerate(grp["detail"]):
                bg = "#0b1a30" if d_idx % 2 == 0 else "#0d1e38"
                d_cells = "".join(
                    "<td style='text-align:right;padding:6px 14px;"
                    "color:#7a8faa;font-size:12px;'>"
                    + detail.get(lbl, "-") + "</td>"
                    for lbl in month_labels
                )
                rows_html += (
                    "<tr id='" + gid + "_" + str(d_idx) + "' "
                    "style='display:none;background:" + bg + ";"
                    "border-bottom:1px solid #162030;'>"
                    "<td style='padding:6px 14px 6px 42px;text-align:left;"
                    "color:#7a8faa;font-size:11px;'>"
                    + detail["항목"] + "</td>"
                    + d_cells + "</tr>"
                )

    # 세부 행 총 개수 (height 계산용)
    total_detail_rows = sum(len(g["detail"]) for g in groups)

    js = """
<script>
var counts = """ + str({str(i): len(g["detail"]) for i, g in enumerate(groups)}) + """;
function toggleGrp(id) {
    var idx = id.replace('g','');
    var cnt = counts[idx] || 0;
    var btn = document.getElementById('btn_' + id);
    var first = document.getElementById(id + '_0');
    var hidden = !first || first.style.display === 'none';
    for (var i = 0; i < cnt; i++) {
        var row = document.getElementById(id + '_' + i);
        if (row) row.style.display = hidden ? 'table-row' : 'none';
    }
    if (btn) {
        btn.innerHTML = hidden ? '&#9660;' : '&#9658;';
        btn.style.background = hidden ? '#1e4a7a' : '#1a3050';
    }
    // 부모 iframe 높이 조정
    var newH = document.body.scrollHeight + 20;
    window.frameElement && (window.frameElement.style.height = newH + 'px');
}
</script>
"""

    return (
        "<style>"
        "body{margin:0;padding:0;background:transparent;}"
        ".etbl{width:100%;border-collapse:collapse;}"
        ".etbl thead th{background:#091525;color:#6a7f9a;"
        "font-size:11px;font-weight:500;letter-spacing:0.06em;"
        "padding:8px 14px;border-bottom:2px solid #1e3058;}"
        ".etbl tbody tr:hover td{filter:brightness(1.15);}"
        "</style>"
        "<table class='etbl'><thead><tr>"
        "<th style='text-align:left;padding:8px 14px;min-width:180px;'>항목</th>"
        + th_cols +
        "</tr></thead><tbody>" + rows_html + "</tbody></table>"
        + js
    )



def _render_labor_expense_table(groups: list, month_labels: list) -> str:
    """인건비+지출금 통합 테이블 - 월별 인원/단가/소계 3열, 버튼 클릭시 세부 확장"""

    th_month = (
        "<th style='text-align:left;padding:8px 12px;min-width:160px;"
        "border-right:1px solid #1e3058;'>항목</th>"
    )
    for lbl in month_labels:
        th_month += (
            "<th colspan='3' style='text-align:center;padding:6px 8px;"
            "border-left:1px solid #1e3058;color:#4a90d9;'>" + lbl + "</th>"
        )

    th_sub = "<th style='border-right:1px solid #1e3058;'></th>"
    for _ in month_labels:
        for sub in ["인원", "단가", "소계"]:
            border = "border-right:1px solid #1e3058;" if sub == "소계" else ""
            th_sub += (
                "<th style='text-align:right;padding:5px 10px;font-size:10px;"
                "color:#6a7f9a;" + border + "'>" + sub + "</th>"
            )

    rows_html = ""
    counts = {}

    for idx, grp in enumerate(groups):
        gtype    = grp["type"]
        has_det  = bool(grp["detail"])
        gid      = "g" + str(idx)
        is_total = gtype == "total"
        is_single= gtype == "single"
        counts[idx] = len(grp["detail"])

        mcells = ""
        for lbl in month_labels:
            md = grp["months"].get(lbl, {})
            for sub in ["인원", "단가", "소계"]:
                val = md.get(sub, "")
                border = "border-right:1px solid #1e3058;" if sub == "소계" else ""
                if is_total and sub == "소계":
                    cs = "color:#4a90d9;font-weight:700;font-size:13px;" + border
                elif sub == "소계":
                    cs = "color:#e2e8f0;font-weight:600;" + border
                elif sub == "단가":
                    cs = "color:#38bdf8;" + border
                else:
                    cs = "color:#c8cfe0;" + border
                if is_single and sub != "인원":
                    val = ""
                mcells += (
                    "<td style='text-align:right;padding:7px 10px;" + cs + "'>"
                    + val + "</td>"
                )

        if has_det:
            # 버튼에 data-gid 속성 사용 → JS에서 addEventListener로 처리
            btn = (
                "<button data-gid='" + gid + "' "
                "class='tog-btn' "
                "style='background:#1a3050;border:none;border-radius:4px;"
                "color:#4a90d9;font-size:12px;width:20px;height:20px;"
                "cursor:pointer;margin-right:8px;padding:0;line-height:20px;"
                "text-align:center;' "
                "id='btn_" + gid + "'>&#9658;</button>"
            )
        else:
            btn = "<span style='display:inline-block;width:28px;'></span>"

        if is_total:
            tr_s  = "background:#0d1e38;border-top:2px solid #4a90d9;border-bottom:2px solid #4a90d9;"
            lbl_s = "color:#4a90d9;font-weight:700;font-size:13px;"
        elif is_single:
            tr_s  = "background:#111a2e;border-bottom:1px solid #1e3058;"
            lbl_s = "color:#8896b3;font-size:11px;"
        else:
            tr_s  = "background:#0f2244;border-bottom:1px solid #1e3058;"
            lbl_s = "color:#c8cfe0;font-weight:600;font-size:12px;"

        rows_html += (
            "<tr style='" + tr_s + "'>"
            "<td style='padding:7px 12px;text-align:left;" + lbl_s +
            "border-right:1px solid #1e3058;'>" + btn + grp["group"] + "</td>"
            + mcells + "</tr>"
        )

        for d_idx, det in enumerate(grp["detail"]):
            bg = "#0b1a30" if d_idx % 2 == 0 else "#0d1e38"
            dcells = ""
            for lbl in month_labels:
                val = det.get(lbl, "-")
                for sub in ["인원", "단가", "소계"]:
                    border = "border-right:1px solid #1e3058;" if sub == "소계" else ""
                    dcells += (
                        "<td style='text-align:right;padding:5px 10px;"
                        "color:#7a8faa;font-size:11px;" + border + "'>"
                        + (val if sub == "소계" else "") + "</td>"
                    )
            rows_html += (
                "<tr id='" + gid + "_" + str(d_idx) + "' "
                "style='display:none;background:" + bg + ";border-bottom:1px solid #162030;'>"
                "<td style='padding:5px 12px 5px 40px;text-align:left;"
                "color:#7a8faa;font-size:11px;border-right:1px solid #1e3058;'>"
                + det["항목"] + "</td>" + dcells + "</tr>"
            )

    counts_json = str(counts).replace("'", '"')

    js = (
        "<script>"
        "var COUNTS=" + counts_json + ";"
        "document.addEventListener('click',function(e){"
        "var btn=e.target.closest('.tog-btn');"
        "if(!btn)return;"
        "var gid=btn.getAttribute('data-gid');"
        "var idx=parseInt(gid.replace('g',''));"
        "var cnt=COUNTS[idx]||0;"
        "var first=document.getElementById(gid+'_0');"
        "var hidden=!first||first.style.display==='none';"
        "for(var i=0;i<cnt;i++){"
        "var r=document.getElementById(gid+'_'+i);"
        "if(r)r.style.display=hidden?'table-row':'none';}"
        "btn.innerHTML=hidden?'&#9660;':'&#9658;';"
        "btn.style.background=hidden?'#1e4a7a':'#1a3050';"
        "var h=document.body.scrollHeight+20;"
        "if(window.frameElement)window.frameElement.style.height=h+'px';});"
        "</script>"
    )

    return (
        "<style>"
        "body{margin:0;padding:0;background:transparent;}"
        ".letbl{width:100%;border-collapse:collapse;}"
        ".letbl thead tr:first-child th{background:#091525;font-size:11px;"
        "font-weight:600;letter-spacing:0.05em;padding:7px 8px;"
        "border-bottom:1px solid #2e3a5a;}"
        ".letbl thead tr:last-child th{background:#091525;padding:4px 8px;"
        "border-bottom:2px solid #2e3a5a;}"
        ".letbl tbody tr:hover td{filter:brightness(1.15);}"
        "</style>"
        "<table class='letbl'><thead>"
        "<tr>" + th_month + "</tr>"
        "<tr>" + th_sub   + "</tr>"
        "</thead><tbody>" + rows_html + "</tbody></table>"
        + js
    )


# ── 운영자 로그인 / 협력사 전망 입력 (lq_kpi3_8) ──────────────────

def _render_admin_login():
    """운영자 로그인 popover — 마감 후에도 수정 가능하게 하는 모드"""
    is_admin = bool(st.session_state.get("kpi3_admin", False))
    label = "🔓 운영자 모드" if is_admin else "🔐 운영자 로그인"
    with st.popover(label, use_container_width=False):
        if is_admin:
            st.success("운영자 모드 활성 — 마감 후에도 수정 가능")
            if st.button("로그아웃", key="kpi3_admin_logout"):
                st.session_state["kpi3_admin"] = False
                st.rerun()
        else:
            pw = st.text_input("관리자 비밀번호",
                               type="password",
                               key="kpi3_admin_pw_input",
                               placeholder="⚠️ 개인정보를 입력하지 마세요")
            if st.button("로그인", key="kpi3_admin_login_btn"):
                # .env 의 KPI3_ADMIN_PWD 가 있으면 그 값, 없으면 기본 "admin1234"
                admin_pw_env = os.environ.get("KPI3_ADMIN_PWD", "admin1234")
                if admin_pw_env and pw == admin_pw_env:
                    st.session_state["kpi3_admin"] = True
                    st.rerun()
                else:
                    st.error("비밀번호가 일치하지 않습니다.")


def _build_past_cumulative_table(year: int, curr_m: int) -> pd.DataFrame:
    """과거 누계 표 — 1월 ~ (curr_m-1) 의 협력사별 실적 + 누계.
    MultiIndex 컬럼: (월, metric)  metric = 기성 / 처리물량 / 투입 / 인시당생산성
    Rows: 5 협력사 (마스킹된 업체명).
    """
    if curr_m <= 1:
        return pd.DataFrame()

    rows = []
    for company in COMPANY_LIST:
        row_data: dict = {("", "업체"): mask_company(company)}
        sum_g = sum_m = sum_t = 0.0
        for m_ in range(1, curr_m):
            try:
                p = get_productivity_data(year_int=year, month_int=m_)
            except Exception:
                p = pd.DataFrame()
            if p is None or p.empty or "업체" not in p.columns:
                g = m_v = t_v = 0.0
            else:
                comp_row = p[p["업체"] == company]
                if comp_row.empty:
                    g = m_v = t_v = 0.0
                else:
                    g   = float(comp_row.iloc[0].get("실적_기성") or 0)
                    m_v = float(comp_row.iloc[0].get("실적_처리물량") or 0)
                    t_v = float(comp_row.iloc[0].get("실적_투입") or 0)
            i_v = (m_v / t_v) if t_v > 0 else 0.0
            row_data[(f"{m_}월", "기성")]         = g
            row_data[(f"{m_}월", "처리물량")]     = m_v
            row_data[(f"{m_}월", "투입")]         = t_v
            row_data[(f"{m_}월", "인시당생산성")] = i_v
            sum_g += g
            sum_m += m_v
            sum_t += t_v
        sum_i = (sum_m / sum_t) if sum_t > 0 else 0.0
        row_data[("누계", "기성")]         = sum_g
        row_data[("누계", "처리물량")]     = sum_m
        row_data[("누계", "투입")]         = sum_t
        row_data[("누계", "인시당생산성")] = sum_i
        rows.append(row_data)

    df = pd.DataFrame(rows)
    df.columns = pd.MultiIndex.from_tuples(list(df.columns))
    return df


def _style_past_cumulative(df_mi: pd.DataFrame, curr_m: int):
    """과거 누계 표 스타일 (Styler) — 누계 컬럼 강조"""
    fmt: dict = {("", "업체"): str}
    months = [f"{m_}월" for m_ in range(1, curr_m)] + ["누계"]
    for mlabel in months:
        fmt[(mlabel, "기성")]         = "{:,.0f}"
        fmt[(mlabel, "처리물량")]     = "{:,.1f}"
        fmt[(mlabel, "투입")]         = "{:,.0f}"
        fmt[(mlabel, "인시당생산성")] = "{:.3f}"

    cell_styles = pd.DataFrame("", index=df_mi.index, columns=df_mi.columns)
    for col in df_mi.columns:
        if col[0] == "" and col[1] == "업체":
            cell_styles[col] = (
                "background-color:#161b2e;color:#e2e8f0;font-weight:700;text-align:left;"
            )
        elif col[0] == "누계":
            cell_styles[col] = (
                "background-color:#1e2a3f;color:#7dd3fc;font-weight:700;text-align:right;"
            )
        elif col[1] == "인시당생산성":
            cell_styles[col] = (
                "background-color:#0f172a;color:#38bdf8;font-weight:600;text-align:right;"
            )
        else:
            cell_styles[col] = (
                "background-color:#0f172a;color:#c8cfe0;text-align:right;"
            )
    return (
        df_mi.style
        .apply(lambda _: cell_styles, axis=None)
        .format(fmt, na_rep="-")
        .set_table_styles([
            {"selector": "thead th", "props": [
                ("background-color", "#0a1525"),
                ("color", "#8896b3"),
                ("font-size", "11px"),
                ("padding", "6px 10px"),
                ("border-bottom", "2px solid #2e3a5a"),
                ("text-align", "center"),
            ]},
        ])
    )


def _merge_user_forecast_into_prod(prod_df: pd.DataFrame,
                                    year: int, month: int) -> pd.DataFrame:
    """get_productivity_data() 결과의 '전망_*' 컬럼을 lq_kpi3_8 사용자 입력값
    (구분=전망) 으로 덮어쓴다. 실적은 DB 값 그대로 유지.
    """
    if prod_df is None or prod_df.empty:
        return prod_df
    try:
        df_fc = get_partner_forecast(year, month, 구분="전망")
    except Exception:
        return prod_df
    if df_fc is None or df_fc.empty:
        return prod_df

    fc_dict = {row["협력사"]: row.to_dict() for _, row in df_fc.iterrows()}
    out = prod_df.copy()
    for idx in out.index:
        company = out.at[idx, "업체"] if "업체" in out.columns else None
        if not company or company not in fc_dict:
            continue
        u = fc_dict[company]
        g = float(u.get("기성") or 0)
        m = float(u.get("처리물량") or 0)
        t = float(u.get("투입") or 0)
        if "전망_기성"        in out.columns: out.at[idx, "전망_기성"]        = g
        if "전망_처리물량"    in out.columns: out.at[idx, "전망_처리물량"]    = m
        if "전망_투입"        in out.columns: out.at[idx, "전망_투입"]        = t
        if "전망_인시당생산성" in out.columns:
            out.at[idx, "전망_인시당생산성"] = (m / t) if t > 0 else 0.0
    return out


def _build_forecast_table(year: int, month: int,
                           existing_dict: dict,
                           saved_edits: dict | None = None) -> pd.DataFrame:
    """입력/조회 양쪽에서 쓰는 5행짜리 DataFrame 빌드.
    saved_edits 가 있으면 그 값을 우선 적용 (저장 실패 후 재렌더 시 편집 보존용).
    """
    saved_edits = saved_edits or {}
    rows = []
    for c in COMPANY_LIST:
        masked = mask_company(c)
        if masked in saved_edits:
            e = saved_edits[masked]
            g = float(e.get("기성") or 0)
            m = float(e.get("처리물량") or 0)
            t = float(e.get("투입") or 0)
        else:
            ex = existing_dict.get(c, {})
            g = float(ex.get("기성") or 0)
            m = float(ex.get("처리물량") or 0)
            t = float(ex.get("투입") or 0)
        rows.append({
            "업체": masked,
            "기성": g,
            "처리물량": m,
            "투입": t,
            "인시당생산성": (m / t) if t > 0 else 0.0,
        })
    return pd.DataFrame(rows)


def _render_forecast_input(year: int, month: int, return_tab_idx: int = 2,
                            구분: str = "전망"):
    """협력사 전망/실적 입력 폼.
    구분: '전망' 또는 '실적' — 같은 lq_kpi3_8 의 구분 컬럼 분리
    - 전망 + 마감 전: 누구나 편집 가능 (📝)
    - 전망 + 마감 후 + 운영자: 편집 가능 (✏️)
    - 전망 + 마감 후 + 일반: 읽기 전용 (🔒)
    - 실적: 항상 운영자만 편집 가능
    return_tab_idx: 저장 후 강제 활성화할 탭 인덱스
    """
    is_admin = bool(st.session_state.get("kpi3_admin", False))

    if 구분 == "실적":
        can_input = is_admin
        if is_admin:
            badge_color = "#A855F7"
            badge_text  = "✏️ 운영자 — 실적 직접 입력/수정 모드"
        else:
            badge_color = "#EF4444"
            badge_text  = "🔒 실적은 운영자만 입력 가능"
    else:  # 전망
        is_open  = is_forecast_input_open(year, month)
        can_input = is_open or is_admin
        if month == 1:
            prev_y, prev_m = year - 1, 12
        else:
            prev_y, prev_m = year, month - 1
        deadline = get_forecast_deadline(prev_y, prev_m)
        if is_open:
            badge_color = "#10B981"
            badge_text  = f"📝 전망 입력 가능 — 마감 {deadline.strftime('%Y-%m-%d')} 23:59"
        elif is_admin:
            badge_color = "#F59E0B"
            badge_text  = (
                "✏️ 운영자 — 전망 직접 수정 모드 "
                f"(원래 마감: {deadline.strftime('%Y-%m-%d')})"
            )
        else:
            badge_color = "#EF4444"
            badge_text  = f"🔒 전망 마감됨 (마감일: {deadline.strftime('%Y-%m-%d')})"

    st.markdown(
        f"<div style='font-size:12px;color:{badge_color};font-weight:700;"
        f"padding:6px 12px;background:#161b2e;border-radius:6px;"
        f"border-left:3px solid {badge_color};margin-bottom:10px;width:fit-content;'>"
        f"{badge_text}</div>",
        unsafe_allow_html=True,
    )

    # 기존 입력값 조회 + 편집 보존
    try:
        df_existing = get_partner_forecast(year, month, 구분=구분)
    except Exception:
        df_existing = pd.DataFrame()
    existing_dict: dict = {}
    if not df_existing.empty and "협력사" in df_existing.columns:
        existing_dict = {
            row["협력사"]: row.to_dict() for _, row in df_existing.iterrows()
        }
    saved_edits_key = f"kpi3_{구분}_edits_{year}_{month}"
    saved_edits = st.session_state.get(saved_edits_key, {})

    df_init = _build_forecast_table(year, month, existing_dict, saved_edits)
    _suffix = f"{year}_{month}_{구분}"
    _qibul_unit = "기성 (MH)"

    if can_input:
        # 편집 모드 — 인시당 생산성 표와 동일 양식 (st.data_editor)
        with st.form(f"kpi3_form_{_suffix}"):
            edited = st.data_editor(
                df_init,
                column_config={
                    "업체": st.column_config.TextColumn(
                        "업체", disabled=True, width="medium"),
                    "기성": st.column_config.NumberColumn(
                        _qibul_unit, min_value=0.0, step=10.0, format="%.1f"),
                    "처리물량": st.column_config.NumberColumn(
                        "처리물량", min_value=0.0, step=1.0, format="%.1f"),
                    "투입": st.column_config.NumberColumn(
                        "투입 (MH)", min_value=0.0, step=10.0, format="%.1f"),
                    "인시당생산성": st.column_config.NumberColumn(
                        "인시당생산성", disabled=True, format="%.3f",
                        help="처리물량 ÷ 투입 (저장 후 자동 계산)"),
                },
                hide_index=True,
                use_container_width=True,
                num_rows="fixed",
                key=f"kpi3_editor_{_suffix}",
            )

            st.markdown("<div style='height:6px;'></div>", unsafe_allow_html=True)
            name = st.text_input(
                "입력자 이름 (필수)", value="",
                placeholder="⚠️ 개인정보가 포함되지 않도록 주의하세요",
                key=f"kpi3_name_{_suffix}",
            )
            submitted = st.form_submit_button(
                f"💾 {구분} 일괄 저장", type="primary")

            if submitted:
                # 편집값 세션 백업 (실패 시 보존)
                st.session_state[saved_edits_key] = {
                    row["업체"]: {
                        "기성": float(row["기성"] or 0),
                        "처리물량": float(row["처리물량"] or 0),
                        "투입": float(row["투입"] or 0),
                    }
                    for _, row in edited.iterrows()
                }

                if not name.strip():
                    st.session_state["kpi3_save_msg"] = (
                        "error", "❌ 입력자 이름을 입력해주세요.")
                    st.session_state["kpi3_force_tab_idx"] = return_tab_idx
                    st.rerun()

                masked_to_orig = {mask_company(c): c for c in COMPANY_LIST}
                fail: list[tuple[str, str]] = []
                for _, row in edited.iterrows():
                    masked = row["업체"]
                    c = masked_to_orig.get(masked)
                    if c is None:
                        continue
                    try:
                        ok, err = save_partner_forecast(
                            c, year, month,
                            float(row["기성"] or 0),
                            float(row["처리물량"] or 0),
                            float(row["투입"] or 0),
                            name.strip(),
                            구분=구분,
                        )
                        if not ok:
                            fail.append((masked, err or "원인 미상"))
                    except Exception as e:
                        fail.append((masked, str(e)))

                if fail:
                    names = ", ".join(n for n, _ in fail)
                    reason = fail[0][1]
                    st.session_state["kpi3_save_msg"] = (
                        "error",
                        f"❌ {구분} 일부 저장 실패 ({names}) — {reason}",
                    )
                    st.session_state["kpi3_force_tab_idx"] = return_tab_idx
                    st.rerun()
                else:
                    st.session_state.pop(saved_edits_key, None)
                    st.session_state["kpi3_save_msg"] = (
                        "success",
                        f"✅ 모든 협력사 {구분}이 저장되었습니다.",
                    )
                    st.session_state["kpi3_force_tab_idx"] = return_tab_idx
                    st.rerun()
    else:
        # 읽기 전용 — Styler 정적 표
        st.dataframe(
            df_init.style.format({
                "기성": "{:,.1f}",
                "처리물량": "{:,.1f}",
                "투입": "{:,.1f}",
                "인시당생산성": "{:.3f}",
            }).set_table_styles([
                {"selector": "thead th", "props": [
                    ("background-color", "#0a1525"),
                    ("color", "#8896b3"),
                    ("font-size", "11px"),
                    ("padding", "6px 10px"),
                    ("border-bottom", "2px solid #2e3a5a"),
                    ("text-align", "center"),
                ]},
            ]),
            use_container_width=True,
            hide_index=True,
            key=f"kpi3_view_{_suffix}",
        )


def _render_forecast_display(year: int, month: int, title: str):
    """협력사 당월 전망 — 읽기 전용 표 (당월 탭 상단용)
    인시당 생산성 표와 동일한 양식 (st.dataframe + Styler)
    """
    try:
        df = get_partner_forecast(year, month)
    except Exception:
        return
    if df is None or df.empty:
        return
    existing_dict = {row["협력사"]: row.to_dict() for _, row in df.iterrows()}

    df_view = _build_forecast_table(year, month, existing_dict)

    st.markdown(f"<div class='section-title'>{title}</div>", unsafe_allow_html=True)
    st.dataframe(
        df_view.style.format({
            "기성": "{:,.1f}",
            "처리물량": "{:,.1f}",
            "투입": "{:,.1f}",
            "인시당생산성": "{:.3f}",
        }).set_table_styles([
            {"selector": "thead th", "props": [
                ("background-color", "#0a1525"),
                ("color", "#8896b3"),
                ("font-size", "11px"),
                ("padding", "6px 10px"),
                ("border-bottom", "2px solid #2e3a5a"),
                ("text-align", "center"),
            ]},
        ]),
        use_container_width=True,
        hide_index=True,
        key=f"kpi3_forecast_display_{year}_{month}",
    )


# ── 메인 렌더 함수 ────────────────────────────────────────────────

def render():
    """kpi_3 화면 렌더링: 정도율 / 인시당생산성 / 협력사 BEP"""
    st.markdown(_CSS, unsafe_allow_html=True)

    # 저장 결과 메시지 (모든 탭에서 보이도록 최상단)
    _save_msg = st.session_state.pop("kpi3_save_msg", None)
    if _save_msg:
        if _save_msg[0] == "error":
            st.error(_save_msg[1])
        else:
            st.success(_save_msg[1])

    # 강제 탭 전환 (저장 후 익월 탭 유지 등)
    _force_tab_idx = st.session_state.pop("kpi3_force_tab_idx", None)
    if _force_tab_idx is not None:
        components.html(
            f"""<script>setTimeout(function(){{
                var tabs=window.parent.document.querySelectorAll('[data-testid="stTab"]');
                if(tabs.length > {int(_force_tab_idx)}){{tabs[{int(_force_tab_idx)}].click();}}
            }},150);</script>""",
            height=0,
        )

    if "kpi3_selected_company" not in st.session_state:
        st.session_state["kpi3_selected_company"] = None
    selected_company: str | None = st.session_state["kpi3_selected_company"]

    try:
        jeongdoyul_당월 = get_jeongdoyul_data(month="당월")
        jeongdoyul_전월 = get_jeongdoyul_data(month="전월")
        jeongdoyul_익월 = get_jeongdoyul_data(month="익월")
        prod_df_당월    = get_productivity_data(month="당월")
        prod_df_전월    = get_productivity_data(month="전월")
        prod_df_익월    = get_productivity_data(month="익월")
    except Exception as e:
        logger.error("정도율 데이터 로드 실패: %s\n%s", e, traceback.format_exc())
        st.error("데이터 로드에 실패했습니다. 관리자에게 문의해 주세요.")
        return

    _today      = datetime.date.today()
    _curr_m     = _today.month
    _curr_y     = _today.year
    _prev_m     = _curr_m - 1 if _curr_m > 1 else 12
    _prev_y     = _curr_y if _curr_m > 1 else _curr_y - 1
    _next_m     = _curr_m + 1 if _curr_m < 12 else 1
    _next_y     = _curr_y if _curr_m < 12 else _curr_y + 1
    _label_전월 = f"{_prev_m}월"
    _label_당월 = f"{_curr_m}월"
    _label_익월 = f"{_next_m}월"

    # 인시당 생산성 표의 '전망_*' 컬럼을 사용자 입력값(lq_kpi3_8) 으로 덮어쓰기
    prod_df_전월 = _merge_user_forecast_into_prod(prod_df_전월, _prev_y, _prev_m)
    prod_df_당월 = _merge_user_forecast_into_prod(prod_df_당월, _curr_y, _curr_m)
    prod_df_익월 = _merge_user_forecast_into_prod(prod_df_익월, _next_y, _next_m)

    # 운영자 로그인 popover (마감 후에도 익월 입력 수정 가능)
    _login_col, _info_col = st.columns([1, 5])
    with _login_col:
        _render_admin_login()
    with _info_col:
        st.markdown(
            "<div style='color:#8896b3;font-size:11px;margin:8px 0 6px 2px;'>"
            "업체명 버튼을 클릭하면 해당 협력사의 BEP 데이터를 확인할 수 있습니다."
            "</div>",
            unsafe_allow_html=True,
        )

    # 첫 진입 시 당월(idx=1) 탭 자동 활성화
    if not st.session_state.get("kpi3_tab_init"):
        st.session_state["kpi3_tab_init"] = True
        components.html(
            """<script>setTimeout(function(){
            var tabs=window.parent.document.querySelectorAll('[data-testid="stTab"]');
            if(tabs.length>=2){tabs[1].click();}},300);</script>""",
            height=0,
        )

    # ── 3개 탭: 과거 누계 / 당월 / 차월 ───────────────────────────
    _is_admin_now = bool(st.session_state.get("kpi3_admin", False))
    _past_label = "📊 과거 누계 (1월~전월)" if _curr_m > 1 else "📊 과거 누계 (없음)"
    _curr_label = f"{_curr_m}월 (당월)"
    _next_label = f"{_next_m}월 (차월)"
    tab_past, tab_curr, tab_next = st.tabs([_past_label, _curr_label, _next_label])

    def _협력사_btns(month_key: str):
        """탭 내 협력사 선택 버튼 행 (key 충돌 방지)"""
        btn_cols = st.columns(len(COMPANY_LIST))
        for i, company in enumerate(COMPANY_LIST):
            with btn_cols[i]:
                is_sel = selected_company == company
                if st.button(mask_company(company),
                             key=f"kpi3_btn_{month_key}_{company}",
                             use_container_width=True,
                             type="primary" if is_sel else "secondary"):
                    st.session_state["kpi3_selected_company"] = (
                        None if is_sel else company
                    )
                    st.rerun()

    def _render_partner_bep(months_tuple: tuple, key_prefix: str):
        """선택된 협력사의 BEP / 인건비·지출금을 해당 월 범위로 렌더.
        months_tuple: ((year, month), ...) — 빈 튜플이면 표시 안 함."""
        if not months_tuple:
            return
        if not selected_company:
            st.markdown(
                "<div style='color:#8896b3;font-size:12px;margin-top:8px;"
                "padding:10px 14px;background:#161b2e;border-radius:8px;"
                "border:1px solid #2a3050;'>"
                "위 버튼에서 협력사를 선택하면 해당 협력사의 BEP 및 인건비 데이터를 확인할 수 있습니다."
                "</div>",
                unsafe_allow_html=True,
            )
            return

        st.markdown(
            f"<div class='section-title'>협력사 현황 &nbsp;—&nbsp; "
            f"{mask_company(selected_company)}</div>",
            unsafe_allow_html=True,
        )
        try:
            bep_df = get_bep_data(selected_company, months=months_tuple)
        except Exception as e:
            logger.error("BEP 데이터 로드 실패: %s\n%s", e, traceback.format_exc())
            st.error("데이터 로드에 실패했습니다. 관리자에게 문의해 주세요.")
            return

        tab_bep, tab_labor_exp = st.tabs(["BEP", "인건비 / 지출금"])
        with tab_bep:
            m_labels = [c for c in bep_df.columns if c != "항목"]
            bep_mi = _make_bep_mi(bep_df, m_labels)
            st.dataframe(_style_bep(bep_mi, m_labels),
                         use_container_width=True, hide_index=True,
                         key=f"kpi3_bep_table_{key_prefix}")
        with tab_labor_exp:
            labor_exp_df = get_labor_expense_data(selected_company, months=months_tuple)
            if not labor_exp_df:
                st.markdown(
                    "<div style='color:#8896b3;font-size:12px;padding:10px 14px;"
                    "background:#161b2e;border-radius:8px;border:1px solid #2a3050;'>"
                    "데이터가 없습니다.</div>",
                    unsafe_allow_html=True,
                )
            else:
                _mlabels = list(labor_exp_df[0]["months"].keys())
                le_html  = _render_labor_expense_table(labor_exp_df, _mlabels)
                n_base   = len(labor_exp_df)
                n_detail = sum(len(g["detail"]) for g in labor_exp_df)
                components.html(
                    le_html,
                    height=max(350, n_base * 44 + n_detail * 36 + 120),
                    scrolling=True,
                )

    # ── 1) 과거 누계 탭 ─────────────────────────────────────────
    with tab_past:
        if _curr_m <= 1:
            st.markdown(
                "<div style='color:#8896b3;font-size:14px;margin:40px 0;"
                "padding:32px;background:#161b2e;border-radius:8px;"
                "border:1px solid #2a3050;text-align:center;'>"
                "📭 <b style='color:#cbd5e1;'>표시할 과거 데이터가 없습니다.</b><br>"
                "<span style='font-size:11px;color:#64748b;'>"
                "당월이 1월이라 1월~전월 범위가 비어있습니다.</span></div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f"<div class='section-title'>"
                f"📊 협력사 월별 실적 (1월 ~ {_prev_m}월) — 누계 포함</div>",
                unsafe_allow_html=True,
            )
            df_past = _build_past_cumulative_table(_curr_y, _curr_m)
            if df_past is None or df_past.empty:
                st.info("데이터가 없습니다.")
            else:
                st.dataframe(
                    _style_past_cumulative(df_past, _curr_m),
                    use_container_width=True, hide_index=True,
                    key="kpi3_past_cumulative_table",
                )
            _협력사_btns("past")

            # 협력사 BEP — 1월 ~ 전월 월별 컬럼
            _past_months = tuple((_curr_y, m) for m in range(1, _curr_m))
            _render_partner_bep(_past_months, "past")

            # 운영자 — 월 선택 후 전망 수정
            if _is_admin_now:
                st.markdown("<div style='height:32px;'></div>",
                            unsafe_allow_html=True)
                st.markdown(
                    "<div class='section-title'>"
                    "✏️ 운영자 — 과거 월 전망 수정</div>",
                    unsafe_allow_html=True,
                )
                _sel_month = st.selectbox(
                    "수정할 월 선택",
                    options=list(range(1, _curr_m)),
                    format_func=lambda v: f"{v}월",
                    key="kpi3_past_admin_month",
                )
                _render_forecast_input(_curr_y, _sel_month,
                                       return_tab_idx=0, 구분="전망")

    # ── 2) 당월 탭 ──────────────────────────────────────────────
    with tab_curr:
        _당월_title = f"📋 협력사 당월 전망 — {_curr_m}월 (전월 입력 기준)"
        _render_forecast_display(_curr_y, _curr_m, _당월_title)

        st.markdown("<div class='section-title'>전망 정도율 (협력사별)</div>",
                    unsafe_allow_html=True)
        _draw_radar_charts(jeongdoyul_당월, tab_key="curr")
        st.markdown("<div class='section-title'>인시당 생산성</div>",
                    unsafe_allow_html=True)
        prod_mi = _make_productivity_mi(prod_df_당월, _DISPLAY_PERIODS_당월)
        st.dataframe(_style_productivity(prod_mi, _DISPLAY_PERIODS_당월),
                     use_container_width=True, hide_index=True,
                     key="kpi3_productivity_curr")
        _협력사_btns("curr")

        # 협력사 BEP — 당월만
        _render_partner_bep(((_curr_y, _curr_m),), "curr")

        if _is_admin_now:
            st.markdown("<div style='height:32px;'></div>",
                        unsafe_allow_html=True)
            st.markdown(
                f"<div class='section-title'>"
                f"✏️ 운영자 — 당월 전망 직접 수정 ({_curr_m}월)</div>",
                unsafe_allow_html=True,
            )
            _render_forecast_input(_curr_y, _curr_m, return_tab_idx=1)

    # ── 3) 차월 탭 ──────────────────────────────────────────────
    with tab_next:
        st.markdown(
            f"<div class='section-title'>📝 협력사 차월 전망 입력 — {_next_m}월</div>",
            unsafe_allow_html=True,
        )
        _render_forecast_input(_next_y, _next_m, return_tab_idx=2)
        st.markdown("<div style='height:18px;'></div>",
                    unsafe_allow_html=True)
        _차월_없음 = (
            prod_df_익월["전망_투입"].sum() == 0
            if "전망_투입" in prod_df_익월.columns else True
        )
        if _차월_없음:
            st.markdown(
                "<div style='color:#8896b3;font-size:13px;margin:24px 0 8px 2px;"
                "padding:14px 18px;background:#161b2e;border-radius:8px;"
                "border:1px solid #2a3050;'>"
                "차월 전망 데이터가 아직 입력되지 않았습니다.<br>"
                "<span style='font-size:11px;color:#4a90d9;'>"
                "매월 23일 이후 입력되며, 입력 완료 시 자동으로 표시됩니다.</span></div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown("<div class='section-title'>전망 정도율 (협력사별)</div>",
                        unsafe_allow_html=True)
            _draw_radar_charts(jeongdoyul_익월, tab_key="next")
            st.markdown("<div class='section-title'>인시당 생산성</div>",
                        unsafe_allow_html=True)
            prod_mi = _make_productivity_mi(prod_df_익월, _DISPLAY_PERIODS_익월)
            st.dataframe(_style_productivity(prod_mi, _DISPLAY_PERIODS_익월),
                         use_container_width=True, hide_index=True,
                         key="kpi3_productivity_next")
            _협력사_btns("next")

            # 협력사 BEP — 차월만
            _render_partner_bep(((_next_y, _next_m),), "next")