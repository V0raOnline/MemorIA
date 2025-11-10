#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ExtractInlineImageLinks_v4.py — versión robusta con parser de llaves anidadas.
Extrae los wikilinks ![[...]] de imagen de diccionarios {…} dentro de bloques
### User / Assistant / Tool, los coloca justo debajo del encabezado
y elimina completamente el bloque {…}.
"""

import re, sys, shutil
from pathlib import Path
import argparse

# Detecta encabezados de rol
SECTION_RE = re.compile(r"(?m)^###\s+(User|Assistant|Tool)\s*$")
# Detecta wikilinks
WIKILINK_RE = re.compile(r"!\[\[(.*?)\]\]")
IMG_EXT_RE = re.compile(r"\.(png|jpg|jpeg|webp)$", re.IGNORECASE)

def find_sections(text: str):
    """Devuelve lista de (inicio, fin) de cada sección ### ..."""
    sections = []
    matches = list(SECTION_RE.finditer(text))
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i+1].start() if i+1 < len(matches) else len(text)
        sections.append((start, end))
    return sections

def find_balanced_blocks(section_text: str):
    """Encuentra bloques { ... } con llaves anidadas correctamente balanceadas."""
    blocks = []
    i = 0
    n = len(section_text)
    while i < n:
        if section_text[i] == '{':
            start = i
            depth = 1
            i += 1
            while i < n and depth > 0:
                if section_text[i] == '{':
                    depth += 1
                elif section_text[i] == '}':
                    depth -= 1
                i += 1
            end = i
            blocks.append((start, end))
        else:
            i += 1
    return blocks

def extract_wikilinks(block_text: str):
    """Extrae wikilinks de imagen dentro del bloque."""
    links = []
    for inner in (x.strip() for x in WIKILINK_RE.findall(block_text)):
        if IMG_EXT_RE.search(inner):
            if not inner.startswith("![["):
                inner = f"![[{inner}]]"
            links.append(inner)
    uniq = []
    for l in links:
        if l not in uniq:
            uniq.append(l)
    return uniq

def process_file(path: Path, in_place: bool, make_backup: bool):
    text = path.read_text(encoding="utf-8", errors="ignore")
    modified = False
    total_links, total_blocks = 0, 0
    sections = find_sections(text)
    for s_start, s_end in reversed(sections):
        section = text[s_start:s_end]
        # Buscar bloques { ... } balanceados
        blocks = find_balanced_blocks(section)
        if not blocks:
            continue
        # Posición donde insertar: debajo del encabezado
        header_end = section.find("\n")
        insert_pos = header_end + 1 if header_end != -1 else 0
        cuts = []
        links_to_add = []
        for a, b in blocks:
            block = section[a:b]
            links = extract_wikilinks(block)
            if links:
                cuts.append((a, b))
                links_to_add.extend(links)
        if not links_to_add:
            continue
        # Elimina los bloques del final hacia el inicio
        cleaned = section
        for a, b in reversed(cuts):
            cleaned = cleaned[:a] + cleaned[b:]
        # Inserta los enlaces debajo del encabezado
        insertion = "\n".join(links_to_add) + "\n\n"
        cleaned = cleaned[:insert_pos] + insertion + cleaned[insert_pos:]
        text = text[:s_start] + cleaned + text[s_end:]
        modified = True
        total_links += len(links_to_add)
        total_blocks += len(cuts)
    if in_place and modified:
        if make_backup:
            bak = path.with_suffix(path.suffix + ".bak")
            if not bak.exists():
                shutil.copy2(path, bak)
        path.write_text(text, encoding="utf-8")
    return total_links, total_blocks

def walk_md(root: Path):
    for p in root.rglob("*.md"):
        if any(x in p.parts for x in (".obsidian", ".git")):
            continue
        yield p

def main():
    ap = argparse.ArgumentParser(description="Extrae wikilinks de imagen de diccionarios {…} con llaves anidadas y elimina los bloques.")
    ap.add_argument("vault", help="Carpeta raíz del Vault")
    ap.add_argument("--in-place", action="store_true", help="Aplica cambios en los archivos")
    ap.add_argument("--no-backup", action="store_true", help="No crear .bak")
    args = ap.parse_args()

    vault = Path(args.vault).expanduser().resolve()
    total_links = total_blocks = 0
    for md in walk_md(vault):
        l, b = process_file(md, args.in_place, not args.no_backup)
        total_links += l
        total_blocks += b
    print(f"Insertados {total_links} enlaces | Bloques eliminados {total_blocks}")
    if not args.in_place:
        print("(Dry-run: sin escribir cambios, usa --in-place para aplicarlos)")

if __name__ == "__main__":
    main()
