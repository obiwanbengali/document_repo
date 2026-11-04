/* =====================================================================
   Phase 3 report: "Comparing architectures"

   Renders the sections from data/phase3-report.json, following the same
   contract as Phase 1 and Phase 2: the payload carries data, lineage and
   evidence class; this file and the HTML carry the prose.

   Phase 3 has one obligation the earlier phases did not. Its figures bear
   directly on the architecture decision, so every section states what kind
   of number it is showing — measured, modelled under stated assumptions,
   or illustrative — and the decision gates are shown before any of them.
   ===================================================================== */

const PHASE3_SECTIONS = [
  'executive_summary',
  'status',
  'representations',
  'cpt_growth',
  'benchmark',
  'runtime',
  'cost',
  'decision',
  'tells_us',
  'does_not_tell_us',
  'methodology',
  'conclusion'
];

(async function initPhase3() {
  const status = document.getElementById('load-status');
  try {
    const report = await loadReport('phase3-report.json', PHASE3_SECTIONS);
    applyMeta(report.meta);

    // Reveal before rendering: Plotly measures its container at plot time.
    status.remove();
    document.querySelectorAll('main > section[hidden]').forEach((section) => {
      section.removeAttribute('hidden');
    });

    renderExecutiveSummary(report.executive_summary);
    renderStatus(report.status);
    renderRepresentations(report.representations);
    renderCptGrowth(report.cpt_growth);
    renderBenchmark(report.benchmark);
    renderRuntime(report.runtime);
    renderCost(report.cost);
    renderDecision(report.decision);
    renderTellsUs(report.tells_us);
    renderLimits(document.getElementById('limits-list'), report.does_not_tell_us);
    renderConclusion(report.conclusion);
    renderDefinitions(document.getElementById('methodology'), report.methodology);
    renderGlossary(document.getElementById('glossary'));

    resizeAllCharts();
    window.addEventListener('load', resizeAllCharts, { once: true });
  } catch (error) {
    if (status.parentNode) status.remove();
    renderLoadError(document.getElementById('report'), error);
    console.error(error);
  }
})();

/* ---------- Executive summary ------------------------------------- */
function renderExecutiveSummary(summary) {
  document.getElementById('exec-headline').textContent = summary.headline;
  const points = document.getElementById('exec-points');
  summary.key_points.forEach((point) => {
    const item = document.createElement('li');
    item.textContent = point;
    points.appendChild(item);
  });
  document.getElementById('exec-bottom-line').textContent = summary.bottom_line;
}

/* ---------- 1. Status and decision gates -------------------------- */
function renderStatus(status) {
  document.getElementById('status-headline').textContent = status.decision_status;

  const cards = document.getElementById('status-cards');
  [
    {
      label: 'Analysis stages complete',
      value: status.gates_passed,
      explanation: `Of ${status.gates_total} checks that evidence exists for each stage.`
    },
    {
      label: 'Decisions still open',
      value: status.gates_open,
      explanation:
        'Points where the analysis cannot proceed without a decision being taken ' +
        'outside it.'
    }
  ].forEach((card) => cards.appendChild(buildStatCard(card)));

  const list = document.getElementById('gate-list');
  status.gates.forEach((gate) => {
    const item = document.createElement('div');
    item.className = `insight-card${gate.passed ? '' : ' insight-card--caution'}`;
    item.innerHTML = `
      <h4>${escapeHtml(gate.gate)}</h4>
      <p><strong>${gate.passed ? 'Evidence produced' : 'Open'}.</strong>
         ${escapeHtml(gate.detail)}</p>`;
    list.appendChild(item);
  });

  document.getElementById('status-note').innerHTML =
    `<p><strong>What "complete" means here.</strong> ${escapeHtml(status.note)}</p>`;
}

