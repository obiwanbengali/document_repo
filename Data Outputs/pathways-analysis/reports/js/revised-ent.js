const REVISED_ENT_SECTIONS = [
  'definition','membership','journey_metrics','potential_endpoints',
  'endpoint_summary','internal_transfers','metric_notes',
  'boundary_summary','boundary_profile','ingress_pairs','egress_pairs',
  'ingress_routes','egress_routes','internal_route_details','disposition_routes'
];

(async function initRevisedEnt() {
  const status = document.getElementById('load-status');
  try {
    const report = await loadReport('revised-ent-report.json', REVISED_ENT_SECTIONS);
    applyMeta(report.meta);
    status.remove();
    document.querySelectorAll('main > section[hidden]').forEach(s => s.removeAttribute('hidden'));
    renderFamily(report);
    renderJourneyMetrics(report.journey_metrics);
    renderBoundarySummary(report);
    renderPairTable('ingress-pair-body', report.ingress_pairs);
    renderPairTable('egress-pair-body', report.egress_pairs);
    renderRouteTable('ingress-route-body', report.ingress_routes, 'ingress');
    renderRouteTable('egress-route-body', report.egress_routes, 'egress');
    renderEndpoints(report);
    renderInternal(report.internal_transfers);
    renderNotes(report.metric_notes);
  } catch (error) {
    if (status && status.parentNode) status.remove();
    renderLoadError(document.getElementById('report'), error);
    console.error(error);
  }
})();

function valueOrNA(value, suffix) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return 'Not available';
  return fmt.decimal(Number(value), 2) + (suffix || '');
}

function metricCard(label, value, detail, unavailable) {
  const card = document.createElement('div');
  card.className = 'metric-card-revised';
  card.innerHTML =
    '<span>' + escapeHtml(label) + '</span>' +
    '<strong class="' + (unavailable ? 'metric-unavailable' : '') + '">' + escapeHtml(value) + '</strong>' +
    '<small>' + escapeHtml(detail || '') + '</small>';
  return card;
}

function renderFamily(report) {
  const d = report.definition;
  document.getElementById('family-summary').innerHTML =
    '<span class="callout__label">Authoritative membership for this investigation</span>' +
    '<h3>' + fmt.int(d.pathway_count) + ' Revised ENT pathways</h3>' +
    '<p>' + d.pathway_ids.map(x => '<code>' + escapeHtml(x) + '</code>').join(' · ') + '</p>' +
    (d.missing_pathway_ids.length
      ? '<p><strong>Warning:</strong> not found in this Pathways snapshot: ' +
        d.missing_pathway_ids.map(escapeHtml).join(', ') + '</p>' : '');

  const body = document.getElementById('membership-body');
  report.membership.forEach(row => {
    const tr = document.createElement('tr');
    tr.innerHTML =
      '<td><code>' + escapeHtml(row.pathway_id) + '</code></td>' +
      '<td>' + escapeHtml(row.title || '—') + '</td>' +
      '<td>' + escapeHtml(row.status) + '</td>';
    body.appendChild(tr);
  });
}

