#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Parsea el CSV crudo de inforealdecine.com (peliculas_raw.csv, en esta misma
carpeta) y genera peliculas.csv con encabezados en la carpeta raiz del proyecto.

Uso (desde cualquier lado):
    python scripts/build_csv.py
"""
import csv
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RAW  = os.path.join(HERE, "peliculas_raw.csv")
OUT  = os.path.join(ROOT, "peliculas.csv")

# Orden real de columnas en el CSV crudo (no trae encabezados)
COLS = ["titulo", "director", "anio", "duracion", "link_pelicula",
        "letterboxd", "tags", "poster", "extra1", "extra2"]
# Columnas que conservamos (descarta extra1/extra2, que vienen vacias)
KEEP = ["titulo", "director", "anio", "duracion", "link_pelicula",
        "letterboxd", "tags", "poster"]

rows = []
with open(RAW, "r", encoding="utf-8", newline="") as f:
    for r in csv.reader(f):
        r = (r + [""] * len(COLS))[:len(COLS)]
        rows.append(r)

idx = [COLS.index(c) for c in KEEP]
with open(OUT, "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f)
    w.writerow(KEEP)
    for r in rows:
        w.writerow([r[i].strip() for i in idx])

con_lb = sum(1 for r in rows if "letterboxd.com" in r[5])
print(f"Filas: {len(rows)} | con Letterboxd: {con_lb} | sin: {len(rows) - con_lb}")
print(f"Generado: {OUT}")
