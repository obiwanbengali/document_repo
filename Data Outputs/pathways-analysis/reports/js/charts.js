/* =====================================================================
   Plotly wrappers for the briefing reports.

   Every chart here follows the same rules:

     - One quantity per axis. No dual-axis charts: two measures on
       different scales get two charts, never two y-axes.
     - Categorical colour comes from the validated palette in fixed slot
       order and is capped at three series, which is the documented subset
       that clears the all-pairs colour-vision separation floors.
     - Heatmaps use a single-hue ramp, light to dark, because they encode
       one magnitude. Never a rainbow.
     - A hover layer is present by default. These are interactive charts in
       a browser; withholding the per-mark value would be a choice to make
       them less useful.
     - Thin marks, recessive gridlines, no chart junk, and text in ink
       colours rather than series colours.
     - Value labels are selective. A number on every mark is noise.

   Plotly is vendored locally (reports/vendor/) so the report makes no
   external network requests when served.
   ===================================================================== */

const CHART_CONFIG = {
  displayModeBar: false,
  responsive: true,
  /* No external requests: the toolbar's image export is local, but the
     whole bar is hidden anyway to keep the page calm. */
  staticPlot: false
};

const FONT_STACK =
  'system-ui, -apple-system, "Helvetica Neue", Helvetica, Arial, sans-serif';

/* Charts rendered through renderChart, kept so a width change can be
   applied to all of them without re-reading the DOM for plot internals. */
const MANAGED_CHARTS = [];

/**
 * Plot a chart at an explicitly measured width.
 *
 * Plotly's own `autosize` is deliberately not used. It sizes a chart from its
 * container for BOTH dimensions, and because the container's height is itself
 * set by the previous plot, a re-measure can shrink the chart until it is
 * clipped by its card. Setting the width explicitly and keeping the height
 * fixed removes that feedback loop: height is a design decision per chart
 * type, width follows the page.
 */
function renderChart(mount, traces, layout) {
  const sized = Object.assign({}, layout, { autosize: false, width: chartWidth(mount) });
  Plotly.newPlot(mount, traces, sized, CHART_CONFIG);
  MANAGED_CHARTS.push({ mount, height: layout.height });
}

function chartWidth(mount) {
  const measured = mount.clientWidth;
  /* A hidden or not-yet-laid-out container measures as zero. Fall back to the
     usual content width rather than Plotly's 700px default, then correct on
     the resize pass once the page is visible. */
  return measured > 40 ? measured : 1040;
}

/**
 * Re-measure every managed chart's width.
 *
 * `responsive` only reacts to window resizes, not to an element becoming
 * visible, so this is called once after the page is revealed and again on
 * genuine resizes.
 */
function resizeAllCharts() {
  requestAnimationFrame(() => {
    MANAGED_CHARTS.forEach(({ mount, height }) => {
      const width = mount.clientWidth;
      if (width > 40) Plotly.relayout(mount, { width, height });
    });
  });
}

let resizeTimer = null;
window.addEventListener('resize', () => {
  window.clearTimeout(resizeTimer);
  resizeTimer = window.setTimeout(resizeAllCharts, 150);
});

/** Layout defaults shared by every chart. */
function baseLayout(overrides) {
  return Object.assign(
    {
      paper_bgcolor: PALETTE.surfaceRaised,
      plot_bgcolor: PALETTE.surfaceRaised,
      font: { family: FONT_STACK, size: 13, color: PALETTE.inkSecondary },
      margin: { l: 70, r: 24, t: 16, b: 52 },
      hoverlabel: {
        bgcolor: PALETTE.inkPrimary,
        bordercolor: PALETTE.inkPrimary,
        font: { family: FONT_STACK, size: 13, color: '#ffffff' }
      },
      showlegend: false,
      xaxis: axisDefaults(),
      yaxis: axisDefaults()
    },
    overrides || {}
  );
}

function axisDefaults(overrides) {
  return Object.assign(
    {
      gridcolor: PALETTE.rule,
      linecolor: PALETTE.ruleStrong,
      zerolinecolor: PALETTE.rule,
      tickfont: { size: 12, color: PALETTE.inkMuted },
      titlefont: { size: 12, color: PALETTE.inkSecondary },
      automargin: true
    },
    overrides || {}
  );
}

