from hashlib import sha256
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
from uuid import uuid4

from .config import settings


def split_passages(text):
    result = []
    for match in re.finditer(r"\S[\s\S]*?(?=\n\s*\n|\Z)", text):
        start, end = match.span()
        while start < end:
            stop = min(start + 3000, end)
            result.append({"text": text[start:stop], "start_offset": start, "line_start": text.count("\n", 0, start)+1, "line_end": text.count("\n", 0, stop-1)+1, "ordinal": len(result)})
            start = stop
    if len(result) > settings.max_passages:
        raise ValueError("passage_limit")
    return result


def extract(path, checksum, media_type, check=lambda: None):
    original = path.read_bytes()
    if sha256(original).hexdigest() != checksum:
        raise ValueError("source_integrity_mismatch")
    check()
    if media_type == "text/plain":
        result = {"pages": [{"number": 1, "text": original.decode("utf-8-sig")}], "warnings": [], "extraction_version": "text-v1"}
    else:
        if settings.parser_seconds <= 0:
            raise ValueError("parser_timeout")
        temporary = settings.storage_dir / ".tmp"
        temporary.mkdir(parents=True, exist_ok=True, mode=0o700)
        with tempfile.TemporaryDirectory(dir=temporary, prefix="parser-") as directory:
            output = Path(directory) / "output.json"
            docker_mode = settings.parser_backend == "docker" or (settings.parser_backend == "auto" and sys.platform == "darwin")
            environment = {"PATH": os.defpath, "TMPDIR": directory, "LANG": "C.UTF-8"}
            container = None
            if docker_mode:
                docker = shutil.which("docker")
                if not docker:
                    raise ValueError("parser_isolation_unavailable")
                container = "evidencelens-parser-"+uuid4().hex
                if os.environ.get("HOME"):
                    environment["HOME"] = os.environ["HOME"]
                if os.environ.get("DOCKER_HOST"):
                    environment["DOCKER_HOST"] = os.environ["DOCKER_HOST"]
                # /tmp here is a private bounded in-container tmpfs, not a shared host path.
                parser_tmpfs = "/tmp:rw,noexec,nosuid,size=16m"  # nosec B108
                command = [docker, "run", "--rm", "--pull=never", "--name", container, "--user", f"{os.getuid()}:{os.getgid()}", "--network", "none", "--memory", "512m", "--cpus", "1", "--pids-limit", "32", "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--read-only", "--tmpfs", parser_tmpfs, "--mount", f"type=bind,source={path},target=/input/source.pdf,readonly", settings.parser_image, "/input/source.pdf", str(settings.max_pdf_pages), str(settings.max_characters)]
            else:
                command = [sys.executable, "-I", "-B", str(Path(__file__).with_name("pdf_parser.py")), str(path), str(settings.max_pdf_pages), str(settings.max_characters)]
            with output.open("wb") as stream:
                process = subprocess.Popen(
                    command,
                    stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.DEVNULL,
                    cwd=directory, close_fds=True,
                    env=environment,
                )
                deadline = time.monotonic() + settings.parser_seconds
                try:
                    while process.poll() is None:
                        check()
                        if time.monotonic() >= deadline:
                            raise ValueError("parser_timeout")
                        time.sleep(0.1)
                finally:
                    if container:
                        subprocess.run([docker, "rm", "-f", container], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=environment, timeout=10)
                    if process.poll() is None:
                        process.kill()
                    process.wait()
            if process.returncode != 0 or output.stat().st_size > 8 * 1024 * 1024:
                raise ValueError("parser_resource_limit")
            try:
                result = json.loads(output.read_bytes())
            except (ValueError, UnicodeError):
                raise ValueError("malformed_pdf") from None
            if "error" in result:
                raise ValueError(result["error"])
    passages = []
    for page in result["pages"]:
        for part in split_passages(page["text"]):
            part["page_number"] = page["number"]
            part["ordinal"] = len(passages)
            passages.append(part)
    if len(passages) > settings.max_passages:
        raise ValueError("passage_limit")
    result["passages"] = passages
    return result
