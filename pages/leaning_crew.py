"""
╔══════════════════════════════════════════════════════════════════╗
║  항목 : [화면 전용] leaning_crew - Leaning Crew 팀 소개          ║
║  형식 : 매거진 스타일 정적 HTML 페이지                             ║
╚══════════════════════════════════════════════════════════════════╝
"""

import streamlit as st

_CSS = """
<style>
/* ── 페이지 전체 배경 ── */
.lc-wrap {
    max-width: 900px;
    margin: 0 auto;
    padding: 0 1rem 4rem;
    font-family: 'Malgun Gothic', '맑은 고딕', sans-serif;
    color: #E2E8F0;
}

/* ── 헤더 배너 ── */
.lc-banner {
    background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 50%, #0c2340 100%);
    border: 1px solid rgba(56,189,248,0.3);
    border-radius: 16px;
    padding: 2.2rem 2.5rem;
    margin-bottom: 2rem;
    position: relative;
    overflow: hidden;
}
.lc-banner::before {
    content: '';
    position: absolute;
    top: -40px; right: -40px;
    width: 200px; height: 200px;
    background: radial-gradient(circle, rgba(56,189,248,0.12) 0%, transparent 70%);
    border-radius: 50%;
}
.lc-tag {
    display: inline-block;
    background: rgba(56,189,248,0.15);
    border: 1px solid rgba(56,189,248,0.4);
    color: #38BDF8;
    font-size: 0.78rem;
    font-weight: 700;
    letter-spacing: 0.12em;
    padding: 0.25rem 0.8rem;
    border-radius: 20px;
    margin-bottom: 0.9rem;
    text-transform: uppercase;
}
.lc-banner-title {
    font-size: 1.9rem;
    font-weight: 900;
    color: #FFFFFF;
    line-height: 1.25;
    margin: 0.3rem 0 0.7rem;
}
.lc-banner-title span { color: #38BDF8; }
.lc-banner-sub {
    font-size: 0.88rem;
    color: #94A3B8;
    line-height: 1.7;
}

/* ── Q 섹션 카드 ── */
.lc-q-card {
    background: linear-gradient(145deg, rgba(15,23,42,0.85), rgba(10,18,40,0.95));
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 14px;
    padding: 1.8rem 2rem;
    margin-bottom: 1.4rem;
    position: relative;
}
.lc-q-label {
    font-size: 0.72rem;
    font-weight: 800;
    letter-spacing: 0.18em;
    color: #38BDF8;
    text-transform: uppercase;
    margin-bottom: 0.3rem;
}
.lc-q-title {
    font-size: 1.25rem;
    font-weight: 800;
    color: #FFFFFF;
    margin-bottom: 1.3rem;
    padding-bottom: 0.8rem;
    border-bottom: 1px solid rgba(56,189,248,0.2);
}

/* ── 팀명/비전 박스 ── */
.lc-team-name-box {
    background: rgba(56,189,248,0.08);
    border-left: 4px solid #38BDF8;
    border-radius: 0 10px 10px 0;
    padding: 1rem 1.4rem;
    margin-bottom: 1.2rem;
}
.lc-team-name-box .name {
    font-size: 1.4rem;
    font-weight: 900;
    color: #38BDF8;
    letter-spacing: 0.04em;
}
.lc-team-name-box .name-sub {
    font-size: 0.82rem;
    color: #94A3B8;
    margin-top: 0.3rem;
    line-height: 1.5;
}

/* ── 스킬 뱃지 ── */
.lc-skill-row {
    display: flex; gap: 0.6rem; flex-wrap: wrap; margin-bottom: 1.2rem;
}
.lc-skill-badge {
    background: rgba(30,41,59,0.8);
    border: 1px solid rgba(56,189,248,0.25);
    color: #CBD5E1;
    padding: 0.35rem 0.9rem;
    border-radius: 20px;
    font-size: 0.82rem;
    font-weight: 600;
}

/* ── 비전 아이템 ── */
.lc-vision-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.85rem;
}
.lc-vision-item {
    background: rgba(15,35,65,0.6);
    border: 1px solid rgba(56,189,248,0.15);
    border-radius: 10px;
    padding: 0.9rem 1.1rem;
    display: flex; align-items: flex-start; gap: 0.75rem;
}
.lc-vision-num {
    background: rgba(56,189,248,0.15);
    color: #38BDF8;
    border-radius: 50%;
    width: 26px; height: 26px;
    display: flex; align-items: center; justify-content: center;
    font-size: 0.8rem; font-weight: 800;
    flex-shrink: 0;
}
.lc-vision-text { font-size: 0.84rem; color: #CBD5E1; line-height: 1.5; }
.lc-vision-text strong { color: #E2E8F0; }

/* ── 전략 아이템 ── */
.lc-strategy-item {
    display: flex; align-items: flex-start; gap: 1rem;
    padding: 0.9rem 0;
    border-bottom: 1px solid rgba(255,255,255,0.05);
}
.lc-strategy-item:last-child { border-bottom: none; }
.lc-strategy-icon {
    font-size: 1.5rem;
    flex-shrink: 0;
    width: 2.2rem;
    text-align: center;
    margin-top: 0.1rem;
}
.lc-strategy-content { flex: 1; }
.lc-strategy-title {
    font-size: 0.95rem; font-weight: 700; color: #F1F5F9;
    margin-bottom: 0.25rem;
}
.lc-strategy-desc { font-size: 0.83rem; color: #94A3B8; line-height: 1.55; }

/* ── 실행 프로세스 스텝 ── */
.lc-step-row {
    display: flex; gap: 0; margin-bottom: 0.3rem;
}
.lc-step {
    flex: 1;
    text-align: center;
    position: relative;
}
.lc-step:not(:last-child)::after {
    content: '→';
    position: absolute;
    right: -0.5rem;
    top: 1.1rem;
    color: #38BDF8;
    font-size: 1rem;
    font-weight: 700;
}
.lc-step-circle {
    width: 2.2rem; height: 2.2rem;
    background: rgba(56,189,248,0.12);
    border: 2px solid rgba(56,189,248,0.4);
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    margin: 0 auto 0.5rem;
    color: #38BDF8; font-size: 0.85rem; font-weight: 800;
}
.lc-step-label {
    font-size: 0.78rem; font-weight: 700; color: #CBD5E1;
    margin-bottom: 0.3rem;
}
.lc-step-desc {
    font-size: 0.72rem; color: #64748B; line-height: 1.45;
    padding: 0 0.3rem;
}

.lc-detail-box {
    background: rgba(15,25,50,0.6);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 10px;
    padding: 1.1rem 1.4rem;
    margin-top: 1rem;
}
.lc-detail-box .dt { font-size: 0.82rem; font-weight: 700; color: #F1F5F9; margin-bottom: 0.4rem; }
.lc-detail-box .dd { font-size: 0.82rem; color: #94A3B8; line-height: 1.6; margin-left: 0.5rem; }

/* ── 로드맵 타임라인 ── */
.lc-roadmap {
    position: relative;
    padding-left: 1.8rem;
}
.lc-roadmap::before {
    content: '';
    position: absolute; left: 0.55rem; top: 0; bottom: 0;
    width: 2px;
    background: linear-gradient(180deg, #38BDF8 0%, rgba(56,189,248,0.1) 100%);
    border-radius: 2px;
}
.lc-phase {
    position: relative;
    margin-bottom: 1.4rem;
}
.lc-phase::before {
    content: '';
    position: absolute;
    left: -1.5rem; top: 0.6rem;
    width: 12px; height: 12px;
    background: #38BDF8;
    border-radius: 50%;
    box-shadow: 0 0 10px rgba(56,189,248,0.5);
}
.lc-phase-header {
    display: flex; align-items: center; gap: 0.75rem;
    margin-bottom: 0.5rem;
}
.lc-phase-tag {
    background: rgba(56,189,248,0.12);
    border: 1px solid rgba(56,189,248,0.3);
    color: #38BDF8;
    font-size: 0.72rem; font-weight: 800;
    padding: 0.15rem 0.6rem;
    border-radius: 10px;
    letter-spacing: 0.05em;
}
.lc-phase-title {
    font-size: 0.95rem; font-weight: 700; color: #E2E8F0;
}
.lc-phase-items {
    display: flex; flex-wrap: wrap; gap: 0.45rem; margin-top: 0.4rem;
}
.lc-phase-chip {
    background: rgba(30,41,59,0.7);
    border: 1px solid rgba(255,255,255,0.08);
    color: #94A3B8;
    font-size: 0.78rem;
    padding: 0.2rem 0.65rem;
    border-radius: 12px;
}
.lc-phase:first-child .lc-phase-chip {
    border-color: rgba(56,189,248,0.2);
    color: #7DD3FC;
}
.lc-phase:first-child .lc-phase-tag {
    background: rgba(56,189,248,0.2);
    border-color: rgba(56,189,248,0.5);
}

/* ── 인용 박스 ── */
.lc-quote {
    background: rgba(56,189,248,0.05);
    border: 1px solid rgba(56,189,248,0.18);
    border-radius: 10px;
    padding: 1rem 1.4rem;
    margin-top: 1rem;
    font-size: 0.85rem;
    color: #94A3B8;
    line-height: 1.65;
    font-style: italic;
}
.lc-quote strong { color: #38BDF8; font-style: normal; }
</style>
"""


