"""Prompt wording for every condition. All text the models see is written here.

No prompt in an item-based condition contains a number of the statistic being asked about: the
only numbers are years (2026, 2022) and, in the numeric-anchor condition C4, the anchor.
Every question ends with the same instruction to give one number, so answers can be compared.
"""

from __future__ import annotations

from typing import Mapping

DESIGN_VERSION = "bidir-v1"

SYSTEM_PROMPT = "You are a helpful assistant."

ESTIMATE_FORMAT = (
    "Give your best estimate as a single {kind}{unit_part}. Do not look anything up. If you are "
    "not sure, still give your best guess instead of refusing. End your reply with a final line "
    "of the form\nEstimate: <number>"
)

ONE_WORD = "Answer with one word: {options}."

# Answer words for the comparison question, by template. They are mapped to more / fewer / unsure.
# Forced choice (design bidir-v2): no UNSURE, as in Young et al.'s two-option comparison.
FORCED_OPTIONS = {
    "count": {"P1": "MORE or FEWER", "P2": "HIGHER or LOWER"},
    "fact": {"P1": "GREATER or SMALLER", "P2": "GREATER or SMALLER"},
    "price": {"P1": "MORE or LESS", "P2": "MORE or LESS"},
}
FORCED_NOTE = " If you are not sure, give your best guess."

OPTIONS = {
    "count": {"P1": "MORE, FEWER, or UNSURE", "P2": "HIGHER, LOWER, or UNSURE"},
    "fact": {"P1": "GREATER, SMALLER, or UNSURE", "P2": "GREATER, SMALLER, or UNSURE"},
    "price": {"P1": "MORE, LESS, or UNSURE", "P2": "MORE, LESS, or UNSURE"},
}
TEMPLATES = ("P1", "P2")

FACT_PLURAL = {"mountains": "mountains", "lake depths": "lakes", "towers": "towers", "waterfalls": "waterfalls",
               "buildings": "buildings"}


def _cap(s: str) -> str:
    return s[:1].upper() + s[1:]


def kind_of(e: Mapping) -> str:
    if e["dataset"] == "young":
        return "price"
    if e["dataset"] in ("facts", "kp"):
        return "fact"
    return "count"


def _year(e: Mapping) -> int:
    return int(float(e["year"]))


def scope_single(e: Mapping) -> str:
    """'across its three group-stage matches at the 2026 FIFA World Cup' and similar."""
    if e["domain"] == "teams":
        if e["scope"] == "tournament":
            return f"across all of its matches at the {_year(e)} FIFA World Cup"
        return f"across its three group-stage matches at the {_year(e)} FIFA World Cup"
    if e["domain"] == "players":
        return f"across {e['team_name']}'s three group-stage matches at the 2026 FIFA World Cup"
    if e["domain"] == "olympics":
        return "at the 2026 Winter Olympics in Milano Cortina"
    return ""


def estimate_question(e: Mapping) -> str:
    """The absolute question about one entity (the same text in every condition)."""
    if e["dataset"] in ("facts", "young", "kp"):
        return e["question"]
    if e["domain"] == "olympics":
        return (f"How many medals in total (gold, silver and bronze) did {e['entity_label']} win "
                f"{scope_single(e)}?")
    if e["domain"] == "players":
        return (f"How many {e['metric_label']} did {e['entity_name']} of {e['team_name']} record in "
                f"total {scope_single(e)}?")
    return f"How many {e['metric_label']} did {e['entity_label']} record in total {scope_single(e)}?"


def estimate_format(e: Mapping) -> str:
    if kind_of(e) == "count":
        return ESTIMATE_FORMAT.format(kind="whole number", unit_part="")
    return ESTIMATE_FORMAT.format(kind="number", unit_part=f" in {e['unit']}")


def estimate_prompt(e: Mapping) -> str:
    return f"{estimate_question(e)}\n\n{estimate_format(e)}"


