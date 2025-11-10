#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TidyBlankLines.py — Limpieza cosmética de saltos de línea.
Reduce múltiples líneas vacías consecutivas a una sola.

Uso:
  python TidyBlankLines.py /ruta/al/vault --in-place
"""

import re, sys, shutil
from pathlib import Path
import argparse

MULTIBLANK_RE = re.compile(r"\n{3,}")  # tres o más saltos seguidos

def tidy_file(path: Path, in_place: bool, make_backup: bool):
    text = path.read_text(encoding="utf-8", errors="ignore")
    cleaned = MULTIBLANK_RE.sub("\n\n", text.strip()) + "\n"
    if cleaned != text:
        if in_place:
            if make_backup:
                bak = path.with_suffix(path.suffix + ".bak")
                if not bak.exists():
                    shutil.copy2(path, bak)
            path.write_text(cleaned, encoding="utf-8")
        return True
    return False

def walk_md(root: Path):
    for p in root.rglob("*.md"):
        if any(x in p.parts for x in (".obsidian", ".git")):
            continue
        yield p

def main():
    ap = argparse.ArgumentParser(description="Reduce saltos de línea múltiples a uno solo.")
    ap.add_argument("vault", help="Carpeta raíz del Vault con notas .md")
    ap.add_argument("--in-place", action="store_true", help="Aplica cambios en los archivos")
    ap.add_argument("--no-backup", action="store_true", help="No crear .bak")
    args = ap.parse_args()

    vault = Path(args.vault).expanduser().resolve()
    total = 0
    for md in walk_md(vault):
        if tidy_file(md, args.in_place, not args.no_backup):
            total += 1
            print(f"✔ Limpio: {md.relative_to(vault)}")
    print(f"\nArchivos ajustados: {total}")
    if not args.in_place:
        print("(Dry-run: sin escribir cambios, usa --in-place para aplicarlos)")

if __name__ == "__main__":
    main()
