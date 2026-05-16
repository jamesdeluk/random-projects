from __future__ import annotations

from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path

import folium
import geopandas as gpd
import numpy as np
import streamlit as st
from geopy.distance import geodesic
from shapely.geometry import Point, Polygon, MultiPolygon, GeometryCollection
from streamlit_folium import st_folium


@dataclass(frozen=True)
class ExtremePoint:
    lon: float
    lat: float


@dataclass(frozen=True)
class CountryExtremes:
    north: ExtremePoint
    south: ExtremePoint
    east: ExtremePoint
    west: ExtremePoint


def _natural_earth_path() -> str:
    """Return a local Natural Earth countries path suitable for offline use."""
    # Preferred local copy (if you later vendor one into this repo).
    local_copy = Path("data/world_countries.geojson")
    if local_copy.exists():
        return str(local_copy)

    # Optional local shapefile copy.
    local_shp = Path("data/world_countries.shp")
    if local_shp.exists():
        return str(local_shp)

    # GeoPandas legacy bundled dataset path (not available in recent versions).
    try:
        return gpd.datasets.get_path("naturalearth_lowres")
    except Exception:
        pass

    # Fallback path used by some older GeoPandas builds.
    fallback = files("geopandas") / "datasets" / "naturalearth_lowres" / "naturalearth_lowres.shp"
    if fallback.is_file():
        return str(fallback)

    # Offline fallback available with pyogrio wheels.
    try:
        pyogrio_fixture = (
            files("pyogrio")
            / "tests"
            / "fixtures"
            / "naturalearth_lowres"
            / "naturalearth_lowres.shp"
        )
        if pyogrio_fixture.is_file():
            return str(pyogrio_fixture)
    except Exception:
        pass

    msg = (
        "Could not find a local countries dataset. Place one at "
        "data/world_countries.geojson or data/world_countries.shp."
    )
    raise FileNotFoundError(msg)


def _to_mainland(geometry):
    if geometry is None or geometry.is_empty:
        return geometry

    if isinstance(geometry, Polygon):
        return geometry

    if isinstance(geometry, MultiPolygon):
        parts = [part for part in geometry.geoms if not part.is_empty]
        return max(parts, key=lambda p: p.area) if parts else geometry

    if isinstance(geometry, GeometryCollection):
        parts = [part for part in geometry.geoms if isinstance(part, Polygon)]
        return max(parts, key=lambda p: p.area) if parts else geometry

    return geometry


def _norm_col(value: str) -> str:
    return "".join(ch for ch in value.lower() if ch.isalnum())


def _find_column(columns: list[str], candidates: list[str], token_sets: list[list[str]]) -> str | None:
    by_lower = {col.lower(): col for col in columns}
    for cand in candidates:
        match = by_lower.get(cand.lower())
        if match:
            return match

    by_norm = {_norm_col(col): col for col in columns}
    for cand in candidates:
        match = by_norm.get(_norm_col(cand))
        if match:
            return match

    for col in columns:
        norm = _norm_col(col)
        for tokens in token_sets:
            if all(token in norm for token in tokens):
                return col

    return None


@st.cache_data(show_spinner=False)
def load_countries() -> gpd.GeoDataFrame:
    path = _natural_earth_path()
    gdf = gpd.read_file(path)

    columns = list(gdf.columns)
    geom_col = gdf.geometry.name

    name_col = _find_column(
        columns=columns,
        candidates=["name", "admin", "country", "sovereignt"],
        token_sets=[["name"], ["country"], ["admin"]],
    )
    if name_col is None:
        raise ValueError(
            f"Could not identify a country-name column. Available columns: {columns}"
        )

    iso_col = _find_column(
        columns=columns,
        candidates=[
            "iso_a3",
            "iso3",
            "adm0_a3",
            "ISO3166-1-Alpha-3",
            "iso3166_1_alpha_3",
        ],
        token_sets=[["iso", "a3"], ["iso", "alpha3"], ["alpha3"]],
    )

    countries = gdf[[name_col, geom_col]].rename(columns={name_col: "country", geom_col: "geometry"})
    if iso_col is None:
        countries["iso_a3"] = "UNK"
    else:
        countries["iso_a3"] = gdf[iso_col].astype(str).str.strip().replace({"": "UNK", "nan": "UNK"})

    countries = countries[countries["country"] != "Antarctica"].copy()
    countries["geometry"] = countries["geometry"].apply(_to_mainland)
    countries = countries[~countries.geometry.is_empty & countries.geometry.notna()].copy()

    # Use area in equal-area projection only to break ties deterministically.
    projected = countries.to_crs(6933)
    countries["mainland_area_m2"] = projected.geometry.area

    return countries.to_crs(4326)


