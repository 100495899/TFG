import csv
import io
import random
import uuid
from dataclasses import dataclass
from typing import Any

import numpy as np
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditSession
from app.schemas.term_inference import TermsPayload
from app.services.statistics_service import build_summary

PROBE_TEMPLATES = [
    "What is {term}?",
    "Explain {term}.",
    "Information about {term}.",
    "Context for {term}.",
    "Meaning of {term}.",
    "About {term}.",
    "Describe {term}.",
    "Details about {term}.",
    "Definition of {term}.",
    "Tell me about {term}.",
    "Give context on {term}.",
    "Summarize the {term}.",
]

DEFAULT_NEGATIVE_CONTROLS = ["zenthorium", "qrevanta", "malvexor", "norithium", "veltraxis"]


@dataclass(frozen=True)
class CalibrationProfile:
    high_mean_ms: float
    high_std_ms: float
    medium_mean_ms: float | None
    low_mean_ms: float
    low_std_ms: float
    threshold_ms: float
    gray_zone_ms: float
    source_label: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "high_mean_ms": self.high_mean_ms,
            "high_std_ms": self.high_std_ms,
            "medium_mean_ms": self.medium_mean_ms,
            "low_mean_ms": self.low_mean_ms,
            "low_std_ms": self.low_std_ms,
            "threshold_ms": self.threshold_ms,
            "gray_zone_ms": self.gray_zone_ms,
            "source_label": self.source_label,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "CalibrationProfile":
        return cls(
            high_mean_ms=float(raw["high_mean_ms"]),
            high_std_ms=float(raw["high_std_ms"]),
            medium_mean_ms=float(raw["medium_mean_ms"]) if raw.get("medium_mean_ms") is not None else None,
            low_mean_ms=float(raw["low_mean_ms"]),
            low_std_ms=float(raw["low_std_ms"]),
            threshold_ms=float(raw["threshold_ms"]),
            gray_zone_ms=float(raw["gray_zone_ms"]),
            source_label=str(raw["source_label"]),
        )


def normalize_terms_payload(payload: TermsPayload) -> dict[str, Any]:
    custom_queries = _validate_custom_queries(payload.custom_queries)
    terms = list(custom_queries) if custom_queries else _dedupe_and_validate_terms(payload.terms, "terms")
    controls = _dedupe_and_validate_terms(payload.negative_controls, "negative_controls") if payload.negative_controls else DEFAULT_NEGATIVE_CONTROLS
    return {"terms": terms, "negative_controls": controls, "custom_queries": custom_queries}


def _dedupe_and_validate_terms(values: list[str], field_name: str) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        term = value.strip()
        key = term.casefold()
        if not term:
            raise HTTPException(status_code=422, detail=f"{field_name} cannot contain empty terms")
        if len(term) > 80:
            raise HTTPException(status_code=422, detail=f"{field_name} terms cannot exceed 80 characters")
        if key not in seen:
            seen.add(key)
            result.append(term)
    if not result:
        raise HTTPException(status_code=422, detail=f"{field_name} must contain at least one term")
    return result


def _validate_custom_queries(raw_queries: dict[str, list[str]]) -> dict[str, list[str]]:
    if not raw_queries:
        return {}

    result: dict[str, list[str]] = {}
    seen_terms: set[str] = set()
    for raw_term, queries in raw_queries.items():
        term = raw_term.strip()
        key = term.casefold()
        if not term:
            raise HTTPException(status_code=422, detail="custom_queries cannot contain empty terms")
        if len(term) > 80:
            raise HTTPException(status_code=422, detail="custom_queries terms cannot exceed 80 characters")
        if key in seen_terms:
            continue
        if not isinstance(queries, list) or not queries:
            raise HTTPException(status_code=422, detail=f"custom_queries for {term} must contain at least one query")

        cleaned_queries: list[str] = []
        seen_queries: set[str] = set()
        for raw_query in queries:
            query = raw_query.strip()
            query_key = query.casefold()
            if not query:
                raise HTTPException(status_code=422, detail=f"custom_queries for {term} cannot contain empty queries")
            if query_key not in seen_queries:
                seen_queries.add(query_key)
                cleaned_queries.append(query)
        if not cleaned_queries:
            raise HTTPException(status_code=422, detail=f"custom_queries for {term} must contain at least one query")
        seen_terms.add(key)
        result[term] = cleaned_queries

    if not result:
        raise HTTPException(status_code=422, detail="custom_queries must contain at least one term")
    return result


def profile_from_summary_groups(groups: list[dict[str, Any]], source_label: str) -> CalibrationProfile:
    def find(frequency: str) -> dict[str, Any]:
        for group in groups:
            if group.get("frequency") == frequency and group.get("length") == "short":
                return group
        raise HTTPException(status_code=422, detail=f"Calibration profile is missing {frequency}/short")

    def read_optional_number(value: Any) -> float | None:
        if value in (None, ""):
            return None
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return None
        return parsed if np.isfinite(parsed) else None

    def read_required_number(value: Any, label: str) -> float:
        parsed = read_optional_number(value)
        if parsed is None:
            raise HTTPException(status_code=422, detail=f"Calibration profile has no valid {label}")
        return parsed

    high = find("high")
    low = find("low")
    medium = next((group for group in groups if group.get("frequency") == "medium" and group.get("length") == "short"), None)
    high_mean = read_required_number(high.get("mean_ttfb_ms"), "high short mean")
    low_mean = read_required_number(low.get("mean_ttfb_ms"), "low short mean")
    high_std = read_required_number(high.get("std_ttfb_ms"), "high short standard deviation")
    low_std = read_required_number(low.get("std_ttfb_ms"), "low short standard deviation")
    medium_row = medium or {}
    medium_mean = read_optional_number(medium_row.get("mean_ttfb_ms"))
    if high_mean >= low_mean:
        raise HTTPException(
            status_code=422,
            detail="Calibration is not valid for this attack: high/short must be faster than low/short.",
        )
    return CalibrationProfile(
        high_mean_ms=high_mean,
        high_std_ms=high_std,
        medium_mean_ms=medium_mean,
        low_mean_ms=low_mean,
        low_std_ms=low_std,
        threshold_ms=(high_mean + low_mean) / 2,
        gray_zone_ms=max(high_std, low_std, 1.0) * 0.75,
        source_label=source_label,
    )


