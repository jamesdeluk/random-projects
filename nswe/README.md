# NSWE Country Position Tool

Streamlit app that lets a user click a point on a map, auto-detects the mainland country, and computes geodesic NSWE percentages.

It includes a basemap selector:
- `OpenStreetMap (labels)` (default)
- `CartoDB` labeled alternatives
- `No basemap (offline)`

## What it computes
- `North + South = 100`
- `East + West = 100`

Percentages are position-style:
- `North %` is higher when the point is closer to the country's north extreme.
- `East %` is higher when the point is closer to the country's east extreme.

## Run
1. Install dependencies.
2. Start Streamlit:

```bash
streamlit run app.py
```

## Offline data notes
The app looks for boundaries in this order:
1. `data/world_countries.geojson` (repo-local file, preferred for strict offline use)
2. `data/world_countries.shp` (repo-local shapefile)
3. GeoPandas packaged `naturalearth_lowres` dataset (older builds)
4. `pyogrio` packaged `naturalearth_lowres` fixture (offline fallback)

If none of the above are available, place a world country dataset at `data/world_countries.geojson` or `data/world_countries.shp`.

## Boundary assumptions
- Uses admin country boundaries from the loaded dataset.
- Uses mainland only (`MultiPolygon` reduced to largest polygon by area).
- Border disputes: whichever polygon contains the click; ties break to larger mainland area.
