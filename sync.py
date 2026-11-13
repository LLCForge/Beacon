#!/usr/bin/env python3
"""Vendor llcforge-beacon into an LLCForge tool repository and render the
shared packaging / ops templates.

    python sync.py <tool-dir> --bin <bin> --name "<name>" --repo <Repo> \
        --description "<description>" --port-metrics <port> [--keep PATH ...]

* Mirrors the crate (Cargo.toml, src/, schema/, tests/, docs, licence files)
  into <tool-dir>/crates/llcforge-beacon/ so the tool builds standalone with
  `llcforge-beacon = { path = "crates/llcforge-beacon" }`.
* Renders templates/ into <tool-dir>, replacing {{bin}}, {{name}}, {{repo}},
  {{description}}, {{port_metrics}} (and the derived {{formula_class}}) in
  file contents and paths.
* Never writes top-level README*, ARCHITECTURE.md or anything under src/;
  never overwrites an existing file listed with --keep.
* Idempotent: files are written only when their content changes.

Standard library only; Python 3.8+.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
from pathlib import Path, PurePosixPath

HERE = Path(__file__).resolve().parent
CRATE_DEST = PurePosixPath("crates/llcforge-beacon")
# What gets vendored from the crate (relative to the crate root).
CRATE_FILES = ["Cargo.toml", "LICENSE", "NOTICE", "README.md", "README.tr.md", "deny.toml"]
CRATE_DIRS = ["src", "schema", "tests", "examples"]
TOKEN_RE = re.compile(r"\{\{(bin|name|repo|description|port_metrics|formula_class)\}\}")


class SyncError(Exception):
    pass


def validate(args: argparse.Namespace) -> dict[str, str]:
    if not re.fullmatch(r"[a-z][a-z0-9-]{0,62}[a-z0-9]", args.bin):
        raise SyncError("--bin must be lowercase [a-z0-9-], 2..64 chars, e.g. event-horizon")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}", args.repo):
        raise SyncError("--repo must be a GitHub repository name, e.g. Event-Horizon")
    for label, value, limit in (("--name", args.name, 64), ("--description", args.description, 200)):
        if not value.strip() or len(value) > limit:
            raise SyncError(f"{label} must be 1..{limit} characters")
        # Values land in TOML, YAML, JSON, Ruby and XML without per-format escaping.
        if any(c in value for c in '"\\<>&`$') or any(ord(c) < 32 for c in value):
            raise SyncError(f"{label} must not contain quotes, backslashes, <>&`$ or control characters")
    if not 1 <= args.port_metrics <= 65535:
        raise SyncError("--port-metrics must be 1..65535")
    formula_class = "".join(part.capitalize() for part in args.bin.split("-"))
    return {
        "bin": args.bin,
        "name": args.name.strip(),
        "repo": args.repo,
        "description": args.description.strip(),
        "port_metrics": str(args.port_metrics),
        "formula_class": formula_class,
    }


def render(text: str, tokens: dict[str, str]) -> str:
    return TOKEN_RE.sub(lambda m: tokens[m.group(1)], text)


def is_protected(rel: PurePosixPath) -> bool:
    if rel.parts and rel.parts[0] == "src":
        return True
    if len(rel.parts) == 1:
        name = rel.name.lower()
        return name.startswith("readme") or name == "architecture.md"
    return False


class Writer:
    def __init__(self, root: Path, dry_run: bool) -> None:
        self.root = root
        self.dry_run = dry_run
        self.stats = {"created": 0, "updated": 0, "unchanged": 0, "kept": 0, "protected": 0, "removed": 0}

    def write(self, rel: PurePosixPath, data: bytes, keep: set[PurePosixPath]) -> None:
        if is_protected(rel):
            self.stats["protected"] += 1
            return
        dest = self.root.joinpath(*rel.parts)
        if dest.is_symlink():
            raise SyncError(f"refusing to write through symlink {dest}")
        if dest.exists():
            if rel in keep:
                self.stats["kept"] += 1
                return
            if dest.read_bytes() == data:
                self.stats["unchanged"] += 1
                return
            action = "updated"
        else:
            action = "created"
        self.stats[action] += 1
        print(f"  {action:8} {rel}")
        if self.dry_run:
            return
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_name(dest.name + ".sync-tmp")
        tmp.write_bytes(data)
        os.replace(tmp, dest)
        if rel.suffix in (".sh", ".py") or rel.name == "sync.py":
            dest.chmod(0o755)


def iter_files(base: Path):
    for dirpath, dirnames, filenames in os.walk(base, followlinks=False):
        dirnames[:] = sorted(d for d in dirnames if d not in ("target", "__pycache__"))
        for f in sorted(filenames):
            p = Path(dirpath) / f
            if p.is_file() and not p.is_symlink():
                yield p


def sync_crate(w: Writer) -> None:
    wanted: dict[PurePosixPath, bytes] = {}
    for name in CRATE_FILES:
        src = HERE / name
        if src.is_file():
            wanted[CRATE_DEST / name] = src.read_bytes()
    for d in CRATE_DIRS:
        for p in iter_files(HERE / d):
            rel = PurePosixPath(p.relative_to(HERE).as_posix())
            wanted[CRATE_DEST / rel] = p.read_bytes()
    for rel, data in sorted(wanted.items()):
        w.write(rel, data, keep=set())
    # Mirror: drop files that no longer exist upstream (only inside the vendored crate).
    dest_root = w.root.joinpath(*CRATE_DEST.parts)
    if dest_root.is_dir():
        for p in iter_files(dest_root):
            rel = CRATE_DEST / PurePosixPath(p.relative_to(dest_root).as_posix())
            if rel not in wanted and rel.parts[2] != "target":
                w.stats["removed"] += 1
                print(f"  removed  {rel}")
                if not w.dry_run:
                    p.unlink()


def sync_templates(w: Writer, tokens: dict[str, str], keep: set[PurePosixPath]) -> None:
    tdir = HERE / "templates"
    for p in iter_files(tdir):
        rel_src = p.relative_to(tdir).as_posix()
        rel = PurePosixPath(render(rel_src, tokens))
        if ".." in rel.parts or rel.is_absolute():
            raise SyncError(f"template path escapes the tool dir: {rel_src}")
        try:
            text = p.read_bytes().decode("utf-8")
        except UnicodeDecodeError as e:
            raise SyncError(f"template is not UTF-8: {rel_src}") from e
        out = render(text, tokens)
        w.write(rel, out.encode("utf-8"), keep)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("tool_dir", type=Path)
    ap.add_argument("--bin", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--description", required=True)
    ap.add_argument("--port-metrics", type=int, required=True)
    ap.add_argument(
        "--keep",
        action="append",
        default=[],
        metavar="PATH",
        help="rendered path (relative to tool dir, e.g. Dockerfile) never overwritten if it exists; repeatable",
    )
    ap.add_argument("--dry-run", action="store_true", help="show what would change")
    args = ap.parse_args(argv)
    try:
        tokens = validate(args)
        root = args.tool_dir.resolve()
        if not (root / "Cargo.toml").is_file():
            raise SyncError(f"{root} has no Cargo.toml; expected a tool repository")
        if root == HERE or HERE in root.parents:
            raise SyncError("tool dir must not be the llcforge-beacon source tree")
        keep = {PurePosixPath(k.replace("\\", "/")) for k in args.keep}
        w = Writer(root, args.dry_run)
        print(f"llcforge-beacon -> {root / 'crates' / 'llcforge-beacon'}")
        sync_crate(w)
        print(f"templates -> {root}")
        sync_templates(w, tokens, keep)
    except (SyncError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    s = w.stats
    print(
        f"done: {s['created']} created, {s['updated']} updated, {s['unchanged']} unchanged, "
        f"{s['kept']} kept, {s['protected']} protected, {s['removed']} removed"
        + (" (dry run)" if args.dry_run else "")
    )
    manifest = (root / "Cargo.toml").read_text(encoding="utf-8", errors="replace")
    if "llcforge-beacon" not in manifest:
        print('hint: add to [dependencies]: llcforge-beacon = { path = "crates/llcforge-beacon" }')
    if shutil.which("cargo") is None:
        print("hint: cargo not found on PATH; build not verified")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
