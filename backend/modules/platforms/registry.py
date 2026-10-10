"""Backend platform registry. Each platform module registers itself from its AppConfig.ready().

    from modules.platforms.registry import PlatformSpec, registry
    registry.register(PlatformSpec(key="sms", name="SMS", permission="sms.access"))
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class PlatformSpec:
    key: str
    name: str
    permission: str
    default_enabled: bool = True
    order: int = 100
    # Optional: extra data merged into GET /auth/me/ under "platform_data"[key] (e.g. Gmail's mailboxes).
    session_data: Callable[[Any], dict] | None = field(default=None, compare=False)


class PlatformRegistry:
    def __init__(self):
        self._specs: dict[str, PlatformSpec] = {}

    def register(self, spec: PlatformSpec) -> None:
        if spec.key in self._specs and self._specs[spec.key] != spec:
            raise ValueError(f"Platform '{spec.key}' is already registered.")
        self._specs[spec.key] = spec

    def unregister(self, key: str) -> None:  # tests and feature flags
        self._specs.pop(key, None)

    def get(self, key: str) -> PlatformSpec | None:
        return self._specs.get(key)

    def all(self) -> list[PlatformSpec]:
        return sorted(self._specs.values(), key=lambda spec: (spec.order, spec.key))


registry = PlatformRegistry()
