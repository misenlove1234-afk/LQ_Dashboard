# 엑셀 회의록 없애기 — 인수인계 문서

> 작성일: 2026-06-23  
> 브랜치: `claude/excel-meeting-log-elimination-dak9zi`  
> 이어서 작업 시 반드시 `git pull` 후 해당 브랜치로 체크아웃하여 시작할 것

---

## 1. 프로젝트 목표

엑셀 → 전산 → SQL Server → Streamlit 흐름을 제거하고, **Streamlit ↔ SQL Server 직접 연동**으로 전환.  
핵심 기능: 앵커 이벤트(블럭입고일, 선각검사일 등)를 입력하면 **원클릭으로 전체 공정 일정 자동 계산**.

---

## 2. 완료된 작업 목록

| 커밋 | 내용 |
|---|---|
| `b345d6d` | proc_2에 기준정보 탭 추가 |
| `dde9f38` | 공종시퀀스·데크순서·선각소요일 기준정보 + 앵커 Excel 양식 |
| `c72be77` | 앵커 이벤트 DB 테이블 3개 + Excel 업로드 기능 |
| `935d225` | 블럭-데크 매핑 + Rule 1 방향 수정 + `wall_straight_date` 컬럼 추가 |
| `6e3c19e` | 계산 엔진 `data/meeting_calc.py` 신규 작성 |
| `da03164` | proc_2에 공정회의록 탭 추가 + 기준정보 탭 들여쓰기 버그 수정 |

---

## 3. 관련 파일 목록

```
data/
  meeting_ref_data.py   # 기준정보 데이터 레이어 (1066줄)
  meeting_calc.py       # 계산 엔진 (503줄)

pages/
  proc_2.py             # 메인 페이지 — TAB_OPTIONS에 "공정회의록" 추가됨 (1152줄)
  proc_2_ref.py         # 기준정보 탭 UI
  proc_2_meeting.py     # 공정회의록 탭 UI (403줄, 신규)
```

---

## 4. DB 테이블 구조

> 모든 테이블은 `data/meeting_ref_data.py` 의 `init_tables()` 호출 시 자동 생성됨.

| 테이블명 | 용도 |
|---|---|
| `lq_meet_ref_30stg` | 30STG 블럭별 공종 소요일 기준 |
| `lq_meet_ref_50stg` | 50STG 데크별 공종 소요일 기준 |
| `lq_meet_ref_inout` | In/Outside 공종 소요일 기준 |
| `lq_meet_ref_sequence` | 공종 실행 순서 및 캘린더 타입 |
| `lq_meet_ref_deck_order` | 데크 순서 (UPP=1, NAV=최대) |
| `lq_meet_ref_calendar` | 비작업일(휴일) 목록 |
| `lq_meet_ref_rules` | 로직 규칙 (Rule 1~6) |
| `lq_meet_ref_vessels` | 호선 목록 (vessel_no, vessel_type) |
| `lq_meet_anchor_30stg` | 블럭별 앵커: blk_in_date / blk_out_date |
| `lq_meet_anchor_50stg` | 데크별 앵커: mount_start_date / inspection_plan / inspection_actual / **wall_straight_date** |
| `lq_meet_ref_block_deck` | 블럭 → 데크 매핑 |
| `lq_meet_schedule` | 계산 결과 저장 (stg, area, work_code, plan_start, plan_end) |

### lq_meet_anchor_50stg 컬럼 (중요)

```sql
vessel_no         NVARCHAR(20)
deck              NVARCHAR(20)
mount_start_date  DATE          -- 블럭탑재일 (수기)
inspection_plan   DATE          -- 선각검사 계획 (수기)
inspection_actual DATE          -- 선각검사 실적 (수기)
wall_straight_date DATE         -- 선각WALL곡직완료일 (수기) ← 트렁크배선 착수 트리거
```

---

## 5. 계산 엔진 알고리즘 (`data/meeting_calc.py`)

### 5-1. 캘린더 규칙

- **작업일**: 월~토 (일요일 + 휴일 제외)
- **B/P검사**: 주중만 (월~금, `weekday_only=True`)
- `add_working_days(start, days)`: start 당일이 1일차. `days=3, start=월 → 수`

### 5-2. 30 STG 계산 (`calc_30stg`)

