"""
JSON-Based Test Plan Service

Converts test plan generation to JSON format for better structure and test card generation.
Each section is represented as a JSON object with proper schema.

JSON Schema:
{
  "test_plan": {
    "metadata": {
      "title": str,
      "pipeline_id": str,
      "doc_title": str,
      "generated_at": str,
      "processing_status": str,
      "total_sections": int,
      "total_requirements": int,
      "total_test_procedures": int,
      "agent_set_id": int,
      "agent_configuration": str
    },
    "sections": [
      {
        "section_id": str,
        "section_title": str,
        "section_index": int,
        "synthesized_rules": str,
        "actor_count": int,
        "dependencies": [str],
        "conflicts": [str],
        "test_procedures": [
          {
            "id": str,
            "requirement_id": str,
            "title": str,
            "objective": str,
            "setup": str,
            "steps": [str],
            "expected_results": str,
            "pass_criteria": str,
            "fail_criteria": str,
            "type": str,
            "priority": str,
            "estimated_duration_minutes": int
          }
        ]
      }
    ]
  }
}
"""

import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import asdict
import uuid

logger = logging.getLogger(__name__)


class JSONTestPlanService:
    """Service for converting test plans to JSON format and vice versa"""

    @staticmethod
    def critic_result_to_json_section(
        critic_result: Any,
        section_index: int,
        section_id: str = None
    ) -> Dict[str, Any]:
        """
        Convert a CriticResult to a JSON section object.
        
        Args:
            critic_result: CriticResult object from multi-agent service
            section_index: Index of the section in the test plan
            section_id: Optional explicit section ID (generated if not provided)
            
        Returns:
            Dictionary representing the JSON section
        """
        if section_id is None:
            section_id = f"section_{uuid.uuid4().hex[:8]}"
        
        return {
            "section_id": section_id,
            "section_title": critic_result.section_title,
            "section_index": section_index,
            "synthesized_rules": critic_result.synthesized_rules,
            "actor_count": critic_result.actor_count,
            "dependencies": critic_result.dependencies or [],
            "conflicts": critic_result.conflicts or [],
            "test_procedures": critic_result.test_procedures or []
        }
    
    @staticmethod
    def final_test_plan_to_json(final_test_plan: Any) -> Dict[str, Any]:
        """
        Convert a FinalTestPlan to complete JSON structure.
        
        Args:
            final_test_plan: FinalTestPlan object from multi-agent service
            
        Returns:
            Complete JSON test plan structure
        """
        sections = []
        for idx, critic_result in enumerate(final_test_plan.sections):
            section = JSONTestPlanService.critic_result_to_json_section(
                critic_result,
                section_index=idx
            )
            sections.append(section)
        
        return {
            "test_plan": {
                "metadata": {
                    "title": final_test_plan.title,
                    "pipeline_id": final_test_plan.pipeline_id,
                    "doc_title": final_test_plan.title,
                    "generated_at": datetime.now().isoformat(),
                    "processing_status": final_test_plan.processing_status,
                    "total_sections": final_test_plan.total_sections,
                    "total_requirements": final_test_plan.total_requirements,
                    "total_test_procedures": final_test_plan.total_test_procedures,
                    "agent_configuration": "multi_agent_gpt4_pipeline"
                },
                "sections": sections
            }
        }
    
    @staticmethod
    def json_to_markdown(json_test_plan: Dict[str, Any]) -> str:
        """
        Convert JSON test plan back to markdown format.
        Useful for document export and display.
        
        Args:
            json_test_plan: Complete JSON test plan structure
            
        Returns:
            Markdown formatted test plan
        """
        metadata = json_test_plan.get("test_plan", {}).get("metadata", {})
        sections = json_test_plan.get("test_plan", {}).get("sections", [])
        
        markdown = f"# {metadata.get('title', 'Test Plan')}\n\n"
        
        # Add metadata section
        markdown += "## Document Metadata\n\n"
        markdown += f"- **Generated**: {metadata.get('generated_at', 'N/A')}\n"
        markdown += f"- **Status**: {metadata.get('processing_status', 'UNKNOWN')}\n"
        markdown += f"- **Total Sections**: {metadata.get('total_sections', 0)}\n"
        markdown += f"- **Total Requirements**: {metadata.get('total_requirements', 0)}\n"
        markdown += f"- **Total Test Procedures**: {metadata.get('total_test_procedures', 0)}\n\n"
        
        # Add sections
        for idx, section in enumerate(sections, 1):
            markdown += f"## {idx}. {section.get('section_title', 'Section')}\n\n"
            
            # Add synthesized rules
            if section.get('synthesized_rules'):
                markdown += "### Requirements\n\n"
                markdown += section.get('synthesized_rules', '') + "\n\n"
            
            # Add test procedures
            test_procedures = section.get('test_procedures', [])
            if test_procedures:
                markdown += "### Test Procedures\n\n"
                for proc_idx, procedure in enumerate(test_procedures, 1):
                    markdown += f"#### Test {section.get('section_index', 0)}.{proc_idx}: {procedure.get('title', 'Test')}\n\n"
                    
                    if procedure.get('requirement_id'):
                        markdown += f"**Requirement ID**: {procedure.get('requirement_id')}\n\n"
                    
                    if procedure.get('objective'):
                        markdown += f"**Objective**: {procedure.get('objective')}\n\n"
                    
                    if procedure.get('setup'):
                        markdown += f"**Setup**:\n{procedure.get('setup')}\n\n"
                    
                    if procedure.get('steps'):
                        markdown += "**Steps**:\n"
                        for step_idx, step in enumerate(procedure.get('steps', []), 1):
                            markdown += f"  {step_idx}. {step}\n"
                        markdown += "\n"
                    
                    if procedure.get('expected_results'):
                        markdown += f"**Expected Results**: {procedure.get('expected_results')}\n\n"
                    
                    if procedure.get('pass_criteria'):
                        markdown += f"**Pass Criteria**: {procedure.get('pass_criteria')}\n\n"
                    
                    markdown += "---\n\n"
            
            # Add dependencies and conflicts
            if section.get('dependencies'):
                markdown += "### Dependencies\n\n"
                for dep in section.get('dependencies', []):
                    markdown += f"- {dep}\n"
                markdown += "\n"
            
            if section.get('conflicts'):
                markdown += "### Conflicts\n\n"
                for conflict in section.get('conflicts', []):
                    markdown += f"- {conflict}\n"
                markdown += "\n"
            
            markdown += "---\n\n"
        
        return markdown
    
    @staticmethod
    def extract_test_cards_from_json(json_test_plan: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract individual test cards from JSON test plan.
        Each test procedure becomes a test card.
        
        Args:
            json_test_plan: Complete JSON test plan structure
            
        Returns:
            List of test card objects
        """
        test_cards = []
        metadata = json_test_plan.get("test_plan", {}).get("metadata", {})
        sections = json_test_plan.get("test_plan", {}).get("sections", [])
        
        for section in sections:
            test_procedures = section.get('test_procedures', [])
            
            for proc_idx, procedure in enumerate(test_procedures, 1):
                test_card = {
                    "document_id": f"testcard_{metadata.get('pipeline_id', 'unknown')}_" + 
                                  f"{section.get('section_id', 'unknown')}_" +
                                  f"{procedure.get('id', f'proc_{proc_idx}')}",
                    "document_name": f"TC-{section.get('section_index', 0)}.{proc_idx}: {procedure.get('title', 'Test')}",
                    "test_id": f"TC-{section.get('section_index', 0)}.{proc_idx}",
                    "test_plan_id": metadata.get('pipeline_id'),
                    "section_id": section.get('section_id'),
                    "section_title": section.get('section_title'),
                    "requirement_id": procedure.get('requirement_id', ''),
                    "title": procedure.get('title', ''),
                    "objective": procedure.get('objective', ''),
                    "setup": procedure.get('setup', ''),
                    "steps": json.dumps(procedure.get('steps', [])),
                    "expected_results": procedure.get('expected_results', ''),
                    "pass_criteria": procedure.get('pass_criteria', ''),
                    "fail_criteria": procedure.get('fail_criteria', ''),
                    "test_type": procedure.get('type', 'functional'),
                    "priority": procedure.get('priority', 'medium'),
                    "estimated_duration_minutes": procedure.get('estimated_duration_minutes', 30),
                    "execution_status": "not_executed",
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat(),
                    "type": "test_card",
                    "format": "json"
                }
                test_cards.append(test_card)
        
        logger.info(f"Extracted {len(test_cards)} test cards from JSON test plan")
        return test_cards
    
    @staticmethod
    def validate_json_test_plan(json_data: Dict[str, Any]) -> tuple[bool, str]:
        """
        Validate JSON test plan structure.
        
        Args:
            json_data: JSON data to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            test_plan = json_data.get("test_plan")
            if not test_plan:
                return False, "Missing 'test_plan' key"
            
            metadata = test_plan.get("metadata")
            if not metadata:
                return False, "Missing 'metadata' in test_plan"
            
            required_metadata = ["title", "pipeline_id", "processing_status"]
            for field in required_metadata:
                if field not in metadata:
                    return False, f"Missing required metadata field: {field}"
            
            sections = test_plan.get("sections", [])
            if not isinstance(sections, list):
                return False, "Sections must be a list"
            
            for idx, section in enumerate(sections):
                if not isinstance(section, dict):
                    return False, f"Section {idx} is not a dictionary"
                
                required_section_fields = ["section_id", "section_title", "test_procedures"]
                for field in required_section_fields:
                    if field not in section:
                        return False, f"Section {idx} missing required field: {field}"
            
            return True, "Valid JSON test plan"
        
        except Exception as e:
            return False, f"Validation error: {str(e)}"
    
    @staticmethod
    def merge_json_sections(*json_test_plans: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge multiple JSON test plans into a single test plan.
        
        Args:
            json_test_plans: Variable number of JSON test plan dictionaries
            
        Returns:
            Merged JSON test plan
        """
        if not json_test_plans:
            raise ValueError("At least one test plan required for merging")
        
        # Use first plan as base
        merged = json.loads(json.dumps(json_test_plans[0]))  # Deep copy
        base_metadata = merged.get("test_plan", {}).get("metadata", {})
        
        # Merge subsequent plans
        for plan in json_test_plans[1:]:
            plan_sections = plan.get("test_plan", {}).get("sections", [])
            merged_sections = merged.get("test_plan", {}).get("sections", [])
            
            # Adjust indices and add sections
            for section in plan_sections:
                section["section_index"] = len(merged_sections)
                merged_sections.append(section)
        
        # Update metadata counts
        if "test_plan" in merged:
            test_plan = merged["test_plan"]
            all_sections = test_plan.get("sections", [])
            test_plan["metadata"]["total_sections"] = len(all_sections)
            
            total_requirements = sum(
                len(s.get("test_procedures", []))
                for s in all_sections
            )
            test_plan["metadata"]["total_requirements"] = total_requirements
            test_plan["metadata"]["total_test_procedures"] = total_requirements
        
        logger.info(f"Merged {len(json_test_plans)} test plans")
        return merged
