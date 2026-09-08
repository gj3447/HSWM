"""Buffered, allowlisted transport for RELUVATOR's remote read-only checks.

The remote helper is sent on stdin and uses an anonymous temporary file so a
Node process cannot lose pipe output during an immediate ``process.exit``.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from typing import Sequence

HOST = "delltower"
MAX_OUTPUT_BYTES = 64000
SSH_PREFIX = (
    "ssh", "-T", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", "-o",
    "StrictHostKeyChecking=yes", HOST,
)
REMOTE_PREFIX = (
    "/usr/bin/env", "--chdir=/data/kjra/PROJECT/RELUVATOR",
    "PATH=/data/kjra/.local/bin:/usr/local/bin:/usr/bin:/bin",
    "/usr/bin/timeout", "--kill-after=5s", "40s", "/data/kjra/.local/bin/node",
)
COMMANDS = {
    "contracts": REMOTE_PREFIX + ("packages/app/src/entrypoints/asyncapi-emit.ts", "--check"),
    "mesh": REMOTE_PREFIX + ("tools/contract-mesh/mesh-check.mjs", "--deep", "--json"),
}


def _buffered_program_source(command: Sequence[str]) -> str:
    """Return constant-compatible Python source; command values are repr-quoted."""
    return """import json, os, resource, subprocess, sys, tempfile
command = {command!r}
limit = {limit!r}
# Limit the regular-file writes in the producer, before forwarding to SSH.
# One extra byte distinguishes overflow from an exactly-full valid report.
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
resource.setrlimit(resource.RLIMIT_FSIZE, (limit + 1, limit + 1))
with tempfile.TemporaryFile() as output:
    process = subprocess.Popen(command, stdout=output, stderr=subprocess.STDOUT)
    code = process.wait()
    if os.fstat(output.fileno()).st_size > limit:
        print(json.dumps(dict(status="FAILED", error="REMOTE_OUTPUT_LIMIT", max_output_bytes=limit)), flush=True)
        raise SystemExit(65)
    output.seek(0)
    destination = sys.stdout.buffer
    while True:
        chunk = output.read(65536)
        if not chunk:
            break
        destination.write(chunk)
    destination.flush()
raise SystemExit(code)
""".format(command=list(command), limit=MAX_OUTPUT_BYTES)


def run(focus: str) -> int:
    command = COMMANDS.get(focus)
    if command is None:
        raise ValueError("focus must be one of: contracts, mesh")
    completed = subprocess.run(
        [*SSH_PREFIX, "/usr/bin/python3", "-"],
        input=_buffered_program_source(command).encode("utf-8"),
        stdout=sys.stdout.buffer,
        stderr=sys.stderr.buffer,
        check=False,
    )
    return completed.returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run one allowlisted RELUVATOR remote read-only check.")
    parser.add_argument("focus", choices=sorted(COMMANDS))
    args = parser.parse_args(argv)
    return run(args.focus)


if __name__ == "__main__":
    raise SystemExit(main())
