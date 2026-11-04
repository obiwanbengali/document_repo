const ENT_SECTIONS = [
  'definition','steps','summary','included_pathways','review_candidates',
  'internal_transitions','outbound_transitions','inbound_transitions',
  'outbound_destinations','inbound_sources','clinical_review_questions'
];

(async function initEnt() {
  const status = document.getElementById('load-status');
  try {
    const report = await loadReport('ent-report.json', ENT_SECTIONS);
    applyMeta(report.meta);
    status.remove();
    document.querySelectorAll('main > section[hidden]').forEach(s => s.removeAttribute('hidden'));
    renderSummary(report);
    renderSteps(report.steps);
    renderIncluded(report.included_pathways);
    renderTransitions('outbound-body', report.outbound_transitions);
    renderTransitions('inbound-body', report.inbound_transitions);
    renderReview(report.review_candidates);
    renderQuestions(report.clinical_review_questions);
  } catch (error) {
    if (status && status.parentNode) status.remove();
    renderLoadError(document.getElementById('report'), error);
    console.error(error);
  }
})();

function renderSummary(report) {
  const s = report.summary;
  const cards = [
    ['Included pathways', s.included_pathways],
    ['Review candidates', s.review_candidates],
    ['Internal transfer pairs', s.internal_transition_pairs],
    ['Outbound transfer pairs', s.outbound_transition_pairs],
    ['Inbound transfer pairs', s.inbound_transition_pairs],
    ['Unique outbound pathways', s.unique_outbound_pathways],
    ['Unique inbound pathways', s.unique_inbound_pathways],
  ];
  const host = document.getElementById('summary-cards');
  cards.forEach(([label, value]) => {
    const card = document.createElement('div');
    card.className = 'ent-stat';
    card.innerHTML = '<strong>' + fmt.int(value) + '</strong><span>' + escapeHtml(label) + '</span>';
    host.appendChild(card);
  });
  const headingHost = document.getElementById('heading-summary');
  Object.entries(s.heading_counts || {})
    .sort((a, b) => a[0].localeCompare(b[0]))
    .forEach(([heading, count]) => {
      const item = document.createElement('div');
      item.className = 'section-summary__item';
      item.innerHTML = '<strong>' + fmt.int(count) + '</strong>' + escapeHtml(heading) + ' pathways';
      headingHost.appendChild(item);
    });

  document.getElementById('definition-note').innerHTML =
    '<span class="callout__label">Provisional rule</span>' +
    '<p><strong>' + escapeHtml(report.definition.long_name) + '</strong>: ' +
    escapeHtml(report.definition.automatic_inclusion_rule) + '</p>' +
    '<p><strong>Why this matters:</strong> ' + escapeHtml(report.definition.principle) + '</p>';
}

function renderSteps(steps) {
  const host = document.getElementById('steps');
  steps.forEach(step => {
    const el = document.createElement('div');
    el.className = 'ent-step';
    el.innerHTML = '<h3>' + step.step + '. ' + escapeHtml(step.title) + '</h3><p>' +
      escapeHtml(step.detail) + '</p>';
    host.appendChild(el);
  });
}

function areaText(row) {
  return (row.clinical_areas || []).map(a => [a.description, a.group].filter(Boolean).join(' / ')).join('; ');
}

