"""Artefact writing: analysis tables, graph files and charts.

Table writing is strict -- a failure to write an analysis table is a failed run.
Chart rendering is deliberately lenient: each chart is isolated so that one broken
optional visualisation cannot lose a completed analysis. See :func:`safe_chart`.

Chart styling
-------------
Colours come from a validated categorical palette (blue ``#2a78d6`` / orange
``#eb6834``), which passes the lightness-band, chroma-floor, CVD-separation,
normal-vision and contrast checks against the light chart surface ``#fcfcfb``.
Single-series charts use blue alone and carry no legend, since the title names the
series; the one two-series chart uses blue/orange plus a legend, so identity is never
carried by colour alone.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable, Final, Sequence

import matplotlib

matplotlib.use("Agg")  # Headless: never try to open a window during a batch run.

import matplotlib.pyplot as plt  # noqa: E402  (must follow the backend selection)
import networkx as nx  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.ticker import MaxNLocator  # noqa: E402
from matplotlib.transforms import offset_copy  # noqa: E402

LOGGER: Final = logging.getLogger(__name__)

# -- Validated palette and chrome ------------------------------------------------------
SURFACE: Final = "#fcfcfb"
INK_PRIMARY: Final = "#0b0b0b"
INK_SECONDARY: Final = "#52514e"
INK_MUTED: Final = "#898781"
GRIDLINE: Final = "#e1e0d9"
BASELINE: Final = "#c3c2b7"
SERIES_1: Final = "#2a78d6"  # blue
SERIES_2: Final = "#eb6834"  # orange

CHART_DPI: Final = 200

_FONT_STACK: Final = [
    "system-ui", "-apple-system", "Helvetica Neue", "Helvetica", "Arial",
    "DejaVu Sans",
]


def apply_chart_theme() -> None:
    """Install the recessive chart theme used by every figure in this package."""
    plt.rcParams.update(
        {
            "figure.facecolor": SURFACE,
            "axes.facecolor": SURFACE,
            "savefig.facecolor": SURFACE,
            "savefig.bbox": "tight",
            "font.family": "sans-serif",
            "font.sans-serif": _FONT_STACK,
            "text.color": INK_PRIMARY,
            "axes.labelcolor": INK_SECONDARY,
            "axes.edgecolor": BASELINE,
            "axes.linewidth": 0.8,
            "axes.titlesize": 13,
            "axes.titleweight": "semibold",
            "axes.labelsize": 10,
            "axes.grid": True,
            "axes.axisbelow": True,
            "grid.color": GRIDLINE,
            "grid.linewidth": 0.7,
            "xtick.color": INK_MUTED,
            "ytick.color": INK_MUTED,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "xtick.direction": "out",
            "ytick.direction": "out",
            "legend.frameon": False,
            "legend.fontsize": 9,
            "figure.dpi": 110,
        }
    )


# -- Table and graph writing -----------------------------------------------------------
def write_table(frame: pd.DataFrame, path: Path) -> Path:
    """Write an analysis table as CSV.

    Uses ``index=False`` and a fixed float format so repeated runs over unchanged data
    produce identical bytes.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, float_format="%.6f")
    LOGGER.info("Wrote %-46s %7d rows", path.name, len(frame))
    return path


def write_parquet(frame: pd.DataFrame, path: Path) -> Path:
    """Write a dataset as Parquet.

    Object columns are cast to string first: a column of mixed ``str``/``None`` has no
    stable Arrow type and would otherwise fail or silently change type between runs.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    prepared = frame.copy()
    for column in prepared.columns:
        if prepared[column].dtype == object:
            prepared[column] = prepared[column].astype("string")
    prepared.to_parquet(path, index=False)
    LOGGER.info("Wrote %-46s %7d rows", path.name, len(prepared))
    return path


def write_graphml(graph: nx.DiGraph, path: Path) -> Path:
    """Write the pathway graph as GraphML.

    GraphML cannot represent ``None``, so null node attributes are dropped and
    remaining non-scalar values are stringified. The graph passed in is not mutated.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    exportable = nx.DiGraph()
    for node, data in graph.nodes(data=True):
        clean: dict[str, Any] = {}
        for key, value in data.items():
            if value is None or (isinstance(value, float) and pd.isna(value)):
                continue
            clean[key] = value if isinstance(value, (str, int, float, bool)) else str(value)
        exportable.add_node(node, **clean)
    for source, target, data in graph.edges(data=True):
        clean = {
            key: (value if isinstance(value, (str, int, float, bool)) else str(value))
            for key, value in data.items()
            if value is not None
        }
        exportable.add_edge(source, target, **clean)
    nx.write_graphml(exportable, path)
    LOGGER.info(
        "Wrote %-46s %5d nodes %6d edges",
        path.name,
        exportable.number_of_nodes(),
        exportable.number_of_edges(),
    )
    return path


