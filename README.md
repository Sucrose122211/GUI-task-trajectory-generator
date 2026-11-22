# GUI Task Trajectory Generator

GUI 화면, 태스크, 정답을 Codex 또는 Claude의 구독 기반 CLI에 제공해 영어 텍스트 trajectory를 생성한다. 데이터 변환, 순차 생성과 재개, 검수, 팀별 분담과 결과 취합을 지원한다. 모델 이름을 지정하지 않으면 CLI 기본 모델을 사용한다.

## 시작하기

Linux 또는 WSL에서 Git, Python 3.10 이상, Docker와 사용할 교사의 CLI 및 구독 로그인이 필요하다.

```bash
git clone https://github.com/Sucrose122211/GUI-task-trajectory-generator.git
cd GUI-task-trajectory-generator
./team setup
```

담당 데이터는 `data/`에 둔 뒤 다음과 같이 실행한다. Claude를 사용하면 `--provider claude`를 선택한다.

```bash
./team init --provider codex --manifest data/assignment-a/manifest.jsonl
./team doctor
./team plan
./team run --limit 1
./team run
./team review
./team submit
```

`plan`까지는 생성하지 않는다. `run`은 구독 사용량을 소비하며, 같은 명령으로 완료한 입력을 건너뛰고 재개한다. 담당 데이터가 없으면 [합성 예제](docs/dataset-adaptation.md#1-포함된-예제로-변환-확인)로 변환과 계획 확인부터 실행할 수 있다.

## 매뉴얼

| 읽는 사람과 목적 | 문서 |
| --- | --- |
| 팀원, 처음 실행 | [빠른 시작](QUICKSTART.md) |
| 에이전트, 구조와 실행 계약 파악 | [에이전트 안내](docs/agent-manual.md) |
| 새 데이터셋 연결 | [데이터셋 적응 안내](docs/dataset-adaptation.md) |
| 상세 명령과 검수 기준 | [파이프라인 실행 안내](docs/pipeline-usage.md) |
| 저장소 운영과 팀 배포 | [GitHub 배포 운영 안내](docs/github-distribution.md) |
| 에이전트에게 역할별 단계 안내 받기 | [사용법 스킬](docs/usage-skill.md) |

에이전트 채팅에서 `/사용법 담당자` 또는 `/사용법 팀원`으로 역할별 절차를 요청할 수 있다. Codex 입력창에서 한글 slash 명령을 거절하면 `$gui-trajectory-usage 담당자` 또는 `$gui-trajectory-usage 팀원`으로 호출한다. 자세한 불러오기 방법은 [사용법 스킬](docs/usage-skill.md)을 참고한다.

## 데이터와 결과 전달

프로그램은 이 저장소를 clone하거나 pull해서 받는다. 담당 데이터는 `./pipeline bundle-data`로 원본 이미지와 함께 따로 전달하고, 팀원은 `./team submit`으로 결과 ZIP을 만든다. 실제 데이터, 생성 결과, 개인 인증 정보는 Git에서 제외한다. `examples/demo/`에는 설치 확인용 합성 화면과 주석만 포함한다.

## 개발 검사

```bash
make build
make check
```

컨테이너에서 정적 검사, 가짜 교사를 이용한 통합 검사와 패키지 빌드를 실행한다. GitHub Actions에서도 같은 검사를 실행하며, 상용 모델이나 구독 로그인을 사용하지 않는다.

## 연구 범위

하버드 논문 *Finetuning with Sampling: SFT Learns Better Than You Think*의 후속 실험을 위한 텍스트 trajectory baseline이다. ScreenSpot-v2 30개를 두 교사로 비교한 파일럿에서 시작했으며, 다른 생성 데이터셋은 변환기를 통해 연결한다. ScreenSpot-v2는 `pilot_dev`로 유지하고 최종 평가는 ScreenSpot-Pro를 사용한다. 이 저장소는 교사 데이터 생성까지 제공하며 projection sampling과 학생 모델 SFT는 포함하지 않는다.