def comparison_question(t: Mapping, o: Mapping, template: str) -> str:
    """Is target `t` higher or lower than other entity `o` on the same statistic? (`t` named first)."""
    a, b = t["entity_label"], o["entity_label"]
    k = kind_of(t)
    if k == "price":
        return f"Does {a} cost more or less than {b}?" if template == "P1" else \
            f"Is {a} more or less expensive than {b}?"
    if k == "fact":
        attr = t["metric_label"]
        return f"Is the {attr} of {a} greater or smaller than the {attr} of {b}?" if template == "P1" else \
            f"Is the {attr} of {a} greater or smaller than that of {b}?"
    label = t["metric_label"]
    if t["domain"] == "olympics":
        return (f"At the 2026 Winter Olympics in Milano Cortina, did {a} win more or fewer medals in "
                f"total than {b}?") if template == "P1" else \
            (f"Was the total number of medals {a} won at the 2026 Winter Olympics in Milano Cortina "
             f"higher or lower than the number {b} won?")
    if t["domain"] == "players":
        scope = "across their teams' three group-stage matches at the 2026 FIFA World Cup"
        return (f"{_cap(scope)}, did {a} record more or fewer {label} than {b}?") if template == "P1" else \
            (f"Was the number of {label} that {a} recorded {scope_single(t)} higher or lower than the "
             f"number that {b} recorded across {o['team_name']}'s three group-stage matches?")
    if t["scope"] == "tournament":
        scope = f"across all of their matches at the {_year(t)} FIFA World Cup"
    else:
        scope = f"across their three group-stage matches each at the {_year(t)} FIFA World Cup"
    return (f"{_cap(scope)}, did {a} record more or fewer {label} than {b}?") if template == "P1" else \
        f"Was {a}'s total number of {label} {scope_single(t)} higher or lower than {b}'s?"


def comparison_prompt(t: Mapping, o: Mapping, template: str, forced: bool = False) -> str:
    """Turn 1. forced=True: only the two directions may be chosen (design bidir-v2)."""
    if forced:
        return (f"{comparison_question(t, o, template)}\n\n"
                f"{ONE_WORD.format(options=FORCED_OPTIONS[kind_of(t)][template])}{FORCED_NOTE}")
    return f"{comparison_question(t, o, template)}\n\n{ONE_WORD.format(options=OPTIONS[kind_of(t)][template])}"


def neutral_turn(t: Mapping) -> str:
    """C5: a first turn of the same length that names only the target."""
    return f"Have you heard of {t['entity_label']}?\n\n{ONE_WORD.format(options='YES, NO, or UNSURE')}"


def letters_turn(first: Mapping, second: Mapping) -> str:
    """C2: an irrelevant comparison of the two names."""
    return (f'Does the name "{first["entity_name"]}" contain more or fewer letters than the name '
            f'"{second["entity_name"]}"?\n\n{ONE_WORD.format(options="MORE, FEWER, or SAME")}')


def comention_sentence(first: Mapping, second: Mapping) -> str:
    a, b = first["entity_label"], second["entity_label"]
    if first["domain"] in ("teams", "players"):
        return _cap(f"{a} and {b} both played in the group stage of the {_year(first)} FIFA World Cup.")
    if first["domain"] == "olympics":
        return _cap(f"{a} and {b} both competed at the 2026 Winter Olympics in Milano Cortina.")
    if first["dataset"] == "young":
        return _cap(f"{a} and {b} are both things you can buy in the UK.")
    return _cap(f"{a} and {b} are both {FACT_PLURAL.get(first['domain'], 'places')}.")


def comention_prompt(t: Mapping, first: Mapping, second: Mapping) -> str:
    """C1: both named, no comparison; then the estimate of `t`."""
    return f"{comention_sentence(first, second)}\n\n{estimate_prompt(t)}"


def no_commitment_prompt(t: Mapping, o: Mapping, first_is_target: bool, template: str) -> str:
    """C3: the comparison is shown but must not be answered."""
    q = comparison_question(t, o, template) if first_is_target else comparison_question(o, t, template)
    return (f'Consider the following question, but do not answer it:\n"{q}"\n\n'
            f"Instead, answer this question. {estimate_prompt(t)}")


def numeric_turn(t: Mapping, anchor_text: str, forced: bool = False) -> str:
    """C4: classic numeric comparison with the same question."""
    opts = ONE_WORD.format(options="HIGHER or LOWER") + FORCED_NOTE if forced else \
        ONE_WORD.format(options="HIGHER, LOWER, or UNSURE")
    return (f'Is the answer to the following question higher or lower than {anchor_text}?\n'
            f'"{estimate_question(t)}"\n\n{opts}')


def format_anchor(value: float) -> str:
    v = float(value)
    return f"{int(round(v)):,}" if abs(v - round(v)) < 1e-9 else f"{v:,.2f}".rstrip("0").rstrip(".")
