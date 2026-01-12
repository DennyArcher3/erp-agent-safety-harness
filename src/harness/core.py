"""
Core Safety Harness

The main orchestrator that coordinates validation, logging, and execution control.
Treats AI as an untrusted client - every action must pass deterministic validation.
"""

import uuid
import time
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime

from ..validators.base import BaseValidator, ValidationResult
from ..audit.logger import AuditLogger


@dataclass
class ActionContext:
    """Context for a proposed action"""
    action_id: str
    action_type: str
    parameters: Dict[str, Any]
    proposed_by: str
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HarnessDecision:
    """Final decision from the harness"""
    approved: bool
    action_context: ActionContext
    validation_results: List[ValidationResult]
    blocked_by: Optional[str] = None
    reason: Optional[str] = None
    execution_time_ms: float = 0.0


class SafetyHarness:
    """
    Safety harness for AI-driven operations.

    Core principle: AI is an untrusted client. Every proposed action
    must pass through deterministic validation before execution.

    Example:
        harness = SafetyHarness(
            validators=[FinancialValidator(), InventoryValidator()],
            fail_closed=True
        )

        decision = harness.evaluate(
            action_type="process_refund",
            parameters={"order_id": "123", "amount": 50.00},
            proposed_by="claude-agent"
        )

        if decision.approved:
            execute_action(decision.action_context.parameters)
    """

    def __init__(
        self,
        validators: List[BaseValidator],
        audit_logger: Optional[AuditLogger] = None,
        fail_closed: bool = True,
        max_actions_per_minute: int = 100,
        agent_id: str = "default-agent"
    ):
        """
        Initialize the safety harness.

        Args:
            validators: List of validators to run on each action
            audit_logger: Logger for audit trail (creates default if None)
            fail_closed: If True, block on any validation uncertainty
            max_actions_per_minute: Rate limit for actions
            agent_id: Identifier for the AI agent using this harness
        """
        self.validators = validators
        self.audit_logger = audit_logger or AuditLogger()
        self.fail_closed = fail_closed
        self.max_actions_per_minute = max_actions_per_minute
        self.agent_id = agent_id

        # Rate limiting state
        self._action_timestamps: List[float] = []

    def evaluate(
        self,
        action_type: str,
        parameters: Dict[str, Any],
        proposed_by: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> HarnessDecision:
        """
        Evaluate a proposed action against all validators.

        This is the core method - every AI-proposed action should go through here.

        Args:
            action_type: Type of action (e.g., "process_refund", "update_price")
            parameters: Action parameters
            proposed_by: Identifier for who/what proposed this action
            metadata: Additional context

        Returns:
            HarnessDecision with approval status and reasoning
        """
        start_time = time.time()

        # Create action context
        context = ActionContext(
            action_id=str(uuid.uuid4()),
            action_type=action_type,
            parameters=parameters,
            proposed_by=proposed_by or self.agent_id,
            timestamp=datetime.utcnow(),
            metadata=metadata or {}
        )

        # Check rate limit first
        if not self._check_rate_limit():
            decision = HarnessDecision(
                approved=False,
                action_context=context,
                validation_results=[],
                blocked_by="RateLimiter",
                reason=f"Rate limit exceeded: {self.max_actions_per_minute}/minute"
            )
            self.audit_logger.log_decision(decision)
            return decision

        # Run all validators
        validation_results: List[ValidationResult] = []
        blocked_by = None
        block_reason = None

        for validator in self.validators:
            try:
                result = validator.validate(action_type, parameters, context)
                validation_results.append(result)

                if not result.approved:
                    blocked_by = validator.__class__.__name__
                    block_reason = result.reason
                    # Don't break - run all validators for complete audit trail

            except Exception as e:
                # Validator error - fail closed if configured
                if self.fail_closed:
                    validation_results.append(ValidationResult(
                        approved=False,
                        reason=f"Validator error: {str(e)}",
                        risk_level="UNKNOWN"
                    ))
                    blocked_by = validator.__class__.__name__
                    block_reason = f"Validator error (fail_closed): {str(e)}"

        # Final decision
        approved = all(r.approved for r in validation_results)

        execution_time = (time.time() - start_time) * 1000

        decision = HarnessDecision(
            approved=approved,
            action_context=context,
            validation_results=validation_results,
            blocked_by=blocked_by if not approved else None,
            reason=block_reason if not approved else None,
            execution_time_ms=execution_time
        )

        # Log decision
        self.audit_logger.log_decision(decision)

        return decision

    def _check_rate_limit(self) -> bool:
        """Check if we're within rate limits"""
        now = time.time()
        minute_ago = now - 60

        # Remove old timestamps
        self._action_timestamps = [
            ts for ts in self._action_timestamps if ts > minute_ago
        ]

        if len(self._action_timestamps) >= self.max_actions_per_minute:
            return False

        self._action_timestamps.append(now)
        return True

    def add_validator(self, validator: BaseValidator) -> None:
        """Add a validator to the harness"""
        self.validators.append(validator)

    def remove_validator(self, validator_class: type) -> bool:
        """Remove validators of a specific class"""
        original_count = len(self.validators)
        self.validators = [
            v for v in self.validators
            if not isinstance(v, validator_class)
        ]
        return len(self.validators) < original_count


class SafetyHarnessBuilder:
    """Builder pattern for creating configured harnesses"""

    def __init__(self):
        self._validators: List[BaseValidator] = []
        self._audit_logger: Optional[AuditLogger] = None
        self._fail_closed: bool = True
        self._max_actions_per_minute: int = 100
        self._agent_id: str = "default-agent"

    def with_validator(self, validator: BaseValidator) -> "SafetyHarnessBuilder":
        self._validators.append(validator)
        return self

    def with_audit_logger(self, logger: AuditLogger) -> "SafetyHarnessBuilder":
        self._audit_logger = logger
        return self

    def with_fail_open(self) -> "SafetyHarnessBuilder":
        """Warning: fail_open is dangerous - use only for testing"""
        self._fail_closed = False
        return self

    def with_rate_limit(self, max_per_minute: int) -> "SafetyHarnessBuilder":
        self._max_actions_per_minute = max_per_minute
        return self

    def for_agent(self, agent_id: str) -> "SafetyHarnessBuilder":
        self._agent_id = agent_id
        return self

    def build(self) -> SafetyHarness:
        return SafetyHarness(
            validators=self._validators,
            audit_logger=self._audit_logger,
            fail_closed=self._fail_closed,
            max_actions_per_minute=self._max_actions_per_minute,
            agent_id=self._agent_id
        )
