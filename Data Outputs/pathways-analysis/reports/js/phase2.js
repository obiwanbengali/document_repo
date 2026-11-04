/* =====================================================================
   Phase 2 report: "Discovering candidate Bayesian families"

   Renders the twelve sections from data/phase2-report.json. All
   explanatory copy is here or in the HTML; the payload carries data,
   lineage, evidence class and the metric tooltips only.
   ===================================================================== */

const PHASE2_SECTIONS = [
  'executive_summary',
  'configuration',
  'evidence_sources',
  'strategy_comparison',
  'families',
  'overlap',
  'boundaries',
  'shared_core',
  'routing',
  'merge_candidates',
  'split_candidates',
  'clinical_review',
  'tells_us',
  'conclusion',
  'does_not_tell_us',
  'next_phase',
  'methodology'
];

(async function initPhase2() {
  const status = document.getElementById('load-status');
  try {
    const report = await loadReport('phase2-report.json', PHASE2_SECTIONS);
    applyMeta(report.meta);

    // Reveal before rendering: Plotly measures its container at plot time.
    status.remove();
    document.querySelectorAll('main > section[hidden]').forEach((section) => {
      section.removeAttribute('hidden');
    });

    renderExecutiveSummary('phase2-executive-summary', report.executive_summary);
    renderApproach(report.evidence_sources);
    renderStrategies(report.strategy_comparison);
    renderExplorer(report.families);
    renderOverlap(report.overlap);
    renderBoundaries(report.boundaries);
    renderSharedCore(report.shared_core);
    renderRouting(report.routing);
    renderMergeSplit(report.merge_candidates, report.split_candidates);
    renderClinicalReview(report.clinical_review);
    renderTellsUs(report.tells_us);
    renderConclusion('phase2-conclusion', report.conclusion);
    renderLimits(document.getElementById('limits-list'), report.does_not_tell_us);
    renderNextPhase(report.next_phase);
    renderDefinitions(document.getElementById('methodology'), report.methodology);
    renderConfiguration(report.configuration);
    renderGlossary(document.getElementById('glossary'));

    resizeAllCharts();
    window.addEventListener('load', resizeAllCharts, { once: true });
  } catch (error) {
    if (status.parentNode) status.remove();
    renderLoadError(document.getElementById('report'), error);
    console.error(error);
  }
})();

function renderExecutiveSummary(elementId, summary) {
  const target = document.getElementById(elementId);
  const points = summary.key_points
    .map((point) => `<li>${escapeHtml(point)}</li>`)
    .join('');
  target.innerHTML = `
    <span class="callout__label">Executive summary</span>
    <h3>${escapeHtml(summary.headline)}</h3>
    <p>${escapeHtml(summary.summary)}</p>
    <ul>${points}</ul>
    <p><strong>Bottom line:</strong> ${escapeHtml(summary.bottom_line)}</p>`;
}

/* ---------- 1. How we looked for families ------------------------- */
function renderApproach(sources) {
  const panels = document.getElementById('evidence-panels');

  const native = sources.native;
  const structural = sources.structural;
  const features = sources.features;

  panels.appendChild(
    buildPanel('Evidence A', 'NHS classification', native.description, [
      `${native.groupings.length} existing classifications were tested as groupings`,
      'Immediately recognisable to clinicians, because they already use them',
      'They overlap, and most are very unevenly sized'
    ])
  );
  panels.appendChild(
    buildPanel('Evidence B', 'Connection structure', structural.description, [
      `${structural.methods.length} clustering methods were run independently`,
      'Groups pathways that hand assessments to each other',
      'Owes nothing to the existing classifications, so agreement with them is meaningful'
    ])
  );
  panels.appendChild(
    buildPanel('Evidence C', 'Shared clinical features', features.description, [
      'Shared questions, symptom discriminators, clinical concepts and outcomes',
      'Measured separately per feature type, never averaged into one score',
      'Symptom discriminators proved the strongest signal; clinical concepts the thinnest'
    ])
  );

  document.getElementById(
    'graph-warning'
  ).innerHTML = `<span class="callout__label">Read this before the charts below</span>
    <p><strong>${escapeHtml(sources.warning)}</strong>
    Automatic clustering finds pathways that refer to each other. It has no clinical
    knowledge whatsoever. A cluster becomes a family only once a clinician has agreed that
    it is one, which is why the presented set required clinical-feature support as well as
    connection evidence, and why every family on this page is still marked as needing
    review.</p>`;

  /* Method agreement. One quantity per chart: cluster counts and agreement
     scores are different scales, so agreement gets its own figure and the
     counts ride along in the hover. */
  const methods = structural.methods.filter(
    (method) => method.agreement_with_primary !== null && !method.is_primary
  );
  if (methods.length) {
    const { figure, chart } = buildFigure({
      title: 'How much the clustering methods agree with each other',
      evidenceClass: 'derived',
      looking:
        'Each clustering method compared against the one used for the presented family ' +
        'set. 1.0 would mean the two produced exactly the same grouping; 0.0 would mean ' +
        'agreement no better than chance.',
      tells:
        'The methods agree substantially without being identical. Different algorithms, ' +
        'given no clinical information, largely find the same structure.',
      matters:
        'This is the strongest evidence that the groupings reflect something real in the ' +
        'data rather than an artefact of one algorithm. It says nothing about whether ' +
        'that structure is clinically meaningful.',
      sources: sources.source,
      technical:
        structural.agreement_note +
        ' The measure is the adjusted Rand index, which compares which pairs of pathways ' +
        'are grouped together and ignores how the groups are labelled or how many there ' +
        'are.'
    });
    document.getElementById('method-agreement-figure').appendChild(figure);
    horizontalBarChart(
      chart,
      methods.map((method) => ({
        label: method.label.replace('Connection clusters ', ''),
        value: method.agreement_with_primary,
        note: `<br>clusters found: ${method.clusters_found}<br>largest: ${method.largest_cluster} pathways`
      })),
      { xTitle: 'Agreement with the primary method (0 to 1)', unit: 'agreement' }
    );
  }
}

