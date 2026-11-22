# GUI trajectory 생성, 팀원용 빠른 시작

GUI 화면, 지시문과 정답을 받아 영어 관찰 설명을 생성합니다. Codex 또는 Claude 구독 중 하나를 선택합니다. 모델 이름은 지정하지 않아도 됩니다.

에이전트에게 순서대로 설명받으려면 `/사용법 팀원`을 입력합니다. 담당자는 `/사용법 담당자`를 사용합니다. Codex가 한글 slash 명령을 거절하면 `$gui-trajectory-usage 팀원` 또는 `$gui-trajectory-usage 담당자`를 사용하세요. 불러오기 방법과 역할별 전체 절차는 [사용법 스킬](docs/usage-skill.md)에 있습니다.

## 1. 준비

Linux 또는 WSL에서 실행합니다. Docker가 실행 중이고 현재 계정으로 사용할 수 있어야 합니다. Python 3.10 이상과 사용할 교사의 CLI가 필요합니다. WSL에서는 CLI 설치와 로그인도 WSL 안에서 진행하세요.

- Codex 사용: `codex login`으로 ChatGPT 구독 로그인.
- Claude 사용: `claude`를 실행해 구독 계정으로 로그인.

GitHub 저장소를 내려받습니다. 비공개 저장소라면 GitHub 계정에 접근 권한이 있어야 합니다. 아래 명령은 모두 내려받은 폴더에서 실행합니다. 프로그램은 호스트에 패키지를 설치하지 않습니다.

```bash
git clone https://github.com/Sucrose122211/GUI-task-trajectory-generator.git
cd GUI-task-trajectory-generator
./team setup
```

처음 빌드할 때 컨테이너 다운로드를 위한 인터넷 연결이 필요합니다. CLI 설치가 필요한 경우 [Codex 공식 안내](https://developers.openai.com/codex/cli), [Claude Code 공식 안내](https://code.claude.com/docs/en/overview)를 참고하세요. 프로그램은 필요한 CLI 옵션이 없는 버전을 진단 단계에서 알려줍니다.

## 2. 받은 데이터 연결

담당자가 준 `assignment-a.zip`을 `data/` 안에 풉니다. 예를 들어 `data/assignment-a/manifest.jsonl`과 `images/`가 생깁니다. 아래 경로는 실제 받은 폴더명으로 바꾸세요.

```bash
./team init --provider codex --manifest data/assignment-a/manifest.jsonl
./team doctor
./team plan
```

Claude를 쓰면 첫 명령의 `codex`를 `claude`로 바꿉니다. `init`은 선택을 `job.json`에 저장합니다. `doctor`는 로그인 확인, `plan`은 입력과 이미지 검증이며 둘 다 생성하지 않습니다.

## 3. 생성

```bash
./team run --limit 1
./team run
```

첫 명령으로 한 개를 시험한 뒤 전체를 생성합니다. 구독 사용량을 소비하는 명령입니다. 첫 결과를 확인하려면 `./team review`를 실행하세요. 중단되거나 사용량 제한에 걸리면 나중에 같은 `./team run`으로 이어갑니다. 완료한 입력은 다시 생성하지 않습니다.

## 4. 검수와 제출

```bash
./team status
./team review
./team submit
```

- `review`가 알려주는 `runs/codex/review/review.html`을 브라우저에서 엽니다. Claude는 `runs/claude/`입니다.
- 점수를 기록하려면 같은 폴더의 `scores.csv`를 편집합니다. 4개 항목은 0-2점, 판정은 `accept` 또는 `reject`, 검수자는 이름이나 식별자입니다. 미검수는 빈칸으로 둡니다.
- 제출 파일은 `dist/codex-results.zip` 또는 `dist/claude-results.zip`입니다. 원본 화면과 입력, 생성 결과, 저장한 점수 CSV를 포함합니다. 이 ZIP만 담당자에게 전달하세요.
- 제출 ZIP은 덮어쓰지 않습니다. 추가 생성 후 다시 제출할 때는 `./team submit --output dist/worker-a-v2.zip`처럼 새 이름을 사용하세요.

점수 항목은 `evidence`(화면 근거), `target_match`(정답 요소 일치), `usefulness`(목표를 찾는 데 도움), `consistency`(설명과 클릭의 일치)입니다. 0점은 부정확, 1점은 부분적, 2점은 명확하게 충족한 경우입니다.

## 자주 필요한 것

| 상황 | 할 일 |
| --- | --- |
| 예제만 확인하고 싶음 | [데이터 연결 안내의 예제](docs/dataset-adaptation.md#1-포함된-예제로-변환-확인)를 실행한 뒤 `plan`까지만 진행 |
| 다른 데이터셋 사용 | [데이터 연결 안내](docs/dataset-adaptation.md)에서 필드 매핑과 좌표 형식 지정 |
| 두 교사를 같은 입력에서 비교 | `./team --config codex-job.json init --provider codex --manifest ...`와 `./team --config claude-job.json init --provider claude --manifest ...`로 각각 설정. 이후 명령에도 `--config`를 앞에 붙임 |
| 작업 설정이나 CLI 버전 변경 후 재개 오류 | 기존 결과를 유지하고 `init --output runs/new-name`으로 새 결과 폴더 사용 |
| Docker 사용 오류 | Docker 실행 상태와 현재 사용자 권한 확인. WSL에서는 Docker의 해당 배포판 연동도 확인 |
| 에이전트에게 실행 맡기기 | [에이전트 안내](docs/agent-manual.md)를 읽도록 지시 |

평가용 ScreenSpot-v2 파일럿은 `pilot_dev`로 유지합니다. 대량 생성 데이터셋과 분담량은 팀에서 정합니다. 이 프로그램은 교사 데이터 생성까지 제공하며 학생 모델 학습은 포함하지 않습니다.

## 코드 업데이트

진행 중인 생성을 먼저 중단한 뒤 `git pull --ff-only`, `./team setup`으로 코드를 갱신합니다. 프롬프트, 버전, 입력이 달라져 기존 결과 폴더에서 재개가 거절되면 `./team --config next-job.json init --provider codex --manifest ... --output runs/next`로 새 작업을 만듭니다. 기존 데이터와 결과, 로그인 정보는 Git에 올리지 않습니다.

저장소 담당자의 생성과 업데이트 방법은 [GitHub 배포 운영 안내](docs/github-distribution.md)에 있습니다.
