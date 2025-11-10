#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RoleBlockExtractor — Limpia dicts estilo Python dentro de bloques ### User/### Assistant/### Tool.
Convierte 'audio_transcription' en texto legible y resume pointers.

Uso:
  python RoleBlockExtractor.py /ruta/al/vault --in-place --keep-json

Opciones:
  --dry-run     Solo informa, no escribe cambios
  --in-place    Escribe cambios en los .md (crea .bak por defecto)
  --no-backup   No crear .bak
  --keep-json   Guarda el dict original colapsado en <details>
  --ext .md     Extensión a procesar (por defecto .md)
"""

import argparse, os, re, sys, shutil, ast, json
from pathlib import Path
from typing import List, Tuple, Optional

# Encabezados de rol (User, Assistant, Tool, etc.)
ROLE_HDR_RE = re.compile(r"(?m)^###\s+(User|Assistant|Tool)\s*$")
NEXT_HDR_RE  = re.compile(r"(?m)^(?=###\s+[^ \n]+)")
# Cachos {...} incluso multilínea; no codiciosos para catch múltiple
DICT_RE = re.compile(r"\{.*?\}", re.DOTALL)

def normalize_newlines(s: str) -> str:
    return s.replace("\r\n","\n").replace("\r","\n")

def find_role_blocks(text: str) -> List[Tuple[int,int,str]]:
    out = []
    for m in ROLE_HDR_RE.finditer(text):
        start = m.start()
        n = NEXT_HDR_RE.search(text, pos=m.end())
        end = n.start() if n else len(text)
        out.append((start, end, text[start:end]))
    return out

def parse_dicts_from_block(body: str) -> List[dict]:
    """
    Devuelve lista de dicts parseados:
    - Busca TODOS los {...} en el body
    - Intenta ast.literal_eval (comillas simples) y si no, json.loads
    - Filtra a solo dicts
    """
    objs = []
    for m in DICT_RE.finditer(body):
        chunk = m.group(0).strip()
        # Primero literal_eval, porque tu input viene con 'comillas simples'
        try:
            val = ast.literal_eval(chunk)
            if isinstance(val, dict):
                objs.append(val)
                continue
            if isinstance(val, (list, tuple)):
                for x in val:
                    if isinstance(x, dict):
                        objs.append(x)
                continue
        except Exception:
            pass
        # Luego JSON normal por si acaso
        try:
            val = json.loads(chunk)
            if isinstance(val, dict):
                objs.append(val)
        except Exception:
            pass
    return objs

def render_audio_transcription(obj: dict) -> Optional[str]:
    if str(obj.get("content_type") or "").lower() != "audio_transcription":
        return None
    text = (obj.get("text") or "").strip()
    # aplasta saltos raros
    text = " ".join(text.split())

    # algunos bloques traen metadatos anidados en otro objeto, a veces no.
    meta = obj.get("metadata") or {}
    start = meta.get("start") or meta.get("start_timestamp")
    end   = meta.get("end") or meta.get("end_timestamp")
    duration = None
    try:
        if start is not None and end is not None:
            duration = float(end) - float(start)
    except Exception:
        duration = None

    info = []
    if duration and duration > 0:
        info.append(f"{duration:.2f}s")

    info_txt = f" ({', '.join(info)})" if info else ""
    return f"🎙️ Transcripción de audio{info_txt}:\n\"{text}\"\n"

def render_asset_pointer(obj: dict) -> Optional[str]:
    """
    Resume pointers para que no estorben. Muestra formato, tamaño y, si hay, duración.
    Acepta tanto 'audio_asset_pointer' como 'real_time_user_audio_video_asset_pointer'.
    """
    ct = str(obj.get("content_type") or "").lower()
    if ct not in ("audio_asset_pointer", "real_time_user_audio_video_asset_pointer"):
        return None

    meta = obj.get("metadata") or {}
    fmt = meta.get("format") or obj.get("format")
    size = meta.get("size_bytes") or obj.get("size_bytes")
    start = meta.get("start") or meta.get("start_timestamp")
    end   = meta.get("end") or meta.get("end_timestamp")
    dur = None
    try:
        if start is not None and end is not None:
            dur = float(end) - float(start)
    except Exception:
        pass

    bits = []
    if fmt: bits.append(f"formato={fmt}")
    if size: bits.append(f"tamaño={size}")
    if dur and dur > 0: bits.append(f"duración={dur:.2f}s")
    hint = ", ".join(bits) if bits else "sin-metadata"
    label = "Audio pointer" if ct == "audio_asset_pointer" else "RT audio/video pointer"
    return f"• {label}: {hint}\n"

def summarize_unknown(obj: dict) -> str:
    fields = []
    for k in ("content_type","name","domain","url","type","tool","tool_name"):
        if obj.get(k):
            fields.append(f"{k}={repr(str(obj.get(k)))[:80]}")
    return f"Tool-Block: {', '.join(fields) if fields else 'sin-pistas'}\n"

RENDERERS = (render_audio_transcription, render_asset_pointer)

def transform_role_block(raw_block: str, keep_json: bool) -> str:
    """
    Mantiene el mismo encabezado (### User / ### Assistant / ### Tool),
    reescribe el cuerpo: reemplaza dicts por texto legible.
    Si el bloque tenía texto normal además de dicts, se conserva.
    """
    parts = raw_block.splitlines()
    if not parts:
        return raw_block

    header = parts[0].strip()  # ej. "### User"
    body   = "\n".join(parts[1:])

    objs = parse_dicts_from_block(body)
    if not objs:
        # nada que transformar
        return raw_block

    # Vamos a construir un bloque “limpio”:
    # 1) Quitamos todos los dicts del body original
    body_clean = DICT_RE.sub("", body).strip()
    # 2) Añadimos rendereos legibles por cada dict
    rendered_chunks = []
    for obj in objs:
        out = None
        for r in RENDERERS:
            out = r(obj)
            if out:
                break
        if not out:
            out = summarize_unknown(obj)
        if keep_json:
            out += "\n<details>\n<summary>dict original</summary>\n\n```json\n" + json.dumps(obj, ensure_ascii=False, indent=2) + "\n```\n</details>\n"
        rendered_chunks.append(out)

    # 3) Ensamblar: encabezado + cuerpo limpio + chunks
    lines = [header, ""]
    if body_clean:
        lines.append(body_clean)
        lines.append("")
    lines.extend(rendered_chunks)
    if not lines[-1].endswith("\n"):
        lines.append("")
    return "\n".join(lines)

def process_file(path: Path, in_place: bool, keep_json: bool, make_backup: bool) -> Tuple[bool,int]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    blocks = find_role_blocks(text)
    if not blocks:
        return False, 0

    changed_text = text
    changed_any = False
    count = 0

    # Reemplazar desde el final para no romper offsets
    for start, end, raw in reversed(blocks):
        new_block = transform_role_block(raw, keep_json=keep_json)
        if new_block != raw:
            changed_text = changed_text[:start] + new_block + changed_text[end:]
            changed_any = True
            count += 1

    if in_place and changed_any:
        if make_backup:
            bak = path.with_suffix(path.suffix + ".bak")
            if not bak.exists():
                shutil.copy2(path, bak)
        path.write_text(changed_text, encoding="utf-8")

    return changed_any, count

def walk_md(root: Path, ext: str) -> list[Path]:
    return [p for p in root.rglob("*") if p.is_file() and p.suffix.lower() == ext.lower()]

def main():
    ap = argparse.ArgumentParser(description="Limpia dicts en bloques ### User/Assistant/Tool (audio_transcription, pointers, etc.)")
    ap.add_argument("root", help="Carpeta raíz (Vault) o carpeta con .md")
    ap.add_argument("--ext", default=".md", help="Extensión de notas (por defecto .md)")
    ap.add_argument("--dry-run", action="store_true", help="No escribe cambios, solo informa")
    ap.add_argument("--in-place", action="store_true", help="Escribe cambios en los .md")
    ap.add_argument("--no-backup", action="store_true", help="No crear .bak")
    ap.add_argument("--keep-json", action="store_true", help="Añadir dict original colapsado")
    args = ap.parse_args()

    root = Path(args.root).expanduser().resolve()
    if not root.is_dir():
        sys.exit(f"❌ Carpeta no válida: {root}")

    files = walk_md(root, args.ext)
    if not files:
        print("No se encontraron archivos.")
        return

    print(f"Escaneando {len(files)} archivos con {args.ext}...\n")
    total_blocks = 0
    changed_files = 0

    for md in files:
        changed, count = process_file(
            md,
            in_place=args.in_place and not args.dry_run,
            keep_json=args.keep_json,
            make_backup=not args.no_backup,
        )
        if count:
            total_blocks += count
            if changed:
                changed_files += 1
                print(f"✔ {md} — {count} bloque(s) reescrito(s)")
            else:
                print(f"· {md} — {count} bloque(s) detectado(s) (sin cambios)")

    print("\nResumen:")
    print(f"- Archivos con cambios: {changed_files}")
    print(f"- Bloques de rol reescritos: {total_blocks}")
    if args.dry_run:
        print("(Dry-run: no se escribieron cambios)")

if __name__ == "__main__":
    main()
