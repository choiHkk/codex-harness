# 서비스 마이그레이션 예제

이 디렉토리는 애플리케이션 코드가 없는 시작용 템플릿이다. 실제 소스와 목표 계약을 확인하기 전에는 마이그레이션을 완료했다고 보고하지 않는다.

<!-- codex-harness:domain:start -->
서비스 API 응답과 소비 코드의 마이그레이션·수정·부분 재실행에는 `.agents/skills/service-migration/SKILL.md`를 읽는다.
<!-- codex-harness:domain:end -->

메인 세션이 작업 장부, 공용 계약·설정, 통합을 관리한다. 작업자는 할당된 파일만 수정하고 다른 작업자의 변경을 되돌리지 않는다. 모델과 추론 수준은 부모 설정을 상속한다.

실행 도구는 설치된 `.agents/skills/harness/references/runtime-guide.md`를 따른다. 최신 작업 패킷과 실제 동료 ID를 제공하고 발견·질문·답변·차단·인계를 적극적으로 전달한다. 중요한 소통은 `_workspace/communications/`에 기록하되 네이티브 전송과 구분한다. 읽기 전용 역할의 기록은 메인이 담당한다. 제품 수정은 migrator가 맡고 QA는 검증한다.
