# Películas — Cine Argentino (datos + elencos)

Dataset de cine argentino construido a partir del catálogo de
**[inforealdecine.com](https://www.inforealdecine.com/)**, enriquecido con los
**elencos** scrapeados desde los links de **Letterboxd** que ese mismo catálogo
provee.

## Origen de los datos

- **Catálogo base (`peliculas.csv`):** inforealdecine.com carga su listado desde un
  Google Sheet publicado como CSV; ese CSV se normaliza a `peliculas.csv`.
- **Elencos (`elencos.csv`):** por cada película con link de Letterboxd se descarga la
  ficha y se extrae el reparto (actor + personaje).

## Archivos de datos (raíz)

### `peliculas.csv`
Una fila por película (**3126** en total; **3050** con link de Letterboxd).

| columna         | descripción                                              |
|-----------------|----------------------------------------------------------|
| `titulo`        | Título de la película                                    |
| `director`      | Director(es); varios separados por coma                  |
| `anio`          | Año de estreno                                           |
| `duracion`      | Duración en minutos                                      |
| `link_pelicula` | Link a la película (Google Drive)                        |
| `letterboxd`    | URL de la ficha en Letterboxd (fuente de los elencos)    |
| `tags`          | Etiquetas/hashtags; varias separadas por coma            |
| `poster`        | URL del póster (override manual, cuando existe)          |

### `elencos.csv`
Formato **largo**: una fila por actor/actriz de cada película.

| columna     | descripción                                                       |
|-------------|-------------------------------------------------------------------|
| `pelicula`  | Título (coincide con `titulo` de `peliculas.csv`)                 |
| `anio`      | Año de estreno                                                    |
| `actor`     | Nombre del actor o actriz                                         |
| `personaje` | Personaje interpretado (vacío si Letterboxd no tiene el dato)     |

> Los documentales y algunas fichas sin reparto no aportan filas a `elencos.csv`.
> El campo `personaje` suele estar presente en películas recientes y vacío en
> las más antiguas (depende de la metadata de Letterboxd/TMDB).

## Dashboard

Tablero interactivo en **Streamlit** (`dashboard/`) que analiza la **red de
colaboración de actores** del cine argentino — nodos = actores; una arista une a dos
actores que actuaron en la **misma película** — replicando el análisis *small-world* de
Watts & Strogatz (1998).

### Correrlo

```bash
pip install -r dashboard/requirements.txt
streamlit run dashboard/app.py
```

Lee `elencos.csv` en vivo, así que las métricas crecen a medida que avanza el scrape.

### Métricas (estadísticas generales)

| métrica            | qué mide                                                              |
|--------------------|----------------------------------------------------------------------|
| **Nodos / aristas**| nº de actores y de pares de actores que coincidieron en una película |
| **Grado medio k**  | promedio de coactores por actor                                      |
| **Componentes / LCC** | nº de subredes inconexas y tamaño del componente conexo mayor     |
| **L** (path length)| nº medio de pasos en el camino más corto entre dos actores           |
| **C** (clustering) | probabilidad de que dos colegas de un actor también actuaran juntos  |
| **σ (small-world)**| `σ = (C/C_random)/(L/L_random)`; **σ ≫ 1** ⇒ red *small-world*        |

La red es *small-world* cuando `L ≈ L_random` (caminos cortos, como un grafo aleatorio)
pero `C ≫ C_random` (mucho más agrupada). En grafos grandes, L y C se estiman por
muestreo para mantener la respuesta rápida.

### Funcionalidades

- **Filtros** (barra lateral): rango de años, mínimo de películas por actor, director y
  tag/etiqueta. Recalculan todas las métricas sobre el subconjunto filtrado.
- **Distribución de grados** y ranking de **actores más conectados**.
- **Cadena de conexiones (seis grados):** se eligen dos actores y se muestra el camino
  más corto que los une, indicando la **película puente** en cada paso, los grados de
  separación y una mini-red del camino.

> **Identidad de actores:** se usa el nombre visible de Letterboxd. Homónimos (dos
> personas con el mismo nombre) colapsan en un nodo y variantes de tildes pueden duplicar.

## Referencia

Watts, D. J., & Strogatz, S. H. (1998). *Collective dynamics of 'small-world' networks.*
**Nature, 393**(6684), 440–442.
[PDF](https://snap.stanford.edu/class/cs224w-readings/watts98smallworld.pdf)
