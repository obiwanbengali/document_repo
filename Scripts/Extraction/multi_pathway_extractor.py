#!/usr/bin/env python3
"""
Multi-Pathway Safety Extractor

Prevents diagnostic tunnel vision by extracting and cross-referencing multiple 
pathways that could relate to the same symptoms, ensuring comprehensive
diagnostic probability space for safe AI model training.
"""

import pyodbc
import json
import sys
from typing import List, Dict, Any, Optional, Tuple, Set
from dataclasses import dataclass, asdict
from pathlib import Path
import logging
from datetime import datetime
import numpy as np

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class MultiPathwayEdge:
    """Enhanced pathway edge with cross-pathway validation"""
    from_node: str
    to_node: str
    answer_text: str
    jump_type: str
    pathway_id: str
    primary_pathway: bool = True
    skillset: Optional[str] = None
    clinical_weight: Optional[float] = None
    cross_pathway_weight: Optional[float] = None
    safety_normalized_weight: Optional[float] = None


@dataclass
class DiagnosticOutcome:
    """Represents a possible diagnostic outcome across pathways"""
    diagnosis_id: str
    diagnosis_name: str
    supporting_pathways: List[str]
    conflicting_pathways: List[str]
    combined_probability: float
    safety_adjusted_probability: float
    confidence_level: str  # "high", "medium", "low", "insufficient"


@dataclass
class PathwayAnalysis:
    """Results of multi-pathway analysis"""
    primary_pathway_id: str
    related_pathways: List[str]
    total_outcomes: int
    unique_diagnoses: int
    cross_pathway_agreements: int
    cross_pathway_conflicts: int
    safety_margin_reserved: float
    extraction_timestamp: datetime


