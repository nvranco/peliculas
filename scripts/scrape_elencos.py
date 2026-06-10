#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scraper de elencos desde Letterboxd para las peliculas de inforealdecine.com.

Lee   peliculas.csv  (en la raiz del proyecto)
Escribe elencos.csv  (en la raiz; col: pelicula, anio, actor, personaje)

Caracteristicas:
  - PROGRESO EN VIVO: muestra avance, % , velocidad y tiempo restante (ETA).
  - REANUDABLE: si lo cortas y lo volves a correr, sigue donde quedo
    (registro en  scripts/scrape_progress.csv ).
  - Reintentos con backoff ante errores de red / HTTP 429 / 5xx.
  - Escritura incremental: cada peli se guarda al instante.

Uso (desde la raiz del proyecto):
    python scripts/scrape_elencos.py            # corre todo (reanudable)
    python scripts/scrape_elencos.py --limit 25 # solo 25 pendientes (prueba)
    python scripts/scrape_elencos.py --delay 1.0

No requiere librerias externas (solo stdlib).
"""

import argparse
import csv
import os
import random
import re
import sys
import time
import urllib.error
import urllib.request

# --- Rutas ---
HERE         = os.path.dirname(os.path.abspath(__file__))
ROOT         = os.path.dirname(HERE)
INPUT_CSV    = os.path.join(ROOT, "peliculas.csv")
OUTPUT_CSV   = os.path.join(ROOT, "elencos.csv")
PROGRESS_CSV = os.path.join(HERE, "scrape_progress.csv")

# --- Parametros de red ---
USER_AGENT   = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " \
               "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
TIMEOUT      = 30          # segundos por request
MAX_RETRIES  = 5           # reintentos ante fallo
BACKOFF_BASE = 3           # segundos; espera = BACKOFF_BASE * 2**intento (+ jitter)

# Regex para el bloque de cast y los links de actor
RE_CAST_BLOCK = re.compile(r'<div class="cast-list[^"]*">(.*?)</div>', re.S)
RE_ACTOR_LINK = re.compile(
    r'<a\b([^>]*)\bclass="text-slug tooltip"[^>]*>(.*?)</a>', re.S)
RE_TITLE_ATTR = re.compile(r'title="(.*?)"', re.S)
RE_TAG        = re.compile(r'<[^>]+>')


def html_unescape(s: str) -> str:
    import html
    return html.unescape(s).replace("\xa0", " ").strip()


def fmt_dur(seg: float) -> str:
    """Formatea segundos como  HhMMm  /  MMm SSs  /  SSs ."""
    seg = int(seg)
    h, r = divmod(seg, 3600)
    m, s = divmod(r, 60)
    if h:
        return f"{h}h {m:02d}m"
    if m:
        return f"{m}m {s:02d}s"
    return f"{s}s"


def fetch(url: str) -> str:
    """Descarga la URL con reintentos y backoff. Devuelve el HTML o lanza."""
    last_err = None
    for intento in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code == 404:
                raise                     # no tiene sentido reintentar un 404
            # 429 / 5xx -> backoff
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last_err = e
        espera = BACKOFF_BASE * (2 ** intento) + random.uniform(0, 2)
        print(f"\n    ! error ({last_err}); reintento en {espera:.0f}s "
              f"({intento + 1}/{MAX_RETRIES})", flush=True)
        time.sleep(espera)
    raise last_err


def parse_cast(html: str):
    """Devuelve lista de (actor, personaje) a partir del HTML del film."""
    m = RE_CAST_BLOCK.search(html)
    if not m:
        return []
    out = []
    for attrs, text in RE_ACTOR_LINK.findall(m.group(1)):
        actor = html_unescape(RE_TAG.sub("", text))
        if not actor:
            continue
        tm = RE_TITLE_ATTR.search(attrs)
        personaje = html_unescape(tm.group(1)) if tm else ""
        out.append((actor, personaje))
    return out


def load_progress() -> set:
    """Set de URLs ya procesadas (para reanudar)."""
    done = set()
    if os.path.exists(PROGRESS_CSV):
        with open(PROGRESS_CSV, "r", encoding="utf-8", newline="") as f:
            for row in csv.reader(f):
                if row:
                    done.add(row[0])
    return done


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0,
                    help="procesar solo N peliculas pendientes (0 = todas)")
    ap.add_argument("--delay", type=float, default=0.8,
                    help="segundos de pausa entre requests (default 0.8)")
    args = ap.parse_args()

    if not os.path.exists(INPUT_CSV):
        sys.exit(f"No encuentro {INPUT_CSV}")

    # Cargar peliculas con link de letterboxd
    pelis = []
    with open(INPUT_CSV, "r", encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            url = (r.get("letterboxd") or "").strip()
            if "letterboxd.com" in url:
                pelis.append((r.get("titulo", "").strip(),
                              r.get("anio", "").strip(), url))

    done = load_progress()
    pendientes = [p for p in pelis if p[2] not in done]
    if args.limit:
        pendientes = pendientes[:args.limit]

    total = len(pendientes)
    print(f"Total con Letterboxd: {len(pelis)} | ya hechas: {len(done)} | "
          f"a procesar ahora: {total}", flush=True)
    if total == 0:
        print("Nada pendiente. Listo.")
        return

    # Abrir salidas en modo append; escribir header si el archivo es nuevo
    new_out = not os.path.exists(OUTPUT_CSV) or os.path.getsize(OUTPUT_CSV) == 0
    out_f  = open(OUTPUT_CSV,   "a", encoding="utf-8", newline="")
    prog_f = open(PROGRESS_CSV, "a", encoding="utf-8", newline="")
    out_w  = csv.writer(out_f)
    prog_w = csv.writer(prog_f)
    if new_out:
        out_w.writerow(["pelicula", "anio", "actor", "personaje"])

    t0 = time.time()
    actores_total = 0
    try:
        for i, (titulo, anio, url) in enumerate(pendientes, 1):
            n_cast = 0
            try:
                html = fetch(url)
                cast = parse_cast(html)
                for actor, personaje in cast:
                    out_w.writerow([titulo, anio, actor, personaje])
                out_f.flush()
                n_cast = len(cast)
                actores_total += n_cast
                prog_w.writerow([url, "ok", n_cast]); prog_f.flush()
            except urllib.error.HTTPError as e:
                estado = "404" if e.code == 404 else f"http{e.code}"
                prog_w.writerow([url, estado, 0]); prog_f.flush()
                n_cast = -1   # marca error visible
            except Exception as e:
                # No marcar como hecha: en la proxima corrida se reintenta
                print(f"\n[{i}/{total}] {titulo} -> FALLO definitivo: {e}",
                      flush=True)
                time.sleep(args.delay + random.uniform(0, 0.4))
                continue

            # --- linea de progreso con ETA ---
            transcurrido = time.time() - t0
            vel = i / transcurrido                       # pelis por segundo
            restantes = total - i
            eta = restantes / vel if vel > 0 else 0
            pct = i * 100 / total
            cast_str = "404/err" if n_cast < 0 else f"{n_cast:>2} act"
            linea = (f"\r[{i:>4}/{total}] {pct:5.1f}% | "
                     f"{vel*60:4.1f} pelis/min | "
                     f"ETA {fmt_dur(eta):>7} | "
                     f"{cast_str} | {titulo[:40]:<40}")
            # padding para limpiar restos de lineas largas previas
            sys.stdout.write(linea + " " * 6)
            sys.stdout.flush()
            time.sleep(args.delay + random.uniform(0, 0.4))
    finally:
        out_f.close()
        prog_f.close()

    total_t = time.time() - t0
    print(f"\nListo. {total} peliculas en {fmt_dur(total_t)} | "
          f"{actores_total} filas de elenco agregadas.", flush=True)


if __name__ == "__main__":
    main()
