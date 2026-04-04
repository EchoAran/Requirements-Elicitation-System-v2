from __future__ import annotations

import asyncio

from temporalio.client import Client
from temporalio.worker import Worker

from ..config import CONFIG
from .skill_runtime_temporal import (
    SkillRuntimeTemporalWorkflow,
    skill_runtime_build_initial_messages,
    skill_runtime_call_llm_step,
    skill_runtime_discover_skills,
    skill_runtime_execute_tool_call,
)


async def run_worker() -> None:
    client = await Client.connect(CONFIG.TEMPORAL_SERVER_URL, namespace=CONFIG.TEMPORAL_NAMESPACE)
    workflow_worker = Worker(
        client=client,
        task_queue=CONFIG.TEMPORAL_SKILL_WORKFLOW_TASK_QUEUE,
        workflows=[SkillRuntimeTemporalWorkflow],
        activities=[],
    )
    activity_worker = Worker(
        client=client,
        task_queue=CONFIG.TEMPORAL_SKILL_ACTIVITY_TASK_QUEUE,
        workflows=[],
        activities=[
            skill_runtime_discover_skills,
            skill_runtime_build_initial_messages,
            skill_runtime_call_llm_step,
            skill_runtime_execute_tool_call,
        ],
    )
    await asyncio.gather(workflow_worker.run(), activity_worker.run())


if __name__ == "__main__":
    asyncio.run(run_worker())
