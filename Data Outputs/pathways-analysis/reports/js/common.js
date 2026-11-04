/* =====================================================================
   Shared behaviour for the NHS Pathways briefing reports.

   Responsibilities:
     - load a report payload and fail visibly if it is missing
     - build the page chrome that every figure shares (title, evidence
       badge, the three explanatory notes, lineage, technical detail)
     - hold the glossary and the evidence-class definitions
     - small formatting helpers

   The payloads are data only. All explanatory copy lives in the pages and
   in this file, so that editorial wording can change without re-running
   the Python build, and so the JSON stays reviewable as data.
   ===================================================================== */

/* Validated palette. Mirrors css/report.css; kept here because Plotly needs
   real values rather than CSS custom properties. The first three slots are
   the documented subset that clears the all-pairs colour-vision floors, so
   no chart uses more than three at once. */
const PALETTE = {
  surface: '#fcfcfb',
  surfaceRaised: '#ffffff',
  inkPrimary: '#0b0b0b',
  inkSecondary: '#52514e',
  inkMuted: '#898781',
  rule: '#e1e0d9',
  ruleStrong: '#c3c2b7',
  series: ['#2a78d6', '#eb6834', '#1baf7a'],
  /* Single-hue sequential ramp, light to dark, for magnitude only.
     Never a rainbow: a heatmap encodes one quantity. */
  sequential: [
    [0.0,  '#cde2fb'],
    [0.15, '#9ec5f4'],
    [0.3,  '#6da7ec'],
    [0.45, '#3987e5'],
    [0.6,  '#2a78d6'],
    [0.75, '#1c5cab'],
    [0.9,  '#104281'],
    [1.0,  '#0d366b']
  ]
};

const EVIDENCE_LABELS = {
  measured: 'Measured',
  derived: 'Derived',
  candidate: 'Candidate'
};

/* ---------------------------------------------------------------------
   Glossary. Written for a reader who has never seen the analysis and does
   not work with data. Every definition avoids defining one unfamiliar term
   with another.
   --------------------------------------------------------------------- */
const GLOSSARY = [
  ['Pathway',
   'One clinical assessment flow: the set of questions and decisions used to assess a ' +
   'particular presenting problem, such as chest pain or a head injury. The NHS ' +
   'Pathways estate contains several hundred of them.'],

  ['Question',
   'A single thing asked during an assessment. The same question is often used by many ' +
   'pathways rather than being written out again for each one.'],

  ['Answer',
   'One of the possible responses to a question. Each answer can send the assessment ' +
   'somewhere different: on to the next question, to another pathway, or to an outcome.'],

  ['Disposition',
   'The outcome of an assessment: what should happen to the patient and how quickly. ' +
   'For example an emergency ambulance response, or speaking to a primary care service ' +
   'within a stated number of hours.'],

  ['Symptom Group',
   'An existing NHS classification that groups pathways by the symptom the patient ' +
   'presents with. It already exists in the data; it was not created by this analysis.'],

  ['Symptom Discriminator',
   'A clinical factor used to separate more urgent presentations from less urgent ones ' +
   'within the same symptom. Two patients reporting the same symptom may be assessed ' +
   'very differently depending on which discriminators apply.'],

  ['Clinical Area',
   'A broad anatomical or clinical grouping such as chest, head or abdomen. A pathway ' +
   'can be listed under several clinical areas at once, so clinical areas overlap ' +
   'rather than dividing the estate cleanly.'],

  ['Bayesian Network',
   'A way of representing clinical reasoning as a set of variables and the probabilistic ' +
   'relationships between them. Rather than following a fixed sequence of questions, it ' +
   'can weigh up the available evidence and update its assessment as answers arrive.'],

  ['Federated Bayesian Network',
   'Instead of one large model covering everything, several smaller models each covering ' +
   'a related area of clinical reasoning, with a way of working together where they ' +
   'overlap. Smaller models are easier to change and test; the difficulty is deciding ' +
   'where to draw the lines between them and how they share information.'],

  ['Family',
   'A group of pathways that might sensibly be handled by one model. In this analysis ' +
   'every family is a candidate: something the evidence suggests, not something that ' +
   'has been agreed or clinically approved.'],

  ['Graph community',
   'A cluster of pathways that hand over to each other more than they hand over to ' +
   'anything else, found automatically by looking only at the connections in the data. ' +
   'It is a statistical grouping. It may or may not correspond to something a clinician ' +
   'would recognise, which is exactly why clinical review is needed.'],

  ['Internal link',
   'A handover from one pathway to another where both pathways are in the same family. ' +
   'A family with a high share of internal links is largely self-contained.'],

  ['External link',
   'A handover that crosses from one family into another. External links are the points ' +
   'where separate models would have to coordinate.'],

  ['Boundary pathway',
   'A pathway that sits at the edge of its family because it hands over to, or receives ' +
   'handovers from, pathways in other families. Boundary pathways are where the choice ' +
   'of family boundary matters most.'],

  ['Shared core',
   'Content used across many candidate families, such as a question asked in dozens of ' +
   'different assessments. If families were built separately, this content would either ' +
   'have to be duplicated in each one or held somewhere common.'],

  ['Jaccard similarity',
   'A way of measuring how much two sets have in common, on a scale from 0 to 1. It is ' +
   'the number of items in both sets divided by the number in either. 0 means nothing ' +
   'in common; 1 means identical. It takes no account of size, so two very small sets ' +
   'can score highly from only a handful of shared items.']
];

