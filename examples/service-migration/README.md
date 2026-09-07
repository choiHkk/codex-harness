# 서비스 API 마이그레이션 시작 예제

두 도메인 역할과 오케스트레이터를 사용하는 작은 예제다. 실제 서비스 코드·테스트 결과는 포함하지 않는다. 실행 상태와 통신 기록을 사용하려면 대상 프로젝트에 기본 하네스 도구를 먼저 설치한다. 상위 저장소 루트에서 실행한다.

```bash
python3 scripts/install.py --target /absolute/path/to/service-project --dry-run
python3 scripts/install.py --target /absolute/path/to/service-project
```

1. 이 예제의 에이전트·도메인 스킬·계획 파일과 `AGENTS.md` 도메인 포인터를 대상 프로젝트에 병합한다. 기존 파일과 기본 하네스 포인터는 보존한다.
2. 실제 API 생산자, 클라이언트 소비자, 테스트 코드·실행 명령을 확인하고, `docs/profile-contract.md`에 목표 계약을 확정한다.
3. Codex에서 해당 프로젝트 루트를 열고 `$service-migration`으로 요청한다. 새 역할이 보이지 않으면 새 세션에서 역할 목록을 확인한다.

```text
$service-migration 프로필 API 응답을 { profile: {...} }로 바꿔줘.
생산자는 src/api/profile.ts, 소비자는 src/client/profile.ts야.
각 경로를 독립적으로 조사한 다음 생산자와 소비자를 순서대로 수정하고 검증해줘.
동료끼리 계약 관련 질문과 답변을 적극적으로 주고받고 중요한 소통을 _workspace에 기록해줘.
```

`plan.example.json`은 입력용 계획이며 실행 결과가 아니다. 실제 경로와 완료 기준으로 바꾸고 사용할 run ID에 맞춰 QA 산출물 경로를 조정한다. 대상 프로젝트에서 다음처럼 초기화한다.

```bash
python3 .agents/skills/harness/scripts/run.py --project . init \
  --plan-file plan.example.json --run-id service-v1
python3 .agents/skills/harness/scripts/run.py --project . ready --run service-v1
```

init이 v2 메타데이터와 입력 지문·패킷을 생성한다. 수정할 제품 파일은 ownership에만, 작업 중 변하지 않는 계약·스킬은 inputs/context에 둔다. 실제 네이티브 ID와 역할·담당 경계를 동료 목록으로 전달한다. 메시지는 기록과 실제 전송을 구분하며, 읽기 전용 mapper의 기록은 메인이 맡는다.

실제 작업·검사가 끝난 뒤 실행 완료를 검증하고 기록을 볼 수 있다.

```bash
python3 .agents/skills/harness/scripts/validate.py --project . --run service-v1 --complete
python3 .agents/skills/harness/scripts/communication.py --project . --run service-v1 view \
  --format markdown --output _workspace/communications/service-v1.md
```

이 예제만 열어서는 존재하지 않는 애플리케이션을 실행하거나 마이그레이션할 수 없다. 예제의 존재나 JSON의 상태 문자열은 실제 통과 근거가 아니다.
