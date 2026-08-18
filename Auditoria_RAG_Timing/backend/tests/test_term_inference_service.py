import pytest
from fastapi import HTTPException

from app.schemas.term_inference import TermsPayload
from app.services.term_inference_service import (
    build_probe_batch,
    classify_term,
    normalize_terms_payload,
    profile_from_summary_csv,
    profile_from_summary_groups,
)


def test_profile_uses_short_high_low_as_primary_boundary():
    profile = profile_from_summary_groups(
        [
            {"frequency": "high", "length": "short", "mean_ttfb_ms": 80.0, "std_ttfb_ms": 4.0},
            {"frequency": "medium", "length": "short", "mean_ttfb_ms": 105.0, "std_ttfb_ms": 5.0},
            {"frequency": "low", "length": "short", "mean_ttfb_ms": 140.0, "std_ttfb_ms": 8.0},
        ],
        "test",
    )

    assert profile.threshold_ms == 110.0
    assert profile.gray_zone_ms == 6.0
    assert profile.medium_mean_ms == 105.0


def test_profile_rejects_calibration_when_high_is_not_faster_than_low():
    with pytest.raises(HTTPException) as exc:
        profile_from_summary_groups(
            [
                {"frequency": "high", "length": "short", "mean_ttfb_ms": 140.0, "std_ttfb_ms": 4.0},
                {"frequency": "low", "length": "short", "mean_ttfb_ms": 80.0, "std_ttfb_ms": 4.0},
            ],
            "test",
        )

    assert exc.value.status_code == 422
    assert "high/short must be faster" in exc.value.detail


def test_summary_csv_rejects_raw_csv_shape():
    raw_csv = b"request_index,query_text,ttfb_ms\n1,hello,10\n"

    with pytest.raises(HTTPException) as exc:
        profile_from_summary_csv(raw_csv, "raw.csv")

    assert exc.value.status_code == 422
    assert "Raw CSV" in exc.value.detail


def test_classify_term_uses_gray_zone_for_inconclusive():
    profile = profile_from_summary_groups(
        [
            {"frequency": "high", "length": "short", "mean_ttfb_ms": 80.0, "std_ttfb_ms": 4.0},
            {"frequency": "low", "length": "short", "mean_ttfb_ms": 140.0, "std_ttfb_ms": 4.0},
        ],
        "test",
    )

    assert classify_term([82.0, 84.0], profile)[0] == "likely_present"
    assert classify_term([136.0, 138.0], profile)[0] == "likely_absent"
    assert classify_term([109.0, 111.0], profile)[0] == "inconclusive"


def test_terms_payload_deduplicates_and_uses_default_controls():
    payload = normalize_terms_payload(TermsPayload(terms=[" bitcoin ", "Bitcoin", "gutenberg"]))

    assert payload["terms"] == ["bitcoin", "gutenberg"]
    assert payload["negative_controls"]
    assert payload["custom_queries"] == {}


def test_terms_payload_accepts_custom_queries():
    payload = normalize_terms_payload(
        TermsPayload(
            custom_queries={
                " man ": [" the man of the day ", "the man of the day", "city man"],
                "Tesla": ["tesla battery"],
            }
        )
    )

    assert payload["terms"] == ["man", "Tesla"]
    assert payload["custom_queries"]["man"] == ["the man of the day", "city man"]


def test_probe_batch_avoids_adjacent_terms_when_possible():
    import random

    probes = build_probe_batch(["bitcoin", "gutenberg", "matrix"], {}, 2, random.Random(7))

    for left, right in zip(probes, probes[1:]):
        assert left[0] != right[0]


def test_probe_batch_interleaves_negative_controls_to_reduce_cache_effects():
    import random

    probe_indexes = {}

    mixed = build_probe_batch(
        ["bitcoin", "playstation", "gutenberg"],
        probe_indexes,
        2,
        random.Random(7),
        negative_controls=["control"],
    )

    assert mixed[3][0] == "control"
    assert mixed[7][0] == "control"
    assert probe_indexes["control"] == 2


def test_probe_batch_can_limit_total_probe_count():
    import random

    probe_indexes = {}

    probes = build_probe_batch(
        ["control-a", "control-b"],
        probe_indexes,
        5,
        random.Random(7),
        max_total_probes=5,
    )

    assert len(probes) == 5
    assert sum(probe_indexes.values()) == 5


def test_probe_batch_uses_custom_queries_when_available():
    import random

    probe_indexes = {}

    probes = build_probe_batch(
        ["man"],
        probe_indexes,
        3,
        random.Random(7),
        custom_queries={"man": ["the man of the day", "city man"]},
    )

    queries = [query for _, query in probes]
    assert sorted(queries) == ["city man", "the man of the day", "the man of the day"]