function buildPanel(eyebrow, title, description, points) {
  const panel = document.createElement('div');
  panel.className = 'panel';
  panel.innerHTML = `
    <p class="panel__eyebrow">${escapeHtml(eyebrow)}</p>
    <h4>${escapeHtml(title)}</h4>
    <p>${escapeHtml(description)}</p>
    <ul>${points.map((point) => `<li>${escapeHtml(point)}</li>`).join('')}</ul>`;
  return panel;
}

/* ---------- 2. Strategy comparison -------------------------------- */
function renderStrategies(comparison) {
  const usable = comparison.rows.filter(
    (row) => row.family_count > 1 && row.internal_link_percentage !== null
  );

  const scatter = buildFigure({
    title: 'Every grouping approach: self-containment against number of families',
    evidenceClass: 'candidate',
    looking:
      'One point per grouping approach. Further right means its families keep more of ' +
      'their handovers inside themselves. Higher means it produces more families. Colour ' +
      'shows which kind of evidence the approach is based on.',
    tells:
      'The approaches spread widely, and the trade-off is visible: the NHS classifications ' +
      'that are most recognisable sit on the left, with low self-containment, while the ' +
      'connection clusters sit on the right but produce many small groups. The hybrid ' +
      'approaches sit between them.',
    matters:
      'There is no approach that is both highly self-contained and small in number. Any ' +
      'choice accepts a trade-off, and this chart makes the shape of that trade-off ' +
      'explicit rather than leaving it implicit in a single recommendation.',
    sources: comparison.source,
    technical:
      comparison.definitions.internal_link_percentage +
      ' Approaches producing a single family are excluded, since self-containment is not ' +
      'meaningful for them. Hover a point for its family sizes and boundary share.'
  });
  document.getElementById('strategy-scatter-figure').appendChild(scatter.figure);
  strategyScatter(scatter.chart, usable);

  /* Percentages only, so both series share one scale. Family counts are a
     different quantity and stay in the scatter and the table. */
  const ranked = usable
    .slice()
    .sort((a, b) => b.internal_link_percentage - a.internal_link_percentage);
  const bars = buildFigure({
    title: 'Self-containment against boundary traffic',
    evidenceClass: 'candidate',
    looking:
      'For each approach: the share of handovers that stay inside a family (blue), and ' +
      'the share of pathways that sit on a boundary with another family (orange). Both ' +
      'are percentages, so they share one scale.',
    tells:
      'The two measures move in opposite directions. Approaches whose families retain ' +
      'their own handovers also have fewer pathways sitting on boundaries — but no ' +
      'approach eliminates boundary pathways entirely.',
    matters:
      'Boundary pathways are where separate models would have to coordinate. The lower ' +
      'that share, the less coordination a federated design would need; no approach ' +
      'reduces it to zero.',
    sources: comparison.source,
    technical: comparison.definitions.boundary_pathway_percentage
  });
  document.getElementById('strategy-bars-figure').appendChild(bars.figure);
  groupedBarChart(
    bars.chart,
    ranked.map((row) => row.label),
    [
      {
        name: 'Handovers staying inside a family',
        values: ranked.map((row) => row.internal_link_percentage)
      },
      {
        name: 'Pathways sitting on a boundary',
        values: ranked.map((row) => row.boundary_pathway_percentage || 0)
      }
    ],
    { percent: true, xTitle: 'Percentage' }
  );

  document.getElementById(
    'no-winner-note'
  ).innerHTML = `<p><strong>No approach is preferred here.</strong> ${escapeHtml(
    comparison.no_winner_note
  )}</p>`;

  document
    .getElementById('strategy-table')
    .appendChild(
      buildTableDisclosure(
        'All fifteen approaches, with every measure',
        [
          { label: 'Approach', value: (row) => row.label },
          { label: 'Based on', value: (row) => row.basis_label },
          { label: 'Families', numeric: true, value: (row) => fmt.int(row.family_count) },
          { label: 'Typical size', numeric: true, value: (row) => fmt.decimal(row.median_size, 0) },
          { label: 'Largest', numeric: true, value: (row) => fmt.int(row.max_size) },
          {
            label: 'Handovers kept inside',
            numeric: true,
            value: (row) => fmt.pct(row.internal_link_percentage, 1)
          },
          {
            label: 'On a boundary',
            numeric: true,
            value: (row) => fmt.pct(row.boundary_pathway_percentage, 1)
          },
          {
            label: 'Pathway in several families?',
            value: (row) => (row.overlapping ? 'yes' : 'no')
          },
          { label: 'Presented set', value: (row) => (row.is_primary ? 'yes' : '') }
        ],
        comparison.rows
      )
    );
}

