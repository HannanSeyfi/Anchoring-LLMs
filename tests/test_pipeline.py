"""End-to-end check of the run and analysis code with the simulated (dry-run) model."""

from pathlib import Path

from anchoring_llms import analysis, run

REPO = Path(__file__).resolve().parents[1]


def _run(out: Path, *extra: str) -> None:
    run.main(["--repo", str(REPO), "--model", "qwen3-8b", "--backend", "dryrun", "--smoke",
              "--output-dir", str(out), *extra])


def test_dry_run_and_analysis(tmp_path):
    out = tmp_path / "data"
    _run(out)
    raw = out / "raw" / "qwen3-8b"
    counts = {s: len(run.read_records(raw / s)) for s in ("baseline", "study1", "study2")}
    # smoke config: 2 items, 3 levels; baseline 3 samples, studies 2 samples per cell
    assert counts == {"baseline": 2 * 3 * 3, "study1": 2 * 8 * 3 * 2, "study2": 2 * 3 * 6 * 2}
    assert (out / "anchors" / "qwen3-8b.json").exists()
    assert len((out / "runs" / "qwen3-8b.jsonl").read_text().splitlines()) == 2  # start + finish

    # Running again resumes: nothing new is generated.
    files = sorted(p.name for p in raw.rglob("*.jsonl.gz"))
    _run(out)
    assert sorted(p.name for p in raw.rglob("*.jsonl.gz")) == files

    res_dir = tmp_path / "results"
    res = analysis.analyse(out, res_dir)
    assert (res_dir / "summary.md").exists()
    assert (res_dir / "hand_coding_sample.csv").exists()
    assert res["data_quality"]["parse_rate"].min() == 1.0
    assert list((res_dir / "figures").glob("*.png"))
