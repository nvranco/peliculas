# -*- coding: utf-8 -*-
"""
Utilidades de grafo para el tablero de cine argentino.

Construye la red de colaboracion de actores (nodos = actores, arista = actuaron
en la misma pelicula) y calcula las metricas del paper de Watts & Strogatz (1998):
longitud caracteristica de camino L y coeficiente de clustering C, comparados
contra un grafo aleatorio equivalente (small-world).

Las funciones de carga/construccion usan el cache de Streamlit para no recalcular
en cada interaccion.
"""

from __future__ import annotations

import math
import os
import random
from collections import defaultdict
from itertools import combinations

import networkx as nx
import pandas as pd
import streamlit as st

# Rutas a los CSV (en la raiz del proyecto, un nivel arriba de dashboard/)
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ELENCOS_CSV = os.path.join(ROOT, "elencos.csv")
PELIS_CSV = os.path.join(ROOT, "peliculas.csv")

# Por encima de este nº de nodos, L y C se estiman por muestreo (son caros exactos)
L_EXACT_MAX_NODES = 2500
L_SAMPLE_SIZE = 400
C_TRIALS = 5000  # muestras para estimar el clustering en grafos grandes


# --------------------------------------------------------------------------- #
# Carga de datos
# --------------------------------------------------------------------------- #
@st.cache_data(show_spinner=False)
def load_elencos(mtime: float) -> pd.DataFrame:
    """Lee elencos.csv y lo enriquece con metadata de peliculas.csv.

    El parametro mtime solo sirve para invalidar el cache cuando el archivo
    cambia (el scrape sigue creciendo).
    """
    df = pd.read_csv(ELENCOS_CSV, dtype=str).fillna("")
    df["actor"] = df["actor"].str.strip()
    df["pelicula"] = df["pelicula"].str.strip()
    df = df[(df["actor"] != "") & (df["pelicula"] != "")]
    df["anio_num"] = pd.to_numeric(df["anio"], errors="coerce")

    # Join opcional con peliculas.csv para filtros por director / tags
    if os.path.exists(PELIS_CSV):
        pelis = pd.read_csv(PELIS_CSV, dtype=str).fillna("")
        pelis = pelis.rename(columns={"titulo": "pelicula"})
        cols = ["pelicula"] + [c for c in ("director", "tags", "duracion") if c in pelis.columns]
        pelis = pelis[cols].drop_duplicates(subset="pelicula")
        df = df.merge(pelis, on="pelicula", how="left").fillna("")
    return df


def elencos_mtime() -> float:
    return os.path.getmtime(ELENCOS_CSV) if os.path.exists(ELENCOS_CSV) else 0.0


# --------------------------------------------------------------------------- #
# Construccion del grafo
# --------------------------------------------------------------------------- #
@st.cache_resource(show_spinner=False)
def build_graph(mtime: float, year_range: tuple, min_films: int,
                director: str, tag: str) -> nx.Graph:
    """Construye la red de coactuacion sobre el subconjunto filtrado.

    Los parametros entran en la clave de cache, asi cada combinacion de filtros
    se calcula una sola vez. mtime invalida cuando crece el CSV.

    Aristas: atributo 'films' = lista de (pelicula, anio) que conectan ese par.
    Nodos:   atributo 'films' = set de peliculas del actor.
    """
    df = load_elencos(mtime)

    lo, hi = year_range
    if lo is not None and hi is not None:
        # Conserva filas sin anio solo si el rango cubre todo el dataset
        mask = df["anio_num"].between(lo, hi)
        df = df[mask]
    if director:
        df = df[df.get("director", "").str.contains(director, case=False, na=False)]
    if tag:
        df = df[df.get("tags", "").str.contains(tag, case=False, na=False)]

    # pelicula -> {actores}, y conteo de peliculas por actor
    cast = defaultdict(set)
    peli_anio = {}
    for row in df.itertuples(index=False):
        cast[row.pelicula].add(row.actor)
        peli_anio[row.pelicula] = getattr(row, "anio", "")

    films_por_actor = defaultdict(set)
    for peli, actores in cast.items():
        for a in actores:
            films_por_actor[a].add(peli)

    G = nx.Graph()
    for peli, actores in cast.items():
        anio = peli_anio.get(peli, "")
        for a, b in combinations(sorted(actores), 2):
            if G.has_edge(a, b):
                G[a][b]["films"].append((peli, anio))
            else:
                G.add_edge(a, b, films=[(peli, anio)])

    # Filtro de grado minimo = nº minimo de peliculas del actor
    if min_films > 1:
        quitar = [a for a, fs in films_por_actor.items() if len(fs) < min_films]
        G.remove_nodes_from(quitar)

    for a in G.nodes:
        G.nodes[a]["films"] = films_por_actor.get(a, set())
        G.nodes[a]["n_films"] = len(films_por_actor.get(a, set()))
    return G


def largest_component(G: nx.Graph) -> nx.Graph:
    """Devuelve el subgrafo del componente conexo mas grande (LCC)."""
    if G.number_of_nodes() == 0:
        return G
    nodes = max(nx.connected_components(G), key=len)
    return G.subgraph(nodes)


