import marimo

__generated_with = "0.18.4"
app = marimo.App(width="full")


@app.cell
def _():
    import os
    import marimo as mo
    import polars as pl
    import plotly.express as px

    px.defaults.template = "plotly_white"
    px.defaults.color_discrete_sequence = px.colors.qualitative.Prism
    return mo, os, pl, px


@app.cell
def _(mo, os, pl):
    json_files = sorted(file for file in os.listdir(".") if file.endswith(".json"))
    mo.stop(len(json_files) == 0, mo.md("No streaming history files found in this directory."))
    data_frames = [pl.read_json(file) for file in json_files]
    df = pl.concat(data_frames, how="vertical_relaxed")
    return (df,)


@app.cell
def _(df, pl):
    df_1 = (
        df.with_columns(
            pl.col("ts").str.strptime(pl.Datetime, format="%Y-%m-%dT%H:%M:%SZ", strict=False)
        )
        .filter(pl.col("episode_name").is_null())
        .select(
            [
                "ts",
                "ms_played",
                "master_metadata_track_name",
                "master_metadata_album_artist_name",
                "master_metadata_album_album_name",
                "reason_start",
                "reason_end",
                "shuffle",
                "skipped",
            ]
        )
        .rename(
            {
                "master_metadata_track_name": "track_name",
                "master_metadata_album_artist_name": "album_artist_name",
                "master_metadata_album_album_name": "album_album_name",
            }
        )
    )
    return (df_1,)


@app.cell
def _(df_1):
    df_1.head()
    return


@app.cell
def _(df_1, mo, pl):
    columns = ["ts", "track_name", "album_artist_name", "album_album_name"]
    unique_counts = pl.DataFrame(
        {
            "column": columns,
            "unique_values": [df_1.select(pl.col(col).n_unique()).item() for col in columns],
        }
    )
    mo.vstack([mo.md("Unique values per column"), unique_counts])
    return


@app.cell
def _(df_1, pl):
    total_days_listened = df_1.select(pl.sum("ms_played")).item() / 1000 / 60 / 60 / 24
    total_days_listened
    return


@app.cell
def _():
    # df.reason_start.value_counts()
    # df.reason_end.value_counts()
    return


@app.cell
def _(df_1, pl):
    top_artists_all_time = (
        df_1.group_by("album_artist_name")
        .agg(pl.col("ms_played").sum())
        .sort("ms_played", descending=True)
        .head(50)["album_artist_name"]
        .to_list()
    )
    top_artists_all_time
    return (top_artists_all_time,)


@app.cell
def _(df_1, mo, pl, px):
    year_filter = 0
    if year_filter == 0:
        working_df = df_1
        plot_title = "of all time"
    else:
        working_df = df_1.filter(pl.col("ts").dt.year() == year_filter)
        plot_title = f"of {year_filter}"

    artists = (
        working_df.group_by("album_artist_name")
        .agg(pl.col("ms_played").sum())
        .sort("ms_played", descending=True)
        .with_columns((pl.col("ms_played") / 1000 / 60).alias("Minutes played"))
        .rename({"album_artist_name": "Album artist"})
    )
    tracks = (
        working_df.group_by("track_name")
        .agg(
            pl.col("ms_played").sum().alias("ms_played"),
            pl.col("album_artist_name").first().alias("album_artist_name"),
        )
        .with_columns(
            (pl.col("ms_played") / 1000 / 60).alias("Minutes played"),
            pl.concat_str(["track_name", pl.lit(" - "), "album_artist_name"]).alias("Track and artist"),
        )
        .select(["Track and artist", "Minutes played"])
        .sort("Minutes played", descending=True)
    )

    fig_artists_pie = px.pie(
        artists.head(20).to_pandas(),
        names="Album artist",
        values="Minutes played",
        title=f"Top 20 artists {plot_title}",
    )
    fig_artists_bar = px.bar(
        artists.head(50).to_pandas(),
        x="Album artist",
        y="Minutes played",
        title=f"Top 50 artists {plot_title}",
    )
    fig_artists_bar.update_layout(xaxis_tickangle=-90)

    fig_tracks_pie = px.pie(
        tracks.head(20).to_pandas(),
        names="Track and artist",
        values="Minutes played",
        title=f"Top 20 tracks {plot_title}",
    )
    fig_tracks_bar = px.bar(
        tracks.head(50).to_pandas(),
        y="Track and artist",
        x="Minutes played",
        title=f"Top 50 tracks {plot_title}",
        orientation="h",
    )

    mo.vstack(
        [
            mo.hstack([mo.ui.plotly(fig_artists_pie), mo.ui.plotly(fig_artists_bar)]),
            mo.hstack([mo.ui.plotly(fig_tracks_pie), mo.ui.plotly(fig_tracks_bar)]),
        ]
    )
    return


