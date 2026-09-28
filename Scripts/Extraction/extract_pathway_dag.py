#!/usr/bin/env python3
"""
Triage Pathway DAG Extractor

Connects to SQL Server database and extracts deterministic pathway structure
as a directed acyclic graph (DAG) for visualization and analysis.
"""

import pyodbc
import json
import sys
import os
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict


@dataclass
class PathwayEdge:
    """Represents an edge in the pathway DAG"""
    from_node: str
    from_question_text: Optional[str]
    to_node: str
    to_node_id: Optional[str]
    to_node_type: str          # "Tx" | "Cx" | "Dx" | "Pathway" | "Transfer" | "Unknown"
    to_question_text: Optional[str]
    answer_text: str
    jump_type: str
    answer_rationale: Optional[str] = None
    from_question_rationale: Optional[str] = None
    dispo_text: Optional[str] = None
    skillset: Optional[str] = None


class PathwayExtractor:
    """Extracts pathway DAG from triage SQL Server database"""
    
    def __init__(self, server: str = "localhost", database: str = "TriageDB",
                 username: Optional[str] = None, password: Optional[str] = None,
                 schema_name: str = "dbo", port: int = 1433,
                 encrypt: str = "yes", trust_server_certificate: str = "yes",
                 login_timeout: int = 30,
                 connection_string: Optional[str] = None):
        if connection_string:
            self.connection_string = connection_string
        else:
            auth_section = (
                f"UID={username};PWD={password};"
                if username and password
                else "Trusted_Connection=yes;"
            )
            self.connection_string = (
                f"DRIVER={{ODBC Driver 18 for SQL Server}};"
                f"SERVER=tcp:{server},{port};"
                f"DATABASE={database};"
                f"{auth_section}"
                f"Encrypt={encrypt};"
                f"TrustServerCertificate={trust_server_certificate};"
                f"LoginTimeout={login_timeout};"
            )
        self.database = database
        self.schema_name = self._validate_schema_name(schema_name)
        self.conn = None

    @staticmethod
    def _validate_schema_name(schema_name: str) -> str:
        """Allow only simple SQL identifiers for schema names."""
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", schema_name):
            raise ValueError(f"Invalid schema name: {schema_name}")
        return schema_name

    def _table(self, table_name: str) -> str:
        """Return fully qualified table name with validated schema."""
        return f"[{self.schema_name}].[{table_name}]"

    @staticmethod
    def _classify_node_type(node_id: Optional[str]) -> str:
        """Classify a resolved node identifier by prefix."""
        if not node_id:
            return "Unknown"
        value = str(node_id).strip()
        if value.startswith("Tx"):
            return "Tx"
        if value.startswith("Cx"):
            return "Cx"
        if value.startswith("Dx"):
            return "Dx"
        if value.startswith("PW") or value.startswith("PA"):
            return "Pathway"
        return "Unknown"

    def _build_order_to_node_id_map(self, pw_id: str, release: str) -> Dict[str, str]:
        """Map triage logic OrderNo values to their target node IDs (typically Tx/Cx)."""
        query = f"""
        SELECT DISTINCT
            TL.OrderNo,
            TL.Qu_ID AS NodeID
        FROM {self._table('PWR_TriageLogic')} TL
        WHERE TL.PW_ID = ?
          AND TL.[Release] = ?
          AND TL.OrderNo IS NOT NULL
          AND TL.Qu_ID IS NOT NULL
        """
        cursor = self.conn.cursor()
        cursor.execute(query, pw_id, release)

        mapping: Dict[str, str] = {}
        for row in cursor.fetchall():
            order_no = str(row.OrderNo).strip()
            node_id = str(row.NodeID).strip()
            if order_no and node_id and order_no not in mapping:
                mapping[order_no] = node_id
        return mapping

    def _build_question_text_map(self, release: str) -> Dict[str, str]:
        """Map question/node IDs to question text for a specific release."""
        query = f"""
        SELECT DISTINCT
            TQ.QuID,
            TQ.QuestionText
        FROM {self._table('PWR_TxQuestions')} TQ
        WHERE TQ.[Release] = ?
          AND TQ.QuID IS NOT NULL
        """
        cursor = self.conn.cursor()
        cursor.execute(query, release)

        mapping: Dict[str, str] = {}
        for row in cursor.fetchall():
            question_id = str(row.QuID).strip()
            question_text = row.QuestionText
            if question_id and question_text and question_id not in mapping:
                mapping[question_id] = question_text
        return mapping

    def _build_disposition_text_map(self, release: str) -> Dict[str, str]:
        """Map disposition codes to their display text for a release."""
        query = f"""
        SELECT DISTINCT
            D.DispoCode,
            D.DispoText
        FROM {self._table('PWR_Dispositions')} D
        WHERE D.[Release] = ?
          AND D.DispoCode IS NOT NULL
        """
        cursor = self.conn.cursor()
        cursor.execute(query, release)

        return {
            str(row.DispoCode).strip(): row.DispoText
            for row in cursor.fetchall()
            if row.DispoCode is not None
        }
    
    def connect(self) -> bool:
        """Establish connection to SQL Server"""
        connection_strings = [self.connection_string]
        
        for i, conn_str in enumerate(connection_strings, 1):
            try:
                print(f"🔍 Attempting connection {i}: {conn_str}")
                self.conn = pyodbc.connect(conn_str)
                print("✅ Connected to SQL Server")
                print(f"✅ Using database: {self.database}")
                return True
            except Exception as e:
                print(f"❌ Connection {i} failed: {e}")
                continue
                
        print("❌ All connection attempts failed")
        return False
    
    def get_pathway_questions(self, pw_id: str) -> List[Dict]:
        """Get all questions for a specific pathway"""
        query = f"""
        SELECT DISTINCT
            TQ.QuID QuestionID,
            TQ.QuestionText,
            TQ.Qu_Rationale,
            TQ.ControlType
        FROM {self._table('PWR_TxQuestions')} TQ
        INNER JOIN {self._table('PWR_TriageLogic')} TL ON TQ.QuID = TL.QuID
        WHERE TL.PW_ID = ?
        ORDER BY TQ.QuID
        """
        
        cursor = self.conn.cursor()
        cursor.execute(query, pw_id)
        
        questions = []
        for row in cursor.fetchall():
            questions.append({
                'QuestionID': row.QuestionID,
                'QuestionText': row.QuestionText,
                'QuRationale': row.Qu_Rationale,
                'ControlType': row.ControlType,
                'PathwayID': pw_id
            })
        
        return questions
    
    def get_question_answers(self, qu_id: str, pathway_id: str) -> List[Dict]:
        """Get only answers that have triage logic for this pathway"""
        query = f"""
        SELECT DISTINCT
            TA.QuestionID,
            TA.AnswerNumber,
            TA.AnswerText,
            TA.AnswerRationale
        FROM {self._table('PWR_TxAnswers')} TA
        INNER JOIN {self._table('PWR_TriageLogic')} TL ON TA.QuestionID = TL.QuestionID 
            AND TA.AnswerNumber = TL.AnswerNumber
        WHERE TA.QuestionID = ? AND TL.PathwayID = ?
        ORDER BY TA.AnswerNumber
        """
        
        cursor = self.conn.cursor()
        cursor.execute(query, qu_id, pathway_id)
        
        answers = []
        for row in cursor.fetchall():
            answers.append({
                'QuestionID': row.QuestionID,
                'AnswerNumber': row.AnswerNumber,
                'AnswerText': row.AnswerText,
                'AnswerRationale': row.AnswerRationale
            })
        
        return answers
    
    def get_triage_logic(self, qu_id: str, answer_no: int) -> List[Dict]:
        """Get triage logic for a specific question-answer combination"""
        query = f"""
        SELECT 
            TL.QuestionID,
            TL.AnswerNumber,
            TL.JumpID,
            TL.PathwayID,
            TL.T1,
            TL.T2,
            TL.T3,
            TL.T4,
            TL.Rank
        FROM {self._table('PWR_TriageLogic')} TL
        WHERE TL.QuestionID = ? AND TL.AnswerNumber = ?
        """
        
        cursor = self.conn.cursor()
        cursor.execute(query, qu_id, answer_no)
        
        logic = []
        for row in cursor.fetchall():
            logic.append({
                'QuestionID': row.QuestionID,
                'AnswerNumber': row.AnswerNumber,
                'JumpID': row.JumpID,
                'PathwayID': row.PathwayID,
                'T1': row.T1,
                'T2': row.T2,
                'T3': row.T3,
                'T4': row.T4,
                'Rank': row.Rank
            })
        
        return logic
    
    def expand_transfer_jumps(
        self,
        from_node: str,
        from_question_text: Optional[str],
        answer_text: str,
        t1: Optional[str],
        t2: Optional[str],
        t3: Optional[str],
        t4: Optional[str],
        answer_rationale: Optional[str] = None,
        from_question_rationale: Optional[str] = None,
        disposition_text_by_id: Optional[Dict[str, str]] = None,
    ) -> List[PathwayEdge]:
        """Expand a terminal JumpID into one edge per skillset (T1–T4).

        The to_node is the disposition value from the matching T column:
        - values starting with 'Dx' are diagnoses
        - values starting with 'PW' are pathway redirects
        - anything else (or NULL) falls back to a generic Transfer label
        """
        skillset_t_values = [("T1", t1), ("T2", t2), ("T3", t3), ("T4", t4)]

        edges = []
        for skillset_code, t_value in skillset_t_values:
            if t_value:
                t_value = t_value.strip()
                if t_value.startswith("Dx"):
                    to_node_type = "Dx"
                elif t_value.startswith("PW") or t_value.startswith("PA"):
                    to_node_type = "Pathway"
                else:
                    to_node_type = "Transfer"
                to_node = t_value
            else:
                to_node = f"Transfer_{skillset_code}"
                to_node_type = "Transfer"

            edge = PathwayEdge(
                from_node=from_node,
                from_question_text=from_question_text,
                to_node=to_node,
                to_node_id=to_node,
                to_node_type=to_node_type,
                to_question_text=None,
                answer_text=answer_text,
                jump_type="Transfer",
                answer_rationale=answer_rationale,
                from_question_rationale=from_question_rationale,
                dispo_text=(disposition_text_by_id or {}).get(to_node),
                skillset=skillset_code,
            )
            edges.append(edge)

        return edges
    
    def extract_pathway_dag(self, pw_id: str, version: Optional[str] = None) -> List[PathwayEdge]:
        """Extract complete DAG for a specific pathway and version."""
        print(f"🔍 Extracting DAG for pathway PW_ID: {pw_id}")
        
        edges = []
        cursor = self.conn.cursor()
        
        if version is None:
            version_query = f"""
            SELECT MAX([Version])
            FROM {self._table('PWR_Pathways')}
            WHERE PW_ID = ?
            """
            cursor.execute(version_query, pw_id)
            version_row = cursor.fetchone()
            if not version_row or version_row[0] is None:
                print(f"⚠️  No version found for pathway: {pw_id}")
                return edges
            version = str(version_row[0])
        else:
            version = str(version)

        print(f"Using version: {version}")

        # Get max release for the max version from pathways for the given PW_ID
        release_query = f"""
        SELECT MAX([Release])
        FROM {self._table('PWR_Pathways')} PW
        WHERE PW.PW_ID = ?
        AND PW.[Version] = ?
        """
        cursor.execute(release_query, pw_id, version)
        release_row = cursor.fetchone()
        if not release_row or release_row[0] is None:
            print(f"⚠️  No release found for pathway: {pw_id}")
            return edges

        release = release_row[0]
        print(f"Using release: {release}")

        # Resolve numeric JumpID order numbers into stable node IDs.
        order_to_node_id = self._build_order_to_node_id_map(pw_id, release)
        question_text_by_id = self._build_question_text_map(release)
        disposition_text_by_id = self._build_disposition_text_map(release)
        
        # Get triage logic with question text for from- and to-nodes so the
        # output is self-contained (no further DB lookups needed).
        query = f"""
        SELECT DISTINCT
            TL.Qu_ID             AS QuestionID,
            TQ_From.QuestionText AS QuestionText,
            TQ_From.Qu_Rationale AS QuRationale,
            TL.AnswerNo          AS AnswerNumber,
            TA.AnswerText,
            TA.AnswerRationale,
            TL.JumpID,
            TQ_To.QuestionText   AS JumpQuestionText,
            TL.T1,
            TL.T2,
            TL.T3,
            TL.T4,
            TL.PW_ID             AS PathwayID
        FROM {self._table('PWR_TriageLogic')} TL
        LEFT JOIN {self._table('PWR_TxAnswers')} TA
            ON  TL.Qu_ID    = TA.QuID
            AND TL.AnswerNo = TA.AnswerNo
        LEFT JOIN {self._table('PWR_TxQuestions')} TQ_From
            ON  TQ_From.QuID      = TL.Qu_ID
            AND TQ_From.[Release] = TL.[Release]
        LEFT JOIN {self._table('PWR_TxQuestions')} TQ_To
            ON  TQ_To.QuID      = TL.JumpID
            AND TQ_To.[Release] = TL.[Release]
        WHERE TL.PW_ID    = ?
          AND TL.[Release] = ?
        ORDER BY TL.Qu_ID, TL.AnswerNo
        """

        cursor.execute(query, pw_id, release)
        
        logic_entries = cursor.fetchall()
        print(f"Found {len(logic_entries)} triage logic entries for pathway")
        
        for logic in logic_entries:
            qu_id = logic.QuestionID
            question_text = logic.QuestionText
            question_rationale = logic.QuRationale
            answer_no = logic.AnswerNumber
            answer_text = logic.AnswerText
            answer_rationale = logic.AnswerRationale
            jump_id = logic.JumpID
            jump_question_text = logic.JumpQuestionText
            t1, t2, t3, t4 = logic.T1, logic.T2, logic.T3, logic.T4

            from_node = f"{qu_id}.{answer_no}"

            # Determine whether JumpID is a terminal (negative) or a forward jump.
            try:
                jump_id_int = int(jump_id) if jump_id is not None else None
            except (ValueError, TypeError):
                jump_id_int = None

            if jump_id_int is not None and jump_id_int < 0:
                # Terminal row — resolve each skillset disposition from T1-T4.
                transfer_edges = self.expand_transfer_jumps(
                    from_node, question_text, answer_text, t1, t2, t3, t4,
                    answer_rationale, question_rationale, disposition_text_by_id
                )
                edges.extend(transfer_edges)
            else:
                # Forward jump — JumpID is the target question/node ID.
                to_node = str(jump_id) if jump_id is not None else "Unknown"
                to_node_id = to_node

                if jump_id_int is not None and jump_id_int >= 0:
                    # Many pathways store JumpID as OrderNo; resolve to Tx/Cx node ID.
                    to_node_id = order_to_node_id.get(str(jump_id_int), to_node)

                if jump_question_text is not None:
                    # DB confirmed a matching question exists.
                    to_node_type = "Tx"
                elif to_node_id and self._classify_node_type(to_node_id) != "Unknown":
                    to_node_type = self._classify_node_type(to_node_id)
                elif jump_id_int is not None:
                    # Numeric JumpID without a matching question row — still
                    # treat as a question-node reference.
                    to_node_type = "Tx"
                else:
                    to_node_type = "Unknown"

                resolved_to_question_text = jump_question_text
                if (
                    resolved_to_question_text is None
                    and to_node_type in {"Tx", "Cx"}
                    and to_node_id is not None
                ):
                    resolved_to_question_text = question_text_by_id.get(str(to_node_id).strip())

                edge = PathwayEdge(
                    from_node=from_node,
                    from_question_text=question_text,
                    to_node=to_node,
                    to_node_id=to_node_id,
                    to_node_type=to_node_type,
                    to_question_text=resolved_to_question_text,
                    answer_text=answer_text,
                    jump_type="Jump",
                    answer_rationale=answer_rationale,
                    from_question_rationale=question_rationale,
                    dispo_text=disposition_text_by_id.get(str(to_node_id).strip()),
                )
                edges.append(edge)
        
        print(f"✅ Extracted {len(edges)} edges from pathway")
        return edges
    
    def save_edges_as_js(self, edges: List[PathwayEdge], filename: str = "pathway_edges.js"):
        """Save edges as JavaScript array for HTML visualization"""
        js_edges = []
        for edge in edges:
            js_edge = {
                "from": edge.from_node,
                "from_question_text": edge.from_question_text,
                "to": edge.to_node,
                "to_node_id": edge.to_node_id,
                "to_node_type": edge.to_node_type,
                "to_question_text": edge.to_question_text,
                "answer_text": edge.answer_text,
                "answer_rationale": edge.answer_rationale,
                "from_question_rationale": edge.from_question_rationale,
                "dispo_text": edge.dispo_text,
                "jump_type": edge.jump_type,
            }
            if edge.skillset:
                js_edge["skillset"] = edge.skillset
            js_edges.append(js_edge)
        
        js_content = f"const edges = {json.dumps(js_edges, indent=2)};"
        
        with open(filename, 'w') as f:
            f.write(js_content)
        
        print(f"💾 Saved JavaScript edges to {filename}")
    
    def save_edges_as_json(self, edges: List[PathwayEdge], filename: str = "pathway_edges.json"):
        """Save edges as JSON for data processing"""
        json_edges = [asdict(edge) for edge in edges]
        
        with open(filename, 'w') as f:
            json.dump(json_edges, f, indent=2)
        
        print(f"💾 Saved JSON edges to {filename}")
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()


