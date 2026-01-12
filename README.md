# ERP Agent Safety Harness

A Python safety layer for AI-driven financial operations that treats LLM outputs as untrusted and validates them against deterministic business rules before execution.

## The Problem

When AI agents interact with financial systems (ERPs, payment processors, inventory systems), they can propose actions that are:
- Syntactically valid but semantically dangerous
- Plausible-sounding but violate business constraints
- Individually safe but catastrophic in sequence

**Example dangerous actions an AI might propose:**
```
- Refund an order that was never paid
- Set inventory to negative values
- Modify a closed financial period
- Process a payment to an unverified account
- Update prices below cost threshold
```

These aren't "hallucinations" in the traditional sense—the AI understands the API. But it lacks the business context to know these actions are invalid.

## The Solution: Deterministic Safety Harness

This harness intercepts all AI-proposed operations and validates them against deterministic rules before database commitment.

```
┌─────────────────────────────────────────────────────────────────┐
│                        AI Agent (Claude)                        │
│                    Proposes financial action                    │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      SAFETY HARNESS                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   Schema     │  │   Business   │  │   Sequence   │          │
│  │  Validator   │  │    Rules     │  │   Analyzer   │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │    Rate      │  │  Permission  │  │    Audit     │          │
│  │   Limiter    │  │    Scope     │  │    Logger    │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │  APPROVED? ─────┼──► Execute
                    │                 │
                    │  REJECTED? ─────┼──► Block + Log + Alert
                    └─────────────────┘
```

## Core Principles

### 1. AI as Untrusted Client
The AI is treated like an external API caller—capable but not trusted. Every action requires validation.

### 2. Deterministic Over Probabilistic
Business rules are deterministic (if-then logic), not probabilistic. We don't ask "is this probably safe?"—we check definite constraints.

### 3. Fail Closed
If validation cannot determine safety, the action is blocked. We don't guess.

### 4. Full Auditability
Every proposed action is logged—approved or rejected—with reasoning. This enables post-incident analysis and model improvement.

## Installation

```bash
pip install erp-agent-safety-harness
```

Or from source:
```bash
git clone https://github.com/DennyArcher3/erp-agent-safety-harness.git
cd erp-agent-safety-harness
pip install -e .
```

## Quick Start

```python
from harness import SafetyHarness
from harness.validators import FinancialValidator, InventoryValidator

# Initialize harness with validators
harness = SafetyHarness(
    validators=[
        FinancialValidator(min_margin=0.1, max_discount=0.5),
        InventoryValidator(allow_negative=False),
    ],
    audit_log="./audit.jsonl",
    fail_closed=True
)

# Wrap your AI agent's proposed action
@harness.validate
def process_refund(order_id: str, amount: float, reason: str):
    """AI-proposed refund action"""
    return erp.create_refund(order_id, amount, reason)

# The harness will:
# 1. Validate the refund against business rules
# 2. Check if order exists and was paid
# 3. Verify amount doesn't exceed original payment
# 4. Log the decision
# 5. Execute only if all checks pass
```

## Validators

### Built-in Validators

| Validator | Purpose |
|-----------|---------|
| `SchemaValidator` | Validates action structure and types |
| `FinancialValidator` | Enforces margin, discount, and payment rules |
| `InventoryValidator` | Prevents negative stock, overselling |
| `TemporalValidator` | Blocks actions on closed periods |
| `SequenceValidator` | Detects dangerous action patterns |
| `RateLimiter` | Prevents high-velocity attacks |
| `PermissionScope` | Enforces least-privilege access |

### Custom Validators

```python
from harness.validators import BaseValidator, ValidationResult

class MyValidator(BaseValidator):
    def validate(self, action: dict) -> ValidationResult:
        # Your deterministic logic here
        if action["amount"] > self.max_amount:
            return ValidationResult(
                approved=False,
                reason=f"Amount {action['amount']} exceeds limit {self.max_amount}",
                risk_level="HIGH"
            )
        return ValidationResult(approved=True)
```

## Sequence Analysis

One dangerous action might be safe in isolation but catastrophic in sequence:

```python
# Each action alone seems fine:
actions = [
    {"type": "update_price", "sku": "WIDGET-1", "price": 0.01},
    {"type": "create_order", "sku": "WIDGET-1", "quantity": 10000},
    {"type": "process_payment", "amount": 100.00},
    {"type": "ship_order", "tracking": "..."},
]

# But together: someone just bought $50,000 of inventory for $100
```

The `SequenceValidator` maintains a sliding window and detects these patterns:

```python
from harness.validators import SequenceValidator

seq_validator = SequenceValidator(
    window_size=10,
    patterns=[
        # Price drop followed by large order
        {"sequence": ["update_price", "create_order"], "alert": "PRICE_MANIPULATION"},
        # Multiple refunds in short window
        {"sequence": ["refund", "refund", "refund"], "alert": "REFUND_ABUSE"},
    ]
)
```

## Audit Logging

Every action is logged with full context:

```json
{
  "timestamp": "2026-01-12T14:32:01Z",
  "action_id": "a1b2c3d4",
  "action_type": "process_refund",
  "proposed_by": "claude-agent-7",
  "parameters": {"order_id": "ORD-123", "amount": 150.00},
  "validation_results": [
    {"validator": "FinancialValidator", "approved": true},
    {"validator": "SequenceValidator", "approved": false, "reason": "Third refund in 5 minutes"}
  ],
  "final_decision": "REJECTED",
  "execution_blocked": true
}
```

## Why This Matters for AI Safety

### Current Problem
AI agents are gaining access to real-world systems. As we standardize agentic tool-use (MCP, function calling), AI can execute actions at superhuman speed. A misaligned or jailbroken agent could cause catastrophic damage before human operators notice.

### This Harness Provides
1. **Defense in Depth**: Even if the AI is compromised, deterministic rules block dangerous actions
2. **Speed-Independent Safety**: Rules execute in microseconds, matching AI speed
3. **Human-Auditable Decisions**: Every block has a clear, logged reason
4. **Pattern Detection**: Catches multi-step attacks that look innocent individually

### Research Direction
I believe AI-automated attacks leave detectable signatures in action sequences—burst patterns, unusual error recovery, non-human timing. This harness could be extended to detect these patterns and enable AI-speed defense against AI-speed attacks.

## License

MIT

## Author

Erhan Guclu - [github.com/DennyArcher3](https://github.com/DennyArcher3)

Built with Claude Code assistance, from experience protecting financial systems. The safety concepts and architecture reflect lessons learned from witnessing AI-enabled attacks at scale.

*I use AI to build. I also understand that AI needs safety boundaries. This project demonstrates both.*