def _all_boundary_coords(polygon: Polygon) -> np.ndarray:
    rings = [np.asarray(polygon.exterior.coords)]
    for interior in polygon.interiors:
        rings.append(np.asarray(interior.coords))
    return np.vstack(rings)


def _wrap_lon(lon: float) -> float:
    return ((lon + 180.0) % 360.0) - 180.0


def compute_extremes(geometry) -> CountryExtremes:
    if isinstance(geometry, MultiPolygon):
        geometry = _to_mainland(geometry)

    if not isinstance(geometry, Polygon):
        raise ValueError("Expected a Polygon mainland geometry.")

    coords = _all_boundary_coords(geometry)
    lons = coords[:, 0]
    lats = coords[:, 1]

    # Prefer the longitude representation with smaller span to better handle
    # geometries near the anti-meridian.
    lons_shifted = np.mod(lons, 360.0)
    use_shifted = (lons_shifted.max() - lons_shifted.min()) < (lons.max() - lons.min())

    if use_shifted:
        lons_eval = lons_shifted
        east_idx = int(np.argmax(lons_eval))
        west_idx = int(np.argmin(lons_eval))
        east_lon = _wrap_lon(float(lons_eval[east_idx]))
        west_lon = _wrap_lon(float(lons_eval[west_idx]))
    else:
        lons_eval = lons
        east_idx = int(np.argmax(lons_eval))
        west_idx = int(np.argmin(lons_eval))
        east_lon = float(lons[east_idx])
        west_lon = float(lons[west_idx])

    north_idx = int(np.argmax(lats))
    south_idx = int(np.argmin(lats))

    return CountryExtremes(
        north=ExtremePoint(lon=float(lons[north_idx]), lat=float(lats[north_idx])),
        south=ExtremePoint(lon=float(lons[south_idx]), lat=float(lats[south_idx])),
        east=ExtremePoint(lon=east_lon, lat=float(lats[east_idx])),
        west=ExtremePoint(lon=west_lon, lat=float(lats[west_idx])),
    )


def km_between(point_lat: float, point_lon: float, other: ExtremePoint) -> float:
    return geodesic((point_lat, point_lon), (other.lat, other.lon)).km


def percentages_from_distances(
    north_km: float, south_km: float, east_km: float, west_km: float
) -> dict[str, float]:
    ns_total = north_km + south_km
    ew_total = east_km + west_km

    if ns_total <= 0:
        pct_north = pct_south = 50.0
    else:
        # Position-style percentages: 100% north means at the north extreme.
        pct_north = (south_km / ns_total) * 100.0
        pct_south = (north_km / ns_total) * 100.0

    if ew_total <= 0:
        pct_east = pct_west = 50.0
    else:
        # Position-style percentages: 100% east means at the east extreme.
        pct_east = (west_km / ew_total) * 100.0
        pct_west = (east_km / ew_total) * 100.0

    return {
        "north": pct_north,
        "south": pct_south,
        "east": pct_east,
        "west": pct_west,
    }


def build_map(
    countries_geojson: dict,
    selected: tuple[float, float] | None,
    base_tiles: str | None,
) -> folium.Map:
    m = folium.Map(location=[18, 0], zoom_start=2, tiles=base_tiles)

    folium.GeoJson(
        data=countries_geojson,
        style_function=lambda _feature: {
            "color": "#1f2937",
            "weight": 1,
            "fillColor": "#9ca3af",
            "fillOpacity": 0.12,
        },
        highlight_function=lambda _feature: {
            "color": "#111827",
            "weight": 2,
            "fillOpacity": 0.3,
        },
        name="countries",
    ).add_to(m)

    if selected is not None:
        lat, lon = selected
        folium.Marker(
            [lat, lon],
            tooltip=f"Selected point: {lat:.4f}, {lon:.4f}",
            icon=folium.Icon(color="red", icon="info-sign"),
        ).add_to(m)

    return m


