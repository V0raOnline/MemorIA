#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BuildScaffoldingIndex.py — crea un índice de archivos de andamiaje ("📄 Archivo cargado: ...")
encontrados en las conversaciones del Vault.

Genera scaffolding_index.md con formato Markdown y enlaces wikilink.
"""

import re
from pathlib import Path
import argparse
from collections import defaultdict

# Detecta líneas del tipo: 📄 Archivo cargado: **Koru.md**
SCAFFOLD_RE = re.compile(r"^📄\s*Archivo\s+cargado:\s*\*\*(.+?)\*\*", re.MULTILINE)

def scan_vault(vault_path: Path):
    """
    Recorre el vault buscando líneas '📄 Archivo cargado: **nombre**'
    y devuelve {nombre: [ruta1, ruta2, ...]}.
    """
    scaffolds = defaultdict(list)
    for md in vault_path.rglob("*.md"):
        if any(x in md.parts for x in (".obsidian", ".git")):
            continue
        try:
            text = md.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for m in SCAFFOLD_RE.finditer(text):
            name = m.group(1).strip()
            scaffolds[name].append(md.relative_to(vault_path))
    return scaffolds

def build_index_text(scaffolds: dict) -> str:
    """Genera el texto Markdown del índice."""
    lines = ["# Índice de Andamiajes\n"]
    for name in sorted(scaffolds.keys(), key=str.lower):
        files = scaffolds[name]
        lines.append(f"## {name}  ({len(files)})\n")
        for f in sorted(files):
            lines.append(f"- [[{f.as_posix()}]]")
        lines.append("")  # salto de línea entre secciones
    return "\n".join(lines)

def main():
    ap = argparse.ArgumentParser(description="Crea scaffolding_index.md con el listado de andamiajes usados.")
    ap.add_argument("vault", help="Carpeta raíz del Vault con notas .md")
    args = ap.parse_args()

    vault = Path(args.vault).expanduser().resolve()
    if not vault.is_dir():
        raise SystemExit(f"❌ Carpeta no válida: {vault}")

    scaffolds = scan_vault(vault)
    if not scaffolds:
        print("No se encontraron archivos de andamiaje (líneas 📄 Archivo cargado: **...**).")
        return

    index_text = build_index_text(scaffolds)
    out_path = vault / "scaffolding_index.md"
    out_path.write_text(index_text, encoding="utf-8")

    print(f"✅ Índice generado: {out_path}")
    print(f"Andamiajes detectados: {len(scaffolds)}")
    total_refs = sum(len(v) for v in scaffolds.values())
    print(f"Conversaciones indexadas: {total_refs}")

if __name__ == "__main__":
    main()