/* ---------- 3. Candidate family explorer -------------------------- */
function renderExplorer(families) {
  const select = document.getElementById('family-select');
  const panel = document.getElementById('family-panel');
  const tooltips = families.metric_tooltips || {};

  families.rows.forEach((family, index) => {
    const option = document.createElement('option');
    option.value = String(index);
    option.textContent = `${family.name} — ${fmt.int(family.pathway_count)} pathway${
      family.pathway_count === 1 ? '' : 's'
    } (${family.family_id})`;
    select.appendChild(option);
  });

  function show(index) {
    const family = families.rows[index];
    panel.innerHTML = '';

    const head = document.createElement('div');
    head.className = 'explorer__title';
    head.innerHTML = `
      <h3>${escapeHtml(family.name)}</h3>
      <span class="badge badge--candidate">Candidate</span>
      <span class="explorer__basis">${escapeHtml(family.family_id)} · based on
        ${escapeHtml(family.basis_label)}</span>`;
    panel.appendChild(head);

    const nameNote = document.createElement('p');
    nameNote.style.marginTop = '0.75rem';
    nameNote.style.fontSize = '0.92rem';
    nameNote.style.color = 'var(--ink-secondary)';
    nameNote.textContent = family.is_named_from_metadata
      ? `Named after its ${family.name_basis}.`
      : 'This family has no dominant NHS classification, so it has deliberately not been ' +
        'given a clinical name. Whether there is a clinical grouping here that the ' +
        'existing classifications do not capture is a question for review.';
    panel.appendChild(nameNote);

    const metrics = document.createElement('div');
    metrics.className = 'metric-grid';
    [
      ['Pathways', fmt.int(family.pathway_count), 'pathway_count'],
      ['Questions', fmt.int(family.unique_questions), 'unique_questions'],
      ['Symptom discriminators', fmt.int(family.unique_discriminators), 'unique_discriminators'],
      ['Clinical concepts', fmt.int(family.unique_snomed), 'unique_snomed'],
      ['Possible outcomes', fmt.int(family.unique_dispositions), 'unique_dispositions'],
      [
        'Handovers kept inside',
        fmt.pct(family.internal_link_percentage, 1),
        'internal_link_percentage'
      ],
      [
        'Handovers leaving',
        fmt.pct(family.external_link_percentage, 1),
        'external_link_percentage'
      ],
      ['Pathways on a boundary', fmt.int(family.boundary_pathway_count), 'boundary_pathway_count'],
      [
        'Pathways linking several families',
        fmt.int(family.cross_family_hub_count),
        'cross_family_hub_count'
      ],
      [
        'Widely shared features used',
        fmt.int(family.shared_core_dependencies),
        'shared_core_dependencies'
      ]
    ].forEach(([label, value, key]) => {
      metrics.appendChild(buildMetric(label, value, tooltips[key]));
    });
    panel.appendChild(metrics);

    panel.appendChild(
      buildFieldRow('Most common clinical areas', family.clinical_areas, tooltips.clinical_areas)
    );
    panel.appendChild(
      buildFieldRow('Most common symptom groups', family.symptom_groups, tooltips.symptom_groups)
    );
    panel.appendChild(
      buildFieldRow(
        'Overlaps strongly with',
        family.overlapping_families,
        tooltips.overlapping_families,
        'No other family passes the high-overlap threshold. Weaker overlaps may still ' +
          'exist — see the overlap grid below.'
      )
    );

    const cohesion = document.createElement('div');
    cohesion.className = 'field-row';
    const cohesionLabel = document.createElement('div');
    cohesionLabel.className = 'field-row__label';
    cohesionLabel.appendChild(document.createTextNode('How well it holds together'));
    cohesionLabel.appendChild(buildTooltip(tooltips.cohesion));
    const cohesionValue = document.createElement('div');
    cohesionValue.className = 'field-row__value';
    cohesionValue.textContent = fmt.sentence(family.cohesion);
    cohesion.appendChild(cohesionLabel);
    cohesion.appendChild(cohesionValue);
    panel.appendChild(cohesion);

    if (family.notes) {
      const notes = document.createElement('div');
      notes.className = 'field-row';
      notes.innerHTML = `
        <div class="field-row__label">Points to note</div>
        <div class="field-row__value">${escapeHtml(fmt.sentence(family.notes))}</div>`;
      panel.appendChild(notes);
    }

    const review = document.createElement('div');
    review.className = 'callout';
    review.style.margin = '1.5rem 0 0';
    review.innerHTML =
      '<p><strong>Clinical review required.</strong> ' +
      escapeHtml(families.review_note) +
      '</p>';
    panel.appendChild(review);
  }

  select.addEventListener('change', (event) => show(Number(event.target.value)));
  show(0);

  const lineage = document.createElement('details');
  lineage.className = 'disclosure';
  lineage.style.border = '1px solid var(--rule)';
  lineage.style.borderRadius = 'var(--radius)';
  lineage.innerHTML = `
    <summary>Technical detail and data source</summary>
    <div class="disclosure__body">
      <p>
        <span class="badge badge--candidate">Candidate</span>
        Pathway titles, question text and feature descriptions are deliberately not loaded
        into this page. They are clinical content and are held in the detailed evidence
        files, including the per-family clinical review pack.
      </p>
      <p><strong>Source</strong><br>${families.source
        .map((path) => `<span class="lineage">${escapeHtml(path)}</span>`)
        .join('')}</p>
    </div>`;
  document.getElementById('explorer-lineage').appendChild(lineage);
}

