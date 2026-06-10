# -*- coding: utf-8 -*-
"""
Tablero Streamlit: red de colaboracion de actores del cine argentino.

Replica el analisis de Watts & Strogatz (1998) sobre la red de actores
(small-world) y agrega filtros y una feature de "seis grados de separacion".

Correr desde la raiz del proyecto:
    streamlit run dashboard/app.py
"""

import math

import networkx as nx
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import graph_utils as gu

st.set_page_config(page_title="Cine Argentino · Red de actores",
                   page_icon="🎬", layout="wide")

# --------------------------------------------------------------------------- #
# Encabezado
# --------------------------------------------------------------------------- #
st.title("🎬 Red de colaboración del cine argentino")
st.markdown(
    "Análisis *small-world* de la red de actores (nodos = actores; una arista une "
    "a dos actores que actuaron en la **misma película**), replicando "
    "[Watts & Strogatz (1998), *Collective dynamics of 'small-world' networks*]"
    "(https://snap.stanford.edu/class/cs224w-readings/watts98smallworld.pdf). "
    "Datos scrapeados de Letterboxd a partir del catálogo de inforealdecine.com."
)

mtime = gu.elencos_mtime()
if mtime == 0:
    st.error("No encuentro `elencos.csv` en la raíz del proyecto.")
    st.stop()

df = gu.load_elencos(mtime)

# --------------------------------------------------------------------------- #
# Sidebar - Filtros
# --------------------------------------------------------------------------- #
st.sidebar.header("Filtros")

anios = df["anio_num"].dropna()
if len(anios):
    amin, amax = int(anios.min()), int(anios.max())
else:
    amin, amax = 1900, 2025
year_range = st.sidebar.slider("Años", amin, amax, (amin, amax))

min_films = st.sidebar.slider(
    "Mínimo de películas por actor", 1, 10, 1,
    help="Filtra actores con pocas apariciones (reduce ruido del grafo).")

director = st.sidebar.text_input("Director contiene", "").strip()
tag = st.sidebar.text_input("Tag/etiqueta contiene", "").strip()

st.sidebar.caption(
    f"Dataset: {df['pelicula'].nunique():,} películas · "
    f"{df['actor'].nunique():,} actores · {len(df):,} apariciones.")

# --------------------------------------------------------------------------- #
# Construccion del grafo (cacheado por combinacion de filtros)
# --------------------------------------------------------------------------- #
with st.spinner("Construyendo la red…"):
    G = gu.build_graph(mtime, tuple(year_range), min_films, director, tag)

if G.number_of_nodes() == 0:
    st.warning("Ningún actor cumple los filtros actuales. Aflojá los filtros.")
    st.stop()

with st.spinner("Calculando métricas…"):
    M = gu.get_metrics(mtime, tuple(year_range), min_films, director, tag)

# --------------------------------------------------------------------------- #
# Seccion 1 - Estadisticas generales
# --------------------------------------------------------------------------- #
st.header("📊 Estadísticas generales")

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Actores (nodos)", f"{M['n_all']:,}")
c2.metric("Colaboraciones (aristas)", f"{M['m_all']:,}")
c3.metric("Grado medio k", f"{M['k']:.1f}")
c4.metric("Componentes", f"{M['n_components']:,}")
c5.metric("Componente mayor (LCC)", f"{M['n']:,}",
          help="El análisis small-world se calcula sobre este componente conexo.")

st.subheader("Fenómeno small-world (Tabla 1 del paper)")

def fmt(x):
    return "—" if (x is None or (isinstance(x, float) and math.isnan(x))) else f"{x:.4g}"

tabla = pd.DataFrame({
    "": ["Cine argentino (LCC)"],
    "L_actual": [fmt(M["L_actual"])],
    "L_random": [fmt(M["L_random"])],
    "C_actual": [fmt(M["C_actual"])],
    "C_random": [fmt(M["C_random"])],
})
st.table(tabla.set_index(""))

colA, colB = st.columns([2, 1])
with colA:
    st.markdown(
        "- **L** (longitud característica de camino): nº medio de pasos en el camino "
        "más corto entre dos actores. **C** (clustering): qué tan probable es que dos "
        "colegas de un actor también hayan actuado juntos.\n"
        "- Una red es **small-world** cuando `L ≈ L_random` pero `C ≫ C_random`: "
        "caminos cortos como en un grafo aleatorio, pero mucho más agrupada."
    )
    if not M["L_exact"]:
        st.caption("⚠️ L estimada por muestreo (grafo grande) para mantener la "
                   "respuesta rápida.")
