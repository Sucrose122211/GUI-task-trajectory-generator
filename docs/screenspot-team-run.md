# ScreenSpot-v2, 4명으로 8묶음 생성하기

이번 임시 운영에 한해 사용자 요청으로 루트 `.env`의 공용 팀 키와 주소를 커밋합니다. 다른 프로젝트에 적용할 일반 규칙이 아닙니다. Codex/Claude 개인 인증은 계속 제외합니다. [저장소 한정 설정 설명](repository-only-settings.md)에 범위와 우선순위를 기록했습니다.

이번 팀 생성은 이전 파일럿과 같은 ScreenSpot-v2의 전체 유효 입력을 사용합니다. 4명 정도가 공통 작업 목록에서 하나씩 가져가고, 먼저 끝낸 사람이 다음 작업을 받습니다. 담당자가 팀원마다 입력 ZIP을 만들거나 팀원이 진행표를 편집할 필요는 없습니다.

## 확정 설정

| 항목 | 값 |
| --- | --- |
| 데이터셋 | OS-Copilot/ScreenSpot-v2 |
| 고정 revision | `5efbb1f1b5463a575f2eb7bc30fe29e49c15f93c` |
| 범위 | 이전 30건 표본이 아닌 전체 유효 입력 1,271건 |
| 변환 | `screenspot_v2`, 원본 화면과 정답 유지 |
| 역할 | `pilot_dev`, SFT 학습에서 제외 |
| 공통 시드 | `42` |
| 입력 묶음 수 | `8`, 번호 `0000`부터 `0007` |
| 실험 이름 | `screenspot-v2-team8-v1` |
| 교사 | Codex와 Claude, 구독 CLI 기본 모델 |
| 생성 작업 수 | 8묶음 × 2교사 = 16작업 |
| 예상 생성 응답 수 | 1,271 × 2 = 2,542건 |
| 팀원 | 약 4명, 인원수에 따라 분할을 다시 만들지 않음 |

같은 화면의 여러 태스크는 한 묶음에 유지합니다. 이 revision의 주석 1,272건 중 범위를 벗어난 box 1건을 제외한 결과가 1,271건입니다. 오류는 `manifest.prepare.json`에 남기며 수정하거나 포함하지 않습니다. 기존 30건 파일럿 결과는 보존하며 이번 campaign에 자동 재사용하지 않습니다. 최종 평가용 ScreenSpot-Pro는 이번 생성에 쓰지 않습니다.

| 묶음 | 입력 수 | 교사별 작업 |
| --- | ---: | --- |
| 0000 | 159 | Codex 1개, Claude 1개 |
| 0001 | 159 | Codex 1개, Claude 1개 |
| 0002 | 159 | Codex 1개, Claude 1개 |
| 0003 | 159 | Codex 1개, Claude 1개 |
| 0004 | 159 | Codex 1개, Claude 1개 |
| 0005 | 159 | Codex 1개, Claude 1개 |
| 0006 | 159 | Codex 1개, Claude 1개 |
| 0007 | 158 | Codex 1개, Claude 1개 |

## 1. 담당자와 팀원 공통, 코드와 전체 데이터 준비

처음에는 다음 명령으로 받습니다. 기존 clone이면 해당 폴더에서 `git pull --ff-only` 후 `./team setup`을 실행합니다. 모두 담당자가 공지한 같은 코드 버전을 사용합니다.

```bash
git clone https://github.com/Sucrose122211/GUI-task-trajectory-generator.git
cd GUI-task-trajectory-generator
./team setup --backend local
git rev-parse HEAD
```

Docker를 쓰려면 `./team setup --backend docker`를 선택할 수 있습니다. 로컬 방식은 Python 3.10 이상과 venv/pip가 필요하며 저장소의 `.venv`에만 라이브러리를 설치합니다. WSL이면 교사 CLI 설치와 로그인도 WSL 안에서 합니다.

모든 참여자는 아래 명령을 똑같이 실행합니다. 이미지 다운로드는 약 1.3GB입니다. 기존 파일을 재사용할 때도 같은 revision과 원본을 사용하세요.

