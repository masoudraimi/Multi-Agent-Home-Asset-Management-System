"""AgentRegistry: discovers and validates agent.yaml configs at startup."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

AGENTS_ROOT = Path(__file__).parent.parent / "agents"


@dataclass
class AgentConfig:
    name: str
    model: str
    max_turns: int
    description: str
    tools: list[str]
    skills: list[str]
    can_delegate_to: list[str]
    memory: dict
    guardrails: dict
    yaml_path: Path


class AgentRegistry:
    _instance: AgentRegistry | None = None

    def __new__(cls) -> AgentRegistry:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._configs: dict[str, AgentConfig] = {}
            cls._instance._load()
        return cls._instance

    def _load(self) -> None:
        if not AGENTS_ROOT.exists():
            return
        for yaml_path in sorted(AGENTS_ROOT.glob("*/agent.yaml")):
            try:
                raw = yaml.safe_load(yaml_path.read_text())
                cfg = AgentConfig(
                    name=raw["name"],
                    model=raw.get("model", "claude-sonnet-4-6"),
                    max_turns=raw.get("max_turns", 20),
                    description=raw.get("description", ""),
                    tools=raw.get("tools", []),
                    skills=raw.get("skills", []),
                    can_delegate_to=raw.get("can_delegate_to", []),
                    memory=raw.get("memory", {}),
                    guardrails=raw.get("guardrails", {}),
                    yaml_path=yaml_path,
                )
                self._configs[cfg.name] = cfg
            except Exception as exc:
                print(f"Warning: could not load {yaml_path}: {exc}")

    def get(self, name: str) -> AgentConfig:
        if name not in self._configs:
            raise KeyError(f"Agent '{name}' not registered. Known: {list(self._configs)}")
        return self._configs[name]

    def all_names(self) -> list[str]:
        return list(self._configs.keys())

    def all_configs(self) -> list[AgentConfig]:
        return list(self._configs.values())

    @classmethod
    def reset(cls) -> None:
        cls._instance = None
