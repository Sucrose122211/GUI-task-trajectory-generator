---
name: gui-trajectory-usage
description: Explain the GUI Task Trajectory Generator workflow step by step in Korean for a coordinator or worker. Use for /사용법 담당자, /사용법 팀원, or requests for this repository's role-specific usage guide.
---

# 역할별 사용법

이 스킬은 GUI Task Trajectory Generator의 사용법을 설명한다. `/사용법` 요청은 안내 요청이다. 명령을 실행하거나 생성, 업로드, 파일 변경을 시작하지 않는다. 사용자가 따로 실행을 요청하면 그 요청의 작업 범위에 따라 저장소의 실행 매뉴얼을 사용한다.

## 역할 선택

- `담당자` 또는 `coordinator`: [담당자 절차](references/coordinator.md)를 처음부터 끝까지 읽는다.
- `팀원` 또는 `worker`: [팀원 절차](references/worker.md)를 처음부터 끝까지 읽는다.
- 역할이 없거나 다른 역할이면 `담당자와 팀원 중 어느 역할의 사용법이 필요한가요?`라고 한 번 묻는다. 두 절차를 모두 출력하지 않는다.
- `/사용법 담당자`, `/사용법 팀원`, `$gui-trajectory-usage 담당자`, `$gui-trajectory-usage 팀원`을 같은 역할 선택으로 해석한다. Claude 진입점이 전달한 인자도 같은 방식으로 해석한다.

## 답변 방식

한국어로 선택한 역할의 전체 순서를 번호로 설명한다. 각 단계에 수행하는 사람, 목적, 복사 가능한 명령어, 만들어지는 파일 또는 확인할 결과를 포함한다. 문서 링크만 전달하지 않는다.

대화에 실제 경로, 교사, 팀원 수, 제출 위치가 있으면 반영한다. 없으면 담당자 1명과 팀원 3명, A의 Codex 작업을 예시로 명확하게 표시한다. 설명을 위해 데이터셋이나 모델을 임의로 확정하지 않는다. 안내 요청에서는 미정 사항 때문에 설명을 중단하거나 불필요한 추가 질문을 하지 않는다.

기본 절차는 Google Sheets 자동 배정이다. 팀원에게 시트, 담당자 칸, 완료 표시나 점수 CSV 편집을 요구하지 않는다. 기존 수동 ZIP 배분은 사용자가 그 방식을 지정했을 때만 안내한다.

현재 저장소를 읽을 수 있으면 명령과 옵션은 `src/gui_trajectory/cli.py`, `src/gui_trajectory/team.py` 및 `docs/pipeline-usage.md`와 대조한다. 안내만을 위해 Docker 빌드, 인증 확인, 생성 또는 외부 조회를 실행할 필요는 없다. 저장소가 없어도 이 스킬에 포함된 절차로 안내할 수 있다.

사용자의 앞선 단계 설명 요청에 맞춰 전체 흐름을 보여준다. `다음 단계`처럼 진행 위치를 묻는 요청이면 이미 끝난 단계를 반복하지 말고 현재 위치부터 안내한다. 문서화된 순서와 사용자가 실제 수행한 결과를 구분하고, 실행하지 않은 작업을 완료했다고 말하지 않는다.

## 반드시 정확하게 설명할 동작

- 프로그램은 GitHub clone/pull로 받고, 공통 전체 데이터와 campaign으로 join/acquire한다. 배정과 진행 기록은 프로그램이 갱신한다. 원본과 결과는 Git에서 제외한다.
- `./team run`과 `./pipeline generate`(dry-run 제외)는 실제 교사를 호출한다. `plan`은 호출 없는 입력 검사다.
- `./team submit`은 로컬 ZIP 생성이며 공유 배정에서는 파일명과 완료 상태도 자동 기록한다. 실제 파일 업로드는 별도다. submitted는 수령이나 사람 검수 완료가 아니다.
- 제출 ZIP의 내부 루트는 생성할 때의 ZIP 파일명에서 확장자를 뺀 이름이다. 받은 ZIP만 이름을 바꿔도 내부 폴더명은 바뀌지 않는다.
- 사람의 점수 CSV는 자동 병합되지 않는다. 담당자가 병합 후 최종 검수하는 흐름을 기본으로 안내한다.
- 병합 manifest는 제출 폴더의 이미지를 참조하므로 `runs/incoming/`을 유지한다.
- ScreenSpot-v2는 `pilot_dev`다. 채택 점수와 `accept`를 임의로 채우지 않는다. export는 후속 학습 후보 생성이며 학생 모델 SFT 실행이 아니다.
