import itertools
import uuid

import numpy as np
from scipy import stats
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditResult
from app.schemas.audit import AuditSummary, ComparisonStats, GroupStats


def _safe_float(value) -> float | None:
    if value is None or np.isnan(value):
        return None
    return float(value)


def _evidence(p_value: float | None, d: float | None, count_a: int, count_b: int) -> str:
    if count_a < 30 or count_b < 30 or p_value is None or d is None:
        return "insufficient"
    abs_d = abs(d)
    if p_value < 0.001 and abs_d >= 0.8:
        return "strong"
    if p_value < 0.01 and abs_d >= 0.5:
        return "moderate"
    if p_value < 0.05 and abs_d >= 0.2:
        return "weak"
    return "insufficient"


async def build_summary(session: AsyncSession, session_id: uuid.UUID) -> AuditSummary:
    rows = (await session.execute(select(AuditResult).where(AuditResult.session_id == session_id))).scalars().all()
    groups: list[GroupStats] = []
    values_by_group: dict[str, list[float]] = {}
    for freq in ["high", "medium", "low"]:
        group_rows = [r for r in rows if r.frequency_tag == freq]
        vals = [float(r.ttfb_ms) for r in group_rows if not r.is_error and r.ttfb_ms is not None]
        values_by_group[freq] = vals
        error_rate = (sum(1 for r in group_rows if r.is_error) / len(group_rows)) if group_rows else 0.0
        arr = np.array(vals, dtype=float)
        groups.append(
            GroupStats(
                frequency=freq,
                count=len(vals),
                mean_ms=_safe_float(np.mean(arr)) if len(arr) else None,
                median_ms=_safe_float(np.median(arr)) if len(arr) else None,
                std_ms=_safe_float(np.std(arr)) if len(arr) else None,
                p25_ms=_safe_float(np.percentile(arr, 25)) if len(arr) else None,
                p75_ms=_safe_float(np.percentile(arr, 75)) if len(arr) else None,
                p95_ms=_safe_float(np.percentile(arr, 95)) if len(arr) else None,
                min_ms=_safe_float(np.min(arr)) if len(arr) else None,
                max_ms=_safe_float(np.max(arr)) if len(arr) else None,
                error_rate=error_rate,
            )
        )
    comparisons: list[ComparisonStats] = []
    for a, b in itertools.combinations(["high", "medium", "low"], 2):
        va, vb = values_by_group[a], values_by_group[b]
        p_welch = p_mw = d = mean_diff = median_diff = None
        if len(va) >= 2 and len(vb) >= 2:
            mean_diff = float(np.mean(vb) - np.mean(va))
            median_diff = float(np.median(vb) - np.median(va))
            p_welch = float(stats.ttest_ind(va, vb, equal_var=False).pvalue)
            p_mw = float(stats.mannwhitneyu(va, vb, alternative="two-sided").pvalue)
            pooled = np.sqrt((np.var(va) + np.var(vb)) / 2)
            d = float((np.mean(vb) - np.mean(va)) / pooled) if pooled > 0 else None
        comparisons.append(
            ComparisonStats(
                group_a=a,
                group_b=b,
                mean_difference_ms=mean_diff,
                median_difference_ms=median_diff,
                welch_p_value=p_welch,
                mann_whitney_p_value=p_mw,
                cohens_d=d,
                evidence=_evidence(p_welch, d, len(va), len(vb)),
            )
        )
    return AuditSummary(session_id=session_id, metric="ttfb_ms", groups=groups, comparisons=comparisons)
