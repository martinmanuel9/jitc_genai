"""
Shared CSS styles for workflow components.
Ensures visual consistency across Upload, Generate, Edit Test Plan,
Generate Test Cards, Edit Test Cards, and Execute tabs.
"""

# =============================================================================
# Panel and Layout Constants
# =============================================================================

# Unified panel height for side-by-side layouts (fixed equal height)
PANEL_HEIGHT = 700  # pixels

# Quill editor heights (proportional to panel)
QUILL_SINGLE_HEIGHT = 300   # Single editor takes more space
QUILL_MULTI_HEIGHT = 150    # Multiple editors (2-3) share space
QUILL_COMPACT_HEIGHT = 100  # Compact mode for 4+ editors

# Text area heights
TEXT_AREA_STANDARD = 100    # Pass/Fail criteria, notes (was 60)
TEXT_AREA_COMPACT = 80      # Inline fields


def get_sidebyside_css() -> str:
    """
    Return CSS for side-by-side panel layouts.
    Use this in any component that has source document + editor panels.
    """
    return f"""
    <style>
    /* ===== SIDE-BY-SIDE PANEL LAYOUT ===== */

    /* Panel content wrapper - equal height panels */
    .panel-container {{
        height: {PANEL_HEIGHT}px !important;
        min-height: {PANEL_HEIGHT}px !important;
        max-height: {PANEL_HEIGHT}px !important;
        overflow-y: auto !important;
        overflow-x: hidden !important;
    }}

    /* ===== SOURCE DOCUMENT PANEL (LEFT) ===== */
    .source-document-panel {{
        height: {PANEL_HEIGHT}px;
        min-height: {PANEL_HEIGHT}px;
        max-height: {PANEL_HEIGHT}px;
        overflow-y: auto;
        padding: 20px;
        background: #fff;
        border: 1px solid #ddd;
        border-radius: 4px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        font-family: 'Georgia', serif;
        color: #333;
        line-height: 1.6;
    }}

    .source-document-panel h1,
    .source-document-panel h2,
    .source-document-panel h3,
    .source-document-panel h4 {{
        font-family: 'Georgia', serif;
        color: #222;
        margin-top: 1em;
        margin-bottom: 0.5em;
    }}

    .source-document-panel p {{
        margin: 0.5em 0;
        text-align: justify;
    }}

    .source-document-panel ul,
    .source-document-panel ol {{
        margin: 0.5em 0;
        padding-left: 24px;
    }}

    /* ===== EDITOR PANEL (RIGHT) ===== */
    .editor-panel {{
        height: {PANEL_HEIGHT}px;
        min-height: {PANEL_HEIGHT}px;
        max-height: {PANEL_HEIGHT}px;
        overflow-y: auto;
        padding: 16px;
        background: #fafafa;
        border: 1px solid #e0e0e0;
        border-radius: 4px;
    }}

    /* ===== QUILL EDITOR CONSTRAINTS ===== */

    /* Single Quill editor - larger */
    .quill-single .quill,
    .quill-single .ql-container {{
        max-height: {QUILL_SINGLE_HEIGHT}px !important;
        overflow-y: auto !important;
    }}

    /* Multiple Quill editors (2-3) - medium */
    .quill-multi .quill,
    .quill-multi .ql-container {{
        max-height: {QUILL_MULTI_HEIGHT}px !important;
        overflow-y: auto !important;
    }}

    /* Compact Quill editors (4+) */
    .quill-compact .quill,
    .quill-compact .ql-container {{
        max-height: {QUILL_COMPACT_HEIGHT}px !important;
        overflow-y: auto !important;
    }}

    /* Override default Quill container styling */
    .ql-container {{
        font-family: 'Georgia', serif;
        font-size: 14px;
    }}

    .ql-editor {{
        min-height: 80px;
    }}

    /* ===== SECTION SEPARATORS ===== */
    .section-separator {{
        border-bottom: 1px solid #e0e0e0;
        margin: 16px 0;
        padding-bottom: 16px;
    }}

    .section-header {{
        font-size: 0.9em;
        font-weight: 600;
        color: #444;
        margin: 12px 0 8px 0;
        padding-bottom: 4px;
        border-bottom: 1px solid #eee;
    }}

    /* ===== SECTION LIST (VERTICAL LAYOUT) ===== */
    .section-list {{
        display: flex;
        flex-direction: column;
        gap: 12px;
    }}

    .section-card {{
        border: 1px solid #e0e0e0;
        border-radius: 4px;
        padding: 12px 16px;
        background: #fff;
        cursor: pointer;
        transition: all 0.2s ease;
    }}

    .section-card:hover {{
        border-color: #1976d2;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }}

    .section-card.selected {{
        border-color: #1976d2;
        background: #f5f9ff;
        box-shadow: 0 2px 8px rgba(25, 118, 210, 0.2);
    }}

    .section-card.reviewed {{
        border-left: 4px solid #4caf50;
    }}

    .section-card.draft {{
        border-left: 4px solid #ff9800;
    }}

    .section-card-title {{
        font-weight: 600;
        color: #333;
        margin-bottom: 4px;
    }}

    .section-card-meta {{
        font-size: 0.85em;
        color: #666;
    }}

    .section-card-badge {{
        display: inline-block;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 0.75em;
        font-weight: 500;
    }}

    .section-card-badge.reviewed {{
        background: #e8f5e9;
        color: #2e7d32;
    }}

    .section-card-badge.draft {{
        background: #fff3e0;
        color: #e65100;
    }}

    /* ===== FORM FIELD LABELS ===== */
    .field-label {{
        font-size: 0.85em;
        color: #666;
        margin: 8px 0 4px 0;
    }}

    .field-label-success {{
        font-size: 0.85em;
        color: #28a745;
        margin: 12px 0 4px 0;
    }}

    .field-label-danger {{
        font-size: 0.85em;
        color: #dc3545;
        margin: 12px 0 4px 0;
    }}

    /* ===== PROGRESS INDICATOR ===== */
    .progress-bar-container {{
        background: #e0e0e0;
        border-radius: 4px;
        height: 8px;
        margin: 8px 0;
        overflow: hidden;
    }}

    .progress-bar-fill {{
        background: linear-gradient(90deg, #4caf50, #81c784);
        height: 100%;
        border-radius: 4px;
        transition: width 0.3s ease;
    }}

    .progress-text {{
        font-size: 0.85em;
        color: #666;
        text-align: center;
    }}

    /* ===== PROCEDURE SELECTION ===== */
    .procedure-item {{
        padding: 8px 12px;
        border: 1px solid #e0e0e0;
        border-radius: 4px;
        margin-bottom: 8px;
        background: #fff;
    }}

    .procedure-item:hover {{
        background: #f5f5f5;
    }}

    .procedure-item.selected {{
        border-color: #1976d2;
        background: #e3f2fd;
    }}

    .procedure-title {{
        font-weight: 500;
        color: #333;
    }}

    .procedure-meta {{
        font-size: 0.85em;
        color: #666;
        margin-top: 4px;
    }}

    /* ===== PREVENT NESTED SCROLLBARS ===== */
    .no-nested-scroll {{
        overflow: visible !important;
    }}

    /* ===== UTILITY CLASSES ===== */
    .mt-1 {{ margin-top: 4px; }}
    .mt-2 {{ margin-top: 8px; }}
    .mt-3 {{ margin-top: 12px; }}
    .mt-4 {{ margin-top: 16px; }}
    .mb-1 {{ margin-bottom: 4px; }}
    .mb-2 {{ margin-bottom: 8px; }}
    .mb-3 {{ margin-bottom: 12px; }}
    .mb-4 {{ margin-bottom: 16px; }}

    </style>
    """


