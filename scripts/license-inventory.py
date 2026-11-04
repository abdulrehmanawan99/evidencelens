"""Record installed pinned Python and locked npm licenses without private runtime data."""
from importlib.metadata import distribution
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
python = []
for line in (root / "backend/requirements-dev.lock").read_text().splitlines():
    name, version = line.split("==")
    package = distribution(name)
    meta = package.metadata
    classifiers = [value.removeprefix("License :: ") for value in meta.get_all("Classifier", []) if value.startswith("License ::")]
    python.append({"name": name, "version": version, "license": meta.get("License-Expression") or classifiers or (meta.get("License") or "Review package metadata").splitlines()[0], "notice_files": [str(path) for path in package.files or [] if "license" in str(path).lower() or "copying" in str(path).lower()]})
lock = json.loads((root / "apps/web/package-lock.json").read_text())
npm = [{"path": path, "version": value.get("version"), "license": value.get("license", "Review distributed package notices"), "development": value.get("dev", False), "optional": value.get("optional", False)} for path, value in lock["packages"].items() if path]
report = {"generated": "2026-11-05", "scope": "Pinned Python runtime/development and all npm lock entries, including optional platforms. License identifiers are metadata, not legal advice. Dependencies retain their package notices. No project-wide redistribution license has been selected.", "python": python, "npm": npm}
(root / "docs/licenses.json").write_text(json.dumps(report, indent=2)+"\n")
