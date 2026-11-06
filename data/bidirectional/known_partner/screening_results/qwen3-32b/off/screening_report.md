# Screening report: qwen3-32b

Frozen 2026-11-06T15:49:56Z. Only baseline answers (no comparison) were used.

Uncertainty cut points (spread = log10 of q90/q10): strong prior <= 0.050 < moderate <= 0.150 < high uncertainty.

## Entities

| dataset   | domain    | metric                 | scope   |   entities |   parsed |   refusals |   known |   spread |
|:----------|:----------|:-----------------------|:--------|-----------:|---------:|-----------:|--------:|---------:|
| kp        | buildings | height                 | fact    |         38 |     1.00 |       0.00 |    0.26 |     0.16 |
| kp        | mountains | height_above_sea_level | fact    |         44 |     1.00 |       0.00 |    0.39 |     0.08 |

Uncertainty categories:

| dataset   |   high uncertainty |   moderate |   strong prior |   strong prior (known) |
|:----------|-------------------:|-----------:|---------------:|-----------------------:|
| kp        |                 37 |         16 |              6 |                     23 |

## Pairs

|                             |   excluded |   pilot |
|:----------------------------|-----------:|--------:|
| ('kp', 'buildings', 'fact') |          0 |      28 |
| ('kp', 'mountains', 'fact') |          2 |      26 |

## Why pairs were excluded

| exclusion_reason                         |   count |
|:-----------------------------------------|--------:|
| low (famous): baseline median off by -N% |       2 |