/* ---------- 2. The three representations -------------------------- */
function renderRepresentations(reps) {
  const { figure, chart } = buildFigure({
    title: 'How many variables each option would contain',
    evidenceClass: 'derived',
    looking:
      'The three ways of turning the Pathways content into a model, and how many ' +
      'variables each implies. A variable is one thing the model reasons about, ' +
      'normally a question and its answers.',
    tells:
      `Writing out every question occurrence in every pathway needs about ` +
      `${fmt.int(reps.rows[0].variable_count)} variables. Treating each distinct ` +
      `question once needs far fewer. Splitting into candidate families sits between ` +
      'the two, because a question used by several families is held in each of them.',
    matters:
      'This is the clearest size difference between the options, and it is decided by ' +
      'one choice: what counts as the same question appearing twice.',
    sources: reps.source,
    technical: `${reps.definition} ${reps.caveat}`
  });
  document.getElementById('representation-figure').appendChild(figure);
  horizontalBarChart(
    chart,
    reps.rows.map((row) => ({
      label: row.label,
      value: row.variable_count,
      note: `<br>${row.variable_identity.replace(/_/g, ' ')}`
    })),
    { xTitle: 'Candidate variables', unit: 'variables' }
  );

  document.getElementById('representation-caveat').innerHTML =
    `<span class="callout__label">These are not proposed designs</span>
     <p>${escapeHtml(reps.caveat)}</p>`;

  document
    .getElementById('representation-table')
    .appendChild(
      buildTableDisclosure(
        'The three options, with how each counts a variable',
        [
          { label: 'Option', value: (row) => row.label },
          { label: 'Counts a variable as', value: (row) => row.variable_identity.replace(/_/g, ' ') },
          { label: 'Variables', numeric: true, value: (row) => fmt.int(row.variable_count) },
          {
            label: 'Difference vs deduplicated',
            numeric: true,
            value: (row) => fmt.int(row.difference_vs_deduplicated)
          },
          { label: 'Evidence', value: (row) => row.evidence_class },
          { label: 'Reading', value: (row) => row.interpretation }
        ],
        reps.rows
      )
    );
}

/* ---------- 3. Probability table growth --------------------------- */
function renderCptGrowth(growth) {
  const { figure, chart, controls } = buildFigure({
    title: 'How the probability tables grow with each added dependency',
    evidenceClass: 'derived',
    looking:
      'The total size of the probability tables for each option, as each variable is ' +
      'assumed to depend on one, two or three others. Use the buttons to switch ' +
      'between a typical and a more demanding assumption about answer counts.',
    tells:
      'Every added dependency multiplies the tables rather than adding to them. The ' +
      'lines separate far more as dependencies increase than they do between the ' +
      'options themselves.',
    matters:
      'Model size is governed by how the variables are connected, not by how many ' +
      'there are. That connection structure is a clinical design decision that has ' +
      'not been made, so these are a sensitivity range rather than an estimate.',
    sources: growth.source,
    technical: `${growth.definition} ${growth.caveat}`,
    withControls: true
  });
  document.getElementById('cpt-figure').appendChild(figure);

  function draw(stateCase) {
    const series = [];
    const representations = [...new Set(growth.rows.map((row) => row.representation))];
    representations.forEach((representation) => {
      const points = growth.rows
        .filter(
          (row) => row.representation === representation && row.parent_state_case === stateCase
        )
        .sort((a, b) => a.parent_count - b.parent_count);
      if (points.length) {
        series.push({
          name: points[0].label,
          x: points.map((point) => point.parent_count),
          y: points.map((point) => point.cpt_entries)
        });
      }
    });
    growthLineChart(chart, series, {
      xTitle: 'Variables each one depends on',
      yTitle: 'Total numbers in the probability tables (log scale)'
    });
    controls.querySelectorAll('button.chip').forEach((button) => {
      button.setAttribute('aria-pressed', String(button.dataset.case === stateCase));
    });
  }

  growth.parent_state_cases.forEach((stateCase) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'chip';
    button.dataset.case = stateCase;
    button.textContent = growth.case_labels[stateCase] || stateCase.replace(/_/g, ' ');
    button.addEventListener('click', () => draw(stateCase));
    controls.appendChild(button);
  });
  draw(growth.default_case);

  document.getElementById('cpt-caveat').innerHTML =
    `<span class="callout__label">Read this as a range, not an estimate</span>
     <p>${escapeHtml(growth.caveat)}</p>`;

  document
    .getElementById('cpt-table')
    .appendChild(
      buildTableDisclosure(
        'Every sizing case, with storage implied',
        [
          { label: 'Option', value: (row) => row.label },
          { label: 'Dependencies each', numeric: true, value: (row) => fmt.int(row.parent_count) },
          { label: 'Answer-count case', value: (row) => row.parent_state_case.replace(/_/g, ' ') },
          { label: 'Variables', numeric: true, value: (row) => fmt.int(row.variables) },
          { label: 'Table entries', numeric: true, value: (row) => fmt.int(row.cpt_entries) },
          {
            label: 'Numbers to estimate',
            numeric: true,
            value: (row) => fmt.int(row.free_parameters)
          },
          {
            label: 'Raw storage (MiB)',
            numeric: true,
            value: (row) => fmt.decimal(row.raw_mib_float32, 2)
          }
        ],
        growth.rows
      )
    );
}