/* ---------------------------------------------------------------------
   Formatting
   --------------------------------------------------------------------- */
const fmt = {
  int(value) {
    if (value === null || value === undefined || Number.isNaN(value)) return '—';
    return Number(value).toLocaleString('en-GB');
  },
  /** Percentages read from the payload are already 0-100. */
  pct(value, digits = 1) {
    if (value === null || value === undefined || Number.isNaN(value)) return 'not measurable';
    return `${Number(value).toFixed(digits)}%`;
  },
  decimal(value, digits = 2) {
    if (value === null || value === undefined || Number.isNaN(value)) return 'not measurable';
    return Number(value).toFixed(digits);
  },
  /** Sentence-cases a snake_case or lower-case string for display. */
  sentence(text) {
    if (!text) return '';
    return text.charAt(0).toUpperCase() + text.slice(1);
  }
};

/* ---------------------------------------------------------------------
   Data loading
   --------------------------------------------------------------------- */

/**
 * Load a report payload.
 *
 * Fails visibly rather than silently: a blank page would leave a reader
 * unable to tell a missing build from a section with no findings.
 */
async function loadReport(filename, expectedKeys) {
  const standalone = window.__PATHWAYS_STANDALONE_DATA__ || {};
  if (Object.prototype.hasOwnProperty.call(standalone, filename)) {
    const payload = standalone[filename];
    const missing = (expectedKeys || []).filter((key) => !(key in payload));
    if (missing.length) {
      throw new Error(
        `Embedded ${filename} is missing the section(s): ${missing.join(', ')}.`
      );
    }
    return payload;
  }

  let response;
  try {
    response = await fetch(`data/${filename}`, { cache: 'no-store' });
  } catch (error) {
    throw new Error(
      `Could not fetch data/${filename}. If you opened this file directly from disk, ` +
      `browsers block local data loading — serve the folder instead.`
    );
  }
  if (!response.ok) {
    throw new Error(
      `data/${filename} was not found (HTTP ${response.status}). Generate it first.`
    );
  }
  const payload = await response.json();
  const missing = (expectedKeys || []).filter((key) => !(key in payload));
  if (missing.length) {
    throw new Error(
      `data/${filename} is missing the section(s): ${missing.join(', ')}. ` +
      `It may have been built by an older version of the report builder.`
    );
  }
  return payload;
}

/** Render a build/load failure where the report would have been. */
function renderLoadError(container, error) {
  container.innerHTML = '';
  const box = document.createElement('div');
  box.className = 'load-error';
  box.innerHTML = `
    <h3>The report data is not available</h3>
    <p>${escapeHtml(error.message)}</p>
    <p>Generate the report data and serve this folder over HTTP:</p>
    <p>
      <code>cd pathways-analysis</code><br>
      <code>python -m pathways_analysis.report_builder</code><br>
      <code>cd reports &amp;&amp; python -m http.server 8000</code>
    </p>
    <p>Then open <code>http://localhost:8000/</code>.</p>
  `;
  container.appendChild(box);
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text === null || text === undefined ? '' : String(text);
  return div.innerHTML;
}

/* ---------------------------------------------------------------------
   Shared page chrome
   --------------------------------------------------------------------- */

