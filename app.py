from datetime import date
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

# Page layout
st.set_page_config(page_title="Netflix catalog insights", page_icon="🎬", layout="wide")
st.title("Netflix catalog insights")
st.caption(
    "Explore the composition, sourcing, and arrival patterns of the Netflix catalog. "
    "Use the sidebar to apply one consistent scope across every dashboard."
)

#Necessary columns
DATA_PATH = Path(__file__).resolve().with_name("cleaned_dataset.csv")
REQUIRED_COLUMNS = {
    "show_id",
    "type",
    "title",
    "director",
    "country",
    "date_added",
    "release_year",
    "rating",
    "duration_value",
    "duration_unit",
    "listed_in",
}

#Loading the data
@st.cache_data
def load_data(path: str) -> pd.DataFrame:
    data = pd.read_csv(path)
    missing_columns = REQUIRED_COLUMNS.difference(data.columns)
    if missing_columns:
        raise ValueError(
            "The dataset is missing required columns: "
            + ", ".join(sorted(missing_columns))
        )

    data["type_display"] = (
        data["type"].fillna("Unknown").astype(str).str.strip().str.casefold()
        .map({"movie": "Movie", "tv show": "TV show"})
        .fillna("Other")
    )
    data["release_year"] = pd.to_numeric(data["release_year"], errors="coerce")
    data["duration_value"] = pd.to_numeric(data["duration_value"], errors="coerce")
    data["date_added"] = pd.to_datetime(data["date_added"], errors="coerce")
    data["year_added"] = data["date_added"].dt.year
    data["rating"] = data["rating"].fillna("Not rated").astype(str).str.strip()
    data["director"] = data["director"].fillna("Unknown director").astype(str).str.strip()
    data["country"] = data["country"].fillna("Unknown").astype(str).str.strip()
    data["listed_in"] = data["listed_in"].fillna("Uncategorized").astype(str)
    data["_countries"] = data["country"].map(
        lambda value: [item.strip() for item in value.split(",") if item.strip()]
    )
    data["_genres"] = data["listed_in"].map(
        lambda value: [item.strip() for item in value.split(",") if item.strip()]
    )
    return data


try:
    df = load_data(str(DATA_PATH))
except FileNotFoundError:
    st.error(f"Dataset not found: `{DATA_PATH}`. Place `cleaned_dataset.csv` next to `app.py`.")
    st.stop()
except ValueError as error:
    st.error(str(error))
    st.stop()

if df.empty:
    st.error("The dataset contains no rows to analyze.")
    st.stop()

#Sidebar
with st.sidebar:
    st.header("Dashboard filters")
    content_options = sorted(df["type_display"].unique().tolist())
    selected_types = st.multiselect(
        "Content type",
        options=content_options,
        default=content_options,
    )
    release_years = df["release_year"].dropna()
    min_year, max_year = int(release_years.min()), int(release_years.max())
    release_year_range = st.slider(
        "Release year",
        min_value=min_year,
        max_value=max_year,
        value=(min_year, max_year),
    )
    rating_options = sorted(df["rating"].unique().tolist())
    selected_rating = st.selectbox("Audience rating", ["All ratings", *rating_options])
    country_options = sorted(
        {
            country
            for countries in df["_countries"]
            for country in countries
            if country.casefold() != "unknown"
        }
    )
    selected_country = st.selectbox("Production country", ["All countries", *country_options])
    genre_options = sorted(
        {
            genre
            for genres in df["_genres"]
            for genre in genres
            if genre.casefold() != "uncategorized"
        }
    )
    selected_genre = st.selectbox("Genre", ["All genres", *genre_options])
    added_dates = df["date_added"].dropna()
    if not added_dates.empty:
        added_dates_range = st.date_input(
            "Date added",
            value=(added_dates.min().date(), added_dates.max().date()),
            min_value=added_dates.min().date(),
            max_value=added_dates.max().date(),
        )
    else:
        added_dates_range = ()
    title_search = st.text_input("Search titles", placeholder="Type a title")

filtered_df = df[
    df["type_display"].isin(selected_types)
    & df["release_year"].between(*release_year_range)
].copy()
if selected_rating != "All ratings":
    filtered_df = filtered_df[filtered_df["rating"] == selected_rating]
if selected_country != "All countries":
    filtered_df = filtered_df[
        filtered_df["_countries"].map(lambda countries: selected_country in countries)
    ]
if selected_genre != "All genres":
    filtered_df = filtered_df[
        filtered_df["_genres"].map(lambda genres: selected_genre in genres)
    ]
if len(added_dates_range) == 2:
    added_start, added_end = added_dates_range
    filtered_df = filtered_df[
        filtered_df["date_added"].between(
            pd.Timestamp(added_start), pd.Timestamp(added_end) + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
        )
    ]