/**
 * Return the given percentile of a matrix's non-zero off-diagonal values.
 *
 * Used to cap a colour scale against a long tail. Returns null when there is
 * nothing to cap, so the caller falls back to the true maximum.
 */
function percentileCap(matrix, percentile) {
  const values = [];
  matrix.forEach((row, i) =>
    row.forEach((value, j) => {
      if (i !== j && value > 0) values.push(value);
    })
  );
  if (values.length < 8) return null;
  values.sort((a, b) => a - b);
  const index = Math.min(values.length - 1, Math.floor(values.length * percentile));
  const cap = values[index];
  const peak = values[values.length - 1];
  /* Only cap where the tail is genuinely extreme. */
  return peak > cap * 1.6 ? cap : null;
}

function buildFieldRow(label, values, tooltip, emptyText) {
  const row = document.createElement('div');
  row.className = 'field-row';
  const labelNode = document.createElement('div');
  labelNode.className = 'field-row__label';
  labelNode.appendChild(document.createTextNode(label));
  labelNode.appendChild(buildTooltip(tooltip));
  row.appendChild(labelNode);

  if (!values || !values.length) {
    const empty = document.createElement('div');
    empty.className = 'field-row__value';
    empty.style.color = 'var(--ink-muted)';
    empty.textContent = emptyText || 'Not recorded';
    row.appendChild(empty);
    return row;
  }

  const list = document.createElement('div');
  list.className = 'tag-list';
  values.forEach((value) => {
    const tag = document.createElement('span');
    tag.className = 'tag';
    tag.textContent = value;
    list.appendChild(tag);
  });
  row.appendChild(list);
  return row;
}

