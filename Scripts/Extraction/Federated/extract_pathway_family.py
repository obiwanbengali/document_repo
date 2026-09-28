#!/usr/bin/env python3
"""
Federated Pathway Family Extractor

Primary entry point for extracting a clinically-defined family of NHS Pathways.

This script reuses the proven single-pathway parsing implementation from
../extract_pathway_dag.py, but changes the operating model and output contract
from "one pathway DAG" to "one family graph".

Key principles:
- A family is an explicit list of pathways; family membership is not inferred here.
- Every node/edge retains source pathway provenance.
- Shared questions/nodes across pathways are identified.
- Cross-pathway redirects are identified and classified as internal/external.
- No synthetic probability weights are created during extraction.
- Output is intended to become the canonical structural input to downstream
  family-BN construction, evidence mapping, analysis and visualisation.

Examples:

    python Scripts/Extraction/Federated/extract_pathway_family.py \
        --family ENT \
        --pathways PW1,PW2,PW3

    python Scripts/Extraction/Federated/extract_pathway_family.py \
        --family ENT \
        --pathways-file config/ent_pathways.json

Pathways file formats supported:

    ["PW1", "PW2", "PW3"]

or:

    {
      "family": "ENT",
      "pathways": ["PW1", "PW2", "PW3"]
    }
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


EXTRACTION_DIR = Path(__file__).resolve().parents[1]
if str(EXTRACTION_DIR) not in sys.path:
    sys.path.insert(0, str(EXTRACTION_DIR))

from extract_pathway_dag import PathwayExtractor  # noqa: E402


def load_env_file() -> None:
    """Load local .env values, preserving variables already set by the shell."""
    candidates = [
        EXTRACTION_DIR / ".env",
        Path.cwd() / ".env",
    ]

    for env_path in candidates:
        if not env_path.exists():
            continue

        with env_path.open("r", encoding="utf-8") as env_file:
            for raw_line in env_file:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue

                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key:
                    os.environ.setdefault(key, value)


def safe_name(value: str) -> str:
    """Return a filename-safe value."""
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", value.strip())
    return cleaned or "unknown"


def load_family_definition(
    family_name: Optional[str],
    pathways_csv: Optional[str],
    pathways_file: Optional[str],
) -> Tuple[str, List[str]]:
    """Load a family name and stable, de-duplicated pathway list."""
    pathways: List[str] = []
    resolved_family = family_name.strip() if family_name else ""

    if pathways_csv:
        pathways.extend(
            item.strip()
            for item in pathways_csv.split(",")
            if item.strip()
        )

    if pathways_file:
        path = Path(pathways_file)
        if not path.exists():
            raise FileNotFoundError(f"Pathways file not found: {path}")

        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)

        if isinstance(payload, list):
            pathways.extend(str(item).strip() for item in payload if str(item).strip())

        elif isinstance(payload, dict):
            file_family = payload.get("family")
            if not resolved_family and file_family:
                resolved_family = str(file_family).strip()

            file_pathways = payload.get("pathways", [])
            if not isinstance(file_pathways, list):
                raise ValueError("'pathways' must be a JSON array")

            pathways.extend(
                str(item).strip()
                for item in file_pathways
                if str(item).strip()
            )

        else:
            raise ValueError(
                "Pathways file must be either a JSON array or an object with a 'pathways' array"
            )

    pathways = list(dict.fromkeys(pathways))

    if not resolved_family:
        raise ValueError("Family name is required via --family or pathways file")

    if not pathways:
        raise ValueError("At least one pathway must be supplied")

    return resolved_family, pathways


class PathwayFamilyExtractor:
    """Coordinates canonical pathway extraction across a family."""

    def __init__(self, extractor: PathwayExtractor):
        self.extractor = extractor

    def _resolve_metadata(
        self,
        pathway_id: str,
        requested_version: Optional[str] = None,
    ) -> Dict[str, Optional[str]]:
        """Resolve the version and release that will be extracted."""
        cursor = self.extractor.conn.cursor()

        if requested_version is None:
            cursor.execute(
                f"""
                SELECT MAX([Version])
                FROM {self.extractor._table('PWR_Pathways')}
                WHERE PW_ID = ?
                """,
                pathway_id,
            )
            row = cursor.fetchone()
            if not row or row[0] is None:
                return {"version": None, "release": None}
            version = str(row[0])
        else:
            version = str(requested_version)

        cursor.execute(
            f"""
            SELECT MAX([Release])
            FROM {self.extractor._table('PWR_Pathways')}
            WHERE PW_ID = ?
              AND [Version] = ?
            """,
            pathway_id,
            version,
        )
        row = cursor.fetchone()
        release = str(row[0]) if row and row[0] is not None else None

        return {
            "version": version,
            "release": release,
        }

    @staticmethod
    def _from_node_id(edge: Dict[str, Any]) -> Optional[str]:
        value = edge.get("from_node")
        if value is None:
            return None
        return str(value).split(".", 1)[0].strip() or None

    @staticmethod
    def _to_node_id(edge: Dict[str, Any]) -> Optional[str]:
        value = edge.get("to_node_id") or edge.get("to_node")
        if value is None:
            return None
        return str(value).strip() or None

    def extract_family(
        self,
        family_name: str,
        pathway_ids: List[str],
        requested_version: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Extract and aggregate a family of pathways."""

        family_members = set(pathway_ids)
        pathway_results: List[Dict[str, Any]] = []
        family_edges: List[Dict[str, Any]] = []
        failures: List[Dict[str, str]] = []

        node_pathways: Dict[str, Set[str]] = defaultdict(set)
        node_types: Dict[str, Set[str]] = defaultdict(set)
        node_texts: Dict[str, Set[str]] = defaultdict(set)

        internal_pathway_jumps: List[Dict[str, Any]] = []
        external_pathway_jumps: List[Dict[str, Any]] = []

        for pathway_id in pathway_ids:
            print(f"\n=== {family_name}: extracting {pathway_id} ===")

            try:
                metadata = self._resolve_metadata(pathway_id, requested_version)
                version = metadata["version"]
                release = metadata["release"]

                if version is None or release is None:
                    failures.append({
                        "pathway_id": pathway_id,
                        "reason": "Unable to resolve version/release",
                    })
                    continue

                edges = self.extractor.extract_pathway_dag(
                    pathway_id,
                    version=version,
                )

                serialised_edges: List[Dict[str, Any]] = []

                for raw_edge in edges:
                    edge = asdict(raw_edge)

                    # Provenance is deliberately attached to every edge.
                    edge["family"] = family_name
                    edge["pathway_id"] = pathway_id
                    edge["version"] = version
                    edge["release"] = release

                    from_node_id = self._from_node_id(edge)
                    to_node_id = self._to_node_id(edge)

                    edge["from_node_id"] = from_node_id
                    edge["resolved_to_node_id"] = to_node_id

                    serialised_edges.append(edge)
                    family_edges.append(edge)

                    if from_node_id:
                        node_pathways[from_node_id].add(pathway_id)
                        node_types[from_node_id].add("Question")
                        if edge.get("from_question_text"):
                            node_texts[from_node_id].add(str(edge["from_question_text"]))

                    if to_node_id:
                        node_pathways[to_node_id].add(pathway_id)
                        node_types[to_node_id].add(str(edge.get("to_node_type") or "Unknown"))

                        target_text = edge.get("to_question_text") or edge.get("dispo_text")
                        if target_text:
                            node_texts[to_node_id].add(str(target_text))

                    if edge.get("to_node_type") == "Pathway" and to_node_id:
                        jump = {
                            "source_pathway_id": pathway_id,
                            "target_pathway_id": to_node_id,
                            "from_node_id": from_node_id,
                            "answer_text": edge.get("answer_text"),
                            "skillset": edge.get("skillset"),
                        }

                        if to_node_id in family_members:
                            jump["classification"] = "internal_family_jump"
                            internal_pathway_jumps.append(jump)
                        else:
                            jump["classification"] = "external_family_jump"
                            external_pathway_jumps.append(jump)

                pathway_results.append({
                    "pathway_id": pathway_id,
                    "version": version,
                    "release": release,
                    "edge_count": len(serialised_edges),
                    "edges": serialised_edges,
                })

                print(
                    f"Extracted {len(serialised_edges)} edges "
                    f"(version={version}, release={release})"
                )

            except Exception as exc:
                failures.append({
                    "pathway_id": pathway_id,
                    "reason": str(exc),
                })
                print(f"ERROR extracting {pathway_id}: {exc}")

        nodes: List[Dict[str, Any]] = []
        shared_nodes: List[Dict[str, Any]] = []

        for node_id in sorted(node_pathways):
            pathways = sorted(node_pathways[node_id])

            node = {
                "node_id": node_id,
                "node_types": sorted(node_types[node_id]),
                "texts": sorted(node_texts[node_id]),
                "pathway_ids": pathways,
                "pathway_count": len(pathways),
                "shared_across_pathways": len(pathways) > 1,
            }

            nodes.append(node)

            if node["shared_across_pathways"]:
                shared_nodes.append(node)

        successful_pathway_ids = [item["pathway_id"] for item in pathway_results]

        summary = {
            "family": family_name,
            "requested_pathways": len(pathway_ids),
            "successfully_extracted_pathways": len(successful_pathway_ids),
            "failed_pathways": len(failures),
            "total_edges": len(family_edges),
            "unique_nodes": len(nodes),
            "shared_nodes": len(shared_nodes),
            "internal_family_pathway_jumps": len(internal_pathway_jumps),
            "external_family_pathway_jumps": len(external_pathway_jumps),
        }

        return {
            "schema_version": "1.0",
            "artifact_type": "pathway_family_graph",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "family": {
                "name": family_name,
                "requested_pathway_ids": pathway_ids,
                "extracted_pathway_ids": successful_pathway_ids,
            },
            "summary": summary,
            "pathways": pathway_results,
            "nodes": nodes,
            "shared_nodes": shared_nodes,
            "edges": family_edges,
            "pathway_jumps": {
                "internal": internal_pathway_jumps,
                "external": external_pathway_jumps,
            },
            "failures": failures,
        }