function renderJourneyMetrics(m) {
  const warning = document.getElementById('journey-warning');
  if (m.status !== 'available') {
    warning.className = 'callout callout--prominent';
    warning.innerHTML = '<span class="callout__label">Observed journey data required</span><p>' +
      escapeHtml(m.reason) + '</p>';
  } else {
    warning.className = 'callout';
    warning.innerHTML = '<p><strong>Observed source:</strong> ' + escapeHtml(m.source || '') +
      ' · <strong>Total journeys:</strong> ' + fmt.int(m.total_111_online_journeys) +
      ' · <strong>Journeys starting in Revised ENT:</strong> ' + fmt.int(m.ent_start_journeys) + '</p>';
  }

  const host = document.getElementById('journey-metrics');
  const unavailable = m.status !== 'available';
  const cards = [
    ['Coverage / volume of 111 Online journeys',
      unavailable ? 'Not available' : fmt.int(m.ent_start_journeys) + ' journeys · ' + valueOrNA(m.coverage_percentage, '%'),
      m.definitions.coverage_percentage],
    ['E2E completion within group',
      valueOrNA(m.e2e_completion_within_group_percentage, '%'),
      m.definitions.e2e_completion_within_group_percentage],
    ['Start and finish in the same pathway',
      valueOrNA(m.same_start_finish_pathway_percentage, '%'),
      m.definitions.same_start_finish_pathway_percentage],
    ['Start and finish within ENT without leaving to an unsupported pathway',
      valueOrNA(m.start_finish_ent_no_unsupported_percentage, '%'),
      m.definitions.start_finish_ent_no_unsupported_percentage],
    ['Start and finish within ENT after leaving to an unsupported pathway',
      valueOrNA(m.start_finish_ent_with_unsupported_percentage, '%'),
      m.definitions.start_finish_ent_with_unsupported_percentage],
    ['Finish with handover to an out-of-scope pathway',
      valueOrNA(m.finish_handover_out_of_scope_percentage, '%'),
      m.definitions.finish_handover_out_of_scope_percentage],
  ];
  cards.forEach(x => host.appendChild(metricCard(x[0], x[1], x[2], unavailable)));
}


function listValues(values) {
  if (!values || !values.length) return '—';
  return values.map(x => '<code>' + escapeHtml(String(x)) + '</code>').join(', ');
}

function renderBoundarySummary(report) {
  const s = report.boundary_summary;
  const host = document.getElementById('boundary-summary');
  [
    ['External pathways entering ENT', s.external_ingress_pathways, 'Distinct pathways outside Revised ENT with at least one direct transfer into the family.'],
    ['ENT pathways receiving ingress', s.ent_ingress_targets, 'Family members with at least one external ingress route.'],
    ['External pathways reached from ENT', s.external_egress_pathways, 'Distinct out-of-scope pathways directly reachable from Revised ENT.'],
    ['ENT pathways with egress', s.ent_egress_sources, 'Family members with at least one direct route out of scope.'],
    ['Two-way boundary pathways', s.two_way_boundary_pathways, 'ENT pathways that both receive external ingress and hand over externally.'],
    ['No external pathway transfer', s.ent_pathways_with_no_external_transfer, 'ENT pathways whose pathway transfers remain within the family; dispositions may still exist.'],
  ].forEach(x => host.appendChild(metricCard(x[0], fmt.int(x[1]), x[2], false)));

  const body = document.getElementById('boundary-body');
  report.boundary_profile.forEach(row => {
    const tr = document.createElement('tr');
    tr.innerHTML =
      '<td><code>' + escapeHtml(row.pathway_id) + '</code><br>' + escapeHtml(row.title || '') + '</td>' +
      '<td><strong>' + escapeHtml(row.boundary_role) + '</strong></td>' +
      '<td>' + fmt.int(row.external_ingress_source_count) + ' external pathways · ' +
        fmt.int(row.ingress_transfer_points) + ' transfer points<br>' +
        listValues(row.external_ingress_sources) + '</td>' +
      '<td>' + fmt.int(row.external_egress_target_count) + ' external pathways · ' +
        fmt.int(row.egress_transfer_points) + ' transfer points<br>' +
        listValues(row.external_egress_targets) + '</td>' +
      '<td>' + fmt.int(row.internal_in_transfer_points) + ' in · ' +
        fmt.int(row.internal_out_transfer_points) + ' out</td>' +
      '<td>' + fmt.int(row.disposition_points) + '</td>';
    body.appendChild(tr);
  });
}

function renderPairTable(id, rows) {
  const body = document.getElementById(id);
  rows.forEach(row => {
    const tr = document.createElement('tr');
    tr.innerHTML =
      '<td><code>' + escapeHtml(row.source_pathway_id) + '</code><br>' + escapeHtml(row.source_title || '') + '</td>' +
      '<td><code>' + escapeHtml(row.target_pathway_id) + '</code><br>' + escapeHtml(row.target_title || '') + '</td>' +
      '<td><strong>' + fmt.int(row.transfer_points) + '</strong></td>' +
      '<td>' + listValues(row.source_orders) + '</td>' +
      '<td>' + listValues(row.target_orders) + '</td>' +
      '<td>' + listValues(row.questions) + '</td>';
    body.appendChild(tr);
  });
  if (!rows.length) {
    body.innerHTML = '<tr><td colspan="6" class="muted">No boundary crossings found.</td></tr>';
  }
}

