# Release Rat AppDeploy GUI Prototype Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and deploy a polished frontend-only AppDeploy prototype that exposes Release Rat's existing state machine as a release inbox and lightweight operations console.

**Architecture:** Use the AppDeploy React/Vite scaffold, deterministic local fixtures, and React state only. The app has four views—Inbox, Repositories, Runs, Settings—with release/run detail panels and no network or backend dependency.

**Tech Stack:** React 19, TypeScript, Vite 6, Lucide React, custom CSS/Tailwind baseline, AppDeploy E2E QA.

**Spec:** `docs/superpowers/specs/2026-09-22-appdeploy-gui-prototype-design.md`

## Global Constraints

- `frontend-only` + `react-vite`.
- No AppDeploy SDK, backend, auth, database, realtime, storage, secrets, cron, or AI.
- No live GitHub/SQLite/Discord/model calls.
- Status is always textual as well as colored.
- Never display/fabricate credential values.
- Settings save locally and explicitly say they are prototype-only.
- Distinguish `interesting` + undelivered from `failed` judgment.
- Represent explicit vs starred repository provenance.
- Explain quiet first-run seeding and explicit backfill.
- Exactly one AppDeploy test has `sanity: true`.

## Review Focus

- Undelivered interesting releases read as delivery retry state, not failed judgment.
- Seeded releases explain notification suppression and backfill.
- Successful zero-report runs read as healthy.
- Credentials are status-only.
- Mobile 375px preserves navigation, forms, filters, and detail content.

---

### Task 1: Define the behavioral contract and fixtures

**Files:**
- Create in AppDeploy: `src/types.ts`
- Create in AppDeploy: `src/data.ts`
- Replace in AppDeploy: `tests/tests.json`

**Interfaces:**
- Produces: `ReleaseRecord`, `RepositoryRecord`, `RunRecord`, `SettingsState`.
- Produces representative records for delivered interesting, retrying interesting, uninteresting, seeded, failed judgment, explicit/starred repositories, quiet normal run, repository-error run, and backfill run.

- [ ] **Step 1: Write the E2E behavioral tests before product UI code**

Use exactly this `tests/tests.json`:

```json
[
  {
    "name": "Inspect a noteworthy release",
    "sanity": true,
    "viewport": "desktop",
    "covers": [
      "Inbox default interesting filter",
      "release detail selection",
      "saved judgment summary and reason",
      "release lifecycle status",
      "delivery channel metadata"
    ],
    "description": "Verifies the default Inbox centers noteworthy releases and exposes the persisted judgment and delivery state.",
    "steps": [
      "Open the Inbox and select the astral-sh/uv 0.9.6 release",
      "Inspect the release detail panel",
      "Read the judgment and delivery sections"
    ],
    "expected": "The release is labeled interesting, shows its saved summary and reason, and shows that it was delivered through Discord."
  },
  {
    "name": "Distinguish seeded, failed, and retrying states",
    "viewport": "desktop",
    "covers": [
      "release status filtering",
      "seeded baseline explanation",
      "failed judgment explanation",
      "interesting undelivered retry state"
    ],
    "description": "Verifies operational states that have different recovery semantics are explained distinctly.",
    "steps": [
      "Change the Inbox filter from Interesting to All",
      "Open the vitejs/vite seeded release and read its state explanation",
      "Open the acme/tool failed release, then open the python/cpython interesting undelivered release"
    ],
    "expected": "Seeded explains the quiet baseline/backfill behavior, failed explains judgment retry, and the undelivered interesting release explains delivery retry without calling the judgment failed."
  },
  {
    "name": "Review repository provenance and run outcomes",
    "viewport": "desktop",
    "covers": [
      "explicit repository provenance",
      "starred repository provenance",
      "repository baseline state",
      "healthy normal run with zero reports",
      "repository-level error isolation",
      "backfill run semantics"
    ],
    "description": "Verifies the operations views reflect repository sources and real Release Rat run semantics.",
    "steps": [
      "Open Repositories and inspect one Explicit repository and one Starred repository",
      "Open Runs and inspect the newest quiet normal run",
      "Inspect the run containing a repository error and the Backfill run"
    ],
    "expected": "Repository source and baseline state are visible; the zero-report run is healthy; the error run identifies an isolated repository failure; and Backfill is explained as processing seeded history."
  },
  {
    "name": "Edit prototype settings on mobile",
    "viewport": "mobile",
    "covers": [
      "responsive navigation",
      "repository configuration editing",
      "poll interval editing",
      "prerelease and LLM toggles",
      "credential presence status",
      "prototype-only settings save"
    ],
    "description": "Verifies real Release Rat settings remain usable on mobile without exposing secret values or implying a real configuration write.",
    "steps": [
      "Open Settings using the mobile navigation",
      "Change the poll interval and toggle Include prereleases",
      "Save settings and inspect the credential status section"
    ],
    "expected": "A visible confirmation says the prototype settings were saved locally, and credentials are shown only as configured/not configured status without secret values."
  }
]
```

