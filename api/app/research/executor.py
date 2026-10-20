"""Research executor (FR-2.5, FR-2.6, FR-2.7). Runs a claimed run step by step.

- Per-step state, a timeout on every connector call, bounded retries with exponential backoff.
- Resumable: steps already finished are never run again, so a re-claimed run continues where it
  stopped. A step is finished once SUCCEEDED, FAILED (attempts used up or permanent error),
  SKIPPED or NOT_AVAILABLE.
- Every attempt is written to the append-only call log with its start and end, outcome, the source's
  access category at that moment, and the provenance reference the connector returned. A call
  without a provenance reference cannot count as success.
- No connector for a source = the step is SKIPPED and says so. Nothing is simulated.
"""

import logging
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from datetime import UTC, datetime
from typing import Any

from app.cases.store import PostgresCaseStore
from app.research.connectors import (
    Connector,
    ConnectorRequest,
    ConnectorResult,
    ConnectorSet,
    PermanentConnectorError,
    RetryableConnectorError,
)
from app.research.plan import Category, StepState
from app.research.run_store import PostgresRunQueue
from app.research.schemas import RunRecord, StepRecord
from app.research.store import PostgresResearchStore
from app.sources.schemas import AccessCategory, Health
from app.sources.store import PostgresSourceStore

logger = logging.getLogger("uw.research")

DONE = {
    StepState.SUCCEEDED,
    StepState.FAILED,
    StepState.SKIPPED,
    StepState.NOT_AVAILABLE,
}
USABLE = {AccessCategory.ACTUALLY_ACCESSIBLE, AccessCategory.DISCOVERY_ONLY}