def safe_chart(name: str, renderer: Callable[[], Path]) -> Path | None:
    """Render one chart, converting any failure into a warning.

    A single optional visualisation must never abort a completed analysis run, so the
    exception is logged with its type and message and the run continues.
    """
    try:
        path = renderer()
    except Exception as exc:  # noqa: BLE001 - deliberate: charts are optional
        LOGGER.warning(
            "Chart %r failed and was skipped (%s: %s).", name, exc.__class__.__name__, exc
        )
        return None
    LOGGER.info("Chart %-44s -> %s", name, path.name)
    return path


# -- Chart building blocks -------------------------------------------------------------
def _finish(
    fig: plt.Figure,
    ax: plt.Axes,
    *,
    title: str,
    subtitle: str,
    source: str,
    path: Path,
    grid_axis: str = "y",
    legend_below: bool = False,
) -> Path:
    """Apply shared chrome to a figure and save it.

    Removes the top/right spines, restricts the grid to the value axis only, and adds a
    subtitle plus a source note so each chart is self-describing when lifted into a
    document.

    Chrome below the axes (legend, source note) is positioned with offsets in **points**
    from the axes edge rather than in figure fractions. These charts vary in height from
    ~3in to ~12in depending on how many bars they hold, and a fixed figure-fraction
    offset drifts badly across that range -- it collides with the subtitle on short
    figures and leaves a large gap on tall ones.

    Args:
        legend_below: Place the axes legend beneath the x-axis label. Used by
            multi-series charts, where a legend anchored above the axes would collide
            with the subtitle.
    """
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ax.spines["left"].set_color(BASELINE)
    ax.spines["bottom"].set_color(BASELINE)
    ax.grid(True, axis=grid_axis, color=GRIDLINE, linewidth=0.7)
    if grid_axis != "both":
        ax.grid(False, axis="x" if grid_axis == "y" else "y")

    ax.set_title(title, loc="left", pad=22, color=INK_PRIMARY)
    ax.annotate(
        subtitle,
        xy=(0.0, 1.0),
        xycoords="axes fraction",
        xytext=(0, 9),
        textcoords="offset points",
        ha="left",
        va="bottom",
        fontsize=9.5,
        color=INK_SECONDARY,
    )

    source_offset = -30.0
    if legend_below:
        handles, labels = ax.get_legend_handles_labels()
        if handles:
            ax.legend(
                handles,
                labels,
                loc="upper left",
                bbox_to_anchor=(0.0, 0.0),
                bbox_transform=_axes_offset(ax, -34.0),
                ncol=min(len(handles), 4),
            )
            source_offset = -54.0

    ax.annotate(
        source,
        xy=(0.0, 0.0),
        xycoords="axes fraction",
        xytext=(0, source_offset),
        textcoords="offset points",
        ha="left",
        va="top",
        fontsize=8,
        color=INK_MUTED,
    )
    fig.savefig(path, dpi=CHART_DPI)
    plt.close(fig)
    return path


def _axes_offset(ax: plt.Axes, points: float):
    """Return the axes transform shifted vertically by ``points``.

    Used to anchor chrome a fixed typographic distance below the axes, independent of
    the figure's overall height.
    """
    return offset_copy(ax.transAxes, fig=ax.figure, x=0.0, y=points, units="points")


def _label_bars_h(ax: plt.Axes, values: Sequence[float], fmt: str = "{:,.0f}") -> None:
    """Direct-label horizontal bars just outside their ends."""
    span = max(values) if len(values) else 0
    offset = span * 0.01 if span else 0.1
    for index, value in enumerate(values):
        ax.text(
            value + offset,
            index,
            fmt.format(value),
            va="center",
            ha="left",
            fontsize=8.5,
            color=INK_SECONDARY,
        )


