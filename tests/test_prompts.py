from anchoring_llms.items import load_items
from anchoring_llms.prompts import anchored_prompt, format_number, unanchored_prompt

ITEMS = load_items("data/items/study1_provided.csv")
ITEMS2 = load_items("data/items/study2_self_anchor.csv")


def test_item_files_load():
    assert len(ITEMS) == 15 and len(ITEMS2) == 15
    assert all(it.truth is not None for it in ITEMS + ITEMS2)
    assert all(it.reference is not None for it in ITEMS2)


def test_format_number():
    assert format_number(187888, True) == "187,888"
    assert format_number(76.70, False) == "76.7"
    assert format_number(-27.0) == "-27"


def test_unanchored_prompt_has_no_comparison():
    p = unanchored_prompt(ITEMS[0])
    assert ITEMS[0].question in p and "higher or lower" not in p and p.endswith("(not a range).")


def test_anchored_prompt_shows_the_anchor_once_in_the_question():
    item = ITEMS[-1]
    p = anchored_prompt(item, 250000.0)
    assert "higher or lower than 250,000" in p and "Comparison:" in p


def test_consider_the_opposite_names_the_anchor_only_when_it_is_given():
    item = ITEMS2[0]
    assert "first value that comes to mind" in unanchored_prompt(item, "opposite")
    assert "different from 100" in anchored_prompt(item, item.reference, "opposite")
