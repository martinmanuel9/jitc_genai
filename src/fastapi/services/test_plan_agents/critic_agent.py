"""
Critic Agent Implementation

Synthesizes and deduplicates outputs from multiple Actor agents.
Creates a single, cohesive set of test procedures from multiple perspectives.
"""

from typing import Any, Dict, List
import logging
import re

from core.agent_base import BaseTestPlanAgent, AgentContext

logger = logging.getLogger(__name__)


class CriticAgent(BaseTestPlanAgent):
    """
    Critic Agent for synthesizing actor outputs.

    This agent reviews outputs from multiple Actor agents and:
    - Synthesizes a single, cohesive set of requirements
    - Eliminates redundancies and duplicates
    - Corrects errors and inconsistencies
    - Ensures comprehensive coverage
    """

    def get_system_prompt(self, context: AgentContext) -> str:
        """
        Get system prompt for Critic Agent.

        Args:
            context: Execution context

        Returns:
            System prompt string
        """
        return """You are a senior test planning reviewer with expertise in synthesizing multiple perspectives into cohesive test plans.

Your role is to critically analyze multiple requirement extractions and create a single, authoritative test plan that:
- Captures all unique requirements
- Eliminates redundancies
- Corrects errors or misinterpretations
- Ensures logical organization and completeness"""

    def get_user_prompt(self, context: AgentContext) -> str:
        """
        Get user prompt for Critic Agent.

        Args:
            context: Execution context with actor_results in previous_results

        Returns:
            User prompt string
        """
        # Get actor results from context
        actor_results = context.previous_results.get('actor_results', [])

        if not actor_results:
            return "ERROR: No actor results provided for criticism"

        # Prepare actor outputs
        actor_outputs_text = ""
        for i, result in enumerate(actor_results, 1):
            model_name = result.get('model_name', 'unknown')
            agent_id = result.get('agent_id', 'unknown')
            rules = result.get('rules_extracted', '')
            actor_outputs_text += f"\n\n### Actor {i}: Model {model_name} ({agent_id})\n{rules}\n{'='*40}"

        return f"""You are a senior test planning reviewer (Critic AI) with expertise in military/technical standards compliance testing.

Given the following section and test procedures extracted by multiple AI models, synthesize a SINGLE, comprehensive test plan.

CRITICAL INSTRUCTIONS:
1. PRESERVE ORIGINAL REQUIREMENT IDs from the source document (4.2.1, REQ-01, etc.)
2. Synthesize and deduplicate test procedures - if multiple actors extracted the same requirement, create ONE authoritative test procedure
3. Maintain HIERARCHICAL STRUCTURE (e.g., 4.2.1 → 4.2.1.1 → 4.2.1.2)
4. Generate TEST PROCEDURES (not requirements tables) - each must be executable by an engineer
5. Ensure test procedures include: Objective, Setup, Steps, Expected Results, Pass/Fail Criteria
6. Resolve contradictions between actor outputs by selecting the most detailed/accurate version

DO NOT:
- Create new requirement IDs (use originals from source)
- Simply concatenate all actor outputs (synthesize and deduplicate)
- Generate requirements tables (generate test procedures)
- Include duplicate test procedures

OUTPUT FORMAT - CRITICAL:
Present your result in this exact markdown structure:

## [Section Title]

**Dependencies:**
- List prerequisites, tools, or configurations needed for testing

**Conflicts:**
- List detected conflicts and provide recommendations

**Test Procedures:**

### Test Procedure [Original Req ID] (e.g., 4.2.1 or REQ-01)
**Requirement:** [Exact requirement text from source]

**Test Objective:** [What this test validates]

**Test Setup:**
- [Equipment/configuration needed]
- [Prerequisites]

**Test Steps:**
- [Detailed step with specific actions]
- [Include specific parameters, values, commands]
- [Be explicit - engineer should know exactly what to do]

**Expected Results:** [Specific measurable outcomes with values/ranges]

**Pass/Fail Criteria:** [Explicit thresholds for pass/fail]

---

Section Name: {context.section_title}

Section Text:
{context.section_content}

---

Actor Outputs from {len(actor_results)} AI models:
{actor_outputs_text}

---

TASK: Synthesize these {len(actor_results)} actor outputs into ONE authoritative test plan. Preserve requirement IDs, eliminate duplicates, and ensure each test procedure is complete and executable."""

    def parse_response(self, response: str, context: AgentContext) -> Dict[str, Any]:
        """
        Parse Critic Agent response into structured data.

        Args:
            response: Raw LLM response
            context: Execution context

        Returns:
            Dictionary with parsed data
        """
        # Apply deduplication
        deduplicated_response = self._deduplicate_markdown(response)

        # Extract structured data
        dependencies = self._extract_dependencies(deduplicated_response)
        conflicts = self._extract_conflicts(deduplicated_response)
        test_procedures = self._extract_test_procedures(deduplicated_response)
        test_rules = self._extract_test_rules(deduplicated_response)

        actor_results = context.previous_results.get('actor_results', [])

        return {
            'section_title': context.section_title,
            'synthesized_rules': deduplicated_response,
            'dependencies': dependencies,
            'conflicts': conflicts,
            'test_procedures': test_procedures,
            'test_rules': test_rules,
            'actor_count': len(actor_results)
        }

    def _deduplicate_markdown(self, text: str) -> str:
        """
        Remove duplicate lines from markdown text.

        Args:
            text: Markdown text

        Returns:
            Deduplicated text
        """
        lines = text.split('\n')
        seen = set()
        deduplicated_lines = []

        for line in lines:
            # Normalize line for comparison (lowercase, strip whitespace)
            normalized = line.strip().lower()

            # Skip empty lines or keep headers
            if not normalized or line.strip().startswith('#'):
                deduplicated_lines.append(line)
                continue

            # Check for duplicates
            if normalized not in seen:
                seen.add(normalized)
                deduplicated_lines.append(line)

        return '\n'.join(deduplicated_lines)

    def _extract_dependencies(self, response: str) -> List[str]:
        """Extract dependencies from response"""
        deps = []
        deps_section = re.search(
            r'\*\*Dependencies:\*\*\s*(.*?)(?=\*\*|##|$)',
            response,
            re.DOTALL | re.IGNORECASE
        )
        if deps_section:
            lines = deps_section.group(1).strip().split('\n')
            for line in lines:
                line = line.strip()
                if line and line.startswith('-'):
                    deps.append(line[1:].strip())
        return deps

    def _extract_conflicts(self, response: str) -> List[str]:
        """Extract conflicts from response"""
        conflicts = []
        conflicts_section = re.search(
            r'\*\*Conflicts:\*\*\s*(.*?)(?=\*\*|##|$)',
            response,
            re.DOTALL | re.IGNORECASE
        )
        if conflicts_section:
            lines = conflicts_section.group(1).strip().split('\n')
            for line in lines:
                line = line.strip()
                if line and line.startswith('-'):
                    conflicts.append(line[1:].strip())
        return conflicts

    def _extract_test_procedures(self, response: str) -> List[Dict[str, Any]]:
        """Extract test procedures as structured data"""
        procedures = []
        rules = self._extract_test_rules(response)

        for idx, rule in enumerate(rules, 1):
            procedures.append({
                'test_id': f"TEST-{idx:03d}",
                'description': rule,
                'dependencies': [],
                'conflicts': []
            })

        return procedures

    def _extract_test_rules(self, response: str) -> List[str]:
        """Extract numbered test rules from response"""
        rules = []
        rules_section = re.search(
            r'\*\*Test Rules:\*\*\s*(.*?)(?=---|\*\*|##|\Z)',
            response,
            re.DOTALL | re.IGNORECASE
        )
        if rules_section:
            lines = rules_section.group(1).strip().split('\n')
            for line in lines:
                line = line.strip()
                if line and re.match(r'^\d+\.', line):
                    # Remove the number prefix
                    rule_text = re.sub(r'^\d+\.\s*', '', line)
                    if rule_text:
                        rules.append(rule_text)
        return rules
