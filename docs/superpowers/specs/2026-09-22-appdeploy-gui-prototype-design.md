# Release Rat AppDeploy GUI Prototype Design

**Date:** 2026-09-22
**Repository:** ClankClub/repo-rat
**Prototype target:** AppDeploy, React + Vite, frontend-only

## Purpose

Build a polished interactive GUI prototype for Release Rat that exposes the product model already present in the codebase: watched repositories, first-run baselines, release judgments, delivery state, run history, and configuration.

The prototype is a product-design surface, not a replacement runtime. It must faithfully model the current Python application without reimplementing GitHub polling, SQLite persistence, Discord delivery, or OpenAI-compatible judgment inside AppDeploy.

Success means a user familiar with Release Rat can immediately recognize how the GUI maps onto the existing CLI/state-machine behavior, while a new user can understand what the rat has seen, what it judged, what it reported, and why.

## Source-grounded product model

The GUI must reflect these real concepts from the repository:

- Release lifecycle states: `seeded`, `pending`, `interesting`, `uninteresting`, and `failed`.
- Delivery is separate from judgment. An interesting release may be delivered through Discord, local JSONL, local fallback, or remain undelivered for retry.
- First normal poll establishes a repository baseline without notifying historical releases.
- Backfill explicitly processes seeded releases.
- Run modes are normal/once, watch, and backfill.
- Run summaries expose fetched, seeded, judged, reported, ignored, errors, and repository errors.
- Repositories come from an explicit configured list plus an optional public starred-repository source.
- LLM judgment is optional; deterministic heuristics remain available as fallback.
- Relevant settings include polling interval, prerelease inclusion, starred username, watched repositories, LLM enablement/model/endpoint, and the presence of GitHub/Discord/model credentials.
- Failures are isolated and retryable where the backend supports it: repository fetch failures do not stop healthy repositories; judgment failures retry; approved undelivered releases are delivered again without being re-judged.

## Product shape

The interface is a hybrid release reader and lightweight operations console.

The default view is an **Inbox** focused on noteworthy releases. Operational detail stays close at hand instead of dominating the first screen.

Primary navigation:

1. **Inbox** — meaningful release feed and release inspection.
2. **Repositories** — configured repositories, starred-source provenance, baseline state, and health.
3. **Runs** — poll history and counts for normal/backfill executions.
4. **Settings** — the real Release Rat configuration represented as an editable prototype form.

No additional product areas should be invented for v1 of the prototype.

## Inbox

The Inbox is the visual center of the app.

It shows release cards/rows with:

- repository
- tag
- release name
- concise saved summary
- publication time
- lifecycle status
- delivery status/channel
- reason or judgment source in secondary metadata

Default filtering emphasizes `interesting` releases, with controls to inspect all statuses.

Selecting a release opens an in-context detail panel rather than navigating away. The detail view shows:

- repository and release identity
- release name/tag
- original release-note excerpt
- saved summary
- saved reason
- lifecycle state
- published / first-seen timestamps
- delivered-at timestamp and channel when available
- a clear explanation when the release is seeded, failed, or awaiting retry

The GUI must visually distinguish "interesting but not yet delivered" from "judgment failed"; those are different recovery paths in the backend.

## Repositories

The Repositories view distinguishes two provenance types:

- **Explicit** — configured directly in `repositories`
- **Starred** — discovered through `starred_username`

A repository row/card includes:

- owner/name
- source
- baseline state
- last known poll state
- latest noteworthy release if available
- error state when applicable

The prototype should make first-run seeding understandable in plain language: a newly monitored repository establishes a quiet baseline before new releases begin generating reports.

## Runs

Runs represent the existing `runs` table and `RunSummary` semantics.

Each run includes:

- mode
- start/finish time
- fetched
- seeded
- judged
- reported
- ignored
- errors
- repository errors

A compact run detail panel may show an error summary and which repositories were affected.