def barh_top_n(
    frame: pd.DataFrame,
    *,
    label_column: str,
    value_column: str,
    top_n: int,
    title: str,
    subtitle: str,
    source: str,
    path: Path,
    value_format: str = "{:,.0f}",
    xlabel: str | None = None,
) -> Path:
    """Render a horizontal top-N bar chart, largest at the top.

    Horizontal bars are used because pathway and clinical-area labels are long; rotated
    x labels would be far harder to read.
    """
    top = (
        frame.sort_values(value_column, ascending=False)
        .head(top_n)
        .iloc[::-1]  # largest at the top once matplotlib draws bottom-up
        .reset_index(drop=True)
    )
    height = max(3.2, 0.30 * len(top) + 1.7)
    fig, ax = plt.subplots(figsize=(11.0, height))
    ax.barh(
        top[label_column].astype(str),
        top[value_column],
        color=SERIES_1,
        height=0.72,
        linewidth=0,
    )
    _label_bars_h(ax, top[value_column].tolist(), fmt=value_format)
    ax.set_xlabel(xlabel or value_column)
    ax.margins(x=0.12)
    ax.tick_params(axis="y", length=0)
    return _finish(
        fig, ax, title=title, subtitle=subtitle, source=source, path=path, grid_axis="x"
    )


def bar_distribution(
    categories: Sequence[str],
    values: Sequence[float],
    *,
    title: str,
    subtitle: str,
    source: str,
    path: Path,
    xlabel: str,
    ylabel: str,
    log_y: bool = False,
    annotate: bool = True,
    figsize: tuple[float, float] = (11.0, 5.2),
    rotate_labels: int = 0,
) -> Path:
    """Render a single-series vertical bar chart for a discrete distribution."""
    fig, ax = plt.subplots(figsize=figsize)
    positions = range(len(categories))
    ax.bar(list(positions), list(values), color=SERIES_1, width=0.74, linewidth=0)
    ax.set_xticks(list(positions))
    ax.set_xticklabels(
        [str(category) for category in categories],
        rotation=rotate_labels,
        ha="right" if rotate_labels else "center",
    )
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    if log_y:
        ax.set_yscale("log")
        ax.set_ylabel(f"{ylabel} (log scale)")
    else:
        ax.yaxis.set_major_locator(MaxNLocator(integer=True, nbins=7))
    if annotate and not log_y:
        span = max(values) if len(values) else 0
        for position, value in zip(positions, values):
            ax.text(
                position,
                value + span * 0.015,
                f"{value:,.0f}",
                ha="center",
                va="bottom",
                fontsize=8.5,
                color=INK_SECONDARY,
            )
        ax.margins(y=0.14)
    ax.tick_params(axis="x", length=0)
    return _finish(fig, ax, title=title, subtitle=subtitle, source=source, path=path)


def histogram(
    values: Sequence[float],
    *,
    bins: int,
    title: str,
    subtitle: str,
    source: str,
    path: Path,
    xlabel: str,
    ylabel: str,
    annotate_stats: bool = True,
) -> Path:
    """Render a single-series histogram with median and p95 reference lines."""
    series = pd.Series(list(values), dtype="float64").dropna()
    fig, ax = plt.subplots(figsize=(11.0, 5.2))
    ax.hist(series, bins=bins, color=SERIES_1, linewidth=0)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)

    if annotate_stats and not series.empty:
        median = float(series.median())
        p95 = float(series.quantile(0.95))
        for value, label, style in (
            (median, f"median {median:,.0f}", "-"),
            (p95, f"p95 {p95:,.0f}", "--"),
        ):
            ax.axvline(value, color=INK_SECONDARY, linewidth=1.2, linestyle=style)
            ax.annotate(
                label,
                xy=(value, 1.0),
                xycoords=("data", "axes fraction"),
                xytext=(4, -12),
                textcoords="offset points",
                fontsize=8.5,
                color=INK_SECONDARY,
                ha="left",
                va="top",
            )
    return _finish(fig, ax, title=title, subtitle=subtitle, source=source, path=path)