if title_search.strip():
    filtered_df = filtered_df[
        filtered_df["title"].astype(str).str.contains(
            title_search.strip(), case=False, regex=False, na=False
        )
    ]

#Business insights functions
def count_values(series: pd.Series, excluded: set[str] | None = None) -> pd.Series:
    values = series.explode().dropna().astype(str).str.strip()
    if excluded:
        values = values[~values.str.casefold().isin({item.casefold() for item in excluded})]
    return values.value_counts()


def get_insights(data: pd.DataFrame) -> list[tuple[str, str, str]]:
    if data.empty:
        return []

    insights: list[tuple[str, str, str]] = []
    type_counts = data["type_display"].value_counts()
    leading_type = type_counts.index[0]
    leading_type_share = type_counts.iloc[0] / len(data) * 100
    insights.append(
        (
            "Catalog mix",
            f"{leading_type} is the largest format, representing {leading_type_share:.1f}% "
            f"of the {len(data):,} selected titles.",
            "Compare this format mix with viewing and retention data before changing acquisition targets.",
        )
    )

    country_counts = count_values(data["_countries"], {"Unknown"})
    if not country_counts.empty:
        country_credit_total = int(country_counts.sum())
        leading_country_share = country_counts.iloc[0] / country_credit_total * 100
        insights.append(
            (
                "Sourcing concentration",
                f"{country_counts.index[0]} has the most production-country credits "
                f"({country_counts.iloc[0]:,}; {leading_country_share:.1f}% of country credits).",
                "Review upcoming licensing against this sourcing mix; use performance data to decide "
                "whether to sustain or diversify country exposure.",
            )
        )

    genre_counts = count_values(data["_genres"], {"Uncategorized"})
    if not genre_counts.empty:
        genre_credit_total = int(genre_counts.sum())
        leading_genre_share = genre_counts.iloc[0] / genre_credit_total * 100
        insights.append(
            (
                "Genre portfolio",
                f"{genre_counts.index[0]} is the most frequent genre tag "
                f"({leading_genre_share:.1f}% of genre tags).",
                "Treat leading genres as a portfolio baseline and test adjacent or less represented "
                "genres against audience demand before reallocating budget.",
            )
        )

    dated = data.dropna(subset=["date_added", "release_year"]).copy()
    if not dated.empty:
        dated["release_to_add_years"] = dated["date_added"].dt.year - dated["release_year"]
        median_lag = dated["release_to_add_years"].median()
        insights.append(
            (
                "Library freshness",
                f"The median gap between release year and catalog-add year is {median_lag:.0f} years.",
                "Separate recent releases from back-catalog additions when planning content windows "
                "and assessing acquisition needs.",
            )
        )
    return insights


def make_report(data: pd.DataFrame, insights: list[tuple[str, str, str]]) -> str:
    if data.empty:
        return (
            "# Netflix catalog analysis report\n\n"
            "No titles matched the selected filters. Widen the filters and generate the report again.\n"
        )

    type_counts = data["type_display"].value_counts()
    country_counts = count_values(data["_countries"], {"Unknown"})
    genre_counts = count_values(data["_genres"], {"Uncategorized"})
    movie_runtimes = data.loc[
        data["duration_unit"].astype(str).str.casefold().eq("min"), "duration_value"
    ].dropna()
    date_min, date_max = data["date_added"].min(), data["date_added"].max()
    date_span = (
        f"{date_min:%Y-%m-%d} to {date_max:%Y-%m-%d}"
        if pd.notna(date_min) and pd.notna(date_max)
        else "not available"
    )

    lines = [
        "# Netflix catalog analysis report",
        "",
        f"Generated: {date.today():%Y-%m-%d}",
        "",
        "## Executive summary",
        "",
        f"- **Titles in scope:** {len(data):,}",
        f"- **Movies:** {int(type_counts.get('Movie', 0)):,}",
        f"- **TV shows:** {int(type_counts.get('TV show', 0)):,}",
        f"- **Date-added coverage:** {date_span}",
        f"- **Median movie runtime:** {movie_runtimes.median():.0f} minutes"
        if not movie_runtimes.empty
        else "- **Median movie runtime:** not available",
        "",
        "## Key findings and recommended actions",
        "",
    ]
    for title, finding, action in insights:
        lines.extend([f"### {title}", "", f"- **Finding:** {finding}", f"- **Recommended action:** {action}", ""])
    lines.extend(
        [
            "## Portfolio leaders",
            "",
            f"- **Top production-country credit:** {country_counts.index[0]} ({country_counts.iloc[0]:,})"
            if not country_counts.empty
            else "- **Top production-country credit:** not available",
            f"- **Top genre tag:** {genre_counts.index[0]} ({genre_counts.iloc[0]:,})"
            if not genre_counts.empty
            else "- **Top genre tag:** not available",
            "",
            "## Scope and limitations",
            "",
            "This analysis describes catalog metadata only. It does not include viewing, subscriber, "
            "revenue, licensing-cost, or profitability data; recommendations are hypotheses to validate "
            "against those business measures. A title can have multiple production countries and genre "
            "tags, so those credit counts can exceed the number of titles.",
        ]
    )
    return "\n".join(lines)

