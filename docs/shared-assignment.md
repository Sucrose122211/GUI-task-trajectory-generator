# 공유 시트로 작업 자동 배정하기

팀원은 Google Sheets를 열거나 행을 편집하지 않습니다. 공통 시드와 버전으로 고정한 작업 목록에서 프로그램이 작업을 받고, 생성 중 진행과 종료 상태를 자동 기록합니다. 별도 서버, VPN, Google API SDK 설치는 필요 없습니다. 담당자는 최초 한 번 Google Sheets와 Apps Script 웹 앱을 준비합니다.

## 담당자 1. 새 시트와 배정 서비스 만들기

1. Google Drive에서 새 Google Sheets를 만듭니다. 이름 예: `GUI trajectory 작업 현황`.
2. 시트 메뉴의 `확장 프로그램 → Apps Script`를 엽니다.
3. 기본 `Code.gs` 내용을 지우고 저장소의 `apps-script/Code.gs` 전체를 붙여넣고 저장합니다.
4. Apps Script 왼쪽 `프로젝트 설정`에서 `appsscript.json 매니페스트 파일 표시`를 켭니다. 편집기로 돌아가 `appsscript.json`을 저장소의 같은 이름 파일 내용으로 바꿉니다.
5. 편집기 상단 함수 선택에서 `setup`을 선택하고 실행합니다. 이 시트에 접근하는 권한을 승인합니다. `Campaigns`, `Tasks` 탭을 자동 생성합니다. 다시 실행해도 기존 작업은 지우지 않습니다.
6. `프로젝트 설정 → 스크립트 속성`에서 `TEAM_KEY` 값을 확인합니다. 프로그램이 접속할 때 입력하는 참여 코드입니다. 코드나 시트 셀에 붙여넣지 않고 팀원에게 별도로 전달합니다. `SHEET_ID`도 자동 설정되어 있습니다.
7. `배포 → 새 배포 → 유형 선택 → 웹 앱`을 선택합니다. 실행 사용자는 본인(배포자), 액세스 권한은 `모든 사용자`로 선택하고 배포합니다. Google Workspace 정책 때문에 이 옵션이 없으면 관리자 허용 또는 다른 계정에서의 배포가 필요합니다. 로그인 사용자 전용 배포는 이 명령줄 클라이언트에서 지원하지 않습니다.
8. 배포된 `/exec`로 끝나는 URL을 보관합니다. `/dev` 주소나 편집기 주소는 사용하지 않습니다.

이 구성에서 웹 앱은 배포자 권한으로 시트를 읽고 쓰며, 팀원은 URL과 참여 코드로 요청합니다. 팀원에게 시트 편집 권한을 줄 필요는 없습니다. 잘못된 코드에는 배정을 거절하고, 참여 코드는 요청 본문으로만 보냅니다. 기존 Codex와 Claude 인증은 전송하지 않습니다.

스크립트를 수정했다면 `배포 관리`에서 기존 배포의 버전을 새 버전으로 갱신하세요. 편집기에서 저장만 해서는 기존 `/exec` 코드가 갱신되지 않습니다.

## 담당자 2. 전체 데이터와 공통 실험 설정 만들기

생성용 데이터셋은 팀에서 선정합니다. ScreenSpot-v2는 `pilot_dev`로 유지합니다. 먼저 [데이터 연결 안내](dataset-adaptation.md)에 따라 원본을 다운로드하고 공통 manifest로 변환합니다. 모든 팀원은 같은 원본 revision, 주석 파일명, 변환 설정과 코드 버전을 사용해야 합니다.

설치 확인용 합성 예제는 다음과 같습니다. 실제 데이터 생성과 구독 호출은 하지 않습니다.

```bash
./team setup --backend local
./pipeline prepare --adapter mapped \
  --annotations examples/demo/annotations.json --image-root examples/demo/images \
  --mapping examples/demo/mapping.json \
  --dataset synthetic/demo --revision demo-v1 --role pilot_dev \
  --output data/demo/manifest.jsonl
./pipeline campaign --manifest data/demo/manifest.jsonl \
  --name demo-v1 --seed 42 --batch-size 30 \
  --providers codex claude --output data/demo/campaign.json
```