def stacked_share_barh(
    frame: pd.DataFrame,
    *,
    label_column: str,
    primary_column: str,
    primary_label: str,
    secondary_label: str,
    title: str,
    subtitle: str,
    source: str,
    path: Path,
    top_n: int | None = None,
) -> Path:
    """Render a 100% stacked horizontal bar of a share against its remainder.

    Used for internal vs external edge percentage. The two segments are complementary
    by construction, so they are drawn as one part-to-whole bar rather than two
    independent series, with a 2px surface gap between segments.
    """
    working = frame.dropna(subset=[primary_column]).sort_values(
        primary_column, ascending=False
    )
    if top_n is not None:
        working = working.head(top_n)
    working = working.iloc[::-1].reset_index(drop=True)

    height = max(3.4, 0.30 * len(working) + 1.9)
    fig, ax = plt.subplots(figsize=(11.5, height))
    labels = working[label_column].astype(str)
    internal = working[primary_column].astype(float)
    external = 100.0 - internal

    ax.barh(labels, internal, color=SERIES_1, height=0.72, linewidth=0,
            label=primary_label)
    ax.barh(labels, external, left=internal, color=SERIES_2, height=0.72,
            linewidth=2.0, edgecolor=SURFACE, label=secondary_label)

    for index, value in enumerate(internal):
        ax.text(
            min(value + 1.2, 88.0),
            index,
            f"{value:.0f}%",
            va="center",
            ha="left",
            fontsize=8.5,
            color=INK_PRIMARY,
        )
    ax.set_xlim(0, 100)
    ax.set_xlabel("Share of edges leaving the group's pathways (%)")
    ax.tick_params(axis="y", length=0)
    return _finish(
        fig,
        ax,
        title=title,
        subtitle=subtitle,
        source=source,
        path=path,
        grid_axis="x",
        legend_below=True,
    )


# -- Phase 2 chart primitives ----------------------------------------------------------
# Colours below come from the same validated palette as the Phase 1 charts. The
# categorical slots used are blue / orange / aqua: that opening three is the documented
# subset that clears the all-pairs CVD and normal-vision floors, which is the pairlist
# that applies to scatter and dot charts where any two series can sit side by side. The
# sequential ramp is the validated single-hue blue ramp; a heatmap must be one hue,
# light to dark, never a rainbow.
SERIES_3: Final = "#1baf7a"  # aqua

#: Validated single-hue sequential ramp (blue 100 -> 700), lightest first.
SEQUENTIAL_BLUE: Final[tuple[str, ...]] = (
    "#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec", "#5598e7", "#3987e5",
    "#2a78d6", "#256abf", "#1c5cab", "#184f95", "#104281", "#0d366b",
)


def sequential_colormap() -> "matplotlib.colors.LinearSegmentedColormap":
    """Return the validated blue sequential colormap used by every Phase 2 heatmap."""
    from matplotlib.colors import LinearSegmentedColormap

    return LinearSegmentedColormap.from_list("pathways_blue", list(SEQUENTIAL_BLUE))


