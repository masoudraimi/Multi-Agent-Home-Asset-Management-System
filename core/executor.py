"""WorkflowExecutor: run steps sequentially, in parallel, conditionally, with retry,
or with a human approval checkpoint."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any, Awaitable, Callable

from core.event_bus import EventBus
from core.events import (
    HumanApprovalRequested,
    WorkflowCompleted,
    WorkflowStarted,
)

Step = Callable[..., Awaitable[Any]]


class WorkflowExecutor:
    def __init__(self, agent_name: str, bus: EventBus | None = None):
        self.agent_name = agent_name
        self.bus = bus or EventBus()

    async def run_sequential(
        self,
        workflow_name: str,
        steps: list[tuple[str, Step, dict]],
    ) -> list[Any]:
        """Run steps one after another; injects prior_result kwarg into each step."""
        self.bus.publish(WorkflowStarted(self.agent_name, workflow_name, {}))
        results: list[Any] = []
        prior: Any = None
        try:
            for _step_name, fn, kwargs in steps:
                kw = {**kwargs}
                if prior is not None:
                    kw["prior_result"] = prior
                result = await fn(**kw)
                results.append(result)
                prior = result
            self.bus.publish(WorkflowCompleted(self.agent_name, workflow_name, results, True))
        except Exception as exc:
            self.bus.publish(WorkflowCompleted(self.agent_name, workflow_name, None, False))
            raise
        return results

    async def run_parallel(
        self,
        workflow_name: str,
        tasks: list[tuple[str, Step, dict]],
    ) -> list[Any]:
        """Run all tasks concurrently via asyncio.gather."""
        self.bus.publish(WorkflowStarted(self.agent_name, workflow_name, {}))
        coros = [fn(**kw) for _, fn, kw in tasks]
        results = list(await asyncio.gather(*coros, return_exceptions=True))
        self.bus.publish(WorkflowCompleted(self.agent_name, workflow_name, results, True))
        return results

    async def run_conditional(
        self,
        workflow_name: str,
        condition: Callable[[], Awaitable[bool]],
        if_true: Step,
        if_false: Step,
        kwargs_true: dict | None = None,
        kwargs_false: dict | None = None,
    ) -> Any:
        """Evaluate condition, then run the matching branch."""
        self.bus.publish(WorkflowStarted(self.agent_name, workflow_name, {}))
        branch_fn = if_true if await condition() else if_false
        branch_kw = (kwargs_true or {}) if branch_fn is if_true else (kwargs_false or {})
        result = await branch_fn(**branch_kw)
        self.bus.publish(WorkflowCompleted(self.agent_name, workflow_name, result, True))
        return result

    async def run_with_retry(
        self,
        workflow_name: str,
        fn: Step,
        kwargs: dict,
        max_retries: int = 3,
        retry_on: tuple[type, ...] = (Exception,),
    ) -> Any:
        """Retry fn up to max_retries times on specified exception types."""
        self.bus.publish(WorkflowStarted(self.agent_name, workflow_name, kwargs))
        last_exc: Exception | None = None
        for attempt in range(max_retries):
            try:
                result = await fn(**kwargs)
                self.bus.publish(WorkflowCompleted(self.agent_name, workflow_name, result, True))
                return result
            except retry_on as exc:
                last_exc = exc
        self.bus.publish(WorkflowCompleted(self.agent_name, workflow_name, None, False))
        raise RuntimeError(f"{workflow_name} failed after {max_retries} retries") from last_exc

    def request_human_approval(
        self,
        action_description: str,
        payload: dict,
    ) -> str:
        """Publish HumanApprovalRequested and return the request_id.

        The caller is responsible for NOT proceeding until the user confirms.
        The Streamlit chat_tab handles the UI and injects a synthetic follow-up message.
        """
        request_id = str(uuid.uuid4())[:8]
        self.bus.publish(HumanApprovalRequested(
            request_id=request_id,
            agent_name=self.agent_name,
            action_description=action_description,
            payload=payload,
        ))
        return request_id
