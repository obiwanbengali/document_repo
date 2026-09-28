#!/usr/bin/env python3
"""
Neo4j Pathway Extractor

Extracts pathway data from SQL Server and stores it in Neo4j graph database.
Includes pathway existence checking and automatic removal/re-insertion logic.
"""

import pyodbc
import json
import sys
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
from neo4j import GraphDatabase
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class PathwayEdge:
    """Represents an edge in the pathway DAG"""
    from_node: str
    to_node: str
    answer_text: str
    jump_type: str
    skillset: Optional[str] = None
    probability_weight: Optional[float] = None


@dataclass  
class PathwayQuestion:
    """Represents a pathway question"""
    id: str
    text: str
    control_type: str
    pathway_id: str
    answers: List[Dict[str, Any]]


@dataclass
class PathwayInfo:
    """Represents pathway metadata"""
    id: str
    name: Optional[str] = None
    description: Optional[str] = None
    extracted_at: Optional[datetime] = None
    total_questions: int = 0
    total_edges: int = 0


class Neo4jPathwayStorage:
    """Handles Neo4j database operations for pathway storage"""
    
    def __init__(self, uri: str = "bolt://localhost:7688", 
                 user: str = "neo4j", password: str = "pathway2pass"):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        logger.info(f"Connected to Neo4j at {uri}")
    
    def close(self):
        """Close Neo4j connection"""
        if self.driver:
            self.driver.close()
            logger.info("Neo4j connection closed")
    
    def check_pathway_exists(self, pathway_id: str) -> bool:
        """Check if pathway already exists in Neo4j"""
        with self.driver.session() as session:
            result = session.run(
                "MATCH (p:Pathway {id: $pathway_id}) RETURN count(p) as count",
                pathway_id=pathway_id
            )
            count = result.single()["count"]
            exists = count > 0
            logger.info(f"Pathway {pathway_id} exists: {exists}")
            return exists
    
    def remove_pathway(self, pathway_id: str) -> int:
        """Remove existing pathway and all related nodes/relationships"""
        with self.driver.session() as session:
            # Count nodes before deletion for reporting
            count_result = session.run(
                """
                MATCH (p:Pathway {id: $pathway_id})
                OPTIONAL MATCH (p)-[*]-(related)
                RETURN count(DISTINCT related) + 1 as total_nodes
                """,
                pathway_id=pathway_id
            )
            total_nodes = count_result.single()["total_nodes"] or 0
            
            # Delete pathway and all connected nodes
            session.run(
                """
                MATCH (p:Pathway {id: $pathway_id})
                OPTIONAL MATCH (p)-[*]-(related)
                DETACH DELETE p, related
                """,
                pathway_id=pathway_id
            )
            
            logger.info(f"Removed pathway {pathway_id} and {total_nodes} related nodes")
            return total_nodes
    
    def store_pathway(self, pathway_info: PathwayInfo, questions: List[PathwayQuestion], 
                     edges: List[PathwayEdge]) -> Dict[str, int]:
        """Store complete pathway structure in Neo4j"""
        
        stats = {"pathway": 0, "questions": 0, "answers": 0, "edges": 0, "diagnoses": 0, "transfers": 0}
        
        with self.driver.session() as session:
            # Create pathway node
            session.run(
                """
                CREATE (p:Pathway {
                    id: $id,
                    name: $name,
                    description: $description,
                    extracted_at: $extracted_at,
                    total_questions: $total_questions,
                    total_edges: $total_edges
                })
                """,
                id=pathway_info.id,
                name=pathway_info.name,
                description=pathway_info.description,
                extracted_at=pathway_info.extracted_at.isoformat() if pathway_info.extracted_at else None,
                total_questions=pathway_info.total_questions,
                total_edges=pathway_info.total_edges
            )
            stats["pathway"] = 1
            logger.info(f"Created pathway node: {pathway_info.id}")
            
            # Create question nodes and answers
            for question in questions:
                # Create question node
                session.run(
                    """
                    MATCH (p:Pathway {id: $pathway_id})
                    CREATE (q:Question {
                        id: $id,
                        text: $text,
                        control_type: $control_type,
                        pathway_id: $pathway_id
                    })
                    CREATE (p)-[:HAS_QUESTION]->(q)
                    """,
                    pathway_id=pathway_info.id,
                    id=question.id,
                    text=question.text,
                    control_type=question.control_type
                )
                stats["questions"] += 1
                
                # Create answer nodes
                for answer in question.answers:
                    session.run(
                        """
                        MATCH (q:Question {id: $question_id, pathway_id: $pathway_id})
                        CREATE (a:Answer {
                            question_id: $question_id,
                            number: $number,
                            text: $text,
                            pathway_id: $pathway_id
                        })
                        CREATE (q)-[:HAS_ANSWER]->(a)
                        """,
                        pathway_id=pathway_info.id,
                        question_id=question.id,
                        number=answer["AnswerNumber"],
                        text=answer["AnswerText"]
                    )
                    stats["answers"] += 1
            
            logger.info(f"Created {stats['questions']} questions and {stats['answers']} answers")
            
            # Create edges and target nodes
            for edge in edges:
                # Determine target node type and create if needed
                if edge.to_node.startswith("Dx") or edge.jump_type == "DiagnosisJump":
                    # Create diagnosis node
                    session.run(
                        """
                        MERGE (d:Diagnosis {id: $id})
                        ON CREATE SET d.name = $id, d.type = 'diagnosis'
                        """,
                        id=edge.to_node
                    )
                    stats["diagnoses"] += 1
                    target_label = "Diagnosis"
                    
                elif edge.to_node.startswith("Transfer_") or edge.jump_type == "Transfer":
                    # Create transfer node
                    session.run(
                        """
                        MERGE (t:Transfer {id: $id})
                        ON CREATE SET 
                            t.name = $id, 
                            t.type = 'transfer',
                            t.skillset = $skillset
                        """,
                        id=edge.to_node,
                        skillset=edge.skillset
                    )
                    stats["transfers"] += 1
                    target_label = "Transfer"
                    
                else:
                    # Create generic target node (could be another question)
                    session.run(
                        """
                        MERGE (n:Node {id: $id})
                        ON CREATE SET n.name = $id, n.type = 'node'
                        """,
                        id=edge.to_node
                    )
                    target_label = "Node"
                
                # Create relationship with probability weight
                session.run(
                    f"""
                    MATCH (a:Answer {{question_id: $from_question_id, number: $from_answer_no, pathway_id: $pathway_id}})
                    MATCH (target:{target_label} {{id: $to_node}})
                    CREATE (a)-[:LEADS_TO {{
                        jump_type: $jump_type,
                        probability_weight: $probability_weight,
                        skillset: $skillset
                    }}]->(target)
                    """,
                    pathway_id=pathway_info.id,
                    from_question_id=edge.from_node.split('.')[0],
                    from_answer_no=int(edge.from_node.split('.')[1]),
                    to_node=edge.to_node,
                    jump_type=edge.jump_type,
                    probability_weight=edge.probability_weight,
                    skillset=edge.skillset
                )
                stats["edges"] += 1
            
            logger.info(f"Created {stats['edges']} edges, {stats['diagnoses']} diagnoses, {stats['transfers']} transfers")
            
        return stats