Expected RED: these workflows cannot pass before the AppDeploy product UI exists. AppDeploy cannot execute browser QA until an initial deployment exists, so the actual pre-implementation RED execution is unavailable; this limitation must be recorded in the execution ledger.

- [ ] **Step 2: Create the type contract**

Create `src/types.ts` with:

```ts
export type ReleaseStatus = 'seeded' | 'pending' | 'interesting' | 'uninteresting' | 'failed';
export type DeliveryChannel = 'discord' | 'local' | 'local-fallback' | null;
export type RepositorySource = 'explicit' | 'starred';
export type RunMode = 'normal' | 'backfill';

export interface ReleaseRecord {
    id: string;
    repository: string;
    releaseId: string;
    tagName: string;
    name: string;
    bodyExcerpt: string;
    htmlUrl: string;
    publishedAt: string | null;
    firstSeenAt: string;
    status: ReleaseStatus;
    summary: string | null;
    reason: string | null;
    deliveredAt: string | null;
    deliveredVia: DeliveryChannel;
    judgmentSource: 'llm' | 'heuristic' | null;
}

export interface RepositoryRecord {
    name: string;
    source: RepositorySource;
    baselineEstablished: boolean;
    lastPollStatus: 'healthy' | 'error';
    latestInterestingRelease: string | null;
    errorMessage: string | null;
}

export interface RunRecord {
    id: string;
    mode: RunMode;
    startedAt: string;
    finishedAt: string;
    fetched: number;
    seeded: number;
    judged: number;
    reported: number;
    ignored: number;
    errors: number;
    repositoryErrors: number;
    errorText: string | null;
}

export interface SettingsState {
    repositories: string[];
    starredUsername: string;
    pollIntervalSeconds: number;
    includePrereleases: boolean;
    llmEnabled: boolean;
    model: string;
    baseUrl: string;
    githubTokenConfigured: boolean;
    openAiKeyConfigured: boolean;
    discordWebhookConfigured: boolean;
    statePath: string;
    localLogPath: string;
}
```

- [ ] **Step 3: Create deterministic fixture data**

Create `src/data.ts` using fixed 2026 timestamps and these required records:
- `astral-sh/uv 0.9.6`: interesting, LLM judgment, delivered via Discord.
- `python/cpython v3.14.1`: interesting, heuristic judgment, delivery fields null; reason indicates security.
- `astral-sh/ruff 0.13.2`: uninteresting documentation-only release.
- `vitejs/vite v8.0.0`: seeded with no judgment.
- `acme/tool v4.2.0`: failed with no summary and reason `LLM request failed; judgment will retry.`.
- Repositories: at least two explicit, two starred; one starred repository has a GitHub HTTP 503 error.
- Runs: latest healthy normal run with `reported: 0`; normal run with one repository error; backfill run that reports one seeded release.
- Initial settings: explicit repositories, `starredUsername: 'silascroe'`, `pollIntervalSeconds: 3600`, prereleases false, LLM enabled, model `gpt-5-mini`, base URL `https://api.openai.com/v1`, GitHub token true, OpenAI key true, Discord webhook true, paths `state.db` and `release-log.jsonl`.

- [ ] **Step 4: Verify contract consistency**

Check that every `covers` entry maps to data or UI behavior represented in Tasks 1–2 and no fixture invents a backend state absent from Release Rat.

Expected: every required spec state has one deterministic record.

---

### Task 2: Build the four-view React prototype

**Files:**
- Modify AppDeploy scaffold: `index.html`
- Modify AppDeploy scaffold: `src/App.tsx`
- Modify AppDeploy scaffold: `src/index.css`
- Consume: `src/types.ts`, `src/data.ts`

**Interfaces:**
- Consumes all Task 1 fixtures/types.
- Produces user-visible navigation, filters, detail panels, repository/run inspection, responsive settings form, and local save confirmation.

- [ ] **Step 1: Set product title**

Replace `APP_TITLE` in `index.html` with `Release Rat — Signal Console`.

- [ ] **Step 2: Implement App state and view switching**

`src/App.tsx` must own:

```ts
type View = 'inbox' | 'repositories' | 'runs' | 'settings';
type ReleaseFilter = 'interesting' | 'all' | ReleaseStatus;

const [view, setView] = useState<View>('inbox');
const [releaseFilter, setReleaseFilter] = useState<ReleaseFilter>('interesting');
const [selectedReleaseId, setSelectedReleaseId] = useState<string | null>(releases[0]?.id ?? null);
const [selectedRunId, setSelectedRunId] = useState<string | null>(runs[0]?.id ?? null);
const [settings, setSettings] = useState<SettingsState>(initialSettings);
const [saved, setSaved] = useState(false);
```

Navigation labels are exactly `Inbox`, `Repositories`, `Runs`, `Settings`.

- [ ] **Step 3: Implement Inbox and release detail behavior**

Inbox requirements:
- header copy: `GitHub releases in. Signal out.`
- default filter `Interesting`
- filter choices: Interesting, All, Seeded, Pending, Uninteresting, Failed
- each row exposes repository, tag, name, summary/fallback copy, publication time, textual lifecycle badge, and delivery state
- clicking a release updates the adjacent detail panel on desktop and stacked detail section on mobile

