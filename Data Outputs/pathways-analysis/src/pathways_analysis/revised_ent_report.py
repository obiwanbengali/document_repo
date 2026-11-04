"""Build the Revised ENT family report.

The revised family membership is explicit and clinically supplied. Structural endpoint
evidence comes from the Pathways database. Observed journey metrics come only from an
optional 111 Online journey CSV; they are never inferred from the deterministic graph.

Examples:
    python -m pathways_analysis.revised_ent_report
    python -m pathways_analysis.revised_ent_report --journeys-csv data/processed/111_online_journeys.csv

Supported journey CSV shapes
----------------------------
1. One row per journey:
   pathway_sequence  (e.g. PW655>PW656>PW1702)
   optional journey_count (defaults to 1)

2. One row per journey step:
   journey_id, pathway_id, step/order/sequence_number
   optional journey_count (must be constant within a journey)

The report measures journeys that START in the revised ENT family.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from .config import DatabaseSettings, Paths, load_dotenv_if_present
from .db import PathwaysDatabase

SCHEMA_VERSION = "1.0"

REVISED_ENT_PATHWAYS = (
    "PW1046", "PW1048", "PW1050", "PW1496", "PW1528", "PW1529", "PW1602",
    "PW1702", "PW1713", "PW1762", "PW636", "PW637", "PW639", "PW640",
    "PW655", "PW656", "PW818", "PW819", "PW854", "PW981", "PW984", "PW1854",
)

_SEQUENCE_COLUMNS = ("pathway_sequence", "pathways", "journey_pathways", "sequence")
_COUNT_COLUMNS = ("journey_count", "count", "volume", "journeys")
_ID_COLUMNS = ("journey_id", "session_id", "assessment_id", "case_id")
_PATHWAY_COLUMNS = ("pathway_id", "pathway", "pathway_code")
_ORDER_COLUMNS = ("step", "step_number", "sequence_number", "order", "position")


def _norm(value: object) -> str:
    return str(value or "").strip().upper()


def _first_column(frame: pd.DataFrame, candidates: tuple[str, ...]) -> Optional[str]:
    lookup = {str(c).strip().lower(): c for c in frame.columns}
    for candidate in candidates:
        if candidate in lookup:
            return str(lookup[candidate])
    return None


def _split_sequence(value: object) -> list[str]:
    raw = str(value or "").strip()
    if not raw:
        return []
    parts = re.split(r"\s*(?:>|→|\||,|;|/)\s*", raw)
    return [_norm(p) for p in parts if _norm(p)]


def _load_journeys(path: Path) -> list[dict[str, Any]]:
    frame = pd.read_csv(path)
    sequence_col = _first_column(frame, _SEQUENCE_COLUMNS)
    count_col = _first_column(frame, _COUNT_COLUMNS)

    if sequence_col:
        journeys = []
        for row in frame.itertuples(index=False):
            values = row._asdict()
            sequence = _split_sequence(values.get(sequence_col))
            if not sequence:
                continue
            count = float(values.get(count_col, 1) or 1) if count_col else 1.0
            journeys.append({"sequence": sequence, "count": count})
        return journeys

    id_col = _first_column(frame, _ID_COLUMNS)
    pathway_col = _first_column(frame, _PATHWAY_COLUMNS)
    order_col = _first_column(frame, _ORDER_COLUMNS)
    if not id_col or not pathway_col:
        raise ValueError(
            "Journey CSV must contain either a pathway_sequence column, or journey_id "
            "and pathway_id columns. Recognised aliases are documented in this module."
        )

    work = frame.copy()
    work[pathway_col] = work[pathway_col].map(_norm)
    if order_col:
        work = work.sort_values([id_col, order_col])
    journeys = []
    for _, group in work.groupby(id_col, sort=False):
        sequence = [p for p in group[pathway_col].tolist() if p]
        if not sequence:
            continue
        count = 1.0
        if count_col:
            counts = pd.to_numeric(group[count_col], errors="coerce").dropna().unique()
            if len(counts):
                count = float(counts[0])
        journeys.append({"sequence": sequence, "count": count})
    return journeys


def _pct(numerator: float, denominator: float) -> Optional[float]:
    if denominator <= 0:
        return None
    return round(100.0 * numerator / denominator, 2)


def _journey_metrics(journeys: list[dict[str, Any]]) -> dict[str, Any]:
    ent = set(REVISED_ENT_PATHWAYS)
    total = sum(float(j["count"]) for j in journeys)
    ent_started = [j for j in journeys if j["sequence"] and j["sequence"][0] in ent]
    ent_volume = sum(float(j["count"]) for j in ent_started)

    same_pathway = 0.0
    finish_ent = 0.0
    finish_ent_no_leave = 0.0
    finish_ent_left_and_returned = 0.0
    finish_out_scope = 0.0

    for journey in ent_started:
        seq = journey["sequence"]
        weight = float(journey["count"])
        start, finish = seq[0], seq[-1]
        all_ent = all(p in ent for p in seq)
        left_ent = any(p not in ent for p in seq)

        if start == finish:
            same_pathway += weight
        if finish in ent:
            finish_ent += weight
            if all_ent:
                finish_ent_no_leave += weight
            elif left_ent:
                finish_ent_left_and_returned += weight
        else:
            finish_out_scope += weight

    return {
        "status": "available",
        "total_111_online_journeys": total,
        "ent_start_journeys": ent_volume,
        "coverage_percentage": _pct(ent_volume, total),
        "e2e_completion_within_group_percentage": _pct(finish_ent, ent_volume),
        "same_start_finish_pathway_percentage": _pct(same_pathway, ent_volume),
        "start_finish_ent_no_unsupported_percentage": _pct(finish_ent_no_leave, ent_volume),
        "start_finish_ent_with_unsupported_percentage": _pct(
            finish_ent_left_and_returned, ent_volume
        ),
        "finish_handover_out_of_scope_percentage": _pct(finish_out_scope, ent_volume),
        "definitions": {
            "coverage_percentage": (
                "Observed 111 Online journeys whose first pathway is in Revised ENT, "
                "as a percentage of all journeys in the supplied dataset."
            ),
            "e2e_completion_within_group_percentage": (
                "Journeys starting in Revised ENT whose final pathway is also in Revised ENT, "
                "whether or not they temporarily left the family."
            ),
            "same_start_finish_pathway_percentage": (
                "Journeys starting in Revised ENT whose final pathway equals their first pathway."
            ),
            "start_finish_ent_no_unsupported_percentage": (
                "Journeys starting and finishing in Revised ENT where every observed pathway "
                "in the sequence is also in Revised ENT."
            ),
            "start_finish_ent_with_unsupported_percentage": (
                "Journeys starting and finishing in Revised ENT that visit at least one pathway "
                "outside Revised ENT before returning."
            ),
            "finish_handover_out_of_scope_percentage": (
                "Journeys starting in Revised ENT whose final observed pathway is outside Revised ENT."
            ),
        },
    }


def _unavailable_metrics() -> dict[str, Any]:
    return {
        "status": "unavailable",
        "reason": (
            "No observed 111 Online journey CSV was supplied. These metrics cannot be "
            "derived from deterministic Pathways structure alone."
        ),
        "total_111_online_journeys": None,
        "ent_start_journeys": None,
        "coverage_percentage": None,
        "e2e_completion_within_group_percentage": None,
        "same_start_finish_pathway_percentage": None,
        "start_finish_ent_no_unsupported_percentage": None,
        "start_finish_ent_with_unsupported_percentage": None,
        "finish_handover_out_of_scope_percentage": None,
        "definitions": _journey_metrics([])["definitions"],
    }


def build(journeys_csv: Optional[Path] = None) -> dict[str, Any]:
    paths = Paths.discover()
    load_dotenv_if_present(paths)
    db = PathwaysDatabase(DatabaseSettings.from_env(), paths)
    try:
        print("Connecting to Pathways database...", flush=True)
        db.validate_connectivity()

        print("Loading pathway and disposition reference data...", flush=True)
        pathways = db.read_query("pathways")
        dispositions = db.read_query("dispositions")

        print(
            f"Loading transfer/end-point data for {len(REVISED_ENT_PATHWAYS)} Revised ENT pathways...",
            flush=True,
        )
        transfer_frames = []
        for index, pathway_id in enumerate(REVISED_ENT_PATHWAYS, start=1):
            print(
                f"  [{index:02d}/{len(REVISED_ENT_PATHWAYS)}] {pathway_id}",
                flush=True,
            )
            transfer_frames.append(
                db.read_query(
                    "transfer_values_for_source_pathway",
                    {"source_pathway_key": pathway_id},
                )
            )
        transfer_values = (
            pd.concat(transfer_frames, ignore_index=True)
            if transfer_frames
            else pd.DataFrame()
        )
        print(
            f"Loaded {len(transfer_values):,} scoped egress/end-point rows.",
            flush=True,
        )

        print(
            f"Loading ingress data into {len(REVISED_ENT_PATHWAYS)} Revised ENT pathways...",
            flush=True,
        )
        ingress_frames = []
        for index, pathway_id in enumerate(REVISED_ENT_PATHWAYS, start=1):
            print(
                f"  inbound [{index:02d}/{len(REVISED_ENT_PATHWAYS)}] {pathway_id}",
                flush=True,
            )
            ingress_frames.append(
                db.read_query(
                    "transfer_values_to_target_pathway",
                    {"target_pathway_prefix": f"{pathway_id}.%"},
                )
            )
        ingress_values = (
            pd.concat(ingress_frames, ignore_index=True)
            if ingress_frames
            else pd.DataFrame()
        )
        print(
            f"Loaded {len(ingress_values):,} scoped ingress rows.",
            flush=True,
        )
    finally:
        db.dispose()

    ent = set(REVISED_ENT_PATHWAYS)
    pathway_rows = pathways[pathways["pathway_key"].map(_norm).isin(ent)].copy()
    found = set(pathway_rows["pathway_key"].map(_norm))
    missing = sorted(ent - found)
    titles = {
        _norm(r.pathway_key): str(r.pathway_title or "")
        for r in pathways.itertuples(index=False)
    }
    disp_text_by_code = {
        _norm(r.disposition_code): str(r.disposition_text or "")
        for r in dispositions.itertuples(index=False)
        if str(r.disposition_code or "").strip()
    }
    disp_text_by_id = {
        _norm(r.disposition_id): str(r.disposition_text or "")
        for r in dispositions.itertuples(index=False)
        if str(r.disposition_id or "").strip()
    }

    # All direct branch endpoints from an ENT pathway. An in-family pathway transfer is
    # continuation, not an endpoint. A disposition or first transfer outside the family
    # is a potential endpoint for the scoped ENT service.
    endpoint_map: dict[tuple[str, str], dict[str, Any]] = {}
    internal_transfers: dict[tuple[str, str], dict[str, Any]] = {}

    for r in transfer_values.itertuples(index=False):
        source = _norm(r.source_pathway_key)
        if source not in ent:
            continue

        resolves_pathway = bool(r.resolves_pathway)
        resolves_disp_code = bool(r.resolves_disposition_code)
        resolves_disp_id = bool(r.resolves_disposition_id)

        if resolves_pathway:
            target = _norm(r.candidate_pathway_key)
            key = (source, target)
            if target in ent:
                current = internal_transfers.setdefault(key, {
                    "source_pathway_id": source,
                    "source_title": titles.get(source, ""),
                    "target_pathway_id": target,
                    "target_title": titles.get(target, ""),
                    "branch_count": 0,
                })
                current["branch_count"] += 1
            else:
                key2 = ("out_of_scope_pathway", target)
                current = endpoint_map.setdefault(key2, {
                    "endpoint_type": "Out-of-scope pathway handover",
                    "endpoint_code": target,
                    "endpoint_name": titles.get(target, ""),
                    "source_pathways": set(),
                    "branch_count": 0,
                })
                current["source_pathways"].add(source)
                current["branch_count"] += 1
            continue

        if resolves_disp_code or resolves_disp_id:
            code = _norm(r.resolved_disposition_code or r.resolved_disposition_id)
            name = disp_text_by_code.get(code) or disp_text_by_id.get(code) or ""
            key2 = ("disposition", code)
            current = endpoint_map.setdefault(key2, {
                "endpoint_type": "Disposition",
                "endpoint_code": code,
                "endpoint_name": name,
                "source_pathways": set(),
                "branch_count": 0,
            })
            current["source_pathways"].add(source)
            current["branch_count"] += 1

    # Detailed boundary-crossing rows. These retain the actual source/target pathway,
    # order position, question reference, answer number and T1-T4 branch so a reviewer
    # can see exactly where the family boundary is crossed.
    egress_routes = []
    disposition_routes = []
    internal_route_details = []

    for r in transfer_values.itertuples(index=False):
        source = _norm(r.source_pathway_key)
        if source not in ent:
            continue
        route = {
            "source_pathway_id": source,
            "source_title": titles.get(source, ""),
            "source_order": int(r.source_order) if pd.notna(r.source_order) else None,
            "question_id": _norm(r.question_key),
            "answer_number": int(r.answer_number) if pd.notna(r.answer_number) else None,
            "jump_id": int(r.jump_id) if pd.notna(r.jump_id) else None,
            "transfer_branch": str(r.branch or ""),
            "raw_transfer_value": str(r.transfer_value or ""),
        }
        if bool(r.resolves_pathway):
            target = _norm(r.candidate_pathway_key)
            route.update({
                "target_pathway_id": target,
                "target_title": titles.get(target, ""),
                "target_order": (
                    int(r.candidate_order_number)
                    if pd.notna(r.candidate_order_number)
                    else None
                ),
                "target_order_resolved": bool(r.target_order_resolved),
            })
            if target in ent:
                internal_route_details.append(route)
            else:
                egress_routes.append(route)
        elif bool(r.resolves_disposition_code) or bool(r.resolves_disposition_id):
            code = _norm(r.resolved_disposition_code or r.resolved_disposition_id)
            route.update({
                "disposition_code": code,
                "disposition_text": disp_text_by_code.get(code)
                    or disp_text_by_id.get(code)
                    or "",
            })
            disposition_routes.append(route)

    ingress_routes = []
    for r in ingress_values.itertuples(index=False):
        source = _norm(r.source_pathway_key)
        target = _norm(r.candidate_pathway_key)
        if target not in ent or source in ent:
            continue
        ingress_routes.append({
            "source_pathway_id": source,
            "source_title": titles.get(source, ""),
            "source_order": int(r.source_order) if pd.notna(r.source_order) else None,
            "question_id": _norm(r.question_key),
            "answer_number": int(r.answer_number) if pd.notna(r.answer_number) else None,
            "jump_id": int(r.jump_id) if pd.notna(r.jump_id) else None,
            "transfer_branch": str(r.branch or ""),
            "target_pathway_id": target,
            "target_title": titles.get(target, ""),
            "target_order": (
                int(r.candidate_order_number)
                if pd.notna(r.candidate_order_number)
                else None
            ),
            "target_order_resolved": bool(r.target_order_resolved),
            "raw_transfer_value": str(r.transfer_value or ""),
        })

    def _route_pair_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        grouped: dict[tuple[str, str], dict[str, Any]] = {}
        for row in rows:
            key = (row["source_pathway_id"], row["target_pathway_id"])
            item = grouped.setdefault(key, {
                "source_pathway_id": row["source_pathway_id"],
                "source_title": row["source_title"],
                "target_pathway_id": row["target_pathway_id"],
                "target_title": row["target_title"],
                "transfer_points": 0,
                "source_orders": set(),
                "target_orders": set(),
                "questions": set(),
            })
            item["transfer_points"] += 1
            if row["source_order"] is not None:
                item["source_orders"].add(row["source_order"])
            if row["target_order"] is not None:
                item["target_orders"].add(row["target_order"])
            if row["question_id"]:
                item["questions"].add(row["question_id"])
        result = []
        for item in grouped.values():
            result.append({
                **item,
                "source_orders": sorted(item["source_orders"]),
                "target_orders": sorted(item["target_orders"]),
                "questions": sorted(item["questions"]),
            })
        return sorted(
            result,
            key=lambda x: (-x["transfer_points"], x["source_pathway_id"], x["target_pathway_id"]),
        )

    ingress_pairs = _route_pair_summary(ingress_routes)
    egress_pairs = _route_pair_summary(egress_routes)

    # Pathway-level boundary profile to expose hotspots and self-contained members.
    boundary_profile = []
    for pid in REVISED_ENT_PATHWAYS:
        ingress_for = [x for x in ingress_routes if x["target_pathway_id"] == pid]
        egress_for = [x for x in egress_routes if x["source_pathway_id"] == pid]
        internal_in = [x for x in internal_route_details if x["target_pathway_id"] == pid]
        internal_out = [x for x in internal_route_details if x["source_pathway_id"] == pid]
        disposition_for = [x for x in disposition_routes if x["source_pathway_id"] == pid]
        external_sources = sorted({x["source_pathway_id"] for x in ingress_for})
        external_targets = sorted({x["target_pathway_id"] for x in egress_for})
        if ingress_for and egress_for:
            boundary_role = "Two-way boundary"
        elif ingress_for:
            boundary_role = "Ingress boundary"
        elif egress_for:
            boundary_role = "Egress boundary"
        else:
            boundary_role = "No external pathway transfer"
        boundary_profile.append({
            "pathway_id": pid,
            "title": titles.get(pid, ""),
            "boundary_role": boundary_role,
            "external_ingress_sources": external_sources,
            "external_ingress_source_count": len(external_sources),
            "ingress_transfer_points": len(ingress_for),
            "external_egress_targets": external_targets,
            "external_egress_target_count": len(external_targets),
            "egress_transfer_points": len(egress_for),
            "internal_in_transfer_points": len(internal_in),
            "internal_out_transfer_points": len(internal_out),
            "disposition_points": len(disposition_for),
        })
    boundary_profile.sort(
        key=lambda x: (
            -(x["ingress_transfer_points"] + x["egress_transfer_points"]),
            x["pathway_id"],
        )
    )

    boundary_summary = {
        "external_ingress_pathways": len({x["source_pathway_id"] for x in ingress_routes}),
        "ent_ingress_targets": len({x["target_pathway_id"] for x in ingress_routes}),
        "ingress_transfer_points": len(ingress_routes),
        "external_egress_pathways": len({x["target_pathway_id"] for x in egress_routes}),
        "ent_egress_sources": len({x["source_pathway_id"] for x in egress_routes}),
        "egress_transfer_points": len(egress_routes),
        "ent_pathways_with_no_external_transfer": sum(
            1 for x in boundary_profile if x["boundary_role"] == "No external pathway transfer"
        ),
        "two_way_boundary_pathways": sum(
            1 for x in boundary_profile if x["boundary_role"] == "Two-way boundary"
        ),
    }

    endpoints = []
    for value in endpoint_map.values():
        endpoints.append({
            **value,
            "source_pathways": sorted(value["source_pathways"]),
            "source_pathway_count": len(value["source_pathways"]),
        })
    endpoints.sort(key=lambda x: (x["endpoint_type"], x["endpoint_code"]))

    membership = [
        {
            "pathway_id": pid,
            "title": titles.get(pid, ""),
            "status": "found" if pid in found else "not_found_in_pathways_snapshot",
        }
        for pid in REVISED_ENT_PATHWAYS
    ]

    if journeys_csv:
        print(f"Loading observed 111 Online journeys from {journeys_csv}...", flush=True)
        metrics = _journey_metrics(_load_journeys(journeys_csv))
        metrics["source"] = str(journeys_csv)
    else:
        metrics = _unavailable_metrics()
        metrics["source"] = None

    return {
        "meta": {
            "schema_version": SCHEMA_VERSION,
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "confidentiality": (
                "Contains derived NHS Pathways analysis and pathway titles. "
                "Handle according to programme information governance requirements."
            ),
            "scope_note": (
                "Revised ENT membership supplied explicitly for family evaluation; "
                "journey percentages are observational only when a 111 Online journey "
                "dataset is supplied."
            ),
        },
        "definition": {
            "family": "Revised ENT",
            "pathway_count": len(REVISED_ENT_PATHWAYS),
            "pathway_ids": list(REVISED_ENT_PATHWAYS),
            "missing_pathway_ids": missing,
        },
        "membership": membership,
        "journey_metrics": metrics,
        "potential_endpoints": endpoints,
        "boundary_summary": boundary_summary,
        "boundary_profile": boundary_profile,
        "ingress_pairs": ingress_pairs,
        "egress_pairs": egress_pairs,
        "ingress_routes": sorted(
            ingress_routes,
            key=lambda x: (
                x["target_pathway_id"],
                x["source_pathway_id"],
                x["source_order"] if x["source_order"] is not None else -1,
            ),
        ),
        "egress_routes": sorted(
            egress_routes,
            key=lambda x: (
                x["source_pathway_id"],
                x["target_pathway_id"],
                x["source_order"] if x["source_order"] is not None else -1,
            ),
        ),
        "internal_route_details": sorted(
            internal_route_details,
            key=lambda x: (
                x["source_pathway_id"],
                x["target_pathway_id"],
                x["source_order"] if x["source_order"] is not None else -1,
            ),
        ),
        "disposition_routes": sorted(
            disposition_routes,
            key=lambda x: (
                x["source_pathway_id"],
                x["disposition_code"],
                x["source_order"] if x["source_order"] is not None else -1,
            ),
        ),
        "endpoint_summary": {
            "total_unique_endpoints": len(endpoints),
            "dispositions": sum(1 for x in endpoints if x["endpoint_type"] == "Disposition"),
            "out_of_scope_pathways": sum(
                1 for x in endpoints if x["endpoint_type"] == "Out-of-scope pathway handover"
            ),
        },
        "internal_transfers": sorted(
            internal_transfers.values(),
            key=lambda x: (-x["branch_count"], x["source_pathway_id"], x["target_pathway_id"]),
        ),
        "metric_notes": [
            "Observed percentages use only journeys whose first pathway is in Revised ENT.",
            "A journey can start and finish in ENT but still leave the family temporarily; that is reported separately.",
            "Ingress and egress rows are deterministic transfer possibilities, not observed journey frequencies.",
            "A transfer point is one concrete Pathways source-order / answer / T1-T4 route that crosses the Revised ENT boundary.",
            "An out-of-scope pathway transfer is treated as the endpoint of the scoped Revised ENT service because the next pathway is unsupported by this family.",
        ],
    }


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build the Revised ENT report data.")
    parser.add_argument(
        "--journeys-csv",
        type=Path,
        default=None,
        help="Optional observed 111 Online journey CSV used for volume/completion metrics.",
    )
    args = parser.parse_args(argv)
    print("Building Revised ENT report...", flush=True)
    payload = build(args.journeys_csv)
    output = Paths.discover().reports_data / "revised-ent-report.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {output}")
    if payload["journey_metrics"]["status"] != "available":
        print("Journey metrics unavailable: supply --journeys-csv to calculate them.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
