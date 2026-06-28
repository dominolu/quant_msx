# AGENTS.md

<!-- CODEGRAPH_START -->
## CodeGraph

In repositories indexed by CodeGraph (a `.codegraph/` directory exists at the repo root), reach for it BEFORE grep/find or reading files when you need to understand or locate code:

- **MCP tools** (when available): `codegraph_explore` answers most code questions in one call — the relevant symbols' verbatim source plus the call paths between them. `codegraph_node` returns one symbol's source + callers, or reads a whole file with line numbers. If the tools are listed but deferred, load them by name via tool search.
- **Shell** (always works): `codegraph explore "<symbol names or question>"` and `codegraph node <symbol-or-file>` print the same output.

If there is no `.codegraph/` directory, skip CodeGraph entirely — indexing is the user's decision.
<!-- CODEGRAPH_END -->

## Project Lessons

This is a trading system. Treat "works in simulation" and "safe for live trading" as different standards. New strategy, order, broker, risk, and account changes must be designed around explicit invariants, failure handling, and auditability before happy-path implementation.

## State Machines

- Any object with lifecycle states must be implemented as a state machine, not as free-form string assignment.
- Define allowed transitions before editing code. For grids this means transitions such as `draft -> running`, `running -> paused`, `paused -> running`, and `running/paused/error -> stopped`.
- Reject illegal transitions at the service layer. Do not rely on frontend buttons to prevent invalid actions.
- Add regression tests for invalid transitions, especially restarting stopped strategies, pausing drafts, and duplicate active strategies.

## Order Service Boundary

- All real or simulated trading actions must go through `OrderService`. Strategy code must not call broker REST methods directly.
- `OrderService` is the audit and safety boundary: every intent, response, error, and exchange order id must be persisted.
- Do not fabricate exchange order ids in live mode. If the exchange response lacks a usable order id, mark the submission failed or unknown and block follow-up actions that require a real id.
- Do not collapse exchange-specific status directly into strategy behavior. Normalize order status before strategy code consumes it.

## Failure Handling

- Implement failure paths together with the happy path.
- Multi-order operations, such as starting a grid, must handle partial success. If one order succeeds and a later order fails, attempt compensation such as cancelling already submitted orders.
- Failed cancellation must not mark an order as canceled. Preserve the previous open status and record the cancellation error so the operation can be retried.
- Never swallow exceptions and then write a successful state. If an error is intentionally tolerated, record an event explaining why the state is still safe.

## Live Trading Safety

- Default to simulation. Live trading must remain behind `settings.live_trading_enabled`.
- Live order submission requires a real account, valid credentials, valid finite numeric values, and a validated symbol.
- Fields such as `reduce_only`, order side, market type, and order type must map explicitly to the exchange request. Do not define request fields that are ignored by the live path.
- Strategy stop, risk reduction, and flattening flows must use reduce-only or close-position semantics where the exchange supports them.

## Validation

- Service-layer validation is the security boundary. Frontend validation is only user experience.
- Reject invalid symbols, negative quantities, zero quantities, non-finite numbers, invalid leverage, unsupported markets, unsupported order types, overlong client ids, and overlong source labels.
- Treat external API responses as untrusted. Validate required fields before persisting state that depends on them.

## Testing Standard

- Each bug found in review should produce a regression test.
- Cover happy path, invalid input, invalid state transitions, external API failure, partial success, and retry behavior.
- For order and strategy code, tests should assert both persisted records and returned API views.
- Before commit, run focused tests plus compile and diff checks:
  - `.venv/bin/python -m pytest tests/test_grid_management.py tests/test_account_management.py tests/test_broker_contracts.py`
  - `.venv/bin/python -m compileall app tests -q`
  - `git diff --check`

## Review Checklist

Before marking a trading feature complete, verify:

- The service has explicit invariants and allowed state transitions.
- The live path cannot execute unless the live trading switch is enabled.
- Any multi-step operation has compensation or a safe error state.
- Persistence reflects the real outcome, not the intended outcome.
- All external identifiers used for follow-up actions come from the exchange, not local fallbacks.
- Tests include failure cases, not only lifecycle success cases.

