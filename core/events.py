"""Event dataclasses for the multi-agent platform."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uid() -> str:
    return str(uuid.uuid4())[:8]


@dataclass
class TaskCompleted:
    agent_name: str
    task_name: str
    result: object
    latency_ms: int
    timestamp: str = field(default_factory=_now)


@dataclass
class WorkflowStarted:
    agent_name: str
    workflow_name: str
    inputs: dict
    timestamp: str = field(default_factory=_now)


@dataclass
class WorkflowCompleted:
    agent_name: str
    workflow_name: str
    result: object
    success: bool
    timestamp: str = field(default_factory=_now)


@dataclass
class AgentEscalated:
    from_agent: str
    to_agent: str
    reason: str
    context: dict
    timestamp: str = field(default_factory=_now)


@dataclass
class HumanApprovalRequested:
    request_id: str
    agent_name: str
    action_description: str
    payload: dict
    timestamp: str = field(default_factory=_now)
