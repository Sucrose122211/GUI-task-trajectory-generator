# 다른 GUI 데이터셋 연결하기

생성기는 공통 manifest만 읽습니다. 데이터셋이 바뀌면 이미지와 주석을 준비하고 변환기만 바꾸면 됩니다. 프롬프트와 생성 코드는 그대로 사용할 수 있습니다.

현재 팀 실행의 ScreenSpot-v2 다운로드와 8분할은 [ScreenSpot 팀 가이드](screenspot-team-run.md)를 따릅니다. 아래 합성 예제는 설치 확인용이며 이번 실제 작업 범위를 대체하지 않습니다.

## 1. 포함된 예제로 변환 확인

프로그램에는 저장과 취소 버튼이 있는 합성 화면 한 장과 지시문 두 개가 있습니다. 실제 벤치마크나 학습 데이터가 아닌 설치 확인용 예제입니다. 먼저 Docker 없이 사용하려면 `./team setup --backend local`을, Docker를 사용하려면 `./team setup --backend docker`를 실행하세요. 이후 변환 명령은 같습니다.

```bash
./pipeline prepare --adapter mapped \
  --annotations examples/demo/annotations.json --image-root examples/demo/images \
  --mapping examples/demo/mapping.json \
  --dataset synthetic/demo --revision demo-v1 --role pilot_dev \
  --output data/demo/manifest.jsonl
./team --config demo-job.json init --provider codex --manifest data/demo/manifest.jsonl \
  --output runs/demo-codex
./team --config demo-job.json plan
```

여기까지는 모델을 호출하지 않습니다.

공유 배정에 참여할 때는 각자 같은 전체 데이터와 revision으로 위 변환을 수행합니다. 담당자의 공통 campaign 파일과 일치해야 join과 acquire가 가능합니다. [자동 배정 안내](shared-assignment.md)를 참고하세요.

## 2. 변환기 선택

| 원본 데이터 | 변환기 | 가정하는 좌표 형식 |
| --- | --- | --- |
| ScreenSpot-v2 | `screenspot_v2` | 픽셀 `xywh`, 이 프로젝트에서는 `pilot_dev`만 허용 |
| OS-Atlas와 같은 주석 형식 | `os_atlas` | `img_filename`, `instruction`, `bbox` 필드, 정규화 `xyxy` |
| 다른 JSON / JSONL | `mapped` | 대응표에서 필드 이름, 단위, box 형식 지정 |

## 3. 자기 데이터 놓기

배포 폴더 안에 다음과 같이 둡니다.

```text
data/custom/
  annotations.json
  mapping.json
  images/
    screen-001.png
```

예를 들어 원본 주석이 다음과 같다면:

```json
{
  "samples": [
    {
      "id": "sample-001",
      "screenshot": {"path": "screen-001.png"},
      "query": "Click Save",
      "target": {"box": [30, 55, 90, 40], "type": "text"}
    }
  ]
}
```

`mapping.json`을 다음과 같이 만듭니다.

```json
{
  "records_path": "samples",
  "image": "screenshot.path",
  "instruction": "query",
  "bbox": "target.box",
  "bbox_format": "xywh",
  "units": "pixels",
  "id": "id",
  "platform_value": "desktop",
  "element_type": "target.type"
}
```

```bash
./pipeline prepare --adapter mapped \
  --annotations data/custom/annotations.json --image-root data/custom/images \
  --mapping data/custom/mapping.json \
  --dataset team/custom --revision local-v1 --role train \
  --output data/custom/manifest.jsonl
```

생성 전에 `manifest.prepare.json`의 `valid`, `invalid`, `errors`를 확인합니다. 변환 오류는 생성 대상에서 빼고 목록에 남기며, 좌표를 임의로 보정하지 않습니다. 전부 오류여도 보고서를 만들므로 명령 성공만으로 판단하지 마세요. `team init`은 빈 manifest를 거절합니다.

## 4. 대응표 항목

