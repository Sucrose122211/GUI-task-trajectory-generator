# GUI trajectory 생성, 팀원용 빠른 시작

GUI 화면, 지시문과 정답을 받아 영어 관찰 설명을 생성합니다. Codex 또는 Claude 구독 중 하나를 선택합니다. 모델 이름은 지정하지 않아도 됩니다.

에이전트에게 순서대로 설명받으려면 `/사용법 팀원`을 입력합니다. 담당자는 `/사용법 담당자`를 사용합니다. Codex가 한글 slash 명령을 거절하면 `$gui-trajectory-usage 팀원` 또는 `$gui-trajectory-usage 담당자`를 사용하세요. 불러오기 방법과 역할별 전체 절차는 [사용법 스킬](docs/usage-skill.md)에 있습니다.

## 1. 준비

Linux 또는 WSL에서 실행합니다. Python 3.10 이상과 사용할 교사의 CLI가 필요합니다. Docker 없이 실행할 수 있습니다. WSL에서는 CLI 설치와 로그인도 WSL 안에서 진행하세요.

- Codex 사용: `codex login`으로 ChatGPT 구독 로그인.
- Claude 사용: `claude`를 실행해 구독 계정으로 로그인.

GitHub 저장소를 내려받습니다. 비공개 저장소라면 GitHub 계정에 접근 권한이 있어야 합니다. 아래 명령은 모두 내려받은 폴더에서 실행합니다. 로컬 실행은 저장소의 `.venv`에만 라이브러리를 설치합니다. 시스템 Python 패키지를 변경하지 않습니다.

```bash
git clone https://github.com/Sucrose122211/GUI-task-trajectory-generator.git
cd GUI-task-trajectory-generator
./team setup --backend local
```

Python의 `venv`와 `pip`가 필요하며, 처음에는 Pillow를 다운로드할 인터넷 연결이 필요합니다. `.venv`를 직접 활성화할 필요는 없습니다. Docker를 쓰려면 실행 중인 Docker를 준비하고 `./team setup --backend docker`를 실행하세요. 선택은 `.pipeline-backend`에 저장되며 이후 `./team setup`도 같은 방식을 사용합니다. 이 설정과 `.venv`는 Git이나 제출 ZIP에 포함되지 않습니다.

