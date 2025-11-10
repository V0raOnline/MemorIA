#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RenderTetherQuotes_v2.py — convierte bloques tether_quote en fragmentos legibles,
usando parser de llaves balanceadas (nada de regex frágiles) y soportando comillas simples.

Convierte:
### Tool
{'content_type': 'tether_quote', 'domain': 'Koru.md', 'text': '...'}
en:
### Assistant
📄 Archivo cargado: **Koru.md**
> ...
"""
import re, json, ast, sys, shutil
from pathlib import Path
import argparse

# Detecta encabezados ### User/Assistant/Tool para no tocar fuera de secciones
SECTION_RE = re.compile(r"(?m)^###\s+(User|Assistant|Tool)\s*$")
# content_type: tether_quote con comillas simples o dobles
IS_TETHER_RE = re.compile(r"[\"']content_type[\"']\s*:\s*[\"']tether_quote[\"']", re.IGNORECASE)

MAX_PREVIEW_LINES = 20  # por si el texto es larguísimo

def find_sections(text: str):
    m = list(SECTION_RE.finditer(text))
    for i, s in enumerate(m):
        start = s.start()
        end = m[i+1].start() if i+1 < len(m) else len(text)
        yield (start, end)

def find_balanced_dicts(s: str):
    """Devuelve (start, end) de TODOS los bloques {…} balanceados en s."""
    i, n = 0, len(s)
    res = []
    while i < n:
        if s[i] == '{':
            depth, j = 1, i + 1
            while j < n and depth > 0:
                c = s[j]
                if c == '{': depth += 1
                elif c == '}': depth -= 1
                j += 1
            # j es posición después de la '}' final si se cerró bien
            if depth == 0:
                res.append((i, j))
                i = j
                continue
            else:
                break
        i += 1
    return res

def parse_json_like(txt: str):
    """Intenta JSON y luego dict estilo Python."""
    try:
        return json.loads(txt)
    except Exception:
        try:
            return ast.literal_eval(txt)
        except Exception:
            return None

def render_quote(obj: dict) -> str:
    domain = obj.get("domain") or obj.get("file") or "archivo desconocido"
    raw = (obj.get("text") or "").strip()
    lines = raw.splitlines()
    if len(lines) > MAX_PREVIEW_LINES:
        lines = lines[:MAX_PREVIEW_LINES] + ["..."]
    quoted = "\n".join("> " + ln for ln in lines) if lines else "> (sin contenido)"
    return f"📄 Archivo cargado: **{domain}**\n\n{quoted}\n"

def process_file(path: Path, in_place: bool, make_backup: bool):
    text = path.read_text(encoding="utf-8", errors="ignore")
    modified = False
    total_conv = 0

    sections = list(find_sections(text))
    # trabajamos de atrás hacia delante
    for s_start, s_end in reversed(sections):
        sec = text[s_start:s_end]
        dicts = find_balanced_dicts(sec)
        if not dicts:
            continue

        # Vamos a sustituir solo los bloques que sean tether_quote
        new_sec = sec
        offset = 0
        for a, b in dicts:
            a += offset; b += offset
            block = new_sec[a:b]
            if not IS_TETHER_RE.search(block):
                continue
            obj = parse_json_like(block)
            if not isinstance(obj, dict) or str(obj.get("content_type")).lower() != "tether_quote":
                continue
            rendered = render_quote(obj)

            # Si el encabezado actual no es Assistant, lo reemplazamos por ### Assistant antes del render
            # Detecta primera línea de la sección
            first_nl = new_sec.find("\n")
            header_line = new_sec[:first_nl] if first_nl != -1 else new_sec
            header_is_assistant = header_line.strip().lower().startswith("### assistant")
            prefix = "" if header_is_assistant else "### Assistant\n\n"

            new_sec = new_sec[:a] + (prefix + rendered) + new_sec[b:]
            offset += len(prefix + rendered) - (b - a)
            total_conv += 1
            modified = True

        if modified:
            text = text[:s_start] + new_sec + text[s_end:]

    if in_place and modified:
        if make_backup:
            bak = path.with_suffix(path.suffix + ".bak")
            if not bak.exists():
                shutil.copy2(path, bak)
        path.write_text(text, encoding="utf-8")
    return total_conv

def walk_md(root: Path):
    for p in root.rglob("*.md"):
        if any(x in p.parts for x in (".obsidian", ".git")):
            continue
        yield p

def main():
    ap = argparse.ArgumentParser(description="Convierte bloques tether_quote en fragmentos legibles dentro de ### User/Assistant/Tool.")
    ap.add_argument("vault", help="Carpeta raíz del Vault")
    ap.add_argument("--in-place", action="store_true", help="Escribir cambios")
    ap.add_argument("--no-backup", action="store_true", help="No crear .bak")
    args = ap.parse_args()

    vault = Path(args.vault).expanduser().resolve()
    total = 0
    for md in walk_md(vault):
        conv = process_file(md, args.in_place, not args.no_backup)
        if conv:
            print(f"✔ {md.relative_to(vault)} — {conv} tether_quote convertido(s)")
            total += conv
    print(f"\nTotal convertidos: {total}")
    if not args.in_place:
        print("(Dry-run: sin escribir cambios, añade --in-place)")

if __name__ == "__main__":
    main()