def write_outputs(
    result: Dict[str, Any],
    output_dir: Path,
) -> Dict[str, str]:
    """Write canonical family outputs."""
    output_dir.mkdir(parents=True, exist_ok=True)

    family_name = safe_name(result["family"]["name"])

    graph_path = output_dir / f"{family_name}_family_graph.json"
    summary_path = output_dir / f"{family_name}_family_summary.json"
    shared_nodes_path = output_dir / f"{family_name}_shared_nodes.json"
    pathway_jumps_path = output_dir / f"{family_name}_pathway_jumps.json"

    with graph_path.open("w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, ensure_ascii=False)

    with summary_path.open("w", encoding="utf-8") as handle:
        json.dump(
            {
                "family": result["family"],
                "summary": result["summary"],
                "failures": result["failures"],
            },
            handle,
            indent=2,
            ensure_ascii=False,
        )

    with shared_nodes_path.open("w", encoding="utf-8") as handle:
        json.dump(result["shared_nodes"], handle, indent=2, ensure_ascii=False)

    with pathway_jumps_path.open("w", encoding="utf-8") as handle:
        json.dump(result["pathway_jumps"], handle, indent=2, ensure_ascii=False)

    return {
        "family_graph": str(graph_path),
        "family_summary": str(summary_path),
        "shared_nodes": str(shared_nodes_path),
        "pathway_jumps": str(pathway_jumps_path),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract a canonical structural graph for a family of NHS Pathways."
    )

    parser.add_argument(
        "--family",
        help="Family name, for example ENT",
    )

    parser.add_argument(
        "--pathways",
        help="Comma-separated pathway IDs",
    )

    parser.add_argument(
        "--pathways-file",
        help="JSON file containing a pathways array, optionally with a family name",
    )

    parser.add_argument(
        "--version",
        help="Optional version to apply to every pathway; defaults to latest per pathway",
    )

    parser.add_argument(
        "--schema",
        default=None,
        help="SQL schema name; defaults to SQL_SCHEMA or dbo",
    )

    parser.add_argument(
        "--output-dir",
        default=None,
        help="Output directory; defaults to outputs/federated/<family>",
    )

    return parser


def main() -> None:
    load_env_file()
    args = build_arg_parser().parse_args()

    try:
        family_name, pathway_ids = load_family_definition(
            args.family,
            args.pathways,
            args.pathways_file,
        )
    except Exception as exc:
        print(f"ERROR: {exc}")
        sys.exit(2)

    sql_connection_string = os.getenv("SQL_CONNECTION_STRING")
    sql_server = os.getenv("SQL_SERVER", "localhost")
    sql_port = int(os.getenv("SQL_PORT", "1433"))
    sql_database = os.getenv("SQL_DATABASE", "TriageDB")
    sql_username = os.getenv("SQL_USERNAME")
    sql_password = os.getenv("SQL_PASSWORD")
    sql_encrypt = os.getenv("SQL_ENCRYPT", "yes")
    sql_trust_server_certificate = os.getenv(
        "SQL_TRUST_SERVER_CERTIFICATE",
        "yes",
    )
    sql_login_timeout = int(os.getenv("SQL_LOGIN_TIMEOUT", "30"))
    schema_name = args.schema or os.getenv("SQL_SCHEMA", "dbo")

    if (sql_username and not sql_password) or (sql_password and not sql_username):
        print(
            "ERROR: set both SQL_USERNAME and SQL_PASSWORD for SQL authentication, "
            "or leave both unset for Trusted_Connection"
        )
        sys.exit(2)

    extractor = PathwayExtractor(
        server=sql_server,
        database=sql_database,
        username=sql_username,
        password=sql_password,
        schema_name=schema_name,
        port=sql_port,
        encrypt=sql_encrypt,
        trust_server_certificate=sql_trust_server_certificate,
        login_timeout=sql_login_timeout,
        connection_string=sql_connection_string,
    )

    if not extractor.connect():
        sys.exit(1)

    try:
        family_extractor = PathwayFamilyExtractor(extractor)

        result = family_extractor.extract_family(
            family_name=family_name,
            pathway_ids=pathway_ids,
            requested_version=args.version,
        )

        output_dir = (
            Path(args.output_dir)
            if args.output_dir
            else Path("outputs") / "federated" / safe_name(family_name)
        )

        files = write_outputs(result, output_dir)

        print("\n=== Family extraction complete ===")
        for key, value in result["summary"].items():
            print(f"{key}: {value}")

        print("\nOutputs:")
        for label, path in files.items():
            print(f"  {label}: {path}")

        if result["failures"]:
            print("\nWARNING: Some pathways failed extraction:")
            for failure in result["failures"]:
                print(
                    f"  {failure['pathway_id']}: {failure['reason']}"
                )

    finally:
        extractor.close()


if __name__ == "__main__":
    main()
