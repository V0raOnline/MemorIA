#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Construye un Vault LIMPIO a partir de un Vault ARCHIVO creado por split_chatgpt_export.py.

- Entrada: ARCHIVO root que contiene 'Conversaciones/' con muchas .md (posibles duplicados/versiones).
- Salida : LIMPIO root con 1 mejor nota por hilo (prefiere la más larga), opcionalmente fusionada.
- Extra  : orden inverso por bloques (User+Assistant) con --reverse-blocks.

Preserva metadatos del front-matter original (incluyendo source_project_id/source_project/tags)
al fusionar o invertir bloques, y solo actualiza title/date/source.
"""
import argparse, os, re, shutil, hashlib
from typing import Dict, List, Tuple

# ---------------- Utilidades seguras (Python 3.11+) ----------------

def normalize_text(txt: str) -> str:
    return re.sub(r"\s+", " ", (txt or "").strip())

def msg_fp(msg: Dict[str, str]) -> str:
    role = (msg.get("role", "") or "").lower()
    content_norm = normalize_text(msg.get("content", ""))
    norm = role + "::" + content_norm
    return hashlib.sha1(norm.encode("utf-8", errors="ignore")).hexdigest()

def group_blocks(messages: List[Dict[str, str]]) -> List[List[Dict[str, str]]]:
    blocks: List[List[Dict[str, str]]] = []
    cur: List[Dict[str, str]] = []
    last_role = None
    for m in messages:
        role = (m.get("role") or "").lower()
        if last_role is None or role == last_role:
            cur.append(m)
        else:
            if cur: blocks.append(cur)
            cur = [m]
        last_role = role
    if cur: blocks.append(cur)
    return blocks

def flatten_blocks(blocks: List[List[Dict[str, str]]]) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    for b in blocks:
        out.extend(b)
    return out

# ---------------- Front-matter helpers ----------------

def read_front_matter(md_path: str) -> Tuple[Dict[str, str], List[Dict[str, str]]]:
    """Devuelve (front, messages). Front es dict de claves YAML planas.
    Mensajes se leen del cuerpo '### Role' secciones.
    """
    front: Dict[str, str] = {}
    messages: List[Dict[str, str]] = []
    if not os.path.exists(md_path):
        return front, messages
    with open(md_path, "r", encoding="utf-8") as f:
        txt = f.read()
    # Parse YAML front matter simple
    if txt.startswith("---\n"):
        end = txt.find("\n---\n", 4)
        if end != -1:
            yaml = txt[4:end].splitlines()
            for line in yaml:
                if not line.strip(): continue
                if ":" in line:
                    k, v = line.split(":", 1)
                    front[k.strip()] = v.strip()
            body = txt[end+5:]
        else:
            body = txt
    else:
        body = txt
    # Parse messages in a very simple way
    parts = re.split(r"^###\s+([A-Za-z]+)\s*$", body, flags=re.MULTILINE)
    # parts = [pre, role1, block1, role2, block2, ...]
    if len(parts) > 1:
        preface = parts[0]
        for i in range(1, len(parts), 2):
            role = parts[i].strip().lower()
            content = parts[i+1].strip()
            messages.append({"role": role, "content": content})
    return front, messages

def write_merged_md(dst_path: str, front: Dict[str, str], messages: List[Dict[str, str]]) -> None:
    os.makedirs(os.path.dirname(dst_path), exist_ok=True)
    lines: List[str] = []
    lines.append("---")
    for k, v in front.items():
        lines.append(f"{k}: {v}")
    lines.append("---\n")
    for m in messages:
        role_title = (m.get("role", "unknown") or "unknown").capitalize()
        lines.append(f"### {role_title}\n")
        lines.append((m.get("content", "") or "").rstrip() + "\n")
    with open(dst_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

def safe_title_from_base(base_name: str) -> str:
    core = base_name[:-3] if base_name.lower().endswith(".md") else base_name
    title_core = core[11:] if len(core) > 11 and core[4] == "-" else core
    return title_core.replace('"', "'")

# ---------------- Programa principal ----------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("archive_root")  # RAW_VAULT
    ap.add_argument("clean_root")    # MERGED_VAULT o REVERSE_VAULT
    ap.add_argument("--merge", action="store_true")
    ap.add_argument("--reverse-blocks", action="store_true")
    ap.add_argument("--by-year", action="store_true")
    ap.add_argument("--by-month", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    conv_dir = os.path.join(args.archive_root, "Conversaciones")
    if not os.path.isdir(conv_dir):
        raise SystemExit(f"No existe carpeta: {conv_dir}")

    # Recoger todos los .md agrupados por base (sin sufijos -hXXXX, -v2, etc.)
    import glob
    files = sorted(glob.glob(os.path.join(conv_dir, "**", "*.md"), recursive=True))
    groups: Dict[str, List[Dict[str, str]]] = {}
    for path in files:
        base = os.path.basename(path)
        # base normalizado sin sufijos -h..., -v..., -t...
        base_core = re.sub(r"-(h[0-9a-f]{8}(-\d+)?|v\d+|t\d{12})(?=\.md$)", "", base, flags=re.IGNORECASE)
        # Extraer fecha YYYY-MM-DD del nombre
        m = re.match(r"(\d{4}-\d{2}-\d{2})_", base_core)
        date = m.group(1) if m else None
        # Leer front y mensajes
        front, messages = read_front_matter(path)
        groups.setdefault(base_core, []).append({
            "path": path,
            "base": base_core,
            "date": date,
            "front": front,
            "messages": messages,
            "size": os.path.getsize(path),
            "words": sum(len((mm.get("content") or "").split()) for mm in messages),
        })

    os.makedirs(args.clean_root, exist_ok=True)
    os.makedirs(os.path.join(args.clean_root, "Conversaciones"), exist_ok=True)

    for base_core, items in sorted(groups.items()):
        # Elegir campeón por palabras, luego tamaño
        items_sorted = sorted(items, key=lambda x: (x["words"], x["size"]), reverse=True)
        champion = items_sorted[0]
        date = champion["date"] or champion["front"].get("date", "0000-00-00")
        # Destino
        y, m = (date[:4], date[5:7]) if re.match(r"\d{4}-\d{2}-\d{2}", date) else ("0000", "00")

        # --- NUEVO BLOQUE ---
        # Forzamos carpeta base 'Conversaciones' dentro del vault limpio
        base_conv = os.path.join(args.clean_root, "Conversaciones")
        out_dir = base_conv
        if args.by_year:
            out_dir = os.path.join(out_dir, y)
        if args.by_month:
            out_dir = os.path.join(out_dir, m if args.by_year else f"{y}-{m}")
        
        dst = os.path.join(out_dir, base_core)
        # --- FIN DEL BLOQUE ---


        if args.merge and len(items_sorted) > 1:
            # Dedupe + merge
            seen = set()
            merged: List[Dict[str, str]] = []
            for it in items_sorted:
                for mm in it["messages"]:
                    fp = msg_fp(mm)
                    if fp not in seen:
                        merged.append(mm); seen.add(fp)

            if args.reverse_blocks:
                merged = flatten_blocks(list(reversed(group_blocks(merged))))

            # Preservar front del campeón y actualizar campos core
            front = dict(champion["front"]) if champion.get("front") else {}
            safe_title = safe_title_from_base(champion["base"])
            front["title"] = '"' + safe_title + '"'
            front["date"] = date or "0000-00-00"
            front["source"] = "archive_merge" + ("_reverse" if args.reverse_blocks else "")
            write_merged_md(dst, front, merged)
        else:
            if args.reverse_blocks:
                msgs = champion["messages"]
                rev = flatten_blocks(list(reversed(group_blocks(msgs))))
                front = dict(champion["front"]) if champion.get("front") else {}
                safe_title = safe_title_from_base(champion["base"])
                front["title"] = '"' + safe_title + '"'
                front["date"] = date or "0000-00-00"
                front["source"] = "archive_copy_reverse"
                write_merged_md(dst, front, rev)
            else:
                # copiar tal cual
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(champion["path"], dst)

    print(f"Listo. Salida: {args.clean_root}")

if __name__ == "__main__":
    main()
