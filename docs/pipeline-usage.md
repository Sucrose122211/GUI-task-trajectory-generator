# 텍스트 trajectory 파이프라인 실행 안내

ScreenSpot-v2의 30개 입력을 같은 조건으로 Codex와 Claude에 제공한다. 실제 모델을 지정하지 않으면 각 CLI의 기본 모델을 사용한다. 다른 데이터셋은 공통 manifest로 변환한 뒤 같은 생성 명령을 사용한다.

## 공유 시트 자동 배정 (기본)

담당자는 [최초 설정 안내](shared-assignment.md)에 따라 Google Sheets와 Apps Script를 한 번 배포하고, `./pipeline campaign`으로 만든 공통 작업 목록을 `./team register`로 등록한다. 팀원은 같은 전체 데이터를 준비한 뒤 `join → acquire → doctor → plan → run → submit → acquire`로 작업을 받는다. 팀원은 시트나 점수 CSV를 편집하지 않는다. run은 진행을 자동 기록하고, submit은 로컬 ZIP 생성 상태와 파일명을 자동 기록한다. 실제 파일 업로드와 담당자의 최종 검수는 별도다. 연결 장애는 로컬에 기록해 재동기화하며 신규 배정은 온라인에서만 허용한다.

```bash
./pipeline campaign --manifest data/full/manifest.jsonl --name baseline-v1 \
  --seed 42 --batch-size 30 --providers codex claude --output data/campaign.json
./team register --campaign data/campaign.json --url '배포된_HTTPS_EXEC_URL'
./team join --campaign data/campaign.json --manifest data/full/manifest.jsonl \
  --url '배포된_HTTPS_EXEC_URL' --worker member-a --provider codex
./team acquire
```

register와 join은 참여 코드를 숨김 입력으로 받는다. 연결 상태는 `.team/`에 보관하며 Git과 ZIP에는 넣지 않는다. `./team sync`는 상태만 재전송하고, `./team return`은 아직 결과가 없는 배정만 반납한다. 모델 선택은 기존 CLI 기본값이다. 공유 배정에서는 등록된 입력과 프롬프트, 교사, 결과 경로를 유지해야 한다. 전체 명령과 예외 처리는 [자동 배정 안내](shared-assignment.md)를 따른다.

## 기존 수동 배정 실행

[빠른 시작](../QUICKSTART.md)에 따라 `./team setup`으로 준비하고, `./team init --provider codex --manifest data/assignment-a/manifest.jsonl`로 작업을 설정한다. 이후 `./team doctor`, `./team plan`, `./team run --limit 1`, `./team run`, `./team review`, `./team submit` 순서로 실행한다. Claude를 쓰면 `--provider claude`를 선택한다.

`team`은 이 문서의 상세 명령을 감싼 실행 도구다. 선택한 교사와 경로는 `job.json`에 저장하고 기본 모델을 사용한다. `--config`를 명령 앞에 붙이면 여러 작업을 분리할 수 있다. 예: `./team --config jobs/a.json run`. 모든 경로는 배포 폴더 안에 둔다. 설정 파일 안의 경로는 설정 파일 위치를 기준으로 해석한다.

[에이전트 안내](agent-manual.md)는 구조, 설정, 입출력 계약과 자동화 시 주의점을 설명한다. [데이터 연결 안내](dataset-adaptation.md)는 실행 가능한 예제와 필드 매핑, 점 정답과 다중 대상 처리 방법을 설명한다.

`/사용법 담당자`와 `/사용법 팀원`은 실행 없이 역할별 전체 단계를 설명하는 요청이다. [사용법 스킬 안내](usage-skill.md)에 클라이언트별 호출법과 담당자 및 팀원 절차를 연결했다.

## 1. 환경 준비

Linux 또는 WSL에서 Python 3.10 이상, 사용할 교사의 CLI가 필요하다. Docker 없이 실행하려면 Python의 venv와 pip를 준비한다. 사용자 계정의 Codex와 Claude Code는 구독으로 로그인하며, 프로그램은 인증 정보를 복사하거나 API key로 전환하지 않는다.

```bash
./team setup --backend local
./pipeline doctor
```

