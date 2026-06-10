# Películas — Cine Argentino (datos + elencos)

Dataset de cine argentino construido a partir del catálogo de
**[inforealdecine.com](https://www.inforealdecine.com/)**, enriquecido con los
**elencos** scrapeados desde los links de **Letterboxd** que ese mismo catálogo
provee.

## Origen de los datos

- **Catálogo base:** inforealdecine.com carga su listado desde un Google Sheet
  publicado como CSV (detectado en `js/config.js` del sitio). Ese CSV crudo está
  guardado en [`scripts/peliculas_raw.csv`](scripts/peliculas_raw.csv) y se
  normaliza con [`scripts/build_csv.py`](scripts/build_csv.py) → `peliculas.csv`.
- **Elencos:** por cada película con link de Letterboxd,
  [`scripts/scrape_elencos.py`](scripts/scrape_elencos.py) descarga la ficha y
  extrae el reparto (actor + personaje) → `elencos.csv`.

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

## Scripts (`scripts/`)

| archivo                | función                                                        |
|------------------------|----------------------------------------------------------------|
| `build_csv.py`         | Normaliza `peliculas_raw.csv` → `peliculas.csv`                |
| `scrape_elencos.py`    | Scrapea elencos de Letterboxd → `elencos.csv`                  |
| `peliculas_raw.csv`    | CSV crudo original del Google Sheet (sin encabezados)         |
| `scrape_progress.csv`  | Registro de avance del scraper (permite reanudar)             |

### Cómo correr el scraper

```bash
python scripts/scrape_elencos.py            # corre todo (reanudable)
python scripts/scrape_elencos.py --limit 25 # prueba con 25 pendientes
python scripts/scrape_elencos.py --delay 1  # más pausa entre requests
```

Características:
- **Progreso en vivo** con %, velocidad (pelis/min) y **ETA** (tiempo restante).
- **Reanudable**: si se corta, al volver a correr sigue donde quedó.
- **Reintentos con backoff** ante errores de red, 429 (rate limit) o 5xx.
- **Escritura incremental**: nada se pierde si se interrumpe.

Para **empezar de cero**, borrá `elencos.csv` y `scripts/scrape_progress.csv`
antes de correr.

> Solo usa la librería estándar de Python 3 — no requiere instalar dependencias.
