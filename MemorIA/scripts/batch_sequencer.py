#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Batch sequencer for ChatGPT → Obsidian imports.
Robusto con gizmo_map:
- Acepta --gizmo-map <ruta> en CLI
- Si no se da, busca gizmo_map.json junto al script
- Si no existe, pregunta; ENTER omite de verdad
- Imprime la ruta final elegida o 'none'
"""

import os, sys, json, shutil, subprocess, argparse
from pathlib import Path
from typing import List, Optional

def say(msg: str = ""): print(msg, flush=True)

def ask_path_optional(prompt: str) -> Optional[Path]:
    try:
        raw = input(prompt).strip().strip('"').strip("'")
    except EOFError:
        return None
    if not raw:
        return None
    p = Path(raw).expanduser()
    return p if p.exists() and p.is_file() else None

def ask_choice(prompt: str, choices: List[str], default: str | None = None) -> str:
    chs = "/".join(choices)
    while True:
        raw = input(f"{prompt} ({chs}" + (f", ENTER={default}" if default else "") + "): ").strip().lower()
        if not raw and default: return default
        for c in choices:
            if raw == c.lower():
                return c
        say("⚠️  Opción no válida.")

def copy_template(dst_root: Path, template_dir: Path | None):
    dst_root.mkdir(parents=True, exist_ok=True)
    if template_dir and template_dir.exists():
        for item in template_dir.iterdir():
            target = dst_root / item.name
            if item.is_dir():
                shutil.copytree(item, target, dirs_exist_ok=True)
            else:
                shutil.copy2(item, target)
    else:
        (dst_root / "Conversaciones").mkdir(parents=True, exist_ok=True)
        (dst_root / "_tags").mkdir(parents=True, exist_ok=True)
        (dst_root / "_index.md").write_text("# Índice\n", encoding="utf-8")


def run_cmd(args: List[str], cwd: Path | None = None):
    say("→ " + " ".join([str(a) for a in args]))
    subprocess.check_call(args, cwd=str(cwd) if cwd else None)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gizmo-map", dest="gizmo_map", default=None, help="Ruta a gizmo_map.json (opcional)")
    args = ap.parse_args()

    here = Path(__file__).resolve().parent
    splitter = here / "split_chatgpt_export.py"
    cleaner  = here / "vault_cleaner.py"
    tagmap   = here / "sample_tag_map.json"
    template = here / "obsidian_vault_template"

    for p in [splitter, cleaner]:
        if not p.exists():
            say(f"❌ Falta: {p}")
            sys.exit(2)

    say("=== ChatGPT → Obsidian (Batch Sequencer) ===\n")

    # Recolectar entradas
    mode = ask_choice("¿Qué quieres importar?", ["carpeta", "lista"], default="carpeta" )
    export_paths: List[Path] = []

    if mode == "carpeta":
        root = Path(input("Arrastra la carpeta con los exports y ENTER: ").strip().strip('"').strip("'"))
        if not root.exists() or not root.is_dir():
            say("❌ Carpeta no válida."); sys.exit(2)
        exts = {".zip", ".json", ".html", ".htm"}
        for p in sorted(root.rglob("*")):
            if p.is_file() and p.suffix.lower() in exts:
                export_paths.append(p)
    else:
        say("Pega rutas de archivos (ZIP/JSON/HTML), una por línea. Línea vacía para terminar:")
        while True:
            try:
                line = input().strip().strip('"').strip("'")
            except EOFError:
                break
            if not line: break
            p = Path(line).expanduser()
            if p.exists() and p.is_file():
                export_paths.append(p)
            else:
                say(f"⚠️  Ignoro (no existe): {p}")

    if not export_paths:
        say("No encontré archivos válidos que importar.")
        sys.exit(2)

    # Carpeta base
    base_dir = Path(input("Carpeta base donde crear los Vaults: ").strip().strip('"').strip("'"))
    base_dir.mkdir(parents=True, exist_ok=True)

    raw_vault     = base_dir / "RAW_VAULT"
    merged_vault  = base_dir / "MERGED_VAULT"
    reverse_vault = base_dir / "REVERSE_VAULT"

    # Preferencias mínimas
    date_field   = ask_choice("Fecha principal en YAML?", ["create", "update"], default="create")
    include_both = True

    # tag-map si existe
    tagmap_arg: List[str] = []
    if tagmap.exists():
        try:
            json.loads(tagmap.read_text(encoding="utf-8"))
            tagmap_arg = ["--tag-map", str(tagmap)]
        except Exception:
            pass

    # Resolver gizmo-map
    gizmo_arg: List[str] = []
    gm_path: Optional[Path] = None
    if args.gizmo_map:
        p = Path(args.gizmo_map).expanduser()
        if p.exists() and p.is_file():
            gm_path = p
    if gm_path is None:
        default_map = here / "gizmo_map.json"
        if default_map.exists() and default_map.is_file():
            gm_path = default_map
    if gm_path is None:
        gm_path = ask_path_optional("Ruta a gizmo_map.json (ENTER para omitir): ")
    if gm_path is not None:
        try:
            json.loads(gm_path.read_text(encoding="utf-8"))
            gizmo_arg = ["--gizmo-map", str(gm_path)]
            say(f"ℹ️  Usando gizmo_map: {gm_path}")
        except Exception:
            say("⚠️  gizmo_map no es JSON válido; sigo sin él.")
            gm_path = None
    if gm_path is None:
        say("ℹ️  Sin gizmo_map. Project_name saldrá 'none' cuando no haya match.")

    # RAW
    say("\n▶ Preparando RAW_VAULT…")
    copy_template(raw_vault, template if template.exists() else None)

    for i, exp in enumerate(export_paths, 1):
        say(f"\n[{i}/{len(export_paths)}] Importando: {exp}")
        splitter_cmd = [
            sys.executable, str(splitter),
            str(exp),
            str((raw_vault / "Conversaciones").resolve()),
            *tagmap_arg, *gizmo_arg,
            "--make-index", "--tag-indexes", "--by-year", "--by-month",
            "--keep-versions", "--suffix-on-duplicate", "--no-dedupe", "--skip-identical",
            "--date-field", date_field, "--include-both-dates",
        ]
        run_cmd(splitter_cmd)

    # MERGED
    say("\n▶ Creando MERGED_VAULT…")
    copy_template(merged_vault, template if template.exists() else None)
    run_cmd([sys.executable, str(cleaner), str(raw_vault), str(merged_vault), "--by-year", "--by-month", "--merge", "--verbose"])

    # REVERSE
    say("\n▶ Creando REVERSE_VAULT…")
    copy_template(reverse_vault, template if template.exists() else None)
    run_cmd([sys.executable, str(cleaner), str(raw_vault), str(reverse_vault), "--by-year", "--by-month", "--merge", "--reverse-blocks", "--verbose"])

    say("\n✅ Hecho.")
    say(f"RAW_VAULT     → {raw_vault}")
    say(f"MERGED_VAULT  → {merged_vault}")
    say(f"REVERSE_VAULT → {reverse_vault}")

if __name__ == "__main__":
    main()
