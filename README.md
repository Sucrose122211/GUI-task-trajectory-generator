# GUI Task Trajectory Generator

이번 임시 운영에 한해 사용자 요청으로 루트 `.env`의 공용 팀 키와 주소를 커밋합니다. 다른 프로젝트에 적용할 일반 규칙이 아닙니다. Codex/Claude 개인 인증은 계속 제외합니다. [저장소 한정 설정 설명](docs/repository-only-settings.md)에 범위와 우선순위를 기록했습니다.

GUI 화면, 태스크, 정답을 Codex 또는 Claude의 구독 기반 CLI에 제공해 영어 텍스트 trajectory를 생성한다. 데이터 변환, 순차 생성과 재개, 검수, 팀별 분담과 결과 취합을 지원한다. 모델 이름을 지정하지 않으면 CLI 기본 모델을 사용한다.

## 이번 팀 생성

이전 파일럿과 같은 ScreenSpot-v2의 전체 유효 입력 1,271건을 seed 42로 8묶음으로 나눈다. 팀원 약 4명이 하나씩 가져가고 끝나면 다음 묶음을 받는다. 같은 입력을 Codex와 Claude로 생성하므로 시트에는 교사별 8개, 총 16작업이 생긴다. ScreenSpot-v2는 `pilot_dev`로 유지한다.

담당자와 팀원 모두 [ScreenSpot-v2 팀 실행 가이드](docs/screenspot-team-run.md)를 기준으로 다운로드, 변환과 8분할을 재현한다. 묶음은 159건 7개와 158건 1개다. 팀원은 시트와 점수표를 관리하지 않는다.

## 시작하기

Linux 또는 WSL에서 Git, Python 3.10 이상과 사용할 교사의 CLI 및 구독 로그인이 필요하다. Docker가 없으면 아래 로컬 실행을 선택한다.

```bash
git clone https://github.com/Sucrose122211/GUI-task-trajectory-generator.git
cd GUI-task-trajectory-generator
./team setup --backend local
```

저장소의 `.venv`에 이미지 처리 라이브러리만 설치한다. 시스템 Python 패키지는 변경하지 않으며 가상환경을 직접 활성화할 필요도 없다. Python의 `venv`와 `pip`, 최초 설치 시 인터넷 연결이 필요하다. Docker를 사용하려면 `./team setup --backend docker`를 실행한다. 선택은 이 컴퓨터의 저장소에 기억되며, 이후 `./team setup`은 같은 방식을 사용한다.

전체 데이터는 담당자가 안내한 방법으로 `data/`에 준비한다. [공유 배정 설정](docs/shared-assignment.md)을 한 번 마친 뒤 다음과 같이 자동으로 작업을 받는다. Claude를 사용하면 `--provider claude`를 선택한다.

```bash
./team join --worker member-a --provider codex
./team acquire
./team doctor
./team plan
./team run --limit 1
./team run
./team review
./team submit
```

`join`은 커밋된 공용 `.env`를 자동으로 읽고 배정과 진행 상태를 기록한다. 키 입력이나 환경 변수 설정은 필요 없다. 팀원은 시트나 점수표를 관리하지 않는다. 전량 생성 후 `submit`하고 `acquire`하면 다음 작업을 받는다. `plan`까지는 생성하지 않는다. `run`은 구독 사용량을 소비하며, 같은 명령으로 완료한 입력을 건너뛰고 재개한다. 담당 데이터가 없으면 [합성 예제](docs/dataset-adaptation.md#1-포함된-예제로-변환-확인)로 변환과 계획 확인부터 실행할 수 있다.

## 매뉴얼

| 읽는 사람과 목적 | 문서 |
| --- | --- |
| 담당자와 팀원, 이번 ScreenSpot 8분할 실행 | [ScreenSpot 팀 가이드](docs/screenspot-team-run.md) |
| 담당자, 공유 시트 최초 설정 | [자동 배정 안내](docs/shared-assignment.md) |
| 팀원, 처음 실행 | [빠른 시작](QUICKSTART.md) |
| 에이전트, 구조와 실행 계약 파악 | [에이전트 안내](docs/agent-manual.md) |
| 새 데이터셋 연결 | [데이터셋 적응 안내](docs/dataset-adaptation.md) |
| 상세 명령과 검수 기준 | [파이프라인 실행 안내](docs/pipeline-usage.md) |
| 저장소 운영과 팀 배포 | [GitHub 배포 운영 안내](docs/github-distribution.md) |
| 에이전트에게 역할별 단계 안내 받기 | [사용법 스킬](docs/usage-skill.md) |

에이전트 채팅에서 `/사용법 담당자` 또는 `/사용법 팀원`으로 역할별 절차를 요청할 수 있다. Codex 입력창에서 한글 slash 명령을 거절하면 `$gui-trajectory-usage 담당자` 또는 `$gui-trajectory-usage 팀원`으로 호출한다. 자세한 불러오기 방법은 [사용법 스킬](docs/usage-skill.md)을 참고한다.

## 데이터와 결과 전달

프로그램은 이 저장소를 clone하거나 pull해서 받는다. 팀원은 같은 전체 데이터와 campaign 파일을 준비하고 `acquire`로 자기 입력을 선택한다. 기존 수동 ZIP 배분도 지원한다. 팀원은 `./team submit`으로 결과 ZIP을 만든다. 실제 데이터, 생성 결과, `.team/`의 연결 정보와 개인 인증 정보는 Git에서 제외한다. `examples/demo/`에는 설치 확인용 합성 화면과 주석만 포함한다.

## 개발 검사

```bash
make build
make check
```

컨테이너에서 정적 검사, 가짜 교사를 이용한 통합 검사와 패키지 빌드를 실행한다. GitHub Actions에서도 같은 검사를 실행하며, 상용 모델이나 구독 로그인을 사용하지 않는다.

## 연구 범위

하버드 논문 *Finetuning with Sampling: SFT Learns Better Than You Think*의 후속 실험을 위한 텍스트 trajectory baseline이다. ScreenSpot-v2 30개를 두 교사로 비교한 초기 파일럿에서 시작했고, 이번 팀 실행은 같은 데이터셋의 전체 유효 입력을 8묶음으로 생성한다. 다른 데이터셋은 변환기로 연결할 수 있다. ScreenSpot-v2는 `pilot_dev`로 유지하고 최종 평가는 ScreenSpot-Pro를 사용한다. 이 저장소는 교사 데이터 생성까지 제공하며 projection sampling과 학생 모델 SFT는 포함하지 않는다.
