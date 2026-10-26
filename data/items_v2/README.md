# Question set v2

New questions for the pilot, made after pilot run 2 showed that Qwen3-32B already knew 13 of the
15 Study 1 questions: an anchor cannot pull an answer the model knows by heart. Question set v2
starts from many candidate questions and keeps the ones the models are unsure about.

## Files

| File | What it is | Written by |
| --- | --- | --- |
| `candidates_study1.csv` | 137 candidate questions for Study 1 (anchors given in the prompt) | by hand, checked against Wikipedia |
| `candidates_study2.csv` | 69 candidate questions for Study 2 (self-generated vs provided anchors) | by hand, checked against Wikipedia |
| `study1.csv` | The 15 Study 1 questions picked by screening | `python -m anchoring_llms.select_items` |
| `study2.csv` | The 15 Study 2 questions picked by screening | `python -m anchoring_llms.select_items` |

`study1.csv` and `study2.csv` appear once the screening has run (`notebooks/04_screen_questions.ipynb`).
They are copies of the picked rows of the candidate files, with the same columns.

Columns: `item_id, question, unit, truth, integer, domain, truth_note, source`, and for Study 2
also `reference`. `integer` marks counts, so anchors for them are whole numbers. `truth_note`
says exactly where the true value comes from; `source` is the page it was checked on.

## The candidates

**Study 1 (137 questions, `C1-001` to `C1-137`).** Less famous facts, so that a large model
should be unsure: depths and areas of lakes (Lake Garda, Vättern, Issyk-Kul), areas of islands
(Bornholm, Saaremaa, Qeshm), heights of national high points (Musala, Triglav, Alam-Kuh), lengths
of tunnels, bridges and canals, steps in towers (Cologne Cathedral, the Monument in London),
heights of waterfalls and towers, national parks, race tracks, small moons, and straight-line
distances between cities. Topics: lakes 20, islands 18, mountains 15, distances 12, tunnels and
bridges 9, steps 9, waterfalls 8, towers 7, landforms 7, canals 6, parks 6, space 6, race tracks 5,
architecture 4, biology 3, borders 2.

**Study 2 (69 questions, `C2-001` to `C2-069`).** Each has a familiar starting value `reference`
that a solver naturally adjusts from, as in Epley and Gilovich's self-generated anchors:

| Topic | Questions | Starting value | Example |
| --- | --- | --- | --- |
| orbits | 15 | 365 days | How many Earth days does the asteroid 2 Pallas take to orbit the Sun? (1,684) |
| US states | 15 | 50 states | How many states had been admitted by the attack on Fort Sumter in April 1861? (34) |
| surface gravity | 10 | 9.81 m/s² | gravity on a planet or moon |
| rotation | 8 | 24 hours | how long an asteroid or planet takes to turn once |
| boiling point | 8 | 100 °C | water boiling on a high summit (Ojos del Salado: 76.9 °C) |
| escape velocity | 7 | 11.2 km/s | escape velocity from Ganymede (2.741 km/s) |
| speed of sound | 6 | 343 m/s | speed of sound in argon at 20 °C (319 m/s) |

## How the true values were checked

Every value was checked on 2026-10-26 against English Wikipedia, mostly the article's infobox,
and the note records which number was used when the infobox and the text differ. Questions whose
sources disagreed by more than a few percent, or whose wording allowed two readings (for example
"length" of a bridge with and without approaches), were dropped before the list was saved.

26 values are calculated rather than looked up, by `scripts/compute_answers_v2.py`:
great-circle distances between city centres (haversine, Earth radius 6,371 km, coordinates from
Wikipedia), boiling points at altitude (standard atmosphere and the Antoine equation, as for the
first question set), and the speed of sound in gases at 20 °C (ideal gas).

## How the 15 + 15 questions are picked

Each candidate is asked 20 times with thinking off and 20 times with low thinking, with no
anchor, first by Qwen3-32B and then by R1-Distill-Qwen-1.5B. A question is kept when:

- every model gives a number in at least 75% of its answers;
- Qwen3-32B gives the true value (within 2%) in at most half of its answers at every level;
- Study 1: Qwen3-32B's answers vary (the 90th percentile at least 1.26 times the 10th), but not
  wildly (at most 100 times), and its median is within 10 times the truth (else the question is
  probably misread, for example in the wrong unit);
- Study 2: with thinking off, Qwen3-32B moves from the starting value towards the truth, but less
  than 80% of the way, so more thinking has room to help.

Questions that pass are ranked (Study 1: most unsure first; Study 2: least adjustment first) and
at most 3 per topic are taken. The rules and limits are in the `screening` section of
`configs/pilot_v2.yaml`; the report with every question's numbers is
`results/screen_v2/screening.md`.
