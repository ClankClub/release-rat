# Repo Rat GitHub Pages Site Design

**Date:** 2026-09-22

**Status:** Proposed for review

## Purpose

Give Repo Rat a welcoming, visual public front door that explains the project and helps visitors decide whether and how to use it. The README remains the repository's detailed reference; the site makes the same project easier to scan and understand.

The audience is a GitHub user who has discovered Repo Rat and wants to know what it does, what a notification looks like, and what setup entails before forking it.

## Goals

- Explain the release-monitoring flow visually and in plain language.
- Show an accurate example of a single Discord report.
- Guide a new user through GitHub Actions setup, including the webhook secret and optional starred-repository variable.
- Make the first-run baseline and the potentially noisy historical backfill behavior unmistakable.
- Be readable on phones and desktops and consistent with Repo Rat's existing visual identity.
- Require no JavaScript, runtime service, analytics, or third-party frontend dependency.

## Non-goals

- A live dashboard, configuration editor, webhook tester, or hosted monitoring service.
- Accounts, user data collection, analytics, or any access to visitors' GitHub/Discord credentials.
- Replacing the README, architecture document, or issue tracker.
- Redesigning Repo Rat's polling, filtering, delivery, or persistence behavior.

## Approaches considered

1. **Plain static site in `docs/` (selected).** A small HTML/CSS site, deployed with GitHub Pages Actions. It is easy to maintain, has no build toolchain, and gives the layout the visual freedom requested.
2. **Jekyll or another documentation generator.** Useful if the project grows into many pages, but currently adds templates and configuration without solving a present need.
3. **Separate hosted frontend.** Could become a richer product UI, but would split the public project experience across services and is unnecessary for a project overview and setup guide.

## Site structure and content

The initial site is a single responsive page at `docs/index.html`, with styles in `docs/site.css` and existing SVG assets reused where appropriate.

1. **Hero:** Repo Rat name, the existing concise project promise, and clear links to the repository and setup section.
2. **What it does:** A short explanation of watching public GitHub releases, filtering for noteworthy changes, remembering processed releases, and delivering reports to Discord or a local log.
3. **Example report:** Reuse the existing illustrative report graphic, clearly labeled as an example. Its text and links must match the actual one-release Discord message format.
4. **How it works:** Reuse the existing pipeline graphic and explain GitHub → SQLite state → significance judgment → Discord/JSONL.
5. **Getting started:** A short Actions setup sequence: fork the repo, add `DISCORD_WEBHOOK_URL` as a secret, optionally set `REPO_RAT_STARRED_USERNAME` as a variable, enable Actions, and let the first normal poll seed a quiet baseline.
6. **Backfill warning:** Explicitly explain that backfill processes previously seeded history and may send many messages; recommend leaving it off for ordinary setup. Mention that Discord may expand GitHub links into previews.
7. **Configuration and transparency:** Link to the README and architecture reference for explicit repository lists, public starred repositories, optional model configuration, and state behavior. State that the workflow handles public release/star data and that secrets are not stored in the checked-in state database.
8. **Footer:** Links to source, issues, license, and architecture documentation.

The page should not duplicate every CLI option or every internal detail already documented in the README and `docs/architecture.md`.

## Visual and accessibility direction

- Preserve Repo Rat's existing dark GitHub-inspired palette, amber accent, wordmark/banner, and compact technical character.
- Use a strong type hierarchy, generous spacing, a narrow readable text measure, and a clear setup callout; avoid a dashboard-like grid of decorative cards.
- Use semantic landmarks and headings, descriptive link text, useful image alternatives, keyboard-visible focus, and sufficient text contrast.
- Use responsive CSS and no motion-dependent interaction.

## Deployment and boundaries

- Add a dedicated Pages deployment workflow that publishes the static `docs/` artifact on changes to the site or deployment workflow, with manual dispatch available for recovery.
- Use GitHub's Pages artifact/deployment flow; do not couple site deployment to the hourly Repo Rat polling workflow or its secrets/state writes.
- The repository's Pages source must be set to GitHub Actions. If that setting needs an owner-level change, pause and ask the user to make or authorize it.
- After a published URL is verified, add a small `Project site` link in the README. Until then, do not add a guessed URL.
- Do not publish the Pages site until the user approves this written design and the implementation plan.

## Validation

- Check HTML structure, local asset and navigation paths, accessibility basics, and responsive layout.
- Build/deploy the Pages artifact in an isolated preview or workflow run before considering publication complete.
- Verify the published page and its asset links at the actual GitHub Pages URL.
- Run the existing Python test suite to confirm the static site work did not affect runtime behavior.

## Self-review

- Scope is limited to a single static landing/setup page and its isolated deployment path.
- The design keeps the sensitive webhook URL out of page content and avoids introducing browser-side secrets or telemetry.
- Backfill's real notification impact is prominent, reflecting the current workflow's manual backfill option.
- Existing visuals and docs are reused rather than creating a parallel explanation of internals.
