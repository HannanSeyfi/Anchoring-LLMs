# Data of the bidirectional anchoring study

Everything here is described in [docs/bidirectional/README.md](../../docs/bidirectional/README.md)
(where each file comes from, the columns, and what to run). `raw_sources/` holds the data as
downloaded; the CSVs next to it are rebuilt from it with
`python -m anchoring_llms.bidirectional.sources` and `python -m anchoring_llms.bidirectional.pairs`.
`frozen_dataset/` appears after screening and is never edited by hand.
