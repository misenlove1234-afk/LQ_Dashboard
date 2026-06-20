"""
담당자 :               (본인 이름 작성)
항목   : [화면] proc_3 - 특수선 공정 현황
작성일 :

반영사항:
  - 카드: st.columns() 로 가로 배치 (왼→오른쪽)
  - 이동바: figure.update_xaxes(range=) 방식으로 강제 적용
  - SUB SYSTEM: EVENT A열(Main/Sub\nSystem) 기준 전체 행
"""

import streamlit as st
import pandas as pd
import datetime
import logging
import traceback
import plotly.graph_objects as go
from plotly.subplots import make_subplots

logger = logging.getLogger(__name__)

from data.proc_3_data import (
    get_ship_list, load_progress_data,
    get_latest_week, get_week_list, get_gongjon_list,
    get_summary_table, get_progress_trend,
    get_weekly_summary, get_total_summary, get_trend,
    load_mc_data, load_mc_data_by_gwa, load_mc_data_all_wc,
    get_mc_kpi, get_mc_kpi_by_week, filter_mc_by_week, get_mc_weekly,
    load_budget_weight,
    get_mc_gongjon_list, get_mc_plan_weekly,
    get_gwamyung_list, load_discipline_map, get_discipline_summary,
    load_event_data, get_event_summary, get_subsystem_summary,
    load_room_data, get_room_list, get_room_summary, get_room_kpi,
    get_mc_detail_by_event, get_mc_detail_by_subsys, get_room_detail,
    get_room_by_gwa,
)

C_PLAN_W = "#4472C4"
C_REAL_W = "#70AD47"
C_PLAN_C = "#ED7D31"
C_REAL_C = "#FF00FF"
C_BG     = "#0E1117"
C_GOOD   = "#00B050"
C_WARN   = "#FFC000"
C_BAD    = "#FF4444"
C_NONE   = "#808080"

# ──────────────────────────────────────────
# 헬퍼
# ──────────────────────────────────────────
def _to_excel(df):
    """DataFrame → 엑셀 바이트"""
    from io import BytesIO
    buf = BytesIO()
    df.to_excel(buf, index=False, engine="openpyxl")
    return buf.getvalue()

def _extract_mc_detail_safe(df_mc):
    """MC DataFrame에서 상세 컬럼 추출 (안전 래퍼)"""
    if df_mc is None or df_mc.empty:
        return pd.DataFrame()
    from data.proc_3_data import _extract_mc_detail
    return _extract_mc_detail(df_mc)

def _find_col_safe(df, candidates):
    """_find_col의 proc_3.py용 래퍼"""
    from data.proc_3_data import _find_col
    return _find_col(df, candidates)
def _pct(v):
    if v is None or (isinstance(v, float) and pd.isna(v)): return "-"
    return f"{v * 100:.1f}%"

def _num(v):
    if v is None or (isinstance(v, float) and pd.isna(v)): return "-"
    return f"{v:,.0f}"

def _rate_color(v):
    if v is None or (isinstance(v, float) and pd.isna(v)): return C_NONE
    f = round(float(v), 4)   # ★ 부동소수점 반올림 → 0.9999...도 1.0으로 처리
    if f >= 1.0:  return C_GOOD
    if f >= 0.7:  return C_WARN
    return C_BAD

def _signal_html(sig):
    emoji = {"GREEN": "🟢", "YELLOW": "🟡", "RED": "🔴", "GRAY": "⚪"}.get(sig, "⚪")
    return f'<span style="font-size:14px;">{emoji}</span>'

def _bullet_html(value, plan):
    try:
        p = float(plan) if plan else 0
        v = float(value) if value else 0
        pct = min(v / p * 100, 150.0) if p else 100.0
    except: pct = 0.0
    color = _rate_color(pct / 100)
    bar_w = min(pct, 100)
    return (
        f'<div style="display:flex;align-items:center;gap:5px;">'
        f'<div style="flex:1;background:#1e2a3a;border-radius:4px;height:13px;min-width:50px;">'
        f'<div style="width:{bar_w:.1f}%;background:{color};height:13px;border-radius:4px;"></div>'
        f'</div>'
        f'<span style="color:{color};font-size:0.8rem;font-weight:600;min-width:42px;">{pct:.1f}%</span>'
        f'</div>'
    )

def _wk_sort(wk):
    try: return int(wk.split("년")[0]) * 100 + int(wk.upper().split("W")[1])
    except: return 0

def _get_current_week_key():
    d = datetime.date.today()
    return str(d.year)[-2:] + "년W" + str(d.isocalendar()[1])

def _get_default_idx(week_list):
    cur_sort = _wk_sort(_get_current_week_key())
    candidates = [(i, _wk_sort(wk)) for i, wk in enumerate(week_list) if _wk_sort(wk) <= cur_sort]
    if not candidates:
        return len(week_list) - 1
    db_latest_idx, db_latest_sort = max(candidates, key=lambda x: x[1])
    # DB 최신 주차 == 현재 주차일 때만 -1주차, 아니면 DB 최신 주차 그대로
    if db_latest_sort == cur_sort:
        return max(0, db_latest_idx - 1)
    return db_latest_idx

def _get_range_wks(wks_sorted, center_week, half=5):
    """center_week 기준 ±half 주 범위 반환"""
    cw_s   = _wk_sort(center_week)
    cw_idx = next((i for i, w in enumerate(wks_sorted) if _wk_sort(w) >= cw_s), len(wks_sorted) - 1)
    s_idx  = max(0, cw_idx - half)
    e_idx  = min(len(wks_sorted) - 1, cw_idx + half)
    return wks_sorted[s_idx], wks_sorted[e_idx]


# ──────────────────────────────────────────
# ★ 카드: st.columns() 가로 배치
# ──────────────────────────────────────────
def _show_cards(items):
    """
    items: list of (label, value, color) 또는 (label, value, color, sub_label, sub_value, sub_color)
    st.columns 로 가로 배치 → 왼쪽에서 오른쪽으로
    4번째 이후 원소: sub_label, sub_value, sub_color (달성율 등 보조 수치 표기용)
    """
    cols = st.columns(len(items))
    for col, item in zip(cols, items):
        label, value, color = item[0], item[1], item[2]
        # 선택적 보조 수치 (달성율 등)
        sub_html = ""
        if len(item) >= 6:
            sl, sv, sc = item[3], item[4], item[5]
            sub_html = (
                f'<div style="margin-top:5px;font-size:0.7rem;color:#64748b;">'
                f'{sl} <span style="color:{sc};font-weight:700;">{sv}</span>'
                f'</div>'
            )
        col.markdown(
            f'<div style="'
            f'background:linear-gradient(135deg,#1a2744,#0f1a33);'
            f'border:1px solid rgba(56,189,248,0.15);'
            f'border-radius:10px;padding:12px 10px;text-align:center;">'
            f'<div style="font-size:0.68rem;color:#64748b;margin-bottom:4px;letter-spacing:0.05em;">{label}</div>'
            f'<div style="font-size:1.1rem;font-weight:700;color:{color};">{value}</div>'
            f'{sub_html}'
            f'</div>',
            unsafe_allow_html=True
        )