`campaign.json`은 작업 번호와 입력 ID를 담은 공통 목록입니다. 원본 이미지, 컴퓨터 경로, 참여 코드를 포함하지 않습니다. 같은 화면 그룹은 나누지 않으므로 한 묶음의 입력 수가 `--batch-size`보다 커질 수 있습니다. 묶음마다 교사별 작업을 생성합니다. 교사 하나만 수집하면 `--providers codex` 또는 `--providers claude`를 사용합니다. 시드는 전체 목록을 나누는 공통 설정이며 팀원마다 바꾸지 않습니다.

실제 데이터에는 예제의 manifest와 실험 이름 및 출력 경로를 바꾸세요. 공통 campaign 파일은 저장소나 별도 파일로 팀원에게 전달할 수 있습니다. 데이터 원본은 각자 다운로드하거나 같은 전체 데이터 묶음을 받습니다. 담당자별 입력 ZIP을 만들 필요는 없습니다. 이 버전은 임의 데이터셋의 다운로드 방법을 자동 추정하지 않으며, 기존 변환기를 이용해 각자의 전체 manifest를 준비해야 합니다.

## 담당자 3. 시트에 작업 목록 자동 등록

```bash
./team register --campaign data/demo/campaign.json --url '배포된_HTTPS_EXEC_URL'
```

안내가 나오면 참여 코드를 입력합니다. 화면에는 표시되지 않습니다. 자동 실행에서는 `GUI_TEAM_KEY` 환경 변수를 사용할 수 있지만 저장소나 공유 문서에 값을 저장하지 않습니다.

등록하면 시트에 모든 작업 행을 자동 생성합니다. 같은 실험을 다시 등록해도 진행 상태를 지우지 않습니다. 같은 이름에 다른 데이터나 프롬프트, 시드 등을 등록하면 거절합니다. 실험을 바꿀 때는 새 실험 이름과 campaign 파일을 사용합니다.

팀원에게 저장소와 코드 버전, 전체 데이터 준비 방법, campaign 파일, 배포 URL과 참여 코드를 전달합니다. 팀원 ID는 서로 다른 영문 이름을 사용하도록 정합니다. 같은 ID와 교사는 같은 사람의 재개로 처리합니다.

## 팀원: 문서 편집 없이 실행

아래는 합성 예제와 Codex 담당자 `member-a`의 예시입니다. 원본 데이터 준비는 앞 절의 공통 변환 명령을 그대로 사용합니다.

```bash
./team setup --backend local
# 담당자가 준 방법으로 전체 데이터를 준비한 뒤:
./team join --campaign data/demo/campaign.json \
  --manifest data/demo/manifest.jsonl \
  --url '배포된_HTTPS_EXEC_URL' --worker member-a --provider codex
./team acquire
./team doctor
./team plan
./team run --limit 1
./team run
./team status
./team submit
```

`join` 때만 참여 코드를 입력합니다. 연결 설정은 Git과 ZIP에서 제외한 `.team/`에 저장합니다. 기존 `job.json`이 있다면 `./team --config jobs/member-a.json join ...`을 사용하고 이후 명령에도 같은 `--config`를 앞에 붙입니다.

