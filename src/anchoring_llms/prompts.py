"""Prompt templates.

All prompts are a single user message; no system prompt is used because the
DeepSeek-R1 distills are trained without one.
"""

from __future__ import annotations

from typing import Optional

from .items import Item

INSTRUCTIONS = {
    "none": "",
    "accuracy": (
        "Accuracy matters here: take as much care as you need to make your "
        "estimate as close as possible to the true value.\n\n"
    ),
    # Consider-the-opposite, adapted from Mussweiler, Strack & Pfeiffer (2000).
    "opposite_self": (
        "Before answering, consider reasons why the true value might be quite "
        "different from the first value that comes to mind.\n\n"
    ),
    "opposite_provided": (
        "Before answering, consider reasons why the true value might be quite "
        "different from {anchor} {unit}.\n\n"
    ),
}

SINGLE_FORMAT = (
    "Give your best estimate. End your reply with a final line of the form\n"
    "Estimate: <number>\n"
    "where <number> is a single number in {unit} (not a range)."
)

COMPARATIVE_FORMAT = (
    "First, is it higher or lower than {anchor} {unit}? Then give your best "
    "estimate. End your reply with these two lines:\n"
    "Comparison: <higher or lower>\n"
    "Estimate: <number>\n"
    "where <number> is a single number in {unit} (not a range)."
)


def format_number(value: float, integer: bool = False) -> str:
    """Human-readable number with thousands separators, no trailing zeros."""
    if integer or float(value).is_integer():
        return f"{int(round(value)):,}"
    text = f"{value:,.6f}".rstrip("0").rstrip(".")
    return text


def unanchored_prompt(item: Item, instruction: str = "none") -> str:
    """Baseline (Study 1) and self-generated anchor (Study 2) prompt."""
    key = "opposite_self" if instruction == "opposite" else instruction
    return (
        f"{item.question}\n\n"
        f"{INSTRUCTIONS[key]}"
        f"{SINGLE_FORMAT.format(unit=item.unit)}"
    )


def anchored_prompt(item: Item, anchor: float, instruction: str = "none",
                    anchor_text: Optional[str] = None) -> str:
    """Comparative two-step paradigm (Jacowitz & Kahneman, 1995) in one message."""
    anchor_text = anchor_text or format_number(anchor, item.integer)
    key = "opposite_provided" if instruction == "opposite" else instruction
    instr = INSTRUCTIONS[key].format(anchor=anchor_text, unit=item.unit)
    return (
        f"{item.question}\n\n"
        f"{instr}"
        f"{COMPARATIVE_FORMAT.format(anchor=anchor_text, unit=item.unit)}"
    )
