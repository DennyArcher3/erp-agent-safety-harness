"""
Decorators for easy integration with existing code.

Allows wrapping functions to automatically validate through harness.
"""

from functools import wraps
from typing import Callable, Optional, Any
from .core import SafetyHarness


# Global harness instance (set via configure())
_global_harness: Optional[SafetyHarness] = None


def configure(harness: SafetyHarness) -> None:
    """Configure the global harness for decorators"""
    global _global_harness
    _global_harness = harness


def validate(
    action_type: Optional[str] = None,
    harness: Optional[SafetyHarness] = None
) -> Callable:
    """
    Decorator to validate function calls through safety harness.

    Usage:
        @validate(action_type="process_refund")
        def refund_order(order_id: str, amount: float):
            return erp.create_refund(order_id, amount)

    Or with explicit harness:
        @validate(action_type="update_price", harness=my_harness)
        def update_price(sku: str, price: float):
            return erp.update_price(sku, price)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Get harness
            h = harness or _global_harness
            if h is None:
                raise RuntimeError(
                    "No harness configured. Call configure(harness) or pass harness to decorator."
                )

            # Determine action type
            act_type = action_type or func.__name__

            # Build parameters from function arguments
            parameters = kwargs.copy()
            # Add positional args with generic names
            for i, arg in enumerate(args):
                parameters[f"arg_{i}"] = arg

            # Validate
            decision = h.evaluate(
                action_type=act_type,
                parameters=parameters,
                proposed_by=f"decorator:{func.__module__}.{func.__name__}"
            )

            if not decision.approved:
                raise ValidationError(
                    f"Action blocked by {decision.blocked_by}: {decision.reason}",
                    decision=decision
                )

            # Execute if approved
            return func(*args, **kwargs)

        return wrapper
    return decorator


def require_approval(
    action_type: Optional[str] = None,
    harness: Optional[SafetyHarness] = None,
    on_rejection: Optional[Callable] = None
) -> Callable:
    """
    Like @validate, but allows custom rejection handling.

    Usage:
        def handle_rejection(decision):
            log.warning(f"Blocked: {decision.reason}")
            return {"error": "Action not allowed"}

        @require_approval(on_rejection=handle_rejection)
        def dangerous_action(params):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            h = harness or _global_harness
            if h is None:
                raise RuntimeError("No harness configured.")

            act_type = action_type or func.__name__
            parameters = kwargs.copy()
            for i, arg in enumerate(args):
                parameters[f"arg_{i}"] = arg

            decision = h.evaluate(
                action_type=act_type,
                parameters=parameters,
                proposed_by=f"decorator:{func.__module__}.{func.__name__}"
            )

            if not decision.approved:
                if on_rejection:
                    return on_rejection(decision)
                raise ValidationError(
                    f"Action blocked: {decision.reason}",
                    decision=decision
                )

            return func(*args, **kwargs)

        return wrapper
    return decorator


class ValidationError(Exception):
    """Raised when validation fails"""

    def __init__(self, message: str, decision: Any = None):
        super().__init__(message)
        self.decision = decision
