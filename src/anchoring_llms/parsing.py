"""Extracting numerical estimates and comparisons from model replies."""

from __future__ import annotations

import re
from typing import Optional

_MINUS = "−–—"  # unicode minus, en dash, em dash
_NUMBER = re.compile(
    rf"(?P<sign>(?<![\w.)])[-{_MINUS}])?\s*"  # a dash after a number is a range, not a sign
    r"(?P<num>\d{1,3}(?:[,   ]\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
    r"(?:\s*(?P<exp>[eE][-+]?\d+))?"
    r"(?:\s*(?P<scale>thousand|million|billion|k\b|m\b))?",
    re.IGNORECASE,
)
_SCALES = {"thousand": 1e3, "k": 1e3, "million": 1e6, "m": 1e6, "billion": 1e9}
_ESTIMATE_LINE = re.compile(r"estimate\s*[:=]\s*(.+)", re.IGNORECASE)
_COMPARISON = re.compile(r"comparison\s*[:=]\s*\**\s*(higher|lower)", re.IGNORECASE)
_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL)


def strip_think(text: str) -> str:
    text = _THINK_BLOCK.sub("", text)
    return text.replace("<think>", "").replace("</think>", "")


def _to_number(match: re.Match, allow_m_scale: bool) -> float:
    digits = re.sub(r"[,   ]", "", match.group("num"))
    value = float(digits)
    if match.group("exp"):
        value *= 10 ** int(match.group("exp")[1:])
    scale = (match.group("scale") or "").lower()
    if scale and (scale != "m" or allow_m_scale):
        value *= _SCALES[scale]
    if match.group("sign"):
        value = -value
    return value


def parse_numbers(text: str, allow_m_scale: bool = False) -> list[float]:
    """All numbers in a text, in order. 'm' is a unit (metres) unless allowed as million."""
    return [_to_number(m, allow_m_scale) for m in _NUMBER.finditer(text)]


def parse_estimate(text: str) -> Optional[float]:
    """The number on the last 'Estimate:' line, else the last number in the reply."""
    text = strip_think(text or "").replace("**", "")
    lines = _ESTIMATE_LINE.findall(text)
    if lines:
        nums = parse_numbers(lines[-1])
        if nums:
            return nums[0]
    nums = parse_numbers(text)
    return nums[-1] if nums else None


def parse_comparison(text: str) -> Optional[str]:
    text = strip_think(text or "").replace("**", "")
    found = _COMPARISON.findall(text)
    return found[-1].lower() if found else None
