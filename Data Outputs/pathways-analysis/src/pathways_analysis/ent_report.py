"""Build the ENT (Ear, Nose and Throat) Bayesian-family evidence pack.

This is a deliberately conservative family-boundary exercise. It does not claim
clinical approval. It identifies a core ENT seed from existing Pathways metadata,
then measures internal transitions plus inbound/outbound pathway handovers.

Usage:
    python -m pathways_analysis.ent_report

Output:
    reports/data/ent-report.json
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from .config import DatabaseSettings, Paths, load_dotenv_if_present
from .db import PathwaysDatabase

SCHEMA_VERSION = "1.0"
CORE_TERMS = (
    "ear", "hearing", "tinnitus", "nose", "nasal", "epistaxis",
    "sinus", "throat", "tonsil", "tonsillar", "larynx", "laryngeal",
    "pharynx", "pharyngeal", "otolaryng", "ent",
)
REVIEW_TERMS = (
    "swallow", "dysphagia", "neck swelling", "facial swelling",
    "dizziness", "vertigo", "jaw",
)

HEADING_TERMS = {
    "Ear": ("ear", "hearing", "tinnitus", "otolaryng"),
    "Nose": ("nose", "nasal", "epistaxis", "sinus"),
    "Throat": ("throat", "tonsil", "tonsillar", "larynx", "laryngeal", "pharynx", "pharyngeal"),
}


def _term_hits(value: object, terms: tuple[str, ...]) -> list[str]:
    text = str(value or "").strip().lower()
    hits = []
    for term in terms:
        if term == "ent":
            if re.search(r"\bent\b", text):
                hits.append(term)
        elif term in text:
            hits.append(term)
    return hits


def _ent_heading(*values: object) -> str:
    """Assign a presentation heading for report grouping only.

    This is not a clinical classification. If terms from more than one ENT domain are
    present, the pathway is deliberately labelled Cross-cutting ENT.
    """
    text = " ".join(str(v or "") for v in values).lower()
    matched = [
        heading
        for heading, terms in HEADING_TERMS.items()
        if any(term in text for term in terms)
    ]
    if len(matched) == 1:
        return matched[0]
    if len(matched) > 1:
        return "Cross-cutting ENT"
    return "Other ENT"


def build() -> dict:
    paths = Paths.discover()
    load_dotenv_if_present(paths)
    db = PathwaysDatabase(DatabaseSettings.from_env(), paths)
    try:
        db.validate_connectivity()
        pathways = db.read_query("pathways")
        symptom_groups = db.read_query("symptom_groups")
        clinical_areas = db.read_query("clinical_areas")
        pathway_areas = db.read_query("pathway_clinical_areas")
        transitions = db.read_query("pathway_transition_edges")
    finally:
        db.dispose()

    active = pathways[pathways["is_active"].astype(bool)].copy()
    sg_lookup = {
        str(r.sg_id): str(r.sg_desc or "")
        for r in symptom_groups.itertuples(index=False)
    }
    area_lookup = {
        str(r.clinical_area_id): (
            str(r.clinical_area_description or ""),
            str(r.area_group or ""),
        )
        for r in clinical_areas.itertuples(index=False)
    }
    areas_by_pathway: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for r in pathway_areas.itertuples(index=False):
        area = area_lookup.get(str(r.clinical_area_id))
        if area:
            areas_by_pathway[str(r.pathway_key)].append(area)

    included = []
    review = []
    included_keys: set[str] = set()

    for r in active.itertuples(index=False):
        key = str(r.pathway_key)
        title = str(r.pathway_title or "")
        sg = sg_lookup.get(str(r.symptom_group_id), "")
        areas = areas_by_pathway.get(key, [])

        reasons = []
        title_hits = _term_hits(title, CORE_TERMS)
        sg_hits = _term_hits(sg, CORE_TERMS)
        area_hits = sorted({
            hit
            for desc, group in areas
            for hit in _term_hits(f"{desc} {group}", CORE_TERMS)
        })
        if area_hits:
            reasons.append(
                "Existing clinical-area metadata is ENT-specific: "
                + ", ".join(area_hits)
            )
        if sg_hits:
            reasons.append(
                "Existing symptom-group metadata is ENT-specific: "
                + ", ".join(sg_hits)
            )
        if title_hits:
            reasons.append(
                "Pathway title has an explicit ENT presentation: "
                + ", ".join(title_hits)
            )

        row = {
            "pathway_id": str(r.pathway_id),
            "pathway_key": key,
            "title": title,
            "symptom_group": sg,
            "clinical_areas": [
                {"description": desc, "group": group} for desc, group in areas
            ],
            "ent_heading": _ent_heading(
                title,
                sg,
                " ".join(f"{desc} {group}" for desc, group in areas),
            ),
        }

        # Conservative core rule: metadata match is sufficient; otherwise title
        # must contain an explicit ENT term. Broad overlap terms never auto-include.
        if area_hits or sg_hits or title_hits:
            included_keys.add(key)
            included.append({
                **row,
                "decision": "include",
                "reasons": reasons,
                "evidence": {
                    "clinical_area_terms": area_hits,
                    "symptom_group_terms": sg_hits,
                    "title_terms": title_hits,
                },
            })
            continue

        review_hits = sorted(set(
            _term_hits(title, REVIEW_TERMS)
            + _term_hits(sg, REVIEW_TERMS)
            + [
                hit
                for desc, group in areas
                for hit in _term_hits(f"{desc} {group}", REVIEW_TERMS)
            ]
        ))
        if review_hits:
            review.append({
                **row,
                "decision": "review_not_included",
                "reasons": [
                    "Potential ENT overlap but not strong enough for automatic inclusion: "
                    + ", ".join(review_hits)
                ],
            })

    title_by_key = {
        str(r.pathway_key): str(r.pathway_title or "")
        for r in active.itertuples(index=False)
    }

    internal, outbound, inbound = [], [], []
    for r in transitions.itertuples(index=False):
        source = str(r.source_pathway_key)
        target = str(r.target_pathway_key)
        item = {
            "source_pathway_id": source,
            "source_title": title_by_key.get(source, ""),
            "target_pathway_id": target,
            "target_title": title_by_key.get(target, ""),
            "transition_count": int(r.transition_count),
            "answer_branches": int(r.answer_branches),
            "source_question_count": int(r.source_question_count),
        }
        source_in = source in included_keys
        target_in = target in included_keys
        if source_in and target_in:
            internal.append(item)
        elif source_in and not target_in:
            outbound.append(item)
        elif not source_in and target_in:
            inbound.append(item)

    def summarise(edges: list[dict], key: str) -> list[dict]:
        grouped: dict[str, dict] = {}
        for edge in edges:
            endpoint = edge[key]
            current = grouped.setdefault(endpoint, {
                "pathway_id": endpoint,
                "title": edge["target_title"] if key.startswith("target") else edge["source_title"],
                "transition_count": 0,
                "edge_count": 0,
            })
            current["transition_count"] += edge["transition_count"]
            current["edge_count"] += 1
        return sorted(
            grouped.values(),
            key=lambda x: (-x["transition_count"], x["pathway_id"])
        )

    included.sort(key=lambda x: (x["ent_heading"], x["title"].lower(), x["pathway_id"]))
    review.sort(key=lambda x: (x["title"].lower(), x["pathway_id"]))
    internal.sort(key=lambda x: (-x["transition_count"], x["source_pathway_id"], x["target_pathway_id"]))
    outbound.sort(key=lambda x: (-x["transition_count"], x["source_pathway_id"], x["target_pathway_id"]))
    inbound.sort(key=lambda x: (-x["transition_count"], x["source_pathway_id"], x["target_pathway_id"]))

    heading_counts = {}
    for row in included:
        heading_counts[row["ent_heading"]] = heading_counts.get(row["ent_heading"], 0) + 1

    unique_outbound = {x["target_pathway_id"] for x in outbound}
    unique_inbound = {x["source_pathway_id"] for x in inbound}

    return {
        "meta": {
            "schema_version": SCHEMA_VERSION,
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "confidentiality": (
                "Contains derived NHS Pathways analysis and pathway titles. "
                "Handle according to programme information governance requirements."
            ),
            "scope_note": (
                "Provisional ENT family definition for architecture and clinical review; "
                "not a clinically approved family boundary."
            ),
        },
        "definition": {
            "family": "ENT",
            "long_name": "Ear, Nose and Throat",
            "status": "provisional candidate for private beta",
            "principle": (
                "Start with a conservative core ENT seed, then inspect one-hop inbound "
                "and outbound pathway transfers before clinical approval."
            ),
            "automatic_inclusion_rule": (
                "Include an active pathway when its clinical-area metadata, symptom-group "
                "metadata, or pathway title contains an explicit ENT term. Broad overlap "
                "terms such as swallowing, dizziness and facial swelling are review-only."
            ),
            "core_terms": list(CORE_TERMS),
            "review_terms": list(REVIEW_TERMS),
        },
        "steps": [
            {
                "step": 1,
                "title": "Define the core ENT seed",
                "detail": "Use explicit ENT metadata/title evidence only; do not use graph proximity alone.",
            },
            {
                "step": 2,
                "title": "List every included pathway and why",
                "detail": "Each inclusion carries the metadata/title evidence that triggered it.",
            },
            {
                "step": 3,
                "title": "Trace outbound jumps",
                "detail": "Find every transfer from an included ENT pathway to a pathway outside the family.",
            },
            {
                "step": 4,
                "title": "Trace inbound jumps",
                "detail": "Reverse the graph to find every non-ENT pathway that transfers into the ENT core.",
            },
            {
                "step": 5,
                "title": "Review the boundary",
                "detail": "Use inbound/outbound evidence to decide what stays external, what is shared evidence and what should be added.",
            },
            {
                "step": 6,
                "title": "Clinical approval before BN build",
                "detail": "The resulting family boundary is an evidence pack for clinical review, not an automated clinical decision.",
            },
        ],
        "summary": {
            "included_pathways": len(included),
            "review_candidates": len(review),
            "internal_transition_pairs": len(internal),
            "outbound_transition_pairs": len(outbound),
            "inbound_transition_pairs": len(inbound),
            "internal_transition_count": sum(x["transition_count"] for x in internal),
            "outbound_transition_count": sum(x["transition_count"] for x in outbound),
            "inbound_transition_count": sum(x["transition_count"] for x in inbound),
            "unique_outbound_pathways": len(unique_outbound),
            "unique_inbound_pathways": len(unique_inbound),
            "heading_counts": heading_counts,
        },
        "included_pathways": included,
        "review_candidates": review,
        "internal_transitions": internal,
        "outbound_transitions": outbound,
        "inbound_transitions": inbound,
        "outbound_destinations": summarise(outbound, "target_pathway_id"),
        "inbound_sources": summarise(inbound, "source_pathway_id"),
        "clinical_review_questions": [
            "Does every included pathway belong in an ENT reasoning model?",
            "Which inbound pathways represent legitimate ENT entry points rather than incidental handovers?",
            "Which outbound transfers are safety escalations that should remain deterministic?",
            "Which boundary presentations should become shared/common evidence rather than family membership?",
            "Are any review-only pathways clinically core enough to move into the ENT family?",
            "Are there ENT-specific pathways missing because their metadata/title does not contain an explicit ENT term?",
        ],
    }


def main() -> int:
    payload = build()
    output = Paths.discover().project_root / "reports" / "data" / "ent-report.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
