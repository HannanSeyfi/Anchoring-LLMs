# Question set v2

New questions for the pilot, made after pilot run 2 showed that Qwen3-32B already knew 13 of the
15 Study 1 questions: an anchor cannot pull an answer the model knows by heart. Question set v2
starts from many candidate questions and keeps the ones the models are unsure about.

## Files

| File | What it is | Written by |
| --- | --- | --- |
| `candidates_study1.csv` | 137 candidate questions for Study 1 (anchors given in the prompt) | by hand, checked against Wikipedia |
| `candidates_study2.csv` | 69 candidate questions for Study 2 (self-generated vs provided anchors) | by hand, checked against Wikipedia |
| `candidates_study2_neo.csv` | 54 more Study 2 questions: orbits of little-known near-Earth asteroids, added after the first screening | from Wikipedia infoboxes, checked against Kepler's third law |
| `candidates_study2_events.csv` | 39 more Study 2 questions: numbers from 2026 events (World Cup, Winter Olympics, Asian Games, Commonwealth Games) and 2025-2026 films, which happened after every model's training | from Wikipedia infoboxes and medal tables |
| `study1.csv` | The 15 Study 1 questions picked by screening | `python -m anchoring_llms.select_items` |
| `study2.csv` | The 10 Study 2 questions picked by screening | `python -m anchoring_llms.select_items` |

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

**Study 2, second batch (54 questions, `C2-101` to `C2-154`).** In the first screening Qwen3-32B
answered almost every Study 2 question correctly straight away. The exceptions were two near-Earth
asteroids: without thinking it said about 369 days for Itokawa (true 557) and 367 for Bennu (true
436.65), and with thinking it got close. So the second batch asks for the orbital periods of
little-known near-Earth asteroids, whose year a solver naturally compares with Earth's 365 days
("How many Earth days does it take the near-Earth asteroid 1685 Toro to orbit the Sun once?").
Periods within 15% of 365 days were left out, so that moving away from 365 can be measured, and
each infobox period was checked against Kepler's third law from the semi-major axis (one
asteroid, 2063 Bacchus, did not match and was dropped).

**Study 2, third batch (39 questions, `C2-201` to `C2-239`).** Questions about things that
happened after every model was trained: all the models we use were released before May 2025,
so none can know a number from late 2025 or 2026. Each question names a recent event and asks
for one of its numbers, and the starting value `reference` is the same number from the previous
edition, which the model does know and can reason from:

| Topic | Questions | Starting value | Example |
| --- | --- | --- | --- |
| 2026 World Cup | 4 | the 2022 World Cup | How many goals were scored in the whole tournament? (308; 2022: 172) |
| 2026 Winter Olympics | 10 | the 2022 Winter Olympics | How many medals in total did the host country, Italy, win? (30; 2022: 17) |
| 2026 Asian Games | 7 | the 2022 Asian Games (held in 2023) | How many gold medals did the host country, Japan, win? (83; 2022: 52) |
| 2026 Commonwealth Games | 6 | the 2022 Commonwealth Games | How many medal events were held? (215; 2022: 283) |
| film box office | 12 | the previous film in the series | Worldwide box office of Zootopia 2, in million US dollars (1,870; Zootopia: 1,026) |

Each question says when and where the event took place and ends with "This happened after your
training data ends, so you will need to estimate.", so that a model gives a number instead of
saying it cannot know. The new value differs from the previous one by at least 15%, so moving away
from the starting value can be measured. The previous edition is not named in the question: the
model has to bring it to mind itself, as in Epley and Gilovich's self-generated anchors, and in
the "provided" condition it is given as the comparison value. Values are as of 2026-10-26; one
film (Spider-Man: Brand New Day, July 2026) is still in some cinemas, so its total may still grow
a little.

## How the true values were checked

Every value was checked on 2026-10-26 against English Wikipedia, mostly the article's infobox,
and the note records which number was used when the infobox and the text differ. Questions whose
sources disagreed by more than a few percent, or whose wording allowed two readings (for example
"length" of a bridge with and without approaches), were dropped before the list was saved.

26 values are calculated rather than looked up, by `scripts/compute_answers_v2.py`:
great-circle distances between city centres (haversine, Earth radius 6,371 km, coordinates from
Wikipedia), boiling points at altitude (standard atmosphere and the Antoine equation, as for the
first question set), and the speed of sound in gases at 20 °C (ideal gas).

## How the questions are picked

Each candidate is asked 20 times with thinking off and 20 times with low thinking, with no
anchor, first by Qwen3-32B and then by R1-Distill-Qwen-1.5B. A question is kept when:

- every model gives a number in at least 75% of its answers;
- Qwen3-32B gives the true value (within 2%) in at most half of its answers at every level;
- Study 1: Qwen3-32B's answers vary (the 90th percentile at least 1.26 times the 10th), but not
  wildly (at most 100 times), and its median is within 10 times the truth (else the question is
  probably misread, for example in the wrong unit);
- Study 2: with thinking off, Qwen3-32B moves from the starting value towards the truth, but less
  than 80% of the way, so more thinking has room to help; and with low thinking its median gets
  clearly closer to the truth (by at least 0.2 in adjustment units), so thinking has something to
  work with. This last rule was added after the second screening (see `CHANGELOG.md`).

Questions that pass are ranked (Study 1: most unsure first, at most 3 per topic, 15 questions;
Study 2: the largest gain from thinking first, 10 questions). The rules and limits are in the `screening` section of
`configs/pilot_v2.yaml`; the report with every question's numbers is
`results/screen_v2/screening.md`.
