"""
Pairwise Synthesis Service
Combines adjacent sections to reduce redundancy and improve cohesion.
Based on test_card_gen.ipynb's synthesize_pairwise_test_plan approach.
"""

import logging
from typing import Dict, List, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)

# Parallel processing configuration (from notebook)
PAIRWISE_MAX_WORKERS = 4  # Maximum concurrent pairwise syntheses


class PairwiseSynthesisService:
    """
    Service for combining adjacent test plan sections.

    Benefits:
    - Reduces redundancy between consecutive sections
    - Identifies cross-section dependencies
    - Merges overlapping test procedures
    - Creates more cohesive test plans

    Based on notebook's approach with enhanced error handling.
    """

    def __init__(self, llm_service):
        """
        Initialize pairwise synthesis service.

        Args:
            llm_service: LLM service instance for synthesis
        """
        self.llm_service = llm_service

    def synthesize_pairwise(
        self,
        sections: Dict[str, str],
        section_order: List[str],
        max_workers: int = PAIRWISE_MAX_WORKERS
    ) -> Dict[str, str]:
        """
        Synthesize adjacent sections pairwise in parallel.

        Args:
            sections: Dictionary mapping section_name -> content
            section_order: Ordered list of section names
            max_workers: Maximum concurrent workers (default: 4)

        Returns:
            Dictionary of first_section_name -> synthesized_content

        Example:
            sections = {
                "Section 4.1": "Power supply requirements...",
                "Section 4.2": "Power supply testing...",
                "Section 4.3": "Grounding requirements..."
            }
            section_order = ["Section 4.1", "Section 4.2", "Section 4.3"]

            Returns: {
                "Section 4.1": "Combined 4.1 & 4.2 content...",
                "Section 4.3": "Section 4.3 content (no pair)..."
            }
        """
        logger.info(f"Starting pairwise synthesis for {len(section_order)} sections")

        if len(section_order) < 2:
            logger.warning("Need at least 2 sections for pairwise synthesis")
            return sections

        pairwise_results = {}

        try:
            # Create pairs: (Section 1, Section 2), (Section 3, Section 4), etc.
            pairs = []
            for i in range(0, len(section_order), 2):
                s1 = section_order[i]

                # Check if we have a pair
                if i + 1 < len(section_order):
                    s2 = section_order[i + 1]
                    if s1 in sections and s2 in sections:
                        pairs.append((s1, s2, sections[s1], sections[s2]))
                        logger.info(f"Created pair: {s1} + {s2}")
                else:
                    # Odd section at end, keep as-is
                    if s1 in sections:
                        pairwise_results[s1] = sections[s1]
                        logger.info(f"No pair for final section: {s1} (keeping original)")

            logger.info(f"Created {len(pairs)} pairs for synthesis")

            if not pairs:
                logger.warning("No valid pairs created")
                return sections

            # Process pairs in parallel
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_pair = {
                    executor.submit(
                        self._synthesize_pair,
                        s1,
                        s2,
                        content1,
                        content2
                    ): (s1, s2)
                    for s1, s2, content1, content2 in pairs
                }

                completed = 0
                total = len(future_to_pair)
                for future in as_completed(future_to_pair):
                    s1, s2 = future_to_pair[future]
                    completed += 1
                    try:
                        combined_content = future.result()
                        pairwise_results[s1] = combined_content
                        logger.info(f" [{completed}/{total}] Synthesized pair: {s1} + {s2}")
                    except Exception as e:
                        logger.error(f" [{completed}/{total}] Failed to synthesize {s1} + {s2}: {e}")
                        # Fallback: keep original first section
                        pairwise_results[s1] = sections.get(s1, "")

            logger.info(f"Completed pairwise synthesis: {len(pairwise_results)} combined sections")
            return pairwise_results

        except Exception as e:
            logger.error(f"Pairwise synthesis failed: {e}")
            # Return original sections on error
            return sections

    def synthesize_consecutive(
        self,
        sections: Dict[str, str],
        section_order: List[str],
        max_workers: int = PAIRWISE_MAX_WORKERS
    ) -> Dict[str, str]:
        """
        Synthesize consecutive adjacent sections (overlapping pairs).

        This is the notebook's original approach where each section is combined
        with the next one: (1,2), (2,3), (3,4), etc.

        Args:
            sections: Dictionary mapping section_name -> content
            section_order: Ordered list of section names
            max_workers: Maximum concurrent workers

        Returns:
            Dictionary of first_section_name -> synthesized_content

        Example:
            sections = {
                "Section 4.1": "...",
                "Section 4.2": "...",
                "Section 4.3": "..."
            }

            Returns: {
                "Section 4.1": "Combined 4.1 & 4.2",
                "Section 4.2": "Combined 4.2 & 4.3"
            }
        """
        logger.info(f"Starting consecutive pairwise synthesis for {len(section_order)} sections")

        if len(section_order) < 2:
            logger.warning("Need at least 2 sections for consecutive synthesis")
            return sections

        pairwise_results = {}

        try:
            # Create consecutive pairs: (1,2), (2,3), (3,4), etc.
            pairs = []
            for i in range(len(section_order) - 1):
                s1 = section_order[i]
                s2 = section_order[i + 1]
                if s1 in sections and s2 in sections:
                    pairs.append((s1, s2, sections[s1], sections[s2]))
                    logger.info(f"Created consecutive pair: {s1} + {s2}")

            logger.info(f"Created {len(pairs)} consecutive pairs for synthesis")

            if not pairs:
                logger.warning("No valid pairs created")
                return sections

            # Process pairs in parallel
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_pair = {
                    executor.submit(
                        self._synthesize_pair,
                        s1,
                        s2,
                        content1,
                        content2
                    ): (s1, s2)
                    for s1, s2, content1, content2 in pairs
                }

                completed = 0
                total = len(future_to_pair)
                for future in as_completed(future_to_pair):
                    s1, s2 = future_to_pair[future]
                    completed += 1
                    try:
                        combined_content = future.result()
                        pairwise_results[s1] = combined_content
                        logger.info(f" [{completed}/{total}] Synthesized consecutive: {s1} + {s2}")
                    except Exception as e:
                        logger.error(f" [{completed}/{total}] Failed to synthesize {s1} + {s2}: {e}")
                        # Fallback: keep original first section
                        pairwise_results[s1] = sections.get(s1, "")

            logger.info(f"Completed consecutive synthesis: {len(pairwise_results)} combined sections")
            return pairwise_results

        except Exception as e:
            logger.error(f"Consecutive synthesis failed: {e}")
            return sections

    def _synthesize_pair(
        self,
        section1_name: str,
        section2_name: str,
        content1: str,
        content2: str
    ) -> str:
        """
        Synthesize two adjacent sections into one cohesive section.
        Based on notebook's approach with enhanced prompt.

        Args:
            section1_name: Name of first section
            section2_name: Name of second section
            content1: Content of first section
            content2: Content of second section

        Returns:
            Combined synthesized content
        """
        prompt = f"""You are a senior QA documentation engineer.

Given the DETAILED test rules for two consecutive sections, synthesize a single, logically organized, highly detailed test plan section.

Instructions:
- Combine rules and merge similar steps
- Cross-reference overlapping content and eliminate redundancy
- Call out dependencies or conflicts between sections
- Use a single, content-based TITLE for this combined section (derived from both section titles)
- Keep bold markdown headings for 'Dependencies', 'Conflicts', and 'Test Rules'
- Test rules must be extremely explicit, step-by-step, and cover ALL possible technical details
- If rules conflict, note the conflict and provide recommendations
- If rules complement each other, integrate them seamlessly
- Format output using clean markdown

=== SECTION 1 ===
Title: {section1_name}

Content:
{content1}

=== SECTION 2 ===
Title: {section2_name}

Content:
{content2}

=== END ===

Output ONLY the combined test plan section in the described format. Do not add any preamble or explanation."""

        try:
            logger.debug(f"Synthesizing: {section1_name} + {section2_name}")

            response = self.llm_service.query_direct(
                model_name="gpt-4",
                query=prompt
            )[0]

            # Log success with preview
            preview = response[:100] + "..." if len(response) > 100 else response
            logger.debug(f"Synthesized successfully. Preview: {preview}")

            return response

        except Exception as e:
            logger.error(f"Pair synthesis failed for {section1_name} + {section2_name}: {e}")
            # Fallback: concatenate with separator
            fallback = f"## Combined: {section1_name} & {section2_name}\n\n"
            fallback += f"### {section1_name}\n\n{content1}\n\n"
            fallback += f"---\n\n"
            fallback += f"### {section2_name}\n\n{content2}\n\n"
            logger.warning(f"Using fallback concatenation for {section1_name} + {section2_name}")
            return fallback

    def synthesize_with_redis_pipeline(
        self,
        pipeline_id: str,
        redis_client,
        synthesis_mode: str = "pairwise",
        max_workers: int = PAIRWISE_MAX_WORKERS
    ) -> Dict[str, str]:
        """
        Synthesize sections from Redis pipeline.

        Args:
            pipeline_id: Redis pipeline ID
            redis_client: Redis client instance
            synthesis_mode: "pairwise" (1+2, 3+4) or "consecutive" (1+2, 2+3, 3+4)
            max_workers: Maximum concurrent workers

        Returns:
            Dictionary of synthesized sections
        """
        try:
            # Get all section critic results from Redis
            pattern = f"pipeline:{pipeline_id}:critic:*"
            critic_keys = redis_client.keys(pattern)

            if not critic_keys:
                logger.warning(f"No sections found for pipeline: {pipeline_id}")
                return {}

            logger.info(f"Found {len(critic_keys)} sections in pipeline {pipeline_id}")

            # Extract sections and order
            sections = {}
            section_order = []

            for key in sorted(critic_keys):  # Sort to maintain order
                critic_data = redis_client.hgetall(key)
                section_title = critic_data.get("section_title", "")
                synthesized_rules = critic_data.get("synthesized_rules", "")

                if section_title and synthesized_rules:
                    sections[section_title] = synthesized_rules
                    section_order.append(section_title)

            logger.info(f"Loaded {len(sections)} sections for synthesis")

            # Synthesize based on mode
            if synthesis_mode == "consecutive":
                return self.synthesize_consecutive(sections, section_order, max_workers)
            else:  # pairwise
                return self.synthesize_pairwise(sections, section_order, max_workers)

        except Exception as e:
            logger.error(f"Redis pipeline synthesis failed: {e}")
            return {}
