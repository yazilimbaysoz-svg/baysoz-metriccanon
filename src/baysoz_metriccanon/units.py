"""Baysöz Labs <baysozlabs@proton.me> — UCUM-aware unit canonicalization."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Mapping

UNIT_CATALOG = frozenset({"", "1", "%", "s", "By", "bit", "V", "A", "W", "J", "Hz", "Cel", "K"})


@dataclass(frozen=True)
class UnitFactor:
    base: str
    factor: Decimal


@dataclass(frozen=True)
class UnitInfo:
    base: str
    factor: Decimal
    known: bool

    @property
    def comparable(self) -> bool:
        return self.known and self.base != ""


def normalize_unit(
    unit: str,
    aliases: Mapping[str, str],
    factors: Mapping[str, UnitFactor],
) -> UnitInfo:
    token = unit.strip()
    if token in aliases:
        token = aliases[token]
    if token in factors:
        scaled = factors[token]
        return UnitInfo(base=scaled.base, factor=scaled.factor, known=True)
    if token in UNIT_CATALOG:
        return UnitInfo(base=token, factor=Decimal(1), known=True)
    return UnitInfo(base=token, factor=Decimal(1), known=False)
