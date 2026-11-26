# 담당자 사용법

기본은 공통 전체 데이터, 시드로 고정한 campaign과 공유 시트 자동 배정이다. 입력을 팀원별 ZIP으로 미리 나누거나 진행표를 직접 관리할 필요가 없다. 팀원이 문서를 편집하는 단계를 요구하지 않는다.

## 1. 저장소와 데이터 준비

Linux 또는 WSL에서 저장소를 clone하고 team setup --backend local을 실행한다. Git 커밋을 기록하고 모두 같은 코드 버전을 사용한다. Docker 방식도 지원한다. 이번 데이터셋은 ScreenSpot-v2 전체 유효 입력 1,271건, revision 5efbb1f1b5463a575f2eb7bc30fe29e49c15f93c로 정해졌다. seed 42와 batch-count 8을 사용한다. 초기 30건 표본은 이번 작업 범위가 아니다. ScreenSpot-v2는 pilot_dev로 유지한다. docs/screenspot-team-run.md의 고정 명령으로 전체 데이터를 다운로드하고 변환한다. 팀원도 같은 원본과 명령으로 전체 manifest를 준비한다.

## 2. 공유 시트 최초 설정

기존 배포와 연결 확인이 끝났으면 이 절을 반복하지 않고 새 campaign 등록으로 진행한다. 이번 로컬 분할 옵션 변경에 Apps Script 재배포는 필요 없다. 새 환경이라면 Google Sheets를 새로 만들고 확장 프로그램 → Apps Script를 연다. apps-script/Code.gs를 붙여넣고, 프로젝트 설정에서 manifest 표시를 켠 뒤 apps-script/appsscript.json도 반영한다. setup 함수를 한 번 실행하여 권한을 승인한다. Campaigns와 Tasks 탭이 생기며, 프로젝트 설정의 Script properties에 SHEET_ID와 TEAM_KEY가 자동 생성된다. 이번 저장소는 사용자가 승인한 임시 예외로 루트 .env에 공용 키와 URL을 커밋하고 자동으로 읽는다. 팀원은 별도로 설정하지 않는다. 개인 CLI 인증을 공유하는 예외는 아니다.

웹 앱으로 새 배포하고 실행 사용자는 본인, 접근은 모든 사용자로 선택한다. /exec URL을 사용한다. Workspace 정책상 이 배포가 불가능하면 관리자 허용 또는 다른 계정이 필요하다. 정확한 화면별 절차는 docs/shared-assignment.md를 읽는다. 실제 배포가 끝나지 않았다면 끝났다고 말하지 않는다.

## 3. 고정 작업 목록과 시트 등록

팀원과 담당자가 같은 전체 데이터에서 아래 명령으로 catalog를 재현한다. 실제 로컬 검증 결과는 159건 7묶음과 158건 1묶음이다. 8묶음 × 2교사이므로 시트 작업은 16개, 전체 응답 계획은 2,542건이다.

```bash
./pipeline campaign --manifest data/screenspot-v2/manifest.jsonl --name screenspot-v2-team8-v1 \
  --seed 42 --batch-count 8 --providers codex claude --output data/screenspot-v2/campaign-team8.json
./team register --campaign data/screenspot-v2/campaign-team8.json
```

register는 공용 .env를 자동으로 읽는다. 팀원에게 키나 URL을 요구하지 않는다. 같은 화면은 나누지 않고 정확히 8개의 비어 있지 않은 묶음을 만든다. batch-size 30을 동시에 쓰지 않는다. 각 묶음에 교사별 작업이 생긴다. 한 교사만 수집하면 providers를 하나로 지정한다. 같은 실험 재등록은 진행을 보존하고 설정이 다른 재등록은 거절한다. 변경은 새 실험 이름으로 한다.

## 4. 팀원에게 전달

저장소와 공통 커밋, 전체 데이터 다운로드 및 변환 명령, 공용 .env가 포함된 코드, 중복되지 않는 팀원 ID와 교사, 실제 결과 ZIP 전달 위치를 안내한다. 팀원은 join, acquire, doctor, plan, 제한 run과 전체 run, submit, acquire로 진행한다. 시트 편집 권한이나 수동 진행 기록을 요구하지 않는다. 약 4명으로 운영하며 Codex 2명과 Claude 2명은 교사 구독에 맞춘 구성 예시다. 사람별 입력을 고정하지 않고 먼저 끝낸 사람이 자기 교사의 다음 작업을 받는다.

## 5. 진행과 결과 수령

시트는 담당자, 작업 번호, 교사, 전체 및 완료, 실패, 자동 유효 건수, 마지막 갱신과 ZIP 이름을 자동 표시한다. submitted는 로컬 ZIP 생성 완료이므로 실제 파일을 수령했는지 별도 확인한다. 사람 검수 통과가 아니다. 오래 멈춘 배정은 담당자와 소통해 재개하며 자동 회수는 없다. 결과가 없는 배정은 팀원의 team return으로 반납할 수 있다. 행을 임의로 수정하지 않는다.

