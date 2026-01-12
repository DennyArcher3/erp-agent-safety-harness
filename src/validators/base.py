"""
Base Validator

Abstract base class for all validators. Defines the interface that
all validators must implement.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..harness.core import ActionContext


@dataclass
class ValidationResult:
    """
    Result of a validation check.

    Attributes:
        approved: Whether the action passed this validator
        reason: Human-readable explanation (required if not approved)
        risk_level: LOW, MEDIUM, HIGH, CRITICAL, or UNKNOWN
        validator_name: Name of the validator that produced this result
        metadata: Additional context for debugging/auditing
    """
    approved: bool
    reason: Optional[str] = None
    risk_level: str = "LOW"
    validator_name: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if not self.approved and not self.reason:
            raise ValueError("Rejected validations must include a reason")


class BaseValidator(ABC):
    """
    Abstract base class for validators.

    Each validator checks one aspect of safety. Validators should be:
    - Deterministic: Same input always produces same output
    - Fast: Microsecond execution to match AI speed
    - Independent: No side effects, can run in parallel
    - Auditable: Clear reasoning in rejection messages
    """

    def __init__(self, name: Optional[str] = None):
        self.name = name or self.__class__.__name__

    @abstractmethod
    def validate(
        self,
        action_type: str,
        parameters: Dict[str, Any],
        context: Optional["ActionContext"] = None
    ) -> ValidationResult:
        """
        Validate a proposed action.

        Args:
            action_type: Type of action being proposed
            parameters: Action parameters to validate
            context: Full action context (optional, for advanced validators)

        Returns:
            ValidationResult with approval status and reasoning
        """
        pass

    def _approve(self, metadata: Optional[Dict[str, Any]] = None) -> ValidationResult:
        """Helper to create an approval result"""
        return ValidationResult(
            approved=True,
            validator_name=self.name,
            metadata=metadata
        )

    def _reject(
        self,
        reason: str,
        risk_level: str = "MEDIUM",
        metadata: Optional[Dict[str, Any]] = None
    ) -> ValidationResult:
        """Helper to create a rejection result"""
        return ValidationResult(
            approved=False,
            reason=reason,
            risk_level=risk_level,
            validator_name=self.name,
            metadata=metadata
        )