/* ---------- 4. Family overlap ------------------------------------- */
function renderOverlap(overlap) {
  const { figure, chart, controls } = buildFigure({
    title: 'Overlap between the largest candidate families',
    evidenceClass: 'candidate',
    looking:
      'A grid of candidate families against each other. Darker cells mean more overlap. ' +
      'Each family\'s overlap with itself is left blank, since that is not a finding. ' +
      'Use the buttons to change which kind of overlap is shown.',
    tells:
      'A handful of the larger families overlap substantially, both in the assessments ' +
      'they exchange and in the clinical vocabulary they share. Most pairs overlap very ' +
      'little.',
    matters:
      'These are the places where a boundary between two models would be least clear-cut, ' +
      'and where clinical judgement is most needed to decide whether the two groups are ' +
      'really one clinical area.',
    sources: overlap.source,
    technical:
      `Showing the ${overlap.families_shown} largest of ${overlap.families_total} ` +
      `candidate families. ${overlap.excluded_single_pathway} single-pathway families are ` +
      'excluded: they produce empty rows, and a pair of them can score a perfect ' +
      'similarity from a handful of shared items, which is arithmetically true and ' +
      'analytically meaningless.',
    withControls: true
  });
  document.getElementById('overlap-figure').appendChild(figure);

  const measures = overlap.measure_order || Object.keys(overlap.matrices);
  const description = document.createElement('p');
  description.style.margin = '0 0 0.35rem';
  description.style.fontSize = '0.88rem';
  description.style.color = 'var(--ink-secondary)';
  description.style.flexBasis = '100%';

  function draw(measure) {
    const matrix = overlap.matrices[measure];
    /* Handover counts have a long tail: one pair can exceed the next by an
       order of magnitude, which on a linear colour scale washes every other
       cell out to near-white. The scale is therefore capped at the 95th
       percentile of the non-zero values and the cap is stated below the
       chart, so the compression is a declared choice rather than a silent
       distortion. Similarity measures are already bounded 0 to 1 and need
       no cap. */
    const cap = measure === 'transitions' ? percentileCap(matrix, 0.95) : null;
    overlapHeatmap(chart, overlap.family_labels, matrix, {
      scaleTitle: overlap.measure_labels[measure],
      unit: measure === 'transitions' ? 'handovers' : 'similarity (0 to 1)',
      zmax: cap
    });
    description.textContent = overlap.measure_descriptions[measure];
    if (cap !== null) {
      const peak = Math.max(...matrix.flat());
      description.textContent +=
        ` Shading is capped at ${fmt.int(Math.round(cap))} handovers so the smaller ` +
        `values stay visible; the busiest pair reaches ${fmt.int(peak)}. Hover any ` +
        'cell for its exact figure.';
    }
    controls.querySelectorAll('button.chip').forEach((button) => {
      button.setAttribute('aria-pressed', String(button.dataset.measure === measure));
    });
  }

  measures.forEach((measure) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'chip';
    button.dataset.measure = measure;
    button.textContent = overlap.measure_labels[measure];
    button.addEventListener('click', () => draw(measure));
    controls.appendChild(button);
  });
  controls.appendChild(description);
  draw(overlap.default_measure);

  document.getElementById(
    'overlap-note'
  ).innerHTML = `<span class="callout__label">How to read overlap</span>
    <p>${escapeHtml(overlap.interpretation_note)}</p>`;
}

/* ---------- 5. Boundary pathways ---------------------------------- */
function renderBoundaries(boundaries) {
  const cards = document.getElementById('boundary-cards');
  [
    {
      label: 'Pathways placed in a family',
      value: boundaries.pathways_classified,
      explanation: 'Every active pathway is placed in the presented candidate family set.'
    },
    {
      label: 'Sitting on a boundary',
      value: boundaries.boundary_pathway_count,
      explanation:
        `${fmt.pct(
          boundaries.boundary_pathway_percentage,
          0
        )} of pathways connect to a pathway outside their own family.`
    },
    {
      label: 'Connecting several families',
      value: (boundaries.buckets.find((b) => b.key === 'cross_family_hub') || {}).count,
      explanation:
        'These would need the most careful handling in any design that separated the ' +
        'families.'
    }
  ].forEach((card) => cards.appendChild(buildStatCard(card)));

  const { figure, chart } = buildFigure({
    title: 'How pathways sit relative to their family boundary',
    evidenceClass: 'candidate',
    looking:
      'All pathways in the presented family set, split by how far outside their own ' +
      'family they reach. The shades run from wholly inside one family to connecting ' +
      'several at once.',
    tells:
      `Only ${fmt.pct(
        (boundaries.buckets.find((b) => b.key === 'internal_pathway') || {}).percentage,
        0
      )} of pathways sit wholly inside one family. The majority reach outside it to some ` +
      'degree.',
    matters:
      'This is the clearest single measure of how separable the estate is. A design using ' +
      'separate models would need a way of handling every pathway that is not wholly ' +
      'internal, and that is most of them.',
    sources: boundaries.source,
    technical:
      boundaries.classification_note +
      ' The bands are cumulative in severity rather than clinical categories: a pathway ' +
      'is counted in the most entangled band that applies to it.'
  });
  document.getElementById('boundary-figure').appendChild(figure);
  stackedShareBar(chart, boundaries.buckets, { rowLabel: 'All pathways' });

  document.getElementById('boundary-note').innerHTML = `<p><strong>These labels describe
    wiring, not clinical importance.</strong> ${escapeHtml(
      boundaries.classification_note
    )}</p>`;
}