이후는 아래의 기존 ZIP 취합과 최종 검수 절차를 사용한다. ZIP은 사람별 4개가 아니라 교사별 작업마다 만들어져 전량 기준 16개다. 실제 받은 파일명으로 취합하고 같은 작업의 재제출은 최신 버전만 선택한다. 팀원은 점수표를 작성하지 않고 담당자가 병합 후 최종 검수한다.

## 6. 제출 파일 수령과 압축 해제

이번 실험에서 선택한 최종 제출 ZIP만 runs/incoming/에 놓는다. demo, 이전 파일럿, 같은 작업의 옛 제출은 섞지 않는다. 폴더를 비운다는 이유로 기존 결과를 삭제하지 말고 다른 보관 폴더를 사용한다. 기본 예시는 이 경로가 이번 취합 전용일 때다.

```bash
mkdir -p runs/incoming
for submission_zip in runs/incoming/*.zip; do
  python3 -m zipfile -e "$submission_zip" runs/incoming/
done
```

내부 폴더명은 ZIP 생성 당시 파일명에서 확장자를 뺀 값이다. 받은 ZIP 이름만 바꿔도 내부 폴더명은 변하지 않는다. 출력된 폴더를 유지한다.

## 7. 배정 건수와 제출 결과 대조

시트에서 screenspot-v2-team8-v1의 Codex 8작업과 Claude 8작업을 확인한다. demo 등록 행이 있으면 전체 시트 행 수와 혼동하지 않는다. 작업별 입력은 158개 또는 159개이며 교사별 1,271건, 전체 2,542건이다. 각 ZIP의 BUNDLE.json samples와 jobs 및 실패 수를 대조한다. submitted는 ZIP 생성 상태이므로 실제 파일 수령도 확인한다. 누락은 해당 팀원이 재개하고 다시 제출한다.

## 8. 결과 병합

아래 glob은 runs/incoming/의 모든 하위 폴더가 이번 실험의 선택한 제출일 때만 사용한다. 다른 폴더가 섞여 있으면 --runs 뒤에 선택한 16개 경로만 명시한다.

```bash
./pipeline merge --runs runs/incoming/*/ --output runs/merged
```

대상은 새 폴더나 빈 폴더여야 한다. 같은 작업의 옛 제출과 v2를 동시에 넣지 않는다. 다른 교사 결과는 보존하고 같은 작업의 다른 결과는 충돌로 중단한다. 병합 manifest는 제출 폴더 이미지를 참조하므로 runs/incoming/을 유지한다.

## 9. 전체 최종 검수

```bash
./pipeline summary --run runs/merged
./pipeline review --run runs/merged --output runs/merged/review
```

`runs/merged/review/review.html`을 브라우저로 열고 `scores.csv`를 편집한다. 네 점수는 `evidence`(화면 근거), `target_match`(목표 일치), `usefulness`(설명 유용성), `consistency`(설명과 클릭의 일치)이며 각각 0-2점이다. `decision`에는 `accept` 또는 `reject`, `reviewer`에는 검수자, `notes`에는 메모를 기록한다. 미검수는 빈칸이다.

기본 운영은 팀원이 생성하고 담당자가 여기서 최종 검수하는 방식이다. 팀원들이 작성한 CSV는 자동 병합되지 않는다. 이미 검수된 행을 사용한다면 `job_id`로 대조해 옮기고 중복 또는 상반된 판정을 확인한다. 자동 좌표 검사를 통과했다는 이유로 사람 점수를 채우지 않는다.

## 10. 채택 데이터 export와 전체 결과 보관

```bash
./pipeline export \
  --run runs/merged --scores runs/merged/review/scores.csv \
  --output runs/merged/expert.jsonl

./pipeline bundle-run --run runs/merged --output dist/merged-reviewed.zip
```

export는 교사 ok, 자동 검증 통과, 사람의 accept와 검수자, 네 점수 합계 6/8 이상이고 모든 항목 1점 이상인 결과를 채택한다. `expert.jsonl`과 `expert.excluded.jsonl`이 만들어진다. ScreenSpot-v2 파일럿은 별도 `--allow-pilot`이 필요하며 export 후에도 학습 제외 표시가 유지된다. validation/test는 export할 수 없다.

`expert.jsonl`의 이미지 경로는 현재 컴퓨터의 절대 경로다. 다른 컴퓨터로 전달하거나 장기 보관할 때는 원본 이미지와 검수 CSV를 포함한 `merged-reviewed.zip`을 함께 보관한다. 이 단계는 후속 학습 후보 준비이며 학생 모델 SFT 실행이 아니다.
