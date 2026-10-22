"""Check public files and reachable Git history without printing secret values."""
import argparse
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = {
    "provider credential": re.compile(rb"\b(?:sk-[A-Za-z0-9_-]{20,}|pat_[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[0-9A-Z]{16})\b"),
    "private key": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "literal bearer token": re.compile(rb"(?i)bearer\s+[A-Za-z0-9_.-]{24,}"),
    "literal secret assignment": re.compile(rb"(?i)\b(?:api[_-]?key|access[_-]?token|api[_-]?token|client[_-]?secret|password)\b[\"']?\s*[:=]\s*[\"']([A-Za-z0-9_./+=-]{16,})[\"']"),
}


def findings(data, known_secrets=()):
    result = [name for name, pattern in PATTERNS.items() if pattern.search(data)]
    if any(value in data for value in known_secrets):
        result.append("known local credential")
    return result


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, stderr=subprocess.PIPE)


def forbidden_path(name):
    path = Path(name)
    return (
        (path.name.startswith(".env") and path.name != ".env.example")
        or path.suffix.lower() in {".pem", ".key", ".p12", ".pfx"}
        or path.name == "execution_logs.json"
    )


def self_test():
    fake = b"sk-" + b"a" * 32
    assert findings(fake) == ["provider credential"]
    assert findings(b"password='" + b"x" * 24 + b"'")
    assert not findings(b"LLM_API_KEY=\nCOZE_API_TOKEN=\n")
    assert forbidden_path("folder/.env.local")
    assert not forbidden_path(".env.example")
    assert findings(b"demo-local-value", [b"demo-local-value"])
    print("Secret scanner self-check passed.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--history", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0

    known = [value.encode() for key, value in os.environ.items()
             if re.search(r"(?:API_KEY|API_TOKEN|ACCESS_TOKEN|CLIENT_SECRET)$", key)
             and len(value) >= 16]
    names = [name.decode("utf-8") for name in git("ls-files", "-z").split(b"\0") if name]
    issues = []
    for name in names:
        if forbidden_path(name):
            issues.append((name, "excluded local file is tracked"))
        path = ROOT / name
        if path.is_file():
            issues.extend((name, item) for item in findings(path.read_bytes(), known))

    blobs = 0
    if args.history:
        object_lines = git("rev-list", "--objects", "--all").decode("utf-8").splitlines()
        for entry in object_lines:
            sha, _, name = entry.partition(" ")
            if git("cat-file", "-t", sha).strip() != b"blob":
                continue
            blobs += 1
            if name and forbidden_path(name):
                issues.append((name, "excluded local file exists in history"))
            issues.extend(("history:" + sha[:12], item)
                          for item in findings(git("cat-file", "blob", sha), known))

    for name, kind in sorted(set(issues)):
        print(f"FAIL {name}: {kind}")
    print(f"Scanned {len(names)} tracked files and {blobs} history blobs; findings={len(set(issues))}.")
    return 1 if issues else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, subprocess.CalledProcessError) as error:
        print(f"Secret scan could not finish: {type(error).__name__}.", file=sys.stderr)
        sys.exit(2)