class Neo4jPathwayExtractor:
    """Main extractor class that combines SQL extraction with Neo4j storage"""
    
    def __init__(self, config_file: str = "pathway_config.json",
                 sql_server: str = "localhost", sql_username: str = "SA", 
                 sql_password: str = "YourStrong!Passw0rd",
                 neo4j_uri: str = "bolt://localhost:7688",
                 neo4j_user: str = "neo4j", neo4j_password: str = "pathway2pass"):
        
        # Load configuration
        self.config = self._load_config(config_file)
        self.tables = self.config["table_mappings"]
        self.settings = self.config["extraction_settings"]
        self.probability_config = self.config["probability_inference"]
        
        # SQL Server connection parameters
        self.sql_server = sql_server
        self.sql_username = sql_username
        self.sql_password = sql_password
        self.database = self.config["database_schema"]["name"]
        self.sql_conn = None
        
        # Neo4j storage
        self.neo4j = Neo4jPathwayStorage(neo4j_uri, neo4j_user, neo4j_password)
    
    def _load_config(self, config_file: str) -> Dict:
        """Load configuration from JSON file"""
        config_path = Path(config_file)
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_file}")
        
        with open(config_path, 'r') as f:
            return json.load(f)
    
    def connect_sql(self) -> bool:
        """Connect to SQL Server database"""
        connection_strings = [
            f"DRIVER={{ODBC Driver 18 for SQL Server}};SERVER={self.sql_server},1433;UID={self.sql_username};PWD={self.sql_password};TrustServerCertificate=yes;LoginTimeout=30",
            f"DRIVER={{ODBC Driver 18 for SQL Server}};SERVER={self.sql_server};PORT=1433;UID={self.sql_username};PWD={self.sql_password};TrustServerCertificate=yes;LoginTimeout=30",
        ]
        
        for i, conn_str in enumerate(connection_strings, 1):
            try:
                logger.info(f"Attempting SQL Server connection {i}")
                self.sql_conn = pyodbc.connect(conn_str)
                cursor = self.sql_conn.cursor()
                cursor.execute(f"USE [{self.database}]")
                logger.info(f"Connected to SQL Server database: {self.database}")
                return True
            except Exception as e:
                logger.error(f"SQL connection {i} failed: {e}")
                continue
                
        logger.error("All SQL Server connection attempts failed")
        return False
    
    def extract_and_store_pathway(self, pathway_id: str, force_replace: bool = True) -> Dict[str, Any]:
        """Extract pathway from SQL and store in Neo4j"""
        
        # Check if pathway exists
        if self.neo4j.check_pathway_exists(pathway_id):
            if force_replace:
                logger.info(f"Pathway {pathway_id} exists - removing for replacement")
                removed_count = self.neo4j.remove_pathway(pathway_id)
                logger.info(f"Removed {removed_count} nodes")
            else:
                logger.info(f"Pathway {pathway_id} already exists - skipping")
                return {"status": "skipped", "reason": "already_exists"}
        
        # Extract from SQL Server
        logger.info(f"Extracting pathway {pathway_id} from SQL Server")
        
        # Get pathway questions
        questions = self._get_pathway_questions(pathway_id)
        if not questions:
            logger.error(f"No questions found for pathway {pathway_id}")
            return {"status": "error", "reason": "no_questions_found"}
        
        # Get pathway edges
        edges = self._extract_pathway_dag(pathway_id)
        if not edges:
            logger.error(f"No edges found for pathway {pathway_id}")
            return {"status": "error", "reason": "no_edges_found"}
        
        # Create pathway info
        pathway_info = PathwayInfo(
            id=pathway_id,
            name=f"Pathway_{pathway_id}",
            description=f"Extracted pathway with clinical probability weights",
            extracted_at=datetime.now(),
            total_questions=len(questions),
            total_edges=len(edges)
        )
        
        # Store in Neo4j
        logger.info(f"Storing pathway {pathway_id} in Neo4j")
        stats = self.neo4j.store_pathway(pathway_info, questions, edges)
        
        return {
            "status": "success", 
            "pathway_id": pathway_id,
            "extraction_stats": stats,
            "extracted_at": pathway_info.extracted_at.isoformat()
        }
    
    def _get_pathway_questions(self, pathway_id: str) -> List[PathwayQuestion]:
        """Extract questions for pathway"""
        questions_table = self.tables["questions"]["table_name"]
        answers_table = self.tables["answers"]["table_name"]
        logic_table = self.tables["triage_logic"]["table_name"]
        
        question_cols = self.tables["questions"]["columns"]
        answer_cols = self.tables["answers"]["columns"]
        logic_cols = self.tables["triage_logic"]["columns"]
        
        # Get questions
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
        
        cursor = self.sql_conn.cursor()
        cursor.execute(query, pathway_id)
        
        questions = []
        for row in cursor.fetchall():
            question_id = getattr(row, question_cols['question_id'])
            
            # Get answers for this question
            answer_query = f"""
            SELECT DISTINCT
                TA.{answer_cols['question_id']},
                TA.{answer_cols['answer_number']},
                TA.{answer_cols['answer_text']}
            FROM {answers_table} TA
            INNER JOIN {logic_table} TL ON TA.{answer_cols['question_id']} = TL.{logic_cols['question_id']} 
                AND TA.{answer_cols['answer_number']} = TL.{logic_cols['answer_number']}
            WHERE TA.{answer_cols['question_id']} = ? AND TL.{logic_cols['pathway_id']} = ?
            ORDER BY TA.{answer_cols['answer_number']}
            """
            
            cursor.execute(answer_query, question_id, pathway_id)
            answers = []
            for ans_row in cursor.fetchall():
                answers.append({
                    'QuestionID': getattr(ans_row, answer_cols['question_id']),
                    'AnswerNumber': getattr(ans_row, answer_cols['answer_number']),
                    'AnswerText': getattr(ans_row, answer_cols['answer_text'])
                })
            
            question = PathwayQuestion(
                id=question_id,
                text=getattr(row, question_cols['question_text']),
                control_type=getattr(row, question_cols['control_type']),
                pathway_id=pathway_id,
                answers=answers
            )
            questions.append(question)
        
        logger.info(f"Extracted {len(questions)} questions for pathway {pathway_id}")
        return questions
    
    def _extract_pathway_dag(self, pathway_id: str) -> List[PathwayEdge]:
        """Extract pathway edges with probability weights"""
        logic_table = self.tables["triage_logic"]["table_name"]
        answers_table = self.tables["answers"]["table_name"]
        
        logic_cols = self.tables["triage_logic"]["columns"]
        answer_cols = self.tables["answers"]["columns"]
        
        query = f"""
        SELECT DISTINCT
            TL.{logic_cols['question_id']},
            TL.{logic_cols['answer_number']},
            TA.{answer_cols['answer_text']},
            TL.{logic_cols['jump_id']},
            TL.{logic_cols['pathway_id']}
        FROM {logic_table} TL
        INNER JOIN {answers_table} TA ON TL.{logic_cols['question_id']} = TA.{answer_cols['question_id']} 
            AND TL.{logic_cols['answer_number']} = TA.{answer_cols['answer_number']}
        WHERE TL.{logic_cols['pathway_id']} = ?
        ORDER BY TL.{logic_cols['question_id']}, TL.{logic_cols['answer_number']}
        """
        
        cursor = self.sql_conn.cursor()
        cursor.execute(query, pathway_id)
        
        edges = []
        for logic in cursor.fetchall():
            qu_id = getattr(logic, logic_cols['question_id'])
            answer_no = getattr(logic, logic_cols['answer_number'])
            answer_text = getattr(logic, answer_cols['answer_text'])
            jump_id = getattr(logic, logic_cols['jump_id'])
            
            from_node = f"{qu_id}.{answer_no}"
            prob_weight = self._calculate_probability_weight(answer_no, qu_id)
            
            if jump_id == self.settings["transfer_jump_id"]:
                transfer_edges = self._expand_transfer_jumps(from_node, answer_text, prob_weight)
                edges.extend(transfer_edges)
            else:
                to_node = f"Jump_{jump_id}" if not str(jump_id).startswith("Dx") else str(jump_id)
                
                edge = PathwayEdge(
                    from_node=from_node,
                    to_node=to_node,
                    answer_text=answer_text,
                    jump_type="Jump",
                    probability_weight=prob_weight
                )
                edges.append(edge)
        
        logger.info(f"Extracted {len(edges)} edges for pathway {pathway_id}")
        return edges
    
    def _calculate_probability_weight(self, answer_no: int, question_id: str) -> float:
        """Calculate clinical intent-based probability weight"""
        max_answers = 4
        position_weight = 1.0 - (answer_no - 1) / max_answers
        depth_weight = self.probability_config["question_depth_confidence"]["early_questions_weight"]
        final_weight = (position_weight * 0.7) + (depth_weight * 0.3)
        return round(final_weight, 3)
    
    def _expand_transfer_jumps(self, from_node: str, answer_text: str, prob_weight: float) -> List[PathwayEdge]:
        """Expand transfer jumps with probability weights"""
        edges = []
        for skillset_code, skillset_name in self.settings["skillset_mappings"].items():
            to_node = f"Transfer_{skillset_code}_{skillset_name}"
            transfer_prob = self.probability_config["transfer_urgency_priors"].get(skillset_code, 0.5)
            combined_prob = (prob_weight + transfer_prob) / 2
            
            edge = PathwayEdge(
                from_node=from_node,
                to_node=to_node,
                answer_text=answer_text,
                jump_type="Transfer",
                skillset=skillset_code,
                probability_weight=round(combined_prob, 3)
            )
            edges.append(edge)
        
        return edges
    
    def close(self):
        """Close all connections"""
        if self.sql_conn:
            self.sql_conn.close()
            logger.info("SQL Server connection closed")
        self.neo4j.close()