/** Stamp the confidentiality banner text from the payload's own meta block. */
function applyMeta(meta) {
  const banner = document.querySelector('[data-confidentiality]');
  if (banner && meta.confidentiality) {
    banner.innerHTML = `<strong>Confidential.</strong> ${escapeHtml(meta.confidentiality)}`;
  }
  document.querySelectorAll('[data-meta-generated]').forEach((node) => {
    node.textContent = meta.generated_utc || '';
  });
  document.querySelectorAll('[data-meta-scope]').forEach((node) => {
    node.textContent = meta.scope_note || '';
  });
}

/**
 * Build a figure: title, evidence badge, chart mount, the three explanatory
 * notes every visual must carry, and expandable lineage plus technical detail.
 *
 * The three notes are not optional. A chart without them asks the reader to
 * work out for themselves what they are looking at, which is how a briefing
 * turns into a dashboard nobody trusts.
 *
 * @returns {{figure: HTMLElement, chart: HTMLElement, controls: HTMLElement}}
 */
function buildFigure(options) {
  const {
    title,
    evidenceClass = 'derived',
    looking,
    tells,
    matters,
    sources = [],
    technical = '',
    withControls = false
  } = options;

  const figure = document.createElement('figure');
  figure.className = 'figure';

  const head = document.createElement('div');
  head.className = 'figure__head';
  head.innerHTML = `
    <h3 class="figure__title">${escapeHtml(title)}</h3>
    <span class="badge badge--${evidenceClass}"
          title="${escapeHtml(EVIDENCE_CLASS_HINTS[evidenceClass] || '')}">
      ${escapeHtml(EVIDENCE_LABELS[evidenceClass] || evidenceClass)}
    </span>`;
  figure.appendChild(head);

  let controls = null;
  if (withControls) {
    controls = document.createElement('div');
    controls.className = 'figure__controls';
    figure.appendChild(controls);
  }

  const chart = document.createElement('div');
  chart.className = 'figure__chart';
  figure.appendChild(chart);

  const notes = document.createElement('dl');
  notes.className = 'figure__notes';
  notes.innerHTML = `
    <div class="figure__note"><dt>What am I looking at?</dt><dd>${escapeHtml(looking)}</dd></div>
    <div class="figure__note"><dt>What does this tell us?</dt><dd>${escapeHtml(tells)}</dd></div>
    <div class="figure__note"><dt>Why does it matter?</dt><dd>${escapeHtml(matters)}</dd></div>`;
  figure.appendChild(notes);

  if (sources.length || technical) {
    const disclosure = document.createElement('details');
    disclosure.className = 'disclosure';
    const sourceMarkup = sources.length
      ? `<p><strong>Source</strong><br>${sources
          .map((path) => `<span class="lineage">${escapeHtml(path)}</span>`)
          .join('')}</p>`
      : '';
    disclosure.innerHTML = `
      <summary>Technical detail and data source</summary>
      <div class="disclosure__body">
        ${technical ? `<p>${escapeHtml(technical)}</p>` : ''}
        ${sourceMarkup}
      </div>`;
    figure.appendChild(disclosure);
  }

  return { figure, chart, controls };
}

const EVIDENCE_CLASS_HINTS = {
  measured: 'Counted directly in the NHS Pathways dataset.',
  derived: 'Calculated from measured values using the stated definition.',
  candidate: 'A possibility suggested by the evidence. Requires clinical review.'
};

/** A headline number card. */
function buildStatCard(card) {
  const element = document.createElement('div');
  element.className = 'stat-card';
  element.innerHTML = `
    <div class="stat-card__value">${fmt.int(card.value)}</div>
    <div class="stat-card__label">${escapeHtml(card.label)}</div>
    ${card.explanation ? `<div class="stat-card__note">${escapeHtml(card.explanation)}</div>` : ''}`;
  return element;
}

/** A plain-language finding card. */
function buildInsightCard(item, variant) {
  const element = document.createElement('div');
  element.className = `insight-card${variant ? ` insight-card--${variant}` : ''}`;
  element.innerHTML = `
    <h4>${escapeHtml(item.title)}</h4>
    <p>${escapeHtml(item.text)}</p>`;
  return element;
}

/**
 * A keyboard-reachable tooltip trigger.
 *
 * Uses a real button with a title rather than a hover-only span, so the
 * explanation is available to keyboard and screen-reader users too.
 */
