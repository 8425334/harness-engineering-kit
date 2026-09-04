# coil-backend-api SDD Adaptation

The project uses the canonical change artifact layout and lifecycle. Its `tasks.md` normally follows dependency order:

1. Shared domain/API contract
2. Domain and application behavior
3. Infrastructure and persistence adapters
4. HTTP/event adapters and authorization
5. Migration and compatibility work
6. Frontend types, API layer, state, and components when applicable
7. Focused tests, project gates, and integration verification
8. Spec sync and archive

Changing fields, errors, permissions, precision, or compatibility after approval invalidates the contract and returns the change to Propose.