def main():
    """Main execution function"""
    if len(sys.argv) not in [2, 3]:
        print("Usage: python neo4j_extractor.py <PATHWAY_ID> [--keep-existing]")
        print("Example: python neo4j_extractor.py 1")
        print("         python neo4j_extractor.py 1 --keep-existing")
        sys.exit(1)
    
    pathway_id = sys.argv[1]
    force_replace = "--keep-existing" not in sys.argv
    
    extractor = None
    try:
        print(f"🚀 Starting Neo4j Pathway Extraction for pathway: {pathway_id}")
        print("=" * 60)
        
        extractor = Neo4jPathwayExtractor()
        
        if not extractor.connect_sql():
            print("❌ Failed to connect to SQL Server")
            sys.exit(1)
        
        result = extractor.extract_and_store_pathway(pathway_id, force_replace)
        
        if result["status"] == "success":
            print(f"\n✅ Pathway {pathway_id} successfully stored in Neo4j!")
            print(f"📊 Statistics:")
            for key, value in result["extraction_stats"].items():
                print(f"   {key}: {value}")
            print(f"\n🔗 Access Neo4j Browser: http://localhost:7475")
            print(f"   Username: neo4j")
            print(f"   Password: pathway2pass")
        else:
            print(f"\n❌ Extraction failed: {result.get('reason', 'unknown error')}")
            
    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        print(f"❌ Error: {e}")
    finally:
        if extractor:
            extractor.close()


if __name__ == "__main__":
    main()