/* ---------- 6. Shared core ---------------------------------------- */
function renderSharedCore(core) {
  const cards = document.getElementById('shared-core-cards');
  [
    {
      label: 'Widely shared features',
      value: core.totals.shared_core_candidates,
      explanation:
        `Questions, discriminators, clinical concepts and outcomes used by at least ` +
        `${core.totals.threshold_families} candidate families.`
    },
    {
      label: 'Duplicate copies implied',
      value: core.totals.duplication_if_separated,
      explanation: core.definitions.duplication_if_separated
    }
  ].forEach((card) => cards.appendChild(buildStatCard(card)));

  const { figure, chart } = buildFigure({
    title: 'How widely each kind of content is shared between families',
    evidenceClass: 'candidate',
    looking:
      'For each kind of content, how many individual items are used by one family only, ' +
      'by two, by three to five, and by six or more. The scale is logarithmic because ' +
      'single-family questions outnumber every other group by an order of magnitude.',
    tells:
      'Most content belongs to one family, but a substantial minority is used across many. ' +
      'Outcomes are the most widely shared: nearly every family can reach a similar set.',
    matters:
      'The widely shared items are the ones a design has to make a decision about. They ' +
      'would either be duplicated in each family that uses them, or held in one shared ' +
      'place with the coordination that implies.',
    sources: core.source,
    technical:
      'Counts are per candidate family in the presented set. The same item can be counted ' +
      'in several families, which is the point of the measure.'
  });
  document.getElementById('shared-core-figure').appendChild(figure);
  sharingBandChart(chart, core.by_type, {
    yTitle: 'Number of items (log scale)',
    logScale: true
  });

  document
    .getElementById('shared-core-figure')
    .appendChild(
      buildTableDisclosure(
        'Shared content by kind, with exact figures',
        [
          { label: 'Kind of content', value: (row) => row.label },
          { label: 'Total items', numeric: true, value: (row) => fmt.int(row.total) },
          { label: 'Used by 1 family', numeric: true, value: (row) => fmt.int(row.bands[0].count) },
          { label: '2 families', numeric: true, value: (row) => fmt.int(row.bands[1].count) },
          { label: '3-5 families', numeric: true, value: (row) => fmt.int(row.bands[2].count) },
          { label: '6 or more', numeric: true, value: (row) => fmt.int(row.bands[3].count) },
          { label: 'Most families for one item', numeric: true, value: (row) => fmt.int(row.max_families) },
          {
            label: 'Duplicate copies implied',
            numeric: true,
            value: (row) => fmt.int(row.duplication_if_separated)
          }
        ],
        core.by_type
      )
    );

  document.getElementById(
    'shared-core-note'
  ).innerHTML = `<span class="callout__label">This is not a conclusion</span>
    <p>${escapeHtml(core.interpretation_note)}</p>`;
}

/* ---------- 7. Routing ambiguity ---------------------------------- */
function renderRouting(routing) {
  const { figure, chart } = buildFigure({
    title: 'How clearly each pathway belongs to one family',
    evidenceClass: 'candidate',
    looking:
      'All pathways in the presented family set, split by how clear-cut their family ' +
      'placement is when judged on structure alone.',
    tells:
      `${fmt.pct(
        routing.association[0].percentage,
        0
      )} of pathways clearly belong to one family. The rest could plausibly sit in more ` +
      `than one, and ${fmt.pct(
        routing.association[2].percentage,
        0
      )} are genuinely ambiguous — two or more families match them almost equally well.`,
    matters: routing.why_it_matters,
    sources: routing.source,
    technical:
      routing.optimistic_bound_note +
      ' Placement is scored from a weighted combination of connection and shared-feature ' +
      'evidence. The weights are configurable and are not clinically validated; the ' +
      'individual component scores are exported per pathway in the detailed evidence.'
  });
  document.getElementById('routing-figure').appendChild(figure);
  stackedShareBar(chart, routing.association, { rowLabel: 'All pathways' });

  const plausible = buildFigure({
    title: 'How many families each pathway could plausibly belong to',
    evidenceClass: 'candidate',
    looking:
      'The same pathways counted a different way: not how clear the best match is, but ' +
      'how many families are a reasonable match at all.',
    tells:
      `${fmt.pct(
        routing.plausible_families[0].percentage,
        0
      )} of pathways have only one plausible family. A meaningful minority have two, and ` +
      `${fmt.pct(routing.plausible_families[2].percentage, 0)} have three or more.`,
    matters:
      'Pathways with several plausible families are candidates for belonging to more than ' +
      'one, rather than being forced into a single choice. The analysis allows that; ' +
      'whether it is the right answer is a clinical and design question.',
    sources: routing.source,
    technical:
      'A family counts as plausible for a pathway when its match score reaches a ' +
      'configured fraction of the best-matching family\'s score.'
  });
  document.getElementById('plausible-figure').appendChild(plausible.figure);
  stackedShareBar(
    plausible.chart,
    routing.plausible_families.map((item) => ({
      label: item.label,
      percentage: item.percentage
    })),
    { rowLabel: 'All pathways' }
  );

  document.getElementById(
    'routing-note'
  ).innerHTML = `<p><strong>Read this as the best case.</strong> ${escapeHtml(
    routing.optimistic_bound_note
  )}</p>`;
}