/* ---------- 4. Benchmark ------------------------------------------ */
function renderBenchmark(benchmark) {
  document.getElementById('benchmark-warning').innerHTML =
    `<span class="callout__label">What these timings are, and are not</span>
     <p>${escapeHtml(benchmark.coverage_warning)}</p>`;

  const { figure, chart } = buildFigure({
    title: 'Measured response time, and how much of the real model was tested',
    evidenceClass: 'measured',
    looking:
      'For each option: the range of measured response times (the bar), and beneath ' +
      'it the share of the real model that the tested model actually contained.',
    tells:
      'Responses are in the low milliseconds across every case tested. But the tested ' +
      `models covered between ${fmt.pct(
        benchmark.coverage_min_percentage,
        1
      )} and ${fmt.pct(benchmark.coverage_max_percentage, 0)} of the real variable counts.`,
    matters:
      'Speed is not currently a discriminator between the options. The low coverage is ' +
      'the reason these figures cannot be quoted as production latency, and saying so ' +
      'is more useful than a confident number that would not survive contact with a ' +
      'real model.',
    sources: benchmark.source,
    technical: benchmark.caveat
  });
  document.getElementById('benchmark-figure').appendChild(figure);
  rangeBarChart(
    chart,
    benchmark.rows.map((row) => ({
      label: `${row.label} (${row.model_scope})`,
      low: row.p95_min_ms,
      high: row.p95_max_ms,
      note:
        `<br>tested at ${fmt.int(row.benchmark_nodes)} variables` +
        `<br>${fmt.pct(row.coverage_percentage, 1)} of the real model`
    })),
    { xTitle: 'Measured 95th-percentile response time (milliseconds)' }
  );

  document
    .getElementById('benchmark-table')
    .appendChild(
      buildTableDisclosure(
        'Benchmark coverage in full',
        [
          { label: 'Option', value: (row) => row.label },
          { label: 'Model tested', value: (row) => row.model_scope },
          { label: 'Variables tested', numeric: true, value: (row) => fmt.int(row.benchmark_nodes) },
          {
            label: 'Share of real model',
            numeric: true,
            value: (row) => fmt.pct(row.coverage_percentage, 2)
          },
          { label: 'Fastest p95 (ms)', numeric: true, value: (row) => fmt.decimal(row.p95_min_ms, 2) },
          { label: 'Slowest p95 (ms)', numeric: true, value: (row) => fmt.decimal(row.p95_max_ms, 2) }
        ],
        benchmark.rows
      )
    );
}

