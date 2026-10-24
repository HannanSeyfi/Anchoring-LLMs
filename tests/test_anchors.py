import math

import pytest

from anchoring_llms.anchors import make_anchor, plausible_range

ESTIMATES = [1500, 1600, 1650, 1665, 1700, 1710, 1750, 1800, 1900, 2000]


def test_plausible_range_needs_five_answers():
    assert plausible_range([1, 2, 3, None]) is None
    rng = plausible_range(ESTIMATES)
    assert rng.log_scale and rng.lo < rng.median < rng.hi
    assert rng.width >= 0.15  # the floor on the width applies


def test_negative_answers_use_a_linear_scale():
    rng = plausible_range([-30, -28, -27, -25, -20, -26])
    assert not rng.log_scale


@pytest.mark.parametrize("integer", [True, False])
@pytest.mark.parametrize("direction", ["low", "high"])
def test_anchors_fall_outside_the_range(direction, integer):
    rng = plausible_range(ESTIMATES)
    values = {}
    for distance in (0.25, 1.0):
        for precision in ("round", "precise"):
            a = make_anchor(rng, direction, distance, precision, integer, key=f"k|{direction}")
            values[(distance, precision)] = a
            assert (a > rng.hi) if direction == "high" else (0 < a < rng.lo)
            if integer:
                assert a == int(a)
    further = (lambda a, b: a > b) if direction == "high" else (lambda a, b: a < b)
    # far anchors are further out than near ones; precise ones slightly further than round ones
    assert further(values[(1.0, "round")], values[(0.25, "round")])
    assert further(values[(0.25, "precise")], values[(0.25, "round")])


def test_round_and_precise_anchors_look_different():
    rng = plausible_range(ESTIMATES)
    r = make_anchor(rng, "high", 0.25, "round", True, key="x")
    p = make_anchor(rng, "high", 0.25, "precise", True, key="x")
    digits_r = str(int(r)).rstrip("0")
    assert len(digits_r) <= 2          # two significant figures
    assert int(p) % 10 != 0            # precise anchors never end in zero


def test_small_integer_anchors_stay_distinct():
    rng = plausible_range([18, 19, 20, 20, 21, 22, 23])
    for direction in ("low", "high"):
        r = make_anchor(rng, direction, 0.25, "round", True, key="s")
        p = make_anchor(rng, direction, 0.25, "precise", True, key="s")
        assert r != p and math.isfinite(p)


def test_no_zero_or_negative_anchors_for_positive_counts():
    # A weak model's answers can span orders of magnitude, starting near 1.
    rng = plausible_range([1, 1, 2, 5, 50, 200, 400, 500])
    for distance in (0.25, 1.0):
        for precision in ("round", "precise"):
            a = make_anchor(rng, "low", distance, precision, True, key="wide")
            assert a is None or 0 < a < rng.lo