```bash
./pipeline fetch-screenspot \
  --revision 5efbb1f1b5463a575f2eb7bc30fe29e49c15f93c \
  --output data/screenspot-v2

./pipeline prepare --adapter screenspot_v2 \
  --annotations data/screenspot-v2 \
  --image-root data/screenspot-v2/images \
  --dataset OS-Copilot/ScreenSpot-v2 \
  --source-info data/screenspot-v2/source.json \
  --role pilot_dev --output data/screenspot-v2/manifest.jsonl

./pipeline campaign --manifest data/screenspot-v2/manifest.jsonl \
  --name screenspot-v2-team8-v1 --seed 42 --batch-count 8 \
  --providers codex claude --output data/screenspot-v2/campaign-team8.json
```

위 명령은 모델을 호출하지 않습니다.

변환 결과는 `valid: 1271`, `invalid: 1`, 작업 목록 출력은 `batches: 8`, `tasks: 16`, `sizes: [159,159,159,159,159,159,159,158]`입니다. 같은 데이터와 코드라면 catalog fingerprint는 다음과 같습니다.

```text
8c0030d9b36dc071f1c55c876dc23dadf53bc179fd0af28dd966c622e0fede92
```

catalog 파일은 컴퓨터 경로와 이미지 본문을 포함하지 않습니다. 각자 생성해도 같은 결과이므로 담당자가 따로 분할 파일을 보내지 않아도 됩니다. 이미 같은 경로의 catalog가 있으면 다시 만들지 말고 기존 것을 사용합니다. 다른 설정이 필요하면 기존 파일을 지우지 않고 새 실험 이름과 경로를 사용합니다.

`--batch-count 8`은 정확히 8개의 비어 있지 않은 묶음을 만듭니다. `--batch-size 30`은 크기 기준의 다른 방식이므로 이번 실행에서는 쓰지 않습니다. 두 옵션은 동시에 사용할 수 없습니다. 이전 연결 확인용 demo catalog도 그대로 사용할 수 있습니다.

## 2. 담당자만, 작업 목록 한 번 등록

