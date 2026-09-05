# Requirement Reflection and Clarification

Requirement Reflection is the response-level quality gate. After drafting a task response, but before sending it or taking a side effect, the Agent checks whether it understood the user's goal well enough to act. This is a conclusion check, not a request to expose private chain-of-thought.

## Decision

Use the following outcomes:

| Outcome | Condition | Agent action |
|---|---|---|
| `ready` | Goal, scope, success criteria, constraints, and authority are sufficiently clear | State material assumptions, answer, and proceed only within the authorized scope |
| `clarify` | An ambiguity could change the implementation, result, cost, safety, or verification | Stop writes and external side effects; ask focused questions and provide a recommended option |
| `correct` | The request conflicts with repository evidence, a declared constraint, or a technical invariant | Show the evidence and conflict; propose the smallest viable correction; ask for confirmation before adopting it |
| `blocked` | The action needs missing authorization, unavailable evidence, or an unsafe decision | Explain the blocker, identify the owner or evidence needed, and provide the safest next plan |

Do not silently choose between materially different interpretations. A reversible explanation may include clearly labeled alternatives, but an implementation or other consequential action waits for confirmation whenever the ambiguity affects its outcome.

## Reflection checklist

Check the draft against:

- **Intent**: What outcome does the user want, for whom, and why?
- **Scope**: Which files, systems, users, environments, and exclusions are included?
- **Acceptance**: What observable result would make the work correct or complete?
- **Constraints**: Which technology, compatibility, security, data, time, or process constraints apply?
- **Evidence**: Which facts come from the repository or tools, and which are assumptions?
- **Consistency**: Does the request conflict with existing contracts, policy, dependencies, or physical feasibility?
- **Authority and risk**: Is the Agent authorized to perform the requested operation, and could it cause an irreversible or high-impact change?

The Agent does not need to ask about every missing detail. Ask only about details that can change the plan, behavior, safety, or completion claim. Group related questions and ask no more than three blocking questions in one response when possible.

## Clarification response

When the outcome is `clarify`, `correct`, or `blocked`, use this order:

1. **Current understanding** — summarize the intended outcome in one or two sentences.
2. **Finding** — name the ambiguity, conflict, missing authorization, or evidence gap precisely.
3. **Evidence** — cite the relevant repository fact, constraint, or unknown; do not present an assumption as fact.
4. **Recommendation** — give the best option, its trade-off, and a short executable plan.
5. **Confirmation** — ask the smallest question that lets the user choose or confirm the recommendation.

Until confirmation arrives, do not present the recommended interpretation as approved, modify consequential files, or claim completion. If the user confirms a changed requirement, update the task plan and run this reflection again before continuing.

## Clear response

For `ready`, briefly state the requirement, any material assumptions, the plan, and the verification approach. Then answer or act within the confirmed scope. If later evidence invalidates the interpretation, return to `correct` or `blocked` instead of defending the earlier answer.

## Relationship to Self-Refine

Requirement Reflection checks whether the Agent should act or ask the user. Self-Refine checks the quality of a draft, design, or implementation after the scope is understood. They share the same bounded feedback principle, but neither one approves a contract, replaces deterministic gates, or authorizes protected and production changes.
