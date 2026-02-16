#!/usr/bin/env python3
"""
Generate KiCad v7+ project library tables recursively, intended to be run
FROM INSIDE the KiCad lib submodule, e.g.:

  ./kicad_lib/gen_lib_tables.py

Where:
  - "kicad_lib" is the submodule dir (name may vary)
  - The script lives at: <submodule>/gen_lib_tables.py
  - The lib folders are:
      <submodule>/symbols
      <submodule>/footprints

Outputs (written to the KiCad PROJECT ROOT, i.e. the parent of the submodule):
  - sym-lib-table
  - fp-lib-table

Discovery:
  - project_root   = script_dir.parent
  - submodule_dir  = script_dir
  - symbols_dir    = submodule_dir / "symbols"
  - footprints_dir = submodule_dir / "footprints"

Content:
  - sym-lib-table: all *.kicad_sym found recursively under <submodule>/symbols
  - fp-lib-table:  base "footprints" entry pointing at <submodule>/footprints
          + all *.pretty dirs found recursively under <submodule>/footprints

URIs are written as ${KIPRJMOD}/<submodule_name>/...

Library naming:
  - Symbol libs: filename stem
  - Footprint libs: directory name without .pretty
  - If duplicates exist, append relative parent path to make unique.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

SYM_HEADER = "(sym_lib_table\n  (version 7)\n"
FP_HEADER = "(fp_lib_table\n  (version 7)\n"
FOOTER = ")\n"


def kicad_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def make_lib_line(name: str, uri: str) -> str:
    return (f'  (lib (name "{kicad_escape(name)}")'
            f'(type "KiCad")'
            f'(uri "{kicad_escape(uri)}")'
            f'(options "")'
            f'(descr ""))')


def make_unique_names(paths: list[Path], base_name_func,
                      project_root: Path) -> dict[Path, str]:
    """
    Ensure library names are unique.
    If duplicates exist, append the parent path relative to project root
    (sanitized).
    """
    seen: dict[str, int] = {}
    result: dict[Path, str] = {}

    for p in paths:
        base = base_name_func(p)
        if base not in seen:
            seen[base] = 1
            result[p] = base
            continue

        try:
            parent_rel = p.parent.relative_to(project_root).as_posix()
        except ValueError:
            parent_rel = p.parent.as_posix()

        suffix = parent_rel.replace("/", "_").replace("\\", "_")
        result[p] = f"{base}_{suffix}"
        seen[base] += 1

    return result


def generate_sym_lib_table(project_root: Path, symbols_dir: Path) -> str:
    if not symbols_dir.exists():
        raise FileNotFoundError(f"Symbols directory not found: {symbols_dir}")

    sym_files = sorted(symbols_dir.rglob("*.kicad_sym"),
                       key=lambda p: p.as_posix().lower())
    name_map = make_unique_names(sym_files, lambda p: p.stem, project_root)

    lines = [SYM_HEADER.rstrip("\n")]
    for sym in sym_files:
        name = name_map[sym]
        rel_path = sym.relative_to(project_root).as_posix()
        uri = f"${{KIPRJMOD}}/{rel_path}"
        lines.append(make_lib_line(name, uri))

    lines.append(FOOTER.rstrip("\n"))
    return "\n".join(lines) + "\n"


def generate_fp_lib_table(project_root: Path, footprints_dir: Path) -> str:
    if not footprints_dir.exists():
        raise FileNotFoundError(
            f"Footprints directory not found: {footprints_dir}")

    pretty_dirs = sorted(
        [p for p in footprints_dir.rglob("*.pretty") if p.is_dir()],
        key=lambda p: p.as_posix().lower(),
    )
    name_map = make_unique_names(
        pretty_dirs,
        lambda p: p.name[:-len(".pretty")]
        if p.name.endswith(".pretty") else p.name,
        project_root,
    )

    lines = [FP_HEADER.rstrip("\n")]

    # Base footprints directory entry (name "footprints")
    base_rel = footprints_dir.relative_to(project_root).as_posix()
    base_uri = f"${{KIPRJMOD}}/{base_rel}"
    lines.append(make_lib_line("footprints", base_uri))

    for d in pretty_dirs:
        name = name_map[d]
        rel_path = d.relative_to(project_root).as_posix()
        uri = f"${{KIPRJMOD}}/{rel_path}"
        lines.append(make_lib_line(name, uri))

    lines.append(FOOTER.rstrip("\n"))
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Generate KiCad sym-lib-table and fp-lib-table"
        "(run from lib submodule dir)")
    ap.add_argument(
        "--sym-out",
        default="sym-lib-table",
        help='Output filename for symbol table'
        '(written to project root; default: "sym-lib-table")',
    )
    ap.add_argument(
        "--fp-out",
        default="fp-lib-table",
        help='Output filename for footprint table'
        '(written to project root; default: "fp-lib-table")',
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not write files; print what would be written to stderr",
    )
    args = ap.parse_args()

    script_path = Path(__file__).resolve()
    submodule_dir = script_path.parent
    project_root = submodule_dir.parent

    symbols_dir = submodule_dir / "symbols"
    footprints_dir = submodule_dir / "footprints"

    try:
        sym_content = generate_sym_lib_table(project_root, symbols_dir)
        fp_content = generate_fp_lib_table(project_root, footprints_dir)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    sym_out_path = project_root / args.sym_out
    fp_out_path = project_root / args.fp_out

    if args.dry_run:
        print(f"[dry-run] would write: {sym_out_path}", file=sys.stderr)
        print(sym_content, file=sys.stderr)
        print(f"[dry-run] would write: {fp_out_path}", file=sys.stderr)
        print(fp_content, file=sys.stderr)
        return 0

    sym_out_path.write_text(sym_content, encoding="utf-8")
    fp_out_path.write_text(fp_content, encoding="utf-8")

    print(f"✔ Generated {sym_out_path}")
    print(f"✔ Generated {fp_out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
