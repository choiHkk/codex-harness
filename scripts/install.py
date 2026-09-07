#!/usr/bin/env python3
"""Install the Codex harness into a project, preserving existing preferences."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".agents" / "skills" / "harness"
sys.path.insert(0, str(SKILL / "scripts"))
from common import agent_names, apply_files, existing_bytes, safe_path  # noqa: E402

START = "<!-- codex-harness:start -->"
END = "<!-- codex-harness:end -->"


def merge_instructions(current: str, block: str) -> str:
    if START not in current and END not in current:
        return current + ("\n\n" if current and not current.endswith("\n\n") else "") + block
    if current.count(START) != 1 or current.count(END) != 1:
        raise ValueError("AGENTS.md has duplicate or incomplete codex-harness markers.")
    start, end = current.index(START), current.index(END)
    if end < start:
        raise ValueError("AGENTS.md harness markers are reversed.")
    return current[:start] + block.rstrip("\n") + current[end + len(END):]


def merge_config(current: str) -> str:
    data = tomllib.loads(current)
    agents = data.get("agents", {})
    if not isinstance(agents, dict):
        raise ValueError("Expected a TOML table for agents.")
    additions = {}
    if "enabled" not in agents:
        additions["enabled"] = True
    if not {"max_concurrent_threads_per_session", "max_threads"} & agents.keys():
        additions["max_concurrent_threads_per_session"] = 3
    if not additions:
        return current
    lines = "".join(f"{key} = {str(value).lower()}\n" for key, value in additions.items())
    header = re.search(r"(?m)^\[\s*(?:agents|'agents'|\"agents\")\s*\][ \t]*(?:#[^\n]*)?(?:\n|$)", current)
    if header:
        point = header.end()
        merged = current[:point] + ("" if current[:point].endswith("\n") else "\n") + lines + current[point:]
    else:
        # Appending a parent table is also valid after implicit [agents.role] tables.
        merged = current + ("\n" if current else "") + "[agents]\n" + lines
        try:
            tomllib.loads(merged)
        except tomllib.TOMLDecodeError:
            # Root dotted keys can be extended by other root dotted keys.
            merged = "".join(f"agents.{key} = {str(value).lower()}\n" for key, value in additions.items()) + current
    try:
        actual = tomllib.loads(merged)
    except tomllib.TOMLDecodeError as exc:
        raise ValueError("Cannot safely extend inline agents config; use an [agents] table, then retry.") from exc
    expected = dict(data)
    expected["agents"] = {**agents, **additions}
    if actual != expected:
        raise ValueError("Config merge would alter existing settings.")
    return merged


def install(target: Path, *, dry_run: bool = False) -> list[Path]:
    if target.expanduser().is_symlink():
        raise ValueError(f"Refusing symlink target: {target}")
    target = safe_path(target.expanduser().resolve())
    if target.exists() and not target.is_dir():
        raise ValueError(f"Target is not a directory: {target}")
    names = agent_names(target)
    payload = {}
    sources = [p for p in SKILL.rglob("*") if p.is_file()
               and "__pycache__" not in p.parts and p.suffix != ".pyc"]
    sources += sorted((ROOT / ".codex" / "agents").glob("*.toml"))
    if not (SKILL / "SKILL.md").is_file() or not sources:
        raise ValueError("The source harness is incomplete.")
    # Detect all collisions before making any destination directories or writes.
    for source in sources:
        path = target / source.relative_to(ROOT)
        content = source.read_bytes()
        if source.parent == ROOT / ".codex" / "agents":
            name = tomllib.loads(content.decode("utf-8"))["name"]
            if name in names and names[name] != path:
                raise ValueError(f"Agent name {name} already exists at {names[name]} (left unchanged).")
        previous = existing_bytes(path)
        if previous is not None and previous != content:
            raise ValueError(f"Conflicting existing file (left unchanged): {path}")
        payload[path] = content
    for name, merge in (("AGENTS.md", merge_instructions), (".codex/config.toml", merge_config)):
        path = target / name
        previous = existing_bytes(path)
        current = previous.decode("utf-8") if previous is not None else ""
        result = (merge(current, (SKILL / "assets" / "AGENTS.md").read_text(encoding="utf-8"))
                  if name == "AGENTS.md" else merge(current))
        payload[path] = result.encode("utf-8")
    return apply_files(payload, dry_run=dry_run)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=Path, required=True, help="Destination project directory.")
    parser.add_argument("--dry-run", action="store_true", help="List planned writes without changing files.")
    args = parser.parse_args()
    try:
        changed = install(args.target, dry_run=args.dry_run)
        for path in changed:
            print(f"{'Would write' if args.dry_run else 'Wrote'} {path}")
        print(f"{len(changed)} file(s) {'planned' if args.dry_run else 'changed'}.")
        print("Open a new trusted local Codex session in the project, then invoke $harness.")
        return 0
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