def render():
    st.markdown(_CSS, unsafe_allow_html=True)

    st.markdown("""
<div class="lc-wrap">

  <!-- ── 헤더 배너 ── -->
  <div class="lc-banner">
    <div class="lc-tag">함께하는 DX문화 · 의장팀 선실부</div>
    <div class="lc-banner-title">선실부 '<span>Leaning Crew</span>'를<br>소개합니다.</div>
    <div class="lc-banner-sub">
      거주구(Crew Quarter)를 직접 만드는 사람들이 데이터로 일하는 방식을 바꿉니다.<br>
      의장·전장·도장·선각, 조선의 모든 스킬이 모인 부서에서 시작된 작은 혁신 이야기.
    </div>
  </div>

  <!-- ═══════════════════════════════════════ -->
  <!--  Q1. 팀 소개 & DT 비전                 -->
  <!-- ═══════════════════════════════════════ -->
  <div class="lc-q-card">
    <div class="lc-q-label">Q1</div>
    <div class="lc-q-title">팀 소개 &amp; DT 비전</div>

    <div class="lc-team-name-box">
      <div class="name">Leaning Crew</div>
      <div class="name-sub">
        <b>Lean</b>(낭비 제거·지속 개선) + <b>Crew</b>(우리가 만드는 거주구, Crew Quarter)<br>
        낭비 없는 공정으로 최고의 거주구를 만드는 팀이라는 의미를 담았습니다.
      </div>
    </div>

    <div style="font-size:0.85rem; color:#94A3B8; line-height:1.7; margin-bottom:1.1rem;">
      의장팀 선실부는 선박의 <b style="color:#E2E8F0;">거주구(Crew Quarter)</b>를 처음부터 끝까지 전담하는 부서입니다.
      단순 조립이 아닌, 아래의 모든 공종이 한 지붕 아래 협력합니다.
    </div>

    <div class="lc-skill-row">
      <span class="lc-skill-badge">⚙️ 의장</span>
      <span class="lc-skill-badge">⚡ 전장</span>
      <span class="lc-skill-badge">🎨 도장</span>
      <span class="lc-skill-badge">🔩 선각</span>
    </div>

    <div style="font-size:0.85rem; color:#94A3B8; line-height:1.7; margin-bottom:1.2rem;">
      이처럼 다양한 공종이 집결된 부서 특성상, 공정 간 연계·병목·리스크를 한 눈에
      파악할 수 있는 통합 데이터 도구의 필요성을 절감했습니다.
      그 해답으로 탄생한 것이 바로 <b style="color:#38BDF8;">LQ All In One 대시보드</b>입니다.
    </div>

    <div style="font-size:0.88rem; font-weight:700; color:#E2E8F0; margin-bottom:0.8rem;">📌 DT 비전 — 4가지 방향</div>
    <div class="lc-vision-grid">
      <div class="lc-vision-item">
        <div class="lc-vision-num">1</div>
        <div class="lc-vision-text">
          <strong>자동화</strong><br>
          반복·수동 업무를 자동화해 사람이 고부가가치 의사결정에 집중
        </div>
      </div>
      <div class="lc-vision-item">
        <div class="lc-vision-num">2</div>
        <div class="lc-vision-text">
          <strong>데이터 통합</strong><br>
          산재된 공정 데이터를 DB로 집중하여 분석 가능한 자산으로 전환
        </div>
      </div>
      <div class="lc-vision-item">
        <div class="lc-vision-num">3</div>
        <div class="lc-vision-text">
          <strong>선제 대응</strong><br>
          공정 리스크를 사전에 감지하고 선제 조치로 돌관작업 최소화
        </div>
      </div>
      <div class="lc-vision-item">
        <div class="lc-vision-num">4</div>
        <div class="lc-vision-text">
          <strong>노하우 체계화</strong><br>
          현장 경험과 공정 판단을 데이터로 보강하여 조직 지식으로 축적
        </div>
      </div>
    </div>
  </div>

  <!-- ═══════════════════════════════════════ -->
  <!--  Q2. 문화&조직 활성화 전략              -->
  <!-- ═══════════════════════════════════════ -->
  <div class="lc-q-card">
    <div class="lc-q-label">Q2</div>
    <div class="lc-q-title">문화 &amp; 조직 활성화 전략</div>

    <div class="lc-strategy-item">
      <div class="lc-strategy-icon">📊</div>
      <div class="lc-strategy-content">
        <div class="lc-strategy-title">Data-First 문화</div>
        <div class="lc-strategy-desc">
          보고서 대신 대시보드, 감(感) 대신 데이터로 판단하는 문화를 목표로 합니다.
          현장 관리자도 클릭 한 번으로 KPI·공정 현황을 바로 확인할 수 있도록
          비전문가 친화적 UI를 최우선으로 설계합니다.
        </div>
      </div>
    </div>

    <div class="lc-strategy-item">
      <div class="lc-strategy-icon">🔗</div>
      <div class="lc-strategy-content">
        <div class="lc-strategy-title">멀티스킬 강점 활용</div>
        <div class="lc-strategy-desc">
          의장·전장·도장·선각이 한 부서에 있다는 점을 역으로 활용합니다.
          개별 공종 화면이 아닌 <b style="color:#E2E8F0;">거주구 전 공정을 통합한 하나의 뷰</b>를 제공해,
          공정 간 연계 리스크와 병목을 즉시 파악합니다.
        </div>
      </div>
    </div>

    <div class="lc-strategy-item">
      <div class="lc-strategy-icon">⚡</div>
      <div class="lc-strategy-content">
        <div class="lc-strategy-title">Quick Win → 신뢰 구축</div>
        <div class="lc-strategy-desc">
          거창한 시스템보다 "오늘 당장 쓸 수 있는 화면" 부터 개발합니다.
          빠른 성과물로 구성원 신뢰를 쌓고, 이를 바탕으로 자발적 데이터 입력 문화를 형성합니다.
          작은 성공 → 확산 → 더 큰 도전이라는 선순환을 만들어 갑니다.
        </div>
      </div>
    </div>

    <div class="lc-strategy-item">
      <div class="lc-strategy-icon">📚</div>
      <div class="lc-strategy-content">
        <div class="lc-strategy-title">학습 커뮤니티</div>
        <div class="lc-strategy-desc">
          Leaning Crew는 도구 개발에 그치지 않고, 팀 전체의 디지털 역량을 키우는
          학습 공동체를 지향합니다.
          사례 공유·코드 리뷰·현업 문제 해결 스터디를 통해 부서 전체가 함께 성장합니다.
        </div>
      </div>
    </div>
  </div>

  <!-- ═══════════════════════════════════════ -->
  <!--  Q3. 기술습득과 실행 과정              -->
  <!-- ═══════════════════════════════════════ -->
  <div class="lc-q-card">
    <div class="lc-q-label">Q3</div>
    <div class="lc-q-title">기술습득과 실행 과정</div>

    <div style="font-size:0.85rem; color:#94A3B8; line-height:1.7; margin-bottom:1.2rem;">
      시스템 구축 전문가가 아닌, 현업 담당자가 직접 만든다는 것이 Leaning Crew의 핵심입니다.
      문제를 가장 잘 아는 사람이 직접 해결 도구를 만들 때 진짜 가치 있는 결과물이 나옵니다.
    </div>

    <div class="lc-step-row">
      <div class="lc-step">
        <div class="lc-step-circle">1</div>
        <div class="lc-step-label">Pain Point 발굴</div>
        <div class="lc-step-desc">수동 집계·보고, 공정 파악 지연, 데이터 산재</div>
      </div>
      <div class="lc-step">
        <div class="lc-step-circle">2</div>
        <div class="lc-step-label">기술 학습</div>
        <div class="lc-step-desc">Python, Pandas, Streamlit, SQL 자기주도 학습</div>
      </div>
      <div class="lc-step">
        <div class="lc-step-circle">3</div>
        <div class="lc-step-label">개발·배포</div>
        <div class="lc-step-desc">LQ All In One 대시보드 사내망 배포</div>
      </div>
      <div class="lc-step">
        <div class="lc-step-circle">4</div>
        <div class="lc-step-label">피드백·고도화</div>
        <div class="lc-step-desc">현장 의견 반영, 기능 확장 지속</div>
      </div>
    </div>

    <div class="lc-detail-box">
      <div class="dt">🛠️ LQ All In One 대시보드 — 현재 제공 기능</div>
      <div class="dd">
        • <b style="color:#E2E8F0;">공정 현황</b> : 사곡 거주구 제작 간트·지연 목록, 특수선 공정 진도율<br>
        • <b style="color:#E2E8F0;">작업 관리</b> : 일일 작업허가서 미출력·밀폐작업 현황 실시간 조회<br>
        • <b style="color:#E2E8F0;">자재 현황</b> : 전장 결선 자재 입고율·미입고 품목 추적<br>
        • <b style="color:#E2E8F0;">KPI 통합</b> : 직영 능률·BEP 실적·협력사 전망 등 7개 KPI 통합
      </div>
    </div>

    <div class="lc-quote">
      "가장 좋은 시스템은 비싼 SI 프로젝트가 아니라, 현장을 아는 사람이
      <strong>실제 필요한 것</strong>만 담아 만든 도구입니다."
    </div>
  </div>

  <!-- ═══════════════════════════════════════ -->
  <!--  Q4. 미래 방향 로드맵                   -->
  <!-- ═══════════════════════════════════════ -->
  <div class="lc-q-card">
    <div class="lc-q-label">Q4</div>
    <div class="lc-q-title">미래 방향 로드맵</div>

    <div style="font-size:0.85rem; color:#94A3B8; line-height:1.7; margin-bottom:1.4rem;">
      LQ All In One은 끝이 아니라 시작입니다. 데이터로 일하는 방식이 자리 잡으면,
      다음 단계로 나아갈 준비가 됩니다.
    </div>

    <div class="lc-roadmap">

      <div class="lc-phase">
        <div class="lc-phase-header">
          <span class="lc-phase-tag">Phase 1 · 현재</span>
          <span class="lc-phase-title">데이터 시각화 — 보는 것부터</span>
        </div>
        <div class="lc-phase-items">
          <span class="lc-phase-chip">공정 현황 통합 대시보드</span>
          <span class="lc-phase-chip">KPI 실시간 조회</span>
          <span class="lc-phase-chip">작업허가서 미출력 모니터링</span>
          <span class="lc-phase-chip">자재 입고율 추적</span>
        </div>
      </div>

      <div class="lc-phase">
        <div class="lc-phase-header">
          <span class="lc-phase-tag">Phase 2 · 단기</span>
          <span class="lc-phase-title">자동화 &amp; 알림 — 일이 나를 찾아오게</span>
        </div>
        <div class="lc-phase-items">
          <span class="lc-phase-chip">공정 지연 자동 알림</span>
          <span class="lc-phase-chip">데이터 입력 자동화</span>
          <span class="lc-phase-chip">일일 리포트 자동 생성</span>
          <span class="lc-phase-chip">이상치 자동 감지</span>
        </div>
      </div>

      <div class="lc-phase">
        <div class="lc-phase-header">
          <span class="lc-phase-tag">Phase 3 · 중장기</span>
          <span class="lc-phase-title">예측 &amp; 최적화 — 미래를 먼저 보는 팀</span>
        </div>
        <div class="lc-phase-items">
          <span class="lc-phase-chip">AI 기반 공정 완료일 예측</span>
          <span class="lc-phase-chip">자원 배분 최적화 제안</span>
          <span class="lc-phase-chip">선박별 리스크 스코어링</span>
          <span class="lc-phase-chip">타 부서·전사 확산</span>
        </div>
      </div>

    </div>

    <div class="lc-quote" style="margin-top:1.5rem;">
      "DX는 IT 부서만의 일이 아닙니다. 거주구를 가장 잘 아는 우리가 직접 만들고,
      직접 바꾸는 것 — 그것이 <strong>진짜 현장 DX</strong>입니다."
    </div>
  </div>

</div>
""", unsafe_allow_html=True)
