/* =====================================================================
   Phase 1 report: "Understanding NHS Pathways"

   Renders the seven sections from data/phase1-report.json. All explanatory
   copy is here or in the HTML; the payload carries data, lineage and
   evidence class only.
   ===================================================================== */

const PHASE1_SECTIONS = [
  'executive_summary',
  'estate',
  'pathway_size',
  'reuse',
  'connectivity',
  'groupings',
  'tells_us',
  'conclusion',
  'does_not_tell_us',
  'methodology'
];

(async function initPhase1() {
  const status = document.getElementById('load-status');
  try {
    const report = await loadReport('phase1-report.json', PHASE1_SECTIONS);
    applyMeta(report.meta);

    // Reveal the sections before rendering. Plotly measures its container at
    // plot time, and a hidden container measures as zero width.
    status.remove();
    document.querySelectorAll('main > section[hidden]').forEach((section) => {
      section.removeAttribute('hidden');
    });

    renderExecutiveSummary('phase1-executive-summary', report.executive_summary);
    renderEstate(report.estate);
    renderPathwaySize(report.pathway_size);
    renderReuse(report.reuse);
    renderConnectivity(report.connectivity);
    renderGroupings(report.groupings);
    renderTellsUs(report.tells_us);
    renderConclusion('phase1-conclusion', report.conclusion);
    renderLimits(document.getElementById('limits-list'), report.does_not_tell_us);
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

/* ---------- 1. Estate at a glance --------------------------------- */
function renderEstate(estate) {
  const grid = document.getElementById('estate-cards');
  estate.cards.forEach((card) => grid.appendChild(buildStatCard(card)));

  const lineage = document.createElement('details');
  lineage.className = 'disclosure';
  lineage.style.border = '1px solid var(--rule)';
  lineage.style.borderRadius = 'var(--radius)';
  lineage.innerHTML = `
    <summary>Evidence class and data source</summary>
    <div class="disclosure__body">
      <p>
        <span class="badge badge--measured">Measured</span>
        Every figure above except the pathway-to-pathway link count is a direct count from
        the dataset. The link count is
        <span class="badge badge--derived">Derived</span>: transfer instructions are
        resolved to their target pathway and aggregated to one link per pair and direction.
      </p>
      <p><strong>Source</strong><br>${estate.source
        .map((path) => `<span class="lineage">${escapeHtml(path)}</span>`)
        .join('')}</p>
    </div>`;
  document.getElementById('estate-lineage').appendChild(lineage);
}

/* ---------- 2. Pathway size --------------------------------------- */
function renderPathwaySize(size) {
  const cards = document.getElementById('size-cards');
  [
    {
      label: 'Typical pathway',
      value: size.stats.median,
      explanation:
        'Questions available in the middle pathway. Half of all pathways have fewer, ' +
        'half have more.'
    },
    {
      label: 'Larger pathways',
      value: size.stats.p90,
      explanation:
        'The tenth of pathways that are largest have at least this many questions.'
    },
    {
      label: 'Largest pathway',
      value: size.stats.max,
      explanation: 'The single biggest pathway in the estate, by questions available.'
    },
    {
      label: 'Smallest pathway',
      value: size.stats.min,
      explanation:
        'Some pathways ask no questions at all — they exist to route an assessment ' +
        'onward or to record an outcome.'
    }
  ].forEach((card) => cards.appendChild(buildStatCard(card)));

  const { figure, chart } = buildFigure({
    title: 'How many questions each pathway can ask',
    evidenceClass: 'derived',
    looking:
      'Every active pathway sorted into size bands, by how many distinct questions it ' +
      'can ask. The height of each bar is the number of pathways in that band.',
    tells:
      `Most pathways are modest in size — the typical one can ask ${fmt.int(
        size.stats.median
      )} questions — but the distribution has a long tail reaching ${fmt.int(
        size.stats.max
      )}. There is no single "normal" pathway size.`,
    matters:
      'Any design has to accommodate the largest pathways, not the typical one. The ' +
      'spread also means effort and complexity are concentrated in a minority of the ' +
      'estate.',
    sources: size.source,
    technical:
      size.definition +
      ` Percentiles over ${fmt.int(size.stats.pathways)} active pathways with ` +
      `triage logic: median ${size.stats.median}, 90th percentile ${size.stats.p90}, ` +
      `95th percentile ${size.stats.p95}, maximum ${size.stats.max}. Values are banded ` +
      'for display; no per-pathway figures are included in the report data.'
  });
  document.getElementById('size-figure').appendChild(figure);
  bandedBarChart(chart, size.distribution, {
    xTitle: 'Questions the pathway can ask',
    yTitle: 'Number of pathways',
    unit: 'pathways'
  });
}

/* ---------- 3. Reuse ---------------------------------------------- */
function renderReuse(reuse) {
  const cards = document.getElementById('reuse-cards');
  [
    {
      label: 'Questions in use',
      value: reuse.headline.questions_referenced,
      explanation: 'Distinct questions referenced anywhere in the estate.'
    },
    {
      label: 'Used by one pathway only',
      value: reuse.headline.single_pathway_questions,
      explanation:
        `${fmt.pct(reuse.headline.single_pathway_percentage, 0)} of questions are ` +
        'specific to a single pathway.'
    },
    {
      label: 'Typical answers per question',
      value: reuse.headline.answers_per_question_median,
      explanation:
        `The most any question offers is ${fmt.int(
          reuse.headline.answers_per_question_max
        )}. Few questions are simple yes/no.`
    }
  ].forEach((card) => cards.appendChild(buildStatCard(card)));

  const { figure, chart } = buildFigure({
    title: 'How many pathways use each question',
    evidenceClass: 'derived',
    looking:
      'Every question referenced by the estate, grouped by how many pathways use it. ' +
      'The left-hand bar is questions used by exactly one pathway.',
    tells:
      `About ${fmt.pct(
        reuse.headline.shared_percentage,
        0
      )} of questions are used by more than one pathway. A minority are used very ` +
      'widely indeed, appearing in dozens or hundreds of pathways.',
    matters:
      'Shared questions are the places where the estate is genuinely interconnected. ' +
      'They are also where a change in one place has effects in many others, which is a ' +
      'consideration for any design and for release management.',
    sources: reuse.source,
    technical: reuse.definition
  });
  document.getElementById('reuse-figure').appendChild(figure);
  bandedBarChart(chart, reuse.question_bands, {
    xTitle: 'Number of pathways using the question',
    yTitle: 'Number of questions',
    unit: 'questions'
  });

  const sd = buildFigure({
    title: 'How many pathways use each symptom discriminator',
    evidenceClass: 'derived',
    looking:
      'The same view for symptom discriminators — the clinical factors that separate ' +
      'more urgent presentations from less urgent ones within the same symptom.',
    tells:
      'Discriminators are shared more heavily than questions. A single discriminator can ' +
      'be reachable from several hundred pathways.',
    matters:
      'Discriminators turn out to be the strongest signal for grouping pathways in ' +
      'Phase 2: pathways that share discriminators tend to be clinically related, which ' +
      'is not automatically true of pathways that merely share a question.',
    sources: reuse.source,
    technical:
      'A discriminator counts towards a pathway where that pathway offers an answer ' +
      'carrying it. Reachability is what the data records; how often the route is ' +
      'actually taken is not available.'
  });
  document.getElementById('discriminator-figure').appendChild(sd.figure);
  bandedBarChart(sd.chart, reuse.discriminator_bands, {
    xTitle: 'Number of pathways reaching the discriminator',
    yTitle: 'Number of discriminators',
    unit: 'discriminators'
  });
}

/* ---------- 4. Connectivity --------------------------------------- */
function renderConnectivity(connectivity) {
  const cards = document.getElementById('connectivity-cards');
  connectivity.cards.forEach((card) => cards.appendChild(buildStatCard(card)));

  const { figure, chart } = buildFigure({
    title: 'How many other pathways each pathway hands over to',
    evidenceClass: 'derived',
    looking:
      'Active pathways grouped by how many different pathways they can hand an ' +
      'assessment over to (outgoing), shown alongside how many can hand over to them ' +
      '(incoming).',
    tells:
      'Most pathways connect to a handful of others, but a small number act as major ' +
      'junctions with dozens of connections. Incoming and outgoing patterns differ: some ' +
      'pathways mainly receive handovers rather than making them.',
    matters:
      'These connections are what would have to be preserved or coordinated by any ' +
      'design that divided the estate into parts. The busiest junctions are where a ' +
      'boundary would be most consequential.',
    sources: connectivity.source,
    technical:
      connectivity.definition +
      ' Counts are banded for display; no per-pathway figures beyond the most-connected ' +
      'list are included in the report data.'
  });
  document.getElementById('connectivity-figure').appendChild(figure);
  groupedBarChart(
    chart,
    connectivity.outgoing_distribution.map((band) => band.band),
    [
      {
        name: 'Hands over to (outgoing)',
        values: connectivity.outgoing_distribution.map((band) => band.count)
      },
      {
        name: 'Receives from (incoming)',
        values: connectivity.incoming_distribution.map((band) => band.count)
      }
    ],
    { xTitle: 'Number of pathways' }
  );

  const top = buildFigure({
    title: 'The most connected pathways',
    evidenceClass: 'derived',
    looking:
      'The ten pathways with the most connections in either direction, identified by ' +
      'their pathway reference. Titles are deliberately not shown here.',
    tells:
      'A few pathways are very heavily referenced. The top one receives handovers from ' +
      `over ${fmt.int(connectivity.top_connected[0].incoming)} other pathways while ` +
      'making almost none of its own — the profile of a shared endpoint rather than a ' +
      'staging post.',
    matters:
      'Highly connected pathways are the hardest to place in any single group, and they ' +
      'are where a division of the estate would most need care. Phase 2 examines them ' +
      'directly as boundary pathways.',
    sources: connectivity.source,
    technical:
      'Pathway references only, with connection counts. Pathway titles are clinical ' +
      'content and are held in the detailed evidence files rather than loaded into this ' +
      'page.'
  });
  document.getElementById('top-connected-figure').appendChild(top.figure);
  horizontalBarChart(
    top.chart,
    connectivity.top_connected.map((item) => ({
      label: item.pathway_id,
      value: item.total,
      note: `<br>outgoing: ${item.outgoing}<br>incoming: ${item.incoming}`
    })),
    { xTitle: 'Total connections', unit: 'connections' }
  );

  document.getElementById(
    'hairball-note'
  ).innerHTML = `<p><strong>Why there is no network diagram here.</strong> ${escapeHtml(
    connectivity.presentation_note
  )}</p>`;
}

/* ---------- 5. Existing groupings --------------------------------- */
function renderGroupings(groupings) {
  document.getElementById(
    'groupings-caveat'
  ).innerHTML = `<span class="callout__label">Important</span><p>${escapeHtml(
    groupings.caveat
  )}</p>`;

  /* Clinical areas: count and self-containment on one shared percentage
     scale would mix two quantities, so they are two charts. */
  const areas = buildFigure({
    title: 'Pathways in each clinical area',
    evidenceClass: 'measured',
    looking:
      'How many active pathways are listed under each clinical area, largest first.',
    tells:
      `The ${groupings.clinical_areas.length} clinical areas are very unevenly sized, and ` +
      'the largest is "not area specific" — a catch-all rather than an anatomical group. ' +
      `The area counts add up to ${fmt.int(
        groupings.clinical_area_overlap.total_links
      )} listings across the estate, well above the number of pathways, because pathways ` +
      'appear under several areas.',
    matters:
      'Clinical areas are the most recognisable existing grouping, so they are an obvious ' +
      'starting point. But because they overlap and are unevenly sized, they do not by ' +
      'themselves divide the estate into balanced parts.',
    sources: groupings.source,
    technical: groupings.clinical_area_overlap.note
  });
  document.getElementById('clinical-area-figure').appendChild(areas.figure);
  horizontalBarChart(
    areas.chart,
    groupings.clinical_areas.map((area) => ({
      label: area.name,
      value: area.pathway_count,
      note: `<br>area group: ${area.area_group || 'not set'}`
    })),
    { xTitle: 'Active pathways', unit: 'pathways' }
  );

  const areaShare = groupings.clinical_areas.filter(
    (area) => area.internal_link_percentage !== null && area.pathway_count >= 2
  );
  if (areaShare.length) {
    const share = buildFigure({
      title: 'How self-contained each clinical area is',
      evidenceClass: 'derived',
      looking:
        'For each clinical area: of all the handovers leaving its pathways, the share ' +
        'that stay inside the same area (blue) against the share that cross into ' +
        'another area (orange).',
      tells:
        'Most clinical areas retain only a small fraction of their own handovers. ' +
        'Assessments routinely move between areas rather than staying within one.',
      matters:
        'This is the first sign that the existing clinical classification does not match ' +
        'the way the estate actually connects. It is why Phase 2 looks for groupings in ' +
        'the connection structure as well as in the existing classifications.',
      sources: groupings.source,
      technical:
        'Internal share = handovers that stay inside the area, divided by all handovers ' +
        'leaving the area\'s pathways. Areas with fewer than two pathways are excluded ' +
        'because the measure is not meaningful for them.'
    });
    document.getElementById('clinical-area-figure').appendChild(share.figure);
    shareBarChart(
      share.chart,
      areaShare.map((area) => ({
        label: area.name,
        value: area.internal_link_percentage
      })),
      {
        primaryLabel: 'Stays inside the clinical area',
        secondaryLabel: 'Crosses into another area'
      }
    );
  }

  /* Symptom groups. */
  const groups = buildFigure({
    title: 'How large the NHS symptom groups are',
    evidenceClass: 'measured',
    looking:
      `Symptom groups sorted into size bands. ${fmt.int(
        groupings.symptom_groups.with_active_pathways
      )} of the ${fmt.int(
        groupings.symptom_groups.total_catalogued
      )} catalogued groups contain at least one active pathway.`,
    tells:
      `Symptom groups are mostly very small — the typical one holds ${fmt.int(
        groupings.symptom_groups.median_pathways
      )} pathways. A handful are much larger.`,
    matters:
      'Used directly as a division of the estate, symptom groups would produce hundreds ' +
      'of tiny parts. That is a real finding about the granularity of the existing ' +
      'classification, not a criticism of it: it was designed for clinical navigation, ' +
      'not for partitioning a model.',
    sources: groupings.source,
    technical:
      'Counts active pathways per symptom group. Note that a number of active pathways ' +
      'carry no symptom group at all; see the metadata coverage table below.'
  });
  document.getElementById('symptom-group-figure').appendChild(groups.figure);
  bandedBarChart(groups.chart, groupings.symptom_groups.size_distribution, {
    xTitle: 'Active pathways in the symptom group',
    yTitle: 'Number of symptom groups',
    unit: 'symptom groups'
  });

  document
    .getElementById('symptom-group-figure')
    .appendChild(
      buildTableDisclosure(
        'The largest symptom groups',
        [
          { label: 'Symptom group', value: (row) => row.name },
          { label: 'Active pathways', numeric: true, value: (row) => fmt.int(row.pathway_count) }
        ],
        groupings.symptom_groups.largest
      )
    );

  /* Age and trauma. */
  const container = document.getElementById('age-trauma-figures');

  const age = buildFigure({
    title: 'Pathways tagged for each age band',
    evidenceClass: 'measured',
    looking:
      'How many active pathways carry each age tag. A pathway can carry several, so the ' +
      'bars overlap rather than dividing the estate.',
    tells:
      'Age tags are widely populated and heavily overlapping: most pathways are tagged ' +
      'for more than one age band, and many for all of them.',
    matters:
      'Age is a real clinical distinction, and paediatric assessment differs from adult ' +
      'assessment. But because the tags overlap so heavily, age cannot simply be used to ' +
      'split the estate. Phase 2 examines whether paediatric content forms its own ' +
      'grouping or cuts across all of them.',
    sources: groupings.source,
    technical:
      'Age tags come from the pathway-to-age link table. They were extracted during ' +
      'Phase 2, which is why the source file below sits in the Phase 2 outputs.'
  });
  container.appendChild(age.figure);
  horizontalBarChart(
    age.chart,
    groupings.age_bands.map((band) => ({ label: band.label, value: band.pathway_count })),
    { xTitle: 'Active pathways tagged', unit: 'pathways' }
  );

  const trauma = buildFigure({
    title: 'Pathways tagged trauma and non-trauma',
    evidenceClass: 'measured',
    looking: 'How many active pathways carry each trauma tag.',
    tells:
      'Trauma is tagged on a substantial minority of pathways, and a small number carry ' +
      'both tags at once. Just over half of active pathways carry no trauma tag at all.',
    matters:
      'Trauma is often suggested as a natural top-level division. The tagging pattern ' +
      'shows it is not a clean binary split in this data, which Phase 2 examines in ' +
      'more detail.',
    sources: groupings.source,
    technical:
      'Trauma tags come from the pathway-to-trauma link table, extracted during Phase 2. ' +
      'Pathways carrying both tags are counted under each.'
  });
  container.appendChild(trauma.figure);
  horizontalBarChart(
    trauma.chart,
    groupings.trauma.map((item) => ({ label: item.label, value: item.pathway_count })),
    { xTitle: 'Active pathways tagged', unit: 'pathways' }
  );

  document
    .getElementById('coverage-disclosure')
    .appendChild(
      buildTableDisclosure(
        'How completely each grouping field is populated',
        [
          { label: 'Field', value: (row) => row.field },
          { label: 'Pathways with a value', numeric: true, value: (row) => fmt.int(row.populated) },
          { label: 'Missing', numeric: true, value: (row) => fmt.int(row.missing) },
          { label: 'Coverage', numeric: true, value: (row) => fmt.pct(row.coverage_percentage, 1) },
          { label: 'Distinct values', numeric: true, value: (row) => fmt.int(row.distinct_values) },
          {
            label: 'Could divide the estate',
            value: (row) => (row.can_separate ? 'yes' : 'no — single value or empty')
          }
        ],
        groupings.metadata_coverage
      )
    );
}

/* ---------- 6. What Phase 1 tells us ------------------------------ */
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
