import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BrandingTests(unittest.TestCase):
    def test_repo_rat_is_the_canonical_public_identity(self):
        self.assertTrue((ROOT / "repo_rat").is_dir())
        self.assertFalse((ROOT / "release_rat").exists())
        self.assertTrue((ROOT / ".github/workflows/repo-rat.yml").is_file())
        self.assertFalse((ROOT / ".github/workflows/release-rat.yml").exists())
        self.assertTrue((ROOT / "docs/assets/repo-rat-banner.svg").is_file())
        self.assertFalse((ROOT / "docs/assets/release-rat-banner.svg").exists())

        files = [
            ROOT / "README.md",
            ROOT / "config.json",
            ROOT / ".env.example",
            ROOT / ".github/workflows/ci.yml",
            ROOT / ".github/workflows/repo-rat.yml",
            ROOT / "pyproject.toml",
            ROOT / "docs/architecture.md",
            ROOT / "docs/assets/repo-rat-banner.svg",
            ROOT / "docs/assets/pipeline.svg",
            ROOT / "docs/assets/report-preview.svg",
            ROOT / "examples/repo-rat.service",
            ROOT / "examples/repo-rat.timer",
        ]
        for path in files:
            contents = path.read_text(encoding="utf-8")
            self.assertNotIn("release-rat", contents, str(path))
            self.assertNotIn("release_rat", contents, str(path))
            self.assertNotIn("Release Rat", contents, str(path))


if __name__ == "__main__":
    unittest.main()
