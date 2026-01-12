"""
Basic Usage Example

Demonstrates how to use the ERP Agent Safety Harness to validate
AI-proposed financial operations.
"""

import sys
sys.path.insert(0, '../src')

from harness import SafetyHarness
from validators import (
    FinancialValidator,
    InventoryValidator,
    SequenceValidator,
    TemporalValidator
)
from audit import AuditLogger


def main():
    # Initialize harness with validators
    harness = SafetyHarness(
        validators=[
            FinancialValidator(
                min_margin=0.1,       # 10% minimum margin
                max_discount=0.5,      # 50% maximum discount
                max_single_transaction=50000.0
            ),
            InventoryValidator(
                allow_negative=False,
                max_quantity_change=1000
            ),
            SequenceValidator(
                max_same_action_per_minute=5
            ),
            TemporalValidator(
                closed_periods={"2025-12"},  # December 2025 is closed
                allow_backdating_days=7
            ),
        ],
        audit_logger=AuditLogger(
            log_path="./audit.jsonl",
            log_to_stdout=True
        ),
        fail_closed=True,
        max_actions_per_minute=100
    )

    print("=" * 60)
    print("ERP Agent Safety Harness - Demo")
    print("=" * 60)

    # Example 1: Valid refund
    print("\n1. Testing valid refund...")
    decision = harness.evaluate(
        action_type="process_refund",
        parameters={
            "order_id": "ORD-12345",
            "amount": 150.00,
            "original_amount": 200.00,
            "reason": "Customer request"
        },
        proposed_by="claude-agent"
    )
    print(f"   Approved: {decision.approved}")

    # Example 2: Invalid refund (exceeds original)
    print("\n2. Testing invalid refund (exceeds original)...")
    decision = harness.evaluate(
        action_type="process_refund",
        parameters={
            "order_id": "ORD-12346",
            "amount": 300.00,
            "original_amount": 200.00,
            "reason": "Customer request"
        },
        proposed_by="claude-agent"
    )
    print(f"   Approved: {decision.approved}")
    if not decision.approved:
        print(f"   Blocked by: {decision.blocked_by}")
        print(f"   Reason: {decision.reason}")

    # Example 3: Price below margin
    print("\n3. Testing price below minimum margin...")
    decision = harness.evaluate(
        action_type="update_price",
        parameters={
            "sku": "WIDGET-001",
            "price": 10.00,
            "cost": 9.50  # Only 5% margin
        },
        proposed_by="claude-agent"
    )
    print(f"   Approved: {decision.approved}")
    if not decision.approved:
        print(f"   Blocked by: {decision.blocked_by}")
        print(f"   Reason: {decision.reason}")

    # Example 4: Negative inventory
    print("\n4. Testing negative inventory...")
    decision = harness.evaluate(
        action_type="update_inventory",
        parameters={
            "sku": "WIDGET-001",
            "quantity": -50
        },
        proposed_by="claude-agent"
    )
    print(f"   Approved: {decision.approved}")
    if not decision.approved:
        print(f"   Blocked by: {decision.blocked_by}")
        print(f"   Reason: {decision.reason}")

    # Example 5: Trigger sequence detection (multiple refunds)
    print("\n5. Testing sequence detection (multiple refunds)...")
    for i in range(4):
        decision = harness.evaluate(
            action_type="process_refund",
            parameters={
                "order_id": f"ORD-{1000 + i}",
                "amount": 25.00,
                "original_amount": 50.00
            },
            proposed_by="claude-agent"
        )
        print(f"   Refund {i+1}: Approved={decision.approved}", end="")
        if not decision.approved:
            print(f" - {decision.reason}")
        else:
            print()

    # Print statistics
    print("\n" + "=" * 60)
    print("Audit Statistics:")
    stats = harness.audit_logger.get_statistics()
    print(f"   Total actions: {stats['total']}")
    print(f"   Approved: {stats['approved']}")
    print(f"   Rejected: {stats['rejected']}")
    print(f"   Rejection rate: {stats['rejection_rate']:.1%}")
    print("=" * 60)


if __name__ == "__main__":
    main()
