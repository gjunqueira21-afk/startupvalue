"""Published, versioned valuation-uncertainty classification (see METHODOLOGY §9).

The label is a presentation convention over dispersion measures of the full
scenario population. It describes how wide the simulated distribution is under
the user's assumptions; it is not a calibrated market-risk rating.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Literal

UNCERTAINTY_RULE_VERSION = "uncertainty-v1"
# Upper-exclusive band limits for IQR / P50: LOW < 0.40 <= MODERATE < 0.80 <= HIGH < 1.50.
IQR_RATIO_BANDS = (0.40, 0.80, 1.50)
# A median below one currency unit is not a meaningful denominator.
MATERIAL_MEDIAN = 1.0
# From this share of non-positive outcomes on, the case is VERY HIGH regardless of IQR.
NON_POSITIVE_OVERRIDE = 0.25

UncertaintyLabel = Literal["LOW", "MODERATE", "HIGH", "VERY HIGH"]
UncertaintyReason = Literal["iqr_ratio", "median_not_positive", "material_non_positive_mass"]


@dataclass(frozen=True, slots=True)
class UncertaintyAssessment:
    label: UncertaintyLabel
    reason: UncertaintyReason
    rule_version: str
    iqr: float
    iqr_ratio: float | None
    spread80: float
    spread80_ratio: float | None
    non_positive_probability: float


def assess_uncertainty(
    *,
    p10: float,
    p25: float,
    p50: float,
    p75: float,
    p90: float,
    non_positive_probability: float,
) -> UncertaintyAssessment:
    quantiles = (p10, p25, p50, p75, p90)
    if not all(isfinite(value) for value in quantiles):
        raise ValueError("percentiles must be finite")
    if any(left > right for left, right in zip(quantiles, quantiles[1:], strict=False)):
        raise ValueError("percentiles must be nondecreasing")
    if not isfinite(non_positive_probability) or not 0.0 <= non_positive_probability <= 1.0:
        raise ValueError("non_positive_probability must be in [0, 1]")

    iqr = p75 - p25
    spread80 = p90 - p10
    if p50 < MATERIAL_MEDIAN:
        return UncertaintyAssessment(
            "VERY HIGH",
            "median_not_positive",
            UNCERTAINTY_RULE_VERSION,
            iqr,
            None,
            spread80,
            None,
            non_positive_probability,
        )
    iqr_ratio = iqr / p50
    spread80_ratio = spread80 / p50
    label: UncertaintyLabel
    reason: UncertaintyReason = "iqr_ratio"
    if non_positive_probability >= NON_POSITIVE_OVERRIDE:
        label, reason = "VERY HIGH", "material_non_positive_mass"
    elif iqr_ratio < IQR_RATIO_BANDS[0]:
        label = "LOW"
    elif iqr_ratio < IQR_RATIO_BANDS[1]:
        label = "MODERATE"
    elif iqr_ratio < IQR_RATIO_BANDS[2]:
        label = "HIGH"
    else:
        label = "VERY HIGH"
    return UncertaintyAssessment(
        label,
        reason,
        UNCERTAINTY_RULE_VERSION,
        iqr,
        iqr_ratio,
        spread80,
        spread80_ratio,
        non_positive_probability,
    )