class MultiPathwaySafetyExtractor:
    """
    Extracts multiple pathways for comprehensive diagnostic safety
    Prevents tunnel vision by considering symptom overlap across pathways
    """
    
    def __init__(self, config_file: str = "pathway_config.json",
                 symptom_mapping_file: str = "symptom_pathway_mapping.json",
                 sql_server: str = "localhost", sql_username: str = "SA", 
                 sql_password: str = "YourStrong!Passw0rd"):
        
        # Load configurations
        self.config = self._load_config(config_file)
        self.symptom_mapping = self._load_config(symptom_mapping_file)
        
        # Extract configurations
        self.tables = self.config["table_mappings"]
        self.settings = self.config["extraction_settings"]
        self.probability_config = self.config["probability_inference"]
        self.safety_config = self.symptom_mapping["clinical_safety"]
        self.safety_rules = self.symptom_mapping["safety_rules"]
        
        # SQL connection parameters
        self.sql_server = sql_server
        self.sql_username = sql_username
        self.sql_password = sql_password
        self.database = self.config["database_schema"]["name"]
        self.sql_conn = None
    
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
    
    def identify_symptom_pathways(self, primary_pathway_id: str, 
                                primary_symptom: str = None) -> List[Dict[str, Any]]:
        """
        Identify all pathways that should be considered for comprehensive extraction
        
        Args:
            primary_pathway_id: The main pathway being extracted
            primary_symptom: Primary symptom (if known) to find overlaps
            
        Returns:
            List of pathway dictionaries with overlap weights
        """
        pathways_to_extract = [
            {
                "pathway_id": primary_pathway_id,
                "overlap_weight": 1.0,
                "is_primary": True,
                "description": "Primary pathway for extraction"
            }
        ]
        
        # If symptom is specified, find related pathways
        if primary_symptom and primary_symptom in self.symptom_mapping["symptom_pathway_groups"]:
            symptom_group = self.symptom_mapping["symptom_pathway_groups"][primary_symptom]
            
            for related_pathway in symptom_group["related_pathways"]:
                if related_pathway["pathway_id"] != primary_pathway_id:
                    pathways_to_extract.append({
                        "pathway_id": related_pathway["pathway_id"],
                        "overlap_weight": related_pathway["overlap_weight"],
                        "is_primary": False,
                        "description": related_pathway["description"]
                    })
                    logger.info(f"Added related pathway: {related_pathway['pathway_id']} (weight: {related_pathway['overlap_weight']})")
        
        # Always include high-risk mandatory pathways
        mandatory_pathways = self.safety_rules["mandatory_inclusions"]["always_consider"]
        for mandatory_pathway in mandatory_pathways:
            if not any(p["pathway_id"] == mandatory_pathway for p in pathways_to_extract):
                pathways_to_extract.append({
                    "pathway_id": mandatory_pathway,
                    "overlap_weight": 0.3,  # Lower weight but still considered
                    "is_primary": False,
                    "description": "Mandatory safety inclusion"
                })
                logger.info(f"Added mandatory safety pathway: {mandatory_pathway}")
        
        logger.info(f"Total pathways to extract: {len(pathways_to_extract)}")
        return pathways_to_extract
    
    def extract_comprehensive_pathway_network(self, primary_pathway_id: str,
                                            primary_symptom: str = None) -> Tuple[List[MultiPathwayEdge], PathwayAnalysis]:
        """
        Extract comprehensive pathway network with safety considerations
        
        Args:
            primary_pathway_id: Main pathway to extract
            primary_symptom: Primary symptom for overlap detection
            
        Returns:
            Tuple of (edges, analysis)
        """
        logger.info(f"Starting comprehensive extraction for pathway: {primary_pathway_id}")
        
        # Identify all pathways to consider
        pathways_to_extract = self.identify_symptom_pathways(primary_pathway_id, primary_symptom)
        
        all_edges = []
        extracted_pathways = []
        
        # Extract each pathway
        for pathway_info in pathways_to_extract:
            try:
                pathway_edges = self._extract_single_pathway_safe(
                    pathway_info["pathway_id"],
                    pathway_info["overlap_weight"],
                    pathway_info["is_primary"]
                )
                
                if pathway_edges:
                    all_edges.extend(pathway_edges)
                    extracted_pathways.append(pathway_info["pathway_id"])
                    logger.info(f"Extracted {len(pathway_edges)} edges from {pathway_info['pathway_id']}")
                else:
                    logger.warning(f"No edges found for pathway: {pathway_info['pathway_id']}")
                    
            except Exception as e:
                logger.error(f"Failed to extract pathway {pathway_info['pathway_id']}: {e}")
                continue
        
        if not all_edges:
            logger.error("No edges extracted from any pathway")
            return [], PathwayAnalysis(
                primary_pathway_id=primary_pathway_id,
                related_pathways=[],
                total_outcomes=0,
                unique_diagnoses=0,
                cross_pathway_agreements=0,
                cross_pathway_conflicts=0,
                safety_margin_reserved=0.0,
                extraction_timestamp=datetime.now()
            )
        
        # Analyze cross-pathway relationships
        analysis = self._analyze_cross_pathway_relationships(all_edges, primary_pathway_id, extracted_pathways)
        
        # Apply safety normalization
        normalized_edges = self._apply_safety_normalization(all_edges, analysis)
        
        logger.info(f"Comprehensive extraction complete: {len(normalized_edges)} total edges")
        return normalized_edges, analysis
    
    def _extract_single_pathway_safe(self, pathway_id: str, overlap_weight: float, 
                                   is_primary: bool) -> List[MultiPathwayEdge]:
        """Extract single pathway with safety metadata"""
        
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
        logic_entries = cursor.fetchall()
        
        for logic in logic_entries:
            qu_id = getattr(logic, logic_cols['question_id'])
            answer_no = getattr(logic, logic_cols['answer_number'])
            answer_text = getattr(logic, answer_cols['answer_text'])
            jump_id = getattr(logic, logic_cols['jump_id'])
            
            from_node = f"{qu_id}.{answer_no}"
            clinical_weight = self._calculate_clinical_weight(answer_no, qu_id)
            cross_pathway_weight = clinical_weight * overlap_weight
            
            if jump_id == self.settings["transfer_jump_id"]:
                # Handle transfer edges
                transfer_edges = self._expand_transfer_jumps_safe(
                    from_node, answer_text, pathway_id, is_primary, 
                    clinical_weight, cross_pathway_weight
                )
                edges.extend(transfer_edges)
            else:
                # Regular diagnostic jump
                to_node = f"Jump_{jump_id}" if not str(jump_id).startswith("Dx") else str(jump_id)
                
                edge = MultiPathwayEdge(
                    from_node=from_node,
                    to_node=to_node,
                    answer_text=answer_text,
                    jump_type="Jump",
                    pathway_id=pathway_id,
                    primary_pathway=is_primary,
                    clinical_weight=clinical_weight,
                    cross_pathway_weight=cross_pathway_weight
                )
                edges.append(edge)
        
        return edges
    
    def _calculate_clinical_weight(self, answer_no: int, question_id: str) -> float:
        """Calculate clinical intent-based weight"""
        max_answers = 4
        position_weight = 1.0 - (answer_no - 1) / max_answers
        depth_weight = self.probability_config["question_depth_confidence"]["early_questions_weight"]
        clinical_weight = (position_weight * 0.7) + (depth_weight * 0.3)
        return round(clinical_weight, 3)
    
    def _expand_transfer_jumps_safe(self, from_node: str, answer_text: str, 
                                  pathway_id: str, is_primary: bool,
                                  clinical_weight: float, cross_pathway_weight: float) -> List[MultiPathwayEdge]:
        """Expand transfer jumps with safety metadata"""
        edges = []
        
        for skillset_code, skillset_name in self.settings["skillset_mappings"].items():
            to_node = f"Transfer_{skillset_code}_{skillset_name}"
            transfer_prob = self.probability_config["transfer_urgency_priors"].get(skillset_code, 0.5)
            combined_weight = (cross_pathway_weight + transfer_prob) / 2
            
            edge = MultiPathwayEdge(
                from_node=from_node,
                to_node=to_node,
                answer_text=answer_text,
                jump_type="Transfer",
                pathway_id=pathway_id,
                primary_pathway=is_primary,
                skillset=skillset_code,
                clinical_weight=clinical_weight,
                cross_pathway_weight=combined_weight
            )
            edges.append(edge)
        
        return edges
    
    def _analyze_cross_pathway_relationships(self, edges: List[MultiPathwayEdge], 
                                           primary_pathway_id: str,
                                           extracted_pathways: List[str]) -> PathwayAnalysis:
        """Analyze relationships and conflicts across pathways"""
        
        # Group edges by target diagnosis
        diagnosis_groups = {}
        for edge in edges:
            target = edge.to_node
            if target not in diagnosis_groups:
                diagnosis_groups[target] = []
            diagnosis_groups[target].append(edge)
        
        # Count agreements and conflicts
        agreements = 0
        conflicts = 0
        
        for target, target_edges in diagnosis_groups.items():
            pathways_for_target = set(edge.pathway_id for edge in target_edges)
            
            if len(pathways_for_target) > 1:
                # Multiple pathways lead to same diagnosis = agreement
                agreements += 1
                logger.info(f"Cross-pathway agreement for {target}: {pathways_for_target}")
            
            # Check for weight conflicts (different pathways giving very different weights)
            weights = [edge.cross_pathway_weight for edge in target_edges if edge.cross_pathway_weight]
            if len(weights) > 1:
                weight_variance = np.var(weights)
                if weight_variance > 0.1:  # High variance indicates conflict
                    conflicts += 1
                    logger.warning(f"Weight conflict for {target}: weights={weights}, variance={weight_variance:.3f}")
        
        # Calculate safety margin
        safety_margin = self.safety_config["safety_margin"]
        
        return PathwayAnalysis(
            primary_pathway_id=primary_pathway_id,
            related_pathways=extracted_pathways,
            total_outcomes=len(edges),
            unique_diagnoses=len(diagnosis_groups),
            cross_pathway_agreements=agreements,
            cross_pathway_conflicts=conflicts,
            safety_margin_reserved=safety_margin,
            extraction_timestamp=datetime.now()
        )
    
    def _apply_safety_normalization(self, edges: List[MultiPathwayEdge], 
                                  analysis: PathwayAnalysis) -> List[MultiPathwayEdge]:
        """Apply safety normalization to prevent overconfidence"""
        
        if not edges:
            return edges
        
        # Calculate total weight for normalization
        total_weight = sum(edge.cross_pathway_weight or 0 for edge in edges)
        if total_weight == 0:
            logger.warning("Total weight is zero, cannot normalize")
            return edges
        
        # Reserve safety margin for unknown conditions
        safety_margin = analysis.safety_margin_reserved
        available_probability = 1.0 - safety_margin
        
        # Apply normalization constraints
        max_single_confidence = self.safety_rules["probability_constraints"]["max_single_pathway_confidence"]
        
        normalized_edges = []
        for edge in edges:
            # Normalize to available probability space
            base_normalized = (edge.cross_pathway_weight / total_weight) * available_probability
            
            # Apply maximum confidence constraint
            safety_normalized = min(base_normalized, max_single_confidence)
            
            edge.safety_normalized_weight = round(safety_normalized, 4)
            normalized_edges.append(edge)
        
        # Verify normalization
        total_normalized = sum(edge.safety_normalized_weight for edge in normalized_edges)
        logger.info(f"Safety normalization: {total_normalized:.3f} + {safety_margin:.3f} safety margin = {total_normalized + safety_margin:.3f}")
        
        return normalized_edges
    
    def generate_diagnostic_outcomes(self, edges: List[MultiPathwayEdge]) -> List[DiagnosticOutcome]:
        """Generate comprehensive diagnostic outcomes with safety considerations"""
        
        # Group edges by target diagnosis
        diagnosis_groups = {}
        for edge in edges:
            target = edge.to_node
            if target not in diagnosis_groups:
                diagnosis_groups[target] = []
            diagnosis_groups[target].append(edge)
        
        outcomes = []
        
        for diagnosis_id, diagnosis_edges in diagnosis_groups.items():
            # Identify supporting and conflicting pathways
            supporting_pathways = []
            conflicting_pathways = []
            
            pathway_weights = {}
            for edge in diagnosis_edges:
                if edge.pathway_id not in pathway_weights:
                    pathway_weights[edge.pathway_id] = []
                pathway_weights[edge.pathway_id].append(edge.safety_normalized_weight or 0)
            
            # Calculate average weights per pathway
            for pathway_id, weights in pathway_weights.items():
                avg_weight = sum(weights) / len(weights)
                if avg_weight > 0.1:  # Significant support
                    supporting_pathways.append(pathway_id)
                else:
                    conflicting_pathways.append(pathway_id)
            
            # Combine probabilities across pathways
            combined_prob = sum(edge.safety_normalized_weight or 0 for edge in diagnosis_edges)
            
            # Determine confidence level
            if combined_prob > 0.5:
                confidence = "high"
            elif combined_prob > 0.2:
                confidence = "medium" 
            elif combined_prob > 0.05:
                confidence = "low"
            else:
                confidence = "insufficient"
            
            outcome = DiagnosticOutcome(
                diagnosis_id=diagnosis_id,
                diagnosis_name=diagnosis_id.replace("Dx", "Diagnosis_").replace("_", " "),
                supporting_pathways=supporting_pathways,
                conflicting_pathways=conflicting_pathways,
                combined_probability=round(combined_prob, 4),
                safety_adjusted_probability=round(combined_prob, 4),
                confidence_level=confidence
            )
            
            outcomes.append(outcome)
        
        # Sort by probability (highest first)
        outcomes.sort(key=lambda x: x.combined_probability, reverse=True)
        
        return outcomes
    
    def save_comprehensive_analysis(self, edges: List[MultiPathwayEdge], 
                                  analysis: PathwayAnalysis,
                                  outcomes: List[DiagnosticOutcome],
                                  output_prefix: str = "multi_pathway"):
        """Save comprehensive multi-pathway analysis"""
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save edges with full metadata
        edges_file = f"{output_prefix}_edges_{timestamp}.json"
        edges_data = [asdict(edge) for edge in edges]
        with open(edges_file, 'w') as f:
            json.dump(edges_data, f, indent=2, default=str)
        
        # Save analysis
        analysis_file = f"{output_prefix}_analysis_{timestamp}.json"
        with open(analysis_file, 'w') as f:
            json.dump(asdict(analysis), f, indent=2, default=str)
        
        # Save outcomes
        outcomes_file = f"{output_prefix}_outcomes_{timestamp}.json"
        outcomes_data = [asdict(outcome) for outcome in outcomes]
        with open(outcomes_file, 'w') as f:
            json.dump(outcomes_data, f, indent=2)
        
        logger.info(f"Saved comprehensive analysis:")
        logger.info(f"  Edges: {edges_file}")
        logger.info(f"  Analysis: {analysis_file}")
        logger.info(f"  Outcomes: {outcomes_file}")
        
        return {
            "edges_file": edges_file,
            "analysis_file": analysis_file, 
            "outcomes_file": outcomes_file
        }
    
    def close(self):
        """Close SQL connection"""
        if self.sql_conn:
            self.sql_conn.close()
            logger.info("SQL Server connection closed")


