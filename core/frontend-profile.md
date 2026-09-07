# Frontend Engineering Profile

This is a Design and verification specialization used by the unified `engineering` Skill, not a standalone workflow or command.

RAD belongs before implementation:

- **Read** during Explore: load product behavior, design system, routes, components, API types, state ownership, tests, and accessibility constraints.
- **Analyze** during Explore/Spec: identify user states, permission boundaries, responsive behavior, compatibility, loading/empty/error behavior, and contract risks.
- **Decompose** during Design: follow [Implementation-Ready Design Review](design-review.md); assign component ownership, data/state flow, typed API boundaries, validation, interaction states, accessibility, and implementation order, and make them visible in topology, runtime flow, and responsibility views.

Apply consumes the approved decomposition. Verify type safety, focused behavior tests, accessibility, build output, three-state behavior, and API alignment with commands from `agent-policy.yaml`.
