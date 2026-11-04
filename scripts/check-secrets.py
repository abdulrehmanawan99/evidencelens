"""Scan tracked/staged text for common live credential patterns, without printing values."""
import json
from pathlib import Path
import re
import subprocess

root = Path(__file__).resolve().parents[1]
git = "git"
paths = subprocess.check_output([git, "ls-files", "-z"], cwd=root).decode().split("\0")
patterns = {"private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"), "openai_key": re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{32,}"), "github_token": re.compile(r"\b(?:ghp_|github_pat_)[A-Za-z0-9_]{30,}"), "aws_key": re.compile(r"\bAKIA[0-9A-Z]{16}\b")}
findings = []
for path in paths:
    if not path or not (root / path).is_file():
        continue
    data = (root / path).read_bytes()
    if b"\x00" in data:
        continue
    text = data.decode("utf-8", errors="replace")
    for name, pattern in patterns.items():
        if pattern.search(text):
            findings.append({"file": path, "pattern": name})
print(json.dumps({"state": "failed" if findings else "passed", "tracked_files": len([p for p in paths if p]), "findings": findings}))
raise SystemExit(bool(findings))
