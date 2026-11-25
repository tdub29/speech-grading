import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import ted_ratings_corpus as ted  # noqa: E402


def row(**over):
    base = {"ratings": "[{'id': 1, 'name': 'Inspiring', 'count': 300}, {'id': 2, 'name': 'Longwinded', 'count': 60},"
                       " {'id': 3, 'name': 'Obnoxious', 'count': 40}]",
            "tags": "['science', 'technology']", "duration": "900", "num_speaker": "1", "film_date": "1300000000",
            "main_speaker": "Ada Lovelace", "title": "Engines", "event": "TED2011",
            "url": "https://www.ted.com/talks/ada_engines\n", "views": "1000000"}
    base.update(over)
    return base


def test_label_is_negative_share_of_all_tags():
    value = ted.label_row(row())
    assert value["neg_share"] == 0.25 and value["ratings_total"] == 400
    assert value["event_class"] == "ted_main" and value["year"] == 2011


def test_eligibility_rules():
    assert ted.label_row(row(num_speaker="2")) is None
    assert ted.label_row(row(duration="300")) is None
    assert ted.label_row(row(tags="['music', 'art']")) is None
    assert ted.label_row(row(ratings="[{'id': 1, 'name': 'Inspiring', 'count': 150}]")) is None


def test_event_classes():
    assert [ted.event_class(e) for e in ("TED2009", "TEDGlobal 2012", "TEDxPuget Sound", "TEDSalon NY2013",
                                         "University of California")] == \
        ["ted_main", "ted_global", "tedx", "ted_other", "external"]


def test_excerpt_is_centred_and_120s():
    assert ted.excerpt(900) == (390.0, 510.0)
    assert ted.excerpt(100) == (0.0, 120.0)


def test_youtube_match_rule():
    item = {"speaker": "Ada Lovelace", "csv_duration_sec": 900}
    ok = {"channel": "TED", "duration": 930, "title": "Engines | Ada Lovelace | TED"}
    assert ted.accept_hit(item, ok)
    assert not ted.accept_hit(item, dict(ok, channel="Some Reupload"))
    assert not ted.accept_hit(item, dict(ok, title="Engines | TED"))
    assert not ted.accept_hit(item, dict(ok, duration=1200))


def test_partial_spearman_recovers_sign():
    rows = [{"neg_share": i / 50, "views": 10 ** (5 + (i % 7) / 3), "year": 2008 + i % 9,
             "event_class": "ted_main" if i % 2 else "tedx", "metrics": {"m": -i + (i % 3)}} for i in range(50)]
    result = ted.association(rows, "m", n_boot=200)
    assert result["partial_spearman"] < -0.9 and result["partial_ci95"][1] < 0
    assert result["auc_low_neg_quartile_higher"] == 1.0
