# Screening report: qwen3-32b

Frozen 2026-11-06T13:10:21Z. Only baseline answers (no comparison) were used.

Uncertainty cut points (spread = log10 of q90/q10): strong prior <= 0.299 < moderate <= 0.657 < high uncertainty.

## Entities

| dataset      | domain      | metric                 | scope       |   entities |   parsed |   refusals |   known |   spread |
|:-------------|:------------|:-----------------------|:------------|-----------:|---------:|-----------:|--------:|---------:|
| facts        | lake depths | maximum_depth          | fact        |          4 |     1.00 |       0.00 |    0.61 |     0.01 |
| facts        | mountains   | height_above_sea_level | fact        |          8 |     1.00 |       0.00 |    0.93 |     0.01 |
| facts        | towers      | height                 | fact        |          4 |     1.00 |       0.00 |    0.72 |     0.03 |
| facts        | waterfalls  | height                 | fact        |          2 |     1.00 |       0.00 |    0.73 |     0.03 |
| olympics2026 | olympics    | medals                 | games       |         18 |     1.00 |       0.00 |    0.12 |     0.17 |
| wc2022       | teams       | attempts               | group_stage |         12 |     1.00 |       0.00 |    0.05 |     0.32 |
| wc2022       | teams       | passes                 | group_stage |         12 |     1.00 |       0.00 |    0.15 |     0.29 |
| wc2026       | players     | attempts               | group_stage |         24 |     1.00 |       0.00 |    0.01 |     0.48 |
| wc2026       | players     | passes                 | group_stage |         24 |     1.00 |       0.00 |    0.00 |     1.66 |
| wc2026       | players     | saves                  | group_stage |         24 |     1.00 |       0.00 |    0.04 |     0.69 |
| wc2026       | teams       | attempts               | group_stage |         35 |     1.00 |       0.00 |    0.03 |     0.38 |
| wc2026       | teams       | attempts               | tournament  |         30 |     1.00 |       0.00 |    0.05 |     0.67 |
| wc2026       | teams       | corners                | group_stage |         27 |     1.00 |       0.00 |    0.16 |     0.18 |
| wc2026       | teams       | crosses                | group_stage |         27 |     1.00 |       0.00 |    0.01 |     0.71 |
| wc2026       | teams       | passes                 | group_stage |         25 |     1.00 |       0.00 |    0.06 |     0.34 |
| young        | prices      | price                  | fact        |          8 |     1.00 |       0.00 |  nan    |     0.18 |

Uncertainty categories:

| dataset      |   high uncertainty |   moderate |   strong prior |   strong prior (known) |
|:-------------|-------------------:|-----------:|---------------:|-----------------------:|
| facts        |                  0 |          0 |              3 |                     15 |
| olympics2026 |                  0 |          2 |             15 |                      1 |
| wc2022       |                  0 |         12 |             12 |                      0 |
| wc2026       |                 78 |         76 |             58 |                      4 |
| young        |                  0 |          3 |              5 |                      0 |

## Pairs

|                                       |   confirmatory |   excluded |   pilot |   robustness |
|:--------------------------------------|---------------:|-----------:|--------:|-------------:|
| ('facts', 'lake depths', 'fact')      |              1 |          0 |       1 |            0 |
| ('facts', 'mountains', 'fact')        |              2 |          0 |       2 |            0 |
| ('facts', 'towers', 'fact')           |              0 |          0 |       2 |            0 |
| ('facts', 'waterfalls', 'fact')       |              1 |          0 |       0 |            0 |
| ('olympics2026', 'olympics', 'games') |              6 |          0 |       9 |            0 |
| ('wc2022', 'teams', 'group_stage')    |              8 |          0 |       4 |            0 |
| ('wc2026', 'players', 'group_stage')  |             24 |          0 |      12 |            0 |
| ('wc2026', 'teams', 'group_stage')    |             60 |          5 |      15 |            0 |
| ('wc2026', 'teams', 'tournament')     |             12 |          0 |       0 |            8 |
| ('young', 'prices', 'fact')           |              0 |          0 |      16 |            0 |

## Why pairs were excluded

| exclusion_reason             |   count |
|:-----------------------------|--------:|
| low: known in N% of replies  |       4 |
| high: known in N% of replies |       1 |
