# Repo Rat GitHub Pages Site Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add and publish a lightweight, accessible GitHub Pages landing/setup page for Repo Rat.

**Architecture:** Serve one hand-authored HTML page and stylesheet from `docs/`, reusing the current SVG assets and adding no frontend build system or browser-side code. A separate, least-privilege GitHub Actions workflow will stage only the page, stylesheet, and required SVGs as a Pages artifact and deploy them; the existing poll workflow remains untouched.

**Tech Stack:** HTML5, CSS, Python standard-library `unittest`/`html.parser`, and the official [Pages artifact](https://github.com/actions/upload-pages-artifact) and [Pages deployment](https://github.com/actions/deploy-pages) actions (`actions/upload-pages-artifact@v5`, `actions/deploy-pages@v4`).

**Spec:** [2026-09-22-repo-rat-pages-design.md](../specs/2026-09-22-repo-rat-pages-design.md)

## Global Constraints

- Require no JavaScript, runtime service, analytics, or third-party frontend dependency.
- The initial site is a single responsive page at `docs/index.html`, with styles in `docs/site.css` and existing SVG assets reused where appropriate.
- Preserve Repo Rat's existing dark GitHub-inspired palette, amber accent, wordmark/banner, and compact technical character.
- Do not introduce a live dashboard, configuration editor, webhook tester, accounts, visitor data collection, or a hosted monitoring service.
- Keep the `DISCORD_WEBHOOK_URL` secret out of page content; describe `REPO_RAT_STARRED_USERNAME` as an optional Actions variable.
- Explain that a normal first poll seeds a quiet baseline and backfill may send many messages; recommend leaving backfill off for ordinary setup.
- Do not change Repo Rat's polling, filtering, delivery, or persistence behavior, or couple Pages deployment to the hourly poll workflow.
- Keep the README as the detailed reference and add a site link only after the published URL is verified.
- Before implementation, do not use the current dirty checkout as the implementation workspace. It contains unrelated rebrand/setup changes and local commits. Follow `superpowers:using-git-worktrees` at execution time to create an isolated worktree from the verified latest `origin/main`; preserve the existing checkout and never push its unrelated changes as part of this work.

## Review Focus

- **Missing local SVG/CSS target:** every relative `href`/`src` resolves from `docs/`; cover with `test_local_links_and_assets_resolve` in Task 1.
- **Broken fragment navigation:** every in-page fragment points to a unique element ID; cover with `test_fragment_links_have_unique_targets` in Task 1.
- **Backfill/setup copy hides a consequential action:** the page explicitly says backfill may send many messages, Discord can expand GitHub links, first normal polling seeds history, and the model/API key is optional; cover with `test_setup_and_backfill_copy_is_explicit` in Task 1.
- **Mobile layout clips content or controls:** check the rendered page at 360px, 768px, and 1280px widths for horizontal overflow, readable measure, and usable navigation in Task 2.
- **Keyboard users cannot see their position:** tab through all links at desktop and mobile widths and verify visible focus and adequate contrast in Task 2.

---

## File Map

- Create `docs/index.html`: semantic content, page metadata, headings, navigation, example report, setup steps, and links.
- Create `docs/site.css`: initial local stylesheet in Task 1, then responsive visual system and focus states in Task 2.
- Reuse, without editing, `docs/assets/repo-rat-banner.svg`, `docs/assets/report-preview.svg`, and `docs/assets/pipeline.svg`.
- Create `tests/test_site.py`: standard-library checks for document structure, accessibility essentials, copy requirements, and local links/assets.
- Create `.github/workflows/pages.yml`: isolated static artifact upload and Pages deployment.
- Modify `README.md` only after deployment returns a verified public URL; add one `Project site` link.
- Do not modify `.github/workflows/repo-rat.yml` or `repo_rat/`.
- Do not modify `.github/workflows/ci.yml`; its existing `python -m unittest discover -s tests -v` step automatically discovers `tests/test_site.py`.

## Task 1: Add the landing page and its content contract

**Files:**
- Create: `tests/test_site.py`
- Create: `docs/index.html`
- Create: `docs/site.css` (minimal local stylesheet, expanded in Task 2)
- Reuse: `docs/assets/repo-rat-banner.svg`, `docs/assets/report-preview.svg`, `docs/assets/pipeline.svg`

**Interfaces:**
- Produces the stable anchors `#how-it-works`, `#setup`, and `#backfill-warning` for in-page links.
- Uses relative links for local assets and the local stylesheet; links to repository documentation use canonical GitHub URLs because the Pages artifact contains only the site files.

- [ ] **Step 1: Write the failing site-contract tests**

Create `tests/test_site.py` with a small `HTMLParser` collector and these assertions:

```python
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit
import unittest


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
PAGE = DOCS / "index.html"


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.hrefs = []
        self.sources = []
        self.images_missing_alt = []
        self.headings_one = 0
        self.landmarks = set()
        self.scripts = 0
        self.text = []
        self.lang = None
        self.title_depth = 0
        self.title = []
        self.description = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get("id"):
            self.ids.append(attrs["id"])
        if tag == "html":
            self.lang = attrs.get("lang")
        if tag in {"header", "nav", "main", "footer"}:
            self.landmarks.add(tag)
        if tag == "h1":
            self.headings_one += 1
        if tag == "title":
            self.title_depth += 1
        if tag == "meta" and attrs.get("name", "").lower() == "description":
            self.description = attrs.get("content")
        if tag == "a" and attrs.get("href"):
            self.hrefs.append(attrs["href"])
        if tag == "img":
            if attrs.get("src"):
                self.sources.append(attrs["src"])
            if "alt" not in attrs:
                self.images_missing_alt.append(attrs.get("src", "<missing src>"))
        if tag == "link" and attrs.get("href"):
            self.hrefs.append(attrs["href"])
        if tag == "script":
            self.scripts += 1

    def handle_endtag(self, tag):
        if tag == "title":
            self.title_depth = max(0, self.title_depth - 1)

    def handle_data(self, data):
        self.text.append(data)
        if self.title_depth:
            self.title.append(data)


class RepoRatSiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = PAGE.read_text(encoding="utf-8")
        cls.page = PageParser()
        cls.page.feed(cls.html)

    def test_document_has_language_title_description_and_landmarks(self):
        self.assertEqual(self.page.lang, "en")
        self.assertTrue("".join(self.page.title).strip())
        self.assertTrue(self.page.description)
        self.assertEqual(self.page.headings_one, 1)
        self.assertTrue({"header", "nav", "main", "footer"} <= self.page.landmarks)

    def test_images_have_alt_text_and_local_assets_exist(self):
        self.assertEqual(self.page.images_missing_alt, [])
        for source in self.page.sources:
            parsed = urlsplit(source)
            self.assertFalse(parsed.scheme or parsed.netloc, source)
            self.assertTrue((DOCS / parsed.path).is_file(), source)

    def test_local_links_and_assets_resolve(self):
        for target in [*self.page.hrefs, *self.page.sources]:
            parsed = urlsplit(target)
            if parsed.scheme or parsed.netloc:
                continue
            if parsed.fragment and not parsed.path:
                self.assertEqual(self.page.ids.count(parsed.fragment), 1, target)
            elif parsed.path:
                self.assertTrue((DOCS / parsed.path).resolve().is_file(), target)
                if parsed.fragment and parsed.path.endswith(".html"):
                    linked = PageParser()
                    linked.feed((DOCS / parsed.path).read_text(encoding="utf-8"))
                    self.assertIn(parsed.fragment, linked.ids, target)

    def test_fragment_links_have_unique_targets(self):
        self.assertEqual(len(self.page.ids), len(set(self.page.ids)))
        for anchor in ("how-it-works", "setup", "backfill-warning"):
            self.assertEqual(self.page.ids.count(anchor), 1)
            self.assertIn(f"#{anchor}", self.page.hrefs)

    def test_footer_uses_canonical_github_links(self):
        expected = {
            "https://github.com/ClankClub/repo-rat",
            "https://github.com/ClankClub/repo-rat/issues",
            "https://github.com/ClankClub/repo-rat/blob/main/LICENSE",
            "https://github.com/ClankClub/repo-rat/blob/main/README.md",
            "https://github.com/ClankClub/repo-rat/blob/main/docs/architecture.md",
        }
        self.assertTrue(expected <= set(self.page.hrefs))

    def test_setup_and_backfill_copy_is_explicit(self):
        copy = " ".join(self.page.text).lower()
        for phrase in (
            "backfill",
            "many messages",
            "first normal poll",
            "repo_rat_starred_username",
            "discord_webhook_url",
            "optional",
            "openai_api_key",
        ):
            self.assertIn(phrase, copy)
        self.assertIn("previews", copy)

    def test_page_has_no_script_tags(self):
        self.assertEqual(self.page.scripts, 0)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests and confirm the page is missing**

Run: `python -m unittest discover -s tests -p 'test_site.py' -v`

Expected: the tests error because `docs/index.html` does not exist yet.

- [ ] **Step 3: Create `docs/index.html`**

Use a valid HTML5 document with `lang="en"`, viewport and description metadata, a title, one `<h1>`, a local `<link rel="stylesheet" href="site.css">`, and semantic `<header>`, `<nav>`, `<main>`, and `<footer>` landmarks. Wrap the page in `.page-shell`; use `.feature-grid` for the example/how-it-works area and `.callout` for setup/backfill emphasis. Include the exact navigation targets `how-it-works`, `setup`, and `backfill-warning`.

Content order and factual copy:

1. Header links: `How it works`, `Setup`, and `GitHub`.
2. Hero: “GitHub releases in. Signal out.” Describe Repo Rat as a self-hosted monitor that filters public GitHub releases and sends noteworthy reports to Discord or JSONL. State that an API key is not required: the deterministic heuristic judge works without an optional OpenAI-compatible model.
3. Example report: label the existing `report-preview.svg` illustrative; provide readable HTML text with the real message shape: repository/tag/name, summary, one release URL.
4. `how-it-works`: reuse `pipeline.svg`, with alt text explaining GitHub releases → SQLite state → significance judge → Discord or JSONL.
5. `setup`: ordered steps to fork, add `DISCORD_WEBHOOK_URL` as an Actions secret, optionally add `REPO_RAT_STARRED_USERNAME` as an Actions variable, enable Actions, and allow a normal poll to establish the initial quiet baseline. Link to the README for explicit-repository and local setup details.
6. `backfill-warning`: state plainly that backfill processes seeded historical releases and may send many messages; tell ordinary users to leave it off. Note that Discord may expand GitHub URLs into previews.
7. Transparency section: explain the public release/star data source and that the checked-in SQLite state contains public release metadata, not credentials. State that `OPENAI_API_KEY` is optional and heuristics still work without it. Link to the architecture reference for internals.
8. Footer links: repository, issues, license, README, and architecture, using canonical GitHub URLs. The Pages artifact contains `docs/`, so do not link to repository-root files as though they were copied into the site.

Every image must have useful `alt` text (empty alt only for a purely decorative image). Use relative paths for local images and `site.css`; link to repository documentation through canonical GitHub URLs. Do not include a webhook value, API key, remote font, tracking pixel, embedded third-party content, or `<script>` tag.

Create the initial stylesheet as a valid local file so Task 1's relative-path test passes:

```css
:root {
  color-scheme: dark;
  font-family: system-ui, sans-serif;
}
```

- [ ] **Step 4: Run the site-contract tests**

Run: `python -m unittest discover -s tests -p 'test_site.py' -v`

Expected: PASS; every relative asset/document path resolves, each fragment has exactly one target, and setup/backfill copy is present.

- [ ] **Step 5: Commit the content/test unit**

```bash
git add tests/test_site.py docs/index.html docs/site.css
git commit -m "feat: add Repo Rat project landing page"
```

## Task 2: Style and validate the responsive page

**Files:**
- Modify: `docs/site.css`
- Modify: `tests/test_site.py`

**Interfaces:**
- The page imports only the local `site.css` file.
- CSS defines a dark GitHub-inspired palette with amber accent and visible keyboard focus.

- [ ] **Step 1: Add failing CSS contract checks**

Add tests asserting the stylesheet link exists and resolves, CSS includes `:focus-visible`, includes a narrow-screen media query, and contains no `@import` or remote `url(https://...)` font/image dependency. Example checks:

```python
    def test_stylesheet_is_local_and_responsive(self):
        self.assertIn('href="site.css"', self.html)
        css = (DOCS / "site.css").read_text(encoding="utf-8")
        self.assertRegex(css, r":focus-visible")
        self.assertRegex(css, r"@media\s*\(max-width:")
        self.assertNotIn("@import", css)
        self.assertNotRegex(css, r"url\(\s*https?://")
```

- [ ] **Step 2: Run the focused tests and confirm they fail**

Run: `python -m unittest discover -s tests -p 'test_site.py' -v`

Expected: the stylesheet test fails because the minimal stylesheet has no `:focus-visible` rule or narrow-screen media query yet.

- [ ] **Step 3: Expand `docs/site.css`**

Use CSS custom properties for page background, surface, primary text, muted text, link blue, and Repo Rat amber. Style a centered max-width layout, a compact header/nav, a prominent hero, a readable single-column text measure, a restrained two-column pipeline/example area that collapses to one column, a visually distinct setup/backfill callout, and a quiet footer. Use system fonts only. Set `box-sizing: border-box`; keep images fluid with `max-width: 100%`; avoid fixed-width content. Add visible `:focus-visible` outlines and a media query at exactly `48rem` to collapse columns and navigation spacing. A suitable starting structure is:

```css
:root {
  color-scheme: dark;
  --page: #0d1117;
  --surface: #161b22;
  --text: #f0f6fc;
  --muted: #8b949e;
  --link: #58a6ff;
  --rat: #d29922;
  font-family: system-ui, sans-serif;
}

*,
*::before,
*::after {
  box-sizing: border-box;
}

body {
  margin: 0;
  background: var(--page);
  color: var(--text);
}

a:focus-visible {
  outline: 3px solid var(--rat);
  outline-offset: 3px;
}

img {
  display: block;
  max-width: 100%;
  height: auto;
}

.page-shell {
  width: min(100% - 2rem, 72rem);
  margin-inline: auto;
}

.feature-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 2rem;
}

@media (max-width: 48rem) {
  .feature-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
```

CSS must not depend on animation, hover-only information, external fonts, external image URLs, or JavaScript. Use text/background colors with strong contrast; keep link states distinguishable without relying on color alone.

- [ ] **Step 4: Run focused checks and inspect responsive rendering**

Run: `python -m unittest discover -s tests -p 'test_site.py' -v`

Expected: PASS. Then inspect the rendered page at 360px, 768px, and 1280px widths. Confirm no horizontal scrolling, clipped text, inaccessible nav links, or loss of visible focus during keyboard tabbing.

- [ ] **Step 5: Commit the stylesheet unit**

```bash
git add docs/site.css docs/index.html tests/test_site.py
git commit -m "style: make Repo Rat site responsive"
```

## Task 3: Add isolated GitHub Pages deployment

**Files:**
- Create: `.github/workflows/pages.yml`
- Do not modify: `.github/workflows/repo-rat.yml`

**Interfaces:**
- Pushes to `main` that change `docs/index.html`, `docs/site.css`, the three site SVGs, or `.github/workflows/pages.yml` deploy the staged site artifact.
- `workflow_dispatch` provides a manual recovery path.
- The deployment job uses the `github-pages` environment, read-only `contents: read`, and only the write permissions `pages: write` and `id-token: write`.

- [ ] **Step 1: Create the Pages workflow**

Use this workflow structure and triggers:

```yaml
name: Deploy Pages

on:
  push:
    branches: [main]
    paths:
      - "docs/index.html"
      - "docs/site.css"
      - "docs/assets/repo-rat-banner.svg"
      - "docs/assets/report-preview.svg"
      - "docs/assets/pipeline.svg"
      - ".github/workflows/pages.yml"
  workflow_dispatch:

permissions:
  contents: read

concurrency:
  group: github-pages
  cancel-in-progress: true

jobs:
  deploy:
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pages: write
      id-token: write
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - name: Check out source
        uses: actions/checkout@v4
      - name: Stage site files only
        run: |
          mkdir -p "$RUNNER_TEMP/repo-rat-pages/assets"
          cp docs/index.html docs/site.css "$RUNNER_TEMP/repo-rat-pages/"
          cp docs/assets/repo-rat-banner.svg docs/assets/report-preview.svg docs/assets/pipeline.svg "$RUNNER_TEMP/repo-rat-pages/assets/"
      - name: Upload static site
        uses: actions/upload-pages-artifact@v5
        with:
          path: ${{ runner.temp }}/repo-rat-pages
      - name: Deploy to GitHub Pages
        id: deployment
        uses: actions/deploy-pages@v4
```

- [ ] **Step 2: Check the workflow diff and permissions**

Run: `git diff --check -- .github/workflows/pages.yml` and inspect the complete workflow. Confirm it has no `DISCORD_WEBHOOK_URL`, `OPENAI_API_KEY`, `state.db` operations, or dependency on the polling workflow; confirm only the page, stylesheet, and three referenced SVGs enter the artifact; confirm the only write permissions are Pages deployment and OIDC.

- [ ] **Step 3: Commit the deployment workflow**

```bash
git add .github/workflows/pages.yml
git commit -m "ci: deploy Repo Rat site to GitHub Pages"
```

## Task 4: Deploy, verify, and link the public site

**Files:**
- Modify: `README.md` after a real Pages URL is returned by a successful deployment.
- No other runtime or polling files.

- [ ] **Step 1: Run the complete project test suite before deployment**

Run: `python -m unittest discover -s tests -v`

Expected: all existing project tests and new site-contract tests pass.

- [ ] **Step 2: Validate GitHub Pages repository configuration**

Push the approved implementation to the intended branch and inspect the Pages deployment workflow. If the workflow reports that Pages is disabled or its source must be set to GitHub Actions and the available connector cannot perform that owner-level setting, stop and ask the user to enable Pages in repository Settings → Pages → Build and deployment → Source → GitHub Actions. Do not change organization/repository permissions or choose a different hosting service.

- [ ] **Step 3: Verify the deployed URL and public assets**

After `Deploy Pages` succeeds, read the exact `page_url` output from the `github-pages` environment/deployment step. Open that returned URL and verify the page, styles, banner, report preview, pipeline SVG, in-page links, and mobile layout load correctly. Do not construct or guess the URL.

- [ ] **Step 4: Add the verified URL to the README**

Add one `Project site` link in the README's centered badge/intro area using only the exact URL returned by the successful deployment. Do not alter README setup semantics or copy a speculative URL.

- [ ] **Step 5: Re-run site and repository validation**

Run: `python -m unittest discover -s tests -v` and `git diff --check`. Verify the README contains the exact deployed URL and the full test suite passes. The Pages workflow need not redeploy for the README-only link.

- [ ] **Step 6: Commit the README link**

```bash
git add README.md
git commit -m "docs: link Repo Rat project site"
```

## Plan Self-Review

- Every design-spec section maps to Task 1 (content and transparency), Task 2 (visual/accessibility direction), Task 3 (isolated deployment), or Task 4 (validation and verified project-site link).
- Review-focus tests/checks are assigned to Tasks 1 and 2; workflow isolation and least privilege are checked in Task 3; configuration blockers are explicit in Task 4.
- There are no new runtime or frontend dependencies; the only new Python code is a standard-library static-site test.
- The implementation must run in a clean worktree based on the latest remote main; the dirty local rebrand/setup checkout remains preserved and must not be pushed by this plan.
