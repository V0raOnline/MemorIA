#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ImageLinkInjector.py — Reemplaza sediment://file_<id> por wikilinks Obsidian
buscando imágenes por PREFIJO (file_<id>*) en un banco de imágenes externo.

Uso:
  python ImageLinkInjector.py /ruta/al/vault /ruta/a/IMAGE_BANK --in-place --wiki-prefix IMAGE_BANK

Ejemplo:
  python ImageLinkInjector.py ~/Vaults/MERGED_VAULT ~/IMAGE_BANK --in-place --wiki-prefix IMAGE_BANK
"""

import os
import re
import sys
import shutil
from pathlib import Path
import argparse
from typing import Optional, List

# Captura IDs tipo file_ + hex largo (no nos importan los sufijos)
SEDIMENT_RE = re.compile(r"sediment://(file_[0-9a-f]{16,})\b", re.IGNORECASE)

# Prioridad de extensiones
EXT_PRIORITY = [".png", ".jpg", ".jpeg", ".webp"]

def find_candidates(file_id: str, img_dir: Path) -> List[Path]:
    """
    Busca recursivamente cualquier archivo que EMPIECE por file_id y tenga
    una extensión de imagen admitida.
    """
    hits = []
    for ext in EXT_PRIORITY:
        # prefijo exacto + cualquier sufijo
        pattern = f"{file_id}*{ext}"
        hits.extend(img_dir.rglob(pattern))
    return hits

def pick_best(candidates: List[Path]) -> Optional[Path]:
    """
    De una lista de candidatos, elige:
      1) por prioridad de extensión (png > jpg > jpeg > webp),
      2) a igualdad, el más reciente por mtime.
    """
    if not candidates:
        return None
    # agrupa por extensión prioridad
    by_ext = {ext: [] for ext in EXT_PRIORITY}
    for c in candidates:
        by_ext.get(c.suffix.lower(), []).append(c)
    for ext in EXT_PRIORITY:
        group = by_ext.get(ext) or []
        if group:
            # más reciente primero
            group.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            return group[0]
    # si nada coincide, devuelve el primero
    return candidates[0]

def build_wikilink(target: Path, wiki_prefix: str) -> str:
    """
    Construye un wikilink [[PREFIX/filename.ext]]
    wiki_prefix puede ser vacío para [[filename.ext]].
    """
    if wiki_prefix:
        rel = f"{wiki_prefix.rstrip('/')}/{target.name}"
    else:
        rel = target.name
    return f"![[{rel}]]"

def process_file(md_path: Path, img_dir: Path, wiki_prefix: str,
                 in_place: bool, make_backup: bool) -> tuple[int, int]:
    """
    Reemplaza todas las ocurrencias de sediment://file_<id> por ![[<prefix>/<name>]]
    Retorna (sustituciones, faltantes)
    """
    text = md_path.read_text(encoding="utf-8", errors="ignore")
    matches = list(SEDIMENT_RE.finditer(text))
    if not matches:
        return (0, 0)

    substitutions, missing = 0, 0
    new_text = text

    # para evitar reemplazos repetidos, procesamos cada match único por su span
    # y usamos reemplazo por índice, no .replace global
    offset = 0
    for m in matches:
        full_match = m.group(0)
        file_id = m.group(1)
        # reubicar con offset si ya hemos modificado texto
        span_start = m.start() + offset
        span_end = m.end() + offset

        candidates = find_candidates(file_id, img_dir)
        best = pick_best(candidates)

        if best:
            wikilink = build_wikilink(best, wiki_prefix)
            new_text = new_text[:span_start] + wikilink + new_text[span_end:]
            # actualizar offset por diferencia de longitudes
            offset += len(wikilink) - (span_end - span_start)
            substitutions += 1
        else:
            missing += 1

    if in_place and substitutions:
        if make_backup:
            bak = md_path.with_suffix(md_path.suffix + ".bak")
            if not bak.exists():
                shutil.copy2(md_path, bak)
        md_path.write_text(new_text, encoding="utf-8")

    return (substitutions, missing)

def walk_md(root: Path):
    # evita carpetas ocultas del sistema y de Obsidian
    skip_dirs = {".obsidian", ".git", ".trash"}
    for p in root.rglob("*.md"):
        parts = set(p.parts)
        if parts & skip_dirs:
            continue
        yield p

def main():
    ap = argparse.ArgumentParser(description="Reemplaza sediment://file_<id> por wikilinks Obsidian a un IMAGE_BANK, buscando por prefijo.")
    ap.add_argument("vault", help="Carpeta raíz del Vault con .md")
    ap.add_argument("image_bank", help="Carpeta base donde están las imágenes extraídas (busca recursivamente)")
    ap.add_argument("--in-place", action="store_true", help="Aplica cambios en los .md")
    ap.add_argument("--no-backup", action="store_true", help="No crear .bak")
    ap.add_argument("--wiki-prefix", default="IMAGE_BANK",
                    help="Prefijo de ruta para el wikilink dentro del Vault (por defecto 'IMAGE_BANK')")
    args = ap.parse_args()

    vault = Path(args.vault).expanduser().resolve()
    img_dir = Path(args.image_bank).expanduser().resolve()

    if not vault.is_dir():
        sys.exit(f"❌ Carpeta de Vault no válida: {vault}")
    if not img_dir.is_dir():
        sys.exit(f"❌ Carpeta de imágenes no válida: {img_dir}")

    md_files = list(walk_md(vault))
    print(f"📘 Escaneando {len(md_files)} notas Markdown...\n")

    total_subs, total_missing, touched = 0, 0, 0

    for md in md_files:
        subs, miss = process_file(
            md, img_dir,
            wiki_prefix=args.wiki_prefix,
            in_place=args.in_place,
            make_backup=not args.no_backup
        )
        if subs or miss:
            touched += 1
            if subs:
                print(f"✔ {md.relative_to(vault)}: {subs} enlace(s)")
            if miss:
                print(f"⚠ {md.relative_to(vault)}: {miss} referencia(s) sin imagen")

        total_subs += subs
        total_missing += miss

    print("\nResumen:")
    print(f"- Archivos con referencias: {touched}")
    print(f"- Enlaces creados: {total_subs}")
    print(f"- Referencias sin imagen: {total_missing}")
    if not args.in_place:
        print("\n(Dry-run: sin escribir cambios, usa --in-place para aplicarlos)")

if __name__ == "__main__":
    main()
