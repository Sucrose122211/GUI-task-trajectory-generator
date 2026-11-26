# 이 저장소에만 적용하는 공용 연결 설정

사용자가 1-2일 정도 사용하는 이번 팀 생성 저장소에 한해, 공용 팀 참여 코드와 배정 서비스 주소를 루트 `.env`에 넣고 GitHub에 커밋하도록 명시적으로 요청했습니다. 이 파일을 공유하는 것은 이번 임시 운영의 의도된 결정입니다. 다른 프로젝트의 인증 정보 관리 방식으로 일반화하지 않습니다.

팀원은 저장소를 clone/pull하면 공용 설정도 함께 받습니다. `.env` 편집, source 실행, 환경 변수 export, 참여 코드 입력이나 서비스 주소 전달이 필요하지 않습니다. 전체 데이터와 campaign을 준비한 뒤 다음 명령으로 참여합니다.

```bash
./team join --worker member-a --provider codex
./team acquire
./team doctor
./team plan
```

join의 기본 입력은 `data/screenspot-v2/manifest.jsonl`, 기본 campaign은 `data/screenspot-v2/campaign-team8.json`입니다. 팀원 ID와 교사는 각자 정한 값을 사용합니다. 데이터 준비와 프로그램 설치, 각자의 Codex 또는 Claude 구독 로그인은 [팀 실행 가이드](screenspot-team-run.md)를 따릅니다.

프로그램은 루트 `.env`의 `GUI_TEAM_KEY`, `GUI_TEAM_URL` 두 항목만 문자 그대로 읽습니다. 파일을 셸로 실행하지 않으며, 파일에서 읽은 값을 교사 프로세스의 환경 변수로 내보내지 않습니다. 주소는 `--url`, `GUI_TEAM_URL` 환경 변수, `.env` 순서로 선택하고 키는 `GUI_TEAM_KEY` 환경 변수, `.env`, 숨김 입력 순서입니다. 일반 환경에서는 제공된 파일만 사용하면 됩니다.

이 키는 배정 서비스의 공용 코드입니다. 해당 코드와 서비스 주소를 가진 사람은 이번 작업을 배정받고 진행을 기록할 수 있습니다. Google OAuth 토큰, 서비스 계정 키, Codex/Claude 로그인 파일이나 API 키를 공개하는 예외가 아닙니다. 실제 키 값을 로그나 채팅, 문서 본문에 출력할 필요도 없습니다.

공용 `.env`는 Git과 소프트웨어 release ZIP에 포함합니다. 각자의 `.team/`, `.env.local` 등 `.env.*`, CLI 인증, 원본 데이터와 생성 결과는 기존대로 Git에서 제외합니다. 데이터 및 결과 ZIP에도 공용 `.env`나 개인 연결 상태를 넣지 않습니다. 새 프로젝트에 코드를 복사할 때는 이 예외를 그대로 적용하지 않습니다.