- `acquire`: 시트의 빈 작업 하나를 자동 선점하고 `job.json`과 해당 입력 목록을 만듭니다. 이미 진행 중인 작업이 있으면 같은 작업을 반환합니다. 배정은 공유 잠금 안에서 처리하여 동시 요청이 같은 행을 가져가지 않습니다.
- `run`: 시작, 실행 중 약 30초 간격, 정상 종료나 중단 때 진행 상황을 자동 기록합니다. 완료한 입력은 다시 생성하지 않습니다. 강제 종료나 전원 중단은 다음 명령 실행 시 복구합니다. 시트의 마지막 갱신 시각으로 멈춘 작업을 확인할 수 있습니다.
- `submit`: 원본 이미지를 포함한 로컬 결과 ZIP을 만들고, 완료 건수와 파일명 및 SHA-256을 자동 기록합니다. 전량 생성했으면 시트 상태가 `submitted`로 바뀝니다. 이는 ZIP 생성 완료를 뜻하며 파일 전달 완료나 사람 검수 통과를 뜻하지 않습니다. 부분 결과는 완료 처리하지 않습니다.
- 다음 작업: 전량 생성한 뒤 submit을 완료하고 `./team acquire`를 다시 실행합니다. 기존 결과는 각각의 배정별 폴더에 남습니다.
- 결과 ZIP은 프로그램이 알려주는 경로에서 기존 공유 Drive 등에 전달합니다. 업로드 자체는 자동화하지 않았습니다. 링크도 기록하려면 `./team submit --result-url 'https://drive.google.com/...'`을 실행하면 프로그램이 시트에 씁니다. 이미 submit했다면 새 ZIP이 생성되며 기존 파일을 덮어쓰지 않습니다.
- 팀원이 점수 CSV를 편집할 필요는 없습니다. 최종 사람 검수는 담당자가 병합한 뒤 진행합니다.

시트에 담당자를 적거나, 진행 건수를 수정하거나, 완료 표시를 누를 필요가 없습니다. 상태 열은 `available`, `reserved`, `running`, `paused`, `generated`, `submitted`를 사용합니다. `completed`는 생성 응답 수, `failed`는 최신 생성 실패 수, `valid`는 자동 검사를 통과한 응답 수이며 사람의 채택 수와 다릅니다.

## 중단, 연결 장애와 반납

```bash
./team run     # 같은 배정 이어서 생성
./team sync    # 진행 상태만 다시 전송, 모델 호출 없음
./team return  # 생성 결과가 전혀 없는 작업 반납
```

시트 연결이 끊겨도 이미 배정받은 작업은 로컬에서 계속 생성할 수 있습니다. 미전송 상태는 로컬에 남기고 다음 run, sync 또는 acquire에서 재전송합니다. 연결이 없는 상태에서는 새 작업을 배정받을 수 없습니다. 제출 기록이 미전송이면 다음 배정 전에 동기화가 성공해야 합니다.

결과가 일부라도 생긴 배정은 자동으로 다른 사람에게 넘기지 않습니다. 그대로 재개하거나 담당자와 상의하세요. 첫 버전에는 시간 만료에 따른 자동 회수가 없고, 작업을 시작하지 않은 경우 return으로 반납합니다. 오래 멈춘 일부 작업의 이전은 별도 협의합니다. `.team/`과 결과 폴더를 지우지 마세요. 다른 PC로 옮길 때는 기존 PC의 작업을 중단하고 담당자와 재개 방법을 정합니다.

## 담당자: 확인과 취합

담당자는 시트를 열면 누가 어떤 교사와 작업 번호를 맡았는지, 생성 건수, 실패, 마지막 갱신, ZIP 파일명을 볼 수 있습니다. 표를 직접 관리할 필요는 없습니다. 작업 셀을 수동 변경하면 배정과 로컬 상태가 달라질 수 있으므로 임의로 수정하지 않습니다.

실제 ZIP 수령 후 [기존 병합 절차](github-distribution.md#결과-취합)를 사용합니다. 같은 작업의 재제출은 사용할 최신 버전만 병합합니다. 점수표는 담당자가 작성하고, ScreenSpot-v2 파일럿은 학습에서 제외합니다.

## 연결 확인과 검증 범위

처음에는 위 합성 예제로 register, join, acquire, plan까지 확인하세요. 여기까지 모델을 호출하지 않습니다. 실제 run은 승인된 입력에서 제한 수량으로 확인합니다. 테스트는 가짜 교사와 HTTP 서비스, Apps Script용 시트 및 잠금 모형을 사용하며 실제 구독을 소비하지 않습니다. Apps Script의 실제 계정 권한과 Workspace 정책은 배포 후 별도 확인이 필요합니다.

구현 근거: [Apps Script 웹 앱](https://developers.google.com/apps-script/guides/web), [공유 잠금](https://developers.google.com/apps-script/reference/lock/lock-service), [Content Service](https://developers.google.com/apps-script/guides/content).