/* ---------- 8. Merge and split evidence --------------------------- */
function renderMergeSplit(merges, splits) {
  document.getElementById(
    'merge-caveat'
  ).innerHTML = `<span class="callout__label">Why one measure is not used here</span>
    <p>${escapeHtml(merges.mechanical_caveat)}</p>`;

  const substantial = merges.rows.filter((row) => Math.min(row.pathways_a, row.pathways_b) >= 5);
  const shown = substantial.length ? substantial : merges.rows;

  if (shown.length) {
    const { figure, chart } = buildFigure({
      title: 'What would happen to clinical similarity if these families were combined',
      evidenceClass: 'candidate',
      looking:
        'For each strongly overlapping pair: how much clinical vocabulary its pathways ' +
        'share before combining (blue) and after (orange). A line moving left means the ' +
        'combined family would be less clinically alike than its parts.',
      tells:
        `${merges.improving_clinical_similarity} of the ${merges.tested} pairs tested ` +
        'would increase clinical similarity. The others would reduce it: the pathways ' +
        'connect to each other without being clinically alike.',
      matters:
        'On this evidence the overlap between these families looks like shared vocabulary ' +
        'and shared routing rather than a boundary in the wrong place. That is not a ' +
        'reason not to combine them — a clinician may still want to — but it is not ' +
        'support for doing so.',
      sources: merges.source,
      technical:
        merges.no_recommendation_note +
        ' Only pairs where both families hold at least five pathways are charted; a pair ' +
        'of very small families overlaps strongly by arithmetic rather than by substance.'
    });
    document.getElementById('merge-figure').appendChild(figure);
    beforeAfterChart(
      chart,
      shown.map((row) => ({
        label: `${row.family_a} + ${row.family_b}`,
        before: row.clinical_similarity_before,
        after: row.clinical_similarity_after
      })),
      {
        beforeLabel: 'Before combining',
        afterLabel: 'After combining',
        xTitle: 'Shared clinical vocabulary (0 to 1)'
      }
    );

    document
      .getElementById('merge-table')
      .appendChild(
        buildTableDisclosure(
          'Overlapping pairs, with the evidence that flagged each one',
          [
            { label: 'Family', value: (row) => row.family_a_name },
            { label: 'and', value: (row) => row.family_b_name },
            { label: 'Sizes', value: (row) => `${row.pathways_a} + ${row.pathways_b}` },
            { label: 'Flagged because of', value: (row) => row.why_flagged },
            {
              label: 'Handovers kept inside, before',
              numeric: true,
              value: (row) => fmt.pct(row.internal_link_before, 1)
            },
            {
              label: 'After',
              numeric: true,
              value: (row) => fmt.pct(row.internal_link_after, 1)
            },
            {
              label: 'Clinical similarity change',
              numeric: true,
              value: (row) => fmt.decimal(row.clinical_similarity_change, 3)
            },
            { label: 'Structural effect', value: (row) => row.verdict }
          ],
          merges.rows
        )
      );
  }

  document.getElementById(
    'split-caveat'
  ).innerHTML = `<span class="callout__label">The mirror image</span>
    <p>${escapeHtml(splits.mechanical_caveat)}</p>`;

  if (splits.rows.length) {
    const { figure, chart } = buildFigure({
      title: 'What would happen to clinical similarity if these families were divided',
      evidenceClass: 'candidate',
      looking:
        'For each family large or loosely-knit enough to test: how much clinical ' +
        'vocabulary its pathways share now (blue), and the size-weighted average across ' +
        'the parts if it were divided (orange).',
      tells:
        'Dividing these families raises clinical similarity within the resulting parts in ' +
        'almost every case. Each part is more clinically alike than the whole was.',
      matters:
        'That is a genuine signal that some of the larger candidate families contain more ' +
        'than one clinical grouping. It does not say where the division should fall, or ' +
        'whether the resulting parts would be sensible units for clinicians.',
      sources: splits.source,
      technical:
        splits.no_recommendation_note +
        ` ${splits.families_triggered} families met a trigger for testing and ` +
        `${splits.proposals_tested} division proposals were measured across two methods. ` +
        'The strongest by family size are charted.'
    });
    document.getElementById('split-figure').appendChild(figure);
    beforeAfterChart(
      chart,
      splits.rows.map((row) => ({
        label: `${row.family_id} (${row.parts} parts)`,
        before: row.clinical_similarity_before,
        after: row.clinical_similarity_after
      })),
      {
        beforeLabel: 'As one family',
        afterLabel: 'If divided',
        xTitle: 'Shared clinical vocabulary (0 to 1)'
      }
    );

    document
      .getElementById('split-table')
      .appendChild(
        buildTableDisclosure(
          'Families tested for division, with the evidence that flagged each one',
          [
            { label: 'Family', value: (row) => row.family_name },
            { label: 'Pathways', numeric: true, value: (row) => fmt.int(row.pathways_before) },
            { label: 'Divided by', value: (row) => row.method_label },
            { label: 'Parts', numeric: true, value: (row) => fmt.int(row.parts) },
            { label: 'Part sizes', value: (row) => row.part_sizes },
            { label: 'Flagged because of', value: (row) => row.why_flagged },
            {
              label: 'Clinical similarity change',
              numeric: true,
              value: (row) => fmt.decimal(row.clinical_similarity_change, 3)
            },
            { label: 'Structural effect', value: (row) => row.verdict }
          ],
          splits.rows
        )
      );
  }
}