/**
 * Vertical bar chart of a banded distribution.
 *
 * Used where the categories have a natural order (size bands, degree
 * bands), because reading left-to-right matches how the bands are read.
 */
function bandedBarChart(mount, bands, options) {
  const opts = options || {};
  const labels = bands.map((band) => band.band);
  const values = bands.map((band) => band.count);
  const percentages = bands.map((band) => band.percentage);

  const trace = {
    type: 'bar',
    x: labels,
    y: values,
    marker: { color: PALETTE.series[0], line: { width: 0 } },
    width: 0.66,
    /* Direct labels on a small number of bars; the hover layer carries the
       detail for everything else. */
    text: values.length <= 10 ? values.map((value) => fmt.int(value)) : null,
    textposition: 'outside',
    textfont: { size: 11, color: PALETTE.inkSecondary },
    cliponaxis: false,
    customdata: percentages,
    hovertemplate:
      `<b>%{x}</b><br>${opts.unit || 'items'}: %{y:,}<br>` +
      'share: %{customdata}%<extra></extra>'
  };

  const layout = baseLayout({
    xaxis: axisDefaults({
      title: { text: opts.xTitle || '', standoff: 12 },
      showgrid: false,
      tickangle: labels.some((label) => String(label).length > 9) ? -30 : 0
    }),
    yaxis: axisDefaults({ title: { text: opts.yTitle || '', standoff: 12 } }),
    height: opts.height || 330,
    margin: { l: 70, r: 24, t: 20, b: 64 }
  });

  renderChart(mount, [trace], layout);
}

/**
 * Horizontal bar chart, largest first.
 *
 * Horizontal because these labels are long clinical names; rotated
 * x-labels would be far harder to read.
 */
function horizontalBarChart(mount, items, options) {
  const opts = options || {};
  const ordered = items.slice().reverse(); // Plotly draws bottom-up.
  const labels = ordered.map((item) => item.label);
  const values = ordered.map((item) => item.value);

  const trace = {
    type: 'bar',
    orientation: 'h',
    x: values,
    y: labels,
    marker: { color: opts.color || PALETTE.series[0], line: { width: 0 } },
    text: values.map((value) => (opts.percent ? fmt.pct(value, 0) : fmt.int(value))),
    textposition: 'outside',
    textfont: { size: 11, color: PALETTE.inkSecondary },
    cliponaxis: false,
    customdata: ordered.map((item) => item.note || ''),
    hovertemplate:
      `<b>%{y}</b><br>${opts.unit || 'value'}: %{x:,}` +
      '%{customdata}<extra></extra>'
  };

  const layout = baseLayout({
    xaxis: axisDefaults({
      title: { text: opts.xTitle || '', standoff: 12 },
      range: opts.percent ? [0, 105] : undefined
    }),
    yaxis: axisDefaults({ showgrid: false, automargin: true }),
    height: opts.height || Math.max(240, 30 * items.length + 90),
    margin: { l: 10, r: 60, t: 16, b: 52 }
  });

  renderChart(mount, [trace], layout);
}

/**
 * Grouped horizontal bar chart of two or three series on one shared scale.
 *
 * A legend is always shown for two or more series, and each bar carries its
 * value, so identity never depends on colour alone.
 */
function groupedBarChart(mount, categories, series, options) {
  const opts = options || {};
  if (series.length > 3) {
    throw new Error(
      'groupedBarChart supports at most three series: the validated palette ' +
      'only clears the all-pairs colour checks for its first three slots.'
    );
  }
  const ordered = categories.slice().reverse();
  const traces = series.map((item, index) => ({
    type: 'bar',
    orientation: 'h',
    name: item.name,
    x: item.values.slice().reverse(),
    y: ordered,
    marker: { color: PALETTE.series[index], line: { width: 0 } },
    text: item.values
      .slice()
      .reverse()
      .map((value) => (opts.percent ? fmt.pct(value, 0) : fmt.int(value))),
    textposition: 'outside',
    textfont: { size: 10, color: PALETTE.inkSecondary },
    cliponaxis: false,
    hovertemplate: `<b>%{y}</b><br>${item.name}: %{x:,}${
      opts.percent ? '%' : ''
    }<extra></extra>`
  }));

  const layout = baseLayout({
    barmode: 'group',
    bargap: 0.28,
    bargroupgap: 0.12,
    showlegend: true,
    legend: {
      orientation: 'h',
      x: 0,
      y: -0.14,
      font: { size: 12, color: PALETTE.inkSecondary }
    },
    xaxis: axisDefaults({
      title: { text: opts.xTitle || '', standoff: 12 },
      range: opts.percent ? [0, 108] : undefined
    }),
    yaxis: axisDefaults({ showgrid: false }),
    height: opts.height || Math.max(280, 34 * categories.length * series.length * 0.62 + 130),
    margin: { l: 10, r: 62, t: 16, b: 74 }
  });

  renderChart(mount, traces, layout);
}

