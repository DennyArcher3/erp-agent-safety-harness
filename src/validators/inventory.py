"""
Inventory Validator

Prevents AI from proposing inventory changes that violate physical
constraints (negative stock, overselling) or business rules.
"""

from typing import Dict, Any, Optional
from .base import BaseValidator, ValidationResult


class InventoryValidator(BaseValidator):
    """
    Validates inventory operations.

    Prevents:
    - Negative inventory levels
    - Overselling (selling more than available)
    - Invalid quantity changes
    - Suspicious bulk operations
    """

    def __init__(
        self,
        allow_negative: bool = False,
        max_quantity_change: int = 10000,
        max_bulk_items: int = 100,
        name: Optional[str] = None
    ):
        """
        Args:
            allow_negative: Allow negative inventory (for backorders)
            max_quantity_change: Maximum single quantity change
            max_bulk_items: Maximum items in a bulk operation
        """
        super().__init__(name)
        self.allow_negative = allow_negative
        self.max_quantity_change = max_quantity_change
        self.max_bulk_items = max_bulk_items

    def validate(
        self,
        action_type: str,
        parameters: Dict[str, Any],
        context: Optional[Any] = None
    ) -> ValidationResult:
        """Validate inventory action"""

        if action_type == "update_inventory":
            return self._validate_inventory_update(parameters)
        elif action_type == "reserve_stock":
            return self._validate_reservation(parameters)
        elif action_type == "bulk_inventory_update":
            return self._validate_bulk_update(parameters)
        elif action_type in ("create_order", "fulfill_order"):
            return self._validate_order_inventory(parameters)

        return self._approve()

    def _validate_inventory_update(self, params: Dict[str, Any]) -> ValidationResult:
        """Validate single inventory update"""
        quantity = params.get("quantity")
        change = params.get("change", params.get("adjustment"))
        current = params.get("current_quantity")

        # Validate absolute quantity
        if quantity is not None:
            if not self.allow_negative and quantity < 0:
                return self._reject(
                    f"Negative inventory not allowed: {quantity}",
                    risk_level="HIGH"
                )

            if abs(quantity) > self.max_quantity_change:
                return self._reject(
                    f"Quantity {quantity} exceeds maximum {self.max_quantity_change}",
                    risk_level="MEDIUM"
                )

        # Validate change amount
        if change is not None:
            if abs(change) > self.max_quantity_change:
                return self._reject(
                    f"Quantity change {change} exceeds maximum {self.max_quantity_change}",
                    risk_level="MEDIUM"
                )

            # Check resulting quantity if current is known
            if current is not None:
                resulting = current + change
                if not self.allow_negative and resulting < 0:
                    return self._reject(
                        f"Change would result in negative inventory: {current} + {change} = {resulting}",
                        risk_level="HIGH"
                    )

        return self._approve()

    def _validate_reservation(self, params: Dict[str, Any]) -> ValidationResult:
        """Validate stock reservation"""
        quantity = params.get("quantity", 0)
        available = params.get("available_quantity")

        if quantity <= 0:
            return self._reject(
                f"Invalid reservation quantity: {quantity}",
                risk_level="MEDIUM"
            )

        if available is not None and quantity > available:
            return self._reject(
                f"Cannot reserve {quantity} units, only {available} available",
                risk_level="HIGH",
                metadata={"requested": quantity, "available": available}
            )

        return self._approve()

    def _validate_bulk_update(self, params: Dict[str, Any]) -> ValidationResult:
        """Validate bulk inventory operation"""
        items = params.get("items", [])

        if len(items) > self.max_bulk_items:
            return self._reject(
                f"Bulk operation has {len(items)} items, maximum is {self.max_bulk_items}",
                risk_level="MEDIUM"
            )

        # Validate each item
        for i, item in enumerate(items):
            result = self._validate_inventory_update(item)
            if not result.approved:
                return self._reject(
                    f"Item {i}: {result.reason}",
                    risk_level=result.risk_level
                )

        return self._approve()

    def _validate_order_inventory(self, params: Dict[str, Any]) -> ValidationResult:
        """Validate inventory for order operations"""
        items = params.get("items", params.get("line_items", []))

        for item in items:
            quantity = item.get("quantity", 0)
            available = item.get("available_quantity")
            sku = item.get("sku", "unknown")

            if quantity <= 0:
                return self._reject(
                    f"Invalid order quantity for {sku}: {quantity}",
                    risk_level="MEDIUM"
                )

            if available is not None and quantity > available:
                return self._reject(
                    f"Insufficient stock for {sku}: need {quantity}, have {available}",
                    risk_level="HIGH"
                )

        return self._approve()
