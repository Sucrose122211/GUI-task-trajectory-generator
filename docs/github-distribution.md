# GitHub 배포 운영 안내

프로그램과 매뉴얼은 GitHub 저장소로 배포합니다. 팀원은 clone 후 `./team setup`을 실행하고, 자기 구독으로 생성합니다. 원본 데이터와 생성 결과는 별도 파일로 전달합니다.

## 저장소에 들어가는 것

- `README.md`, `QUICKSTART.md`, `AGENTS.md`.
- `team`, `pipeline`, `src/`, `tests/`.
- `Dockerfile`, `Makefile`, 패키지와 개발 의존성 설정.
- `configs/`, `examples/demo/`의 합성 화면과 주석.
- 사람용, 에이전트용, 데이터 적응 및 운영 문서.
- `.github/workflows/check.yml` 자동 검사.

실제 데이터, 생성 결과, 논문 PDF, 검수 산출물, 개인 인증 디렉터리와 로컬 작업 기록은 제외합니다. `.gitignore`를 제공하며, 처음 커밋할 때도 코드 경로를 명시적으로 선택합니다.

## 저장소와 접근 권한

저장소는 [Sucrose122211/GUI-task-trajectory-generator](https://github.com/Sucrose122211/GUI-task-trajectory-generator)입니다. 비공개로 운영하면 소유자가 팀원의 GitHub 계정에 접근 권한을 부여합니다. 각 팀원은 자기 GitHub 로그인으로 clone하고, 상용 교사 인증은 별도로 자기 구독 로그인을 사용합니다.

다른 프로젝트에 같은 구조의 저장소를 새로 만들려면 GitHub 웹에서 빈 저장소를 만들거나, 이미 GitHub CLI로 로그인한 담당자 환경에서 다음 명령을 사용합니다.

```bash
gh auth status
gh repo create gui-trajectory --private
```

## 팀원에게 전달할 것

1. GitHub 저장소 URL과 접근 권한.
2. `QUICKSTART.md` 링크.
3. 담당 데이터 ZIP과 사용할 교사(Codex 또는 Claude).

```bash
./pipeline shard --manifest data/custom/manifest.jsonl --count 3 --output data/shards
./pipeline bundle-data --manifest data/shards/shard-000.jsonl --output dist/assignment-a.zip
```

데이터 ZIP에는 이미지도 포함됩니다. 저장소에 대용량 데이터를 커밋하지 않습니다. 팀원은 데이터 ZIP을 clone한 폴더의 `data/`에 풀고 매뉴얼대로 실행합니다. 구독 인증은 각자 자기 컴퓨터에서 유지합니다.

## 수정과 자동 검사

기능 변경은 별도 브랜치에서 커밋하고 PR로 검토합니다. `main` push와 PR에서 GitHub Actions가 컨테이너 빌드, Ruff 검사, 가짜 교사 테스트, wheel build를 실행합니다. 구독 로그인이나 상용 모델 호출은 하지 않습니다. 검사 설정은 [공식 checkout 액션](https://github.com/actions/checkout)의 v6를 사용하며 읽기 권한만 요청합니다.

```bash
make build
make check
git switch -c improve-pipeline
# 변경한 코드와 문서 경로를 명시해서 add, commit한 뒤 해당 브랜치를 push합니다.
```

같은 버전의 CLI와 코드에서 생성된 결과끼리 묶고, 생성 설정이 바뀌면 새 결과 폴더를 사용합니다. 안정된 시점의 commit 또는 tag를 팀에 공지하면 같은 코드를 맞춰 쓰기 쉽습니다.

## 결과 취합

팀원은 `./team submit --output dist/worker-a-results.zip`으로 결과를 제출합니다. 담당자는 각 ZIP을 `runs/incoming/`에 풀고 새 폴더로 병합합니다.

```bash
./pipeline merge --runs runs/incoming/worker-a-results runs/incoming/worker-b-results \
  --output runs/merged
./pipeline review --run runs/merged --output runs/merged/review
```

점수 CSV는 자동으로 합치지 않습니다. 상세 기준은 [실행 안내](pipeline-usage.md)와 [에이전트 안내](agent-manual.md)에 있습니다.

`./team release`의 소프트웨어 ZIP은 오프라인 전달이 필요할 때 쓸 수 있는 보조 기능입니다. 일반적인 코드 배포와 업데이트는 GitHub clone과 pull을 사용합니다.
