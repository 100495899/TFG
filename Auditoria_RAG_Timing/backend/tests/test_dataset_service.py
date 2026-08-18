import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.schemas.dataset import DatasetContent
from app.services.dataset_service import (
    distribution,
    flatten_dataset,
    invalid_dataset_format,
)


def valid_dataset() -> dict:
    return {
        "alta_frecuencia": {
            "corta": ["High short"],
            "media": ["High query with medium length"],
            "larga": ["High query with a deliberately longer text"],
        },
        "media_frecuencia": {
            "corta": ["Medium short"],
            "media": ["Medium query with medium length"],
            "larga": ["Medium query with a deliberately longer text"],
        },
        "baja_frecuencia": {
            "corta": ["Low short"],
            "media": ["Low query with medium length"],
            "larga": ["Low query with a deliberately longer text"],
        },
    }


def test_grouped_dataset_is_flattened_for_execution():
    dataset = DatasetContent.model_validate(valid_dataset())

    queries = flatten_dataset(dataset)

    assert len(queries) == 9
    assert queries[0].frequency == "high"
    assert queries[0].length == "short"
    assert queries[-1].frequency == "low"
    assert queries[-1].length == "long"


def test_flat_array_is_rejected():
    with pytest.raises(ValidationError):
        DatasetContent.model_validate(
            [{"query": "What is time?", "frequency": "high", "length": "short"}]
        )


def test_missing_required_group_is_rejected():
    raw = valid_dataset()
    del raw["baja_frecuencia"]["larga"]

    with pytest.raises(ValidationError):
        DatasetContent.model_validate(raw)


def test_extra_group_is_rejected():
    raw = valid_dataset()
    raw["frecuencia_desconocida"] = {
        "corta": [],
        "media": [],
        "larga": [],
    }

    with pytest.raises(ValidationError):
        DatasetContent.model_validate(raw)


def test_empty_query_is_rejected():
    raw = valid_dataset()
    raw["alta_frecuencia"]["corta"] = ["   "]

    with pytest.raises(ValidationError):
        DatasetContent.model_validate(raw)


def test_distribution_counts_frequency_and_length():
    queries = flatten_dataset(DatasetContent.model_validate(valid_dataset()))

    assert distribution(queries) == {
        "frequency": {"high": 3, "medium": 3, "low": 3},
        "length": {"short": 3, "medium": 3, "long": 3},
    }


def test_format_error_contains_expected_example():
    error = invalid_dataset_format([{"message": "missing field"}])

    assert isinstance(error, HTTPException)
    assert error.status_code == 422
    assert "expected_format" in error.detail
