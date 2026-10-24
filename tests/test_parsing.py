import pytest

from anchoring_llms.parsing import parse_comparison, parse_estimate, parse_numbers


@pytest.mark.parametrize("reply, expected", [
    ("Estimate: 1,665", 1665),
    ("Estimate: −27", -27),
    ("**Estimate:** **12,100**", 12100),
    ("Estimate: 1 665", 1665),
    ("Estimate: 3.6 thousand", 3600),
    ("Estimate: ~187,888", 187888),
    ("Estimate: 4.6e3", 4600),
    ("Estimate: 0.5 million", 500000),
    ("I think 300 m.\nEstimate: 979 m", 979),
    ("No estimate line, but about 82 km.", 82),
    ("<think>maybe 10</think>Estimate: 20", 20),
    ("I cannot say.", None),
])
def test_parse_estimate(reply, expected):
    assert parse_estimate(reply) == expected


def test_range_is_not_a_negative_number():
    assert parse_numbers("between 25-35 km") == [25, 35]


def test_m_is_metres_unless_allowed():
    assert parse_numbers("979 m") == [979]
    assert parse_numbers("5 m", allow_m_scale=True) == [5e6]


@pytest.mark.parametrize("reply, expected", [
    ("Comparison: higher\nEstimate: 10", "higher"),
    ("**Comparison:** Lower\nEstimate: 10", "lower"),
    ("Estimate: 10", None),
])
def test_parse_comparison(reply, expected):
    assert parse_comparison(reply) == expected