#Website tabs
st.caption(f"Showing **{len(filtered_df):,}** of **{len(df):,}** titles")
overview_tab, catalog_tab, geography_tab, trends_tab, ratings_tab, report_tab = st.tabs(
    [
        "Executive overview",
        "Content portfolio",
        "Geographic sourcing",
        "Release and arrival trends",
        "Ratings profile",
        "Insights and report",
    ]
)

with overview_tab:
    if filtered_df.empty:
        st.info("No titles match the current filters. Adjust the sidebar to view the catalog.")
    else:
        movie_count = int(filtered_df["type_display"].eq("Movie").sum())
        tv_count = int(filtered_df["type_display"].eq("TV show").sum())
        movie_runtimes = filtered_df.loc[
            filtered_df["duration_unit"].astype(str).str.casefold().eq("min"), "duration_value"
        ].dropna()
        country_count = len(count_values(filtered_df["_countries"], {"Unknown"}))
        kpi_columns = st.columns(5)
        kpi_columns[0].metric("Titles in scope", f"{len(filtered_df):,}", border=True)
        kpi_columns[1].metric("Movies", f"{movie_count:,}", border=True)
        kpi_columns[2].metric("TV shows", f"{tv_count:,}", border=True)
        kpi_columns[3].metric("Production countries", f"{country_count:,}", border=True)
        kpi_columns[4].metric(
            "Median movie runtime",
            f"{movie_runtimes.median():.0f} min" if not movie_runtimes.empty else "—",
            border=True,
        )

        left, right = st.columns(2)
        with left:
            with st.container(border=True):
                st.subheader("Catalog format mix")
                format_counts = (
                    filtered_df["type_display"].value_counts().rename_axis("Format").reset_index(name="Titles")
                )
                fig = px.pie(
                    format_counts,
                    names="Format",
                    values="Titles",
                    hole=0.48,
                    color="Format",
                    color_discrete_map={"Movie": "#E50914", "TV show": "#5B5B5B", "Other": "#BDBDBD"},
                )
                fig.update_traces(textposition="inside", textinfo="percent+label")
                st.plotly_chart(fig, width="stretch")
        with right:
            with st.container(border=True):
                st.subheader("Most represented genres")
                genre_counts = count_values(filtered_df["_genres"], {"Uncategorized"}).head(10)
                genre_chart = genre_counts.rename_axis("Genre").reset_index(name="Titles")
                fig = px.bar(
                    genre_chart,
                    x="Titles",
                    y="Genre",
                    orientation="h",
                    color="Titles",
                    color_continuous_scale="Reds",
                )
                fig.update_layout(yaxis={"categoryorder": "total ascending"}, coloraxis_showscale=False)
                st.plotly_chart(fig, width="stretch")

with catalog_tab:
    if filtered_df.empty:
        st.info("No titles match the current filters.")
    else:
        left, right = st.columns(2)
        with left:
            with st.container(border=True):
                st.subheader("Genre allocation")
                genre_counts = count_values(filtered_df["_genres"], {"Uncategorized"})
                genre_chart = genre_counts.head(15).rename_axis("Genre").reset_index(name="Titles")
                fig = px.bar(
                    genre_chart,
                    x="Titles",
                    y="Genre",
                    orientation="h",
                    color="Titles",
                    color_continuous_scale="Reds",
                )
                fig.update_layout(yaxis={"categoryorder": "total ascending"}, coloraxis_showscale=False)
                st.plotly_chart(fig, width="stretch")
        with right:
            with st.container(border=True):
                st.subheader("Most prolific listed directors")
                director_counts = (
                    filtered_df.loc[filtered_df["director"] != "Unknown director", "director"]
                    .value_counts()
                    .head(10)
                    .rename_axis("Director")
                    .reset_index(name="Titles")
                )
                if director_counts.empty:
                    st.info("No director credits are available for the selected titles.")
                else:
                    fig = px.bar(
                        director_counts,
                        x="Titles",
                        y="Director",
                        orientation="h",
                        color="Titles",
                        color_continuous_scale="Reds",
                    )
                    fig.update_layout(yaxis={"categoryorder": "total ascending"}, coloraxis_showscale=False)
                    st.plotly_chart(fig, width="stretch")

