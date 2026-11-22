# 역할별 사용법 스킬

저장소를 연 에이전트에게 담당자 또는 팀원 역할을 알려주면, 각자가 해야 할 일을 명령어와 결과 파일까지 단계별로 설명한다. 사용법을 묻는 것만으로 생성이나 제출을 실행하지 않는다.

## 받기

최초에는 저장소를 clone하고 그 폴더에서 에이전트를 시작한다. 기존 사용자는 진행 중인 생성이 없을 때 코드를 받는다.

```bash
git pull --ff-only
```

새 스킬이 보이지 않으면 에이전트 세션을 새로 열어 프로젝트 스킬을 다시 불러온다. 별도의 전역 설치나 호스트 패키지 설치는 필요 없다.

## 사용하기

프로젝트 채팅에서 다음처럼 입력한다.

```text
/사용법 담당자
```

입력 준비, 데이터 변환, 분담과 이미지 포장, 팀원 안내, 결과 수령과 건수 확인, 병합, 최종 검수와 export 순서를 설명한다.

```text
/사용법 팀원
```

배정 확인, 환경 준비, 데이터 압축 해제, 설정과 로그인 확인, 한 개 시험 생성, 전체 생성과 재개, 제출 ZIP 만들기와 실제 전달 순서를 설명한다.

Claude Code에는 `.claude/skills/사용법/SKILL.md`를 넣어 `/사용법` 진입점을 제공한다. Codex에는 `.agents/skills/gui-trajectory-usage/`와 AGENTS.md의 역할 라우팅을 제공한다. Codex에서 `/사용법` 메시지가 대화로 전달되면 같은 안내를 따른다. 입력창이 등록되지 않은 slash 명령으로 거절하면 다음 기본 스킬 호출을 사용한다.

```text
$gui-trajectory-usage 담당자
$gui-trajectory-usage 팀원
```

이는 셸 명령이 아니라 에이전트 채팅에 입력하는 요청이다. Codex의 스킬 선택 목록에서는 표시 이름 `사용법`을 찾을 수 있다. 역할을 빼고 요청하면 어느 역할인지 먼저 묻는다.

## 절차 원문

- [담당자 전체 절차](../.agents/skills/gui-trajectory-usage/references/coordinator.md)
- [팀원 전체 절차](../.agents/skills/gui-trajectory-usage/references/worker.md)

모르는 데이터셋, 교사, 팀원 수나 경로는 예시임을 표시한다. 이미 제공한 배정 정보가 있으면 그 값으로 명령어를 맞춰 설명한다. 실제 실행까지 맡기려면 안내 후 작업 범위와 입력을 별도로 알려준다.

## 구조와 유지보수

```text
.agents/skills/gui-trajectory-usage/
  SKILL.md
  agents/openai.yaml
  references/coordinator.md
  references/worker.md
.claude/skills/사용법/SKILL.md
```

절차는 reference 두 파일에서 관리하고, 두 에이전트의 진입점은 같은 절차를 읽는다. 스킬은 명령을 새로 구현하지 않고 기존 `team`과 `pipeline` 사용법을 설명한다.

호출 및 프로젝트 스킬 위치는 [Codex 공식 문서](https://developers.openai.com/codex/skills)와 [Claude Code 공식 문서](https://code.claude.com/docs/en/skills)를 참고했다. 설명용 스킬을 정상 등록한 것과 각 클라이언트의 채팅 입력창에서 명령을 직접 실행해 본 것은 구분한다.