`doctor`는 설치 버전, 구독 인증 방식, 필요한 실행 옵션만 확인하며 추론을 호출하지 않는다. `ready: true`는 실제 이미지 추론까지 성공했다는 뜻은 아니다.

`doctor`와 `generate`는 기존 로그인에 접근하기 위해 호스트에서 실행한다. 추가 Python 패키지가 필요 없다. 나머지 명령은 선택한 실행 환경을 사용한다. `./team setup --backend local`은 저장소의 `.venv`에 `requirements-local.txt`의 Pillow만 설치하며 Docker를 호출하지 않는다. 가상환경 활성화는 필요 없다. 최초 설치에는 인터넷 연결이 필요하며 시스템 Python 패키지를 변경하지 않는다. Docker를 사용하려면 `./team setup --backend docker`를 실행한다. 선택은 Git에서 제외한 `.pipeline-backend`에 저장하고, 이후 인자 없는 `./team setup`은 같은 방식을 유지한다. 설정이 없을 때의 기본은 기존 Docker 방식이다. 설치 실패 시 이전 선택을 유지한다. Python에 venv 또는 pip가 없다면 해당 기능을 제공하는 Python 환경이나 Docker를 준비해야 하며 시스템 패키지를 자동 설치하지 않는다.

## 2. ScreenSpot-v2 준비

공식 배포에서 이미지 약 1.3GB와 세 환경의 주석을 내려받는다. 지정 revision을 실제 commit으로 해석해 `source.json`에 기록한다. `data/`와 `runs/`는 Git에서 제외한다.

```bash
./pipeline fetch-screenspot --output data/screenspot-v2
./pipeline prepare --adapter screenspot_v2 \
  --annotations data/screenspot-v2 \
  --image-root data/screenspot-v2/images \
  --dataset OS-Copilot/ScreenSpot-v2 \
  --source-info data/screenspot-v2/source.json \
  --role pilot_dev --output data/screenspot-v2/manifest.jsonl
./pipeline pilot --manifest data/screenspot-v2/manifest.jsonl \
  --count 30 --seed 42 --output data/pilot30.jsonl
```

변환 결과의 건수와 오류는 `manifest.prepare.json`에 기록한다.

ScreenSpot-v2의 픽셀 `xywh` box를 원본 이미지 기준 `[0,1]`의 `xyxy` box와 중심점으로 변환한다. 원본 값, 이미지 크기, 이미지 hash, 디코딩한 픽셀의 화면 그룹을 함께 보존한다. 잘못된 box는 임의로 보정하지 않고 준비 오류 목록에 남긴다.

표본 추출은 플랫폼과 text/icon 층을 순환하며 같은 화면 그룹을 한 번만 선택한다. 여섯 층에 충분한 서로 다른 화면이 있으면 층마다 5개씩 선택한다. 부족하면 실제 분포를 selection 파일에 기록하고, 총 30개 서로 다른 그룹을 확보하지 못하면 실패한다. `screenspot_v2` 변환기로는 `train` manifest를 만들 수 없다.

## 3. 생성과 재개

먼저 호출 없는 실행 계획을 확인한다.

```bash
./pipeline generate --manifest data/pilot30.jsonl --provider codex \
  --output runs/pilot30-codex --dry-run
```

이후 구독으로 생성한다. 처음 연결을 확인할 때는 `--limit 1`을 사용한다. 같은 명령에서 `--limit`을 제거하면 완료한 입력을 건너뛰고 나머지를 생성한다.

```bash
./pipeline generate --manifest data/pilot30.jsonl --provider codex \
  --output runs/pilot30-codex --limit 1
./pipeline generate --manifest data/pilot30.jsonl --provider claude \
  --output runs/pilot30-claude --limit 1
```

```bash
./pipeline generate --manifest data/pilot30.jsonl --provider codex \
  --output runs/pilot30-codex
./pipeline generate --manifest data/pilot30.jsonl --provider claude \
  --output runs/pilot30-claude
```

필요하면 `--model MODEL_ID`로 명시적인 모델을 선택할 수 있다. 기본 모드에서는 `cli_default`로 기록하며 실제 모델 정보는 CLI가 노출하는 범위만 남긴다. Codex는 개인 config와 AGENTS 문맥을 제외한 CLI 기본 모델을 사용한다. 정확한 모델 snapshot 재현이 필요하면 명시 모델을 지정한다.