# ──────────────────────────────────────────
# Line 수치 겹침 방지
# ──────────────────────────────────────────
def _auto_text_pos(vals_a, vals_b, threshold=0.05):
    pos_a, pos_b = [], []
    for a, b in zip(vals_a, vals_b):
        try:
            fa, fb = float(a), float(b)
            diff = abs(fa - fb)
            ref  = max(abs(fa), abs(fb), 1)
            if diff / ref < threshold:
                pos_a.append("top center")
                pos_b.append("bottom center")
            else:
                pos_a.append("top center" if fa >= fb else "bottom center")
                pos_b.append("top center" if fb > fa  else "bottom center")
        except:
            pos_a.append("top center")
            pos_b.append("bottom center")
    return pos_a, pos_b


# ──────────────────────────────────────────
# Total Progress 차트 (% 단위)
# ──────────────────────────────────────────
def _make_total_pct_chart(df_trend: pd.DataFrame, height=290) -> go.Figure:
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    df  = df_trend.copy()
    for col in ["주간계획","주간실적","누계계획","누계실적"]:
        if col in df.columns:
            df[col] = df[col].apply(
                lambda v: v * 100 if v is not None and not (isinstance(v, float) and pd.isna(v)) else 0
            )

    def _txt(col):
        return df[col].apply(lambda v: f"{v:.1f}%" if v and v != 0 else "")

    nk_vals = df["누계계획"].tolist() if "누계계획" in df.columns else []
    nr_vals = df["누계실적"].tolist() if "누계실적" in df.columns else []
    nk_pos, nr_pos = _auto_text_pos(nk_vals, nr_vals)

    if "주간계획" in df.columns:
        fig.add_trace(go.Bar(x=df["week_key"], y=df["주간계획"],
            name="주간계획", marker_color=C_PLAN_W, opacity=0.6,
            text=_txt("주간계획"), textposition="outside",
            textfont=dict(size=11, color="white")), secondary_y=False)
    if "주간실적" in df.columns:
        fig.add_trace(go.Bar(x=df["week_key"], y=df["주간실적"],
            name="주간실적", marker_color=C_REAL_W, opacity=0.6,
            text=_txt("주간실적"), textposition="outside",
            textfont=dict(size=11, color="white")), secondary_y=False)
    if "누계계획" in df.columns:
        fig.add_trace(go.Scatter(x=df["week_key"], y=df["누계계획"],
            name="누계계획", mode="lines+markers+text",
            line=dict(color=C_PLAN_C, width=2),
            text=_txt("누계계획"), textposition=nk_pos,
            textfont=dict(size=11, color=C_PLAN_C)), secondary_y=True)
    if "누계실적" in df.columns:
        fig.add_trace(go.Scatter(x=df["week_key"], y=df["누계실적"],
            name="누계실적", mode="lines+markers+text",
            line=dict(color=C_REAL_C, width=2),
            text=_txt("누계실적"), textposition=nr_pos,
            textfont=dict(size=11, color=C_REAL_C)), secondary_y=True)

    import math as _math
    max_cum  = max((df[c].max() for c in ["누계계획","누계실적"] if c in df.columns), default=0)
    max_week = max((df[c].max() for c in ["주간계획","주간실적"] if c in df.columns), default=0)
    # ★ Y축 범위를 데이터에 맞게 동적 설정
    cum_ymax  = _math.ceil((max_cum  + 5) / 10) * 10 if max_cum  < 80 else (100 if max_cum < 100 else 110)
    week_ymax = _math.ceil((max_week + 2) / 5)  * 5  if max_week < 10 else 10

    fig.update_layout(
        height=height, paper_bgcolor=C_BG, plot_bgcolor=C_BG,
        font=dict(color="white"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        barmode="group",
        margin=dict(l=0, r=0, t=30, b=10),
        xaxis=dict(gridcolor="#333333", zerolinecolor="#555555"),
    )
    fig.update_yaxes(title_text="주간(%)", secondary_y=False,
                     range=[0, week_ymax], ticksuffix="%",
                     gridcolor="#333333", zerolinecolor="#555555")
    fig.update_yaxes(title_text="누계(%)", secondary_y=True,
                     range=[0, cum_ymax], ticksuffix="%",
                     gridcolor="#333333", zerolinecolor="#555555")
    return fig


# ──────────────────────────────────────────
# 공종별 차트 (절대값 + 이동바)
# ──────────────────────────────────────────
def _make_dual_chart(df_trend: pd.DataFrame, height=290,
                     rangeslider=False, center_week=None, half=5) -> go.Figure:
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    def _txt(col):
        return df_trend[col].apply(lambda v: f"{v:,.0f}" if v and v != 0 else "")

    nk_vals = df_trend["누계계획"].tolist() if "누계계획" in df_trend.columns else []
    nr_vals = df_trend["누계실적"].tolist() if "누계실적" in df_trend.columns else []
    nk_pos, nr_pos = _auto_text_pos(nk_vals, nr_vals)

    if "주간계획" in df_trend.columns:
        fig.add_trace(go.Bar(x=df_trend["week_key"], y=df_trend["주간계획"],
            name="주간계획", marker_color=C_PLAN_W, opacity=0.6,
            text=_txt("주간계획"), textposition="outside",
            textfont=dict(size=11, color="white")), secondary_y=False)
    if "주간실적" in df_trend.columns:
        fig.add_trace(go.Bar(x=df_trend["week_key"], y=df_trend["주간실적"],
            name="주간실적", marker_color=C_REAL_W, opacity=0.6,
            text=_txt("주간실적"), textposition="outside",
            textfont=dict(size=11, color="white")), secondary_y=False)
    if "누계계획" in df_trend.columns:
        fig.add_trace(go.Scatter(x=df_trend["week_key"], y=df_trend["누계계획"],
            name="누계계획", mode="lines+markers+text",
            line=dict(color=C_PLAN_C, width=2),
            text=_txt("누계계획"), textposition=nk_pos,
            textfont=dict(size=11, color=C_PLAN_C)), secondary_y=True)
    if "누계실적" in df_trend.columns:
        fig.add_trace(go.Scatter(x=df_trend["week_key"], y=df_trend["누계실적"],
            name="누계실적", mode="lines+markers+text",
            line=dict(color=C_REAL_C, width=2),
            text=_txt("누계실적"), textposition=nr_pos,
            textfont=dict(size=11, color=C_REAL_C)), secondary_y=True)

    # ★ 이동바 + 초기 범위 강제 설정
    xaxis_cfg = dict(gridcolor="#333333", zerolinecolor="#555555")
    if rangeslider and center_week and not df_trend.empty:
        wks = sorted(df_trend["week_key"].tolist(), key=_wk_sort)
        r_start, r_end = _get_range_wks(wks, center_week, half)
        # ★ 카테고리 x축은 인덱스 번호로 range 지정
        try:
            i_start = wks.index(r_start)
            i_end   = wks.index(r_end)
        except ValueError:
            i_start, i_end = 0, len(wks) - 1
        xaxis_cfg.update(dict(
            rangeslider=dict(visible=True, thickness=0.07),
            range=[i_start - 0.5, i_end + 0.5],
            autorange=False,
        ))

    # ★ 주간 Y축 범위를 데이터에 맞게 자동 설정
    import math as _math
    max_week = max((df_trend[c].max() for c in ["주간계획","주간실적"] if c in df_trend.columns), default=0)
    if max_week and max_week > 0:
        week_ymax = _math.ceil(max_week * 1.3 / 10) * 10  # 30% 여유
        week_ymax = max(week_ymax, 10)
    else:
        week_ymax = None  # 자동

    # ★ 누계 Y축 범위도 데이터에 맞게 설정
    max_cum = max((df_trend[c].max() for c in ["누계계획","누계실적"] if c in df_trend.columns), default=0)
    if max_cum and max_cum > 0:
        cum_ymax = _math.ceil(max_cum * 1.1 / 100) * 100  # 10% 여유
        cum_ymax = max(cum_ymax, 100)
    else:
        cum_ymax = None

    fig.update_layout(
        height=height, paper_bgcolor=C_BG, plot_bgcolor=C_BG,
        font=dict(color="white"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        barmode="group",
        margin=dict(l=0, r=0, t=30, b=45 if rangeslider else 10),
        xaxis=xaxis_cfg,
    )
    fig.update_yaxes(title_text="주간", secondary_y=False,
                     range=[0, week_ymax] if week_ymax else None,
                     gridcolor="#333333", zerolinecolor="#555555")
    fig.update_yaxes(title_text="누계", secondary_y=True,
                     range=[0, cum_ymax] if cum_ymax else None,
                     gridcolor="#333333", zerolinecolor="#555555")
    return fig


def _get_5week_trend(df_long, sel_week, week_list, total_volume=None):
    cur_sort = _wk_sort(_get_current_week_key())
    sel_sort = _wk_sort(sel_week)
    if sel_sort >= cur_sort:
        target = [wk for wk in week_list if _wk_sort(wk) < cur_sort]
    else:
        target = [wk for wk in week_list if _wk_sort(wk) <= sel_sort]
    target = sorted(target, key=_wk_sort)[-5:]
    # ★ target이 비어있으면 week_list 전체 사용 (미래 주차 포함)
    if not target:
        target = sorted(week_list, key=_wk_sort)

    # ★ 카드와 동일한 방식: 전체합산 / 전체총물량
    sub = df_long[
        (~df_long["공종"].isin(["Progress","LQ Total Progress"])) &
        (~df_long["공종"].apply(lambda g: "MC" in str(g).replace(" ","").upper()))
    ].copy()

    total_tv = sum(v for k, v in (total_volume or {}).items()
                   if "MC" not in str(k).replace(" ","").upper()) or 1.0

    rows = []
    for wk in target:
        s = sub[sub["week_key"] == wk]
        result = {"week_key": wk, "주간계획": 0.0, "주간실적": 0.0,
                  "누계계획": 0.0, "누계실적": 0.0}
        for 항목 in ["주간계획","주간실적","누계계획","누계실적"]:
            val = s[s["항목"]==항목]["값"].sum()
            result[항목] = val / total_tv
        rows.append(result)

    if not rows:
        return pd.DataFrame()

    df_result = pd.DataFrame(rows)

    # ★ 누계값이 모두 0이면 주간 누적합으로 대체 (SN2688형)
    if df_result["누계계획"].sum() == 0:
        if df_result["주간계획"].sum() > 0:
            df_result["누계계획"] = df_result["주간계획"].cumsum()
    if df_result["누계실적"].sum() == 0:
        if df_result["주간실적"].sum() > 0:
            df_result["누계실적"] = df_result["주간실적"].cumsum()

    return df_result


# ──────────────────────────────────────────
# 테이블 HTML
# ──────────────────────────────────────────
def _th(t): return f'<th style="padding:7px 9px;text-align:center;color:#7dd3fc;font-size:0.79rem;white-space:nowrap;background:#1a2744;">{t}</th>'
def _td(t, right=False, bold=False):
    return f'<td style="padding:6px 9px;font-size:0.79rem;color:#e2e8f0;text-align:center;font-weight:{"700" if bold else "400"};white-space:nowrap;">{t}</td>'
def _td_g(t): return f'<td style="padding:6px 9px;font-size:0.79rem;color:#94a3b8;text-align:center;white-space:nowrap;">{t}</td>'

def _tbl(head_cols, rows_data):
    head = "<tr>" + "".join([_th(c) for c in head_cols]) + "</tr>"
    rows = ""
    for i, row in enumerate(rows_data):
        bg = "rgba(255,255,255,0.03)" if i % 2 == 0 else "transparent"
        rows += f'<tr style="background:{bg};">' + "".join(row) + "</tr>"
    return f'<div style="overflow-x:auto;"><table style="width:100%;border-collapse:collapse;"><thead>{head}</thead><tbody>{rows}</tbody></table></div>'

def _진도율_html(value, plan):
    """진도율 전용: 100% 초과 시 ⚠️ + 빨간색 경고 표시"""
    try:
        p = float(plan) if plan else 0
        v = float(value) if value else 0
        pct = round((v / p * 100), 4) if p else 0.0  # ★ 부동소수점 반올림
    except:
        pct = 0.0
    if round(pct, 2) > 100.0:
        # ★ 100% 초과: 빨간색 경고 + ⚠️ 아이콘
        bar_w = 100  # 바는 100%로 캡
        return (
            f'<div style="display:flex;align-items:center;gap:5px;">'
            f'<div style="flex:1;background:#1e2a3a;border-radius:4px;height:13px;min-width:50px;">'
            f'<div style="width:100%;background:{C_BAD};height:13px;border-radius:4px;"></div>'
            f'</div>'
            f'<span style="color:{C_BAD};font-size:0.8rem;font-weight:700;min-width:70px;">⚠️ {pct:.1f}%</span>'
            f'</div>'
        )
    # 정상: 기존 _bullet_html 과 동일
    color = _rate_color(pct / 100)
    bar_w = min(pct, 100)
    return (
        f'<div style="display:flex;align-items:center;gap:5px;">'
        f'<div style="flex:1;background:#1e2a3a;border-radius:4px;height:13px;min-width:50px;">'
        f'<div style="width:{bar_w:.1f}%;background:{color};height:13px;border-radius:4px;"></div>'
        f'</div>'
        f'<span style="color:{color};font-size:0.8rem;font-weight:600;min-width:42px;">{pct:.1f}%</span>'
        f'</div>'
    )

def _summary_html(df):
    rows = []
    for _, r in df.iterrows():
        rows.append([
            _td(r["구분"]),
            _td_g(_num(r["총물량"])),
            _td_g(_num(r["누계계획"])),
            _td(_num(r["누계실적"]), right=True, bold=True),
            f'<td style="padding:6px 9px;">{_bullet_html(r["누계실적"], r["누계계획"])}</td>',
            # ★ 진도율: 100% 초과 시 경고 표시
            f'<td style="padding:6px 9px;">{_진도율_html(r["누계실적"], r["총물량"])}</td>',
        ])
    return _tbl(["구분","총물량","누계계획","누계실적","달성율","진도율"], rows)

def _weekly_html(df):
    rows = []
    for _, r in df.iterrows():
        rows.append([_td(r["구분"]), _td_g(_num(r["주간계획"])), _td(_num(r["주간실적"]), right=True),
                     f'<td style="padding:6px 9px;">{_bullet_html(r["주간실적"], r["주간계획"])}</td>'])
    return _tbl(["구분","주간계획","주간실적","달성율"], rows)

def _total_html(df):
    rows = []
    for _, r in df.iterrows():
        rows.append([_td(r["구분"]), _td_g(_num(r["누계계획"])), _td(_num(r["누계실적"]), right=True),
                     f'<td style="padding:6px 9px;">{_bullet_html(r["누계실적"], r["누계계획"])}</td>'])
    return _tbl(["구분","누계계획","누계실적","달성율"], rows)

def _event_html(df, cols):
    rows = []
    for _, r in df.iterrows():
        row_cells = []
        for c in cols:
            if c in ("신호등", "상태"):
                row_cells.append(f'<td style="padding:6px 9px;text-align:center;">{_signal_html(r.get("신호등","GRAY"))}</td>')
            elif c == "완료율(%)":
                try: v = float(r.get(c, 0))
                except: v = 0.0
                row_cells.append(f'<td style="padding:6px 9px;min-width:90px;">{_bullet_html(v, 100)}</td>')
            elif c in ("MC 총합","MC완료"):
                row_cells.append(_td_g(str(r.get(c,"-"))))
            else:
                row_cells.append(_td(str(r.get(c,"-"))))
        rows.append(row_cells)
    return _tbl(cols, rows)


# ──────────────────────────────────────────
# render()
# ──────────────────────────────────────────
def render():
    try:
        ship_list = get_ship_list()
    except Exception as e:
        logger.error("호선 목록 로드 실패: %s\n%s", e, traceback.format_exc())
        st.error("데이터 로드에 실패했습니다. 관리자에게 문의해 주세요."); return
    if not ship_list:
        st.warning("upload_proc3_to_db.py upload 를 먼저 실행하세요."); return

    st.sidebar.markdown("### 호선 선택")
    # ★ 첫 번째 옵션을 빈 값으로 → 선택 강제
    selected_ship = st.sidebar.selectbox(
        "호선", ship_list,
        label_visibility="collapsed",
        key="proc3_ship_select"
    )

    try:
        df_long, total_volume = load_progress_data(selected_ship)
    except Exception as e:
        logger.error("PROGRESS 데이터 로드 실패: %s\n%s", e, traceback.format_exc())
        st.error("데이터 로드에 실패했습니다. 관리자에게 문의해 주세요."); return
    if df_long.empty:
        st.warning("선택한 호선의 PROGRESS 데이터가 없습니다."); return

    week_list   = get_week_list(df_long)
    default_idx = _get_default_idx(week_list)
    current_wk  = week_list[default_idx]

    # ★ sel_week 기준 월 계산
    def _week_to_month(wk_str):
        try:
            yr = int(wk_str.split("년")[0]) + 2000
            wn = int(wk_str.upper().split("W")[1])
            import datetime as _dt2
            d = _dt2.date.fromisocalendar(yr, wn, 1)
            return d.month
        except:
            return None
    def _week_to_year(wk_str):
        try:
            return int(wk_str.split("년")[0]) + 2000
        except: return None

    st.sidebar.markdown("### 기준 주차")
    # ★ 최초 진입 또는 호선 변경 시 금일 기준 주차 자동 선택
    _ship_chg_key = "proc3_ship"
    _week_val_key = "proc3_week_val"
    if st.session_state.get(_ship_chg_key) != selected_ship:
        # 호선 변경 시 → 금일 기준 주차로 초기화
        st.session_state[_ship_chg_key]  = selected_ship
        st.session_state[_week_val_key]  = current_wk
    if _week_val_key not in st.session_state:
        # 최초 진입 시 → 금일 기준 주차 설정
        st.session_state[_week_val_key]  = current_wk
    if st.session_state[_week_val_key] not in week_list:
        st.session_state[_week_val_key]  = current_wk

    _cur_idx = week_list.index(st.session_state[_week_val_key])
    sel_week = st.sidebar.selectbox(
        "주차", week_list,
        index=_cur_idx,
        label_visibility="collapsed",
        key="proc3_week_select"
    )
    # 선택값 저장
    st.session_state[_week_val_key] = sel_week
    # ★ 선택된 주차의 월 표시
    _sel_month = _week_to_month(sel_week)
    _sel_yr = _week_to_year(sel_week)
    if _sel_month and _sel_yr:
        st.sidebar.markdown(
            f'<div style="color:#94a3b8;font-size:0.8rem;margin-top:-8px;padding-left:2px;">'
            f'📅 {_sel_yr}년{_sel_month}월기준</div>',
            unsafe_allow_html=True
        )

    # ★ 과 선택(MC현황) - 사이드바 selectbox
    # key 없이 index만 사용 → session_state 충돌 방지
    st.sidebar.markdown("### 과 선택(MC현황)")
    gwa_list = get_gwamyung_list(selected_ship)

    # 이전 선택값 유지 (호선 변경 시 초기화)
    _gwa_state_key  = "proc3_gwa_val"
    _gwa_ship_key   = "proc3_gwa_ship"
    if st.session_state.get(_gwa_ship_key) != selected_ship:
        st.session_state[_gwa_ship_key] = selected_ship
        st.session_state[_gwa_state_key] = gwa_list[0]
    if _gwa_state_key not in st.session_state:
        st.session_state[_gwa_state_key] = gwa_list[0]
    if st.session_state[_gwa_state_key] not in gwa_list:
        st.session_state[_gwa_state_key] = gwa_list[0]

    _gwa_idx = gwa_list.index(st.session_state[_gwa_state_key])
    sel_gwa  = st.sidebar.selectbox(
        "과", gwa_list,
        index=_gwa_idx,
        label_visibility="collapsed",
        key="proc3_gwa_select"
    )
    st.session_state[_gwa_state_key] = sel_gwa



    tbl_week   = sel_week
    # ★ 공종 목록 동적 조회 (Progress 제외, 엑셀 순서 유지)
    gj_list    = get_gongjon_list(selected_ship)
    summary_df = get_summary_table(df_long, total_volume, tbl_week, gj_list)

    tab1, tab2, tab3, tab4 = st.tabs(["📊 PROGRESS", "📋 계획/실적 현황", "🔧 MC 현황", "⚡ 전기실 MC 현황"])

    # ════════════════════════════════════════
    # TAB 1
    # ════════════════════════════════════════
    with tab1:
        col_l, col_r = st.columns(2)

        with col_l:
            # ★ 선택 불가 selectbox (오른쪽 공종선택 selectbox와 높이 동일)
            st.selectbox("호선", [selected_ship], disabled=True, label_visibility="visible", key="tab1_ship_display")
            st.markdown("#### LQ TOTAL PROGRESS")

            # ★ 카드: tbl_week 기준, MC 제외 총물량으로 계산 (그래프와 동일)
            _mc_excl_tv = sum(v for k, v in total_volume.items()
                              if "MC" not in str(k).replace(" ","").upper()) if total_volume else 0
            ttv = _mc_excl_tv or summary_df["총물량"].sum()
            # ★ summary_df 누계실적 직접 합산 대신 DB 전체 합산으로 계산
            _all_sub = df_long[
                (~df_long["공종"].isin(["Progress","LQ Total Progress"])) &
                (~df_long["공종"].apply(lambda g: "MC" in str(g).replace(" ","").upper()))
            ]
            _week_sub = _all_sub[_all_sub["week_key"] == tbl_week]
            tnk = _week_sub[_week_sub["항목"]=="누계계획"]["값"].sum()
            tnr = _week_sub[_week_sub["항목"]=="누계실적"]["값"].sum()
            # ★ 누계값 없으면 주간값으로 대체 (SN2688형 단일주차 파일)
            if tnk == 0:
                tnk = _week_sub[_week_sub["항목"]=="주간계획"]["값"].sum()
            if tnr == 0:
                tnr = _week_sub[_week_sub["항목"]=="주간실적"]["값"].sum()
            달성율_v  = tnr / tnk if tnk else 1.0

            _show_cards([
                ("WEEK",   tbl_week,                          "#38BDF8"),
                ("누계계획", _pct(tnk / ttv if ttv else 0),   "#94a3b8"),
                ("누계실적", _pct(tnr / ttv if ttv else 0),   "#e2e8f0"),
                ("달성율",  _pct(달성율_v),                    _rate_color(달성율_v)),
            ])

            trend_5w = _get_5week_trend(df_long, sel_week, week_list, total_volume)
            if not trend_5w.empty:
                st.plotly_chart(_make_total_pct_chart(trend_5w, 290), width='stretch')

        with col_r:
            sel_gj = st.selectbox("공종 선택", gj_list, key="tab1_gj")
            st.markdown(f"#### LQ PROGRESS – {sel_gj}")

            gj_row = summary_df[summary_df["구분"] == sel_gj]
            if not gj_row.empty:
                r = gj_row.iloc[0]
                _show_cards([
                    ("WEEK",   tbl_week,            "#38BDF8"),
                    ("누계계획", _num(r["누계계획"]),  "#94a3b8"),
                    ("누계실적", _num(r["누계실적"]),  "#e2e8f0"),
                    ("달성율",  _pct(r["달성율"]),    _rate_color(r["달성율"])),
                ])

            trend_gj = get_trend(df_long, sel_gj, total_volume)
            if not trend_gj.empty:
                st.plotly_chart(
                    _make_dual_chart(trend_gj, 290, rangeslider=True,
                                     center_week=sel_week, half=5),
                    width='stretch'
                )

        st.markdown("---")
        st.markdown(f"### 총물량 기준 진도율 – {tbl_week}")
        st.write(_summary_html(summary_df), unsafe_allow_html=True)

    # ════════════════════════════════════════
    # TAB 2
    # ════════════════════════════════════════
    with tab2:
        st.markdown(f"### 계획/실적 현황 – {tbl_week}")
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("#### LQ WEEKLY PROGRESS")
            st.write(_weekly_html(get_weekly_summary(df_long, tbl_week, gj_list)), unsafe_allow_html=True)
        with col_b:
            # ★ 얼라인 맞춤: #### 마크다운으로 통일
            st.markdown("#### LQ TOTAL PROGRESS")
            st.write(_total_html(get_total_summary(df_long, tbl_week, gj_list)), unsafe_allow_html=True)
        st.markdown("---")
        st.markdown("#### LQ PROGRESS")
        sel_gj2 = st.selectbox("공종 선택", gj_list, key="tab2_gj")
        trend2  = get_trend(df_long, sel_gj2, total_volume)
        if not trend2.empty:
            st.plotly_chart(
                _make_dual_chart(trend2, 370, rangeslider=True,
                                 center_week=sel_week, half=5),
                width='stretch'
            )

    # ════════════════════════════════════════
    # TAB 3
    # ════════════════════════════════════════
    with tab3:
        st.markdown(f"### MC 현황 – {selected_ship}  |  {sel_gwa}")

        try:
            df_mc = load_mc_data_by_gwa(selected_ship, sel_gwa)
            # ★ 기준주차 필터 적용본 (카드/테이블용)
            # RESULT 컬럼을 기준주차 기준으로 재설정
            df_mc_week = filter_mc_by_week(df_mc, sel_week) if df_mc is not None else None
        except Exception as e:
            st.warning(f"MC 데이터 없음: {e}"); df_mc = None; df_mc_week = None

        try: df_event, df_subsys = load_event_data(selected_ship)
        except Exception as e: st.warning(f"EVENT 데이터 없음: {e}"); df_event = df_subsys = None

        if df_mc is not None and not df_mc.empty:
            # ★ 카드: 전체 기준 (기준주차 무관)
            kpi  = get_mc_kpi(df_mc)
            rate = kpi["완료율"]
            _show_cards([
                ("MC 총합", f"{kpi['MC 총합']:,}", "#94a3b8"),
                ("MC 완료", f"{kpi['MC 완료']:,}", C_GOOD),
                ("MC 잔여", f"{kpi['MC 잔여']:,}", C_BAD if kpi['MC 잔여'] > 0 else C_GOOD),
                ("완료율",  f"{rate:.1f}%",         _rate_color(rate / 100)),
            ])
        else:
            st.markdown(
                '<div style="text-align:center;padding:3rem 0;">'
                '<div style="font-size:1.5rem;margin-bottom:8px;">🚢</div>'
                '<div style="font-size:1rem;color:#94a3b8;">MC 미적용 호선입니다.</div>'
                '</div>',
                unsafe_allow_html=True
            )

        st.markdown("---")

        # ★ MC 그래프: sel_week 기준 ±5주
        if df_mc is not None and not df_mc.empty:
            _col_mc_title, _col_mc_ymax = st.columns([3, 1])
            with _col_mc_title:
                st.markdown("#### MC 주차별 완료 현황")
            with _col_mc_ymax:
                _ymax_key = f"mc_ymax_{selected_ship}"
                # ★ session_state 초기화 (알람 방지: value 대신 session_state만 사용)
                if _ymax_key not in st.session_state:
                    st.session_state[_ymax_key] = 0
                st.number_input(
                    "완료율 최대(%)", min_value=0, max_value=100,
                    step=10, key=_ymax_key,
                    help="0이면 자동 설정"
                )
            _user_ymax = st.session_state.get(_ymax_key, 0)
            mc_weekly = get_mc_weekly(df_mc)
            if not mc_weekly.empty:
                import math
                # ★ MC 공종 계획 데이터 조회 (과 선택 기준)
                mc_gj_list  = get_mc_gongjon_list(selected_ship)
                mc_plan_df  = get_mc_plan_weekly(selected_ship, mc_gj_list, sel_gwa)

                # ★ 전체 주차 범위 (실적+계획 합산), sel_week 기준 ±5주 이동바
                all_wks = sorted(set(mc_weekly["week_key"].tolist() +
                          (mc_plan_df["week_key"].tolist() if not mc_plan_df.empty else [])),
                          key=_wk_sort)
                # sel_week 기준으로 ±5주 인덱스 계산
                cw_s   = _wk_sort(sel_week)
                cw_idx = next((i for i, w in enumerate(all_wks) if _wk_sort(w) >= cw_s),
                              len(all_wks) - 1)
                s_idx  = max(0, cw_idx - 5)
                e_idx  = min(len(all_wks) - 1, cw_idx + 5)
                r_start = all_wks[s_idx]
                r_end   = all_wks[e_idx]

                fig_mc = make_subplots(specs=[[{"secondary_y": True}]])

                import math
                max_bar = mc_weekly["MC완료"].max() if not mc_weekly.empty else 1
                max_bar = max_bar if max_bar else 1

                # ★ 계획 막대 (주간계획)
                if not mc_plan_df.empty and "주간계획" in mc_plan_df.columns:
                    fig_mc.add_trace(go.Bar(
                        x=mc_plan_df["week_key"], y=mc_plan_df["주간계획"],
                        name="주간계획", marker_color=C_PLAN_W, opacity=0.5,
                        text=mc_plan_df["주간계획"].apply(
                            lambda v: f"{v:,.0f}" if v and not (isinstance(v,float) and pd.isna(v)) else ""),
                        textposition="outside", textfont=dict(size=9, color="white"),
                    ), secondary_y=False)
                    max_plan = mc_plan_df["주간계획"].max()
                    if max_plan: max_bar = max(max_bar, max_plan)

                # ★ 실적 막대 (MC완료)
                fig_mc.add_trace(go.Bar(
                    x=mc_weekly["week_key"], y=mc_weekly["MC완료"],
                    name="MC완료", marker_color=C_REAL_W,
                    text=mc_weekly["MC완료"].apply(lambda v: f"{v:,}"),
                    textposition="outside", textfont=dict(size=11, color="white"),
                ), secondary_y=False)

                bar_y_max = math.ceil(max_bar * 2 / 10) * 10

                # ★ 누계계획 % 변환 (MC 총합 기준)
                kpi_total = get_mc_kpi(df_mc)["MC 총합"] if df_mc is not None else 0
                # kpi_total 0이면 mc_weekly 누적완료 최대값으로 추정
                if kpi_total == 0 and not mc_weekly.empty and "누적완료" in mc_weekly.columns:
                    kpi_total = mc_weekly["누적완료"].max() or 0
                if not mc_plan_df.empty and "누계계획" in mc_plan_df.columns and kpi_total > 0:
                    mc_plan_df["누계계획_pct"] = mc_plan_df["누계계획"].apply(
                        lambda v: round(float(v) / kpi_total * 100, 1)
                        if v is not None and not (isinstance(v, float) and pd.isna(v)) else None
                    )
                    fig_mc.add_trace(go.Scatter(
                        x=mc_plan_df["week_key"], y=mc_plan_df["누계계획_pct"],
                        name="누계계획(%)", mode="lines+markers+text",
                        line=dict(color=C_PLAN_C, width=2, dash="dot"),
                        text=mc_plan_df["누계계획_pct"].apply(
                            lambda v: f"{v:.1f}%" if v is not None else ""),
                        textposition="bottom center",
                        textfont=dict(size=9, color=C_PLAN_C),
                    ), secondary_y=True)

                if "완료율" in mc_weekly.columns:
                    max_rate = mc_weekly["완료율"].max()
                    if _user_ymax > 0:
                        y_max = _user_ymax
                    else:
                        y_max = math.ceil((max_rate + 10) / 10) * 10 if max_rate else 20
                    fig_mc.add_trace(go.Scatter(
                        x=mc_weekly["week_key"], y=mc_weekly["완료율"],
                        name="완료율(%)", mode="lines+markers+text",
                        line=dict(color=C_REAL_C, width=2),
                        text=mc_weekly["완료율"].apply(lambda v: f"{v:.1f}%"),
                        textposition="top center",
                        textfont=dict(size=10, color=C_REAL_C),
                    ), secondary_y=True)
                else:
                    y_max = 20

                # ★ _make_dual_chart 와 동일한 방식으로 range 계산
                # 전체 x 카테고리 정렬
                _all_x = sorted(set(
                    mc_weekly["week_key"].tolist() +
                    (mc_plan_df["week_key"].tolist() if not mc_plan_df.empty else [])
                ), key=_wk_sort)
                # sel_week 인덱스 찾기
                _cw_sort = _wk_sort(sel_week)
                try:
                    _cw_i = next(i for i, w in enumerate(_all_x) if _wk_sort(w) >= _cw_sort)
                except StopIteration:
                    _cw_i = len(_all_x) - 1
                _si = max(0, _cw_i - 5)
                _ei = min(len(_all_x) - 1, _cw_i + 5)

                fig_mc.update_layout(
                    height=300, paper_bgcolor=C_BG, plot_bgcolor=C_BG,
                    font=dict(color="white"),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02),
                    barmode="group",
                    xaxis=dict(
                        gridcolor="#333333",
                        categoryorder="array",
                        categoryarray=_all_x,
                        rangeslider=dict(visible=True, thickness=0.07),
                        range=[_si - 0.5, _ei + 0.5],
                        autorange=False,
                    ),
                    margin=dict(l=0, r=0, t=30, b=45),
                )
                fig_mc.update_yaxes(
                    title_text="MC 완료", secondary_y=False,
                    range=[0, bar_y_max],
                    gridcolor="#333333", zerolinecolor="#555555"
                )
                fig_mc.update_yaxes(
                    title_text="완료율(%)", secondary_y=True,
                    range=[0, y_max], ticksuffix="%",
                    gridcolor="#333333", zerolinecolor="#555555"
                )
                st.plotly_chart(fig_mc, width='stretch')
            else:
                st.markdown(
                    '<div style="text-align:center;padding:1.5rem 0;">'
                    '<div style="font-size:1rem;color:#94a3b8;">🚢 MC 데이터가 없습니다.</div>'
                    '</div>',
                    unsafe_allow_html=True
                )

        # ★ DISCIPLINE별 집계 테이블
        st.markdown("---")
        st.markdown("#### DISCIPLINE 기준 MC 현황")
        try:
            disc_summary = get_discipline_summary(df_mc_week)
            if not disc_summary.empty:
                def _disc_html(df):
                    head_cols = ["Discipline","Description","총합","완료","잔여","완료율(%)"]
                    head = "<tr>" + "".join([_th(c) for c in head_cols]) + "</tr>"
                    rows = ""
                    for i, r in df.iterrows():
                        bg = "rgba(255,255,255,0.03)" if i % 2 == 0 else "transparent"
                        try: v = float(r["완료율(%)"])
                        except: v = 0.0
                        rows += (
                            f'<tr style="background:{bg};">'
                            + _td(str(r["Discipline"]))
                            + _td(str(r["Description"]))
                            + _td_g(str(r["총합"]))
                            + _td_g(str(r["완료"]))
                            + _td_g(str(r["잔여"]))
                            + f'<td style="padding:6px 9px;min-width:90px;">{_bullet_html(v, 100)}</td>'
                            + "</tr>"
                        )
                    return f'<div style="overflow-x:auto;"><table style="width:100%;border-collapse:collapse;"><thead>{head}</thead><tbody>{rows}</tbody></table></div>'
                st.write(_disc_html(disc_summary), unsafe_allow_html=True)
            else:
                st.markdown(
                    '<div style="text-align:center;padding:1.5rem 0;">'
                    '<div style="font-size:1rem;color:#94a3b8;">🚢 MC 데이터가 없습니다.</div>'
                    '</div>',
                    unsafe_allow_html=True
                )
        except Exception as e:
            st.warning(f"DISCIPLINE 로드 실패: {e}")

        st.markdown("---")

        if df_event is not None and not df_event.empty:
            if "_df_reset" not in st.session_state:
                st.session_state["_df_reset"] = 0
            _rk = st.session_state["_df_reset"]

            col_ev, col_ss = st.columns(2)

            # ── MAIN EVENT ──
            with col_ev:
                st.markdown("#### MAIN EVENT 현황")
                ev_df = get_event_summary(df_event, df_subsys, df_mc_week)
                ev_df = ev_df[ev_df["MC 총합"].apply(lambda v: str(v) != "-" and int(float(v)) > 0 if str(v) != "-" else False)]
                import datetime as _dt
                ev_df = ev_df.sort_values(by="완료계획일", key=lambda col: col.map(
                    lambda d: (1, "9") if d == "-" or not d else (0, d)
                )).reset_index(drop=True)
                if not ev_df.empty:
                    sig_map = {"GREEN":"🟢","YELLOW":"🟡","RED":"🔴","GRAY":"⚫"}
                    ev_display = ev_df[["MAIN EVENT","완료계획일","MC 총합","MC완료","완료율(%)","신호등"]].copy()
                    ev_display["상태"] = ev_display["신호등"].apply(lambda v: sig_map.get(v, "⚫"))
                    ev_display["완료율(%)"] = ev_display["완료율(%)"].apply(lambda v: round(float(v),1) if str(v) not in ("-","") else 0.0)
                    ev_display = ev_display[["상태","MAIN EVENT","완료계획일","MC 총합","MC완료","완료율(%)"]]

                    ev_selection = st.dataframe(
                        ev_display, hide_index=True, height=400,
                        on_select="rerun", selection_mode="single-row",
                        key=f"ev_df_{_rk}",
                        column_config={
                            "완료율(%)": st.column_config.ProgressColumn("완료율(%)", min_value=0, max_value=100, format="%.1f%%"),
                            "상태": st.column_config.TextColumn("상태", width=50),
                        }
                    )
                    # ★ 행 선택 시 바로 아래에 expander
                    if ev_selection and ev_selection.selection and ev_selection.selection.rows:
                        sel_idx = ev_selection.selection.rows[0]
                        sel_ev_name = ev_df.iloc[sel_idx]["MAIN EVENT"]
                        detail_ev = get_mc_detail_by_event(df_mc, sel_ev_name, df_event, df_subsys)
                        with st.expander(f"📋 {sel_ev_name} 상세", expanded=True):
                            if not detail_ev.empty:
                                st.dataframe(detail_ev, hide_index=True, height=300)
                                st.download_button(
                                    f"📥 {sel_ev_name} 다운로드", _to_excel(detail_ev),
                                    f"MC_{sel_ev_name}_상세.xlsx", key=f"dl_ev_{_rk}"
                                )
                            else:
                                st.info(f"{sel_ev_name} 상세 데이터가 없습니다.")
                else:
                    st.markdown(
                        '<div style="text-align:center;padding:1.5rem 0;"><div style="font-size:1rem;color:#94a3b8;">🚢 MC 데이터가 없습니다.</div></div>',
                        unsafe_allow_html=True
                    )

            # ── SUB SYSTEM ──
            with col_ss:
                st.markdown("#### SUB SYSTEM 현황")
                ss_df = get_subsystem_summary(df_event, df_subsys, df_mc_week)
                ss_df = ss_df[ss_df["MC 총합"].apply(lambda v: str(v) != "-" and int(float(v)) > 0 if str(v) != "-" else False)]
                if not ss_df.empty:
                    sig_map = {"GREEN":"🟢","YELLOW":"🟡","RED":"🔴","GRAY":"⚫"}
                    ss_display = ss_df[["SUB SYSTEM","완료계획일","MC 총합","MC완료","완료율(%)","신호등"]].copy()
                    ss_display["상태"] = ss_display["신호등"].apply(lambda v: sig_map.get(v, "⚫"))
                    ss_display["완료율(%)"] = ss_display["완료율(%)"].apply(lambda v: round(float(v),1) if str(v) not in ("-","") else 0.0)
                    ss_display = ss_display[["상태","SUB SYSTEM","완료계획일","MC 총합","MC완료","완료율(%)"]]

                    ss_selection = st.dataframe(
                        ss_display, hide_index=True, height=400,
                        on_select="rerun", selection_mode="single-row",
                        key=f"ss_df_{_rk}",
                        column_config={
                            "완료율(%)": st.column_config.ProgressColumn("완료율(%)", min_value=0, max_value=100, format="%.1f%%"),
                            "상태": st.column_config.TextColumn("상태", width=50),
                        }
                    )
                    # ★ 행 선택 시 바로 아래에 expander
                    if ss_selection and ss_selection.selection and ss_selection.selection.rows:
                        sel_idx = ss_selection.selection.rows[0]
                        sel_ss_name = ss_df.iloc[sel_idx]["SUB SYSTEM"]
                        detail_ss = get_mc_detail_by_subsys(df_mc, sel_ss_name)
                        with st.expander(f"📋 {sel_ss_name} 상세", expanded=True):
                            if not detail_ss.empty:
                                st.dataframe(detail_ss, hide_index=True, height=300)
                                st.download_button(
                                    f"📥 {sel_ss_name} 다운로드", _to_excel(detail_ss),
                                    f"MC_{sel_ss_name}_상세.xlsx", key=f"dl_ss_{_rk}"
                                )
                            else:
                                st.info(f"{sel_ss_name} 상세 데이터가 없습니다.")
                else:
                    st.markdown(
                        '<div style="text-align:center;padding:1.5rem 0;"><div style="font-size:1rem;color:#94a3b8;">🚢 MC 데이터가 없습니다.</div></div>',
                        unsafe_allow_html=True
                    )
        else:
            st.markdown(
                '<div style="text-align:center;padding:1.5rem 0;"><div style="font-size:1rem;color:#94a3b8;">🚢 MC 데이터가 없습니다.</div></div>',
                unsafe_allow_html=True
            )

    # ════════════════════════════════════════
    # TAB 4 - 전기실 MC 현황
    # ════════════════════════════════════════
    with tab4:
        try:
            df_room = load_room_data(selected_ship)
        except Exception as e:
            st.warning(f"전기실 MC 데이터 없음: {e}")
            df_room = pd.DataFrame()

        # ★ 마트 MC 데이터: 호선 전체 (WC코드 제한 없이)
        try:
            df_mc_all = load_mc_data_all_wc(selected_ship)
        except Exception:
            df_mc_all = pd.DataFrame()

        # ★ WC코드 → 과명 매핑 (마트의 CNST_WK_CENT_DESC 사용)
        df_mc_dict = {}
        if df_mc_all is not None and not df_mc_all.empty:
            desc_col = _find_col_safe(df_mc_all, ["CNST_WK_CENT_DESC","WC_DESC","WC_NM","부서명","과명"])
            if desc_col:
                for gwa_name, grp in df_mc_all.groupby(desc_col):
                    gwa_str = str(gwa_name).strip()
                    if gwa_str and gwa_str not in ("","None","nan"):
                        df_mc_dict[gwa_str] = grp.reset_index(drop=True)
            else:
                # DESC 없으면 WC코드로 fallback
                wc_col = _find_col_safe(df_mc_all, ["CNST_WK_CENT","WC","W/C"])
                if wc_col:
                    for wc_val, grp in df_mc_all.groupby(wc_col):
                        df_mc_dict[str(wc_val).strip()] = grp.reset_index(drop=True)
                else:
                    df_mc_dict["전체"] = df_mc_all

        if df_room is not None and not df_room.empty:
            sel_room = "전체"

            st.markdown(f"### 전기실 MC 현황 – {selected_ship}")

            # KPI 카드 — 총합=엑셀, 완료/잔여=마트 전체
            room_kpi = get_room_kpi(df_room, sel_room, df_mc_all)

            r_rate = room_kpi["완료율"]
            _show_cards([
                ("총합",   f"{room_kpi['총합']:,}",   "#94a3b8"),
                ("완료",   f"{room_kpi['완료']:,}",   C_GOOD),
                ("잔여",   f"{room_kpi['잔여']:,}",   C_BAD if room_kpi['잔여'] > 0 else C_GOOD),
                ("완료율", f"{r_rate:.1f}%",           _rate_color(r_rate / 100)),
            ])

            st.markdown("---")

            room_summary = get_room_summary(df_room, sel_room, df_mc_all)
            if not room_summary.empty:
                if "_df_reset_rm" not in st.session_state:
                    st.session_state["_df_reset_rm"] = 0
                _rkr = st.session_state["_df_reset_rm"]

                rm_display = room_summary.copy()
                rm_display["상태"] = rm_display["신호등"].apply(lambda v: {"🟢":"🟢","🟡":"🟡","🔴":"🔴","⚪":"⚫"}.get(str(v), "⚫"))
                rm_display["완료율(%)"] = rm_display["완료율(%)"].apply(lambda v: round(float(v),1) if str(v) not in ("-","") else 0.0)
                rm_display = rm_display[["상태","ROOM NAME","총합","완료","잔여","완료율(%)","RM H/O"]]

                rm_selection = st.dataframe(
                    rm_display, hide_index=True, height=450,
                    on_select="rerun", selection_mode="single-row",
                    key=f"rm_df_{_rkr}",
                    column_config={
                        "완료율(%)": st.column_config.ProgressColumn("완료율(%)", min_value=0, max_value=100, format="%.1f%%"),
                        "상태": st.column_config.TextColumn("상태", width=50),
                    }
                )

                # ★ ROOM 행 선택 시 → expander로 과별 탭 펼침
                if rm_selection and rm_selection.selection and rm_selection.selection.rows:
                    sel_idx = rm_selection.selection.rows[0]
                    sel_rm_name = room_summary.iloc[sel_idx]["ROOM NAME"]

                    gwa_data = get_room_by_gwa(df_room, sel_rm_name, df_mc_dict)

                    with st.expander(f"📂 {sel_rm_name} – 과별 현황", expanded=True):
                        if gwa_data:
                            # ★ 전체 탭: 과별 수량/진도율 요약
                            tab_names = ["◆ 전체"] + [f"🔹 {g}" for g in gwa_data.keys()]
                            gwa_tabs = st.tabs(tab_names)

                            # 전체 탭
                            with gwa_tabs[0]:
                                sum_rows = []
                                for gwa_name, gwa_info in gwa_data.items():
                                    g_rate = gwa_info["완료율"]
                                    sum_rows.append({
                                        "과": gwa_name,
                                        "총합": gwa_info["총합"],
                                        "완료": gwa_info["완료"],
                                        "잔여": gwa_info["잔여"],
                                        "완료율(%)": g_rate,
                                    })
                                if sum_rows:
                                    df_sum = pd.DataFrame(sum_rows)
                                    # 합계행 추가
                                    t_total = df_sum["총합"].sum()
                                    t_done = df_sum["완료"].sum()
                                    t_remain = df_sum["잔여"].sum()
                                    t_rate = round(t_done / t_total * 100, 1) if t_total else 0.0
                                    df_sum.loc[len(df_sum)] = {"과": "합계", "총합": t_total, "완료": t_done, "잔여": t_remain, "완료율(%)": t_rate}
                                    st.dataframe(
                                        df_sum, hide_index=True,
                                        column_config={
                                            "완료율(%)": st.column_config.ProgressColumn("완료율(%)", min_value=0, max_value=100, format="%.1f%%"),
                                        }
                                    )

                            # 과별 탭
                            for tab_gwa, (gwa_name, gwa_info) in zip(gwa_tabs[1:], gwa_data.items()):
                                with tab_gwa:
                                    st.markdown(f"**{gwa_name}** — 총합: {gwa_info['총합']}  |  완료: {gwa_info['완료']}  |  잔여: {gwa_info['잔여']}  |  완료율: {gwa_info['완료율']:.1f}%")

                                    detail_gwa = _extract_mc_detail_safe(gwa_info.get("df_mc"))
                                    if detail_gwa is not None and not detail_gwa.empty:
                                        st.dataframe(detail_gwa, hide_index=True, height=300)
                                        st.download_button(
                                            f"📥 {sel_rm_name}_{gwa_name} 다운로드",
                                            _to_excel(detail_gwa),
                                            f"ROOM_{sel_rm_name}_{gwa_name}.xlsx",
                                            key=f"dl_rm_{gwa_name}_{_rkr}"
                                        )
                                    else:
                                        st.info(f"{gwa_name} 매칭 데이터가 없습니다.")
                        else:
                            st.info(f"{sel_rm_name}에 매칭되는 마트 데이터가 없습니다.")
            else:
                st.info("전기실 MC 데이터가 없습니다.")
        else:
            st.markdown(
                '<div style="text-align:center;padding:3rem 0;">'
                '<div style="font-size:1.5rem;margin-bottom:8px;">⚡</div>'
                '<div style="font-size:1rem;color:#94a3b8;">전기실 MC 데이터가 없습니다.</div>'
                '</div>',
                unsafe_allow_html=True
            )  