function renderIncluded(rows) {
  const body = document.getElementById('included-body');
  const input = document.getElementById('pathway-filter');
  const groupSelect = document.getElementById('pathway-group');

  function groupKey(row, mode) {
    if (mode === 'ent_heading') return row.ent_heading || 'Other ENT';
    if (mode === 'symptom_group') return row.symptom_group || 'No symptom group';
    if (mode === 'clinical_area') {
      const areas = row.clinical_areas || [];
      return areas.length ? (areas[0].description || areas[0].group || 'No clinical area') : 'No clinical area';
    }
    return '';
  }

  function pathwayRow(row) {
    const tr = document.createElement('tr');
    const reasons = (row.reasons || []).map(r => '<li>' + escapeHtml(r) + '</li>').join('');
    const areas = (row.clinical_areas || []).map(a =>
      '<span class="pill">' + escapeHtml([a.description, a.group].filter(Boolean).join(' / ')) + '</span>'
    ).join('');
    tr.innerHTML =
      '<td><code>' + escapeHtml(row.pathway_id) + '</code></td>' +
      '<td>' + escapeHtml(row.title) + '</td>' +
      '<td>' + escapeHtml(row.symptom_group || '—') + '</td>' +
      '<td>' + (areas || '—') + '</td>' +
      '<td><ul class="reason-list">' + reasons + '</ul></td>';
    return tr;
  }

  function draw() {
    const q = (input.value || '').trim().toLowerCase();
    const mode = groupSelect.value;
    body.innerHTML = '';

    const filtered = rows.filter(row => {
      const haystack = [
        row.pathway_id, row.title, row.symptom_group, row.ent_heading, areaText(row),
        ...(row.reasons || [])
      ].join(' ').toLowerCase();
      return !q || haystack.includes(q);
    });

    if (mode === 'none') {
      filtered.forEach(row => body.appendChild(pathwayRow(row)));
      return;
    }

    const groups = new Map();
    filtered.forEach(row => {
      const key = groupKey(row, mode);
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(row);
    });

    [...groups.entries()]
      .sort((a, b) => a[0].localeCompare(b[0]))
      .forEach(([heading, groupRows]) => {
        const group = document.createElement('tr');
        group.className = 'group-row';
        group.innerHTML = '<td colspan="5">' + escapeHtml(heading) +
          ' <span class="muted">(' + fmt.int(groupRows.length) + ' pathways)</span></td>';
        body.appendChild(group);
        groupRows
          .sort((a, b) => (a.title || '').localeCompare(b.title || ''))
          .forEach(row => body.appendChild(pathwayRow(row)));
      });

    if (!filtered.length) {
      body.innerHTML = '<tr><td colspan="5" class="muted">No pathways match the current filter.</td></tr>';
    }
  }

  input.addEventListener('input', draw);
  groupSelect.addEventListener('change', draw);
  draw();
}

function renderTransitions(id, rows) {
  const body = document.getElementById(id);
  rows.forEach(row => {
    const tr = document.createElement('tr');
    tr.innerHTML =
      '<td><code>' + escapeHtml(row.source_pathway_id) + '</code><br>' + escapeHtml(row.source_title || '') + '</td>' +
      '<td><code>' + escapeHtml(row.target_pathway_id) + '</code><br>' + escapeHtml(row.target_title || '') + '</td>' +
      '<td>' + fmt.int(row.transition_count) + '</td>' +
      '<td>' + fmt.int(row.answer_branches) + '</td>' +
      '<td>' + fmt.int(row.source_question_count) + '</td>';
    body.appendChild(tr);
  });
  if (!rows.length) {
    body.innerHTML = '<tr><td colspan="5" class="muted">No transitions in this category.</td></tr>';
  }
}

function renderReview(rows) {
  const body = document.getElementById('review-body');
  rows.forEach(row => {
    const tr = document.createElement('tr');
    tr.innerHTML =
      '<td><code>' + escapeHtml(row.pathway_id) + '</code></td>' +
      '<td>' + escapeHtml(row.title) + '</td>' +
      '<td>' + escapeHtml((row.reasons || []).join(' ')) + '</td>';
    body.appendChild(tr);
  });
  if (!rows.length) {
    body.innerHTML = '<tr><td colspan="3" class="muted">No review-only candidates found by the current rule.</td></tr>';
  }
}

function renderQuestions(rows) {
  const host = document.getElementById('clinical-questions');
  rows.forEach(text => {
    const li = document.createElement('li');
    li.textContent = text;
    host.appendChild(li);
  });
}