def heatmap(
    matrix: Sequence[Sequence[float]],
    *,
    row_labels: Sequence[str],
    column_labels: Sequence[str],
    title: str,
    subtitle: str,
    source: str,
    path: Path,
    value_label: str,
    annotate: bool = False,
    value_format: str = "{:.2f}",
    vmax: float | None = None,
) -> Path:
    """Render a sequential heatmap of a family-by-family matrix.

    One hue, light to dark, because the encoded quantity is a magnitude. The lightest
    step is allowed to recede into the surface: near-zero overlap should read as
    "nothing here" rather than competing with the cells that matter.

    Cell values are annotated only for small matrices; past roughly 20x20 the numbers
    become unreadable and the colour carries the signal, with the underlying CSV as the
    exact-value view.
    """
    import numpy as np

    data = np.asarray(matrix, dtype=float)
    rows, columns = data.shape
    cell = 0.42 if max(rows, columns) > 18 else 0.58
    fig, ax = plt.subplots(
        figsize=(
            max(6.5, min(13.0, 3.6 + cell * columns)),
            max(5.0, min(13.0, 2.9 + cell * rows)),
        )
    )
    ax.grid(False)
    image = ax.imshow(
        data,
        cmap=sequential_colormap(),
        aspect="auto",
        vmin=0.0,
        vmax=vmax if vmax is not None else (float(data.max()) if data.size else 1.0),
        interpolation="nearest",
    )
    ax.set_xticks(range(columns))
    ax.set_yticks(range(rows))
    ax.set_xticklabels([str(label) for label in column_labels], rotation=90, fontsize=7.5)
    ax.set_yticklabels([str(label) for label in row_labels], fontsize=7.5)
    ax.tick_params(axis="both", length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)

    if annotate and rows <= 20 and columns <= 20:
        midpoint = (float(data.max()) if data.size else 1.0) * 0.55
        for row in range(rows):
            for column in range(columns):
                value = data[row, column]
                if value <= 0:
                    continue
                ax.text(
                    column,
                    row,
                    value_format.format(value),
                    ha="center",
                    va="center",
                    fontsize=6.8,
                    color=SURFACE if value >= midpoint else INK_PRIMARY,
                )

    colorbar = fig.colorbar(image, ax=ax, fraction=0.030, pad=0.02)
    colorbar.set_label(value_label, color=INK_SECONDARY, fontsize=9)
    colorbar.outline.set_visible(False)
    colorbar.ax.tick_params(labelsize=8, length=0, colors=INK_MUTED)

    ax.set_title(title, loc="left", pad=22, color=INK_PRIMARY)
    ax.annotate(
        subtitle,
        xy=(0.0, 1.0),
        xycoords="axes fraction",
        xytext=(0, 9),
        textcoords="offset points",
        ha="left",
        va="bottom",
        fontsize=9.5,
        color=INK_SECONDARY,
    )
    # The column labels are rotated 90 degrees, so the space they occupy below the axes
    # depends on the longest label, not on the figure height. A fixed offset collides
    # with them on a heatmap with long family names.
    longest_label = max((len(str(label)) for label in column_labels), default=0)
    source_offset = -(24.0 + 5.0 * longest_label)
    ax.annotate(
        source,
        xy=(0.0, 0.0),
        xycoords="axes fraction",
        xytext=(0, source_offset),
        textcoords="offset points",
        ha="left",
        va="top",
        fontsize=8,
        color=INK_MUTED,
    )
    fig.savefig(path, dpi=CHART_DPI)
    plt.close(fig)
    return path


def scatter_by_category(
    frame: pd.DataFrame,
    *,
    x_column: str,
    y_column: str,
    category_column: str,
    label_column: str,
    title: str,
    subtitle: str,
    source: str,
    path: Path,
    xlabel: str,
    ylabel: str,
) -> Path:
    """Render a labelled scatter, one colour per category.

    Capped at three categories: the validated palette's first three slots are the
    documented subset that clears the all-pairs colour-vision floors, which is the
    pairlist a scatter needs. Every point is also directly labelled, so identity is
    never carried by colour alone.
    """
    categories = sorted(frame[category_column].astype(str).unique())
    if len(categories) > 3:
        raise ValueError(
            f"scatter_by_category supports at most 3 categories, got {len(categories)}. "
            "Fold the remainder into 'Other' or facet the chart."
        )
    palette = {
        category: colour
        for category, colour in zip(categories, (SERIES_1, SERIES_2, SERIES_3))
    }

    fig, ax = plt.subplots(figsize=(11.0, 6.6))
    for category in categories:
        subset = frame.loc[frame[category_column].astype(str) == category]
        ax.scatter(
            subset[x_column],
            subset[y_column],
            s=74,
            color=palette[category],
            edgecolor=SURFACE,
            linewidth=2.0,  # 2px surface ring keeps overlapping marks separable
            label=category,
            zorder=3,
        )
    # Points that sit close together would otherwise have their labels printed on top
    # of one another. Nearby labels are staggered above/below and left/right of their
    # point, which is enough to separate them without a label-placement solver.
    placed: list[tuple[float, float]] = []
    x_span = float(frame[x_column].max() - frame[x_column].min()) or 1.0
    y_span = float(frame[y_column].max() - frame[y_column].min()) or 1.0
    for row in frame.sort_values([y_column, x_column], ascending=False).itertuples():
        x_value = float(getattr(row, x_column))
        y_value = float(getattr(row, y_column))
        crowded = sum(
            1
            for other_x, other_y in placed
            if abs(other_x - x_value) < 0.12 * x_span
            and abs(other_y - y_value) < 0.06 * y_span
        )
        offsets = ((8, 4), (8, -11), (-8, 4), (-8, -11))
        x_offset, y_offset = offsets[crowded % len(offsets)]
        ax.annotate(
            str(getattr(row, label_column)),
            xy=(x_value, y_value),
            xytext=(x_offset, y_offset),
            textcoords="offset points",
            fontsize=7.6,
            color=INK_SECONDARY,
            ha="left" if x_offset > 0 else "right",
        )
        placed.append((x_value, y_value))
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.margins(x=0.13, y=0.13)
    return _finish(
        fig,
        ax,
        title=title,
        subtitle=subtitle,
        source=source,
        path=path,
        grid_axis="both",
        legend_below=True,
    )