with colB:
    sigma = M["sigma"]
    es_sw = (not math.isnan(sigma)) and sigma > 1 and M["C_actual"] > 5 * M["C_random"]
    st.metric("Coeficiente small-world σ", fmt(sigma),
              help="σ = (C/C_random) / (L/L_random). σ ≫ 1 indica small-world.")
    if es_sw:
        st.success("✅ La red **es small-world**: muy agrupada y con caminos cortos.")
    elif not math.isnan(sigma):
        st.info("Señal small-world parcial: revisá C vs C_random.")

# --- Distribucion de grados ---
st.subheader("Distribución de grados")
seq = gu.degree_sequence(G)
fig_deg = go.Figure(go.Histogram(x=seq, nbinsx=50))
fig_deg.update_layout(
    xaxis_title="Grado (nº de coactores)", yaxis_title="Cantidad de actores",
    yaxis_type="log", bargap=0.02, height=320, margin=dict(t=10, b=10))
st.plotly_chart(fig_deg, width="stretch")
st.caption("Escala log en el eje Y: pocos actores muy conectados, muchos con pocas "
           "conexiones (típico de redes sociales reales).")

# --- Top actores ---
st.subheader("Actores más conectados")
top = gu.top_actors(G, 15)
colT1, colT2 = st.columns([1, 1])
with colT1:
    st.dataframe(top, width="stretch", hide_index=True)
with colT2:
    fig_top = go.Figure(go.Bar(
        x=top["conexiones"][::-1], y=top["actor"][::-1], orientation="h"))
    fig_top.update_layout(height=480, margin=dict(t=10, b=10, l=10),
                          xaxis_title="conexiones (grado)")
    st.plotly_chart(fig_top, width="stretch")

# --------------------------------------------------------------------------- #
# Seccion 2 - Cadena de conexiones (seis grados)
# --------------------------------------------------------------------------- #
st.header("🔗 Cadena de conexiones entre dos actores")
st.markdown("Elegí dos actores y encontrá el camino más corto que los une a través "
            "de películas compartidas (*seis grados de separación*).")

actores = sorted(G.nodes)
col1, col2 = st.columns(2)
actor_a = col1.selectbox("Actor A", actores, index=0, key="actor_a")
default_b = min(1, len(actores) - 1)
actor_b = col2.selectbox("Actor B", actores, index=default_b, key="actor_b")

if st.button("Buscar cadena", type="primary"):
    ok, msg, pasos = gu.shortest_chain(G, actor_a, actor_b)
    if not ok:
        st.warning(msg)
    else:
        st.success(f"**{len(pasos)} grado(s) de separación** entre "
                   f"{actor_a} y {actor_b}.")
        # Cadena textual
        lineas = []
        for i, p in enumerate(pasos, 1):
            extra = f"  _(+{p['otras']} películas más)_" if p["otras"] else ""
            anio = f", {p['anio']}" if p["anio"] else ""
            lineas.append(
                f"{i}. **{p['desde']}** —🎬 *{p['pelicula']}*{anio} — **{p['hasta']}**{extra}")
        st.markdown("\n".join(lineas))

        # Mini-red del camino
        path_nodes = [pasos[0]["desde"]] + [p["hasta"] for p in pasos]
        xs = list(range(len(path_nodes)))
        edge_x, edge_y = [], []
        for i in range(len(path_nodes) - 1):
            edge_x += [xs[i], xs[i + 1], None]
            edge_y += [0, 0, None]
        fig_path = go.Figure()
        fig_path.add_trace(go.Scatter(x=edge_x, y=edge_y, mode="lines",
                                      line=dict(color="#888", width=2),
                                      hoverinfo="none"))
        fig_path.add_trace(go.Scatter(
            x=xs, y=[0] * len(path_nodes), mode="markers+text",
            text=path_nodes, textposition="top center",
            marker=dict(size=22, color="#e45756"), hoverinfo="text"))
        # Etiquetas de pelicula sobre cada arista
        for i, p in enumerate(pasos):
            fig_path.add_annotation(x=(xs[i] + xs[i + 1]) / 2, y=-0.12,
                                    text=f"🎬 {p['pelicula']}", showarrow=False,
                                    font=dict(size=10, color="#555"))
        fig_path.update_layout(
            height=240, showlegend=False, margin=dict(t=30, b=20),
            xaxis=dict(visible=False, range=[-0.5, len(path_nodes) - 0.5]),
            yaxis=dict(visible=False, range=[-0.4, 0.4]))
        st.plotly_chart(fig_path, width="stretch")