/**
 * 100% stacked bar showing a share against its remainder.
 *
 * Used for internal versus external links, which are complementary by
 * construction: drawing them as two independent series would imply they can
 * vary separately.
 */
function shareBarChart(mount, items, options) {
  const opts = options || {};
  const ordered = items.slice().reverse();
  const labels = ordered.map((item) => item.label);
  const internal = ordered.map((item) => item.value);
  const external = internal.map((value) => 100 - value);

  const traces = [
    {
      type: 'bar',
      orientation: 'h',
      name: opts.primaryLabel || 'Internal',
      x: internal,
      y: labels,
      marker: { color: PALETTE.series[0], line: { width: 0 } },
      text: internal.map((value) => fmt.pct(value, 0)),
      textposition: 'inside',
      insidetextanchor: 'start',
      textfont: { size: 11, color: '#ffffff' },
      hovertemplate: `<b>%{y}</b><br>${opts.primaryLabel || 'Internal'}: %{x:.1f}%<extra></extra>`
    },
    {
      type: 'bar',
      orientation: 'h',
      name: opts.secondaryLabel || 'External',
      x: external,
      y: labels,
      /* 2px surface gap between the two segments so they stay separable. */
      marker: { color: PALETTE.series[1], line: { width: 2, color: PALETTE.surfaceRaised } },
      hovertemplate: `<b>%{y}</b><br>${opts.secondaryLabel || 'External'}: %{x:.1f}%<extra></extra>`
    }
  ];

  const layout = baseLayout({
    barmode: 'stack',
    bargap: 0.3,
    showlegend: true,
    legend: {
      orientation: 'h',
      x: 0,
      y: -0.16,
      font: { size: 12, color: PALETTE.inkSecondary }
    },
    xaxis: axisDefaults({
      title: { text: opts.xTitle || 'Share of handovers (%)', standoff: 12 },
      range: [0, 100]
    }),
    yaxis: axisDefaults({ showgrid: false }),
    height: opts.height || Math.max(280, 30 * items.length + 130),
    margin: { l: 10, r: 24, t: 16, b: 78 }
  });

  renderChart(mount, traces, layout);
}

/**
 * Heatmap of a symmetric family-by-family matrix.
 *
 * One hue, light to dark. The lightest step is allowed to recede into the
 * surface: near-zero overlap should read as "nothing here" rather than
 * competing with the cells that matter. The diagonal is blanked, because a
 * family's overlap with itself is not a finding.
 */
function overlapHeatmap(mount, labels, matrix, options) {
  const opts = options || {};
  const masked = matrix.map((row, i) =>
    row.map((value, j) => (i === j ? null : value))
  );

  const trace = {
    type: 'heatmap',
    z: masked,
    x: labels,
    y: labels,
    colorscale: PALETTE.sequential,
    zmin: 0,
    zmax: opts.zmax === null || opts.zmax === undefined ? undefined : opts.zmax,
    zauto: opts.zmax === null || opts.zmax === undefined,
    hoverongaps: false,
    xgap: 1,
    ygap: 1,
    colorbar: {
      title: { text: opts.scaleTitle || '', side: 'right', font: { size: 11 } },
      thickness: 12,
      len: 0.85,
      outlinewidth: 0,
      tickfont: { size: 11, color: PALETTE.inkMuted }
    },
    hovertemplate:
      `<b>%{y}</b><br>and <b>%{x}</b><br>${opts.unit || 'value'}: %{z}<extra></extra>`
  };

  const layout = baseLayout({
    xaxis: axisDefaults({ tickangle: -45, showgrid: false, ticks: '' }),
    yaxis: axisDefaults({ showgrid: false, ticks: '', autorange: 'reversed' }),
    height: opts.height || Math.max(420, 26 * labels.length + 150),
    margin: { l: 10, r: 24, t: 16, b: 10 }
  });

  renderChart(mount, [trace], layout);
}

