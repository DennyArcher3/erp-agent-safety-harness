"""
ERP Agent Safety Harness

A safety layer for AI-driven financial operations that validates
LLM outputs against deterministic business rules before execution.
"""

from .harness.core import SafetyHarness
from .harness.decorators import validate, require_approval
from .validators.base import ValidationResult

__version__ = "0.1.0"
__all__ = ["SafetyHarness", "validate", "require_approval", "ValidationResult"]