@app.cell
def _(df_1, mo, pl, px):
    years = (
        df_1.select(pl.col("ts").dt.year().alias("Year"))
        .unique()
        .sort("Year")["Year"]
        .to_list()
    )
    totals = []
    top_artists = []
    top_tracks = []
    for year in years:
        yearly_df = df_1.filter(pl.col("ts").dt.year() == year)
        total_hours = yearly_df.select(pl.sum("ms_played")).item() / 1000 / 60 / 60
        totals.append(pl.DataFrame({"Year": [year], "Hours played": [total_hours]}))

        artist_row = (
            yearly_df.group_by("album_artist_name")
            .agg(pl.col("ms_played").sum())
            .sort("ms_played", descending=True)
            .head(1)
            .with_columns((pl.col("ms_played") / 1000 / 60).alias("Minutes played"))
            .rename({"album_artist_name": "Album artist"})
            .with_columns(pl.lit(year).alias("Year"))
            .select(["Year", "Album artist", "Minutes played"])
        )
        top_artists.append(artist_row)

        track_row = (
            yearly_df.group_by("track_name")
            .agg(
                pl.col("ms_played").sum().alias("ms_played"),
                pl.col("album_artist_name").first().alias("Album artist"),
            )
            .sort("ms_played", descending=True)
            .head(1)
            .with_columns(
                (pl.col("ms_played") / 1000 / 60).alias("Minutes played"),
                pl.lit(year).alias("Year"),
                pl.col("track_name").alias("Track name"),
            )
            .select(["Year", "Track name", "Album artist", "Minutes played"])
        )
        top_tracks.append(track_row)

    totals_df = pl.concat(totals).sort("Year")
    artists_df = pl.concat(top_artists).sort("Year")
    tracks_df = pl.concat(top_tracks).sort("Year")

    line_df = pl.concat(
        [
            totals_df.select(pl.col("Year"), pl.col("Hours played").alias("Value")).with_columns(
                pl.lit("Total (hours)").alias("Metric")
            ),
            artists_df.select(pl.col("Year"), pl.col("Minutes played").alias("Value")).with_columns(
                pl.lit("Top artist (minutes)").alias("Metric")
            ),
            tracks_df.select(pl.col("Year"), pl.col("Minutes played").alias("Value")).with_columns(
                pl.lit("Top track (minutes)").alias("Metric")
            ),
        ]
    )

    trend_fig = px.line(
        line_df.to_pandas(),
        x="Year",
        y="Value",
        color="Metric",
        markers=True,
        title="Total play time over time",
    )
    trend_fig.update_layout(yaxis_title="Play time (minutes or hours)")

    mo.vstack(
        [
            mo.ui.plotly(trend_fig),
            mo.tabs(
                {
                    "Totals": mo.ui.dataframe(totals_df),
                    "Top artists": mo.ui.dataframe(artists_df),
                    "Top tracks": mo.ui.dataframe(tracks_df),
                }
            ),
        ]
    )
    return


@app.cell
def _(df_1, mo, pl, px):
    data_2023 = df_1.filter(pl.col("ts").dt.year() == 2023)
    data_2024 = df_1.filter(pl.col("ts").dt.year() == 2024)
    data_2025 = df_1.filter(pl.col("ts").dt.year() == 2025)

    def top_artists_list(frame: pl.DataFrame) -> list[str]:
        return (
            frame.group_by("album_artist_name")
            .agg(pl.col("ms_played").sum())
            .sort("ms_played", descending=True)
            .select("album_artist_name")
            .head(50)["album_artist_name"]
            .to_list()
        )

    artists_2023 = top_artists_list(data_2023)
    artists_2024 = top_artists_list(data_2024)
    artists_2025 = top_artists_list(data_2025)

    artists_2025_not_2024 = [artist for artist in artists_2025 if artist not in artists_2024]
    artists_2024_not_2023 = [artist for artist in artists_2024 if artist not in artists_2023]
    artists_2023_not_2024 = [artist for artist in artists_2023 if artist not in artists_2024]

    def describe(values: list[str]) -> str:
        return ", ".join(values) if values else "None"

    summary = mo.vstack(
        [
            mo.md(
                f"Top 50 artists in 2025 but not in 2024: {describe(artists_2025_not_2024)} ({len(artists_2025_not_2024)})"
            ),
            mo.md(
                f"Top 50 artists in 2024 but not in 2023: {describe(artists_2024_not_2023)} ({len(artists_2024_not_2023)})"
            ),
            mo.md(
                f"Top 50 artists in 2023 but not in 2024: {describe(artists_2023_not_2024)} ({len(artists_2023_not_2024)})"
            ),
        ]
    )

    artists_for_plot = (
        data_2024.group_by("album_artist_name")
        .agg(pl.col("ms_played").sum())
        .sort("ms_played", descending=True)
        .with_columns(
            (pl.col("ms_played") / 1000 / 60).alias("Minutes played"),
            pl.col("album_artist_name").alias("Album artist"),
            pl.when(pl.col("album_artist_name").is_in(artists_2025_not_2024))
            .then("Yes")
            .otherwise("No")
            .alias("New in 2025"),
        )
        .select(["Album artist", "Minutes played", "New in 2025"])
        .head(50)
    )

    artists_fig = px.bar(
        artists_for_plot.to_pandas(),
        x="Album artist",
        y="Minutes played",
        color="New in 2025",
        title="Top artists in 2025",
    )
    artists_fig.update_layout(xaxis_tickangle=-90)

    mo.vstack([summary, mo.ui.plotly(artists_fig)])
    return (data_2024,)