with geography_tab:
    if filtered_df.empty:
        st.info("No titles match the current filters.")
    else:
        country_counts = count_values(filtered_df["_countries"], {"Unknown"})
        if country_counts.empty:
            st.info("Production-country data is not available for the selected titles.")
        else:
            geo_data = country_counts.rename_axis("Country").reset_index(name="Title credits")
            st.caption(
                "A title may list more than one production country, so the map counts country credits, "
                "not exclusive market shares."
            )
            map_col, table_col = st.columns([1.5, 1])
            with map_col:
                fig = px.choropleth(
                    geo_data,
                    locations="Country",
                    locationmode="country names",
                    color="Title credits",
                    hover_name="Country",
                    color_continuous_scale="Reds",
                    title="Production-country credits",
                )
                fig.update_layout(
                    geo={"showframe": False, "showcoastlines": False, "projection_type": "natural earth"}
                )
                st.plotly_chart(fig, width="stretch")
            with table_col:
                with st.container(border=True):
                    st.subheader("Leading production countries")
                    st.dataframe(
                        geo_data.head(15),
                        hide_index=True,
                        column_config={"Title credits": st.column_config.NumberColumn(format="%d")},
                    )

with trends_tab:
    if filtered_df.empty:
        st.info("No titles match the current filters.")
    else:
        release_counts = (
            filtered_df.groupby(["release_year", "type_display"], as_index=False)
            .size()
            .rename(columns={"size": "Titles"})
        )
        added_counts = (
            filtered_df.dropna(subset=["year_added"])
            .groupby("year_added", as_index=False)
            .size()
            .rename(columns={"year_added": "Year added", "size": "Titles"})
        )
        left, right = st.columns(2)
        with left:
            with st.container(border=True):
                st.subheader("Titles by release year")
                fig = px.line(
                    release_counts,
                    x="release_year",
                    y="Titles",
                    color="type_display",
                    markers=True,
                    color_discrete_map={"Movie": "#E50914", "TV show": "#4B4B4B", "Other": "#BDBDBD"},
                    labels={"release_year": "Release year", "type_display": "Format"},
                )
                st.plotly_chart(fig, width="stretch")
        with right:
            with st.container(border=True):
                st.subheader("Titles added to the catalog by year")
                if added_counts.empty:
                    st.info("Date-added values are not available for the selected titles.")
                else:
                    fig = px.bar(
                        added_counts,
                        x="Year added",
                        y="Titles",
                        color_discrete_sequence=["#E50914"],
                    )
                    st.plotly_chart(fig, width="stretch")
        st.caption(
            "Release year describes when a title was released; date added describes when it entered "
            "the catalog. The final calendar year may be partial in the source data."
        )

with ratings_tab:
    if filtered_df.empty:
        st.info("No titles match the current filters.")
    else:
        left, right = st.columns(2)
        with left:
            with st.container(border=True):
                st.subheader("Titles by audience rating")
                rating_counts = (
                    filtered_df.groupby(["rating", "type_display"], as_index=False)
                    .size()
                    .rename(columns={"size": "Titles"})
                )
                fig = px.bar(
                    rating_counts,
                    x="rating",
                    y="Titles",
                    color="type_display",
                    barmode="group",
                    color_discrete_map={"Movie": "#E50914", "TV show": "#4B4B4B", "Other": "#BDBDBD"},
                    labels={"rating": "Audience rating", "type_display": "Format"},
                )
                st.plotly_chart(fig, width="stretch")
        with right:
            with st.container(border=True):
                st.subheader("Rating and format cross-tabulation")
                rating_matrix = pd.crosstab(filtered_df["rating"], filtered_df["type_display"])
                fig = px.imshow(
                    rating_matrix,
                    text_auto=True,
                    aspect="auto",
                    color_continuous_scale="Reds",
                    labels={"x": "Format", "y": "Audience rating", "color": "Titles"},
                )
                st.plotly_chart(fig, width="stretch")

with report_tab:
    insights = get_insights(filtered_df)
    st.header("Business insights")
    st.caption(
        "These are catalog-planning signals, not proof of audience or financial performance. "
        "Validate recommendations against viewing, retention, revenue, and licensing-cost data."
    )
    if insights:
        for title, finding, action in insights:
            with st.container(border=True):
                st.subheader(title)
                st.write(f"**Finding:** {finding}")
                st.write(f"**Recommended action:** {action}")
    else:
        st.info("No titles match the current filters, so there are no findings to report.")

    st.divider()
    st.subheader("Final analytical report")
    report = make_report(filtered_df, insights)
    st.markdown(report)
    st.download_button(
        "Download analytical report",
        data=report,
        file_name="netflix_catalog_analysis.md",
        mime="text/markdown",
    )
    export_columns = [
        column
        for column in filtered_df.columns
        if column not in {"type_display", "year_added", "_countries", "_genres"}
    ]
    st.download_button(
        "Download filtered data (CSV)",
        data=filtered_df[export_columns].to_csv(index=False).encode("utf-8"),
        file_name="netflix_filtered_catalog.csv",
        mime="text/csv",
    )