def grouped_barh(
    frame: pd.DataFrame,
    *,
    label_column: str,
    value_columns: Sequence[str],
    series_labels: Sequence[str],
    title: str,
    subtitle: str,
    source: str,
    path: Path,
    xlabel: str,
    value_format: str = "{:,.1f}",
) -> Path:
    """Render a grouped horizontal bar chart of two or three series.

    Bars within a group are separated by a 2px surface gap. A legend is always present
    for two or more series, and each bar is directly labelled, so the series are
    identifiable without relying on colour.
    """
    if len(value_columns) != len(series_labels):
        raise ValueError("value_columns and series_labels must be the same length")
    if len(value_columns) > 3:
        raise ValueError("grouped_barh supports at most 3 series")

    working = frame.iloc[::-1].reset_index(drop=True)
    positions = range(len(working))
    series_count = len(value_columns)
    height = 0.78 / series_count
    colours = (SERIES_1, SERIES_2, SERIES_3)[:series_count]

    figure_height = max(3.8, 0.42 * len(working) * series_count / 2 + 2.2)
    fig, ax = plt.subplots(figsize=(11.5, figure_height))
    for index, (column, label, colour) in enumerate(zip(value_columns, series_labels, colours)):
        offsets = [
            position + (index - (series_count - 1) / 2) * height for position in positions
        ]
        values = working[column].astype(float).tolist()
        ax.barh(
            offsets,
            values,
            height=height * 0.92,  # leaves a surface gap between adjacent bars
            color=colour,
            linewidth=0,
            label=label,
        )
        span = max(values) if values else 0
        for offset, value in zip(offsets, values):
            ax.text(
                value + (span * 0.012 if span else 0.1),
                offset,
                value_format.format(value),
                va="center",
                ha="left",
                fontsize=7.6,
                color=INK_SECONDARY,
            )
    ax.set_yticks(list(positions))
    ax.set_yticklabels(working[label_column].astype(str))
    ax.set_xlabel(xlabel)
    ax.margins(x=0.16)
    ax.tick_params(axis="y", length=0)
    return _finish(
        fig,
        ax,
        title=title,
        subtitle=subtitle,
        source=source,
        path=path,
        grid_axis="x",
        legend_below=True,
    )


