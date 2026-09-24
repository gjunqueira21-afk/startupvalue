"""Decision-intelligence analysis over immutable simulation samples."""

from .catalog import describe, split_by_role
from .sensitivity import DriverRanking, RankedDriver, rank_drivers
from .targets import TargetAnalysis, analyze_target, wilson_interval
from .uncertainty import UncertaintyAssessment, assess_uncertainty

__all__ = [
    "DriverRanking",
    "RankedDriver",
    "TargetAnalysis",
    "UncertaintyAssessment",
    "analyze_target",
    "assess_uncertainty",
    "describe",
    "rank_drivers",
    "split_by_role",
    "wilson_interval",
]
