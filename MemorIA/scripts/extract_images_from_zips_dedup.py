#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extract_images_from_zips_dedup.py — Extrae imágenes únicas de varios ZIPs de backup,
deduplicando por hash SHA256 y manteniendo el nombre base original.

Uso:
  python extract_images_from_zips_dedup.py /ruta/con/backups /ruta/de/salida
"""

import zipfile
import os
import sys
import hashlib
from pathlib import Path
import shutil

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}

def sha256_filelike(f, chunk_size=65536):
    """Calcula SHA256 de un objeto file-like abierto en modo binario."""
    h = hashlib.sha256()
    for chunk in iter(lambda: f.read(chunk_size), b""):
        h.update(chunk)
    return h.hexdigest()

def extract_unique_images(zip_path: Path, out_dir: Path, seen_hashes: set):
    """
    Extrae imágenes únicas de un zip a out_dir.
    Evita duplicados por hash.
    Devuelve (extraídas, saltadas).
    """
    extracted, skipped = 0, 0
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            for name in zf.namelist():
                ext = Path(name).suffix.lower()
                if ext not in IMAGE_EXTS:
                    continue
                base = Path(name).name
                try:
                    with zf.open(name) as src:
                        data = src.read()
                        h = hashlib.sha256(data).hexdigest()
                        if h in seen_hashes:
                            skipped += 1
                            continue
                        seen_hashes.add(h)
                        dest = out_dir / base
                        # Si el archivo base ya existe (mismo nombre, distinto hash),
                        # añadimos sufijo para evitar colisión de distinto contenido
                        counter = 1
                        while dest.exists():
                            dest = out_dir / f"{dest.stem}_{counter}{dest.suffix}"
                            counter += 1
                        with open(dest, "wb") as dst:
                            dst.write(data)
                        extracted += 1
                except Exception as e:
                    print(f"[!] Error al leer {name} en {zip_path.name}: {e}")
    except Exception as e:
        print(f"[x] Error procesando {zip_path}: {e}")
    return extracted, skipped

def main():
    if len(sys.argv) < 3:
        print("Uso: python extract_images_from_zips_dedup.py <carpeta_zips> <carpeta_salida>")
        sys.exit(1)

    zips_dir = Path(sys.argv[1]).expanduser().resolve()
    out_dir = Path(sys.argv[2]).expanduser().resolve()

    if not zips_dir.is_dir():
        sys.exit(f"❌ Carpeta no válida: {zips_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)

    zips = list(zips_dir.glob("*.zip"))
    if not zips:
        sys.exit("No se encontraron archivos .zip en la carpeta indicada.")

    print(f"🗜️  Procesando {len(zips)} ZIPs...\n")

    seen_hashes = set()
    total_extracted, total_skipped = 0, 0

    for zp in sorted(zips):
        extracted, skipped = extract_unique_images(zp, out_dir, seen_hashes)
        total_extracted += extracted
        total_skipped += skipped
        print(f"✔ {zp.name}: {extracted} nuevas, {skipped} duplicadas.")

    print("\nResumen final:")
    print(f"- Carpeta salida: {out_dir}")
    print(f"- Imágenes únicas extraídas: {total_extracted}")
    print(f"- Duplicados omitidos: {total_skipped}")
    print(f"- Total único: {len(seen_hashes)}\n")

if __name__ == "__main__":
    main()
