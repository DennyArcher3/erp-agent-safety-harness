"""
Sequence Validator

Detects dangerous patterns across multiple actions. Individual actions
may be safe, but become dangerous in combination.

This is crucial for AI safety - an AI might decompose a harmful action
into innocent-looking steps.
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from collections import deque
from datetime import datetime, timedelta, timezone
from .base import BaseValidator, ValidationResult


@dataclass
class ActionRecord:
    """Record of a past action for sequence analysis"""
    action_type: str
    parameters: Dict[str, Any]
    timestamp: datetime
    agent_id: str


@dataclass
class DangerousPattern:
    """Definition of a dangerous action sequence"""
    name: str
    sequence: List[str]  # Action types in order
    window_seconds: int  # Time window to look for pattern
    risk_level: str
    description: str


class SequenceValidator(BaseValidator):
    """
    Detects dangerous multi-action patterns.

    Example: Price drop followed by large order might indicate manipulation:
        1. update_price(sku="WIDGET", price=0.01)  # Looks innocent
        2. create_order(sku="WIDGET", quantity=10000)  # Looks innocent
        3. Together: Someone just bought $50K inventory for $100

    This validator maintains a sliding window of recent actions and
    checks each new action against known dangerous patterns.
    """

    # Default dangerous patterns
    DEFAULT_PATTERNS = [
        DangerousPattern(
            name="PRICE_MANIPULATION",
            sequence=["update_price", "create_order"],
            window_seconds=300,
            risk_level="CRITICAL",
            description="Price reduction followed by large order - possible manipulation"
        ),
        DangerousPattern(
            name="REFUND_ABUSE",
            sequence=["process_refund", "process_refund", "process_refund"],
            window_seconds=300,
            risk_level="HIGH",
            description="Multiple refunds in short window - possible abuse"
        ),
        DangerousPattern(
            name="INVENTORY_DRAIN",
            sequence=["update_inventory", "create_order", "fulfill_order"],
            window_seconds=60,
            risk_level="HIGH",
            description="Inventory update followed by immediate order+fulfillment"
        ),
        DangerousPattern(
            name="RAPID_MODIFICATION",
            sequence=["update_order", "update_order", "update_order"],
            window_seconds=60,
            risk_level="MEDIUM",
            description="Rapid order modifications - possible testing/probing"
        ),
    ]

    def __init__(
        self,
        patterns: Optional[List[DangerousPattern]] = None,
        window_size: int = 100,
        max_same_action_per_minute: int = 10,
        name: Optional[str] = None
    ):
        """
        Args:
            patterns: Dangerous patterns to detect (uses defaults if None)
            window_size: Maximum actions to keep in history
            max_same_action_per_minute: Max repetitions of same action type
        """
        super().__init__(name)
        self.patterns = patterns or self.DEFAULT_PATTERNS
        self.window_size = window_size
        self.max_same_action_per_minute = max_same_action_per_minute
        self._history: deque[ActionRecord] = deque(maxlen=window_size)

    def validate(
        self,
        action_type: str,
        parameters: Dict[str, Any],
        context: Optional[Any] = None
    ) -> ValidationResult:
        """Check if this action completes a dangerous pattern"""

        now = datetime.now(timezone.utc)

        # Check for rapid repetition
        repetition_result = self._check_repetition(action_type, now)
        if not repetition_result.approved:
            return repetition_result

        # Check against all patterns
        for pattern in self.patterns:
            if self._matches_pattern(action_type, pattern, now):
                # Record the action before returning
                self._record_action(action_type, parameters, now, context)

                return self._reject(
                    f"Action completes dangerous pattern: {pattern.name} - {pattern.description}",
                    risk_level=pattern.risk_level,
                    metadata={
                        "pattern": pattern.name,
                        "sequence": pattern.sequence,
                        "window_seconds": pattern.window_seconds
                    }
                )

        # Record and approve
        self._record_action(action_type, parameters, now, context)
        return self._approve()

    def _check_repetition(self, action_type: str, now: datetime) -> ValidationResult:
        """Check for too many repetitions of same action"""
        minute_ago = now - timedelta(minutes=1)

        same_action_count = sum(
            1 for record in self._history
            if record.action_type == action_type and record.timestamp > minute_ago
        )

        if same_action_count >= self.max_same_action_per_minute:
            return self._reject(
                f"Too many '{action_type}' actions: {same_action_count} in last minute",
                risk_level="MEDIUM",
                metadata={"action_type": action_type, "count": same_action_count}
            )

        return self._approve()

    def _matches_pattern(
        self,
        action_type: str,
        pattern: DangerousPattern,
        now: datetime
    ) -> bool:
        """Check if action completes a dangerous pattern"""

        # This action should be the last in the sequence
        if pattern.sequence[-1] != action_type:
            return False

        # Look for preceding actions in the pattern
        window_start = now - timedelta(seconds=pattern.window_seconds)
        recent_actions = [
            r.action_type for r in self._history
            if r.timestamp > window_start
        ]

        # Check if the pattern (minus last action) exists in recent history
        pattern_prefix = pattern.sequence[:-1]
        if not pattern_prefix:
            return True  # Single-action pattern

        # Simple subsequence matching
        prefix_idx = 0
        for action in recent_actions:
            if action == pattern_prefix[prefix_idx]:
                prefix_idx += 1
                if prefix_idx >= len(pattern_prefix):
                    return True

        return False

    def _record_action(
        self,
        action_type: str,
        parameters: Dict[str, Any],
        timestamp: datetime,
        context: Optional[Any]
    ) -> None:
        """Record action in history"""
        agent_id = "unknown"
        if context and hasattr(context, 'proposed_by'):
            agent_id = context.proposed_by

        self._history.append(ActionRecord(
            action_type=action_type,
            parameters=parameters.copy(),
            timestamp=timestamp,
            agent_id=agent_id
        ))

    def add_pattern(self, pattern: DangerousPattern) -> None:
        """Add a new dangerous pattern"""
        self.patterns.append(pattern)

    def clear_history(self) -> None:
        """Clear action history (use carefully)"""
        self._history.clear()
