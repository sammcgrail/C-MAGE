"""How many images each blind Sonnet reader was handed, and from which row (benchmarks/reader_protocol.json).

The corpus arms were read ten images to a reader until 2 Oct 2026, then one image per reader. The
switch is recorded once, in the repo, and every page that shows these rows says where it falls:
the Sonnet 5.5 tab (build_sonnet55c.py), /sonnet-compare (build_sonnet55.py) and /sonnet-report
(build_sonnet_report.py).
"""
import json
from pathlib import Path

PATH = Path(__file__).resolve().parent.parent / "benchmarks" / "reader_protocol.json"


def switches() -> list[dict]:
    return json.load(open(PATH))["switches"] if PATH.exists() else []


def single() -> dict | None:
    """The switch to single-image readers, or None if there is none on record."""
    return next((s for s in switches() if s.get("images_per_reader") == 1), None)


def summary(lane_rows: int | None = None, s5_rows: int | None = None) -> dict | None:
    """What a page needs: the rows each arm switched at, and whether any single-image row exists yet."""
    s = single()
    if not s:
        return None
    f = s["rows_from"]
    return {"at": s["at"], "images_per_reader": 1, "before": s["before"],
            "s55c_from_row": f["s55c"], "s5_from_row": f["s5"],
            "s55c_single_rows": max(0, lane_rows - f["s55c"] + 1) if lane_rows is not None else None,
            "s5_single_rows": max(0, s5_rows - f["s5"] + 1) if s5_rows is not None else None,
            "why": s["why"], "prompt_change": s["prompt_change"], "pairing": s["pairing"],
            "text": (f"Single-image readers from row {f['s55c']} of the Sonnet 5.5 arm and row {f['s5']} of the "
                     f"Sonnet 5 arm ({s['at'][:10]}): one image per reader, both models reading each new image "
                     f"at the same time. Earlier rows were read {s['before']} images to a reader, in one shared "
                     f"context.")}
