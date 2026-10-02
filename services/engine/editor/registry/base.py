"""Common machinery for the creative registries (effects, transitions, text, colour, audio, motion).

A definition declares typed, bounded parameters. `resolve()` clamps/validates user or AI supplied
values, so anything that reaches a filter string is a number from a known range or a whitelisted enum."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(frozen=True)
class Param:
    name: str
    kind: str  # "float" | "int" | "enum"
    default: Any
    min: float | None = None
    max: float | None = None
    step: float | None = None  # grid used to count/enumerate configurations
    choices: tuple[str, ...] = ()

    def clamp(self, v: Any) -> Any:
        if self.kind == "enum":
            return v if v in self.choices else self.default
        try:
            x = float(v)
        except (TypeError, ValueError):
            return self.default
        if math.isnan(x) or math.isinf(x):
            return self.default
        x = min(max(x, self.min if self.min is not None else x), self.max if self.max is not None else x)
        return int(round(x)) if self.kind == "int" else x

    def grid_size(self) -> int:
        if self.kind == "enum":
            return len(self.choices)
        if self.step and self.min is not None and self.max is not None:
            return int(round((self.max - self.min) / self.step)) + 1
        return 1

    def as_dict(self) -> dict:
        d = {"name": self.name, "type": self.kind, "default": self.default}
        if self.kind == "enum":
            d["choices"] = list(self.choices)
        else:
            d.update(min=self.min, max=self.max, step=self.step)
        return d


@dataclass(frozen=True)
class Definition:
    id: str
    name: str
    category: str
    params: tuple[Param, ...] = ()
    tags: tuple[str, ...] = ()
    description: str = ""
    performance_cost: float = 1.0  # relative render cost (1 = cheap filter)
    render: Callable[..., Any] | None = field(default=None, compare=False)

    def resolve(self, values: dict | None) -> dict:
        values = values or {}
        return {p.name: p.clamp(values.get(p.name, p.default)) for p in self.params}

    def configurations(self) -> int:
        n = 1
        for p in self.params:
            n *= max(1, p.grid_size())
        return n

    def as_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name, "category": self.category, "tags": list(self.tags),
            "description": self.description, "performance_cost": self.performance_cost,
            "parameters": [p.as_dict() for p in self.params],
            "defaults": {p.name: p.default for p in self.params},
            "constraints": {p.name: ({"choices": list(p.choices)} if p.kind == "enum" else {"min": p.min, "max": p.max}) for p in self.params},
            "configurations": self.configurations(),
            "preview": f"/library/preview/{self.category}/{self.id}",
        }


class Registry:
    def __init__(self, kind: str):
        self.kind = kind
        self._items: dict[str, Definition] = {}

    def register(self, d: Definition) -> Definition:
        if d.id in self._items:
            raise ValueError(f"duplicate {self.kind} id {d.id}")
        self._items[d.id] = d
        return d

    def get(self, id_: str) -> Definition:
        if id_ not in self._items:
            raise KeyError(f"unknown {self.kind}: {id_}")
        return self._items[id_]

    def has(self, id_: str) -> bool:
        return id_ in self._items

    def all(self) -> list[Definition]:
        return list(self._items.values())

    def total_configurations(self) -> int:
        return sum(d.configurations() for d in self._items.values())

    def search(self, q: str) -> list[Definition]:
        terms = [t for t in q.lower().replace(",", " ").split() if t not in {"a", "the", "for", "and", "of"}]
        scored = []
        for d in self._items.values():
            hay = " ".join([d.id, d.name, d.category, d.description, *d.tags]).lower()
            s = sum(2 if t in d.tags else 1 for t in terms if t in hay or t.rstrip("s") in hay)
            if s:
                scored.append((s, d))
        return [d for _, d in sorted(scored, key=lambda x: -x[0])]


def f(name, default, lo, hi, step=None) -> Param:
    return Param(name, "float", default, lo, hi, step)


def i(name, default, lo, hi, step=1) -> Param:
    return Param(name, "int", default, lo, hi, step)


def e(name, default, *choices) -> Param:
    return Param(name, "enum", default, choices=tuple(choices))


def num(x: float) -> str:
    """Format a float for FFmpeg filter strings (no exponent notation)."""
    return f"{x:.5f}".rstrip("0").rstrip(".") if isinstance(x, float) else str(x)