def find_country_for_point(countries: gpd.GeoDataFrame, lat: float, lon: float):
    point = Point(lon, lat)
    matches = countries[countries.geometry.covers(point)]
    if matches.empty:
        return None

    # Disputed borders can overlap; pick the largest mainland match.
    best = matches.sort_values("mainland_area_m2", ascending=False).iloc[0]
    return best


def main() -> None:
    st.set_page_config(page_title="NSWE Country Position Tool", layout="wide")
    st.title("NSWE Percentage Position by Country")
    st.caption(
        "Click a point on the map. The app detects the mainland country and computes "
        "geodesic north/south/east/west percentages."
    )

    try:
        countries = load_countries()
    except Exception as exc:
        st.error(str(exc))
        st.stop()

    if "selected_point" not in st.session_state:
        st.session_state.selected_point = None

    left, right = st.columns([3, 2])

    with left:
        st.subheader("Map")
        tile_options = {
            "OpenStreetMap (labels)": "OpenStreetMap",
            "CartoDB Positron (labels)": "CartoDB Positron",
            "CartoDB Voyager (labels)": "CartoDB Voyager",
            "No basemap (offline)": None,
        }
        tile_label = st.selectbox("Basemap", list(tile_options), index=0)
        map_obj = build_map(
            countries.__geo_interface__,
            st.session_state.selected_point,
            tile_options[tile_label],
        )
        if tile_options[tile_label] is None:
            st.caption("Offline mode: no tile labels.")
        else:
            st.caption("Basemap tiles require internet access.")
        map_state = st_folium(
            map_obj,
            height=650,
            width=None,
            returned_objects=["last_clicked"],
            use_container_width=True,
        )

        clicked = map_state.get("last_clicked") if map_state else None
        if clicked:
            new_point = (float(clicked["lat"]), float(clicked["lng"]))
            if st.session_state.selected_point != new_point:
                st.session_state.selected_point = new_point
                st.rerun()

        if st.button("Clear selected point"):
            st.session_state.selected_point = None
            st.rerun()

    with right:
        st.subheader("Results")

        selected = st.session_state.selected_point
        if selected is None:
            st.info("Select a point on the map to see results.")
            return

        lat, lon = selected
        st.write(f"Selected point: `{lat:.6f}, {lon:.6f}`")

        country_row = find_country_for_point(countries, lat, lon)
        if country_row is None:
            st.warning(
                "The selected point is not inside a mainland country polygon in this dataset. "
                "Try a point farther inland."
            )
            return

        st.write(f"Detected country: **{country_row['country']}** (`{country_row['iso_a3']}`)")

        extremes = compute_extremes(country_row.geometry)

        north_km = km_between(lat, lon, extremes.north)
        south_km = km_between(lat, lon, extremes.south)
        east_km = km_between(lat, lon, extremes.east)
        west_km = km_between(lat, lon, extremes.west)

        pct = percentages_from_distances(
            north_km=north_km,
            south_km=south_km,
            east_km=east_km,
            west_km=west_km,
        )

        st.markdown("### Percentage Position")
        st.metric("North", f"{pct['north']:.2f}%")
        st.metric("South", f"{pct['south']:.2f}%")
        st.metric("East", f"{pct['east']:.2f}%")
        st.metric("West", f"{pct['west']:.2f}%")

        st.caption("By construction: North + South = 100, and East + West = 100.")

        with st.expander("Distance details (km)"):
            st.write(
                {
                    "to_north_extreme_km": round(north_km, 3),
                    "to_south_extreme_km": round(south_km, 3),
                    "to_east_extreme_km": round(east_km, 3),
                    "to_west_extreme_km": round(west_km, 3),
                }
            )

            st.write(
                {
                    "north_extreme": {"lat": extremes.north.lat, "lon": extremes.north.lon},
                    "south_extreme": {"lat": extremes.south.lat, "lon": extremes.south.lon},
                    "east_extreme": {"lat": extremes.east.lat, "lon": extremes.east.lon},
                    "west_extreme": {"lat": extremes.west.lat, "lon": extremes.west.lon},
                }
            )


if __name__ == "__main__":
    main()
