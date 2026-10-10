"""Token cost from config/llm_pricing.toml (official price page, dated)."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

PRICING_FILE = Path(__file__).resolve().parents[2] / "config" / "llm_pricing.toml"


@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0

    def __add__(self, other: Usage) -> Usage:
        return Usage(*(a + b for a, b in zip(self.as_tuple(), other.as_tuple(), strict=True)))

    def as_tuple(self) -> tuple[int, int, int, int]:
        return (self.input_tokens, self.output_tokens, self.cache_creation_input_tokens, self.cache_read_input_tokens)

    @property
    def total(self) -> int:
        return sum(self.as_tuple())

    @classmethod
    def from_api(cls, usage) -> Usage:
        """From an SDK `usage` object; missing cache fields count as 0."""
        return cls(*(int(getattr(usage, name, 0) or 0) for name in cls.__dataclass_fields__))


def load(path: Path = PRICING_FILE) -> dict[str, dict[str, float]]:
    """공개 가격표에, 있으면 이 머신 전용 비공개 가격표(<이름>.local.toml, git 제외)를 덧씌운다.

    @param path 공개 가격표 경로
    @returns 모델명 → 단가표
    """
    with path.open("rb") as handle:
        models = tomllib.load(handle)["models"]
    local = path.with_suffix(".local.toml")
    if local.exists():
        with local.open("rb") as handle:
            models = {**models, **tomllib.load(handle).get("models", {})}
    return models


def cost_usd(model: str, usage: Usage, prices: dict[str, dict[str, float]] | None = None) -> float:
    prices = prices if prices is not None else load()
    if model not in prices:
        raise KeyError(f"no price for {model!r} in config/llm_pricing.toml or config/llm_pricing.local.toml")
    rate = prices[model]
    return (
        usage.input_tokens * rate["input"]
        + usage.cache_creation_input_tokens * rate["cache_write_5m"]
        + usage.cache_read_input_tokens * rate["cache_read"]
        + usage.output_tokens * rate["output"]
    ) / 1_000_000


def cost_usd_or_none(model: str, usage: Usage) -> float | None:
    """가격표에 모델이 없으면 None(비용 미확인). 비공개 단가가 없는 환경에서도 오프라인 평가가 돌게 한다.

    @param model 모델명
    @param usage 토큰 사용량
    @returns USD 비용 또는 None
    """
    return cost_usd(model, usage) if model in load() else None