def get_panel_inline_style() -> str:
    """
    Return inline style string for document panels.
    Use when you need inline style instead of CSS class.
    """
    return f"""
        height: {PANEL_HEIGHT}px;
        min-height: {PANEL_HEIGHT}px;
        max-height: {PANEL_HEIGHT}px;
        overflow-y: auto;
        padding: 20px;
        background: #fff;
        border: 1px solid #ddd;
        border-radius: 4px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        font-family: 'Georgia', serif;
        color: #333;
    """


def get_section_progress_html(reviewed: int, total: int) -> str:
    """
    Generate HTML for section review progress indicator.

    Args:
        reviewed: Number of reviewed sections
        total: Total number of sections

    Returns:
        HTML string with progress bar and text
    """
    if total == 0:
        return ""

    percentage = (reviewed / total) * 100
    return f"""
    <div class="progress-bar-container">
        <div class="progress-bar-fill" style="width: {percentage}%;"></div>
    </div>
    <div class="progress-text">{reviewed}/{total} sections reviewed ({percentage:.0f}%)</div>
    """


def get_section_card_html(
    title: str,
    procedures_count: int,
    is_reviewed: bool,
    is_selected: bool = False,
    heading_level: int = 1
) -> str:
    """
    Generate HTML for a section card in the vertical list.

    Args:
        title: Section title
        procedures_count: Number of test procedures in section
        is_reviewed: Whether section has been reviewed
        is_selected: Whether section is currently selected
        heading_level: Heading level for indentation (1-4)

    Returns:
        HTML string for section card
    """
    # Build CSS classes
    classes = ["section-card"]
    if is_selected:
        classes.append("selected")
    if is_reviewed:
        classes.append("reviewed")
    else:
        classes.append("draft")

    class_str = " ".join(classes)

    # Badge
    badge_class = "reviewed" if is_reviewed else "draft"
    badge_text = "Reviewed" if is_reviewed else "Draft"

    # Indentation based on heading level
    indent = (heading_level - 1) * 16

    return f"""
    <div class="{class_str}" style="margin-left: {indent}px;">
        <div class="section-card-title">{title}</div>
        <div class="section-card-meta">
            <span class="section-card-badge {badge_class}">{badge_text}</span>
            &nbsp;&middot;&nbsp; {procedures_count} procedure(s)
        </div>
    </div>
    """
