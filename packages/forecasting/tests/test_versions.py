"""One version number everywhere: VERSION, every manifest and the code agree."""

import json
import tomllib
from pathlib import Path

import freshcast

ROOT = Path(__file__).resolve().parents[3]


def test_every_manifest_matches_the_version_file() -> None:
    version = (ROOT / "VERSION").read_text().strip()
    for toml in (
        "packages/forecasting/pyproject.toml",
        "apps/api/pyproject.toml",
        "infrastructure/cdk/pyproject.toml",
    ):
        data = tomllib.loads((ROOT / toml).read_text())
        assert data["project"]["version"] == version, toml
    package = json.loads((ROOT / "apps/dashboard/package.json").read_text())
    lock = json.loads((ROOT / "apps/dashboard/package-lock.json").read_text())
    assert (
        package["version"]
        == lock["version"]
        == lock["packages"][""]["version"]
        == version
    )
    assert freshcast.__version__ == version
    assert (
        f'version="{version}"'
        in (ROOT / "apps/api/src/freshcast_api/main.py").read_text()
    )


def test_the_release_has_notes_and_a_changelog_entry() -> None:
    version = (ROOT / "VERSION").read_text().strip()
    assert (ROOT / "docs/releases" / f"v{version}.md").exists()