/* ---------- 5. Runtime patterns ----------------------------------- */
function renderRuntime(runtime) {
  document.getElementById('runtime-key-point').innerHTML =
    `<p><strong>Dividing the model and deploying it are separate decisions.</strong>
      ${escapeHtml(runtime.key_point)}</p>`;

  const panels = document.getElementById('runtime-patterns');
  runtime.patterns.forEach((pattern, index) => {
    const panel = document.createElement('div');
    panel.className = 'panel';
    panel.innerHTML = `
      <p class="panel__eyebrow">Pattern ${String.fromCharCode(65 + index)}</p>
      <h4>${escapeHtml(pattern.label)}</h4>
      <ul>
        <li><strong>Held in memory:</strong> ${escapeHtml(pattern.model_residency)}</li>
        <li><strong>Routing:</strong> ${escapeHtml(pattern.routing)}</li>
        <li><strong>Coordination:</strong> ${escapeHtml(pattern.coordination)}</li>
      </ul>`;
    panels.appendChild(panel);
  });

  document
    .getElementById('runtime-tables')
    .appendChild(
      buildTableDisclosure(
        'What has to be re-tested and re-released when one part changes',
        [
          { label: 'Pattern', value: (row) => row.label },
          { label: 'Smallest unit of change', value: (row) => row.change_unit },
          { label: 'Release affects', value: (row) => row.release_blast_radius },
          { label: 'Re-testing scope', value: (row) => row.regression_scope }
        ],
        runtime.blast_radius
      )
    );

  document
    .getElementById('runtime-tables')
    .appendChild(
      buildTableDisclosure(
        'How each pattern fails, and what would have to control it',
        [
          { label: 'Pattern', value: (row) => row.label },
          { label: 'Failure mode', value: (row) => row.failure_mode },
          { label: 'Likely scope', value: (row) => row.scope },
          { label: 'Control required', value: (row) => row.control }
        ],
        runtime.failure_modes
      )
    );

  document
    .getElementById('runtime-tables')
    .appendChild(
      buildTableDisclosure(
        'Structural evidence carried forward from Phase 2',
        [
          { label: 'Evidence', value: (row) => row.evidence },
          { label: 'Value', numeric: true, value: (row) => fmt.decimal(row.value, 2) },
          { label: 'Unit', value: (row) => row.unit },
          { label: 'What it means at runtime', value: (row) => row.meaning }
        ],
        runtime.coordination_evidence
      )
    );
}

/* ---------- 6. Cost ----------------------------------------------- */
function renderCost(cost) {
  document.getElementById('cost-caveat').innerHTML =
    `<span class="callout__label">Illustrative, not a quotation</span>
     <p>${escapeHtml(cost.caveat)}</p>
     <p style="margin-top:0.75rem">${escapeHtml(cost.floor_note)}</p>`;

  /* What the cost evidence says depends on which volume is shown, so the notes are
     built from the computed spread rather than asserting one regime. */
  const widest = cost.spread_by_volume.reduce((a, b) => (b.ratio > a.ratio ? b : a));
  const flat = cost.spread_by_volume.filter((item) => !item.patterns_differ);
  const tells = widest.patterns_differ
    ? `The patterns only separate once volume is high enough. At ${fmt.int(
        widest.assessments_per_month
      )} assessments a month the most expensive pattern costs about ${fmt.decimal(
        widest.ratio,
        1
      )} times the cheapest ($${fmt.int(widest.min_monthly_usd)} against $${fmt.int(
        widest.max_monthly_usd
      )} a month). At lower volumes they cost the same.`
    : 'The patterns cost the same at every volume modelled.';

  const { figure, chart, controls } = buildFigure({
    title: 'Illustrative monthly running cost by deployment pattern',
    evidenceClass: 'candidate',
    looking:
      'Modelled monthly compute cost for each deployment pattern, at a chosen monthly ' +
      'assessment volume. Use the buttons to change the volume.',
    tells,
    matters:
      'Even at the widest spread these are small absolute sums, so cost is unlikely to ' +
      'decide the architecture on its own. The more useful reading is that the ' +
      'difference scales with volume: whatever premium a pattern carries, it is paid ' +
      'per unit of load, not once.',
    sources: cost.source,
    technical:
      `${cost.caveat} ${cost.floor_note} Pricing status: ` +
      `${cost.pricing_status.replace(/_/g, ' ')}.`,
    withControls: true
  });
  document.getElementById('cost-figure').appendChild(figure);

  function draw(volume) {
    const rows = cost.rows.filter((row) => row.assessments_per_month === volume);
    horizontalBarChart(
      chart,
      rows.map((row) => ({
        label: row.label,
        value: row.monthly_usd,
        note:
          `<br>${fmt.int(row.tasks)} compute tasks` +
          `<br>$${fmt.decimal(row.cost_per_1000_usd, 2)} per 1,000 assessments`
      })),
      { xTitle: 'Illustrative monthly cost (USD)', unit: 'USD per month' }
    );
    controls.querySelectorAll('button.chip').forEach((button) => {
      button.setAttribute('aria-pressed', String(Number(button.dataset.volume) === volume));
    });
  }

  cost.volumes.forEach((volume) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'chip';
    button.dataset.volume = String(volume);
    button.textContent = `${fmt.int(volume)} assessments/month`;
    button.addEventListener('click', () => draw(volume));
    controls.appendChild(button);
  });
  draw(cost.default_volume);

  document
    .getElementById('cost-table')
    .appendChild(
      buildTableDisclosure(
        'Every cost scenario',
        [
          { label: 'Pattern', value: (row) => row.label },
          {
            label: 'Assessments / month',
            numeric: true,
            value: (row) => fmt.int(row.assessments_per_month)
          },
          { label: 'Compute tasks', numeric: true, value: (row) => fmt.int(row.tasks) },
          {
            label: 'Monthly (USD)',
            numeric: true,
            value: (row) => fmt.decimal(row.monthly_usd, 2)
          },
          {
            label: 'Per 1,000 assessments (USD)',
            numeric: true,
            value: (row) => fmt.decimal(row.cost_per_1000_usd, 4)
          }
        ],
        cost.rows
      )
    );
}