/* ---------- 9. Clinical review ------------------------------------ */
function renderClinicalReview(review) {
  const cards = document.getElementById('clinical-cards');
  review.items.forEach((item) =>
    cards.appendChild(
      buildStatCard({ label: item.label, value: item.value, explanation: item.detail })
    )
  );

  const questions = document.getElementById('clinical-questions');
  review.questions.forEach((question) => {
    const item = document.createElement('li');
    item.textContent = question;
    questions.appendChild(item);
  });

  document.getElementById(
    'review-pack-note'
  ).innerHTML = `<p><strong>A review document already exists.</strong> ${escapeHtml(
    review.review_pack_note
  )} It is held at <span class="lineage">${escapeHtml(
    review.review_pack
  )}</span> and contains the clinical detail deliberately left out of this page.</p>`;
}

/* ---------- 10. What Phase 2 tells us ----------------------------- */
function renderTellsUs(cards) {
  const grid = document.getElementById('tells-cards');
  cards.forEach((card) => grid.appendChild(buildInsightCard(card)));
}

function renderConclusion(elementId, conclusion) {
  const target = document.getElementById(elementId);
  const paragraphs = conclusion.paragraphs
    .map((paragraph) => `<p>${escapeHtml(paragraph)}</p>`)
    .join('');
  target.innerHTML = `
    <span class="callout__label">Phase conclusion</span>
    <h3>${escapeHtml(conclusion.title)}</h3>
    ${paragraphs}
    <p><strong>Next question:</strong> ${escapeHtml(conclusion.next_question)}</p>`;
}

/* ---------- 12. Next: Phase 3 ------------------------------------- */
function renderNextPhase(next) {
  document.getElementById('next-description').textContent = next.description;

  const options = document.getElementById('next-options');
  next.options.forEach((option, index) => {
    const panel = document.createElement('div');
    panel.className = 'panel';
    panel.innerHTML = `
      <p class="panel__eyebrow">Option ${index + 1}</p>
      <h4>${escapeHtml(option.label)}</h4>
      <p>${escapeHtml(option.detail)}</p>`;
    options.appendChild(panel);
  });

  const criteria = document.getElementById('next-criteria');
  next.criteria.forEach((item) => {
    const li = document.createElement('li');
    li.textContent = item;
    criteria.appendChild(li);
  });

  const inputs = document.getElementById('next-inputs');
  next.inputs_needed.forEach((item) => {
    const li = document.createElement('li');
    li.textContent = item;
    inputs.appendChild(li);
  });
}

/* ---------- Configuration disclosure ------------------------------ */
function renderConfiguration(configuration) {
  document.getElementById('config-note').textContent = configuration.note;
  document
    .getElementById('config-table')
    .appendChild(
      buildTableDisclosure(
        `All ${configuration.settings.length} settings`,
        [
          { label: 'Setting', value: (row) => row.setting },
          { label: 'Value', value: (row) => row.value }
        ],
        configuration.settings
      )
    );
}
