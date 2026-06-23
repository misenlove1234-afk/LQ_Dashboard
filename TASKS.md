# 공정회의록 작업 목록

> 브랜치: `claude/excel-meeting-log-elimination-dak9zi`  
> 규칙: **같은 파일을 동시에 수정하지 않으면 충돌 없음**  
> 작업 시작 전 반드시 `git pull` / 완료 후 즉시 `git push`

---

## 병렬 작업 구조

```
웹 세션 (여기)          CLI 세션
────────────────        ─────────────────────
사진 첨부 필요 작업      로직/기능 개발
meeting_ref_data.py     meeting_calc.py
proc_2_meeting.py       proc_2.py / proc_2_ref.py
```

---

## 작업 목록

### 🌐 웹 세션 담당 (사진 필요)

| # | 작업 | 파일 | 상태 |
|---|---|---|---|
| W-1 | 블럭-데크 매핑 도면 재검증 (M31OS/M31OP B-DK 등 의심 항목) | `data/meeting_ref_data.py` | ⬜ 대기 |
| W-2 | CONT 블럭 배치 사진 대조 후 매핑 수정 | `data/meeting_ref_data.py` | ⬜ 대기 |
| W-3 | 공정표 UI 스크린샷 보며 레이아웃 개선 | `pages/proc_2_meeting.py` | ⬜ 대기 |
| W-4 | 50STG 소요일 기준 사진 대조 수정 (`_INIT_50STG`) | `data/meeting_ref_data.py` | ⬜ 대기 |

### 💻 CLI 세션 담당 (로직/기능)

| # | 작업 | 파일 | 상태 |
|---|---|---|---|
| C-1 | 계산 엔진 실데이터 테스트 및 디버깅 | `data/meeting_calc.py` | ⬜ 대기 |
| C-2 | 공정표 Excel 다운로드 기능 추가 | `pages/proc_2_meeting.py` | ⬜ 대기 |
| C-3 | 실적 입력 기능 (actual_start/actual_end 컬럼 추가) | `data/meeting_calc.py` | ⬜ 대기 |
| C-4 | 캘린더 관리 UI — 휴일 일괄 등록 기능 | `pages/proc_2_ref.py` | ⬜ 대기 |
| C-5 | 간트 차트 연동 (기존 gantt_editor.html 활용) | `pages/proc_2_meeting.py` | ⬜ 대기 |

---

## 상태 표시 규칙

| 기호 | 의미 |
|---|---|
| ⬜ 대기 | 시작 전 |
| 🔄 진행중 (웹) | 웹 세션 작업 중 — CLI 해당 파일 수정 금지 |
| 🔄 진행중 (CLI) | CLI 세션 작업 중 — 웹 해당 파일 수정 금지 |
| ✅ 완료 | 커밋+푸시 완료 |
| ❌ 보류 | 추가 논의 필요 |

---

## 파일 소유권 (충돌 방지)

| 파일 | 기본 담당 | 비고 |
|---|---|---|
| `data/meeting_ref_data.py` | 웹 세션 | 기준 데이터 수정 = 사진 필요 |
| `data/meeting_calc.py` | CLI 세션 | 계산 로직 |
| `pages/proc_2_meeting.py` | 협의 필요 | 기능(CLI) / UI(웹) 구분 |
| `pages/proc_2_ref.py` | CLI 세션 | |
| `pages/proc_2.py` | CLI 세션 | |

> `proc_2_meeting.py` 는 동시 작업이 필요한 경우 이 파일의 상태를 먼저 확인하고 착수할 것.

---

## 최근 업데이트

| 날짜 | 세션 | 내용 |
|---|---|---|
| 2026-06-23 | 웹 | 공정회의록 탭 UI 완성, 계산 엔진 완성, 블럭-데크 매핑 추가 |
| 2026-06-23 | 웹 | TASKS.md / HANDOFF_meeting_log.md 작성 |
