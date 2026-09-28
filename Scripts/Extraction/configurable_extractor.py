#!/usr/bin/env python3
"""
Configurable Triage Pathway DAG Extractor

Uses pathway_config.json to map database tables and extract pathway structure
as a directed acyclic graph (DAG) for visualization and analysis.
"""

import pyodbc
import json
import sys
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class PathwayEdge:
    """Represents an edge in the pathway DAG"""
    from_node: str
    to_node: str
    answer_text: str
    jump_type: str
    skillset: Optional[str] = None
    probability_weight: Optional[float] = None
    # Enhanced labels for visualization
    from_label: Optional[str] = None  # e.g., "Is patient breathing?"
    to_label: Optional[str] = None    # e.g., "Call ambulance" or next question text
    answer_number: Optional[int] = None


class ConfigurablePathwayExtractor:
    """Extracts pathway DAG using configurable table mappings"""
    
    def __init__(self, config_file: str = "config/pathway_config.json",
                 server: str = "127.0.0.1", username: str = "SA",
                 password: str = "YourStrong!Passw0rd"):
        self.config = self._load_config(config_file)
        self.server = server
        self.username = username
        self.password = password
        self.database = self.config["database_schema"]["name"]
        self.conn = None
        
        # Extract table mappings for easier access
        self.tables = self.config["table_mappings"]
        self.settings = self.config["extraction_settings"]
        self.probability_config = self.config["probability_inference"]
    
    def _load_config(self, config_file: str) -> Dict:
        """Load configuration from JSON file"""
        config_path = Path(config_file)
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_file}")
        
        with open(config_path, 'r') as f:
            return json.load(f)
    
    def connect(self) -> bool:
        """Establish connection to SQL Server"""
        connection_strings = [
            f"DRIVER={{ODBC Driver 18 for SQL Server}};SERVER={self.server},1433;UID={self.username};PWD={self.password};Encrypt=yes;TrustServerCertificate=yes;LoginTimeout=30",
            f"DRIVER={{ODBC Driver 18 for SQL Server}};SERVER={self.server};PORT=1433;UID={self.username};PWD={self.password};Encrypt=yes;TrustServerCertificate=yes;LoginTimeout=30",
            f"DRIVER={{ODBC Driver 18 for SQL Server}};SERVER={self.server}\\1433;UID={self.username};PWD={self.password};Encrypt=yes;TrustServerCertificate=yes;LoginTimeout=30",
        ]
        
        for i, conn_str in enumerate(connection_strings, 1):
            try:
                print(f"🔍 Attempting connection {i}")
                self.conn = pyodbc.connect(conn_str)
                print("✅ Connected to SQL Server")
                
                # Change to the target database
                cursor = self.conn.cursor()
                cursor.execute(f"USE [{self.database}]")
                print(f"✅ Changed to database: {self.database}")
                return True
            except Exception as e:
                print(f"❌ Connection {i} failed: {e}")
                continue
                
        print("❌ All connection attempts failed")
        return False
    
    def validate_schema(self) -> bool:
        """Validate that required tables and columns exist"""
        print("🔍 Validating database schema...")
        
        cursor = self.conn.cursor()
        
        for table_key, table_config in self.tables.items():
            table_name = table_config["table_name"]
            
            # Skip optional tables if they don't exist
            if table_config.get("optional", False):
                try:
                    cursor.execute(f"SELECT TOP 1 * FROM {table_name}")
                    print(f"✅ Optional table {table_name} exists")
                except:
                    print(f"⚠️  Optional table {table_name} not found - skipping")
                    continue
            
            # Check required tables
            try:
                cursor.execute(f"SELECT TOP 1 * FROM {table_name}")
                print(f"✅ Required table {table_name} exists")
                
                # Check columns exist
                columns = table_config["columns"]
                for col_key, col_name in columns.items():
                    try:
                        cursor.execute(f"SELECT TOP 1 {col_name} FROM {table_name}")
                        print(f"   ✅ Column {col_name} exists")
                    except Exception as e:
                        print(f"   ❌ Column {col_name} missing: {e}")
                        return False
                        
            except Exception as e:
                print(f"❌ Required table {table_name} not found: {e}")
                return False
        
        print("✅ Schema validation completed successfully")
        return True
    
    def get_pathway_questions(self, pw_id: str) -> List[Dict]:
        """Get all questions for a specific pathway using configured table names"""
        questions_table = self.tables["questions"]["table_name"]
        logic_table = self.tables["triage_logic"]["table_name"]
        
        question_cols = self.tables["questions"]["columns"]
        logic_cols = self.tables["triage_logic"]["columns"]
        
        query = f"""
        SELECT DISTINCT
            TQ.{question_cols['question_id']},
            TQ.{question_cols['question_text']},
            TQ.{question_cols['control_type']}
        FROM {questions_table} TQ
        INNER JOIN {logic_table} TL ON TQ.{question_cols['question_id']} = TL.{logic_cols['question_id']}
        WHERE TL.{logic_cols['pathway_id']} = ?
        ORDER BY TQ.{question_cols['question_id']}
        """
        
        cursor = self.conn.cursor()
        cursor.execute(query, pw_id)
        
        questions = []
        for row in cursor.fetchall():
            questions.append({
                'QuestionID': getattr(row, question_cols['question_id']),
                'QuestionText': getattr(row, question_cols['question_text']),
                'ControlType': getattr(row, question_cols['control_type']),
                'PathwayID': pw_id
            })
        
        return questions

    def _build_question_text_lookup(self, pw_id: str) -> Dict[str, str]:
        """Build a lookup dictionary of question_id -> question_text"""
        questions_table = self.tables["questions"]["table_name"]
        logic_table = self.tables["triage_logic"]["table_name"]

        question_cols = self.tables["questions"]["columns"]
        logic_cols = self.tables["triage_logic"]["columns"]

        query = f"""
        SELECT DISTINCT
            TQ.{question_cols['question_id']},
            TQ.{question_cols['question_text']}
        FROM {questions_table} TQ
        INNER JOIN {logic_table} TL ON TQ.{question_cols['question_id']} = TL.{logic_cols['question_id']}
        WHERE TL.{logic_cols['pathway_id']} = ?
        """

        cursor = self.conn.cursor()
        cursor.execute(query, pw_id)

        lookup = {}
        for row in cursor.fetchall():
            qu_id = getattr(row, question_cols['question_id'])
            qu_text = getattr(row, question_cols['question_text'])
            lookup[qu_id] = qu_text

        return lookup

    def _build_orderno_lookup(self, pw_id: str) -> Dict[str, tuple]:
        """Build a lookup dictionary of OrderNo -> (QuestionID/DispositionID, text, is_disposition)

        This allows us to resolve JumpIDs (which reference OrderNo) to actual questions OR inline dispositions
        """
        logic_table = self.tables["triage_logic"]["table_name"]
        questions_table = self.tables["questions"]["table_name"]
        logic_cols = self.tables["triage_logic"]["columns"]
        question_cols = self.tables["questions"]["columns"]

        # Check if dispositions table is configured
        if "diagnoses" in self.tables:
            diagnoses_table = self.tables["diagnoses"]["table_name"]
            diag_cols = self.tables["diagnoses"]["columns"]

            # Query that checks both questions AND dispositions (for inline dispositions)
            query = f"""
            SELECT DISTINCT
                TL.{logic_cols['order_no']},
                TL.{logic_cols['question_id']},
                COALESCE(TQ.{question_cols['question_text']}, DD.{diag_cols['diagnosis_text']}) as text,
                CASE WHEN DD.{diag_cols['diagnosis_id']} IS NOT NULL THEN 1 ELSE 0 END as is_disposition,
                DD.{diag_cols['diagnosis_code']}
            FROM {logic_table} TL
            LEFT JOIN {questions_table} TQ ON TL.{logic_cols['question_id']} = TQ.{question_cols['question_id']}
            LEFT JOIN {diagnoses_table} DD ON TL.{logic_cols['question_id']} = DD.{diag_cols['diagnosis_id']}
            WHERE TL.{logic_cols['pathway_id']} = ?
            """
        else:
            # Fallback to questions only
            query = f"""
            SELECT DISTINCT
                TL.{logic_cols['order_no']},
                TL.{logic_cols['question_id']},
                TQ.{question_cols['question_text']} as text,
                0 as is_disposition,
                NULL as DispositionCode
            FROM {logic_table} TL
            INNER JOIN {questions_table} TQ ON TL.{logic_cols['question_id']} = TQ.{question_cols['question_id']}
            WHERE TL.{logic_cols['pathway_id']} = ?
            """

        cursor = self.conn.cursor()
        try:
            cursor.execute(query, pw_id)

            lookup = {}
            disposition_count = 0
            for row in cursor.fetchall():
                order_no = str(getattr(row, logic_cols['order_no']))
                node_id = getattr(row, logic_cols['question_id'])
                text = row.text
                is_disp = row.is_disposition

                if is_disp:
                    disposition_count += 1
                    # For inline dispositions, use DispositionCode (which already has Dx prefix)
                    if hasattr(row, 'DispositionCode') and row.DispositionCode:
                        disp_code = row.DispositionCode
                    else:
                        # Fallback to using node_id directly
                        disp_code = node_id if node_id.startswith('Dx') else f"Dx{node_id}"
                    lookup[order_no] = (disp_code, text, True)
                else:
                    lookup[order_no] = (node_id, text, False)

            print(f"✅ Built OrderNo lookup with {len(lookup)} entries ({disposition_count} inline dispositions)")
            # DEBUG: Print first few entries
            if lookup:
                sample = list(lookup.items())[:3]
                for order_no, (node_id, text, is_disp) in sample:
                    node_type = "Disposition" if is_disp else "Question"
                    print(f"   OrderNo {order_no} → {node_id} ({node_type}): {text[:40]}...")
            return lookup
        except Exception as e:
            print(f"⚠️  Could not build OrderNo lookup: {e}")
            return {}

    def _build_disposition_lookup(self, pw_id: str) -> Dict[str, tuple]:
        """Build a lookup dictionary of JumpID -> (disposition_code, disposition_text)

        Returns a dict mapping JumpID (as string) to tuple of (code, text)

        This works by JOIN'ing the triage logic with dispositions WHERE JumpID matches DispositionID
        """
        if "diagnoses" not in self.tables:
            print("⚠️  No diagnoses table configured - JumpIDs will not be resolved to Dx codes")
            return {}

        diagnoses_table = self.tables["diagnoses"]["table_name"]
        logic_table = self.tables["triage_logic"]["table_name"]
        diag_cols = self.tables["diagnoses"]["columns"]
        logic_cols = self.tables["triage_logic"]["columns"]

        # Join triage logic with dispositions to find which JumpIDs are actually dispositions
        query = f"""
        SELECT DISTINCT
            TL.{logic_cols['jump_id']},
            DD.{diag_cols['diagnosis_code']},
            DD.{diag_cols['diagnosis_text']}
        FROM {logic_table} TL
        INNER JOIN {diagnoses_table} DD ON TL.{logic_cols['jump_id']} = DD.{diag_cols['diagnosis_id']}
        WHERE TL.{logic_cols['pathway_id']} = ?
        """

        cursor = self.conn.cursor()
        try:
            cursor.execute(query, pw_id)

            lookup = {}
            for row in cursor.fetchall():
                jump_id = str(getattr(row, logic_cols['jump_id']))
                disp_code = getattr(row, diag_cols['diagnosis_code'])
                disp_text = getattr(row, diag_cols['diagnosis_text'])
                lookup[jump_id] = (disp_code, disp_text)

            print(f"✅ Built disposition lookup with {len(lookup)} entries (JumpIDs that are dispositions)")
            # DEBUG: Print first few entries
            if lookup:
                sample = list(lookup.items())[:3]
                for jump_id, (code, text) in sample:
                    print(f"   JumpID {jump_id} → {code}: {text[:40]}...")
            return lookup
        except Exception as e:
            print(f"⚠️  Could not build disposition lookup: {e}")
            return {}

    def extract_pathway_dag(self, pw_id: str) -> List[PathwayEdge]:
        """Extract complete DAG for a specific pathway using configuration"""
        print(f"🔍 Extracting DAG for pathway: {pw_id}")

        # Build lookups for questions, dispositions, and orderno mapping
        question_texts = self._build_question_text_lookup(pw_id)
        disposition_lookup = self._build_disposition_lookup(pw_id)
        orderno_lookup = self._build_orderno_lookup(pw_id)

        logic_table = self.tables["triage_logic"]["table_name"]
        answers_table = self.tables["answers"]["table_name"]
        questions_table = self.tables["questions"]["table_name"]

        logic_cols = self.tables["triage_logic"]["columns"]
        answer_cols = self.tables["answers"]["columns"]
        question_cols = self.tables["questions"]["columns"]

        query = f"""
        SELECT DISTINCT
            TL.{logic_cols['question_id']},
            TL.{logic_cols['answer_number']},
            TA.{answer_cols['answer_text']},
            TL.{logic_cols['jump_id']},
            TL.{logic_cols['pathway_id']},
            TQ.{question_cols['question_text']}
        FROM {logic_table} TL
        INNER JOIN {answers_table} TA ON TL.{logic_cols['question_id']} = TA.{answer_cols['question_id']}
            AND TL.{logic_cols['answer_number']} = TA.{answer_cols['answer_number']}
        INNER JOIN {questions_table} TQ ON TL.{logic_cols['question_id']} = TQ.{question_cols['question_id']}
        WHERE TL.{logic_cols['pathway_id']} = ?
        ORDER BY TL.{logic_cols['question_id']}, TL.{logic_cols['answer_number']}
        """

        cursor = self.conn.cursor()
        cursor.execute(query, pw_id)

        logic_entries = cursor.fetchall()
        print(f"Found {len(logic_entries)} triage logic entries for pathway")
        
        edges = []
        
        for logic in logic_entries:
            qu_id = getattr(logic, logic_cols['question_id'])
            answer_no = getattr(logic, logic_cols['answer_number'])
            answer_text = getattr(logic, answer_cols['answer_text'])
            jump_id = getattr(logic, logic_cols['jump_id'])
            question_text = getattr(logic, question_cols['question_text'])

            from_node = f"{qu_id}.{answer_no}"
            from_label = f"{qu_id}: {question_text[:60]}..."  # Truncate long questions

            # Calculate probability weight based on clinical intent
            prob_weight = self._calculate_probability_weight(answer_no, qu_id)

            if jump_id == self.settings["transfer_jump_id"]:
                # Expand into transfer edges
                transfer_edges = self._expand_transfer_jumps(
                    from_node, answer_text, prob_weight,
                    from_label=from_label, answer_number=answer_no
                )
                edges.extend(transfer_edges)
            else:
                # Resolve JumpID using OrderNo lookup
                jump_id_str = str(jump_id)

                # Check if JumpID > 0 (positive = OrderNo reference)
                if jump_id > 0 and jump_id_str in orderno_lookup:
                    # This is a jump to another question or inline disposition via OrderNo
                    target_node_id, target_text, is_disposition = orderno_lookup[jump_id_str]
                    to_node = target_node_id
                    to_label = f"{target_node_id}: {target_text[:60]}..."
                    jump_type = "Disposition" if is_disposition else "Jump"
                elif jump_id_str in disposition_lookup:
                    # This is a disposition/diagnosis outcome (unlikely with current schema)
                    disp_code, disp_text = disposition_lookup[jump_id_str]
                    to_node = f"Dx{disp_code}"
                    to_label = f"{disp_code}: {disp_text[:60]}..."
                    jump_type = "Disposition"
                else:
                    # Special JumpID codes (-2 to -9) or unresolved
                    to_node = f"Special_{jump_id}"
                    to_label = f"Special Jump Code: {jump_id}"
                    jump_type = "Special"

                edge = PathwayEdge(
                    from_node=from_node,
                    to_node=to_node,
                    answer_text=answer_text,
                    jump_type=jump_type,
                    probability_weight=prob_weight,
                    from_label=from_label,
                    to_label=to_label,
                    answer_number=answer_no
                )
                edges.append(edge)
        
        print(f"✅ Extracted {len(edges)} edges from pathway")
        return edges
    
    def _calculate_probability_weight(self, answer_no: int, question_id: str) -> float:
        """Calculate probability weight based on clinical intent patterns"""
        # Answer position weighting (lower numbers = higher severity/probability)
        if self.probability_config["answer_severity_weighting"]["method"] == "inverse_position":
            # Assume max 4 answers per question (adjust as needed)
            max_answers = 4
            position_weight = 1.0 - (answer_no - 1) / max_answers
        else:
            position_weight = 0.5  # Default neutral weight
        
        # Question depth confidence (could be enhanced with actual depth analysis)
        depth_weight = self.probability_config["question_depth_confidence"]["early_questions_weight"]
        
        # Combine weights
        final_weight = (position_weight * 0.7) + (depth_weight * 0.3)
        return round(final_weight, 3)
    
    def _expand_transfer_jumps(self, from_node: str, answer_text: str, prob_weight: float,
                               from_label: str = None, answer_number: int = None) -> List[PathwayEdge]:
        """Expand transfer jumps into skillset-specific edges with probability weights"""
        edges = []

        for skillset_code, skillset_name in self.settings["skillset_mappings"].items():
            to_node = f"Transfer_{skillset_code}_{skillset_name}"
            to_label = f"Transfer: {skillset_name}"

            # Use configured urgency priors for transfer probability weights
            transfer_prob = self.probability_config["transfer_urgency_priors"].get(skillset_code, 0.5)
            combined_prob = (prob_weight + transfer_prob) / 2  # Average clinical and transfer weights

            edge = PathwayEdge(
                from_node=from_node,
                to_node=to_node,
                answer_text=answer_text,
                jump_type="Transfer",
                skillset=skillset_code,
                probability_weight=round(combined_prob, 3),
                from_label=from_label,
                to_label=to_label,
                answer_number=answer_number
            )
            edges.append(edge)

        return edges
    
    def save_edges_with_probabilities(self, edges: List[PathwayEdge],
                                    js_filename: str = "visualization/pathway_edges.js",
                                    json_filename: str = "visualization/pathway_edges.json"):
        """Save edges with probability weights for both visualization and analysis"""

        # Prepare data with probability information and enhanced labels
        enhanced_edges = []
        for edge in edges:
            edge_dict = {
                "from": edge.from_node,  # HTML expects "from" not "from_node"
                "to": edge.to_node,      # HTML expects "to" not "to_node"
                "answer_text": edge.answer_text,
                "jump_type": edge.jump_type,
                "probability_weight": edge.probability_weight,
                "from_label": edge.from_label,
                "to_label": edge.to_label,
                "answer_number": edge.answer_number
            }
            if edge.skillset:
                edge_dict["skillset"] = edge.skillset
            enhanced_edges.append(edge_dict)

        # Save as JavaScript for visualization
        js_content = f"const edges = {json.dumps(enhanced_edges, indent=2)};"
        with open(js_filename, 'w') as f:
            f.write(js_content)

        # Save as JSON for data processing
        json_edges = [asdict(edge) for edge in edges]
        with open(json_filename, 'w') as f:
            json.dump(json_edges, f, indent=2)

        print(f"💾 Saved enhanced edges to {js_filename} and {json_filename}")
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()