# --------------------------------------------------------------------------- #
# Metricas estilo Watts & Strogatz
# --------------------------------------------------------------------------- #
def estimate_L(G: nx.Graph, sample: int = L_SAMPLE_SIZE) -> float:
    """Estima L promediando la distancia desde una muestra de nodos.

    Usa scipy.sparse.csgraph (BFS en C), mucho mas rapido que networkx puro.
    """
    import numpy as np
    from scipy.sparse.csgraph import shortest_path

    n = G.number_of_nodes()
    if n <= 1:
        return 0.0
    A = nx.to_scipy_sparse_array(G, format="csr", dtype="int8")
    idx = np.random.default_rng(42).choice(n, size=min(sample, n), replace=False)
    dist = shortest_path(A, method="D", unweighted=True, indices=idx)
    # promedia distancias finitas y > 0 (excluye self y nodos inalcanzables)
    finite = dist[np.isfinite(dist) & (dist > 0)]
    return float(finite.mean()) if finite.size else 0.0


def compute_metrics(G: nx.Graph) -> dict:
    """Metricas globales del grafo y small-world sobre el LCC."""
    n_all = G.number_of_nodes()
    m_all = G.number_of_edges()
    if n_all == 0:
        return {"vacio": True}

    comps = list(nx.connected_components(G))
    H = G.subgraph(max(comps, key=len))
    n = H.number_of_nodes()
    m = H.number_of_edges()
    k = (2 * m / n) if n else 0.0

    exact = n <= L_EXACT_MAX_NODES

    if n <= 2:
        C_actual = 0.0
    elif exact:
        C_actual = nx.average_clustering(H)
    else:
        # Estimacion por muestreo (rapida en grafos grandes)
        from networkx.algorithms.approximation import average_clustering as approx_C
        C_actual = approx_C(H, trials=C_TRIALS, seed=42)
    C_random = (k / n) if n else 0.0

    if n <= 1:
        L_actual = 0.0
    elif exact:
        L_actual = nx.average_shortest_path_length(H)
    else:
        L_actual = estimate_L(H)
    L_random = (math.log(n) / math.log(k)) if (n > 1 and k > 1) else float("nan")

    # Coeficiente small-world: alto clustering relativo, camino corto relativo
    if C_random > 0 and L_random and not math.isnan(L_random) and L_actual > 0:
        sigma = (C_actual / C_random) / (L_actual / L_random)
    else:
        sigma = float("nan")

    return {
        "vacio": False,
        "n_all": n_all, "m_all": m_all,
        "n_components": len(comps),
        "n": n, "m": m, "k": k,
        "density": nx.density(G),
        "C_actual": C_actual, "C_random": C_random,
        "L_actual": L_actual, "L_random": L_random,
        "L_exact": exact,
        "sigma": sigma,
    }


@st.cache_data(show_spinner=False)
def get_metrics(mtime: float, year_range: tuple, min_films: int,
                director: str, tag: str) -> dict:
    """compute_metrics cacheado por combinacion de filtros (se calcula 1 vez)."""
    G = build_graph(mtime, year_range, min_films, director, tag)
    return compute_metrics(G)


# --------------------------------------------------------------------------- #
# Rankings y distribucion
# --------------------------------------------------------------------------- #
def top_actors(G: nx.Graph, n: int = 15) -> pd.DataFrame:
    """Top actores por nº de conexiones (grado) y por nº de peliculas."""
    filas = []
    for a, deg in G.degree():
        filas.append((a, deg, G.nodes[a].get("n_films", 0)))
    df = pd.DataFrame(filas, columns=["actor", "conexiones", "peliculas"])
    return df.sort_values("conexiones", ascending=False).head(n).reset_index(drop=True)


def degree_sequence(G: nx.Graph) -> list:
    return [d for _, d in G.degree()]


# --------------------------------------------------------------------------- #
# Cadena de conexiones (seis grados de separacion)
# --------------------------------------------------------------------------- #
def shortest_chain(G: nx.Graph, a: str, b: str):
    """Devuelve (ok, mensaje, pasos).

    pasos = lista de dicts: {desde, hasta, pelicula, anio} por cada salto.
    """
    if a == b:
        return False, "Elegí dos actores distintos.", []
    if a not in G or b not in G:
        falta = a if a not in G else b
        return False, f"'{falta}' no está en el grafo (revisá los filtros).", []
    if not nx.has_path(G, a, b):
        return False, ("No hay conexión entre ambos: pertenecen a componentes "
                       "distintos de la red (con los filtros actuales)."), []

    path = nx.shortest_path(G, a, b)
    pasos = []
    for u, v in zip(path, path[1:]):
        films = G[u][v]["films"]
        peli, anio = films[0]  # una pelicula puente representativa
        pasos.append({"desde": u, "hasta": v, "pelicula": peli,
                      "anio": anio, "otras": max(0, len(films) - 1)})
    return True, "", pasos
