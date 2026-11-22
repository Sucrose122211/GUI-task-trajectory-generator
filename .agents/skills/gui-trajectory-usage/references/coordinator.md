# 담당자 사용법

담당자가 원본 데이터를 준비해 나누고, 팀원들의 결과를 받아 병합하고 최종 검수하는 절차다. 아래는 팀원 A, B, C 세 명의 예시다. 실제 데이터셋은 팀에서 정한다. `team/custom`, `local-v1`, 파일 경로는 선택한 데이터에 맞게 바꾼다.

## 1. 저장소 접근과 공통 환경 준비

팀원에게 저장소 접근 권한을 제공한다. 담당자와 팀원 모두 Linux 또는 WSL에서 Git, Python 3.10 이상과 실행 중인 Docker를 준비한다. 생성 팀원은 사용할 교사의 CLI와 구독 로그인이 추가로 필요하다.

```bash
git clone https://github.com/Sucrose122211/GUI-task-trajectory-generator.git
cd GUI-task-trajectory-generator
./team setup
git rev-parse HEAD
```

이미 clone했다면 해당 폴더에서 작업한다. 출력된 커밋 값을 배정 안내에 기록해 팀원들이 같은 코드와 프롬프트를 쓰게 한다. 이후 명령은 저장소 루트에서 실행한다.

## 2. 원본 데이터와 매핑 준비

```bash
mkdir -p data/custom/images
cp configs/mapped-example.json data/custom/mapping.json
```

선정한 원본 주석은 `data/custom/annotations.json`, 이미지는 `data/custom/images/`에 놓는다. 매핑 예제를 실제 주석에 맞게 수정한다. 기존 예제는 `samples` 배열, `screenshot.path`, `query`, 정규화된 `target.box`의 xyxy 형식이다. 픽셀 xywh를 쓰는 원본에 이 설정을 그대로 적용하면 안 된다. `docs/dataset-adaptation.md`에서 필드, 좌표 단위, 점 정답 및 다중 대상 설정을 확인한다.

## 3. 공통 manifest로 변환

아래는 학습용으로 사용할 수 있는 별도 데이터셋의 예시다. ScreenSpot-v2 파일럿은 전용 변환기와 `pilot_dev` 역할을 사용한다.

```bash
./pipeline prepare \
  --adapter mapped \
  --annotations data/custom/annotations.json \
  --image-root data/custom/images \
  --mapping data/custom/mapping.json \
  --dataset team/custom --revision local-v1 --role train \
  --output data/custom/manifest.jsonl

cat data/custom/manifest.prepare.json
```

생성된 `manifest.jsonl`과 보고서의 `valid`, `invalid`, `errors`를 확인한다. 잘못된 주석은 오류 목록에 남으며 입력에서 빠진다. 전부 오류여도 변환 보고서는 만들어지므로 명령 성공만으로 판단하지 않는다.

## 4. 팀원별 입력 분배

```bash
./pipeline shard \
  --manifest data/custom/manifest.jsonl \
  --count 3 --output data/shards
```

`shard-000.jsonl`, `shard-001.jsonl`, `shard-002.jsonl`이 만들어진다. 출력의 `sizes`를 확인한다. 같은 원본 화면 그룹은 분리하지 않으며 화면 그룹이 부족하면 빈 shard가 생길 수 있다. 빈 할당을 배정하지 않는다.

```bash
./pipeline bundle-data --manifest data/shards/shard-000.jsonl --output dist/assignment-a.zip
./pipeline bundle-data --manifest data/shards/shard-001.jsonl --output dist/assignment-b.zip
./pipeline bundle-data --manifest data/shards/shard-002.jsonl --output dist/assignment-c.zip
```

세 ZIP에 각 입력과 원본 이미지가 들어간다. ZIP은 덮어쓰지 않으므로 다시 만들 때 새 이름을 정한다.

## 5. 배정표와 파일 전달

| 팀원 | 입력 ZIP | 교사 예시 | 제출 파일명 |
| --- | --- | --- | --- |
| A | assignment-a.zip | Codex | member-a.zip |
| B | assignment-b.zip | Claude | member-b.zip |
| C | assignment-c.zip | Codex | member-c.zip |

저장소 URL, 코드 커밋, 담당 ZIP, 교사, 배정 건수, 결과를 올릴 공유 위치를 전달한다. 코드만 GitHub에서 배포하며 실제 데이터와 결과 ZIP은 따로 전달한다. 이 표는 입력을 나눠 생성량을 확보하는 예시다. 같은 입력에서 두 교사를 비교하려면 동일 assignment를 Codex와 Claude 담당자에게 각각 전달한다.

## 6. 제출 파일 수령과 압축 해제

팀원은 `team submit`으로 ZIP을 만들고 정해진 위치에 직접 전달한다. 담당자는 받은 파일을 `runs/incoming/`에 놓는다.

```bash
mkdir -p runs/incoming
python3 -m zipfile -e runs/incoming/member-a.zip runs/incoming/
python3 -m zipfile -e runs/incoming/member-b.zip runs/incoming/
python3 -m zipfile -e runs/incoming/member-c.zip runs/incoming/
```

내부 폴더명은 ZIP 생성 당시 파일명에 따라 `member-a`, `member-b`, `member-c`가 된다. ZIP 이름만 나중에 바꿨다면 실제 내부 폴더명을 확인해 아래 경로에 적용한다. 이전 제출을 유지하려면 재제출은 새 ZIP 이름과 새 내부 폴더명으로 받는다.

## 7. 배정 건수와 제출 결과 대조

```bash
./pipeline summary --run runs/incoming/member-a
./pipeline summary --run runs/incoming/member-b
./pipeline summary --run runs/incoming/member-c
```

`summary`는 저장된 결과만 집계한다. 이것만으로 아직 생성하지 않은 입력 수까지 알 수는 없다. `bundle-data` 때 기록한 배정 건수, 각 제출의 `BUNDLE.json`에 있는 `samples`와 `jobs`, 실패 집계를 대조한다. 하나의 교사에 배정한 입력 수와 작업 결과 수가 일치하는지 확인하고, 실패나 누락은 해당 팀원에게 재개 후 재제출을 요청한다. 하나의 assignment를 두 교사로 생성했다면 두 제출을 각각 확인한다.

## 8. 결과 병합

```bash
./pipeline merge \
  --runs runs/incoming/member-a runs/incoming/member-b runs/incoming/member-c \
  --output runs/merged
```

병합 대상은 새 폴더 또는 빈 폴더다. 원본 이미지 hash를 확인하고 동일한 작업의 같은 결과는 합친다. 같은 작업 ID의 서로 다른 결과는 충돌로 중단한다. 다른 교사 결과는 보존한다. 재제출 v2가 있으면 그 사람의 이전 제출을 함께 넣지 말고 사용할 버전을 선택한다. `runs/merged/manifest.jsonl`은 제출 폴더의 이미지를 참조하므로 `runs/incoming/`을 유지한다.

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
