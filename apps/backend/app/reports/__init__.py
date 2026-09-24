"""Institutional reports rendered from persisted simulation results."""

from .pdf import build_report_pdf
from .schema import ReportData

__all__ = ["ReportData", "build_report_pdf"]
