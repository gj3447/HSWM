"""Send one non-sensitive trace and one durable smoke workflow.

This is an infrastructure check, not an HSWM experiment or efficacy result.
"""
from __future__ import annotations

import asyncio
from datetime import timedelta
from hashlib import sha256
import json
from pathlib import Path
import time
from uuid import uuid4

from temporalio import activity, workflow
from temporalio.common import (
    SearchAttributeKey,
    SearchAttributePair,
    TypedSearchAttributes,
)


@activity.defn(name="hswm_research_fabric_smoke_activity")
async def smoke_activity(value: dict[str, str]) -> dict[str, str]:
    return {
        "run_id": value["run_id"],
        "status": "PASS",
        "claim_boundary": "infrastructure smoke only",
    }


@workflow.defn(name="hswm_research_fabric_smoke_workflow")
class SmokeWorkflow:
    @workflow.run
    async def run(self, value: dict[str, str]) -> dict[str, str]:
        return await workflow.execute_activity(
            smoke_activity,
            value,
            start_to_close_timeout=timedelta(seconds=15),
        )


async def _temporal_smoke(run_id: str) -> dict[str, object]:
    from temporalio.client import Client
    from temporalio.worker import Worker

    client = await Client.connect("127.0.0.1:7233", namespace="hswm-dev")
    task_queue = "hswm-research-fabric-smoke"
    workflow_id = f"hswm-infra-smoke-{run_id}"
    async with Worker(
        client,
        task_queue=task_queue,
        workflows=[SmokeWorkflow],
        activities=[smoke_activity],
    ):
        result = await client.execute_workflow(
            SmokeWorkflow.run,
            {"run_id": run_id},
            id=workflow_id,
            task_queue=task_queue,
            execution_timeout=timedelta(seconds=30),
            memo={"claim_boundary": "infrastructure smoke only"},
            search_attributes=TypedSearchAttributes(
                [
                    SearchAttributePair(
                        SearchAttributeKey.for_keyword("HswmRunId"), run_id
                    ),
                    SearchAttributePair(
                        SearchAttributeKey.for_keyword("HswmSchemaVersion"),
                        "none-infrastructure-smoke",
                    ),
                    SearchAttributePair(
                        SearchAttributeKey.for_keyword("HswmOutcome"), "PASS"
                    ),
                ]
            ),
        )
    return {"workflow_id": workflow_id, "result": result}


def _phoenix_smoke(run_id: str, temporal_result: dict[str, object]) -> str:
    from phoenix.otel import register

    secret_path = (
        Path.home()
        / ".local/state/hswm-research-fabric/secrets/phoenix.json"
    )
    secrets_value = json.loads(secret_path.read_text(encoding="utf-8"))
    admin_secret = secrets_value["phoenix_admin_secret"]
    provider = register(
        endpoint="http://127.0.0.1:6006/v1/traces",
        project_name="hswm-research-fabric-smoke",
        protocol="http/protobuf",
        batch=False,
        auto_instrument=False,
        verbose=False,
        headers={"Authorization": f"Bearer {admin_secret}"},
    )
    tracer = provider.get_tracer("hswm.infrastructure.research_fabric")
    result_bytes = json.dumps(
        temporal_result, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    with tracer.start_as_current_span("hswm.infrastructure.smoke") as span:
        span.set_attribute("hswm.run.id", run_id)
        span.set_attribute("hswm.projection.kind", "infrastructure_smoke")
        span.set_attribute("hswm.claim.boundary", "infrastructure smoke only")
        span.set_attribute("hswm.temporal.workflow_id", temporal_result["workflow_id"])
        span.set_attribute("hswm.temporal.result_sha256", sha256(result_bytes).hexdigest())
    provider.force_flush(timeout_millis=10_000)
    return sha256(result_bytes).hexdigest()


async def _main() -> int:
    run_id = f"{time.time_ns()}-{uuid4().hex[:12]}"
    temporal_result = await _temporal_smoke(run_id)
    result_sha256 = _phoenix_smoke(run_id, temporal_result)
    print(
        json.dumps(
            {
                "schema": "hswm-research-fabric-smoke/v1",
                "claim_boundary": (
                    "infrastructure smoke; not HSWM cognition, learning, or efficacy"
                ),
                "run_id": run_id,
                "temporal": temporal_result,
                "phoenix_result_sha256": result_sha256,
                "status": "PASS",
            },
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
