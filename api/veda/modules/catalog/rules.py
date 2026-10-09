"""Catalog rules: evaluated server-side on every configuration; unsupported combinations are refused (ADR-013 D8).

`active` is the set of reference paths a configuration selects: `room:<key>`, `product:<key>`, `product:<key>#<variant>`,
`product:<key>@<group>=<choice>`, `product:<key>#<variant>@<group>=<choice>` and `extra:<key>`. A rule's subject or object
matches when its exact path is active. Rule semantics:

- requires          subject selected → every object selected
- excludes          subject selected → no object selected
- compatible_with   subject selected → at least one object selected
- available_only_for  subject selected outside the condition → refused
- hidden_when       subject selected inside the condition → refused (and hidden in the view)
- default_when      inside the condition the subject is preselected (view only; never refuses)
- measurement_bounds  subject selected with the input measured outside [min, max] → refused
- requires_consultation  subject selected (inside the condition, if any) → refused: priced after a consultation
- unavailable_online  subject selected → refused online (staff preview may price it)
- staff_only        subject selected in a public configuration → refused, and never shown publicly

Records' own availability (property types, home sizes, project kinds, markets, effective dates) is checked as an
implicit rule for every selected record.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING

from . import kinds

if TYPE_CHECKING:  # compile imports rules
    from .compile import Catalog


@dataclass(frozen=True)
class Context:
    property_type: kinds.PropertyCode
    home_size: kinds.HomeSize
    project_kind: kinds.ProjectKind
    package: kinds.PackageCode
    market: str | None = None
    public: bool = True
    today: date | None = None


def matches(condition: kinds.Condition | None, ctx: Context) -> bool:
    if condition is None:
        return True
    checks = (
        (condition.property_types, ctx.property_type),
        (condition.home_sizes, ctx.home_size),
        (condition.project_kinds, ctx.project_kind),
        (condition.packages, ctx.package),
    )
    if any(allowed and value not in allowed for allowed, value in checks):
        return False
    if condition.markets and (ctx.market or "").strip().lower() not in {m.lower() for m in condition.markets}:
        return False
    return True


def available(a: kinds.Availability, ctx: Context) -> bool:
    today = ctx.today or date.today()
    cond = kinds.Condition(
        property_types=a.property_types, home_sizes=a.home_sizes, project_kinds=a.project_kinds, markets=a.markets
    )
    if not matches(cond, ctx):
        return False
    return not ((a.effective_from and today < a.effective_from) or (a.effective_to and today > a.effective_to))


def _message(cat: Catalog, rule: kinds.Rule, default: str) -> str:
    copy = cat.one(kinds.Copy, rule.message)
    return copy.statement if copy is not None else default


def _subject_kind_key(path: str) -> tuple[str, str]:
    kind, rest = path.split(":", 1)
    key = rest.split("#")[0].split("@")[0]
    return {"product": "product", "extra": "extra", "room": "room_template"}[kind], key


def evaluate(cat: Catalog, ctx: Context, active: set[str], measures: dict[str, dict[str, float]]) -> list[dict]:
    errors: list[dict] = []

    def refuse(path: str, code: str, message: str) -> None:
        errors.append({"field": path, "code": code, "message": message})

    # Implicit: every selected record is available in this context.
    for path in sorted(active):
        if "#" in path or "@" in path:
            continue
        kind, key = _subject_kind_key(path)
        model = cat.model(kind, key)
        if model is None:
            refuse(path, "UNAVAILABLE", "This choice is not available.")
            continue
        if isinstance(model, kinds.Described) and not available(model.availability, ctx):
            refuse(path, "UNAVAILABLE", "This choice is not available for this home.")
    for _key, rule in sorted(cat.of(kinds.Rule).items()):
        if rule.subject not in active:
            continue
        objects = set(rule.objects)
        if rule.type == "requires" and not objects <= active:
            refuse(rule.subject, "REQUIRES", _message(cat, rule, "This choice needs another choice."))
        elif rule.type == "excludes" and objects & active:
            refuse(rule.subject, "EXCLUDES", _message(cat, rule, "These choices cannot be combined."))
        elif rule.type == "compatible_with" and not objects & active:
            refuse(rule.subject, "INCOMPATIBLE", _message(cat, rule, "This choice does not fit this item."))
        elif rule.type == "available_only_for" and not matches(rule.condition, ctx):
            refuse(rule.subject, "UNAVAILABLE", _message(cat, rule, "This choice is not available for this home."))
        elif rule.type == "hidden_when" and matches(rule.condition, ctx):
            refuse(rule.subject, "UNAVAILABLE", _message(cat, rule, "This choice is not available for this home."))
        elif rule.type == "measurement_bounds":
            if rule.input is None or rule.min is None or rule.max is None:  # the schema requires all three
                refuse(rule.subject, "INVALID_RULE", "This choice cannot be checked right now.")
                continue
            value = measures.get(rule.subject.split("#")[0].split("@")[0], {}).get(rule.input)
            if value is not None and not rule.min <= value <= rule.max:
                refuse(
                    rule.subject, "OUT_OF_RANGE", _message(cat, rule, f"Enter between {rule.min:g} and {rule.max:g}.")
                )
        elif rule.type == "requires_consultation" and matches(rule.condition, ctx):
            refuse(
                rule.subject,
                "CONSULTATION_REQUIRED",
                _message(cat, rule, "This is priced after a design consultation."),
            )
        elif rule.type == "unavailable_online" and ctx.public and matches(rule.condition, ctx):
            refuse(
                rule.subject, "UNAVAILABLE_ONLINE", _message(cat, rule, "Ask us about this; it is not priced online.")
            )
        elif rule.type == "staff_only" and ctx.public:
            refuse(rule.subject, "UNAVAILABLE", "This choice is not available.")
    return errors


def defaults(cat: Catalog, ctx: Context) -> set[str]:
    """Subjects preselected in this context by default_when rules."""
    return {r.subject for r in cat.of(kinds.Rule).values() if r.type == "default_when" and matches(r.condition, ctx)}


def staff_only_subjects(cat: Catalog) -> set[str]:
    return {r.subject for r in cat.of(kinds.Rule).values() if r.type == "staff_only"}


def rules_used(cat: Catalog, active: set[str]) -> dict[str, set[str]]:
    """The rule (and message copy) records a configuration was checked against, for its snapshot."""
    out: dict[str, set[str]] = {}
    for key, rule in cat.of(kinds.Rule).items():
        if rule.subject in active:
            out.setdefault("rule", set()).add(key)
            if rule.message:
                out.setdefault("copy", set()).add(rule.message)
    return out


def contradictions(cat: Catalog) -> list[str]:
    """Rules that can never all hold: A requires B while A (or B) excludes the other, a subject that requires or
    excludes itself, or a measurement range that is empty."""
    found = []
    req: dict[str, set[str]] = {}
    exc: dict[str, set[str]] = {}
    for key, rule in sorted(cat.of(kinds.Rule).items()):
        if rule.subject in rule.objects:
            found.append(f"rule {key}: {rule.type} names its own subject")
        if rule.type == "requires":
            req.setdefault(rule.subject, set()).update(rule.objects)
        if rule.type == "excludes":
            exc.setdefault(rule.subject, set()).update(rule.objects)
    for subject, needed in req.items():
        for other in needed:
            if other in exc.get(subject, set()) or subject in exc.get(other, set()):
                found.append(f"{subject} both requires and excludes {other}")
            for third in needed:
                if third != other and third in exc.get(other, set()):
                    found.append(f"{subject} requires {other} and {third}, which exclude each other")
    return sorted(set(found))
