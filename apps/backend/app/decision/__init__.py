"""Decision-intelligence analysis over immutable simulation samples."""

from .catalog import describe, split_by_role
from .multiples import ImpliedMultiples, MultipleSummary, compute_implied_multiples, implied_multiples_payload
from .sensitivity import DriverRanking, RankedDriver, rank_drivers
from .targets import TargetAnalysis, analyze_target, wilson_interval
from .uncertainty import UncertaintyAssessment, assess_uncertainty

__all__ = [
    "DriverRanking",
    "ImpliedMultiples",
    "MultipleSummary",
    "RankedDriver",
    "TargetAnalysis",
    "UncertaintyAssessment",
    "analyze_target",
    "assess_uncertainty",
    "compute_implied_multiples",
    "describe",
    "implied_multiples_payload",
    "rank_drivers",
    "split_by_role",
    "wilson_interval",
]
