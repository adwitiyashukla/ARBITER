"""Objective oracles.

An oracle here never decides whether a bug report is reproduced. It only reports
machine-checkable facts about what happened on screen and in the page. The semantic
step, does this evidence match what the reporter described, belongs to the judge.
"""
from .crash import CrashOracle
from .visual import VisualOracle, analyze_burst
from .dom import DomOracle

__all__ = ["CrashOracle", "VisualOracle", "DomOracle", "analyze_burst"]
