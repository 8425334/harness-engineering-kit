# coil-backend-api SDD Adaptation

The project uses the OpenSpec-native change layout and lifecycle. OpenSpec `tasks.md` is the sole dependency-ordered task list; Engineering records matching execution evidence:

1. Shared domain/API contract
2. Domain and application behavior
3. Infrastructure and persistence adapters
4. HTTP/event adapters and authorization
5. Migration and compatibility work
6. Frontend types, API layer, state, and components when applicable
7. Focused tests, project gates, and integration verification
8. Spec sync and archive

Independent tasks may share an execution wave only when their write scopes are disjoint. After each verified task the coordinator records completion through Harness, which automatically checks its OpenSpec task. The coordinator integrates results and reruns the project gates; platforms without safe concurrent workers execute the same graph sequentially and record the fallback.

Changing fields, errors, permissions, precision, task dependencies/scopes, or compatibility after approval invalidates the contract and returns the change to Propose.
