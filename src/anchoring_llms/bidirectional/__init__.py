"""Bidirectional item-based anchoring study.

Does comparing two entities ("Did Argentina record more or fewer attempts at goal than France?")
pull the model's later estimate of *each* of them towards the other? The steps, in order:

    sources   -> data/bidirectional/candidate_entities.csv   (real values, with sources)
    pairs     -> candidate_pairs.csv, verified_pairs.csv, triplets.csv
    trials    -> generated_trials/*.jsonl                    (every prompt of every condition)
    run       -> runs/<phase>/<model>/<level>/part-*.jsonl.gz (raw replies)
    screen    -> screening report + frozen_dataset/            (baseline-only selection)
    analysis  -> results/bidirectional/                        (effects, figures, report)

See docs/bidirectional/README.md.
"""
