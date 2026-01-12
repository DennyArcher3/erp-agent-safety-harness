"""
Temporal Validator

Prevents actions on closed financial periods and enforces
time-based business rules.
"""

from typing import Dict, Any, Optional, Set
from datetime import datetime, date, timezone
from .base import BaseValidator, ValidationResult


class TemporalValidator(BaseValidator):
    """
    Validates time-based constraints.

    Prevents:
    - Modifications to closed financial periods
    - Actions outside business hours (if configured)
    - Backdated transactions
    """

    def __init__(
        self,
        closed_periods: Optional[Set[str]] = None,  # Format: "YYYY-MM"
        allow_backdating_days: int = 0,
        business_hours_only: bool = False,
        business_start_hour: int = 9,
        business_end_hour: int = 17,
        name: Optional[str] = None
    ):
        super().__init__(name)
        self.closed_periods = closed_periods or set()
        self.allow_backdating_days = allow_backdating_days
        self.business_hours_only = business_hours_only
        self.business_start_hour = business_start_hour
        self.business_end_hour = business_end_hour

    def validate(
        self,
        action_type: str,
        parameters: Dict[str, Any],
        context: Optional[Any] = None
    ) -> ValidationResult:
        """Validate temporal constraints"""

        # Check business hours
        if self.business_hours_only:
            result = self._check_business_hours()
            if not result.approved:
                return result

        # Check for closed period modifications
        target_date = self._extract_date(parameters)
        if target_date:
            result = self._check_closed_period(target_date)
            if not result.approved:
                return result

            result = self._check_backdating(target_date)
            if not result.approved:
                return result

        return self._approve()

    def _check_business_hours(self) -> ValidationResult:
        """Check if current time is within business hours"""
        now = datetime.now(timezone.utc)
        hour = now.hour

        if hour < self.business_start_hour or hour >= self.business_end_hour:
            return self._reject(
                f"Action outside business hours ({self.business_start_hour}:00-{self.business_end_hour}:00 UTC)",
                risk_level="LOW"
            )

        return self._approve()

    def _check_closed_period(self, target_date: date) -> ValidationResult:
        """Check if date falls in a closed period"""
        period = target_date.strftime("%Y-%m")

        if period in self.closed_periods:
            return self._reject(
                f"Cannot modify closed financial period: {period}",
                risk_level="HIGH"
            )

        return self._approve()

    def _check_backdating(self, target_date: date) -> ValidationResult:
        """Check if date is too far in the past"""
        today = date.today()
        days_back = (today - target_date).days

        if days_back > self.allow_backdating_days:
            return self._reject(
                f"Backdating by {days_back} days exceeds limit of {self.allow_backdating_days}",
                risk_level="MEDIUM",
                metadata={"target_date": str(target_date), "days_back": days_back}
            )

        return self._approve()

    def _extract_date(self, parameters: Dict[str, Any]) -> Optional[date]:
        """Extract date from action parameters"""
        for key in ("date", "transaction_date", "effective_date", "posting_date"):
            if key in parameters:
                value = parameters[key]
                if isinstance(value, date):
                    return value
                if isinstance(value, datetime):
                    return value.date()
                if isinstance(value, str):
                    try:
                        return datetime.fromisoformat(value).date()
                    except ValueError:
                        pass
        return None

    def close_period(self, period: str) -> None:
        """Mark a period as closed (format: YYYY-MM)"""
        self.closed_periods.add(period)

    def open_period(self, period: str) -> None:
        """Mark a period as open"""
        self.closed_periods.discard(period)