/**
 * Scatter of strategies, coloured by evidence basis.
 *
 * Capped at three categories, which is what the palette's first three slots
 * validate for under the all-pairs check that a scatter needs. Every point
 * is directly labelled, so identity is not carried by colour alone.
 */
function strategyScatter(mount, rows, options) {
  const opts = options || {};
  const groups = {};
  rows.forEach((row) => {
    const key = row.basis_label || row.basis;
    (groups[key] = groups[key] || []).push(row);
  });
  const keys = Object.keys(groups).sort();
  if (keys.length > 3) {
    throw new Error('strategyScatter supports at most three bases.');
  }

  const traces = keys.map((key, index) => {
    const items = groups[key];
    return {
      type: 'scatter',
      mode: 'markers+text',
      name: key,
      x: items.map((row) => row.internal_link_percentage),
      y: items.map((row) => row.family_count),
      text: items.map((row) => row.label),
      textposition: 'middle right',
      textfont: { size: 10, color: PALETTE.inkSecondary },
      marker: {
        size: 13,
        color: PALETTE.series[index],
        /* 2px surface ring keeps overlapping points separable. */
        line: { width: 2, color: PALETTE.surfaceRaised }
      },
      customdata: items.map((row) => [row.median_size, row.max_size, row.boundary_pathway_percentage]),
      hovertemplate:
        '<b>%{text}</b><br>candidate families: %{y}<br>' +
        'handovers staying inside a family: %{x:.1f}%<br>' +
        'typical family size: %{customdata[0]}<br>' +
        'largest family: %{customdata[1]}<br>' +
        'pathways on a boundary: %{customdata[2]:.1f}%<extra></extra>'
    };
  });

  const layout = baseLayout({
    showlegend: true,
    legend: {
      orientation: 'h',
      x: 0,
      y: -0.16,
      font: { size: 12, color: PALETTE.inkSecondary }
    },
    xaxis: axisDefaults({
      title: { text: opts.xTitle || 'Handovers staying inside a family (%)', standoff: 12 },
      range: [-8, 118]
    }),
    yaxis: axisDefaults({
      title: { text: opts.yTitle || 'Number of candidate families', standoff: 12 },
      rangemode: 'tozero'
    }),
    height: opts.height || 470,
    margin: { l: 70, r: 130, t: 16, b: 78 }
  });

  renderChart(mount, traces, layout);
}

/**
 * Single horizontal 100% bar broken into ordered segments.
 *
 * Used for the boundary and routing breakdowns, where the parts sum to the
 * whole and the reader's question is "how is the estate split", not "how
 * big is each part in isolation". Segments are shaded along the sequential
 * ramp, because the categories are ordered (from wholly internal to most
 * entangled) rather than unrelated.
 */
function stackedShareBar(mount, segments, options) {
  const opts = options || {};
  const ramp = ['#cde2fb', '#86b6ef', '#2a78d6', '#104281'];
  const traces = segments.map((segment, index) => ({
    type: 'bar',
    orientation: 'h',
    name: segment.label,
    x: [segment.percentage],
    y: [opts.rowLabel || ''],
    marker: {
      color: ramp[index % ramp.length],
      line: { width: 2, color: PALETTE.surfaceRaised }
    },
    text: [segment.percentage >= 6 ? fmt.pct(segment.percentage, 0) : ''],
    textposition: 'inside',
    insidetextanchor: 'middle',
    textfont: {
      size: 12,
      color: index >= 2 ? '#ffffff' : PALETTE.inkPrimary
    },
    customdata: [segment.count === undefined ? '' : fmt.int(segment.count)],
    hovertemplate:
      `<b>${segment.label}</b><br>%{x:.1f}% of pathways` +
      (segment.count === undefined ? '' : '<br>%{customdata} pathways') +
      '<extra></extra>'
  }));

  const layout = baseLayout({
    barmode: 'stack',
    showlegend: true,
    legend: {
      orientation: 'h',
      x: 0,
      y: -0.55,
      font: { size: 12, color: PALETTE.inkSecondary },
      traceorder: 'normal'
    },
    xaxis: axisDefaults({
      title: { text: opts.xTitle || 'Share of pathways (%)', standoff: 12 },
      range: [0, 100]
    }),
    yaxis: axisDefaults({ showgrid: false, showticklabels: false }),
    height: opts.height || 210,
    margin: { l: 10, r: 24, t: 10, b: 96 }
  });

  renderChart(mount, traces, layout);
}