class Executor:
    def __init__(
        self,
        *,
        runs: PostgresResearchStore,
        queue: PostgresRunQueue,
        sources: PostgresSourceStore,
        cases: PostgresCaseStore,
        connectors: ConnectorSet,
        timeout_seconds: float = 30.0,
        backoff_seconds: float = 1.0,
        max_backoff_seconds: float = 30.0,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._runs = runs
        self._queue = queue
        self._sources = sources
        self._cases = cases
        self._connectors = connectors
        self._timeout = timeout_seconds
        self._backoff = backoff_seconds
        self._max_backoff = max_backoff_seconds
        self._sleep = sleep

    def work_once(self) -> bool:
        """Claim and execute one queued run. False when nothing was waiting."""
        run = self._queue.claim_next()
        if run is None:
            return False
        self.execute(run)
        return True

    def execute(self, run: RunRecord) -> None:
        used: dict[str, str] = dict(run.versions.get("connectors") or {})
        # Sources that kept refusing or not answering in this pass, with the last error class. A
        # later step on the same source fails without a call (0 attempts, nothing in the call log):
        # the answer would be the same, and each refusal costs a minute of backoff.
        refused: dict[str, str] = {}
        for step in self._runs.steps_for_run(run.id):
            if step.state in DONE:
                continue
            key = str(step.source_snapshot.get("key"))
            if key in refused:
                self._queue.mark_step(step.id, "FAILED", error_class=refused[key], finished=True)
                continue
            try:
                version = self._run_step(run, step, refused)
            except Exception:  # keep the worker alive; the step is recorded as failed
                logger.exception("research.step_crashed run=%s step=%s", run.id, step.id)
                self._queue.mark_step(
                    step.id, "FAILED", error_class="internal_error", finished=True
                )
                version = None
            if version:
                used[version[0]] = version[1]
        # A discovery-only source can never verify a claim (P-06), so its failure does not fail the
        # run. The step itself stays FAILED, with its reason, and can be tried again.
        failed = any(
            s.state is StepState.FAILED and not s.discovery_only
            for s in self._runs.steps_for_run(run.id)
        )
        versions: dict[str, Any] = {**run.versions, "connectors": used}
        self._queue.finish_run(run.id, "FAILED" if failed else "COMPLETED", versions)

    def _run_step(
        self, run: RunRecord, step: StepRecord, refused: dict[str, str]
    ) -> tuple[str, str] | None:
        if step.source_id is None:
            self._queue.mark_step(step.id, "SKIPPED", reason="No source to search.", finished=True)
            return None
        source = self._sources.get(step.source_id)
        key = str(step.source_snapshot.get("key"))
        if source is None or source.access_category not in USABLE:
            self._queue.mark_step(
                step.id,
                "SKIPPED",
                reason="The source is no longer available in the registry.",
                finished=True,
            )
            return None
        connector = self._connectors.get(key)
        if connector is None:
            self._queue.mark_step(
                step.id,
                "SKIPPED",
                reason="No connector is implemented for this source, so it was not searched.",
                finished=True,
            )
            return None
        case = self._cases.get(run.case_id)
        request = ConnectorRequest(
            case_id=run.case_id,
            tenant_id=run.tenant_id,
            category=Category(step.category),
            source_key=key,
            jurisdictions=run.jurisdictions,
            legal_name=case.legal_name if case else None,
            registration_number=case.registration_number if case else None,
            industry=case.industry if case else None,
        )
        return self._attempts(run, step, connector, request, source.access_category.value, refused)

    def _attempts(
        self,
        run: RunRecord,
        step: StepRecord,
        connector: Connector,
        request: ConnectorRequest,
        access_status: str,
        refused: dict[str, str],
    ) -> tuple[str, str] | None:
        attempt = step.attempts
        while attempt < step.max_attempts:
            attempt += 1
            self._queue.mark_step(step.id, "RUNNING", attempts=attempt, started=True)
            started = datetime.now(UTC)
            outcome, error_class, result = self._call(connector, request)
            self._queue.add_call(
                tenant_id=run.tenant_id,
                case_id=run.case_id,
                run_id=run.id,
                step_id=step.id,
                source_id=step.source_id,
                source_key=request.source_key,
                connector_version=connector.version,
                attempt=attempt,
                action=connector.describe(request),
                access_status=access_status,
                started_at=started,
                ended_at=datetime.now(UTC),
                outcome=outcome,
                error_class=error_class,
                provenance_ref=result.provenance_ref if result else None,
            )
            if outcome == "SUCCESS":
                self._queue.mark_step(step.id, "SUCCEEDED", attempts=attempt, finished=True)
                self._observe_health(step, Health.HEALTHY)
                return connector.key, connector.version
            if error_class and error_class.startswith("permanent"):
                break
            if attempt < step.max_attempts:
                self._sleep(min(self._backoff * 2 ** (attempt - 1), self._max_backoff))
        self._queue.mark_step(
            step.id, "FAILED", attempts=attempt, error_class=error_class, finished=True
        )
        if error_class in ("retryable", "timeout"):
            # The source itself kept refusing or not answering. A permanent error (no unique
            # match, no name) is about the request, so it says nothing about the source.
            self._observe_health(step, Health.DEGRADED)
            refused[request.source_key] = error_class
        return connector.key, connector.version

    def _observe_health(self, step: StepRecord, health: Health) -> None:
        if step.source_id is None:
            return
        try:
            self._sources.record_health(step.source_id, health)
        except Exception:  # health is a convenience; it never fails a research step
            logger.exception("research.health_not_recorded source=%s", step.source_id)

    def _call(
        self, connector: Connector, request: ConnectorRequest
    ) -> tuple[str, str | None, ConnectorResult | None]:
        """Run one connector call under a timeout. Returns (outcome, error_class, result)."""
        timeout = float(getattr(connector, "timeout_seconds", None) or self._timeout)
        pool = ThreadPoolExecutor(max_workers=1)
        future = pool.submit(connector.execute, request)
        try:
            result = future.result(timeout=timeout)
        except FutureTimeout:
            return "TIMEOUT", "timeout", None
        except RetryableConnectorError:
            return "ERROR", "retryable", None
        except PermanentConnectorError as exc:
            return "ERROR", f"permanent:{exc.code}" if exc.code else "permanent", None
        except Exception:
            logger.exception("research.connector_crashed source=%s", request.source_key)
            return "ERROR", "permanent", None
        finally:
            pool.shutdown(wait=False, cancel_futures=True)
        if not result.provenance_ref.strip():
            return "ERROR", "no_provenance", None
        return "SUCCESS", None, result