Google Sheets와 Apps Script가 이미 배포돼 있고 연결 확인을 마쳤다면 setup과 재배포를 반복할 필요가 없습니다. 이번 변경은 로컬 분할 옵션이며 기존 Apps Script를 그대로 사용합니다. 처음 설정하는 경우만 [최초 배포 안내](shared-assignment.md#담당자-1-새-시트와-배정-서비스-만들기)를 따릅니다.

```bash
./team register --campaign data/screenspot-v2/campaign-team8.json
```

공용 `.env`의 연결 설정을 자동 사용합니다. `ok: true`, `tasks: 16`이면 등록 성공입니다. 시트에는 이번 실험의 16행이 생깁니다. 연결 확인용 demo 2행이 남아 있으면 시트 전체 행 수는 더 많을 수 있습니다. 실험 이름으로 구분하고 직접 행을 지우거나 담당자를 입력하지 않습니다. 실제 등록과 모델 생성은 이 가이드를 작성하며 실행하지 않았습니다.

담당자는 팀원에게 다음을 전달합니다.

- 저장소 URL과 공통 코드 커밋, 이 가이드.
- 공용 `.env`가 포함된 같은 코드 버전. 키나 URL을 별도로 설정할 필요는 없습니다.
- 서로 다른 팀원 ID, 사용할 교사와 결과 ZIP을 올릴 공유 위치.

## 3. 4명 구성 예시

교사를 비교하므로 Codex와 Claude 작업이 모두 처리돼야 합니다. 다음은 구독 상황에 맞춰 정할 수 있는 운영 예시이며 실제 인명이나 확정 배정표가 아닙니다.

| 팀원 ID 예시 | 교사 | 가져올 작업 |
| --- | --- | --- |
| member-a | Codex | 빈 Codex 작업 하나씩 |
| member-b | Codex | 빈 Codex 작업 하나씩 |
| member-c | Claude | 빈 Claude 작업 하나씩 |
| member-d | Claude | 빈 Claude 작업 하나씩 |

각 교사 2명씩이면 총량이 같을 때 한 사람당 약 4작업을 맡는 셈입니다. 실제로는 속도와 구독 한도에 따라 다르게 나뉩니다. 사람별로 2개나 4개를 미리 고정하지 않으며 한 번에 하나만 선점합니다. 인원이 늘거나 줄어도 8묶음은 그대로 유지합니다. 한 교사를 쓸 수 있는 팀원이 없으면 그 교사의 미배정 작업은 남으므로 담당자가 해당 구독을 사용할 참여자를 정합니다.

## 4. 팀원, 참여와 첫 작업 받기

Codex 담당자 member-a의 명령입니다. 이름과 교사는 담당자가 정한 값으로 바꾸세요. Claude 담당자는 `--provider claude`를 사용합니다.

```bash
./team join --worker member-a --provider codex
./team acquire
./team doctor
./team plan
```

join은 저장소의 공용 `.env`를 자동 사용하므로 참여 코드를 입력하지 않습니다. Codex는 `codex login`, Claude는 `claude` 실행 후 각자의 구독으로 로그인해 두세요. acquire가 배정한 입력은 158개 또는 159개이며 plan에서 확인할 수 있습니다. 여기까지 모델 호출은 없습니다.

이전에 연결 확인을 했거나 `job.json`이 이미 있다면 새 설정을 사용하세요. 예를 들어 다음처럼 `--config`를 붙이고, 이후 명령에도 계속 같은 값을 붙입니다.

```bash
./team --config jobs/screenspot-team8.json join --worker member-a --provider codex
./team --config jobs/screenspot-team8.json acquire
./team --config jobs/screenspot-team8.json plan
```

`join`은 최초 한 번만 합니다. 이후에는 기존 설정과 `.team/`을 유지하고 acquire/run/submit을 사용합니다. 출력의 다음 명령이 `./team run`처럼 기본 설정으로 표시되더라도 별도 설정을 선택한 사람은 자기 `--config`를 계속 붙입니다.

## 5. 생성, ZIP 전달과 다음 묶음

기본 설정을 사용하는 경우입니다. 별도 설정을 선택했다면 아래 모든 명령 앞에 같은 `--config`를 붙입니다.

```bash
./team run --limit 1
./team review
./team run
./team status
./team submit
```

run은 실제 구독 사용량을 소비합니다. 첫 한 개를 확인한 뒤 전체를 생성합니다. 시작, 약 30초 간격과 종료 시 진행을 자동 기록하고 중단되면 같은 run으로 재개합니다. 팀원은 시트나 점수 CSV를 편집하지 않습니다.

submit은 원본 이미지와 입력 및 결과를 포함한 로컬 ZIP을 만들고 파일명과 SHA-256을 자동 기록합니다. 출력된 ZIP을 정해진 공유 Drive에 전달하세요. 파일 업로드 자체는 자동화하지 않았습니다. 링크를 남기려면 `./team submit --result-url 'https://drive.google.com/...'`을 사용합니다. 새 ZIP이 만들어지며 기존 ZIP은 덮어쓰지 않습니다.

전량 생성하고 ZIP을 만든 뒤 다음 작업을 가져옵니다.

```bash
./team acquire
./team plan
./team run
./team submit
```

acquire가 미배정 작업이 없다고 안내하면 해당 교사에서 새로 가져올 작업이 없는 상태입니다. 다른 사람이 진행 중인 작업까지 끝났다는 뜻은 아닙니다. 담당자는 시트의 실험별, 교사별 현황을 확인합니다. 한 작업이 일부만 끝났으면 다음 작업을 주지 않고 같은 배정을 반환합니다.

연결 문제는 `./team sync`, 결과가 없는 작업 반납은 `./team return`을 사용합니다. 일부 결과가 있는 작업은 재개하거나 담당자와 협의합니다. 연결 확인용 `jobs/connection-check.json`에 배정이 남아 있으면 `./team --config jobs/connection-check.json return`으로 별도 반납할 수 있습니다.

## 6. 담당자, 전체 결과 수령과 검수

이번 실험의 교사별 8작업, 총 16작업을 기준으로 확인합니다. 모든 입력이 생성됐을 때 교사별 1,271건, 전체 2,542건입니다. ZIP의 `BUNDLE.json`과 시트의 작업별 완료 건수를 대조합니다. `submitted`는 ZIP 생성 상태이며 실제 파일 수령이나 사람 검수 통과가 아닙니다.

ZIP을 각각 `runs/incoming/`에 풀고 [결과 취합 절차](github-distribution.md#결과-취합)로 병합합니다. 같은 작업의 여러 제출은 최신 버전만 선택합니다. 병합 manifest가 이미지를 참조하므로 원본 제출 폴더를 유지합니다. 담당자가 최종 검수 CSV를 작성하고 ScreenSpot-v2 결과는 `pilot_dev`로 유지합니다. export가 필요하면 `--allow-pilot`을 사용하며 학습 제외 표시가 유지됩니다.