/**
 * Grouped bars of how widely features are shared, one group per feature type.
 *
 * Four sharing bands are shown as an ordered ramp rather than four
 * categorical hues, because the bands are a progression.
 */
function sharingBandChart(mount, byType, options) {
  const opts = options || {};
  const bandNames = byType[0].bands.map((band) => band.band);
  const ramp = ['#cde2fb', '#86b6ef', '#2a78d6', '#104281'];

  const traces = bandNames.map((bandName, index) => ({
    type: 'bar',
    name: bandName,
    x: byType.map((item) => item.label),
    y: byType.map((item) => {
      const band = item.bands.find((entry) => entry.band === bandName);
      return band ? band.count : 0;
    }),
    marker: { color: ramp[index % ramp.length], line: { width: 0 } },
    hovertemplate: `<b>%{x}</b><br>${bandName}: %{y:,} features<extra></extra>`
  }));

  const layout = baseLayout({
    barmode: 'group',
    bargap: 0.3,
    bargroupgap: 0.08,
    showlegend: true,
    legend: {
      orientation: 'h',
      x: 0,
      y: -0.22,
      font: { size: 12, color: PALETTE.inkSecondary },
      traceorder: 'normal'
    },
    xaxis: axisDefaults({ showgrid: false }),
    yaxis: axisDefaults({
      title: { text: opts.yTitle || 'Number of features', standoff: 12 },
      type: opts.logScale ? 'log' : 'linear'
    }),
    height: opts.height || 400,
    margin: { l: 70, r: 24, t: 16, b: 86 }
  });

  renderChart(mount, traces, layout);
}

/**
 * Before-and-after dumbbell chart for merge and split evidence.
 *
 * A dumbbell rather than paired bars: the reader's question is the size and
 * direction of the change, which a connecting line shows directly.
 */
function beforeAfterChart(mount, items, options) {
  const opts = options || {};
  const ordered = items.slice().reverse();
  const labels = ordered.map((item) => item.label);

  const lines = {
    type: 'scatter',
    mode: 'lines',
    x: ordered.flatMap((item) => [item.before, item.after, null]),
    y: ordered.flatMap((item) => [item.label, item.label, null]),
    line: { color: PALETTE.ruleStrong, width: 2 },
    hoverinfo: 'skip',
    showlegend: false
  };

  const before = {
    type: 'scatter',
    mode: 'markers',
    name: opts.beforeLabel || 'Before',
    x: ordered.map((item) => item.before),
    y: labels,
    marker: {
      size: 12,
      color: PALETTE.series[0],
      line: { width: 2, color: PALETTE.surfaceRaised }
    },
    hovertemplate: `<b>%{y}</b><br>${opts.beforeLabel || 'Before'}: %{x:.3f}<extra></extra>`
  };

  const after = {
    type: 'scatter',
    mode: 'markers',
    name: opts.afterLabel || 'After',
    x: ordered.map((item) => item.after),
    y: labels,
    marker: {
      size: 12,
      color: PALETTE.series[1],
      line: { width: 2, color: PALETTE.surfaceRaised }
    },
    hovertemplate: `<b>%{y}</b><br>${opts.afterLabel || 'After'}: %{x:.3f}<extra></extra>`
  };

  const layout = baseLayout({
    showlegend: true,
    legend: {
      orientation: 'h',
      x: 0,
      y: -0.2,
      font: { size: 12, color: PALETTE.inkSecondary }
    },
    xaxis: axisDefaults({
      title: { text: opts.xTitle || '', standoff: 12 },
      rangemode: 'tozero'
    }),
    yaxis: axisDefaults({ showgrid: false }),
    height: opts.height || Math.max(260, 42 * items.length + 120),
    margin: { l: 10, r: 40, t: 16, b: 80 }
  });

  renderChart(mount, [lines, before, after], layout);
}

