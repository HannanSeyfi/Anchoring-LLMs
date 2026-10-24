# How the model changes its answer: reading the thinking (pilot run 1)

Model: R1-Distill-Qwen-1.5B. Study 1, anchors **above** the normal zone, thinking on (low and high
levels), 1,200 answers. One person (Claude) read 40 of them, drawn at random
(`sample(n=40, random_state=7)` from those 1,200), and coded what the thinking does. This is a
first look; the planned two-coder hand coding is still needed.

## What the final answers look like (all answers, not just the 40)

Share of answers per condition (200 answers per row). "Copied" = within 10% of the anchor.
"Own zone" = inside the model's normal zone (5th to 95th percentile of its answers without an anchor).

| Thinking | Anchor | Own zone | Copied | Elsewhere | No number |
| --- | --- | ---: | ---: | ---: | ---: |
| off | near | 29% | 52% | 10% | 9% |
| off | far | 37% | 38% | 16% | 9% |
| low | near | 55% | 28% | 17% | 0% |
| low | far | 55% | 18% | 26% | 0% |
| high | near | 52% | 31% | 17% | 0% |
| high | far | 56% | 16% | 28% | 0% |

## What the thinking does (40 random traces)

| What happened | Count |
| --- | ---: |
| Recalled its own value first and kept it; the anchor was ignored (in one case considered and rejected) | 23 |
| The first value it "remembered" was the anchor, and it kept it | 8 |
| Recalled its own value, then was pushed up towards the anchor (2 all the way, 2 part way) | 4 |
| Started at the anchor and corrected part of the way back (the textbook "adjusting" pattern) | 1 |
| Other: unit mistakes, digits borrowed from the anchor | 4 |

In 31 of 40 the first value the model commits to is its final answer. When the value does change
during thinking (5 of 40), it moves towards the anchor in 4 cases and away from it in 1.

Examples (anchor in brackets):
- Kept own value: Lhasa [19,290 m]: "I think around 3,800 meters ... Lhasa is about 3,867 meters above sea level." Final 3,867.
- Anchor taken as a memory: Angel Falls [99,000 m]: "I've heard it's around 97,000 meters tall." Final 97,000.
- Own value, then pushed to the anchor: London Underground [417,916]: counts about 40 stations, then "Looking it up, the London Underground has around 417,916 stations." Final 417,916.
- Own value, then pushed up: Angel Falls [100,700 m]: "around 1,079 meters. Wait, that seems too short ... about 1,079 kilometers." Final 1,079,000.
- Adjusting: Malta [170,000,000 km²]: "I think Malta's land area is around 170 million ... that doesn't make sense because it's a small island ... around 500,000." Final 500,000.
- Borrowed digits: Malta [173,200,000 km²]: "I think it's something like 173,000 square kilometers." Final 173,000.

## What this means

- The anchor acts at the moment the model first recalls a value: it either produces its own memory
  or the anchor in place of a memory. Step-by-step adjustment away from the anchor is rare (1 of 40).
- So the median result in the summary (far anchors stop near the edge of the normal zone) should not
  be read as support for insufficient adjustment. It follows from the mix: far anchors are copied
  less often (16 to 18% vs 28 to 31%), so the median sits lower.
- Thinking reduces copying (52% to about 30% for near anchors) mainly because the model usually
  tries to recall its own value first, and once it has one it tends to keep it.
- Several copies come with invented confirmation ("I think I've heard that number before",
  "Looking it up ..."). That resembles the hypothesis-testing step of selective accessibility, except
  that the model adopts the anchor itself instead of moving part of the way.
- This is one small model that is often confused (for example, Liechtenstein "a small island in
  Switzerland"). The 8B models may behave differently.