```
입력: lq_meet_anchor_30stg (blk_in_date / blk_out_date)
출력: {block_no: {work_code: (start, end)}}

공종 순서 (lq_meet_ref_sequence 참조):
  blk_in(앵커) → 족장설치(1일, 예외블럭 있음) → 관철 → 덕트 → 전장 → 도장 → 배선 → 뒤집기(1일) → blk_out(앵커)
```

### 5-3. In/Outside 계산 (`calc_inout`)

```
트리거: wall_straight_date (LNG→D-DK, CONT→F-DK)
공종 순서:
  트렁크배선 → 윈도우설치 → 윈도우검사 → 내부배관검사 →
  외부배관검사 → 외판도장 → 외판족장철거 → FLOOR도장 →
  탑재준비 → 탑재사열 → 인양 → 탑재
```

### 5-4. 50 STG 계산 (`calc_50stg`)

```
입력 앵커: 선각검사일 (실적 우선, 없으면 계획) per deck
시작점: UPP-DK 제외. A-DK부터 NAV-DK까지.

알고리즘:
  for 공종(목의화기1차 → 스커트 순서):
    for 데크(UPP-DK 제외, A-DK → NAV-DK 순):
      제약(배타적, start > date) 수집:
        - 동일 데크 이전 공종 완료일
        - Rule 4(계단식): 하부 데크 동일 공종 완료일
        - Rule 2(배선): 트렁크배선 완료일
      제약(포함적, start >= date) 수집:
        - Rule 1(도장PB): 상부 데크 목의화기1차 종료-2 작업일
      시작일 = max(배타적 후 첫 작업일, 포함적 작업일)

※ 외부 루프=공종, 내부 루프=데크 순서가 핵심:
  Rule 1에서 상부 데크 목의화기1차가 먼저 계산되어 있어야 하부 도장PB 제약을 적용 가능
```

### 5-5. 로직 규칙 상세

| Rule | 설명 | 방향 | 제약 타입 |
|---|---|---|---|
| Rule 1 | **상부** 데크 목의화기1차 종료 -2 작업일 → **하부** 데크 도장PB 착수 가능 | upper→lower | 포함적 (start >=) |
| Rule 2 | 트렁크배선 완료 → 전 데크 배선 착수 가능 | in_outside→all_deck | 배타적 (start >) |
| Rule 3 | 선각검사 완료 → 동 데크 목의화기1차 착수 | anchor 기반 (자동 적용) | 배타적 |
| Rule 4 | 하부 데크 동일공종 완료 → 상부 데크 동일공종 착수 | lower→upper | 배타적 (start >) |
| Rule 5 | LNG D-DK wall_straight_date → 트렁크배선 착수 | anchor 기반 | - |
| Rule 6 | CONT F-DK wall_straight_date → 트렁크배선 착수 | anchor 기반 | - |

---

## 6. UI 구조 (`pages/proc_2_meeting.py`)

```
render_meeting_tab(current_user, is_admin)
  ├── 호선 선택 (selectbox)
  ├── 원클릭 계산 버튼 (관리자만 활성화) → calc_and_save(vessel_no)
  ├── 앵커 현황 지표 4개 (블럭입고, 블럭탑재, 선각검사, WALL곡직)
  └── 서브 탭
        ├── ⚙️ 30 STG  → _make_30stg_table()   데크 구분선 포함
        ├── 🏗️ 50 STG  → _make_50stg_table()   UPP-DK = "—"
        └── 🔌 In/Outside → _make_inout_table()
```

#### 색상 코딩
- 과거 (완료): `background: #1a2535`
- 진행 중: `background: #1e3a5f`
- 예정: 배경 없음 (투명)

---

## 7. 블럭-데크 매핑

### LNG (21 블럭)

| 데크 | 블럭 |
|---|---|
| UPP-DK | M120S, M120P, M110S, M110P |
| A-DK | M220S, M220P, M210S, M210P |
| B-DK | M31NS, M31NP, M31OS, M31OP |
| C-DK | M410S, M410P |
| D-DK | M610C, M510S, M510P |
| NAV-DK | M51NS, M51NP, M900S, M900P |

### CONT (28 블럭)

| 데크 | 블럭 |
|---|---|
| UPP-DK | M110S, M110P |
| A-DK | M220S, M220P, M210S, M210P, M120S, M120P |
| B-DK | M320S, M320P, M310S, M310P |
| C-DK | M410S, M410P |
| D-DK | M510S, M510P |
| E-DK | M610S, M610P |
| F-DK | M710S, M710P |
| NAV-DK | M940S, M930P, M920S, M920P, M910S, M910P, M900S, M900P |