def main():
    """Main execution function"""
    # Load local .env values before reading environment variables.
    env_candidates = [
        Path(__file__).resolve().parents[1] / ".env",
        Path.cwd() / ".env",
    ]
    for env_path in env_candidates:
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
                    # Keep shell-provided env vars as highest priority.
                    os.environ.setdefault(key, value)

    if len(sys.argv) not in (2, 3, 4):
        print("Usage: python extract_pathway_dag.py <PW_ID> [SCHEMA_NAME] [VERSION_LIST]")
        print("Example (latest version): python extract_pathway_dag.py P2 dbo")
        print("Example (specific versions): python extract_pathway_dag.py P2 dbo 1,2,3")
        sys.exit(1)
    
    pw_id = sys.argv[1]  # PathwayID is a string in this database
    schema_name = sys.argv[2] if len(sys.argv) >= 3 else os.getenv("SQL_SCHEMA", "dbo")
    version_list_arg = sys.argv[3] if len(sys.argv) >= 4 else None
    requested_versions = None
    if version_list_arg:
        requested_versions = [v.strip() for v in version_list_arg.split(",") if v.strip()]
        if not requested_versions:
            print("Error: VERSION_LIST was provided but no valid versions were found")
            sys.exit(1)
    # output_version is no longer used for filename; version will be fetched from DB

    sql_connection_string = os.getenv("SQL_CONNECTION_STRING")
    sql_server = os.getenv("SQL_SERVER", "localhost")
    sql_port = int(os.getenv("SQL_PORT", "1433"))
    sql_database = os.getenv("SQL_DATABASE", "TriageDB")
    sql_username = os.getenv("SQL_USERNAME")
    sql_password = os.getenv("SQL_PASSWORD")
    sql_encrypt = os.getenv("SQL_ENCRYPT", "yes")
    sql_trust_server_certificate = os.getenv("SQL_TRUST_SERVER_CERTIFICATE", "yes")
    sql_login_timeout = int(os.getenv("SQL_LOGIN_TIMEOUT", "30"))

    if (sql_username and not sql_password) or (sql_password and not sql_username):
        print("Error: set both SQL_USERNAME and SQL_PASSWORD for SQL authentication, or leave both unset for Trusted_Connection")
        sys.exit(1)

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

    def _safe_suffix(value: str) -> str:
        """Allow only filename-safe characters for generated output names."""
        cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", value.strip())
        return cleaned or "unknown"

    safe_pw_id = _safe_suffix(pw_id)
    
    try:
        versions_to_process = requested_versions
        if not versions_to_process:
            cursor = extractor.conn.cursor()
            version_query = f"""
            SELECT MAX([Version])
            FROM {extractor._table('PWR_Pathways')}
            WHERE PW_ID = ?
            """
            cursor.execute(version_query, pw_id)
            version_row = cursor.fetchone()
            if not version_row or version_row[0] is None:
                print(f"⚠️  No version found for pathway: {pw_id}")
                return
            versions_to_process = [str(version_row[0])]

        for version in versions_to_process:
            safe_version = _safe_suffix(str(version))
            js_filename = f"{safe_pw_id}_pathway_edges_{safe_version}.js"
            json_filename = f"{safe_pw_id}_pathway_edges_{safe_version}.json"

            edges = extractor.extract_pathway_dag(pw_id, version)

            if not edges:
                print(f"⚠️  No edges found for pathway {pw_id} at version {version}")
                continue

            # Save outputs
            extractor.save_edges_as_js(edges, js_filename)
            extractor.save_edges_as_json(edges, json_filename)

            print(f"\n📊 Summary:")
            print(f"  Pathway ID: {pw_id}")
            print(f"  Version: {version}")
            print(f"  Total edges: {len(edges)}")
            print(f"  Transfer edges: {len([e for e in edges if e.jump_type == 'Transfer'])}")
            print(f"  Question edges: {len([e for e in edges if e.jump_type != 'Transfer'])}")

    except Exception as e:
        print(f"❌ Error extracting pathway: {e}")
    finally:
        extractor.close()


if __name__ == "__main__":
    main()