The visual hierarchy should make a successful run with zero reports look normal, not suspicious. "Nothing interesting happened" is a legitimate outcome.

## Settings

Settings mirrors the codebase rather than inventing platform controls.

Editable prototype fields:

- explicit repositories
- starred GitHub username
- poll interval
- include prereleases
- LLM enabled
- model name
- OpenAI-compatible base URL

Credential fields are represented only as presence/status controls:

- GitHub token
- OpenAI-compatible API key
- Discord webhook

The prototype must never display or fabricate secret values.

State path, local log path, and environment-variable-name overrides may appear in an Advanced section because they are real settings but lower-frequency GUI concerns.

Saving settings is a local prototype interaction only. It should visibly confirm the form state changed without claiming to modify the actual GitHub repository, Actions secrets, or Python config.

## Prototype interaction model

This is a frontend-only AppDeploy prototype with deterministic representative data.

The representative dataset should demonstrate:

- delivered interesting release
- undelivered interesting release awaiting retry
- uninteresting release
- seeded release
- failed judgment
- explicit repository
- starred-source repository
- healthy run with no reports
- run with repository-level error
- backfill run

Interactive behavior should include:

- navigation among the four product areas
- release status filtering
- opening/closing release details
- repository source filtering or inspection
- opening run details
- editing/saving settings locally
- responsive behavior at mobile width

No network dependency is required for the prototype.

## Visual design

The interface should feel like serious developer tooling with a distinct Release Rat personality.

Direction:

- dark industrial/control-room shell
- warm off-white reading surfaces where appropriate
- restrained acid-green accent for healthy/active states
- amber/red only for warning/failure semantics
- compact monospace metadata paired with strong sans-serif display/body typography
- dense but readable information hierarchy
- a minimal rat mark or typographic motif created in CSS/text rather than requiring an external asset

Avoid:

- generic SaaS gradient dashboards
- oversized KPI cards
- cartoon mascot treatment
- excessive glassmorphism
- tables as the only information architecture
- visual status colors without text labels

The GUI should feel compact and slightly opinionated, not whimsical.

## Accessibility and responsive behavior

- Status must never rely on color alone.
- Interactive rows/cards must have visible hover/focus states.
- Desktop should support the detail drawer/panel without hiding the feed.
- Mobile should collapse navigation and render details as a full-width sheet/stack.
- Touch targets should remain usable at 375px viewport width.
- Text contrast must remain readable across dark and light surfaces.

## AppDeploy implementation boundaries

- App type: `frontend-only`
- Frontend template: `react-vite`
- No AppDeploy backend or SDK feature is required.
- No authentication, database, realtime, secrets, storage, cron, or AI features are required.
- No user-provided binary resources are required.
- Use the template-provided React/Lucide stack and ordinary local React state.
- SPA navigation should not depend on absolute server routes.

## Test coverage map

The AppDeploy e2e suite should contain 4 independent tests:

1. **Inspect a noteworthy release** — covers Inbox default state, release selection, saved judgment, lifecycle, and delivery metadata.
2. **Inspect seeded/failed operational states** — covers status filtering, seeded baseline explanation, failed judgment distinction, and retry-oriented messaging.
3. **Review repositories and runs** — covers explicit vs starred provenance, repository baseline state, normal run with zero reports, repository-level error, and backfill semantics.
4. **Edit settings on mobile** — covers navigation/responsive layout, real configuration fields, secret-presence representation, local save confirmation, and mobile usability.

Exactly one critical workflow should be marked sanity in AppDeploy's test definition.

## Non-goals

This prototype does not:

- replace or modify Release Rat's Python runtime
- connect directly to GitHub
- read the committed SQLite database
- send Discord messages
- call an LLM
- edit GitHub Actions variables or secrets
- promise multi-user administration
- introduce analytics, billing, authentication, or organization management

Those would be separate product/engineering decisions after the GUI direction is validated.
