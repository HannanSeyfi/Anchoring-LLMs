"""Reading the model's replies. Raw replies are always kept; this only adds labels.

* The comparison answer (turn 1) is mapped to more / fewer / unsure (and same, yes, no).
* The estimate is the number on the last "Estimate:" line (the existing unit-aware
  `parse_estimate`, no fallback): a reply without that line is *no answer*, never zero.
* A reply is a refusal if it has no estimate and says it cannot know or answer.
* Flags: a range on the Estimate line, several numbers on it, a reply cut off at the length
  limit, a very long reply, uncertainty words, and numbers in the turn-1 answer (the model
  brought in statistics of its own: "contaminated").
"""

from __future__ import annotations

import re
from typing import Optional

from ..parsing import has_estimate_line, parse_estimate, parse_numbers, strip_think

_WORDS = {
    "more": "more", "higher": "more", "greater": "more", "larger": "more", "bigger": "more",
    "fewer": "fewer", "less": "fewer", "lower": "fewer", "smaller": "fewer",
    "unsure": "unsure", "same": "same", "yes": "yes", "no": "no",
}
_WORD_RE = re.compile(r"\b(" + "|".join(_WORDS) + r")\b", re.IGNORECASE)
_REFUSAL = re.compile(
    r"(I (?:don't|do not|cannot|can't|am unable to|am not able to) (?:have|know|provide|access|predict|give)|"
    r"knowledge cut-?off|not (?:yet )?(?:available|happened|taken place|occurred)|has(?:n't| not) (?:yet )?"
    r"(?:happened|taken place|occurred)|in the future|I'?m (?:sorry|unable)|cannot (?:be )?(?:determined|known)|"
    r"no (?:reliable |official )?(?:data|information|record))", re.IGNORECASE)
_UNCERTAIN = re.compile(r"\b(not sure|uncertain|unsure|rough(?:ly)? estimate|guess|approximately|"
                        r"I don't know|hard to say|speculat)", re.IGNORECASE)
_RANGE = re.compile(r"\d\s*(?:-|–|to)\s*\d")
_YEARS = re.compile(r"\b(?:19|20)\d\d\b")
_EST_LINE = re.compile(r"estimate\s*[:=]\s*(.+)", re.IGNORECASE)

LONG_REPLY_CHARS = 1500


def parse_comparison_word(text: str) -> Optional[str]:
    """First answer word in the reply: MORE / FEWER / UNSURE / ... -> more, fewer, unsure, ..."""
    t = strip_think(text or "").replace("**", "")
    m = _WORD_RE.search(t)
    return _WORDS[m.group(1).lower()] if m else None


def numbers_besides_years(text: str) -> list[float]:
    t = _YEARS.sub(" ", strip_think(text or ""))
    return parse_numbers(t)


def read_estimate(reply: str, finish_reason: Optional[str] = None, unit: Optional[str] = None) -> dict:
    text = strip_think(reply or "").replace("**", "")
    value = parse_estimate(text, fallback=False, unit=unit)
    lines = _EST_LINE.findall(text)
    last = lines[-1] if lines else ""
    nums_on_line = parse_numbers(_YEARS.sub(" ", last)) if last else []
    refusal = value is None and bool(_REFUSAL.search(text))
    status = "ok" if value is not None else ("refusal" if refusal else "invalid")
    if finish_reason == "length" and value is None:
        status = "cut_off"
    return dict(
        estimate=value, parse_status=status, has_estimate_line=has_estimate_line(text),
        refusal=refusal, flag_range=bool(last and _RANGE.search(last)),
        flag_multiple_numbers=len(nums_on_line) > 1, flag_cut_off=finish_reason == "length",
        flag_long=len(text) > LONG_REPLY_CHARS, flag_uncertain=bool(_UNCERTAIN.search(text)),
        flag_negative=value is not None and value < 0)


def read_turn1(reply: str, condition: str, finish_reason: Optional[str] = None) -> dict:
    word = parse_comparison_word(reply)
    nums = numbers_besides_years(reply)
    return dict(turn1_answer=word, turn1_numbers=len(nums),
                contaminated=condition in ("LT", "LA", "HT", "HA", "TRI", "C2") and len(nums) > 0,
                turn1_cut_off=finish_reason == "length")


def comparison_correct(condition: str, order: str, role: str, answer: Optional[str]) -> Optional[bool]:
    """Did the turn-1 answer match the true order? The question asks about whoever is named first."""
    if answer not in ("more", "fewer"):
        return None
    if condition in ("LT", "LA", "HT", "HA"):
        first_is_low = (condition == "LT") or (condition == "HA")
        return answer == ("fewer" if first_is_low else "more")
    if condition == "TRI":
        target_low = role in ("low_vs_mid", "mid_vs_high")  # target is the lower of the two
        first_is_low = target_low == (order == "target_first")
        return answer == ("fewer" if first_is_low else "more")
    if condition == "C4":  # the anchor is the partner's value: a low target is below it
        return answer == ("fewer" if role == "low" else "more")
    return None
