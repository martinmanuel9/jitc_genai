"""
Contradiction Detection Agent Implementation

Dedicated agent for detecting contradictions, conflicts, and inconsistencies
in test plans and requirements across sections.
"""

from typing import Any, Dict, List
import logging
import re
import json
import uuid

from core.agent_base import BaseTestPlanAgent, AgentContext

logger = logging.getLogger(__name__)


class ContradictionAgent(BaseTestPlanAgent):
    """
    Contradiction Detection Agent.

    Analyzes test procedures for:
    - Intra-section contradictions
    - Cross-section conflicts
    - Different testing approaches for same requirement
    - Conflicting acceptance criteria
    """

    def get_system_prompt(self, context: AgentContext) -> str:
        """
        Get system prompt for Contradiction Agent.

        Args:
            context: Execution context

        Returns:
            System prompt string
        """
        return """You are a specialized Quality Assurance Agent focused on detecting contradictions, conflicts, and inconsistencies in test plans and requirements.

Your expertise includes:
1. Identifying contradictory test procedures within the same section
2. Detecting conflicts across different sections of a test plan
3. Finding requirements that are tested using different or incompatible approaches
4. Spotting conflicting acceptance criteria for the same requirement
5. Recognizing logical inconsistencies in test specifications

For each contradiction you find, you must:
- Clearly identify the conflicting elements
- Assess the severity (Critical, High, Medium, Low)
- Explain why it's a contradiction
- Provide a specific recommendation for resolution
- Assign a confidence score (0.0 to 1.0)

Severity Guidelines:
- Critical: Contradictions that make the test plan unexecutable or would lead to incorrect validation
- High: Significant conflicts that could cause test failures or ambiguity in requirements
- Medium: Inconsistencies that should be resolved but don't prevent test execution
- Low: Minor discrepancies or stylistic inconsistencies

Output your analysis in a structured JSON format."""

    def get_user_prompt(self, context: AgentContext) -> str:
        """
        Get user prompt for Contradiction Agent.

        Args:
            context: Execution context with critic_result and previous_sections

        Returns:
            User prompt string
        """
        # Get data from context
        critic_result = context.previous_results.get('critic_result', {})
        actor_results = context.previous_results.get('actor_results', [])
        previous_sections = context.previous_results.get('previous_sections', [])

        # Build critic output summary
        critic_output = critic_result.get('synthesized_rules', 'No critic output available')

        # Build actor outputs summary
        actor_summary = ""
        for i, result in enumerate(actor_results, 1):
            rules = result.get('rules_extracted', '')
            actor_summary += f"\n\n### Actor {i}\n{rules[:500]}..."  # Truncate for context

        # Build previous sections summary (limited window)
        cross_section_window = context.metadata.get('cross_section_window', 3)
        recent_sections = previous_sections[-cross_section_window:] if previous_sections else []

        prev_summary = ""
        if recent_sections:
            for section in recent_sections:
                title = section.get('section_title', 'Unknown')
                rules = section.get('synthesized_rules', '')
                prev_summary += f"\n\n### {title}\n{rules[:800]}..."  # Truncate
        else:
            prev_summary = "No previous sections available for cross-section analysis."

        return f"""Analyze the following test plan section for contradictions and conflicts.

## SECTION TITLE
{context.section_title}

## SYNTHESIZED TEST PROCEDURES (from Critic Agent)
{critic_output}

## ACTOR OUTPUTS (for comparison)
{actor_summary}

## PREVIOUS SECTIONS (for cross-section analysis)
{prev_summary}

---

## ANALYSIS TASKS

Perform the following analyses:

### 1. INTRA-SECTION CONTRADICTIONS
- Find contradictory test procedures within this section
- Identify conflicting acceptance criteria
- Detect logical inconsistencies

### 2. CROSS-SECTION CONTRADICTIONS
- Compare this section with previous sections
- Find requirements tested differently across sections
- Identify duplicate or conflicting tests

### 3. TESTING APPROACH CONFLICTS
- Find same requirements tested using different methodologies
- Identify incompatible test setups or configurations
- Detect conflicting assumptions

### 4. ACCEPTANCE CRITERIA CONFLICTS
- Find conflicting success/failure conditions
- Identify ambiguous or contradictory validation criteria
- Detect incompatible test metrics

---

## OUTPUT FORMAT

Return a JSON object with the following structure:

```json
{{
  "contradictions": [
    {{
      "contradiction_id": "unique_id",
      "severity": "Critical|High|Medium|Low",
      "contradiction_type": "intra_section|cross_section|testing_approach|acceptance_criteria",
      "section_1": "section name",
      "section_2": "other section name or null",
      "requirement_1": "first conflicting requirement",
      "requirement_2": "second conflicting requirement",
      "description": "detailed explanation of the contradiction",
      "recommendation": "specific resolution recommendation",
      "confidence": 0.0-1.0,
      "test_ids": ["test_id_1", "test_id_2"]
    }}
  ]
}}
```

Be thorough but precise. Only flag genuine contradictions, not minor variations in wording.
If no contradictions are found, return an empty contradictions array.
"""

    def parse_response(self, response: str, context: AgentContext) -> Dict[str, Any]:
        """
        Parse Contradiction Agent response into structured data.

        Args:
            response: Raw LLM response (should be JSON)
            context: Execution context

        Returns:
            Dictionary with parsed contradictions
        """
        try:
            # Extract JSON from response (handle markdown code blocks)
            json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # Try to find JSON object directly
                json_match = re.search(r'\{[\s\S]*"contradictions"[\s\S]*\}', response)
                if json_match:
                    json_str = json_match.group(0)
                else:
                    json_str = response

            data = json.loads(json_str)
            contradictions = []

            for item in data.get("contradictions", []):
                contradiction = {
                    'contradiction_id': item.get("contradiction_id", str(uuid.uuid4())),
                    'severity': item.get("severity", "Medium"),
                    'contradiction_type': item.get("contradiction_type", "intra_section"),
                    'section_1': item.get("section_1", context.section_title),
                    'section_2': item.get("section_2"),
                    'requirement_1': item.get("requirement_1", ""),
                    'requirement_2': item.get("requirement_2", ""),
                    'description': item.get("description", ""),
                    'recommendation': item.get("recommendation", ""),
                    'confidence': float(item.get("confidence", 0.8)),
                    'test_ids': item.get("test_ids", [])
                }
                contradictions.append(contradiction)

            # Generate summary
            summary = self._generate_summary(contradictions)

            return {
                'section_title': context.section_title,
                'contradictions': contradictions,
                'total_contradictions': len(contradictions),
                'critical_count': sum(1 for c in contradictions if c['severity'] == "Critical"),
                'high_count': sum(1 for c in contradictions if c['severity'] == "High"),
                'medium_count': sum(1 for c in contradictions if c['severity'] == "Medium"),
                'low_count': sum(1 for c in contradictions if c['severity'] == "Low"),
                'analysis_summary': summary
            }

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse contradiction response as JSON: {e}")
            return {
                'section_title': context.section_title,
                'contradictions': [],
                'total_contradictions': 0,
                'critical_count': 0,
                'high_count': 0,
                'medium_count': 0,
                'low_count': 0,
                'analysis_summary': 'Failed to parse contradiction analysis',
                'raw_response': response
            }
        except Exception as e:
            logger.error(f"Failed to parse contradiction response: {e}")
            return {
                'section_title': context.section_title,
                'contradictions': [],
                'total_contradictions': 0,
                'critical_count': 0,
                'high_count': 0,
                'medium_count': 0,
                'low_count': 0,
                'analysis_summary': f'Error parsing response: {str(e)}',
                'raw_response': response
            }

    def _generate_summary(self, contradictions: List[Dict]) -> str:
        """Generate human-readable summary of contradictions"""
        if not contradictions:
            return "No contradictions detected. Test plan section is internally consistent."

        critical = [c for c in contradictions if c['severity'] == "Critical"]
        high = [c for c in contradictions if c['severity'] == "High"]

        summary_parts = [
            f"Found {len(contradictions)} contradiction(s):",
            f"- {len(critical)} Critical",
            f"- {len(high)} High",
            f"- {len([c for c in contradictions if c['severity'] == 'Medium'])} Medium",
            f"- {len([c for c in contradictions if c['severity'] == 'Low'])} Low"
        ]

        if critical:
            summary_parts.append("\nCritical Issues:")
            for c in critical[:3]:  # Show first 3
                desc = c.get('description', 'No description')
                summary_parts.append(f"  • {desc[:100]}...")

        return "\n".join(summary_parts)