def community_graph(
    nodes: pd.DataFrame,
    edges: pd.DataFrame,
    *,
    node_label_column: str,
    node_size_column: str,
    edge_weight_column: str,
    title: str,
    subtitle: str,
    source: str,
    path: Path,
    max_edges: int = 90,
    circular_layout_limit: int = 30,
) -> Path:
    """Render a family-level aggregate node-link diagram.

    The pathway-level graph is deliberately **not** drawn: at ~840 nodes and ~3,500
    edges it is a hairball that communicates nothing. This aggregates to one node per
    candidate family and keeps only the strongest inter-family edges.

    Two readability rules are applied, and both are stated on the chart rather than
    applied silently:

    * **Families with no inter-family edge are omitted.** A force-directed layout pushes
      isolated nodes to the perimeter, where they take most of the canvas and compress
      the connected core into an unreadable blob. Their count goes in the subtitle.
    * **A circular layout is used up to ``circular_layout_limit`` families.** With a few
      dozen nodes it guarantees no node or label overlap and puts every label outside
      the ring, which a spring layout cannot promise. Above the limit the spring layout
      is used, since a ring of that many labels stops being legible.

    Node area is proportional to pathway count and edge width to transition count, and
    every node is directly labelled, so nothing depends on judging size alone.

    Args:
        nodes: One row per family with ``family_id``, a label and a size column.
        edges: Inter-family edges with ``source``, ``target`` and a weight column.
        max_edges: Keep only this many heaviest edges. Stated on the chart.
        circular_layout_limit: Node count up to which the circular layout is used.
    """
    import numpy as np

    graph = nx.Graph()
    for row in nodes.itertuples():
        graph.add_node(
            row.family_id,
            size=float(getattr(row, node_size_column)),
            label=str(getattr(row, node_label_column)),
        )

    kept = (
        edges.sort_values(edge_weight_column, ascending=False).head(max_edges)
        if not edges.empty else edges
    )
    for row in kept.itertuples():
        if row.source == row.target:
            continue
        if graph.has_node(row.source) and graph.has_node(row.target):
            weight = float(getattr(row, edge_weight_column))
            if graph.has_edge(row.source, row.target):
                graph[row.source][row.target]["weight"] += weight
            else:
                graph.add_edge(row.source, row.target, weight=weight)

    isolated = [node for node in graph.nodes() if graph.degree(node) == 0]
    graph.remove_nodes_from(isolated)
    if graph.number_of_nodes() == 0:
        raise ValueError("No family has an inter-family edge, so there is no graph to draw.")
    if isolated:
        subtitle = (
            f"{subtitle}. {len(isolated)} families with no inter-family transfer are "
            "omitted"
        )

    node_order = sorted(
        graph.nodes(), key=lambda node: (-graph.nodes[node]["size"], node)
    )
    if graph.number_of_nodes() <= circular_layout_limit:
        layout = nx.circular_layout(graph.subgraph(node_order))
        # circular_layout orders by the graph's node order, so re-place by size to put
        # the largest families at consistent positions run to run.
        angles = np.linspace(0, 2 * np.pi, len(node_order), endpoint=False)
        layout = {
            node: np.array([np.cos(angle), np.sin(angle)])
            for node, angle in zip(node_order, angles)
        }
        label_radius = 1.16
    else:
        layout = nx.spring_layout(graph, seed=42, weight="weight", k=1.8, iterations=400)
        label_radius = None

    sizes = np.array([graph.nodes[node]["size"] for node in graph.nodes()], dtype=float)
    scaled = 120.0 + 1500.0 * (sizes / max(sizes.max(), 1.0))

    fig, ax = plt.subplots(figsize=(12.5, 10.0))
    ax.grid(False)
    ax.set_axis_off()

    if graph.number_of_edges():
        weights = np.array(
            [graph[u][v]["weight"] for u, v in graph.edges()], dtype=float
        )
        widths = 0.6 + 4.4 * (weights / max(weights.max(), 1.0))
        nx.draw_networkx_edges(
            graph,
            layout,
            ax=ax,
            width=widths.tolist(),
            edge_color=BASELINE,
            alpha=0.85,
        )
    nx.draw_networkx_nodes(
        graph,
        layout,
        ax=ax,
        node_size=scaled.tolist(),
        node_color=SERIES_1,
        edgecolors=SURFACE,
        linewidths=2.0,
    )
    for node, position in layout.items():
        x, y = float(position[0]), float(position[1])
        if label_radius is not None:
            # Push each label radially outward from the ring, so labels never sit on a
            # node or on one another.
            norm = max((x**2 + y**2) ** 0.5, 1e-9)
            label_x, label_y = x / norm * label_radius, y / norm * label_radius
            ax.text(
                label_x,
                label_y,
                graph.nodes[node]["label"],
                ha="left" if label_x >= 0 else "right",
                va="center",
                fontsize=7.6,
                color=INK_SECONDARY,
            )
        else:
            ax.text(
                x,
                y - 0.06,
                graph.nodes[node]["label"],
                ha="center",
                va="top",
                fontsize=7.4,
                color=INK_SECONDARY,
            )
    if label_radius is not None:
        ax.set_xlim(-2.1, 2.1)
        ax.set_ylim(-1.35, 1.35)

    ax.set_title(title, loc="left", pad=20, color=INK_PRIMARY)
    ax.annotate(
        subtitle,
        xy=(0.0, 1.0),
        xycoords="axes fraction",
        xytext=(0, 8),
        textcoords="offset points",
        ha="left",
        va="bottom",
        fontsize=9.5,
        color=INK_SECONDARY,
    )
    ax.annotate(
        source,
        xy=(0.0, 0.0),
        xycoords="axes fraction",
        xytext=(0, -14),
        textcoords="offset points",
        ha="left",
        va="top",
        fontsize=8,
        color=INK_MUTED,
    )
    fig.savefig(path, dpi=CHART_DPI, bbox_inches="tight")
    plt.close(fig)
    return path
