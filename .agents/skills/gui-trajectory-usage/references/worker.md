# 팀원 사용법

담당자가 배정한 데이터를 자기 구독으로 생성하고 ZIP으로 전달하는 절차다. 아래는 팀원 A가 `assignment-a.zip`을 Codex로 생성해 `member-a.zip`으로 제출하는 예시다. 실제 배정 정보가 있으면 그 값으로 바꾼다.

## 1. 담당자에게 받을 정보

저장소 접근 권한과 코드 커밋, 담당 데이터 ZIP, 사용할 교사, 배정 건수, 제출 파일명, 결과를 올릴 공유 위치를 확인한다. 다른 사람과 입력을 다시 나누거나 교사를 임의로 변경하지 않는다.

## 2. 저장소와 환경 준비

Linux 또는 WSL에서 Git, Python 3.10 이상, 실행 중인 Docker, 사용할 교사의 CLI와 구독 로그인을 준비한다. WSL을 사용하면 CLI 설치와 로그인도 WSL 안에서 한다.

```bash
git clone https://github.com/Sucrose122211/GUI-task-trajectory-generator.git
cd GUI-task-trajectory-generator
./team setup
git rev-parse HEAD
```

담당자가 전달한 커밋과 대조한다. 이미 clone했다면 저장소 루트에서 이후 명령을 실행한다. Codex는 `codex login`, Claude는 `claude` 실행 후 자기 구독 계정으로 로그인한다. 인증 정보를 제출하지 않는다.

## 3. 담당 데이터 압축 해제

담당자가 준 ZIP을 저장소의 `data/assignment-a.zip`에 놓은 뒤:

```bash
mkdir -p data
python3 -m zipfile -e data/assignment-a.zip data/
```

`data/assignment-a/manifest.jsonl`과 `images/`가 생긴다. ZIP을 받은 뒤 파일명만 바꿨다면 내부 폴더명은 바뀌지 않으므로 실제 경로를 확인한다.

## 4. 작업 설정과 호출 없는 확인

```bash
./team init \
  --provider codex \
  --manifest data/assignment-a/manifest.jsonl \
  --output runs/member-a
./team doctor
./team plan
```

Claude를 배정받았으면 `--provider claude`를 사용한다. B와 C는 assignment와 출력 경로도 자기 배정에 맞게 바꾼다. 설정은 `job.json`에 저장된다. `doctor`의 ready와 `plan`의 samples를 확인한다. 여기까지 모델 생성은 하지 않는다.

`job.json`이 이미 있다면 init을 반복하지 않는다. 같은 작업은 기존 설정을 사용한다. 다른 작업은 `./team --config next-job.json init ...`으로 만들고 이후 명령에도 같은 `--config`를 명령 앞에 붙인다. 모델 이름은 별도로 지정하지 않아도 된다.

## 5. 한 개 시험 생성

```bash
./team run --limit 1
./team review
```

이제 실제 구독을 사용한다. `runs/member-a/review/review.html`을 브라우저로 열어 화면과 설명이 정상인지 확인한다. 정상이라면 전체 생성을 진행한다.

## 6. 전체 생성과 중단 후 재개

```bash
./team run
./team status
```

완료한 입력은 건너뛰고 남은 입력을 순차 생성한다. 구독 한도나 로그인 문제로 멈추면 그 문제를 해결한 뒤 같은 `./team run`으로 재개한다. 재개를 위해 결과 폴더를 지우지 않는다. 완료됐지만 내용 검증에 실패한 설명은 자동으로 다시 뽑지 않고 검수 대상으로 남는다.

생성 중 코드, 입력, 프롬프트, 모델 설정을 바꾸지 않는다. 변경 때문에 재개가 거절되면 기존 결과를 보존하고 담당자에게 알려 새 작업 폴더를 정한다. 동작 중인 같은 결과 폴더에 두 생성기를 실행하지 않는다.

## 7. 제출 전 확인과 ZIP 생성

```bash
./team status
./team review
./team submit --output dist/member-a.zip
```

`status`의 저장된 작업 집계와 담당자가 알려준 배정 수를 대조한다. ZIP 출력의 samples와 jobs도 확인한다. submit은 부분 생성이나 실패가 있는 결과도 포장할 수 있으므로 ZIP 생성 성공만으로 전량 완료라고 판단하지 않는다.

팀원이 생성만 맡았다면 검수 점수는 빈칸으로 둔다. 담당자가 팀원 검수를 요청했다면 `runs/member-a/review/scores.csv`에 점수와 판정, 검수자를 기록한 뒤 ZIP을 만든다. 검수 HTML 자체에서 점수를 입력하는 구조는 아니며 CSV를 편집한다.

## 8. 결과 파일을 직접 전달

`dist/member-a.zip`을 담당자가 정한 공유 위치에 직접 올린다. `submit`은 로컬 ZIP만 만들며 GitHub나 공유 폴더에 자동 업로드하지 않는다. 원본 화면, 입력, 작업별 최신 결과, 실행 설정과 저장된 점수 CSV가 포함된다.

담당자에게 제출 파일명, 배정 수, 완료 및 실패 수를 함께 알린다. 에이전트에게 사용법만 물었을 때 이 전달을 자동 실행했다고 말하지 않는다.

## 9. 누락 보완과 재제출

남은 입력이나 재개 가능한 실패가 있다면 기존 작업에서:

```bash
./team run
./team status
./team submit --output dist/member-a-v2.zip
```

기존 ZIP은 덮어쓰지 않는다. 새 ZIP을 공유 위치에 전달하고 담당자에게 최신 제출 버전을 알려준다. 현재 단계에서 팀원이 병합하거나 전체 데이터의 최종 export를 할 필요는 없다.
