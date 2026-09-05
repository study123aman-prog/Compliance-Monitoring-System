"""
guardrails.py — the Deterministic First Pass (detection stage 2).

Before any expensive or nuanced evaluation runs, every normalised event is put
through a bank of fast, zero-latency, fully deterministic checks. These are the
"bright-line" rules of compliance — things that are true or false with no
judgement required:

    * a counterparty on the OFAC sanctions list         (membership test)
    * cash deposits all structured just under $10,000    (threshold test)
    * client comms on a personal WhatsApp                 (enum test)
    * "guaranteed returns" language in marketing          (regex test)
    * an instrument on the restricted list in an earnings window

Why a separate first pass? Three reasons, all straight from the build brief:
  1. Latency / cost — bright-line rules are microseconds and need no model call,
     so they run first and cheaply.
  2. Hard stops — some hits (a sanctions match) are violations on their own and
     must never be "reasoned away" by a downstream evaluator.
  3. Explainability — a deterministic hit is trivially auditable: here is the
     rule, here is the field, here is the value that tripped it.

Mechanics
---------
Each deterministic indicator declared on a signal names a generic `check`
(regex / threshold / set-membership / …) plus its parameters. The engine runs
the *real* predicate against the normalised event's features and, if it fires,
counts the indicator's risk `points` and records a fully-traced `GuardrailHit`.
The catalog of checks below is a small, general rule engine — the indicators are
data, the predicates are code.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable

from .normalization import NormalizedEvent

# --------------------------------------------------------------------------- #
#  Small reference lists (in production these are live sanctions/restricted
#  feeds; here they are tiny fixed demo sets so the checks are runnable offline).
# --------------------------------------------------------------------------- #
OFAC_SANCTIONS_DEMO: frozenset[str] = frozenset({
    "garnet trading fzco", "meridian shell holdings", "blacklisted-entity-ltd",
    "orion petro dmcc", "sanctioned-counterparty",
})
RESTRICTED_WATCHLIST: frozenset[str] = frozenset({
    "acme", "nortech", "helios-pharma", "restricted-ticker",
})
PERSONAL_CHANNELS: frozenset[str] = frozenset({
    "personal_whatsapp", "personal_sms", "personal_email", "signal_app",
    "wechat_personal", "personal_device",
})


# --------------------------------------------------------------------------- #
#  The check catalog — generic, reusable deterministic predicates.
#  Each takes (features, params) and returns True if the rule fires.
# --------------------------------------------------------------------------- #
def _num(x: Any) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return float("nan")


def _c_equals(f: dict, p: dict) -> bool:
    return f.get(p["field"]) == p["value"]


def _c_is_true(f: dict, p: dict) -> bool:
    return bool(f.get(p["field"])) is True


def _c_gt(f: dict, p: dict) -> bool:
    return _num(f.get(p["field"])) > float(p["value"])


def _c_ge(f: dict, p: dict) -> bool:
    return _num(f.get(p["field"])) >= float(p["value"])


def _c_lt(f: dict, p: dict) -> bool:
    return _num(f.get(p["field"])) < float(p["value"])


def _c_in_range(f: dict, p: dict) -> bool:
    x = _num(f.get(p["field"]))
    return float(p["low"]) <= x <= float(p["high"])


def _c_in_set(f: dict, p: dict) -> bool:
    return f.get(p["field"]) in set(p["values"])


def _c_regex(f: dict, p: dict) -> bool:
    return re.search(p["pattern"], str(f.get(p["field"], "")), re.IGNORECASE) is not None


def _c_count_ge(f: dict, p: dict) -> bool:
    seq = f.get(p["field"]) or []
    return len(seq) >= int(p["value"])


def _c_all_below(f: dict, p: dict) -> bool:
    """Every value in a list is below a threshold (classic structuring shape)."""

    seq = f.get(p["field"]) or []
    return bool(seq) and all(_num(x) < float(p["value"]) for x in seq)


def _c_channel_personal(f: dict, p: dict) -> bool:
    return str(f.get(p.get("field", "channel"), "")).lower() in PERSONAL_CHANNELS


def _c_on_sanctions_list(f: dict, p: dict) -> bool:
    return str(f.get(p.get("field", "counterparty"), "")).strip().lower() in OFAC_SANCTIONS_DEMO


def _c_on_restricted_list(f: dict, p: dict) -> bool:
    return str(f.get(p.get("field", "instrument"), "")).strip().lower() in RESTRICTED_WATCHLIST


GUARDRAIL_CHECKS: dict[str, Callable[[dict, dict], bool]] = {
    "equals": _c_equals,
    "is_true": _c_is_true,
    "gt": _c_gt,
    "ge": _c_ge,
    "lt": _c_lt,
    "in_range": _c_in_range,
    "in_set": _c_in_set,
    "regex": _c_regex,
    "count_ge": _c_count_ge,
    "all_below": _c_all_below,
    "channel_is_personal": _c_channel_personal,
    "on_sanctions_list": _c_on_sanctions_list,
    "on_restricted_list": _c_on_restricted_list,
}


@dataclass
class GuardrailHit:
    """One deterministic rule that fired, fully traced for audit."""

    rule_id: str
    description: str
    points: int
    hard: bool          # True => a bright-line violation that must not be reasoned away
    check: str          # which predicate fired


@dataclass
class GuardrailResult:
    """Outcome of the deterministic first pass over one event."""

    hits: list[GuardrailHit] = field(default_factory=list)
    misses: list[str] = field(default_factory=list)  # declared det. rules that did NOT fire

    @property
    def points(self) -> int:
        return sum(h.points for h in self.hits)

    @property
    def hard(self) -> bool:
        """True if any bright-line (hard) rule fired — a standalone violation."""

        return any(h.hard for h in self.hits)

    def summary(self) -> list[str]:
        """Human-readable chain-of-thought fragments for the first pass."""

        return [
            f"[deterministic] {h.rule_id}: {h.description} (+{h.points}"
            f"{', HARD' if h.hard else ''})"
            for h in self.hits
        ]


class GuardrailEngine:
    """Runs the deterministic first pass. Pure, stateless, microsecond-cheap."""

    def first_pass(self, event: NormalizedEvent, indicators: list[dict]) -> GuardrailResult:
        """Evaluate every declared deterministic indicator against the event.

        `indicators` is the signal's full indicator list; we act only on those
        tagged ``tier == "deterministic"``. Each names a `check` from the catalog
        above and carries its parameters inline. An indicator whose predicate
        does NOT fire is recorded in `misses` (so a mis-authored scenario is
        caught rather than silently under-scoring).
        """

        result = GuardrailResult()
        for ind in indicators:
            if ind.get("tier") != "deterministic":
                continue
            check = ind.get("check")
            fn = GUARDRAIL_CHECKS.get(check)
            if fn is None:
                raise KeyError(f"unknown guardrail check '{check}' in rule '{ind.get('id')}'")
            if fn(event.features, ind):
                result.hits.append(GuardrailHit(
                    rule_id=ind["id"],
                    description=ind.get("desc", ind["id"]),
                    points=int(ind.get("points", 0)),
                    hard=bool(ind.get("hard", False)),
                    check=check,
                ))
            else:
                result.misses.append(ind["id"])
        return result