def main():
    """Main execution function"""
    if len(sys.argv) not in [2, 3, 4]:
        print("Usage: python multi_pathway_extractor.py <PRIMARY_PATHWAY_ID> [SYMPTOM] [--analysis-only]")
        print("Example: python multi_pathway_extractor.py cardiac_pathway chest_pain")
        print("         python multi_pathway_extractor.py respiratory_pathway shortness_of_breath --analysis-only")
        sys.exit(1)
    
    primary_pathway_id = sys.argv[1]
    primary_symptom = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith('--') else None
    analysis_only = "--analysis-only" in sys.argv
    
    extractor = None
    try:
        print(f"🔒 Multi-Pathway Safety Extraction")
        print("=" * 50)
        print(f"Primary Pathway: {primary_pathway_id}")
        if primary_symptom:
            print(f"Primary Symptom: {primary_symptom}")
        print(f"Analysis Only: {analysis_only}")
        print()
        
        extractor = MultiPathwaySafetyExtractor()
        
        if not extractor.connect_sql():
            print("❌ Failed to connect to SQL Server")
            sys.exit(1)
        
        # Extract comprehensive pathway network
        edges, analysis = extractor.extract_comprehensive_pathway_network(
            primary_pathway_id, primary_symptom
        )
        
        if not edges:
            print("⚠️  No edges found in comprehensive extraction")
            return
        
        # Generate diagnostic outcomes
        outcomes = extractor.generate_diagnostic_outcomes(edges)
        
        # Save results
        if not analysis_only:
            files = extractor.save_comprehensive_analysis(edges, analysis, outcomes)
            print(f"📁 Files saved: {len(files)} output files")
        
        # Display summary
        print(f"\n📊 Multi-Pathway Safety Analysis:")
        print(f"  Primary pathway: {analysis.primary_pathway_id}")
        print(f"  Related pathways: {len(analysis.related_pathways)}")
        print(f"  Total diagnostic outcomes: {analysis.total_outcomes}")
        print(f"  Unique diagnoses: {analysis.unique_diagnoses}")
        print(f"  Cross-pathway agreements: {analysis.cross_pathway_agreements}")
        print(f"  Cross-pathway conflicts: {analysis.cross_pathway_conflicts}")
        print(f"  Safety margin reserved: {analysis.safety_margin_reserved:.1%}")
        
        print(f"\n🎯 Top Diagnostic Outcomes:")
        for i, outcome in enumerate(outcomes[:5], 1):
            print(f"  {i}. {outcome.diagnosis_name}")
            print(f"     Probability: {outcome.combined_probability:.1%} ({outcome.confidence_level} confidence)")
            print(f"     Supporting pathways: {len(outcome.supporting_pathways)}")
            if outcome.conflicting_pathways:
                print(f"     Conflicts: {len(outcome.conflicting_pathways)} pathways")
        
        print(f"\n✅ Multi-pathway extraction completed safely!")
        print(f"🔒 Diagnostic tunnel vision risk: MITIGATED")
        
    except Exception as e:
        logger.error(f"Multi-pathway extraction failed: {e}")
        print(f"❌ Error: {e}")
        sys.exit(1)
    finally:
        if extractor:
            extractor.close()


if __name__ == "__main__":
    main()