/* ---------- 7. Decision evidence ---------------------------------- */
function renderDecision(decision) {
  const grid = document.getElementById('tradeoff-panels');
  decision.tradeoffs.forEach((tradeoff) => {
    const panel = document.createElement('div');
    panel.className = 'panel';
    panel.innerHTML = `
      <p class="panel__eyebrow">${escapeHtml(tradeoff.label)}</p>
      <h4>Strength</h4>
      <p>${escapeHtml(tradeoff.strength)}</p>
      <h4 style="margin-top:1rem">Cost of that strength</h4>
      <p>${escapeHtml(tradeoff.tradeoff)}</p>`;
    grid.appendChild(panel);
  });

  document.getElementById('no-recommendation').innerHTML =
    `<span class="callout__label">No architecture is recommended</span>
     <p>${escapeHtml(decision.no_recommendation)}</p>
     <p style="margin-top:0.75rem">${escapeHtml(decision.outstanding)}</p>`;

  document
    .getElementById('decision-table')
    .appendChild(
      buildTableDisclosure(
        'All the evidence assembled, per option',
        [
          { label: 'Option', value: (row) => row.label },
          { label: 'Variables', numeric: true, value: (row) => fmt.int(row.variable_count) },
          {
            label: 'Reference table entries',
            numeric: true,
            value: (row) => fmt.int(row.reference_cpt_entries)
          },
          { label: 'Benchmark coverage', value: (row) => row.benchmark_coverage },
          { label: 'Measured p95 range', value: (row) => row.benchmark_range },
          {
            label: 'Illustrative monthly (USD)',
            numeric: true,
            value: (row) => fmt.decimal(row.illustrative_monthly_usd, 2)
          },
          { label: 'Evidence status', value: (row) => row.evidence_status.replace(/_/g, ' ') }
        ],
        decision.rows
      )
    );
}

/* ---------- 8/9. Findings and conclusion -------------------------- */
function renderTellsUs(cards) {
  const grid = document.getElementById('tells-cards');
  cards.forEach((card) => grid.appendChild(buildInsightCard(card)));
}

function renderConclusion(conclusion) {
  const container = document.getElementById('conclusion-body');
  conclusion.paragraphs.forEach((text) => {
    const paragraph = document.createElement('p');
    paragraph.textContent = text;
    container.appendChild(paragraph);
  });
  document.getElementById('conclusion-question').textContent = conclusion.next_question;
  document.getElementById('conclusion-status').textContent = conclusion.status_note;
}