각 입력은 새 세션에서 순차 처리한다. 임시 작업 폴더에는 원본 화면과 출력 schema만 제공한다. Codex는 이미지를 첨부하고, Claude는 읽기 도구로 같은 이미지를 받는다. 예상하지 않은 도구 사용이나 Claude의 이미지 전달 미확인 결과는 실패로 처리한다. CLI의 내부 reasoning과 이미지 base64 이벤트는 결과 파일에 보존하지 않는다.

실행 폴더의 `run.json`에는 데이터와 설정의 identity를 기록한다. 모델 지정, 프롬프트, schema, CLI 버전 또는 입력이 바뀌면 같은 폴더에서 재개하지 않는다. 샘플별 `jobs/*/attempt-*.json`에 시도 이력을 남기고, `result.json`에 최신 결과를 둔다. 한 폴더를 두 생성기가 동시에 수정할 수 없다.

`--timeout`은 입력당 초 단위 제한으로 기본 300, `--retries`는 일시적인 오류의 추가 재시도 횟수로 기본 1이다. 인증 실패, 구독 한도, 모델 설정 오류에서는 중단하고 상태를 남긴다. 출력 내용이 잘못된 경우 자동으로 좋은 결과가 나올 때까지 재생성하지 않는다. 완성됐으나 검증에 실패한 출력도 검수 대상으로 보존한다.

## 4. 검수

```bash
./pipeline summary --run runs/pilot30-codex
./pipeline review --run runs/pilot30-codex --output runs/pilot30-codex/review
```

`review.html`을 로컬 브라우저에서 열어 원본 화면, 지시, 정답과 생성 설명을 확인한다. `scores.csv`의 `evidence`, `target_match`, `usefulness`, `consistency`에 0-2점을 기록하고, `decision`을 `accept` 또는 `reject`, `reviewer`를 검수자 식별자로 채운다. 보고서를 다시 만들어도 기존 점수 파일은 덮어쓰지 않는다.

정답을 이미 제공한 생성이므로 최종 좌표 일치는 독립적인 grounding 성능이 아니다. 설명의 화면 근거와 유용성을 사람이 확인해야 한다.

```bash
./pipeline export --run runs/pilot30-codex \
  --scores runs/pilot30-codex/review/scores.csv \
  --output runs/pilot30-codex/expert.jsonl --allow-pilot
```

자동 검증 통과, 교사 `ok`, 사람의 명시적인 채택, 검수자 기록, 총 6/8 이상과 모든 항목 1점 이상을 만족한 결과만 export한다. 파일럿은 `--allow-pilot`이 있어야 export할 수 있고, 출력에도 `exclude_from_training: true`를 유지한다. validation/test는 export하지 않는다. 최종 SFT 데이터에서는 파일럿을 제외한다.

## 5. 다른 데이터셋 연결

OS-Atlas의 `img_filename`, `instruction`, 정규화 `xyxy` box는 `--adapter os_atlas`로 변환한다. 원본 주석 형식이 다르면 `--adapter mapped --mapping configs/mapped-example.json`을 사용한다.

```bash
./pipeline prepare --adapter mapped \
  --annotations data/custom/annotations.json \
  --image-root data/custom/images \
  --dataset custom/source --revision local-v1 --role train \
  --mapping configs/mapped-example.json --output data/custom/manifest.jsonl
```

매핑의 `records_path`는 JSON 안의 레코드 목록, `items_path`는 한 화면에 달린 여러 요소 목록을 지정한다. 후자는 부모 레코드와 요소 필드를 합쳐 처리한다. 필드 경로는 `screenshot.path`처럼 점으로 구분한다. `image`, `instruction`, `bbox` 또는 `point`, `bbox_format`, `units`를 지정한다. 단위는 `pixels`, `normalized`, `1000`, box 형식은 `xywh`, `xyxy`를 지원한다. 유형이 없으면 `unknown`을 유지한다.