CLI 설치가 필요한 경우 [Codex 공식 안내](https://developers.openai.com/codex/cli), [Claude Code 공식 안내](https://code.claude.com/docs/en/overview)를 참고하세요. 프로그램은 필요한 CLI 옵션이 없는 버전을 진단 단계에서 알려줍니다.

## 2. 전체 데이터 준비와 참여

담당자에게 전체 데이터 준비 방법, 공통 `campaign.json`, Apps Script `/exec` URL, 참여 코드와 사용할 교사를 받습니다. 데이터셋과 revision 및 변환 설정은 모두 같아야 합니다. 담당자 최초 준비는 [공유 배정 안내](docs/shared-assignment.md)에 있습니다. 팀원은 시트를 열거나 편집하지 않습니다.

아래는 경로 예시입니다. 실제 받은 경로와 URL로 바꾸세요.

```bash
./team join --campaign data/campaign.json --manifest data/full/manifest.jsonl \
  --url '배포된_HTTPS_EXEC_URL' --worker member-a --provider codex
./team acquire
./team doctor
./team plan
```

join 안내에 참여 코드를 입력합니다. 화면에 표시되지 않으며 `.team/`에 저장해 이후 다시 입력하지 않습니다. Claude는 `--provider claude`를 사용합니다. `acquire`는 빈 작업을 가져와 `job.json`을 만듭니다. 이미 진행 중인 작업은 같은 배정을 반환합니다. `doctor`와 `plan`까지는 모델을 호출하지 않습니다.

## 3. 생성과 재개

```bash
./team run --limit 1
./team run
```

첫 명령으로 한 개를 시험한 뒤 전체를 생성합니다. 구독 사용량을 소비합니다. `./team review`로 첫 결과를 확인할 수 있습니다. 중단되거나 한도에 걸리면 나중에 같은 `./team run`으로 이어갑니다. 진행 건수는 시작, 실행 중 약 30초 간격과 종료 시 자동 기록합니다. 시트 연결이 끊겨도 이미 받은 작업은 로컬에서 계속 생성할 수 있습니다.

## 4. ZIP 생성과 다음 작업

```bash
./team status
./team submit
./team acquire
```

`submit`은 로컬 ZIP을 만들고 시트에 완료 건수, 파일명과 SHA-256을 자동 기록합니다. 전량 생성한 작업만 시트에서 `submitted`로 기록하고 다음 작업을 받을 수 있습니다. 부분 생성은 계속 같은 작업을 유지합니다. 자동 검사를 통과하지 않은 응답은 사람 검수 대상으로 보존합니다.

출력된 ZIP을 정해진 공유 Drive 등에 전달하세요. 파일 업로드 자체는 자동화하지 않습니다. 팀원은 시트의 완료 표시나 점수 CSV를 편집할 필요가 없습니다. 최종 검수는 담당자가 합니다. 파일 링크도 남기려면 `./team submit --result-url 'https://drive.google.com/...'`으로 자동 기록할 수 있습니다. 새 ZIP을 만들며 이전 파일은 덮어쓰지 않습니다.

연결 장애가 있었다면 `./team sync`로 다시 전송할 수 있습니다. 아직 생성하지 않은 배정은 `./team return`으로 반납합니다. 일부 결과가 있는 배정은 그대로 재개하거나 담당자에게 알려주세요. 결과 폴더와 `.team/`은 유지합니다.

공유 배정 없이 기존 입력 ZIP을 받았다면 `./team init --provider codex --manifest data/assignment-a/manifest.jsonl`로 설정한 뒤 같은 doctor, plan, run과 submit을 사용합니다. 이 경우 시트 기록은 없습니다.

## 자주 필요한 것

| 상황 | 할 일 |
| --- | --- |
| 예제만 확인하고 싶음 | [데이터 연결 안내의 예제](docs/dataset-adaptation.md#1-포함된-예제로-변환-확인)를 실행한 뒤 `plan`까지만 진행 |
| 다른 데이터셋 사용 | [데이터 연결 안내](docs/dataset-adaptation.md)에서 필드 매핑과 좌표 형식 지정 |
| 두 교사를 같은 입력에서 비교 | `./team --config codex-job.json join ... --provider codex`와 `./team --config claude-job.json join ... --provider claude`로 각각 참여. 이후 명령에도 `--config`를 앞에 붙임 |
| 작업 설정이나 CLI 버전 변경 후 재개 오류 | 기존 결과를 유지하고 담당자와 공통 코드 및 교사 CLI 버전을 확인. 임의로 입력이나 배정을 바꾸지 않음 |
| Docker가 없음 | `./team setup --backend local` 사용 |
| 로컬 설치 시 venv / ensurepip 오류 | Python의 venv와 pip가 제공되는 환경을 준비하거나 Docker 방식 선택. 프로그램이 시스템 패키지를 자동 설치하지는 않음 |
| 에이전트에게 실행 맡기기 | [에이전트 안내](docs/agent-manual.md)를 읽도록 지시 |

평가용 ScreenSpot-v2 파일럿은 `pilot_dev`로 유지합니다. 대량 생성 데이터셋과 분담량은 팀에서 정합니다. 이 프로그램은 교사 데이터 생성까지 제공하며 학생 모델 학습은 포함하지 않습니다.

## 코드 업데이트

진행 중인 생성을 먼저 중단한 뒤 `git pull --ff-only`, `./team setup`으로 선택했던 실행 환경도 갱신합니다. 공유 배정의 프롬프트나 입력이 달라지면 기존 작업을 유지하고 담당자에게 공통 버전을 확인합니다. 실험 변경은 새 campaign으로 진행합니다. 기존 수동 작업은 새 설정과 결과 폴더로 분리할 수 있습니다. 기존 데이터와 결과, 로그인 정보는 Git에 올리지 않습니다.

저장소 담당자의 생성과 업데이트 방법은 [GitHub 배포 운영 안내](docs/github-distribution.md)에 있습니다.
