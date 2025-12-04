"""
Test Card Schemas
Pydantic models for test card generation requests and responses.
"""

from pydantic import BaseModel, Field
from typing import List, Optional


class TestCardRequest(BaseModel):
    """Request model for generating test cards from test rules"""
    section_title: str = Field(..., description="Title of the section being tested")
    rules_markdown: str = Field(..., description="Markdown containing test rules and procedures")
    format: str = Field(
        default="markdown_table",
        description="Output format: markdown_table, json, or docx_table"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "section_title": "Section 4.1: Power Supply Requirements",
                "rules_markdown": "## Power Supply Requirements\n\n**Test Rules:**\n1. Verify voltage is 120V ±5%\n2. Check current draw under load",
                "format": "markdown_table"
            }
        }


class TestCardResponse(BaseModel):
    """Response model for test card generation"""
    section_title: str = Field(..., description="Title of the section")
    test_card_content: str = Field(..., description="Generated test card in requested format")
    format: str = Field(..., description="Format of the test card content")
    test_count: int = Field(..., description="Number of test cases in the card")

    class Config:
        json_schema_extra = {
            "example": {
                "section_title": "Section 4.1: Power Supply Requirements",
                "test_card_content": "| Test ID | Test Title | ... |\n|---------|------------|-----|\n| TC-001  | Verify voltage | ... |",
                "format": "markdown_table",
                "test_count": 2
            }
        }


class TestCardBatchRequest(BaseModel):
    """Request model for generating test cards for multiple sections"""
    pipeline_id: str = Field(..., description="Redis pipeline ID")
    format: str = Field(
        default="markdown_table",
        description="Output format for all test cards"
    )
    section_titles: Optional[List[str]] = Field(
        default=None,
        description="Optional list of section titles to generate cards for. If None, generates for all sections."
    )

    class Config:
        json_schema_extra = {
            "example": {
                "pipeline_id": "pipeline_abc123def456",
                "format": "markdown_table",
                "section_titles": ["Section 4.1", "Section 4.2"]
            }
        }


class TestCardBatchResponse(BaseModel):
    """Response model for batch test card generation"""
    pipeline_id: str = Field(..., description="Redis pipeline ID")
    test_cards: dict = Field(..., description="Dictionary mapping section titles to test card content")
    total_sections: int = Field(..., description="Total number of sections processed")
    total_tests: int = Field(..., description="Total number of test cases generated")
    format: str = Field(..., description="Format used for test cards")

    class Config:
        json_schema_extra = {
            "example": {
                "pipeline_id": "pipeline_abc123def456",
                "test_cards": {
                    "Section 4.1": "| Test ID | ... |\n|---------|-----|\n| TC-001  | ... |"
                },
                "total_sections": 2,
                "total_tests": 5,
                "format": "markdown_table"
            }
        }


class ExportTestPlanWithCardsRequest(BaseModel):
    """Request model for exporting test plan with embedded test cards"""
    pipeline_id: str = Field(..., description="Redis pipeline ID")
    include_test_cards: bool = Field(
        default=False,
        description="Whether to include test card tables (deprecated - use test_card_viewer.py instead)"
    )
    export_format: str = Field(
        default="pandoc",
        description="Export method: pandoc or python-docx"
    )
    include_toc: bool = Field(
        default=True,
        description="Whether to include table of contents (Pandoc only)"
    )
    number_sections: bool = Field(
        default=True,
        description="Whether to number sections automatically (Pandoc only)"
    )
    reference_docx: Optional[str] = Field(
        default=None,
        description="Path to reference .docx for styling (Pandoc only)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "pipeline_id": "pipeline_abc123def456",
                "include_test_cards": False,
                "export_format": "pandoc",
                "include_toc": True,
                "number_sections": True
            }
        }


class ExportTestPlanWithCardsResponse(BaseModel):
    """Response model for test plan export with test cards"""
    filename: str = Field(..., description="Generated filename")
    content_b64: str = Field(..., description="Base64-encoded Word document content")
    format: str = Field(..., description="Export format used")
    includes_test_cards: bool = Field(..., description="Whether test cards are included")
    file_size_bytes: Optional[int] = Field(default=None, description="Size of generated file in bytes")

    class Config:
        json_schema_extra = {
            "example": {
                "filename": "Test_Plan_with_test_cards.docx",
                "content_b64": "UEsDBBQABgAIAAAAIQ...",
                "format": "pandoc",
                "includes_test_cards": True,
                "file_size_bytes": 45678
            }
        }