async def profile_from_audit(session: AsyncSession, audit_id: uuid.UUID) -> CalibrationProfile:
    audit = await session.get(AuditSession, audit_id)
    if audit is None:
        raise HTTPException(status_code=404, detail="Calibration audit not found")
    if audit.status != "COMPLETED":
        raise HTTPException(status_code=422, detail="Calibration audit must be completed")
    summary = await build_summary(session, audit_id)
    groups = [
        {
            "frequency": group.frequency,
            "length": group.length,
            "mean_ttfb_ms": group.mean_ms,
            "std_ttfb_ms": group.std_ms,
        }
        for group in summary.by_frequency_length
    ]
    return profile_from_summary_groups(groups, f"Audit {audit_id}")


def profile_from_summary_csv(content: bytes, filename: str) -> CalibrationProfile:
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    required = {"frequency", "length", "mean_ttfb_ms", "std_ttfb_ms"}
    fieldnames = set(reader.fieldnames or [])
    if not required.issubset(fieldnames):
        if {"request_index", "query_text", "ttfb_ms"}.issubset(fieldnames):
            raise HTTPException(status_code=422, detail="Raw CSV is not supported here. Upload the Summary CSV.")
        raise HTTPException(status_code=422, detail="CSV must be the Summary CSV exported from an audit report")
    return profile_from_summary_groups(list(reader), filename)


def build_probe_batch(
    active_terms: list[str],
    probe_indexes: dict[str, int],
    count_per_term: int,
    rng: random.Random,
    max_probes_per_term: int | None = None,
    negative_controls: list[str] | None = None,
    max_total_probes: int | None = None,
    custom_queries: dict[str, list[str]] | None = None,
) -> list[tuple[str, str]]:
    batch: list[tuple[str, str]] = []
    for term in active_terms:
        if max_total_probes is not None and len(batch) >= max_total_probes:
            break
        start = probe_indexes.get(term, 0)
        count = count_per_term
        if max_probes_per_term is not None:
            count = max(0, min(count_per_term, max_probes_per_term - start))
        if max_total_probes is not None:
            count = min(count, max_total_probes - len(batch))
        for offset in range(count):
            probe_index = start + offset
            if custom_queries and term in custom_queries:
                queries = custom_queries[term]
                query_text = queries[probe_index % len(queries)]
            else:
                template = PROBE_TEMPLATES[probe_index % len(PROBE_TEMPLATES)]
                query_text = template.format(term=term)
            batch.append((term, query_text))
        probe_indexes[term] = start + count
    rng.shuffle(batch)

    remaining = batch.copy()
    ordered: list[tuple[str, str]] = []
    last_term: str | None = None
    while remaining:
        index = next((i for i, item in enumerate(remaining) if item[0] != last_term), 0)
        item = remaining.pop(index)
        ordered.append(item)
        last_term = item[0]

    if not ordered or not negative_controls:
        return ordered

    control_index = 0
    since_last_control = 0
    interval = max(1, len(active_terms))
    with_controls: list[tuple[str, str]] = []
    for item in ordered:
        with_controls.append(item)
        since_last_control += 1
        if since_last_control >= interval:
            control = negative_controls[control_index % len(negative_controls)]
            control_index += 1
            probe_index = probe_indexes.get(control, 0)
            template = PROBE_TEMPLATES[probe_index % len(PROBE_TEMPLATES)]
            with_controls.append((control, template.format(term=control)))
            probe_indexes[control] = probe_index + 1
            since_last_control = 0

    return with_controls


def classify_term(values: list[float], profile: CalibrationProfile) -> tuple[str, float | None, float | None, float | None, str | None]:
    if not values:
        return "inconclusive", None, None, None, None
    if len(values) < 100:
        cleaned = values.copy()
    else:
        values_array = np.array(values, dtype=float)
        lower_limit = float(np.percentile(values_array, 1))
        upper_limit = float(np.percentile(values_array, 99))
        cleaned = [value for value in values if lower_limit <= value <= upper_limit]
    if not cleaned:
        return "inconclusive", None, None, None, None

    mean = float(np.mean(cleaned))
    std = float(np.std(np.array(cleaned, dtype=float)))
    distance = mean - profile.threshold_ms
    references = {
        "high": profile.high_mean_ms,
        "low": profile.low_mean_ms,
    }
    if profile.medium_mean_ms is not None:
        references["medium"] = profile.medium_mean_ms
    closest = min(references, key=lambda name: abs(mean - references[name]))

    lower_bound = profile.threshold_ms - profile.gray_zone_ms
    upper_bound = profile.threshold_ms + profile.gray_zone_ms
    if mean < lower_bound:
        classification = "likely_present"
    elif mean > upper_bound:
        classification = "likely_absent"
    else:
        classification = "inconclusive"
    return classification, mean, std, distance, closest