/**
 * Multi-series line chart on a logarithmic value axis.
 *
 * Used for probability-table growth, where each added dependency multiplies
 * the total rather than adding to it. On a linear axis the smaller options
 * flatten to the baseline and the reader loses the comparison entirely; a log
 * axis keeps all three legible and makes a constant multiple a straight line,
 * which is the shape the data actually has.
 *
 * Capped at three series: the palette's first three slots are the documented
 * subset that clears the all-pairs colour-vision floors, which is the pairlist
 * a line chart with markers needs.
 */
function growthLineChart(mount, series, options) {
  const opts = options || {};
  if (series.length > 3) {
    throw new Error('growthLineChart supports at most three series.');
  }
  const traces = series.map((item, index) => ({
    type: 'scatter',
    mode: 'lines+markers',
    name: item.name,
    x: item.x,
    y: item.y,
    line: { color: PALETTE.series[index], width: 2 },
    marker: {
      size: 9,
      color: PALETTE.series[index],
      /* 2px surface ring keeps overlapping markers separable. */
      line: { width: 2, color: PALETTE.surfaceRaised }
    },
    hovertemplate:
      `<b>${item.name}</b><br>depends on %{x} other variable(s)` +
      '<br>table entries: %{y:,}<extra></extra>'
  }));

  const layout = baseLayout({
    showlegend: true,
    legend: {
      orientation: 'h',
      x: 0,
      y: -0.22,
      font: { size: 12, color: PALETTE.inkSecondary }
    },
    xaxis: axisDefaults({
      title: { text: opts.xTitle || '', standoff: 12 },
      dtick: 1,
      showgrid: false
    }),
    yaxis: axisDefaults({
      title: { text: opts.yTitle || '', standoff: 12 },
      type: 'log',
      /* Label decades only. Plotly's default log minor ticks produce a column of
         2s and 5s between each power of ten, which is unreadable at this size. */
      dtick: 1,
      tickformat: '~s'
    }),
    height: opts.height || 400,
    margin: { l: 88, r: 28, t: 16, b: 86 }
  });

  renderChart(mount, traces, layout);
}

/**
 * Horizontal range bars showing a measured low-to-high interval.
 *
 * Used for the benchmark timings, which are an envelope across several
 * structural cases rather than a single figure. Drawing them as a bar from
 * zero would imply a point estimate the measurement does not support, so the
 * bar starts at the observed low and the endpoints are labelled.
 */
function rangeBarChart(mount, items, options) {
  const opts = options || {};
  const ordered = items.slice().reverse();
  const labels = ordered.map((item) => item.label);
  const lows = ordered.map((item) => item.low);
  const spans = ordered.map((item) => Math.max(item.high - item.low, 0));

  const traces = [
    /* Invisible offset bar carrying the range up to its starting value. */
    {
      type: 'bar',
      orientation: 'h',
      x: lows,
      y: labels,
      marker: { color: 'rgba(0,0,0,0)' },
      hoverinfo: 'skip',
      showlegend: false
    },
    {
      type: 'bar',
      orientation: 'h',
      name: 'Measured range',
      x: spans,
      y: labels,
      marker: { color: PALETTE.series[0], line: { width: 0 } },
      customdata: ordered.map((item) => [item.low, item.high, item.note || '']),
      text: ordered.map(
        (item) => `${item.low.toFixed(1)}–${item.high.toFixed(1)} ms`
      ),
      textposition: 'outside',
      textfont: { size: 11, color: PALETTE.inkSecondary },
      cliponaxis: false,
      hovertemplate:
        '<b>%{y}</b><br>fastest: %{customdata[0]:.2f} ms' +
        '<br>slowest: %{customdata[1]:.2f} ms%{customdata[2]}<extra></extra>',
      showlegend: false
    }
  ];

  const layout = baseLayout({
    barmode: 'stack',
    bargap: 0.4,
    xaxis: axisDefaults({
      title: { text: opts.xTitle || '', standoff: 12 },
      rangemode: 'tozero'
    }),
    yaxis: axisDefaults({ showgrid: false }),
    height: opts.height || Math.max(240, 44 * items.length + 100),
    margin: { l: 10, r: 120, t: 16, b: 60 }
  });

  renderChart(mount, traces, layout);
}
