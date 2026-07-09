# frontend-architecture.md — coil-backend-api Adaptation

This project's Vue 3 + Soybean Admin frontend partially implements the methodology:

- **Contract-first**: API calls must go through `src/service/api/coil/` — direct use of low-level request utilities in views/components is prohibited (corresponds to "Architecture Boundary Contract").
- **Domain types**: Each domain has a dedicated API file (e.g., `driver.ts`, `in-authorization-letter.ts`), equivalent to the `infrastructure/api/` layer.
- **VibeCoding complement**: This project's frontend uses VibeCoding (PACE routing + RIPER-7 phases), complementing AIDM in "abstraction-first / boundary contract / FDD" layers. See `.vibe/methodology.md`.
- **Fitness integration point**: Frontend `console.log` cleanup and ESLint boundary rules can plug into `docs/fitness/scripts/fitness.py`'s check chain.
