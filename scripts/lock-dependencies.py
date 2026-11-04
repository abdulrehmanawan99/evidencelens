"""Regenerate exact runtime/dev closures from the verified local Python environment."""
from importlib.metadata import distribution
from pathlib import Path
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

ROOT = Path(__file__).resolve().parents[1]


def lock(roots):
    pending = [Requirement(line) for line in roots]
    versions, seen = {}, set()
    while pending:
        req = pending.pop()
        name = canonicalize_name(req.name)
        key = (name, tuple(sorted(req.extras)))
        if key in seen:
            continue
        seen.add(key)
        installed = distribution(name)
        if req.specifier and installed.version not in req.specifier:
            raise RuntimeError(f"Installed {name} does not match {req}")
        versions[name] = installed.version
        for value in installed.requires or []:
            dependency = Requirement(value)
            if not dependency.marker or any(dependency.marker.evaluate({"extra": extra}) for extra in {"", *req.extras}):
                pending.append(dependency)
    return "".join(f"{name}=={version}\n" for name, version in sorted(versions.items()))


runtime = (ROOT / "backend/requirements.txt").read_text().splitlines()
dev = [line for line in (ROOT / "backend/requirements-dev.txt").read_text().splitlines() if not line.startswith("-r")]
(ROOT / "backend/requirements.lock").write_text(lock(runtime))
(ROOT / "backend/requirements-dev.lock").write_text(lock(runtime + dev))