@app.cell
def _(df_1, mo, pl, px, top_artists_all_time):
    most_skipped = (
        df_1.filter(pl.col("skipped"))
        .group_by("album_artist_name")
        .agg(pl.len().alias("Skipped"))
        .rename({"album_artist_name": "Album artist"})
        .sort("Skipped", descending=True)
        .with_columns(
            pl.when(pl.col("Album artist").is_in(top_artists_all_time))
            .then("Yes")
            .otherwise("No")
            .alias("Most played artist")
        )
    )

    skipped_fig = px.bar(
        most_skipped.head(50).to_pandas(),
        x="Album artist",
        y="Skipped",
        color="Most played artist",
        title="Most skipped artists of all time",
    )
    skipped_fig.update_layout(xaxis_tickangle=-90, yaxis_title="Skip count")

    mo.vstack([mo.ui.dataframe(most_skipped), mo.ui.plotly(skipped_fig)])
    return


@app.cell
def _(data_2024, mo, pl, px):
    minutes_per_day_2024 = (
        data_2024.with_columns(pl.col("ts").dt.date().alias("date"))
        .group_by("date")
        .agg(pl.col("ms_played").sum())
        .with_columns((pl.col("ms_played") / 1000 / 60).alias("Minutes played"))
        .select(["date", "Minutes played"])
        .sort("date")
    )
    avg_minutes = minutes_per_day_2024.select(pl.mean("Minutes played")).item()

    minutes_fig = px.line(
        minutes_per_day_2024.to_pandas(),
        x="date",
        y="Minutes played",
        title="Minutes played by day in 2024, with average",
    )
    minutes_fig.add_hline(
        y=avg_minutes,
        line_dash="dash",
        line_color="#008000",
        annotation_text="Average",
        annotation_position="top left",
    )
    minutes_fig.update_layout(xaxis_title="Date", yaxis_title="Minutes played")
    minutes_fig.update_xaxes(dtick="M1", tickformat="%b")

    mo.vstack([mo.ui.plotly(minutes_fig), minutes_per_day_2024])
    return (minutes_per_day_2024,)


@app.cell
def _(data_2024, minutes_per_day_2024, mo, pl):
    top_day = (
        minutes_per_day_2024.sort("Minutes played", descending=True)["date"][0]
        if len(minutes_per_day_2024) > 0
        else None
    )
    mo.stop(top_day is None, mo.md("No listening data available for 2024."))

    top_day_tracks = (
        data_2024.filter(pl.col("ts").dt.date() == top_day)
        .group_by("track_name")
        .agg(
            pl.col("ms_played").sum().alias("ms_played"),
            pl.col("album_artist_name").first().alias("album_artist_name"),
            pl.col("album_album_name").first().alias("album_album_name"),
        )
        .with_columns(
            (pl.col("ms_played") / 1000 / 60).alias("Minutes played"),
            pl.col("track_name").alias("Track name"),
            pl.col("album_artist_name").alias("Album artist"),
            pl.col("album_album_name").alias("Album name"),
        )
        .select(["Track name", "Album artist", "Album name", "Minutes played"])
        .sort("Minutes played", descending=True)
    )

    mo.vstack([mo.md(f"Top listening day: {top_day.isoformat()}"), top_day_tracks])
    return (top_day_tracks,)


@app.cell
def _(pl, top_day_tracks):
    avg_minutes_top_day = top_day_tracks.select(pl.mean("Minutes played")).item()
    avg_minutes_top_day
    return


if __name__ == "__main__":
    app.run()