| 키 | 내용 |
| --- | --- |
| `records_path` | JSON 안의 레코드 배열. 최상위가 배열인 JSON / JSONL이면 생략 |
| `items_path` | 한 화면에 여러 대상이 있을 때 대상 배열. 부모와 자식을 합치며 같은 필드는 자식 값 우선 |
| `image` | `image-root` 기준 이미지 경로가 담긴 필드 |
| `instruction` | 원본 지시문 필드 |
| `bbox` / `point` | box 4개 수 / 점 2개 수의 필드. 적어도 하나 필요 |
| `bbox_format` | box가 있으면 필수. `xywh` 또는 `xyxy` |
| `units` | 필수. `pixels`, `normalized`, `1000` 중 하나 |
| `id` | 원본 레코드 식별자. 생략하면 레코드와 대상의 인덱스 사용 |
| `platform` / `platform_value` | 환경이 담긴 필드 / 고정 환경 값. 없으면 `unknown` |
| `element_type` | text / icon 등이 담긴 필드. 없으면 `unknown` |
| `group` | 같은 원본 화면의 식별자 필드. crop이나 재인코딩 화면도 같은 담당에게 배정할 때 지정 |

필드 경로에는 `target.box`처럼 점 구분을 사용합니다. 좌표 순서나 열 이름을 자동으로 추정하지 않습니다. 화면 크기와 hash는 이미지에서 읽습니다.

### 좌표 예시

- 너비 300, 높이 150인 이미지에서 픽셀 `xywh=[30,55,90,40]`은 내부 `bbox=[0.1,0.366666...,0.4,0.633333...]`, 중심 `point=[0.25,0.5]`가 됩니다.
- 이미 0-1인 `xyxy`는 `units="normalized"`, `bbox_format="xyxy"`로 설정합니다.
- 0-1000인 점만 있으면 `point="target.xy"`, `units="1000"`으로 설정하고 `bbox`, `bbox_format`을 생략합니다. 없는 box를 만들어 넣지 않습니다.
- box와 점을 모두 주면 같은 단위여야 하며, 점은 box 안에 있어야 합니다.

### 한 화면에 여러 대상

```json
{
  "screens": [
    {
      "image": "screen-001.png",
      "screen_id": "screen-001",
      "targets": [
        {"id": "save", "query": "Click Save", "box": [30,55,90,40]},
        {"id": "cancel", "query": "Click Cancel", "box": [170,55,90,40]}
      ]
    }
  ]
}
```

이 형식은 `records_path="screens"`, `items_path="targets"`, `image="image"`, `instruction="query"`, `bbox="box"`, `bbox_format="xywh"`, `units="pixels"`, `id="id"`, `group="screen_id"`로 지정합니다. 각 대상이 입력 한 개가 되며, 같은 원본 화면의 대상은 담당을 나눌 때 분리하지 않습니다.

## 5. 변환 뒤에는 같은 실행 방법 사용

```bash
./team --config custom-job.json init --provider claude \
  --manifest data/custom/manifest.jsonl --output runs/custom-claude
./team --config custom-job.json plan
./team --config custom-job.json run --limit 1
./team --config custom-job.json run
```

팀원별로 나누려면:

```bash
./pipeline shard --manifest data/custom/manifest.jsonl --count 3 --output data/shards
./pipeline bundle-data --manifest data/shards/shard-000.jsonl --output dist/assignment-a.zip
```

`assignment-a.zip`에는 이미지도 포함됩니다. 받는 사람은 ZIP을 `data/`에 풀고 `data/assignment-a/manifest.jsonl`을 `team init`에 지정합니다. 화면 그룹이 부족하면 빈 shard가 생길 수 있으므로 `shard`의 `sizes`를 확인하세요. 빈 할당은 ZIP으로 만들 수 없습니다.

## 6. 새 변환기가 필요한 경우

CSV, Parquet, ZIP 내부 이미지, 문자열 좌표, 복잡한 행동 시퀀스는 먼저 JSON / JSONL과 이미지 파일로 풀어냅니다. 같은 화면 위의 정답 점 또는 box로 표현할 수 있으면 `mapped`를 사용할 수 있습니다. 그것으로 표현할 수 없는 경우에만 `data.py`, `cli.py`에 변환기를 추가하고 원본 주석, 좌표 변환, 누락과 범위 초과 사례를 검사합니다.

이미지를 crop / resize하면 주석 좌표도 같은 변환을 적용한 뒤 넣어야 합니다. EXIF 회전이 있는 이미지는 원본 데이터 쪽에서 정규화해야 합니다. 평가 데이터를 `train`으로 바꾸지 말고 역할과 데이터셋 revision을 유지하세요.
