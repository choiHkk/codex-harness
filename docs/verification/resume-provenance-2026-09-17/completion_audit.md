# 완료 판정과 실행 수명 독립 검사

검사 대상: `codex-harness`, baseline `79b82281d305c89181fbb216499d5f1e962c14ed`.

프로젝트의 `AGENTS.md`, `skills/harness/SKILL.md`, 실행 가이드와 `run.py`, `run_state.py`, `run_checks.py`, 관련 기존 테스트를 읽었다. 커스텀 역할을 직접 호출할 수 없어 기본 collaboration 에이전트로 읽기 전용 제품 검토와 별도 검사 작성만 수행했다. 제품 코드는 수정하지 않았다.

## 결론

이번 감사에서 정상 CLI 순서로 **같은 실행 안의 완료 검사**를 우회하는 결함은 확인하지 못했다. 필수 작업 상태, 필수 검사 실패, 입력 변경, 수락한 산출물 변경, 아직 활동 중인 에이전트는 기존 코드가 확인한다.

별도 실행 사이에서는 두 가지 한계를 재현했다. 둘 다 실행별 `agents.json`만 참조하는 구조에서 발생한다. 문서가 프로젝트 전체의 동시 실행 보호를 명시적으로 약속하지 않고, 네이티브 세션 식별자도 저장하지 않으므로 이번 수정의 필수 회귀 결함으로 확정하지 않는다. 부모의 주된 수정 대상인 다세대 resume의 과거 산출물 보존 결함과는 분리한다.

## 실제 실행한 후보 검사

명령:

```bash
python3 -m unittest discover -s tests -p test_completion_adversarial.py -v
```

실제 결과: **2개 실행, 2개 실패, 종료 코드 1**. 두 검사 모두 보호 장치가 실행 시작을 거부해야 한다고 가정했지만 CLI가 종료 코드 0과 `status: running`을 반환했다. 테스트는 임시 프로젝트를 만들고 공개 CLI만 호출했다. 저장된 plan이나 registry를 직접 조작하지 않았다.

| 후보 | 재현 순서 | 검사에서 기대한 동작 | 실제 관찰 |
| --- | --- | --- | --- |
| 실행 간 쓰기 소유권 | current 실행에서 shared.txt 담당을 running으로 등록 → parallel 실행에서 같은 파일 담당 시작 | 시작 거부, pending 유지 | 두 번째 시작 성공, running 기록 |
| resume 이후 슬롯 점유 | 한도 1 → current 결과 수락 → idle 관찰 기록 → 입력 변경 → resume → 새 에이전트 ID 시작 | 기존 에이전트 종료 전에는 새 ID 등록 거부 | 새 ID 시작 성공, running 기록 |

대표 실제 출력:

```json
{"run_id":"parallel","task_id":"01","agent_id":"observed-agent-02","status":"running","attempts":1}
```

```json
{"run_id":"resumed","task_id":"01","agent_id":"observed-agent-02","status":"running","attempts":1}
```

## 판단 근거와 반론

확인한 사실: `_reasons()`는 현재 실행의 등록 에이전트와 작업만 살핀다. `start_task()`의 슬롯 점유 계산도 현재 실행의 registry만 사용한다. `_write_new()`는 빈 registry를 작성한다. `resume_run()`은 이전 registry에 running 또는 stop_requested 상태가 없으면 재개를 허용하므로 idle과 stopped는 남아 있을 수 있다.

해석: 한 네이티브 세션에서 여러 실행을 사용하는 경우 로컬 장부가 실제 슬롯 점유를 충분히 표현하지 못한다. 같은 프로젝트에서 여러 실행을 동시에 진행하면 실행 사이의 파일 충돌도 검사하지 않는다.

가장 강한 반론: 별도 run이 별도 네이티브 세션일 수 있다. 프로젝트의 모든 과거 에이전트를 합산하면 이미 종료된 세션을 살아 있는 것으로 오인할 수 있다. 문서의 완료 검사 자체도 실제 네이티브 전송이나 동시 실행 성공을 증명한다고 주장하지 않는다. 따라서 단순 전역 registry 스캔을 해결책으로 제시하면 다른 정상 사용을 막을 수 있다.

이번 판단: 별도 실행 간 수명 관리 범위를 잔여 한계로 기록한다. 세션 식별자, 이전 실행의 에이전트 인계 규칙, 장부 최신성을 확인하는 계약이 먼저 정해져야 한다. 이번 감사에서는 실제 네이티브 에이전트를 만들거나 OS 수준의 동시 쓰기, 스케줄러 한도 초과를 재현하지 않았다. ID와 관찰 증거 문구는 CLI 장부 검사용 fixture이며 실제 런타임 관찰이라는 성과로 계산하지 않는다.

## 검사 코드 보존

위 두 검사는 아직 확정하지 않은 실행 간 보호 정책을 요구하므로 최종 회귀 테스트 수에 포함하지 않는다. 원래 테스트 파일은 제거하고 `cross_run_limitations.py`에 독립 실행용 검사를 보존했다. `python3 /workspace/scratch/3c97394f8dce/cross_run_limitations.py -v`로 재실행했으며, 2개 실패와 종료 코드 1을 다시 확인했다. 전체 로그는 `cross_run_limitations.log`에 있다. 아래는 최초 검사 코드다.

```python
"""Cross-run lifecycle regressions reached through the public CLI only.

The IDs below model observed native threads. These tests exercise the local
ledger and do not claim to create or inspect a real native agent session.
"""

from __future__ import annotations

import unittest

from test_run_checks import RunFixture
import test_run_state as state_tests


class CrossRunLifecycleTests(RunFixture):
    init = state_tests.RunStateTests.init
    stored = state_tests.RunStateTests.stored
    start = state_tests.RunStateTests.start
    submit = state_tests.RunStateTests.submit

    def observe(self, state: str, run_id: str = "current"):
        return self.cli(
            "run.py", "agent", "--run", run_id,
            "--agent-id", "observed-agent-01", "--state", state,
            "--evidence", "Fixture runtime observed the stated lifecycle.",
        )

    def test_other_run_cannot_dispatch_overlapping_active_writer(self) -> None:
        """A different run ID must not bypass an existing file ownership hold."""
        self.init([self.task(ownership=["shared.txt"])])
        self.start()
        self.init([self.task(ownership=["shared.txt"])], run_id="parallel")

        rejected = self.start(
            agent_id="observed-agent-02", run_id="parallel", success=False
        )
        self.assertIn("ownership", rejected.stderr.lower())
        self.assertEqual(self.stored("parallel")["tasks"][0]["status"], "pending")

    def test_resume_does_not_release_unclosed_native_slot(self) -> None:
        """Idle is reusable, but changing run IDs does not close a thread."""
        (self.project / ".codex/config.toml").write_text(
            "[agents]\nmax_concurrent_threads_per_session = 1\n", encoding="utf-8"
        )
        self.init()
        self.start()
        self.submit()
        self.observe("idle")
        self.input.write_text("Changed requirement after the first run.\n", encoding="utf-8")
        self.cli("run.py", "resume", "--run", "current", "--new-run", "resumed")

        rejected = self.start(
            agent_id="observed-agent-02", run_id="resumed", success=False
        )
        self.assertIn("capacity", rejected.stderr.lower())
        self.assertEqual(self.stored("resumed")["tasks"][0]["status"], "pending")


if __name__ == "__main__":
    unittest.main()
```
