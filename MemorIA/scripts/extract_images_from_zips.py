#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extract_images_from_zips.py — Extrae todas las imágenes (.png, .jpg, .jpeg, .webp)
de múltiples archivos ZIP de backup a una carpeta única elegida por el usuario.

Uso:
  python extract_images_from_zips.py /ruta/con/backups /ruta/de/salida

Ejemplo:
  python extract_images_from_zips.py ~/Backups ~/VaultAssets/img
"""

import zipfile
import os
import sys
from pathlib import Path
import shutil

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}

def extract_images_from_zip(zip_path: Path, out_dir: Path):
    """
    Extrae imágenes de un zip a out_dir.
    Retorna lista de nombres extraídos.
    """
    extracted = []
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            for name in zf.namelist():
                ext = Path(name).suffix.lower()
                if ext in IMAGE_EXTS:
                    # Normalizamos nombre
                    base = Path(name).name
                    dest = out_dir / base
                    # Si ya existe, genera variante única
                    counter = 1
                    while dest.exists():
                        dest = out_dir / f"{dest.stem}_{counter}{dest.suffix}"
                        counter += 1
                    with zf.open(name) as src, open(dest, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    extracted.append(dest.name)
    except Exception as e:
        print(f"[x] Error procesando {zip_path}: {e}")
    return extracted

def main():
    if len(sys.argv) < 3:
        print("Uso: python extract_images_from_zips.py <carpeta_zips> <carpeta_salida>")
        sys.exit(1)

    zips_dir = Path(sys.argv[1]).expanduser().resolve()
    out_dir = Path(sys.argv[2]).expanduser().resolve()

    if not zips_dir.is_dir():
        sys.exit(f"❌ Carpeta no válida: {zips_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)

    zips = list(zips_dir.glob("*.zip"))
    if not zips:
        sys.exit("No se encontraron archivos .zip en la carpeta indicada.")

    total_imgs = 0
    print(f"🗜️  Procesando {len(zips)} archivos ZIP...\n")

    for zp in zips:
        extracted = extract_images_from_zip(zp, out_dir)
        if extracted:
            total_imgs += len(extracted)
            print(f"✔ {zp.name}: {len(extracted)} imágenes extraídas.")
        else:
            print(f"· {zp.name}: sin imágenes.")

    print("\nResumen:")
    print(f"Carpeta salida: {out_dir}")
    print(f"Total de imágenes extraídas: {total_imgs}")

if __name__ == "__main__":
    main()
