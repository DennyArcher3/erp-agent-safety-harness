"""
Financial Validator

Enforces financial business rules to prevent AI from proposing
actions that violate accounting logic or create financial risk.
"""

from typing import Dict, Any, Optional, Set
from .base import BaseValidator, ValidationResult


class FinancialValidator(BaseValidator):
    """
    Validates financial operations against business rules.

    Example dangerous actions this blocks:
    - Refunds exceeding original payment
    - Discounts below minimum margin
    - Payments to unverified accounts
    - Price changes that violate constraints
    """

    def __init__(
        self,
        min_margin: float = 0.1,
        max_discount: float = 0.5,
        max_refund_ratio: float = 1.0,
        max_single_transaction: float = 100000.0,
        blocked_action_types: Optional[Set[str]] = None,
        name: Optional[str] = None
    ):
        """
        Args:
            min_margin: Minimum profit margin (0.1 = 10%)
            max_discount: Maximum discount allowed (0.5 = 50%)
            max_refund_ratio: Max refund as ratio of original (1.0 = 100%)
            max_single_transaction: Maximum single transaction amount
            blocked_action_types: Action types to always reject
        """
        super().__init__(name)
        self.min_margin = min_margin
        self.max_discount = max_discount
        self.max_refund_ratio = max_refund_ratio
        self.max_single_transaction = max_single_transaction
        self.blocked_action_types = blocked_action_types or set()

    def validate(
        self,
        action_type: str,
        parameters: Dict[str, Any],
        context: Optional[Any] = None
    ) -> ValidationResult:
        """Validate financial action"""

        # Check blocked actions
        if action_type in self.blocked_action_types:
            return self._reject(
                f"Action type '{action_type}' is blocked",
                risk_level="HIGH"
            )

        # Route to specific validators
        if action_type == "process_refund":
            return self._validate_refund(parameters)
        elif action_type == "update_price":
            return self._validate_price_update(parameters)
        elif action_type == "apply_discount":
            return self._validate_discount(parameters)
        elif action_type == "process_payment":
            return self._validate_payment(parameters)
        elif action_type in ("create_order", "update_order"):
            return self._validate_order(parameters)

        # Unknown action types - approve but flag
        return self._approve(metadata={"warning": "Unknown action type"})

    def _validate_refund(self, params: Dict[str, Any]) -> ValidationResult:
        """Validate refund action"""
        amount = params.get("amount", 0)
        original_amount = params.get("original_amount")

        # Check absolute limit
        if amount > self.max_single_transaction:
            return self._reject(
                f"Refund amount ${amount:,.2f} exceeds maximum ${self.max_single_transaction:,.2f}",
                risk_level="HIGH"
            )

        # Check ratio if original amount provided
        if original_amount is not None and original_amount > 0:
            ratio = amount / original_amount
            if ratio > self.max_refund_ratio:
                return self._reject(
                    f"Refund ratio {ratio:.1%} exceeds maximum {self.max_refund_ratio:.1%}",
                    risk_level="HIGH",
                    metadata={"amount": amount, "original": original_amount}
                )

        # Check for negative refunds (would be a credit)
        if amount < 0:
            return self._reject(
                "Negative refund amount (would credit customer)",
                risk_level="CRITICAL"
            )

        return self._approve()

    def _validate_price_update(self, params: Dict[str, Any]) -> ValidationResult:
        """Validate price change"""
        new_price = params.get("price", params.get("new_price"))
        cost = params.get("cost")

        if new_price is None:
            return self._reject("Price update missing price value", risk_level="MEDIUM")

        if new_price <= 0:
            return self._reject(
                f"Invalid price: ${new_price}",
                risk_level="CRITICAL"
            )

        # Check margin if cost provided
        if cost is not None and cost > 0:
            margin = (new_price - cost) / new_price
            if margin < self.min_margin:
                return self._reject(
                    f"Price ${new_price:,.2f} yields margin {margin:.1%}, below minimum {self.min_margin:.1%}",
                    risk_level="HIGH",
                    metadata={"price": new_price, "cost": cost, "margin": margin}
                )

        return self._approve()

    def _validate_discount(self, params: Dict[str, Any]) -> ValidationResult:
        """Validate discount application"""
        discount = params.get("discount", params.get("discount_percent", 0))

        # Normalize to decimal if percentage
        if discount > 1:
            discount = discount / 100

        if discount > self.max_discount:
            return self._reject(
                f"Discount {discount:.1%} exceeds maximum {self.max_discount:.1%}",
                risk_level="MEDIUM"
            )

        if discount < 0:
            return self._reject(
                "Negative discount (would increase price)",
                risk_level="MEDIUM"
            )

        return self._approve()

    def _validate_payment(self, params: Dict[str, Any]) -> ValidationResult:
        """Validate payment processing"""
        amount = params.get("amount", 0)

        if amount > self.max_single_transaction:
            return self._reject(
                f"Payment ${amount:,.2f} exceeds maximum ${self.max_single_transaction:,.2f}",
                risk_level="HIGH"
            )

        if amount <= 0:
            return self._reject(
                f"Invalid payment amount: ${amount}",
                risk_level="HIGH"
            )

        return self._approve()

    def _validate_order(self, params: Dict[str, Any]) -> ValidationResult:
        """Validate order creation/update"""
        total = params.get("total", params.get("order_total", 0))

        if total > self.max_single_transaction:
            return self._reject(
                f"Order total ${total:,.2f} exceeds maximum ${self.max_single_transaction:,.2f}",
                risk_level="HIGH"
            )

        return self._approve()
