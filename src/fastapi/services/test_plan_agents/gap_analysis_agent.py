"""
Gap Analysis Agent Implementation

Identifies requirement gaps and missing test coverage by comparing
the generated test plan against the source standard document.
"""

from typing import Any, Dict, List
import logging
import re
import json
import uuid

from core.agent_base import BaseTestPlanAgent, AgentContext

logger = logging.getLogger(__name__)


class GapAnalysisAgent(BaseTestPlanAgent):
    """
    Gap Analysis Agent.

    Analyzes test plans for:
    - Missing requirements from source standard
    - Incomplete test coverage
    - Untested sections or clauses
    - Implicit requirements that should be explicit
    """

    def get_system_prompt(self, context: AgentContext) -> str:
        """
        Get system prompt for Gap Analysis Agent.

        Args:
            context: Execution context

        Returns:
            System prompt string
        """
        return """You are a specialized Quality Assurance Agent focused on identifying requirement gaps and incomplete test coverage.

Your expertise includes:
1. Comparing generated test plans against source specifications
2. Identifying missing requirements that should be tested
3. Finding untested sections, clauses, or specifications
4. Recognizing implicit requirements that need explicit testing
5. Assessing test coverage completeness

For each gap you find, you must:
- Clearly identify what is missing
- Assess the severity (Critical, High, Medium, Low)
- Explain why it's important
- Provide specific recommendations for additional tests
- Assign a confidence score (0.0 to 1.0)

Severity Guidelines:
- Critical: Missing requirements that are essential for compliance or functionality
- High: Significant gaps that reduce test coverage meaningfully
- Medium: Gaps that should be addressed for comprehensive testing
- Low: Minor omissions that have limited impact

Output your analysis in a structured JSON format."""

    def get_user_prompt(self, context: AgentContext) -> str:
        """
        Get user prompt for Gap Analysis Agent.

        Args:
            context: Execution context with critic_result and source content

        Returns:
            User prompt string
        """
        # Get data from context
        critic_result = context.previous_results.get('critic_result', {})
        synthesized_rules = critic_result.get('synthesized_rules', '')

        return f"""Analyze the following section for requirement gaps and missing test coverage.

## SOURCE SECTION (Original Standard)
Title: {context.section_title}

Content:
{context.section_content}

## GENERATED TEST PROCEDURES (from Critic Agent)
{synthesized_rules}

---

## ANALYSIS TASKS

Perform a comprehensive gap analysis:

### 1. REQUIREMENT COVERAGE
- Compare generated test procedures against source content
- Identify requirements mentioned in source but not tested
- Find specifications that lack explicit test procedures

### 2. IMPLICIT REQUIREMENTS
- Identify implicit requirements in the source that should be explicit
- Find assumed behaviors that need testing
- Detect unstated prerequisites or dependencies

### 3. SECTION COMPLETENESS
- Check if all subsections are addressed
- Identify skipped clauses or paragraphs
- Find figures, tables, or equations that aren't referenced in tests

### 4. TEST COVERAGE DEPTH
- Assess if tests cover all aspects of each requirement
- Identify requirements with shallow or incomplete testing
- Find edge cases or boundary conditions not covered

---

## OUTPUT FORMAT

Return a JSON object with the following structure:

```json
{{
  "gaps": [
    {{
      "gap_id": "unique_id",
      "gap_type": "missing_requirement|implicit_requirement|incomplete_coverage|untested_section",
      "severity": "Critical|High|Medium|Low",
      "source_reference": "reference to source content (e.g., 'Section 3.2.1', 'Table 4')",
      "missing_requirement": "description of what's missing",
      "current_coverage": "what is currently tested (if anything)",
      "recommendation": "specific recommendation for additional testing",
      "suggested_test": "concrete test procedure to address the gap",
      "confidence": 0.0-1.0
    }}
  ],
  "coverage_metrics": {{
    "total_source_requirements": 0,
    "tested_requirements": 0,
    "coverage_percentage": 0.0
  }}
}}
```

Be thorough and specific. Focus on genuine gaps that impact test completeness.
If no significant gaps are found, return an empty gaps array but still provide coverage metrics."""

    def parse_response(self, response: str, context: AgentContext) -> Dict[str, Any]:
        """
        Parse Gap Analysis Agent response into structured data.

        Args:
            response: Raw LLM response (should be JSON)
            context: Execution context

        Returns:
            Dictionary with parsed gaps
        """
        try:
            # Extract JSON from response
            json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # Try to find JSON object directly
                json_match = re.search(r'\{[\s\S]*"gaps"[\s\S]*\}', response)
                if json_match:
                    json_str = json_match.group(0)
                else:
                    json_str = response

            data = json.loads(json_str)
            gaps = []

            for item in data.get("gaps", []):
                gap = {
                    'gap_id': item.get("gap_id", str(uuid.uuid4())),
                    'gap_type': item.get("gap_type", "missing_requirement"),
                    'severity': item.get("severity", "Medium"),
                    'source_reference': item.get("source_reference", ""),
                    'missing_requirement': item.get("missing_requirement", ""),
                    'current_coverage': item.get("current_coverage", "None"),
                    'recommendation': item.get("recommendation", ""),
                    'suggested_test': item.get("suggested_test", ""),
                    'confidence': float(item.get("confidence", 0.8))
                }
                gaps.append(gap)

            # Get coverage metrics
            coverage_metrics = data.get("coverage_metrics", {})

            # Generate summary
            summary = self._generate_summary(gaps, coverage_metrics)

            return {
                'section_title': context.section_title,
                'gaps': gaps,
                'total_gaps': len(gaps),
                'critical_count': sum(1 for g in gaps if g['severity'] == "Critical"),
                'high_count': sum(1 for g in gaps if g['severity'] == "High"),
                'medium_count': sum(1 for g in gaps if g['severity'] == "Medium"),
                'low_count': sum(1 for g in gaps if g['severity'] == "Low"),
                'coverage_metrics': coverage_metrics,
                'analysis_summary': summary
            }

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse gap analysis response as JSON: {e}")
            return {
                'section_title': context.section_title,
                'gaps': [],
                'total_gaps': 0,
                'critical_count': 0,
                'high_count': 0,
                'medium_count': 0,
                'low_count': 0,
                'coverage_metrics': {},
                'analysis_summary': 'Failed to parse gap analysis',
                'raw_response': response
            }
        except Exception as e:
            logger.error(f"Failed to parse gap analysis response: {e}")
            return {
                'section_title': context.section_title,
                'gaps': [],
                'total_gaps': 0,
                'critical_count': 0,
                'high_count': 0,
                'medium_count': 0,
                'low_count': 0,
                'coverage_metrics': {},
                'analysis_summary': f'Error parsing response: {str(e)}',
                'raw_response': response
            }

    def _generate_summary(self, gaps: List[Dict], coverage_metrics: Dict) -> str:
        """Generate human-readable summary of gaps"""
        if not gaps:
            coverage_pct = coverage_metrics.get('coverage_percentage', 0)
            return f"No significant gaps detected. Estimated coverage: {coverage_pct:.1f}%"

        critical = [g for g in gaps if g['severity'] == "Critical"]
        high = [g for g in gaps if g['severity'] == "High"]

        summary_parts = [
            f"Found {len(gaps)} requirement gap(s):",
            f"- {len(critical)} Critical",
            f"- {len(high)} High",
            f"- {len([g for g in gaps if g['severity'] == 'Medium'])} Medium",
            f"- {len([g for g in gaps if g['severity'] == 'Low'])} Low"
        ]

        # Add coverage metrics if available
        if coverage_metrics:
            tested = coverage_metrics.get('tested_requirements', 0)
            total = coverage_metrics.get('total_source_requirements', 0)
            if total > 0:
                pct = (tested / total) * 100
                summary_parts.append(f"\nCoverage: {tested}/{total} requirements ({pct:.1f}%)")

        if critical:
            summary_parts.append("\nCritical Gaps:")
            for g in critical[:3]:  # Show first 3
                missing = g.get('missing_requirement', 'No description')
                summary_parts.append(f"  • {missing[:100]}...")

        return "\n".join(summary_parts)
