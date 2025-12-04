"""
Markdown Sanitization Service
Combines notebook sanitization with service deduplication for cleaner output.
"""

import re
from typing import Set, List
import logging

logger = logging.getLogger(__name__)


class MarkdownSanitizationService:
    """
    Service for sanitizing and deduplicating markdown content.
    Combines approaches from mil_test_plan_gen.ipynb and multi_agent_test_plan_service.
    """

    @staticmethod
    def sanitize_markdown(md: str) -> str:
        """
        Normalize markdown for Pandoc compatibility.
        From notebook's _sanitize_markdown.

        Args:
            md: Raw markdown content

        Returns:
            Sanitized markdown
        """
        if not md:
            return ""

        # Replace common emoji bullets with hyphen bullets
        md = md.replace(" ", "- ")
        md = md.replace("• ", "- ")
        md = md.replace("– ", "- ")
        md = md.replace("● ", "- ")
        md = md.replace("◦ ", "  - ")  # Sub-bullets

        # Normalize numbered lists that use ')' instead of '.'
        md = re.sub(r'^(\s*)(\d+)\)\s+', r'\1\2. ', md, flags=re.MULTILINE)

        # Fix bold markers separated by spaces: ** bold ** -> **bold**
        md = re.sub(r'\*\*\s+(.*?)\s+\*\*', r'**\1**', md)

        # Fix italic markers: * italic * -> *italic*
        md = re.sub(r'(?<!\*)\*\s+(.*?)\s+\*(?!\*)', r'*\1*', md)

        # Remove multiple consecutive blank lines (keep max 2)
        md = re.sub(r'\n{3,}', '\n\n', md)

        # Ensure headings have blank line before them (unless at start of doc)
        md = re.sub(r'([^\n])\n(#{1,6}\s)', r'\1\n\n\2', md)

        # Ensure headings have blank line after them
        md = re.sub(r'(#{1,6}\s[^\n]+)\n([^#\n])', r'\1\n\n\2', md)

        # Fix list items to have proper spacing
        # Ensure blank line before list starts (unless at start)
        md = re.sub(r'([^\n])\n([-*+]\s)', r'\1\n\n\2', md)

        # Normalize code block fences
        md = re.sub(r'```\s*(\w+)?\s*\n', r'```\1\n', md)

        # Trim excess whitespace at line ends
        md = re.sub(r'[ \t]+$', '', md, flags=re.MULTILINE)

        # Trim leading/trailing whitespace from document
        md = md.strip()

        # Ensure document ends with newline
        return md + "\n" if md else ""

    @staticmethod
    def deduplicate_markdown_sections(text: str) -> str:
        """
        Deduplicate sentences within markdown sections.
        From multi_agent_test_plan_service._deduplicate_markdown.

        Args:
            text: Markdown text with potential duplicates

        Returns:
            Deduplicated markdown
        """
        if not text:
            return ""

        output = []
        section_boundary = lambda l: l.startswith("## ") or (l.startswith("**") and l.endswith("**"))

        def process_block(block):
            """Process a block of text and deduplicate sentences"""
            if not block.strip():
                return

            local_seen = set()
            for sentence in re.split(r'(?<=[.!?]) +', block):
                sent = sentence.strip()
                if not sent:
                    continue

                # Normalize for comparison (lowercase, collapse whitespace)
                norm = re.sub(r'\s+', ' ', sent.lower())

                if norm not in local_seen:
                    output.append(sent)
                    local_seen.add(norm)

        current_block = []
        for line in text.split('\n'):
            if section_boundary(line):
                # Process accumulated block
                process_block(' '.join(current_block))
                current_block = []
                output.append(line)
            elif line.strip() == "":
                # Empty line - process block and preserve empty line
                process_block(' '.join(current_block))
                current_block = []
                output.append(line)
            else:
                current_block.append(line.strip())

        # Process final block
        process_block(' '.join(current_block))

        return '\n'.join(output)

    @staticmethod
    def global_deduplicate(text: str) -> str:
        """
        Remove duplicate lines globally across entire document.
        From multi_agent_test_plan_service._final_global_deduplicate.

        Args:
            text: Markdown text

        Returns:
            Globally deduplicated markdown
        """
        if not text:
            return ""

        seen = set()
        out = []

        for line in text.split('\n'):
            # For long lines, split by sentences
            sentences = re.split(r'(?<=[.!?]) +', line) if len(line) > 120 else [line]
            unique_sentences = []

            for s in sentences:
                s_stripped = s.strip()

                # Preserve empty lines
                if not s_stripped:
                    unique_sentences.append(s)
                    continue

                # Normalize for comparison
                norm = re.sub(r'\s+', ' ', s_stripped.lower())

                if norm not in seen:
                    unique_sentences.append(s)
                    seen.add(norm)

            joined = ' '.join(unique_sentences).strip()

            # Add to output (preserve empty lines)
            if joined or not line.strip():
                out.append(joined)

        return '\n'.join(out)

    @classmethod
    def full_sanitization_pipeline(cls, markdown: str, skip_dedup: bool = False) -> str:
        """
        Complete sanitization pipeline combining all methods.

        Pipeline:
        1. Sanitize markdown syntax
        2. Deduplicate within sections (optional)
        3. Global deduplication (optional)

        Args:
            markdown: Raw markdown content
            skip_dedup: If True, skip deduplication steps (only sanitize)

        Returns:
            Fully sanitized markdown
        """
        if not markdown:
            return ""

        logger.debug("Starting markdown sanitization pipeline")

        # Step 1: Sanitize syntax
        markdown = cls.sanitize_markdown(markdown)
        logger.debug("Markdown syntax sanitized")

        if skip_dedup:
            logger.debug("Skipping deduplication (skip_dedup=True)")
            return markdown

        # Step 2: Section-level deduplication
        markdown = cls.deduplicate_markdown_sections(markdown)
        logger.debug("Section-level deduplication complete")

        # Step 3: Global deduplication
        markdown = cls.global_deduplicate(markdown)
        logger.debug("Global deduplication complete")

        return markdown

    @staticmethod
    def remove_specific_patterns(markdown: str, patterns: List[str]) -> str:
        """
        Remove specific regex patterns from markdown.

        Args:
            markdown: Markdown content
            patterns: List of regex patterns to remove

        Returns:
            Markdown with patterns removed
        """
        if not markdown or not patterns:
            return markdown

        for pattern in patterns:
            try:
                markdown = re.sub(pattern, '', markdown, flags=re.MULTILINE)
            except re.error as e:
                logger.warning(f"Invalid regex pattern '{pattern}': {e}")

        return markdown

    @staticmethod
    def normalize_headings(markdown: str) -> str:
        """
        Normalize heading styles and ensure proper hierarchy.

        Args:
            markdown: Markdown content

        Returns:
            Markdown with normalized headings
        """
        if not markdown:
            return ""

        lines = markdown.split('\n')
        normalized = []

        for line in lines:
            # Convert underline-style headings to hash-style
            if line.strip() and len(line.strip()) > 0:
                next_idx = lines.index(line) + 1
                if next_idx < len(lines):
                    next_line = lines[next_idx].strip()

                    # Heading 1: underlined with ===
                    if next_line and all(c == '=' for c in next_line):
                        normalized.append(f"# {line.strip()}")
                        lines[next_idx] = ""  # Skip the underline
                        continue

                    # Heading 2: underlined with ---
                    if next_line and all(c == '-' for c in next_line):
                        normalized.append(f"## {line.strip()}")
                        lines[next_idx] = ""  # Skip the underline
                        continue

            # Ensure consistent spacing in hash-style headings
            heading_match = re.match(r'^(#{1,6})\s*(.*)', line)
            if heading_match:
                hashes, text = heading_match.groups()
                normalized.append(f"{hashes} {text.strip()}")
            else:
                normalized.append(line)

        return '\n'.join(normalized)

    @classmethod
    def prepare_for_pandoc(cls, markdown: str) -> str:
        """
        Prepare markdown specifically for Pandoc conversion.

        Args:
            markdown: Markdown content

        Returns:
            Pandoc-ready markdown
        """
        # Full sanitization
        markdown = cls.full_sanitization_pipeline(markdown)

        # Normalize headings
        markdown = cls.normalize_headings(markdown)

        # Ensure code blocks use fenced style (not indented)
        # Pandoc handles fenced blocks better

        # Add metadata block if not present (for Pandoc title page)
        if not markdown.startswith('---'):
            # Extract title from first heading if present
            title_match = re.search(r'^#\s+(.+)$', markdown, re.MULTILINE)
            if title_match:
                title = title_match.group(1)
                # Don't add metadata block, just ensure proper structure
                pass

        return markdown