function buildTooltip(text) {
  if (!text) return document.createDocumentFragment();
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'tip';
  button.title = text;
  button.setAttribute('aria-label', `Explanation: ${text}`);
  button.textContent = 'i';
  button.addEventListener('click', () => window.alert(text));
  return button;
}

/** A labelled metric with an optional tooltip. */
function buildMetric(label, value, tooltip) {
  const element = document.createElement('div');
  element.className = 'metric';
  const valueNode = document.createElement('div');
  valueNode.className = 'metric__value';
  valueNode.textContent = value;
  const labelNode = document.createElement('div');
  labelNode.className = 'metric__label';
  labelNode.appendChild(document.createTextNode(label));
  labelNode.appendChild(buildTooltip(tooltip));
  element.appendChild(valueNode);
  element.appendChild(labelNode);
  return element;
}

/** Render a definition list into a container, used by the methodology blocks. */
function renderDefinitions(container, definitions) {
  container.innerHTML = '';
  definitions.forEach((item) => {
    const term = document.createElement('dt');
    term.textContent = item.term;
    const definition = document.createElement('dd');
    definition.textContent = item.definition;
    container.appendChild(term);
    container.appendChild(definition);
  });
}

/** Render the shared glossary. */
function renderGlossary(container) {
  if (!container) return;
  container.innerHTML = '';
  GLOSSARY.forEach(([term, definition]) => {
    const wrapper = document.createElement('div');
    wrapper.className = 'glossary-item';
    const list = document.createElement('dl');
    list.style.margin = '0';
    list.innerHTML = `<dt>${escapeHtml(term)}</dt><dd>${escapeHtml(definition)}</dd>`;
    wrapper.appendChild(list);
    container.appendChild(wrapper);
  });
}

/** Render the evidence-class key shown on each report page. */
function renderEvidenceKey(container, classes) {
  if (!container) return;
  container.innerHTML = '';
  Object.entries(classes || EVIDENCE_CLASS_HINTS).forEach(([name, meaning]) => {
    const wrapper = document.createElement('div');
    wrapper.className = 'glossary-item';
    wrapper.innerHTML = `
      <dl style="margin:0">
        <dt><span class="badge badge--${name}">${escapeHtml(
          EVIDENCE_LABELS[name] || name
        )}</span></dt>
        <dd>${escapeHtml(meaning)}</dd>
      </dl>`;
    container.appendChild(wrapper);
  });
  const wrapper = document.createElement('div');
  wrapper.className = 'glossary-item';
  wrapper.innerHTML = `
    <dl style="margin:0">
      <dt>Architectural interpretation</dt>
      <dd>What the evidence implies for the design. Deliberately absent from these
      reports: that comparison is Phase 3 work and has not been done.</dd>
    </dl>`;
  container.appendChild(wrapper);
}

/** Render a simple list of limitation statements. */
function renderLimits(container, items) {
  if (!container) return;
  container.innerHTML = '';
  items.forEach((text) => {
    const item = document.createElement('li');
    item.textContent = text;
    container.appendChild(item);
  });
}

/**
 * Render a small data table inside a disclosure element.
 *
 * Tables are never the first thing a reader sees: the brief asks for figures
 * on the surface and detail underneath. This builds the "underneath".
 */
function buildTableDisclosure(summaryText, columns, rows) {
  const disclosure = document.createElement('details');
  disclosure.className = 'disclosure';
  const header = columns
    .map((column) => `<th${column.numeric ? ' class="num"' : ''}>${escapeHtml(column.label)}</th>`)
    .join('');
  const body = rows
    .map(
      (row) =>
        '<tr>' +
        columns
          .map((column) => {
            const value = column.value(row);
            return `<td${column.numeric ? ' class="num"' : ''}>${escapeHtml(value)}</td>`;
          })
          .join('') +
        '</tr>'
    )
    .join('');
  disclosure.innerHTML = `
    <summary>${escapeHtml(summaryText)}</summary>
    <div class="disclosure__body">
      <table class="data-table">
        <thead><tr>${header}</tr></thead>
        <tbody>${body}</tbody>
      </table>
    </div>`;
  return disclosure;
}

/** Mark the current page in the navigation. */
function markCurrentNav() {
  const page = window.location.pathname.split('/').pop() || 'index.html';
  document.querySelectorAll('.site-nav a').forEach((link) => {
    if (link.getAttribute('href') === page) {
      link.setAttribute('aria-current', 'page');
    }
  });
}

document.addEventListener('DOMContentLoaded', markCurrentNav);