---

## 8. 앵커 Excel 업로드 양식

`기준정보 탭 → 앵커 이벤트` 에서 양식 다운로드/업로드 가능.

### 30STG_앵커 시트 컬럼 순서
`vessel_no | vessel_type | block_no | blk_in_date | blk_out_date`

### 50STG_앵커 시트 컬럼 순서
`vessel_no | vessel_type | deck | mount_start_date | inspection_plan | inspection_actual | inspection_status | wall_straight_date`

날짜 컬럼: 30STG=[4,5], 50STG=[4,5,6,8] (1-based 인덱스)

---

## 9. 남은 작업 / 개선 포인트

### 즉시 가능한 개선

1. **공정표 PDF/Excel 다운로드**  
   현재 HTML 테이블만 표시. `st.download_button`으로 Excel 출력 추가 가능.
   ```python
   # pages/proc_2_meeting.py 의 각 서브탭 하단에 추가
   df_30 = sched_df[sched_df["stg"] == "30"]
   st.download_button("📥 30STG 다운로드", df_30.to_csv(index=False).encode("utf-8-sig"), "30stg.csv")
   ```

2. **간트 차트 시각화**  
   현재 표 형태만. `proc_2_data.py` 의 기존 간트 로직(`assets/gantt_editor.html`) 참고하여 추가 가능.

3. **실적 입력 기능**  
   현재는 계획(plan_start, plan_end)만 저장. `actual_start`, `actual_end` 컬럼 추가 후 편집 UI 구현 가능.

4. **블럭-데크 매핑 검증 필요**  
   M31OS/M31OP → B-DK 배치가 실제 도면과 맞는지 담당자 확인 필요.

### 확인 필요 사항

- `lq_meet_ref_vessels` 테이블에 호선 데이터가 등록되어 있어야 공정회의록 탭 작동  
  → `기준정보 탭 → 앵커 이벤트`에서 Excel 업로드 시 자동 등록됨
- `lq_meet_ref_calendar` 에 연간 휴일 데이터 등록 필요  
  → 미등록 시 일요일만 제외하고 계산됨 (토요일은 작업일로 처리)

---

## 10. 이어서 작업하는 방법

```bash
# 1. 브랜치 체크아웃
git checkout claude/excel-meeting-log-elimination-dak9zi
git pull

# 2. 앱 실행
streamlit run app.py

# 3. 공정회의록 탭 접근 경로
#    사이드바 → "사곡공장 선실 제작 현황" → 상단 탭 → "공정회의록"

# 4. 첫 실행 시 필요한 작업 순서
#    기준정보 탭 → 기준 파일 초기화(버튼) → 앵커 이벤트 Excel 업로드 → 공정회의록 탭 → 원클릭 계산
```

### 주요 함수 진입점

| 작업 | 함수 | 파일 |
|---|---|---|
| DB 초기화 (기준정보) | `init_tables()` | `data/meeting_ref_data.py` |
| DB 초기화 (일정) | `init_schedule_table()` | `data/meeting_calc.py` |
| 전체 계산 + 저장 | `calc_and_save(vessel_no)` | `data/meeting_calc.py` |
| 계산 결과 조회 | `get_schedule(vessel_no)` | `data/meeting_calc.py` |
| 앵커 Excel 업로드 | `upload_anchor_excel(file)` | `data/meeting_ref_data.py` |
| 기준정보 UI | `render_ref_tab()` | `pages/proc_2_ref.py` |
| 공정회의록 UI | `render_meeting_tab(user, is_admin)` | `pages/proc_2_meeting.py` |

---

## 11. 코딩 주의사항 (CLAUDE.md 요약)

- 모든 응답과 커밋 메시지는 **한국어**
- DB 접속 정보 하드코딩 절대 금지 → `.env` 에서만 로드
- 예외 처리: `st.error("관리자에게 문의")` 만 표시, `st.exception()` 금지
- 외부 CDN/폰트 URL 사용 금지 (사내망 차단)
- 커밋 전 `.env`, `__pycache__/` 제외 확인
- `git add .` 사용 금지 → 파일명 직접 지정

---

*이 문서 자체는 커밋 대상에서 제외해도 무방합니다. 작업 완료 후 삭제하세요.*
