# 팀원 사용법

기본 절차는 공유 시트 자동 배정이다. 아래는 Codex 담당자 member-a의 예시이며 실제 데이터 경로와 URL로 바꾼다. 팀원은 시트나 점수 CSV를 편집하지 않는다.

## 1. 공통 정보 받기

저장소 접근 권한과 코드 버전, 전체 데이터의 다운로드와 변환 방법, 공통 campaign 파일, Apps Script /exec URL, 참여 코드, 팀원 ID와 교사, 실제 ZIP 전달 위치를 받는다. ID는 서로 다르게 정하고 같은 실험의 데이터 revision과 변환 설정은 유지한다.

## 2. 환경과 전체 데이터 준비

```bash
git clone https://github.com/Sucrose122211/GUI-task-trajectory-generator.git
cd GUI-task-trajectory-generator
./team setup --backend local
git rev-parse HEAD
```

Linux 또는 WSL의 Python 3.10 이상, venv와 pip, 교사 CLI를 사용한다. 기존 clone이면 해당 폴더에서 작업한다. Docker를 선호하면 setup --backend docker를 사용한다. Codex는 codex login, Claude는 claude 실행 후 자기 구독으로 로그인한다. 담당자가 안내한 방법으로 전체 원본을 다운로드하고 공통 manifest로 변환한다. 경로 예시는 data/full/manifest.jsonl, campaign은 data/campaign.json이다. 임의 데이터셋을 자동 다운로드하는 명령은 없으므로 공통 데이터 준비 명령을 사용한다.

## 3. 최초 참여와 자동 배정

```bash
./team join --campaign data/campaign.json --manifest data/full/manifest.jsonl \
  --url '배포된_HTTPS_EXEC_URL' --worker member-a --provider codex
./team acquire
./team doctor
./team plan
```

join 때 참여 코드를 숨김 입력으로 한 번 받는다. Claude는 --provider claude다. acquire가 빈 작업을 선점하고 job.json과 해당 입력을 만든다. 이미 진행 중이면 같은 배정을 반환한다. doctor와 plan까지는 모델을 호출하지 않는다. 이미 job.json이 있으면 --config jobs/member-a.json을 join 앞에 붙이고 이후 모든 명령에도 같은 --config를 붙인다. 원본 revision, 데이터와 프롬프트가 다르면 참여를 거절한다.

## 4. 한 개 시험 후 전체 생성

```bash
./team run --limit 1
./team review
./team run
./team status
```

run은 실제 구독을 사용한다. review가 알려주는 HTML을 열어 첫 결과를 확인한다. 진행 상태는 시작, 약 30초 간격과 종료 시 시트에 자동 기록한다. 중단되거나 한도에 걸리면 같은 run으로 재개한다. 결과 폴더와 .team/은 지우지 않는다. 완료했지만 자동 검사에 실패한 응답은 검수 대상으로 남는다. 생성 중 입력, 코드와 모델 설정을 바꾸지 않는다.

## 5. ZIP 생성과 실제 전달

```bash
./team submit
```

원본 화면과 입력 및 최신 결과를 담은 ZIP을 만들고 시트에 파일명과 SHA-256, 완료 상태를 자동 기록한다. 전량 응답이 있어야 submitted가 된다. 부분 생성은 다음 작업을 열지 않는다. submitted는 로컬 ZIP 생성 완료이며 파일 전달이나 사람 채택이 아니다. 출력된 ZIP을 담당자가 정한 Drive 등에 직접 올린다. 링크를 시트에 남기려면 submit --result-url 'https://drive.google.com/...'을 사용한다. 시트를 직접 편집하지 않으며 이 명령은 새 ZIP을 만든다. 팀원은 사람 점수 CSV를 채우지 않는다.

## 6. 다음 작업과 장애 처리

```bash
./team acquire
./team run
./team submit
```

전량 생성 후 submit한 상태에서 acquire하면 다음 묶음을 가져온다. 진행 중이면 기존 묶음이다. 결과는 배정별 폴더에 보존한다. 연결이 끊겨도 이미 받은 입력은 로컬 생성이 가능하고 다음 run, sync 또는 acquire에서 동기화한다. 오프라인 신규 배정은 하지 않는다.

```bash
./team sync
./team return
```

sync는 상태 전송만 하고 모델을 호출하지 않는다. return은 결과가 없는 배정만 반납한다. 일부 결과가 있으면 재개하거나 담당자와 협의한다. 추가 설정과 예외는 docs/shared-assignment.md를 참고한다.

## 기존 수동 배정이 명시된 경우

받은 assignment ZIP을 data/에 풀고 team init --provider codex --manifest data/assignment-a/manifest.jsonl로 설정한다. 이후 doctor, plan, run, submit은 같다. 이 경우 시트 자동 기록은 없다. ZIP 내부 루트는 생성 당시 ZIP 파일명에서 확장자를 뺀 이름이다. 결과를 직접 전달하고 담당자가 병합 및 최종 검수한다.
