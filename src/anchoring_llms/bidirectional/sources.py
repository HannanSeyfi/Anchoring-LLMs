"""Turn the downloaded source files into one table of entities with true values.

Every row of `candidate_entities.csv` is one quantity a model will be asked to estimate, e.g.
"attempts at goal by Argentina across its three group-stage matches at the 2026 World Cup".

Sources (all downloaded through a browser on 2026-11-06, files in data/bidirectional/raw_sources/):

* FIFA World Cup 2026 and 2022: FIFA's own match-data service, which feeds the statistics pages
  of fifa.com. One file per match per team (`fdh-api.fifa.com/v1/stats/match/<id>/teams.json`),
  one per match per player, plus FIFA's tournament totals (`/v1/stats/season/<id>/teams.json`),
  used here only to check our sums.
* Milano Cortina 2026 Winter Olympics medal table: olympics.com refuses automated browsers
  (HTTP 403), so the English Wikipedia medal table is used (revision 1376824706, checked:
  gold + silver + bronze = total for every row, column sums 116/118/115/349 as printed).
* Familiar facts: questions of data/items_v2/candidates_study1.csv, whose true values were checked
  on Wikipedia on 2026-10-26, and which Qwen3-32B answered within 2% at least half the time
  in the October screening (strong prior knowledge).
* Young et al. (2026) Experiment 1 products: their pre-registration (OSF 2a9nz) lists the eight
  products with the mean price given by a human pilot sample. These have no true value; they are
  used only for the human-paradigm replication, where the measure is relative to the model's own
  unanchored answers.

    python -m anchoring_llms.bidirectional.sources        # rewrites candidate_entities.csv
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd

ROOT = Path("data/bidirectional")
RAW = ROOT / "raw_sources"
RETRIEVED = "2026-11-06T08:10:00Z"

FIFA_PAGE_2026 = "https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026/statistics"
FIFA_PAGE_2022 = "https://www.fifa.com/en/tournaments/mens/worldcup/qatar2022"
FIFA_MATCH_TEAMS = "https://fdh-api.fifa.com/v1/stats/match/{id_ifes}/teams.json"
FIFA_MATCH_PLAYERS = "https://fdh-api.fifa.com/v1/stats/match/{id_ifes}/players.json"
FIFA_SEASON_TEAMS = "https://fdh-api.fifa.com/v1/stats/season/{season}/teams.json"
FIFA_CALENDAR = "https://api.fifa.com/api/v3/calendar/matches?idCompetition=17&idSeason={season}"
WIKI_OLYMPICS = "https://en.wikipedia.org/w/index.php?title=2026_Winter_Olympics_medal_table&oldid=1376824706"
OSF_YOUNG = "https://osf.io/2a9nz/ (anchoringTheAnchor_preReg.docx, Table A1)"

# Training cutoffs: Qwen3 was released in April 2025 and Llama 3.x has a documented cutoff of
# December 2023, so both World Cup 2026 (11 June - 19 July 2026) and the Winter Olympics
# (6-22 February 2026) happened after every model we use. WC 2022 happened before all of them.
AFTER_CUTOFF = {"wc2026": True, "olympics2026": True, "wc2022": False, "facts": False, "young": False}

# Former World Cup winners: a documented, model-independent "famous team" marker.
FORMER_CHAMPIONS = {"BRA", "GER", "ITA", "ARG", "FRA", "URU", "ENG", "ESP"}

# Team metrics, group stage (every team played exactly 3 matches, so exposure is equal).
TEAM_METRICS = {
    "attempts": ("AttemptAtGoal", "attempts at goal",
                 "All attempts at goal (on target, off target and blocked), FIFA definition."),
    "passes": ("Passes", "passes", "All passes attempted (completed or not), FIFA definition."),
    "corners": ("Corners", "corner kicks", "Corner kicks taken, FIFA definition."),
    "crosses": ("Crosses", "crosses", "Crosses attempted (completed or not), FIFA definition."),
}
# Player metrics, group stage, by position (no goalkeeper-vs-striker comparisons).
PLAYER_METRICS = {
    "attempts": ("AttemptAtGoal", "attempts at goal", ["Forward"], 200, 6),
    "passes": ("Passes", "passes", ["Midfielder", "Defender"], 250, 60),
    "saves": ("GoalkeeperSaves", "saves", ["Goalkeeper"], 270, 5),
}

# Familiar facts (strong priors). Entity names and comparison attribute written by hand; the
# question text and true value are taken unchanged from the checked candidates file.
FACT_ENTITIES = {
    "C1-051": ("Kékes", "the highest mountain in Hungary", "mountains"),
    "C1-042": ("Galdhøpiggen", "the highest mountain in Norway", "mountains"),
    "C1-043": ("Hvannadalshnúkur", "the highest peak in Iceland", "mountains"),
    "C1-044": ("Mount Kazbek", "in the Caucasus", "mountains"),
    "C1-041": ("Triglav", "the highest mountain in Slovenia", "mountains"),
    "C1-046": ("Mount Elgon", "on the Uganda-Kenya border", "mountains"),
    "C1-040": ("Moldoveanu Peak", "the highest mountain in Romania", "mountains"),
    "C1-047": ("Mount Cameroon", "in Cameroon", "mountains"),
    "C1-023": ("Lake Constance", "in Central Europe", "lake depths"),
    "C1-026": ("Lake Matano", "in Indonesia", "lake depths"),
    "C1-021": ("Lake Garda", "in Italy", "lake depths"),
    "C1-027": ("Lake Issyk-Kul", "in Kyrgyzstan", "lake depths"),
    "C1-086": ("the Atomium", "in Brussels", "towers"),
    "C1-088": ("the Žižkov Television Tower", "in Prague", "towers"),
    "C1-090": ("the Macau Tower", "in Macau", "towers"),
    "C1-085": ("the Ostankino Tower", "in Moscow", "towers"),
    "C1-083": ("the Rhine Falls", "in Switzerland", "waterfalls"),
    "C1-082": ("Skógafoss", "in Iceland", "waterfalls"),
}
FACT_ATTRIBUTE = {"mountains": "height above sea level", "lake depths": "maximum depth",
                  "towers": "height", "waterfalls": "height"}

# Young et al. (2026) Experiment 1 products and the human pilot's mean price (GBP), Table A1 of
# the OSF pre-registration. These are NOT true prices; they only fix which item is "low" or "high".
YOUNG_ITEMS = [
    ("stapler", "a Rapesco stapler", 6.56, "low"),
    ("torch", "a handheld flashlight torch", 15.11, "low"),
    ("calculator", "a Sharp calculator", 18.64, "low"),
    ("vodka", "a one-litre bottle of Zubrowka vodka", 22.22, "low"),
    ("rent", "one month's rent in London (per person)", 825.0, "high"),
    ("laptop", "an Apple laptop", 1038.89, "high"),
    ("moped", "a moped", 1240.0, "high"),
    ("car", "a second-hand car", 3155.0, "high"),
]

COLUMNS = ["entity_id", "dataset", "domain", "competition", "year", "event_end_date", "after_cutoff",
           "entity_type", "entity_name", "entity_label", "entity_code", "team_code", "team_name",
           "position", "famous", "metric", "metric_label", "metric_definition", "scope", "unit",
           "value", "integer", "matches_played", "minutes_played", "question", "source_name",
           "source_url", "source_endpoint", "retrieved_utc", "verification", "notes"]


def nice_name(name: str) -> str:
    """'Juan MUSSO' -> 'Juan Musso' (FIFA writes family names in capitals)."""
    if not isinstance(name, str):
        return ""
    return " ".join(w.title() if w.isupper() and len(w) > 1 else w for w in name.split())


def _first_stage(stage: pd.Series) -> pd.Series:
    return stage.str.lower().str.startswith("first stage")


def wc_team_entities(year: int) -> pd.DataFrame:
    dataset = f"wc{year}"
    m = pd.read_csv(RAW / f"fifa_wc{year}" / "team_match_stats.csv", dtype={"id_ifes": str})
    g = m[_first_stage(m["stage"])]
    totals = None
    if (RAW / f"fifa_wc{year}" / "team_tournament_totals.csv").exists():
        totals = pd.read_csv(RAW / f"fifa_wc{year}" / "team_tournament_totals.csv").set_index("team_code")
    all_sums = m.groupby("team_code").sum(numeric_only=True)
    rows = []
    for code, t in g.groupby("team_code"):
        name = t["team_name"].iloc[0]
        for metric, (col, label, definition) in TEAM_METRICS.items():
            if t[col].isna().any():
                continue  # a match file without this statistic: mark missing, do not guess
            check = "sum of FIFA per-match files"
            if totals is not None and code in totals.index:
                diff = all_sums.loc[code, col] - totals.loc[code, col]
                check += ("; all-match sum equals FIFA tournament total" if diff == 0 else
                          f"; all-match sum differs from FIFA tournament total by {diff:g}")
            rows.append(dict(
                entity_id=f"{dataset}-team-{code}-{metric}-group", dataset=dataset, domain="teams",
                competition="FIFA World Cup", year=year,
                event_end_date="2026-07-19" if year == 2026 else "2022-12-18",
                after_cutoff=AFTER_CUTOFF[dataset], entity_type="team", entity_name=name,
                entity_label=name, entity_code=code, team_code=code, team_name=name, position="",
                famous=code in FORMER_CHAMPIONS, metric=metric, metric_label=label,
                metric_definition=definition, scope="group_stage", unit=label, value=float(t[col].sum()),
                integer=True, matches_played=int(len(t)), minutes_played=round(float(t["TimePlayed"].sum()), 1)
                if t["TimePlayed"].notna().all() else None, question="",
                source_name="FIFA match data (fdh-api.fifa.com)",
                source_url=FIFA_PAGE_2026 if year == 2026 else FIFA_PAGE_2022,
                source_endpoint=";".join(FIFA_MATCH_TEAMS.format(id_ifes=i) for i in t["id_ifes"]),
                retrieved_utc=RETRIEVED, verification=check, notes=""))
        if year == 2026 and totals is not None and code in totals.index:  # robustness: whole tournament
            col, label, definition = TEAM_METRICS["attempts"]
            mp = int(totals.loc[code, "MatchesPlayed"])
            rows.append(dict(
                entity_id=f"{dataset}-team-{code}-attempts-tournament", dataset=dataset, domain="teams",
                competition="FIFA World Cup", year=year, event_end_date="2026-07-19", after_cutoff=True,
                entity_type="team", entity_name=name, entity_label=name, entity_code=code, team_code=code,
                team_name=name, position="", famous=code in FORMER_CHAMPIONS, metric="attempts",
                metric_label=label, metric_definition=definition, scope="tournament", unit=label,
                value=float(totals.loc[code, col]), integer=True, matches_played=mp,
                minutes_played=round(float(totals.loc[code, "TimePlayed"]), 1), question="",
                source_name="FIFA tournament totals (fdh-api.fifa.com)", source_url=FIFA_PAGE_2026,
                source_endpoint=FIFA_SEASON_TEAMS.format(season=285023), retrieved_utc=RETRIEVED,
                verification="FIFA tournament total; equals the sum of FIFA per-match files",
                notes=f"Played {mp} matches: totals depend on how far the team went."))
    return pd.DataFrame(rows)


def wc2026_player_entities() -> pd.DataFrame:
    p = pd.read_csv(RAW / "fifa_wc2026" / "player_group_stage_totals.csv", dtype={"player_id": str})
    season = pd.read_csv(RAW / "fifa_wc2026" / "player_tournament_totals.csv",
                         dtype={"player_id": str}).set_index("player_id")
    teams = pd.read_csv(RAW / "fifa_wc2026" / "team_match_stats.csv").drop_duplicates("team_code")
    team_name = dict(zip(teams["team_code"], teams["team_name"]))
    rows = []
    for metric, (col, label, positions, min_minutes, min_value) in PLAYER_METRICS.items():
        ok = p[p["position"].isin(positions) & (p["TimePlayed"] >= min_minutes) & (p[col] >= min_value)
               & p["player_name"].notna() & (p["n_match_files"] == 3)]
        for _, r in ok.iterrows():
            name = nice_name(r["player_name"])
            code = r["team_code"]
            check = "sum of FIFA per-match files (3 group matches)"
            if r["player_id"] in season.index and season.loc[r["player_id"], "MatchesPlayed"] == 3:
                same = season.loc[r["player_id"], col] == r[col]
                check += "; equals FIFA tournament total" if same else "; DIFFERS from FIFA tournament total"
            rows.append(dict(
                entity_id=f"wc2026-player-{r['player_id']}-{metric}-group", dataset="wc2026",
                domain="players", competition="FIFA World Cup", year=2026, event_end_date="2026-07-19",
                after_cutoff=True, entity_type="player", entity_name=name,
                entity_label=f"{name} ({team_name.get(code, code)})", entity_code=r["player_id"],
                team_code=code, team_name=team_name.get(code, code), position=r["position"],
                famous="", metric=metric, metric_label=label,
                metric_definition=TEAM_METRICS.get(metric, (None, None, "Goalkeeper saves, FIFA definition."))[2],
                scope="group_stage", unit=label, value=float(r[col]), integer=True, matches_played=3,
                minutes_played=round(float(r["TimePlayed"]), 1), question="",
                source_name="FIFA match data (fdh-api.fifa.com)", source_url=FIFA_PAGE_2026,
                source_endpoint=FIFA_MATCH_PLAYERS.format(id_ifes="<each group match>"),
                retrieved_utc=RETRIEVED, verification=check, notes=""))
    return pd.DataFrame(rows)


def olympics_entities(min_total: int = 3) -> pd.DataFrame:
    t = pd.read_csv(RAW / "olympics_2026" / "medal_table_wikipedia.csv")
    t = t[(t["total"] >= min_total) & (t["noc"] != "Individual Neutral Athletes")]
    rows = []
    for _, r in t.iterrows():
        code = re.sub(r"\W", "", r["noc"]).upper()[:12]
        rows.append(dict(
            entity_id=f"olympics2026-noc-{code}-medals", dataset="olympics2026", domain="olympics",
            competition="Winter Olympics", year=2026, event_end_date="2026-02-22", after_cutoff=True,
            entity_type="country", entity_name=r["noc"],
            entity_label=("the " if r["noc"] in ("United States", "Netherlands", "Czech Republic") else "")
            + r["noc"], entity_code=code, team_code="", team_name="", position="", famous="",
            metric="medals", metric_label="medals", metric_definition="Total medals (gold + silver + bronze), final table.",
            scope="games", unit="medals", value=float(r["total"]), integer=True, matches_played=None,
            minutes_played=None, question="", source_name="Wikipedia medal table (secondary; olympics.com blocked)",
            source_url=WIKI_OLYMPICS, source_endpoint=WIKI_OLYMPICS, retrieved_utc=RETRIEVED,
            verification="rows sum to totals; column totals match the table's own totals row",
            notes="Secondary source: check against olympics.com before publication."))
    return pd.DataFrame(rows)


def fact_entities() -> pd.DataFrame:
    c = pd.read_csv("data/items_v2/candidates_study1.csv").set_index("item_id")
    rows = []
    for item_id, (name, where, domain) in FACT_ENTITIES.items():
        r = c.loc[item_id]
        rows.append(dict(
            entity_id=f"facts-{item_id}", dataset="facts", domain=domain, competition="", year="",
            event_end_date="", after_cutoff=False, entity_type="place", entity_name=name,
            entity_label=f"{name} ({where})", entity_code=item_id, team_code="", team_name="",
            position="", famous="", metric=FACT_ATTRIBUTE[domain].replace(" ", "_"),
            metric_label=FACT_ATTRIBUTE[domain], metric_definition=r["truth_note"], scope="fact",
            unit=r["unit"], value=float(r["truth"]), integer=False, matches_played=None,
            minutes_played=None, question=r["question"], source_name="Wikipedia (checked 2026-10-26)",
            source_url=r["source"], source_endpoint=r["source"], retrieved_utc="2026-10-26",
            verification="checked on Wikipedia for question set v2; Qwen3-32B within 2% in >= 50% of 20 answers",
            notes="Familiar fact: strong prior expected."))
    return pd.DataFrame(rows)


def young_entities() -> pd.DataFrame:
    rows = []
    for key, label, mean, tier in YOUNG_ITEMS:
        rows.append(dict(
            entity_id=f"young-{key}-price", dataset="young", domain="prices", competition="", year="",
            event_end_date="", after_cutoff=False, entity_type="product", entity_name=label,
            entity_label=label, entity_code=key, team_code="", team_name="", position="", famous="",
            metric="price", metric_label="price", metric_definition="Price in British pounds (UK).",
            scope="fact", unit="British pounds", value=mean, integer=False, matches_played=None,
            minutes_played=None, question=f"How much does {label} cost in the UK, in British pounds?",
            source_name="Young et al. (2026) pre-registration, human pilot mean", source_url=OSF_YOUNG,
            source_endpoint=OSF_YOUNG, retrieved_utc=RETRIEVED,
            verification="NOT a true value: human pilot mean, used only to mark the item low or high",
            notes=f"{tier} price item in Young et al. Experiment 1."))
    return pd.DataFrame(rows)


def build_entities() -> pd.DataFrame:
    parts = [wc_team_entities(2026), wc2026_player_entities(), olympics_entities(),
             wc_team_entities(2022), fact_entities(), young_entities()]
    df = pd.concat(parts, ignore_index=True)[COLUMNS]
    assert df["entity_id"].is_unique
    return df


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=str(ROOT / "candidate_entities.csv"))
    a = ap.parse_args(argv)
    df = build_entities()
    df.to_csv(a.out, index=False)
    print(f"{len(df)} entities -> {a.out}")
    print(df.groupby(["dataset", "domain", "metric", "scope"]).size().to_string())


if __name__ == "__main__":
    main()
