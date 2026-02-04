# V2 Decisions (Approved)

Date: 2026-02-04

## Product/Execution Decisions

1. Prioritize **UI refactor first**.
2. Ingestion/sync runtime can migrate to **Zorin** if it is more efficient.
3. New ingestion automation should run as a **Dockerized service**.
4. Move secrets/config to safer env-based handling; remove hardcoded sensitive values.
5. Deliver a **big-bang UI redesign** while preserving dark mode.
6. Primary UX bar: **easy and intuitive to use**.
7. Add ingestion APIs and UI (new panel/workflow visibility).
8. Deliver as a **new version** with milestone commits and GitHub pushes.

## Implementation Guardrails

- Keep queue/conversion reliability intact while UI is being replaced.
- Validate all major flows with smoke tests before version tagging.
- Push plan state and milestones to GitHub continuously.
