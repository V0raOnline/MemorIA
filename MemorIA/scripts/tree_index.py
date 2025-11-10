#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tree_index.py — Índice tipo árbol por proyecto con wikilinks (Obsidian)
Agrupa: Project_name → Año → Mes → Notas (ordenadas por fecha desc).

Uso básico:
  python tree_index.py /ruta/al/MERGED_VAULT

Opciones:
  --out _tree_index.md        Archivo de salida dentro del vault (por defecto)
  --max-per-month 0           Límite de notas por mes (0 = sin límite)
  --conversations-dir Conversaciones   Subcarpeta a escanear
"""

import os
import re
import argparse
from pathlib import Path
from collections import defaultdict

MONTH_NAMES_ES = {
    "01": "01 · enero",
    "02": "02 · febrero",
    "03": "03 · marzo",
    "04": "04 · abril",
    "05": "05 · mayo",
    "06": "06 · junio",
    "07": "07 · julio",
    "08": "08 · agosto",
    "09": "09 · septiembre",
    "10": "10 · octubre",
    "11": "11 · noviembre",
    "12": "12 · diciembre",
}

DATE_RX = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")

def read_frontmatter(path: Path) -> dict:
    """Lectura mínima de front-matter YAML sin dependencias externas."""
    try:
        txt = path.read_text(encoding="utf-8")
    except Exception:
        return {}

    if not txt.startswith("---"):
        return {}

    # Encuentra cierre del bloque YAML
    # Acepta '---' en línea sola como cierre.
    lines = txt.splitlines()
    if len(lines) < 3:
        return {}

    fm_lines = []
    ended = False
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            ended = True
            break
        fm_lines.append(lines[i])

    if not ended:
        return {}

    fm = {}
    for raw in fm_lines:
        if ":" not in raw:
            continue
        k, v = raw.split(":", 1)
        k = k.strip()
        v = v.strip()
        # Quita comillas simples/dobles exteriores
        if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
            v = v[1:-1].strip()
        fm[k] = v
    return fm

def infer_date_from_any(path: Path, title: str) -> str:
    """Intenta date en front, filename o contenido; retorna YYYY-MM-DD o '0000-00-00'."""
    # 1) Busca en nombre de archivo
    m = DATE_RX.search(path.stem)
    if m:
        return "-".join(m.groups())

    # 2) Busca en título
    m = DATE_RX.search(title or "")
    if m:
        return "-".join(m.groups())

    # 3) Como último recurso, 0000-00-00
    return "0000-00-00"

def to_wikilink(rel_md_path: Path, title: str) -> str:
    """
    Genera [[ruta/sin_extension|Título]].
    Obsidian resuelve rutas relativas dentro del vault.
    """
    # Quita .md y usa separador POSIX
    without_ext = rel_md_path.with_suffix("").as_posix()
    # Si el título está vacío, usa el stem
    alias = title if title else rel_md_path.stem
    # Escapes livianos para barras verticales en alias
    alias = alias.replace("|", "¦")
    return f"[[{without_ext}|{alias}]]"

def collect_notes(vault_root: Path, conversations_dir: str) -> list[dict]:
    base = vault_root / conversations_dir
    out = []
    for root, _, files in os.walk(base):
        for fn in files:
            if not fn.lower().endswith(".md"):
                continue
            p = Path(root) / fn
            fm = read_frontmatter(p)
            project = (fm.get("Project_name") or "none").strip()
            title = (fm.get("title") or p.stem).strip()
            date = (fm.get("date") or "").strip()
            if not DATE_RX.match(date):
                date = infer_date_from_any(p, title)

            y, m, d = (date[0:4], date[5:7], date[8:10]) if len(date) >= 10 else ("0000","00","00")
            rel = p.relative_to(vault_root)
            out.append({
                "project": project or "none",
                "title": title,
                "date": date,
                "year": y,
                "month": m,
                "day": d,
                "rel": rel,
            })
    # orden global por fecha desc, luego título
    out.sort(key=lambda r: (r["date"], r["title"].lower()), reverse=True)
    return out

def group_by_project_year_month(rows: list[dict]):
    tree = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    counts = defaultdict(int)
    for r in rows:
        proj = r["project"]
        year = r["year"]
        month = r["month"]
        tree[proj][year][month].append(r)
        counts[proj] += 1
    return tree, counts

def render_markdown(tree, counts, max_per_month: int, conversations_dir: str) -> str:
    lines = []
    total_projects = len(tree)
    total_notes = sum(counts.values())

    lines.append("# Índice por Proyecto\n")
    lines.append(f"_Subcarpeta:_ `{conversations_dir}`  ·  _Proyectos:_ **{total_projects}**  ·  _Notas:_ **{total_notes}**\n")

    # Ordena proyectos por nombre alfabético
    for proj in sorted(tree.keys(), key=lambda s: s.lower()):
        n = counts.get(proj, 0)
        lines.append(f"\n## {proj}  ({n})\n")

        # Orden de años: descendente
        for year in sorted(tree[proj].keys(), reverse=False):
            lines.append(f"\n### {year}\n")

            # Orden de meses: descendente
            for month in sorted(tree[proj][year].keys(), reverse=False):
                month_label = MONTH_NAMES_ES.get(month, month)
                lines.append(f"\n#### {month_label}\n")

                notes = tree[proj][year][month]
                # Orden por fecha desc, luego título
                notes.sort(key=lambda r: (r['date'], r['title'].lower()), reverse=False)

                shown = 0
                for r in notes:
                    if max_per_month and shown >= max_per_month:
                        break
                    link = to_wikilink(r["rel"], r["title"])
                    # Muestra fecha completa para ordenar visual y desambiguar
                    lines.append(f"- {r['date']} — {link}")
                    shown += 1

                if max_per_month and len(notes) > max_per_month:
                    lines.append(f"- … (**{len(notes) - max_per_month}** más en este mes)")

    lines.append("")  # newline final
    return "\n".join(lines)

def main():
    ap = argparse.ArgumentParser(description="Genera un árbol de navegación por Project_name (wikilinks Obsidian).")
    ap.add_argument("vault", help="Ruta al Vault (raíz que contiene la carpeta de conversaciones)")
    ap.add_argument("--out", default="_tree_index.md", help="Archivo de salida dentro del vault")
    ap.add_argument("--max-per-month", type=int, default=0, help="Límite de notas por mes (0 = sin límite)")
    ap.add_argument("--conversations-dir", default="Conversaciones", help="Subcarpeta a escanear dentro del vault")
    args = ap.parse_args()

    vault = Path(args.vault).expanduser().resolve()
    if not vault.is_dir():
        raise SystemExit(f"[x] No existe la carpeta del vault: {vault}")

    rows = collect_notes(vault, args.conversations_dir)
    tree, counts = group_by_project_year_month(rows)
    md = render_markdown(tree, counts, args.max_per_month, args.conversations_dir)

    out_path = vault / args.out
    out_path.write_text(md, encoding="utf-8")
    print(f"✅ Índice generado: {out_path}")
    print(f"   Proyectos: {len(tree)}  ·  Notas: {sum(counts.values())}")

if __name__ == "__main__":
    main()
