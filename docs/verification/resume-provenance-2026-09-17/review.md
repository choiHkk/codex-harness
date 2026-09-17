# 다세대 resume 수정 독립 최종 리뷰

판정: 검토한 수정에서 납품을 막을 회귀 문제를 발견하지 못했다. 완료된 결과를 여러 번 재사용한 뒤 입력 또는 계약이 바뀌면, 과거 실행 안의 출력 소유권을 새 실행 경로로 옮긴다. 일반 프로젝트 출력 경로와 변경 없는 결과 재사용은 유지한다. 실제 네이티브 에이전트가 소유권을 준수하는지는 이 검사로 증명하지 않는다.

## 직접 확인한 구현

구현자의 설명 대신 현재 `git diff`와 `tests/test_resume_adversarial.py`를 읽었다.

- `_resume_ancestors()`가 직전 실행부터 `previous_run_id`를 따라 전체 선행 실행을 수집한다. 실행 ID와 프로젝트 루트를 확인하며 순환을 거부한다.
- `_resumed_ownership()`이 경로를 정규화하고 심볼릭 링크가 가리키는 경로를 확인한 뒤, 선행 실행 안의 쓰기 경로를 새 실행에 대응시킨다. glob의 뒷부분과 디렉터리 표기를 유지한다.
- 변경된 작업에만 경로 변환을 적용한다. 변경 없는 결과의 재사용 로직은 유지한다.
- 관련 없는 실행을 수정하는 경로는 새 실행을 생성하기 전에 거부한다.

## 실제 실행한 검증

```bash
python3 -m unittest discover -s tests -p test_resume_adversarial.py -v
```

결과: **3개 테스트 통과, 종료 코드 0**. 입력 변경 후 두 번째 resume, 여러 차례 재사용 후 계약 변경, 디렉터리·glob·심볼릭 링크 별칭·일반 프로젝트 출력, 무관한 실행으로의 경로 변경 거부를 검사한다. 하나의 테스트가 포함한 조건을 별도 테스트 수로 부풀리지 않았다.

추가로 unittest fixture를 이용한 독립 Python 검사 하나를 실제 실행했다. 두 조건을 각각 진행했다.

1. `./`와 연속 슬래시가 들어간 과거 실행 경로, `**/report?.txt` glob. 변경 없는 resume 두 번 이후 입력을 바꿨다. glob에 맞는 `nested/report1.txt`를 새 실행에 작성하고 결과 수락 및 완료 검사를 통과했다.
2. 과거 실행의 단일 파일을 가리키는 심볼릭 링크 별칭. 동일한 재사용·변경 순서 후 새 실행의 실제 파일 경로로 소유권이 이동했음을 확인했다.

두 조건 모두 **최초 실행과 재사용 실행 두 개의 모든 파일 바이트가 재실행 전후 동일**했다. 기존 result, plan, packet도 비교에 포함했다. 변경 없는 재사용 단계에서도 완료 검사가 통과하고 소유권 표기가 유지됨을 확인했다.

독립 검사 실제 출력:

```text
runTest (__main__.AdditionalResumeReview.runTest) ... ok
VERIFIED normalized-glob : matching output created; three prior generations byte-for-byte unchanged
VERIFIED file-symlink : matching output created; three prior generations byte-for-byte unchanged
Ran 1 test in 1.583s
OK
```

추가 검사 첫 초안은 glob과 실제 파일명이 맞지 않는 약한 fixture였다. 이를 확인하고 glob과 일치하는 실제 파일 경로로 수정해 다시 실행했다. 위 결과와 판단은 수정 후 검사에 근거한다. 테스트 수는 반복 실행 횟수를 포함하지 않는다.

## 남은 범위와 반론

수정은 쓰기 소유권과 작업 패킷의 경로를 바꾼다. 에이전트가 그 경로를 무시해 과거 파일을 직접 수정하는 행위까지 OS 수준에서 막지 않는다. 이 저장소의 기존 도구는 네이티브 샌드박스나 실행 도구를 대신하지 않는 로컬 상태 관리 도구다.

`cross_run_limitations.py`의 추가 경계 검사 **2개는 여전히 실패**한다. 서로 다른 실행 사이의 쓰기 충돌과, 같은 세션에서 resume한 뒤 이전 유휴 에이전트의 슬롯 점유를 이 도구가 함께 관리하지 않는다. 이번 다세대 경로 수정과는 다른 문제이며 해결했다고 주장하지 않는다. 상세한 정상 CLI 재현, 실제 실패 로그와 세션 범위에 관한 반론은 `completion_audit.md` 및 `cross_run_limitations.log`에 남겼다.

전체 테스트 및 구조 검증의 최종 결과는 부모의 통합 검증 기록을 사용한다. 이 리뷰에서는 위에 기록한 검사만 실행했다.

## 검토 파일 지문

- `skills/harness/scripts/run_state.py`: `502b82539fedd23eff95abcddd50afb9e77fa72ec865074c85be7fd7a128074b`
- `tests/test_resume_adversarial.py`: `e68d9e2f7a527807c8b498ca4ffb779d0535a1bc94d567bc5a0de28e8963c853`