def main():
    """Main execution function"""
    if len(sys.argv) != 2:
        print("Usage: python configurable_extractor.py <PATHWAY_ID>")
        print("Example: python configurable_extractor.py 1")
        sys.exit(1)
    
    pw_id = sys.argv[1]
    
    try:
        extractor = ConfigurablePathwayExtractor()
        
        if not extractor.connect():
            sys.exit(1)
        
        if not extractor.validate_schema():
            print("❌ Schema validation failed. Please check your pathway_config.json")
            sys.exit(1)
        
        # Extract DAG with probabilities
        edges = extractor.extract_pathway_dag(pw_id)
        
        if not edges:
            print("⚠️  No edges found for this pathway")
            return
        
        # Save enhanced outputs
        extractor.save_edges_with_probabilities(edges)
        
        # Summary with probability statistics
        prob_weights = [e.probability_weight for e in edges if e.probability_weight]
        avg_prob = sum(prob_weights) / len(prob_weights) if prob_weights else 0
        
        print(f"\n📊 Enhanced Summary:")
        print(f"  Pathway ID: {pw_id}")
        print(f"  Total edges: {len(edges)}")
        print(f"  Transfer edges: {len([e for e in edges if e.jump_type == 'Transfer'])}")
        print(f"  Question edges: {len([e for e in edges if e.jump_type != 'Transfer'])}")
        print(f"  Average probability weight: {avg_prob:.3f}")
        print(f"  Min probability: {min(prob_weights):.3f}")
        print(f"  Max probability: {max(prob_weights):.3f}")
        
    except Exception as e:
        print(f"❌ Error extracting pathway: {e}")
    finally:
        if 'extractor' in locals():
            extractor.close()


if __name__ == "__main__":
    main()