function renderRouteTable(id, rows, direction) {
  const body = document.getElementById(id);
  rows.forEach(row => {
    const tr = document.createElement('tr');
    const source = '<code>' + escapeHtml(row.source_pathway_id) + '</code><br>' +
      escapeHtml(row.source_title || '');
    const target = '<code>' + escapeHtml(row.target_pathway_id) + '</code><br>' +
      escapeHtml(row.target_title || '');
    tr.innerHTML =
      '<td>' + source + '</td>' +
      '<td>' + (row.source_order === null ? '—' : fmt.int(row.source_order)) + '</td>' +
      '<td><code>' + escapeHtml(row.question_id || '—') + '</code></td>' +
      '<td>' + (row.answer_number === null ? '—' : fmt.int(row.answer_number)) + '</td>' +
      '<td>' + escapeHtml(row.transfer_branch || '—') + '</td>' +
      '<td>' + target + '</td>' +
      '<td>' + (row.target_order === null ? '—' : fmt.int(row.target_order)) +
        (row.target_order_resolved ? '' : ' <span class="muted">(unresolved)</span>') + '</td>' +
      '<td><code>' + escapeHtml(row.raw_transfer_value || '—') + '</code></td>';
    body.appendChild(tr);
  });
  if (!rows.length) {
    body.innerHTML = '<tr><td colspan="8" class="muted">No ' + escapeHtml(direction) + ' transfer points found.</td></tr>';
  }
}

function renderEndpoints(report) {
  const s = report.endpoint_summary;
  const summary = document.getElementById('endpoint-summary');
  summary.appendChild(metricCard('All unique endpoints', fmt.int(s.total_unique_endpoints), 'Disposition outcomes plus first handovers to unsupported pathways.', false));
  summary.appendChild(metricCard('Disposition endpoints', fmt.int(s.dispositions), 'Terminal disposition codes reachable directly from Revised ENT pathways.', false));
  summary.appendChild(metricCard('Out-of-scope pathway endpoints', fmt.int(s.out_of_scope_pathways), 'First pathway handovers that leave Revised ENT.', false));

  const body = document.getElementById('endpoint-body');
  report.potential_endpoints.forEach(row => {
    const tr = document.createElement('tr');
    tr.innerHTML =
      '<td>' + escapeHtml(row.endpoint_type) + '</td>' +
      '<td><code>' + escapeHtml(row.endpoint_code) + '</code></td>' +
      '<td>' + escapeHtml(row.endpoint_name || '—') + '</td>' +
      '<td>' + row.source_pathways.map(x => '<span class="pill">' + escapeHtml(x) + '</span>').join('') + '</td>' +
      '<td>' + fmt.int(row.branch_count) + '</td>';
    body.appendChild(tr);
  });
}

function renderInternal(rows) {
  const body = document.getElementById('internal-body');
  rows.forEach(row => {
    const tr = document.createElement('tr');
    tr.innerHTML =
      '<td><code>' + escapeHtml(row.source_pathway_id) + '</code><br>' + escapeHtml(row.source_title || '') + '</td>' +
      '<td><code>' + escapeHtml(row.target_pathway_id) + '</code><br>' + escapeHtml(row.target_title || '') + '</td>' +
      '<td>' + fmt.int(row.branch_count) + '</td>';
    body.appendChild(tr);
  });
  if (!rows.length) body.innerHTML = '<tr><td colspan="3">No internal pathway transfers found.</td></tr>';
}

function renderNotes(notes) {
  const host = document.getElementById('metric-notes');
  notes.forEach(note => {
    const li = document.createElement('li');
    li.textContent = note;
    host.appendChild(li);
  });
}