이미지 경로는 `image-root` 안에 있어야 한다. EXIF 방향 변환이 있는 이미지는 좌표가 달라질 수 있어 upstream에서 정규화한 뒤 다시 준비해야 한다. Aria-UI의 다양한 annotation 변형은 실제 사용할 파일의 필드를 확인해 매핑하거나 새 변환기를 추가해야 하며, 모든 변형을 검증한 전용 adapter는 아직 제공하지 않는다.

## 6. 팀 작업 분담과 취합

```bash
./pipeline shard --manifest data/custom/manifest.jsonl \
  --count 3 --output data/shards
./pipeline merge --runs runs/worker-a runs/worker-b \
  --output runs/merged
```

`shard`는 같은 화면 그룹을 나누지 않고 분담한다. `sizes`를 확인해 빈 shard를 배정하지 않는다. 팀원이 다른 컴퓨터에서 실행할 때는 이미지까지 포함한 데이터 ZIP을 만든다.

```bash
./pipeline bundle-data --manifest data/shards/shard-000.jsonl \
  --output dist/assignment-a.zip
```

프로그램은 [GitHub 저장소](https://github.com/Sucrose122211/GUI-task-trajectory-generator)를 clone해 받고, 담당 데이터 ZIP은 별도로 전달한다. 저장소에는 실행 도구, 사람과 에이전트용 매뉴얼, 데이터 매핑 예제, 합성 화면과 검사 코드가 들어간다. 기존 실험 데이터와 결과, 로그인 정보, 머신별 작업 기록은 넣지 않는다. 코드 변경과 자동 검사는 [GitHub 배포 운영 안내](github-distribution.md)를 따른다. `./team release`의 프로그램 ZIP은 오프라인 전달이 필요한 경우의 보조 기능이다.

팀원은 데이터 ZIP을 `data/`에 풀어 `data/assignment-a/manifest.jsonl`을 사용한다. `bundle-data`는 원본 이미지 hash를 확인하고, 이미지 경로만 묶음 안의 상대 경로로 바꾼다. ID, 정답, 역할, 출처는 유지한다.

```bash
./team submit --output dist/worker-a-results.zip
# 상세 명령을 직접 사용할 수도 있다.
./pipeline bundle-run --run runs/worker-a --output dist/worker-a-results-v2.zip
```

제출 ZIP에는 원본 화면, manifest, run 설정, 작업별 최신 result, 존재하는 경우 `review/scores.csv`가 들어간다. 시도별 이력과 비공개 CLI 로그는 넣지 않는다. 부분 생성과 실패도 보존하므로 제출 전 `status`로 상태를 확인한다. 배포 ZIP에는 파일별 `SHA256SUMS.txt`와 종류 및 버전을 기록한 `BUNDLE.json`이 있다. 기존 ZIP은 덮어쓰지 않으므로 재제출할 때 새 파일명을 쓴다.

받은 결과를 `runs/incoming/`에 각각 푼 뒤 새 폴더로 병합한다.

```bash
./pipeline merge --runs runs/incoming/worker-a-results runs/incoming/worker-b-results \
  --output runs/merged
./pipeline review --run runs/merged --output runs/merged/review
```

`merge`는 이미지 hash를 검증하며, 다른 컴퓨터에서 같은 이미지를 각각 복사한 경로 차이는 허용한다. 같은 입력의 다른 교사 결과를 함께 보존하고, 같은 작업 ID의 다른 결과는 충돌로 처리한다. 병합 대상 폴더는 비어 있어야 한다. 프롬프트와 교사 설정은 결과별로 남아 서로 다른 설정의 결과를 식별할 수 있다.

사람의 점수표는 자동 병합하지 않는다. 각 제출 폴더의 CSV를 보존하고, 검수한 행을 `job_id` 기준으로 병합 폴더의 점수표에 옮긴다. 중복되거나 판정이 다른 행은 담당자가 확인한다. 개인 로그인 정보는 제출하지 않는다.

## 7. 개발 검사

```bash
make check
```

컨테이너에서 lint, format 검사, 단위 및 가짜 CLI를 실행하는 통합 검사, wheel build를 수행한다. 검사 자체는 구독이나 외부 모델 호출을 사용하지 않는다. 실제 서비스 연결 여부는 별도의 제한 수량 실행으로 확인한다.
