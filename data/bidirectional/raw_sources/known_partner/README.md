# Known-partner pairs: raw sources

Retrieved 2026-11-06 from the Wikidata Query Service (query.wikidata.org) through the browser
(the cloud workspace cannot reach Wikidata).

- `famous.tsv`: well-known buildings and mountains, picked by hand from items with many Wikipedia
  language editions (`sitelinks`, 45-238). `value` is the height (m) or elevation (m) used;
  `note` gives the Wikidata statement(s) and why that value was chosen when there were several.
- `obscure_wikidata.tsv`: candidate obscure items. Query: instance of mountain (Q8502) with one
  elevation statement (P2044) in metres between 400 and 7,000, or instance of skyscraper (Q11303)
  with one height statement (P2048) in metres between 40 and 700; 2-3 sitelinks (little known);
  with an English Wikipedia article; first 80 of each in the order MD5(item IRI) (a fixed,
  arbitrary order). Country (P17) and one administrative area (P131) for the prompt.
- `building_dates_wikidata.tsv`: opening date (P1619), inception (P571) and state of use (P5817)
  of the obscure buildings, used to keep only buildings that stand (a date up to 2024, not under
  construction, on hold or closed).

`python -m anchoring_llms.bidirectional.known_partner` turns these into entities and pairs.
