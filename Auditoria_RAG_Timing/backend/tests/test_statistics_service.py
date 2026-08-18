from app.services.statistics_service import _evidence, _filter_extreme_percentiles


def test_evidence_is_insufficient_without_enough_data():
    assert _evidence(0.0001, 4, 4) == "insufficient"


def test_evidence_detects_strength_levels():
    assert _evidence(0.0005, 40, 40) == "strong"
    assert _evidence(0.005, 40, 40) == "moderate"
    assert _evidence(0.04, 40, 40) == "weak"


def test_evidence_requires_p_value():
    assert _evidence(None, 40, 40) == "insufficient"


def test_filter_extreme_percentiles_preserves_raw_data_contract():
    values = [0.0] + [float(value) for value in range(1, 101)] + [10_000.0]
    cleaned, lower_threshold, upper_threshold = _filter_extreme_percentiles(values)

    assert lower_threshold is not None
    assert upper_threshold is not None
    assert 0.0 not in cleaned
    assert 10_000.0 not in cleaned
    assert 50.0 in cleaned


def test_filter_extreme_percentiles_does_not_distort_small_groups():
    values = [10.0, 11.0, 12.0, 1000.0]

    assert _filter_extreme_percentiles(values) == (values, None, None)


def test_filter_extreme_percentiles_handles_empty_groups():
    assert _filter_extreme_percentiles([]) == ([], None, None)