State explanations:
- interesting + delivered: `Judgment saved. Delivery complete.`
- interesting + not delivered: `Judgment saved. Delivery is still pending and can retry without another model call.`
- seeded: `Quiet baseline: this release existed when monitoring began. Use Backfill to process seeded history explicitly.`
- failed: `Judgment failed. Release Rat will retry the judgment on a later poll.`
- uninteresting: `Judged and intentionally ignored.`
- pending: `Fetched and waiting for judgment.`

Detail panel must show summary, reason, judgment source, published/first-seen timestamps, delivery channel/time, release ID, and release-note excerpt.

- [ ] **Step 4: Implement Repositories**

Each repository card exposes:
- exact repository name
- `Explicit` or `Starred` source badge
- `Baseline established` / `Baseline pending`
- healthy/error poll state
- latest noteworthy release when present
- error text when present

Include this explanatory panel:
`New repositories establish a quiet baseline on their first successful normal poll. Existing releases are remembered but not reported unless you deliberately run Backfill.`

- [ ] **Step 5: Implement Runs and run detail**

Each run row exposes:
- `Normal poll` or `Backfill`
- started/finished time
- fetched, judged, reported, ignored, errors
- healthy/error status

A healthy `reported: 0` run must say `Quiet run — everything checked, nothing worth reporting.`

Backfill detail must say `Backfill includes releases previously marked seeded by the first normal poll.`

Error runs show `repositoryErrors` and `errorText`, with copy explaining healthy repositories still complete.

- [ ] **Step 6: Implement Settings**

Settings controls:
- repositories textarea, one `owner/name` per line
- starred username
- poll interval seconds number input
- include prereleases checkbox/switch
- LLM enabled checkbox/switch
- model
- OpenAI-compatible base URL
- Advanced disclosure with state path and local log path
- credential status cards for GitHub token, model API key, Discord webhook

Credential UI says only `Configured` or `Not configured`.

Save action:
- updates local state from the form
- sets `saved=true`
- renders `Prototype settings saved locally. No GitHub, Actions, or Release Rat configuration was changed.`

- [ ] **Step 7: Apply visual system and responsive behavior**

`src/index.css` must define:
- dark charcoal shell and left rail
- warm paper-like content cards
- acid green only for healthy/active emphasis
- amber/red warning and failure semantics
- sans body + system monospace metadata
- compact radius, borders, restrained shadows
- clear hover/focus-visible states
- desktop two-column Inbox with sticky detail panel
- under ~760px: compact top/mobile navigation, single-column content, detail stacked full width, full-width form controls, >=44px primary touch targets
- no gradients, glassmorphism, mascot illustration, or oversized KPI tiles

- [ ] **Step 8: Run AppDeploy build/validation through deployment**

Expected: no TypeScript, lint, template, or validation errors.

---

### Task 3: Deploy, QA, inspect, and repair

**Files:**
- AppDeploy remote snapshot only; update changed files with diffs if QA finds defects.

**Interfaces:**
- Consumes the four E2E tests from Task 1.
- Produces a public AppDeploy URL with terminal `ready` status and reviewed QA/runtime output.

- [ ] **Step 1: Preflight AppDeploy payload**

Confirm:
- new app has `app_id: null`, `frontend_template: 'react-vite'`, `app_type: 'frontend-only'`
- title placeholder replaced
- App content placeholder replaced
- only new files plus diffs to scaffold files plus full `tests/tests.json`
- no SDK imports
- exactly four tests, exactly one sanity test
- every material spec capability appears in a `covers` array
- no binary resources/secrets

- [ ] **Step 2: Deploy**

Call AppDeploy with:
- app name `Release Rat — Signal Console`
- description `Interactive GUI prototype for Release Rat's release inbox, repository baselines, run history, and configuration.`
- model `gpt-5.6-sol`
- intent `initial Release Rat GUI prototype deploy`
- initiator `user`
- type `feature`

- [ ] **Step 3: Poll to terminal status**

Call `get_app_status` at least 5 seconds apart until `ready`, `failed`, or `deleted`.

Expected: `ready`.

- [ ] **Step 4: Treat QA/runtime evidence as authoritative**

If E2E fails:
1. call `get_e2e_qa_run_details`
2. inspect remote files with `src_read/src_grep/src_glob`
3. load `superpowers:systematic-debugging`
4. fix the root cause with an AppDeploy update
5. poll again

Attempt up to three automatic repair deployments.

- [ ] **Step 5: Final verification**

Freshly inspect `get_app_status` and verify:
- deployment status `ready`
- E2E result has no failing tests
- frontend/backend runtime error logs contain no unresolved errors
- QA snapshot is consistent with the four-view design

Only after those checks report the public URL as complete.

## Execution Ruling

AppDeploy browser E2E QA cannot run before an app deployment exists. The tests are therefore authored before UI code as the behavioral contract, but the literal TDD RED browser run is unavailable for the first deployment. The first executable QA run occurs immediately after deployment, and any defect found there must follow RED→fix→GREEN using the failing QA evidence before the repair.
