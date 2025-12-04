"""
Unified Agent Manager Component

Single component for managing ALL agents and agent sets in the system.
All agents and agent sets are database-backed.

Supports:
- Individual Agents: Actor, Critic, Contradiction Detection, Gap Analysis, Custom
- Agent Sets: Orchestration pipelines combining multiple agents
- Full CRUD operations for both agents and agent sets
"""

import streamlit as st
from config.settings import config
from app_lib.api.client import api_client
import json
from datetime import datetime
from typing import Optional, Dict, List
from collections import Counter

# API endpoints - unified database-backed system
TEST_PLAN_AGENT_API = f"{config.fastapi_url}/api/test-plan-agents"
AGENT_SET_API = f"{config.fastapi_url}/api/agent-sets"

# Workflow type mappings - user-friendly names for UI
WORKFLOW_DISPLAY_TO_BACKEND = {
    "Direct Query (Single Agent)": "document_analysis",
    "Agent Pipeline (Multi-Stage)": "test_plan_generation",
    "Custom": "general"
}

WORKFLOW_BACKEND_TO_DISPLAY = {
    "document_analysis": "Direct Query (Single Agent)",
    "test_plan_generation": "Agent Pipeline (Multi-Stage)",
    "general": "Custom"
}

# User-friendly descriptions
WORKFLOW_DESCRIPTIONS = {
    "Direct Query (Single Agent)": {
        "description": "Single agent responds to your query. Use for direct questions, document analysis, compliance checks.",
        "placeholders": "{data_sample} - Your input text or document content",
        "use_cases": "Direct Chat → Chat with AI tab, simple Q&A, document review"
    },
    "Agent Pipeline (Multi-Stage)": {
        "description": "Multiple agents process content in stages (Actor → Critic → QA). Use for complex analysis requiring multiple perspectives.",
        "placeholders": "{section_title}, {section_content}, {actor_outputs}, {critic_output}, {context}",
        "use_cases": "Direct Chat → Agent Pipeline tab, test plan generation, multi-agent analysis"
    },
    "Custom": {
        "description": "Flexible configuration for custom workflows. Define your own placeholders.",
        "placeholders": "Any custom placeholders you define",
        "use_cases": "Advanced users, experimental workflows"
    }
}


def render_unified_agent_manager():
    """
    Main entry point for Unified Agent Manager.
    Manages both individual agents and agent sets (orchestration pipelines).
    """
    st.title("Agent & Orchestration Manager")
    st.markdown("""
    **Agents**: Individual AI agents with specific roles (Actor, Critic, QA, etc.)
    
    **Agent Sets**: Orchestration pipelines that combine multiple agents in stages
    """)

    # Top-level navigation: Agents vs Agent Sets
    main_tab1, main_tab2 = st.tabs(["Individual Agents", "Agent Sets and Pipelines"])

    with main_tab1:
        # Sub-tabs for agent management
        agent_tab1, agent_tab2, agent_tab3, agent_tab4 = st.tabs([
            "View Agents",
            "Create Agent",
            "Manage Agents",
            "Help & Info"
        ])

        with agent_tab1:
            render_agent_list_view()

        with agent_tab2:
            render_create_agent_form()

        with agent_tab3:
            render_manage_agents_view()

        with agent_tab4:
            render_help_info()

    with main_tab2:
        # Sub-tabs for agent set management
        set_tab1, set_tab2, set_tab3 = st.tabs([
            "View Agent Sets",
            "Create Agent Set",
            "Analytics"
        ])

        with set_tab1:
            render_view_agent_sets()

        with set_tab2:
            render_create_agent_set()

        with set_tab3:
            render_agent_set_analytics()


def fetch_agents_cached(agent_type_filter: str = "All", include_inactive: bool = False, force_refresh: bool = False):
    """
    Fetch agents with session state caching for better UX.

    Args:
        agent_type_filter: Filter by agent type or "All"
        include_inactive: Include inactive agents
        force_refresh: Force refresh from API

    Returns:
        Tuple of (agents list, total_count)
    """
    # Create cache key based on filters
    cache_key = f"agents_{agent_type_filter}_{include_inactive}"

    # Check if we need to fetch (first time or forced refresh)
    if force_refresh or cache_key not in st.session_state:
        params = {"include_inactive": include_inactive}
        if agent_type_filter != "All":
            params["agent_type"] = agent_type_filter

        try:
            response = api_client.get(TEST_PLAN_AGENT_API, params=params)
            if response and "agents" in response:
                agents = response["agents"]
                total_count = response.get("total_count", len(agents))

                # Cache the results
                st.session_state[cache_key] = {
                    "agents": agents,
                    "total_count": total_count,
                    "timestamp": datetime.now()
                }
                return agents, total_count
            else:
                return [], 0
        except Exception as e:
            st.error(f"Error loading agents: {str(e)}")
            return [], 0
    else:
        # Return cached results
        cached = st.session_state[cache_key]
        return cached["agents"], cached["total_count"]


def render_agent_list_view():
    """
    Display list of agents with filtering options and auto-load.
    """
    st.subheader("Agent List")

    # Filters
    col1, col2, col3 = st.columns([2, 1, 1])

    with col1:
        agent_type_filter = st.selectbox(
            "Filter by Agent Type",
            ["All", "actor", "critic", "contradiction", "gap_analysis", "general", "rule_development"],
            key="agent_type_filter",
            help="Filter agents by their type"
        )

    with col2:
        include_inactive = st.checkbox("Include Inactive", value=False, key="include_inactive")

    with col3:
        force_refresh = st.button("Refresh", use_container_width=True)

    # Fetch agents (cached on first load, refreshed on button click)
    try:
        with st.spinner("Loading agents..." if force_refresh else None):
            agents, total_count = fetch_agents_cached(
                agent_type_filter,
                include_inactive,
                force_refresh=force_refresh
            )

        if agents:
            st.success(f"Found {total_count} agent(s)")

            # Display agents grouped by type
            agent_types = {}
            for agent in agents:
                agent_type = agent["agent_type"]
                if agent_type not in agent_types:
                    agent_types[agent_type] = []
                agent_types[agent_type].append(agent)

            # Render each agent type group
            for agent_type, type_agents in agent_types.items():
                with st.expander(f"**{agent_type.upper()}** ({len(type_agents)} agents)", expanded=True):
                    for agent in type_agents:
                        render_agent_card(agent)
        else:
            st.info("No agents found. Create one using the 'Create Agent' tab.")

    except Exception as e:
        st.error(f"Error loading agents: {str(e)}")


def render_agent_card(agent: Dict):
    """
    Render a single agent card with details and quick actions.
    """
    # Status badge
    status_color = "[ACTIVE]" if agent["is_active"] else "[INACTIVE]"
    default_badge = "System Default" if agent["is_system_default"] else "Custom"

    col1, col2 = st.columns([3, 1])

    with col1:
        st.markdown(f"### {status_color} {agent['name']}")
        workflow_display = WORKFLOW_BACKEND_TO_DISPLAY.get(
            agent.get('workflow_type', 'general'),
            agent.get('workflow_type', 'Unknown')
        )
        st.markdown(f"*{default_badge}* | **{workflow_display}** | Model: **{agent['model_name']}**")

    with col2:
        st.markdown(f"**ID:** {agent['id']}")
        st.markdown(f"**Active:** {'Yes' if agent['is_active'] else 'No'}")

    # Details in columns
    detail_col1, detail_col2 = st.columns(2)

    with detail_col1:
        st.markdown(f"**Temperature:** {agent['temperature']}")
        st.markdown(f"**Max Tokens:** {agent['max_tokens']}")

        if agent.get('description'):
            st.markdown(f"**Description:** {agent['description']}")

    with detail_col2:
        st.markdown(f"**Created:** {agent.get('created_at', 'N/A')[:10]}")
        st.markdown(f"**Updated:** {agent.get('updated_at', 'N/A')[:10]}")
        if agent.get('created_by'):
            st.markdown(f"**Created By:** {agent['created_by']}")

    # Expandable prompts
    with st.expander("View Prompts"):
        st.text_area("System Prompt", agent['system_prompt'], height=150, disabled=True, key=f"sys_{agent['id']}")
        st.text_area("User Prompt Template", agent['user_prompt_template'], height=150, disabled=True, key=f"usr_{agent['id']}")

    st.markdown("---")


def render_smart_template_builder(workflow_type: str, agent_type: str) -> tuple[str, str]:
    """
    Smart Template Builder - helps users create prompts without worrying about placeholders.

    Args:
        workflow_type: The workflow type (document_analysis, test_plan_generation, general)
        agent_type: The agent type (actor, critic, etc.)

    Returns:
        Tuple of (system_prompt, user_prompt_template) with proper placeholders
    """
    st.markdown("### Smart Template Builder")
    st.info("Describe what you want the agent to do, and we'll build the template with correct placeholders.")

    # Track workflow/agent type changes to clear generated templates
    current_config = f"{workflow_type}_{agent_type}"
    if st.session_state.get("smart_builder_config") != current_config:
        # Config changed, clear previous generated templates
        st.session_state.smart_builder_config = current_config
        st.session_state.pop("generated_system_prompt", None)
        st.session_state.pop("generated_user_prompt", None)

    # User describes what the agent should do
    agent_instruction = st.text_area(
        "What should this agent do?",
        height=100,
        placeholder="e.g., Extract testable requirements and identify compliance gaps...",
        help="Describe the agent's task in plain language. We'll add the necessary data placeholders.",
        key="smart_builder_instruction"
    )

    # User describes desired output format
    output_format = st.text_area(
        "Desired output format (optional)",
        height=80,
        placeholder="e.g., Return a numbered list of requirements with test criteria...",
        help="Describe how you want the output structured",
        key="smart_builder_output"
    )

    # Generate button to explicitly trigger template generation
    if st.button("Generate Template", type="primary", key="smart_builder_generate"):
        if not agent_instruction:
            st.error("Please describe what the agent should do first.")
            return st.session_state.get("generated_system_prompt", ""), st.session_state.get("generated_user_prompt", "")

        # Build system prompt
        role_descriptions = {
            "actor": "You are an expert analyst who extracts detailed, testable requirements from documents.",
            "critic": "You are a critical reviewer who synthesizes, validates, and deduplicates findings from multiple analysts.",
            "contradiction": "You are a contradiction detection specialist who identifies conflicts and inconsistencies.",
            "gap_analysis": "You are a gap analysis expert who identifies missing requirements and coverage gaps.",
            "compliance": "You are a compliance analyst who evaluates documents against standards and requirements.",
            "general": "You are an expert AI assistant specialized in analysis and problem-solving.",
            "rule_development": "You are a technical documentation specialist focused on creating structured guidelines.",
            "custom": "You are a specialized AI agent."
        }

        system_prompt = f"""{role_descriptions.get(agent_type, role_descriptions['custom'])}

Your task: {agent_instruction}

{f'Output format: {output_format}' if output_format else 'Provide clear, structured output.'}

Be thorough, accurate, and provide actionable insights."""

        # Build user prompt template based on workflow and agent type
        if workflow_type == "document_analysis":
            user_prompt_template = f"""Analyze the following document:

{{data_sample}}

Task: {agent_instruction}
{f'Format: {output_format}' if output_format else ''}"""

        elif workflow_type == "test_plan_generation":
            # Different templates based on agent stage position
            if agent_type == "actor":
                user_prompt_template = f"""## Section: {{section_title}}

{{section_content}}

---

Task: {agent_instruction}
{f'Format: {output_format}' if output_format else ''}"""

            elif agent_type == "critic":
                user_prompt_template = f"""## Section: {{section_title}}

### Original Content:
{{section_content}}

### Previous Analysis (Actor Outputs):
{{actor_outputs}}

---

Task: {agent_instruction}
{f'Format: {output_format}' if output_format else ''}"""

            elif agent_type in ["contradiction", "gap_analysis"]:
                user_prompt_template = f"""## Section: {{section_title}}

### Original Content:
{{section_content}}

### Previous Analysis:
{{context}}

### Critic Synthesis:
{{critic_output}}

---

Task: {agent_instruction}
{f'Format: {output_format}' if output_format else ''}"""

            else:  # other test_plan types
                user_prompt_template = f"""## Section: {{section_title}}

{{section_content}}

### Context from Previous Stages:
{{context}}

---

Task: {agent_instruction}
{f'Format: {output_format}' if output_format else ''}"""

        else:  # general workflow
            user_prompt_template = f"""{{input}}

---

Task: {agent_instruction}
{f'Format: {output_format}' if output_format else ''}"""

        # Store in session state so the form can use them
        st.session_state.generated_system_prompt = system_prompt
        st.session_state.generated_user_prompt = user_prompt_template
        st.success("Template generated! The prompts below have been updated.")
        st.rerun()

    # Return stored values (or empty if not generated yet)
    return st.session_state.get("generated_system_prompt", ""), st.session_state.get("generated_user_prompt", "")


def render_create_agent_form():
    """
    Form to create a new agent with template auto-population.
    """
    st.subheader("Create a New Agent")

    st.info("💡 **Tip**: Select a workflow type and agent type below, and we'll auto-populate the form with a proven template you can customize!")

    # Fetch system default agents for template loading
    try:
        response = api_client.get(TEST_PLAN_AGENT_API, params={"include_inactive": False})
        all_agents = response.get("agents", []) if response else []
        system_defaults = [a for a in all_agents if a.get("is_system_default", False)]
    except:
        system_defaults = []

    # Workflow type selection with user-friendly names
    workflow_display = st.selectbox(
        "Workflow Type",
        list(WORKFLOW_DISPLAY_TO_BACKEND.keys()),
        help="Select how this agent will be used",
        key="create_workflow_display"
    )

    # Map to backend value
    workflow_type = WORKFLOW_DISPLAY_TO_BACKEND[workflow_display]

    # Show workflow-specific guidance using new descriptions
    info = WORKFLOW_DESCRIPTIONS[workflow_display]
    st.info(f"""
**{workflow_display}**

{info['description']}

**Available Placeholders:** `{info['placeholders']}`

**Use Cases:** {info['use_cases']}

**See the Template Variable Reference below for complete usage examples.**
    """)

    # Template Variable Helper (collapsible reference)
    with st.expander("Template Variable Reference & Examples", expanded=False):
        st.markdown("### Quick Reference for " + workflow_type.replace('_', ' ').title())

        if workflow_type == "document_analysis":
            st.info("""
            **Available Variables for Document Analysis:**

            | Variable | Description |
            |----------|-------------|
            | `{data_sample}` | The complete document content to analyze |

            **When to Use**: Single-agent compliance checks, requirement extraction, document review
            """)

            st.markdown("**Example User Prompt Template:**")
            st.code("""
Analyze the following document for compliance with MIL-STD requirements:

{data_sample}

Identify:
1. Any violations of the requirements
2. Missing sections or incomplete information
3. Areas that need clarification

Format your findings as:
- Issue: [description]
- Severity: [High/Medium/Low]
- Recommendation: [specific action needed]
            """, language="text")

        elif workflow_type == "test_plan_generation":
            st.info("""
            **Available Variables for Test Plan Generation:**

            | Variable | When Available | Description |
            |----------|----------------|-------------|
            | `{section_title}` | All stages | Current section title |
            | `{section_content}` | All stages | Current section content |
            | `{actor_outputs}` | After actor stage | Combined output from all actor agents |
            | `{critic_output}` | After critic stage | Synthesized critic output |
            | `{context}` | All stages | All previous stage outputs combined |

            **Important**: Variables are only available AFTER their stage completes!
            """)

            col1, col2 = st.columns(2)

            with col1:
                st.markdown("**For Actor Agents (Stage 1 - First to run):**")
                st.code("""
Analyze the following section and extract testable requirements:

## Section: {section_title}

{section_content}

For each requirement, provide:
1. Test ID and title
2. Test methodology
3. Acceptance criteria
4. Required resources
                """, language="text")
                st.caption("Actors only have access to section_title and section_content")

            with col2:
                st.markdown("**For Critic Agents (Stage 2 - After actors):**")
                st.code("""
Review and synthesize the following analyses from actor agents:

{actor_outputs}

Your task:
1. Remove duplicate test cases
2. Resolve conflicts
3. Merge similar requirements
4. Create unified test plan

Output a consolidated list with no duplicates.
                """, language="text")
                st.caption("Critics can use actor_outputs from Stage 1")

            st.markdown("**For QA/Gap Analysis (Stage 3+ - After critic):**")
            st.code("""
Review the synthesized test plan for gaps:

## Original Section
{section_title}
{section_content}

## Synthesized Test Plan
{critic_output}

Identify:
1. Missing test scenarios
2. Untested edge cases
3. Gaps in coverage
            """, language="text")
            st.caption("Later stages can use all previous outputs")

        else:  # general
            st.info("""
            **General Workflow - Flexible Placeholders**

            Use any placeholder format you need for your custom workflow.

            Common patterns:
            - `{input}` - User input or document content
            - `{context}` - Additional context information
            - `{data}` - Generic data to process
            - Custom placeholders as needed for your use case
            """)

            st.markdown("**Example User Prompt Template:**")
            st.code("""
Process the following input according to the specified requirements:

{input}

Apply the analysis framework and provide structured output.
            """, language="text")

        st.markdown("---")

        st.warning("""
        **Common Mistakes to Avoid:**

        - Do NOT use `{rag_context}` - RAG context is automatically prepended by the system
        - Do NOT use variables before they're available (e.g., {actor_outputs} in actor stage)
        - ALWAYS include the required placeholder for your workflow type
        """)

        st.success("""
        **Pro Tips:**

        - Check the **Help & Info** tab for complete examples and best practices
        - Use system default agents as templates (auto-loaded above)
        - Test your agent with sample data before production use
        """)

    # Agent type selection - filtered by workflow type
    agent_type_options = {
        "document_analysis": ["compliance", "custom"],
        "test_plan_generation": ["actor", "critic", "contradiction", "gap_analysis"],
        "general": ["general", "rule_development", "custom"]
    }

    agent_type = st.selectbox(
        "Agent Type",
        agent_type_options.get(workflow_type, ["custom"]),
        help="Select the specific role this agent will play",
        key="create_agent_type"
    )

    # Show type-specific info
    type_info = {
        "actor": "Extracts testable requirements from document sections with detailed analysis",
        "critic": "Synthesizes and deduplicates outputs from multiple actor agents",
        "contradiction": "Detects contradictions and conflicts in test procedures",
        "gap_analysis": "Identifies missing requirements and test coverage gaps",
        "general": "General purpose agent for systems/quality/test engineering",
        "rule_development": "Specialized in document analysis and test plan creation",
        "compliance": "Evaluates documents for compliance with requirements and standards",
        "custom": "Custom agent with user-defined behavior"
    }
    st.caption(f"**{agent_type.upper()}**: {type_info.get(agent_type, '')}")

    st.markdown("---")

    # Template creation method selection
    template_method = st.radio(
        "How would you like to create the prompts?",
        ["Use Smart Builder (Recommended)", "Use System Template", "Write from Scratch"],
        horizontal=True,
        key="template_method",
        help="Smart Builder auto-generates placeholders. System Template loads proven defaults. Write from Scratch gives full control."
    )

    # Initialize default values
    default_system_prompt = ""
    default_user_prompt = ""
    default_model = 'gpt-4'
    default_temp = 0.7
    default_max_tokens = 2500
    default_description = ""

    # Smart Builder mode
    if template_method == "Use Smart Builder (Recommended)":
        smart_system_prompt, smart_user_prompt = render_smart_template_builder(workflow_type, agent_type)
        # Use session state values for form defaults
        default_system_prompt = st.session_state.get("generated_system_prompt", "")
        default_user_prompt = st.session_state.get("generated_user_prompt", "")

        if default_system_prompt and default_user_prompt:
            st.success("Template generated! Review and customize in the form below.")
            with st.expander("Preview Generated Template", expanded=False):
                st.markdown("**System Prompt:**")
                st.code(default_system_prompt, language="text")
                st.markdown("**User Prompt Template:**")
                st.code(default_user_prompt, language="text")

    elif template_method == "Use System Template":
        # Clear any Smart Builder generated templates when switching methods
        st.session_state.pop("generated_system_prompt", None)
        st.session_state.pop("generated_user_prompt", None)

        # Find matching system default template
        template_agent = None
        for agent in system_defaults:
            if agent.get('workflow_type') == workflow_type and agent.get('agent_type') == agent_type:
                template_agent = agent
                break

        # Set default values from template
        if template_agent:
            default_model = template_agent.get('model_name', 'gpt-4')
            default_temp = template_agent.get('temperature', 0.7)
            default_max_tokens = template_agent.get('max_tokens', 4000)
            default_description = template_agent.get('description', '')
            default_system_prompt = template_agent.get('system_prompt', '')
            default_user_prompt = template_agent.get('user_prompt_template', '')

            st.success(f"Template loaded: **{template_agent['name']}**")
            st.caption(f"Form is pre-filled with this template. Customize as needed and give it a unique name.")
        else:
            st.warning("No system template found for this combination. You'll need to write prompts from scratch.")

    else:  # Write from Scratch
        # Clear any Smart Builder generated templates when switching methods
        st.session_state.pop("generated_system_prompt", None)
        st.session_state.pop("generated_user_prompt", None)

        default_system_prompt = ""
        default_user_prompt = ""
        st.info("You'll need to write prompts with correct placeholders. See the Template Variable Reference above.")

    with st.form("create_agent_form"):
        col1, col2 = st.columns(2)

        with col1:
            name = st.text_input(
                "Agent Name *",
                placeholder="e.g., 'My Custom Actor Agent'",
                help="Give your agent a unique name"
            )

            available_models = config.get_available_models()
            model_index = available_models.index(default_model) if default_model in available_models else 0
            model_name = st.selectbox(
                "LLM Model *",
                available_models,
                index=model_index,
                help="Select the language model to use"
            )

            temperature = st.slider(
                "Temperature",
                0.0, 1.0,
                float(default_temp),
                0.1,
                help="Lower = more focused, Higher = more creative"
            )

            max_tokens = st.number_input(
                "Max Tokens",
                100, 32000,
                int(default_max_tokens),
                100,
                help="Maximum response length"
            )

        with col2:
            description = st.text_area(
                "Description",
                value=default_description,
                height=100,
                placeholder="Brief description of this agent's purpose"
            )
            is_active = st.checkbox("Active", value=True, help="Whether this agent is active")
            created_by = st.text_input("Created By", placeholder="Your name (optional)")

        system_prompt = st.text_area(
            "System Prompt *",
            value=default_system_prompt,
            height=200,
            placeholder="Define the agent's role, expertise, and behavior...",
            help="Core instructions that define the agent's personality and capabilities"
        )

        user_prompt_template = st.text_area(
            "User Prompt Template *",
            value=default_user_prompt,
            height=200,
            placeholder="Template for user interactions. Use appropriate placeholders.",
            help="Template that will be filled with actual data during execution"
        )

        # Submit button
        submitted = st.form_submit_button("Create Agent", type="primary", use_container_width=True)

        if submitted:
            # Validation
            if not name or len(name.strip()) < 3:
                st.error("Agent name must be at least 3 characters")
            elif not system_prompt or len(system_prompt.strip()) < 10:
                st.error("System prompt must be at least 10 characters")
            elif not user_prompt_template or len(user_prompt_template.strip()) < 10:
                st.error("User prompt template must be at least 10 characters")
            else:
                # Prepare payload
                payload = {
                    "name": name.strip(),
                    "agent_type": agent_type,
                    "workflow_type": workflow_type,
                    "model_name": model_name,
                    "system_prompt": system_prompt.strip(),
                    "user_prompt_template": user_prompt_template.strip(),
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "is_active": is_active,
                    "is_system_default": False,
                    "description": description.strip() if description else None,
                    "created_by": created_by.strip() if created_by else None
                }

                try:
                    with st.spinner("Creating agent..."):
                        response = api_client.post(TEST_PLAN_AGENT_API, data=payload)

                        if response:
                            st.success(f"Agent '{name}' created successfully!")
                            # Clear cache to force refresh
                            for key in list(st.session_state.keys()):
                                if key.startswith("agents_"):
                                    del st.session_state[key]
                        else:
                            st.error("Failed to create agent")
                except Exception as e:
                    st.error(f"Error creating agent: {str(e)}")


def render_manage_agents_view():
    """
    Manage existing agents (edit, delete, clone, activate/deactivate).
    """
    st.subheader("Manage Existing Agents")

    # Add refresh button
    col1, col2 = st.columns([4, 1])
    with col2:
        force_refresh = st.button("🔄 Refresh List", use_container_width=True)

    # Fetch all agents
    agents, _ = fetch_agents_cached("All", include_inactive=True, force_refresh=force_refresh)

    if not agents:
        st.info("No agents found. Create one in the 'Create Agent' tab.")
        return

    # Agent selection
    agent_options = {f"{agent['name']} (ID: {agent['id']})": agent for agent in agents}
    selected_option = st.selectbox(
        "Select Agent to Manage",
        ["--Select Agent--"] + list(agent_options.keys()),
        key="manage_agent_selector"
    )

    if selected_option == "--Select Agent--":
        return

    agent = agent_options[selected_option]

    # Management actions
    action = st.radio(
        "Action",
        ["View Details", "Edit", "Clone", "Activate/Deactivate", "Delete"],
        horizontal=True,
        key="manage_agent_action"
    )

    if action == "View Details":
        render_view_details(agent)
    elif action == "Edit":
        render_edit_agent(agent)
    elif action == "Clone":
        render_clone_agent(agent)
    elif action == "Activate/Deactivate":
        render_toggle_active(agent)
    elif action == "Delete":
        render_delete_agent(agent)


def render_view_details(agent: Dict):
    """View full agent details."""
    st.subheader(f"Agent Details: {agent['name']}")

    col1, col2 = st.columns(2)

    with col1:
        workflow_display = WORKFLOW_BACKEND_TO_DISPLAY.get(
            agent.get('workflow_type', 'general'),
            agent.get('workflow_type', 'N/A')
        )
        st.json({
            "ID": agent['id'],
            "Name": agent['name'],
            "Type": agent['agent_type'],
            "Workflow": workflow_display,
            "Model": agent['model_name'],
            "Temperature": agent['temperature'],
            "Max Tokens": agent['max_tokens'],
            "Active": agent['is_active'],
            "System Default": agent['is_system_default']
        })

    with col2:
        st.json({
            "Created": agent.get('created_at'),
            "Updated": agent.get('updated_at'),
            "Created By": agent.get('created_by'),
            "Description": agent.get('description')
        })

    st.text_area("System Prompt", agent['system_prompt'], height=200, disabled=True)
    st.text_area("User Prompt Template", agent['user_prompt_template'], height=200, disabled=True)

    if agent.get('metadata'):
        st.json(agent['metadata'])


def render_edit_agent(agent: Dict):
    """Edit agent form."""
    st.subheader(f"Edit Agent: {agent['name']}")

    with st.form("edit_agent_form"):
        col1, col2 = st.columns(2)

        with col1:
            new_name = st.text_input("Agent Name", value=agent['name'])

            # Workflow type selection with user-friendly names
            current_workflow = agent.get('workflow_type', 'general')
            current_workflow_display = WORKFLOW_BACKEND_TO_DISPLAY.get(current_workflow, "Custom")
            workflow_display_options = list(WORKFLOW_DISPLAY_TO_BACKEND.keys())
            workflow_display_index = workflow_display_options.index(current_workflow_display) if current_workflow_display in workflow_display_options else 2

            new_workflow_display = st.selectbox(
                "Workflow Type",
                workflow_display_options,
                index=workflow_display_index,
                help="Select the workflow this agent will be used for"
            )

            # Map to backend value
            new_workflow_type = WORKFLOW_DISPLAY_TO_BACKEND[new_workflow_display]

            new_model = st.selectbox(
                "Model",
                config.get_available_models(),
                index=config.get_available_models().index(agent['model_name']) if agent['model_name'] in config.get_available_models() else 0
            )
            new_temperature = st.slider("Temperature", 0.0, 1.0, agent['temperature'], 0.1)
            new_max_tokens = st.number_input("Max Tokens", 100, 32000, agent['max_tokens'], 100)

        with col2:
            new_description = st.text_area("Description", value=agent.get('description', ''), height=100)
            new_is_active = st.checkbox("Active", value=agent['is_active'])

        new_system_prompt = st.text_area("System Prompt", value=agent['system_prompt'], height=200)
        new_user_prompt = st.text_area("User Prompt Template", value=agent['user_prompt_template'], height=200)

        submitted = st.form_submit_button("Update Agent", type="primary")

        if submitted:
            payload = {
                "name": new_name,
                "workflow_type": new_workflow_type,
                "model_name": new_model,
                "system_prompt": new_system_prompt,
                "user_prompt_template": new_user_prompt,
                "temperature": new_temperature,
                "max_tokens": new_max_tokens,
                "is_active": new_is_active,
                "description": new_description if new_description else None
            }

            try:
                with st.spinner("Updating agent..."):
                    api_client.put(f"{TEST_PLAN_AGENT_API}/{agent['id']}", data=payload)
                    st.success("Agent updated successfully!")
                    # Clear cache
                    for key in list(st.session_state.keys()):
                        if key.startswith("agents_"):
                            del st.session_state[key]
                    st.rerun()
            except Exception as e:
                st.error(f"Error updating agent: {str(e)}")


def render_clone_agent(agent: Dict):
    """Clone agent form."""
    st.subheader(f"Clone Agent: {agent['name']}")
    st.info("Create a copy of this agent with a new name")

    with st.form("clone_agent_form"):
        new_name = st.text_input("New Agent Name", placeholder=f"{agent['name']} (Copy)")
        created_by = st.text_input("Created By", placeholder="Your name (optional)")

        submitted = st.form_submit_button("Clone Agent", type="primary")

        if submitted:
            if not new_name or len(new_name.strip()) < 3:
                st.error("New name must be at least 3 characters")
            else:
                payload = {"new_name": new_name.strip(), "created_by": created_by.strip() if created_by else None}
                try:
                    with st.spinner("Cloning agent..."):
                        api_client.post(f"{TEST_PLAN_AGENT_API}/{agent['id']}/clone", data=payload)
                        st.success(f"Agent cloned as '{new_name}'!")
                        for key in list(st.session_state.keys()):
                            if key.startswith("agents_"):
                                del st.session_state[key]
                        st.rerun()
                except Exception as e:
                    st.error(f"Error cloning agent: {str(e)}")


def render_toggle_active(agent: Dict):
    """Toggle agent active status."""
    st.subheader(f"Toggle Active Status: {agent['name']}")

    current_status = "Active" if agent['is_active'] else "Inactive"
    new_status = "Inactive" if agent['is_active'] else "Active"
    new_is_active = not agent['is_active']

    st.info(f"Current status: **{current_status}**")
    st.warning(f"This will change the status to: **{new_status}**")

    if st.button(f"Confirm: Set to {new_status}", type="primary"):
        try:
            with st.spinner(f"Setting agent to {new_status}..."):
                # Use the activate endpoint with is_active boolean
                api_client.post(f"{TEST_PLAN_AGENT_API}/{agent['id']}/activate", data={"is_active": new_is_active})
                st.success(f"Agent is now {new_status}")
                for key in list(st.session_state.keys()):
                    if key.startswith("agents_"):
                        del st.session_state[key]
                st.rerun()
        except Exception as e:
            st.error(f"Error updating status: {str(e)}")


def render_delete_agent(agent: Dict):
    """Delete agent with two-step workflow: deactivate first, then permanent delete."""
    st.subheader(f"Delete Agent: {agent['name']}")

    if agent['is_system_default']:
        st.error("Cannot delete system default agents")
        return

    # Two-step delete process
    if agent['is_active']:
        st.warning("**STEP 1: Deactivate First**")
        st.info("This agent is currently active. You must deactivate it before permanently deleting it.")

        with st.expander("Agent Details", expanded=True):
            st.json({
                "ID": agent['id'],
                "Name": agent['name'],
                "Type": agent['agent_type'],
                "Status": "ACTIVE",
                "Created": agent.get('created_at')
            })

        if st.button("Deactivate Agent", type="primary"):
            try:
                with st.spinner("Deactivating agent..."):
                    # Use the activate endpoint with is_active=False
                    api_client.post(f"{TEST_PLAN_AGENT_API}/{agent['id']}/activate", data={"is_active": False})
                    st.success("Agent deactivated. You can now permanently delete it if needed.")
                    # Clear cache
                    for key in list(st.session_state.keys()):
                        if key.startswith("agents_") or key == "manage_agent_selector":
                            del st.session_state[key]
                    st.rerun()
            except Exception as e:
                st.error(f"Error deactivating agent: {str(e)}")

    else:
        # Agent is already deactivated, allow permanent deletion
        st.error("**STEP 2: Permanent Deletion**")
        st.warning("This agent is deactivated. You can now permanently delete it if needed.")
        st.warning("**⚠️ PERMANENT ACTION**: Deleting an agent cannot be undone.")

        with st.expander("Agent to be deleted", expanded=True):
            st.json({
                "ID": agent['id'],
                "Name": agent['name'],
                "Type": agent['agent_type'],
                "Status": "INACTIVE",
                "Created": agent.get('created_at')
            })

        confirm_name = st.text_input(f"Type '{agent['name']}' to confirm permanent deletion:")
        confirm_check = st.checkbox("I understand this action is permanent and cannot be undone")

        if confirm_name == agent['name'] and confirm_check:
            if st.button("⚠️ Permanently Delete Agent", type="secondary"):
                try:
                    with st.spinner("Permanently deleting agent..."):
                        # Use soft_delete=false for permanent deletion
                        api_client.delete(f"{TEST_PLAN_AGENT_API}/{agent['id']}?soft_delete=false")
                        st.success("Agent permanently deleted")
                        # Clear all agent-related cache and selector state
                        for key in list(st.session_state.keys()):
                            if key.startswith("agents_") or key == "manage_agent_selector":
                                del st.session_state[key]
                        st.rerun()
                except Exception as e:
                    st.error(f"Error deleting agent: {str(e)}")


def render_help_info():
    """Display comprehensive help and best practices with detailed template variable guide."""
    st.subheader("Agent Management Guide")

    # Create tabs for different sections
    help_tab1, help_tab2, help_tab3, help_tab4 = st.tabs([
        "Template Variables",
        "Workflow Guide",
        "Best Practices",
        "Common Mistakes"
    ])

    with help_tab1:
        st.markdown("## Template Variable Quick Reference")
        st.info("Template variables are placeholders in your prompts that get replaced with actual data during execution.")

        # Quick reference table
        st.markdown("""
        ### Available Template Variables by Workflow

        | Variable | Workflow | Stage Availability | Description |
        |----------|----------|-------------------|-------------|
        | `{data_sample}` | document_analysis | Always | The complete document content to analyze |
        | `{section_title}` | test_plan_generation | All stages | Title of the current section being processed |
        | `{section_content}` | test_plan_generation | All stages | Full content of the current section |
        | `{actor_outputs}` | test_plan_generation | After actor stage | Combined output from all actor agents |
        | `{critic_output}` | test_plan_generation | After critic stage | Synthesized critic output |
        | `{context}` | test_plan_generation | All stages | All previous stage outputs combined |
        """)

        st.markdown("---")

        # Stage execution order diagram
        st.markdown("### Stage Execution Order & Variable Availability")
        st.code("""
Test Plan Generation Pipeline:

┌─────────────────────────────────────────────────────────┐
│ Stage 1: Actor Stage                                    │
│ ├─ Agent 1 (Actor) ──┐                                  │
│ ├─ Agent 2 (Actor) ──┼─► {actor_outputs} populated     │
│ └─ Agent 3 (Actor) ──┘                                  │
│                                                          │
│ Available variables: {section_title}, {section_content} │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│ Stage 2: Critic Stage                                   │
│ └─ Agent 4 (Critic) ────► {critic_output} populated    │
│                                                          │
│ Available variables: {section_title}, {section_content},│
│                     {actor_outputs}, {context}          │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│ Stage 3+: QA/Contradiction/Gap Analysis Stages          │
│ └─ Additional agents ────► Additional outputs           │
│                                                          │
│ Available variables: ALL previous stage outputs         │
│ ({section_title}, {section_content}, {actor_outputs},   │
│  {critic_output}, {context})                            │
└─────────────────────────────────────────────────────────┘
        """, language="text")

        st.markdown("---")

        # RAG context explanation
        st.markdown("### RAG Context (NOT a Template Variable)")
        st.warning("""
        **IMPORTANT**: RAG context is NOT a placeholder variable you can use!

        RAG context is automatically prepended to your input when you use RAG collections.
        You don't need to reference it in your prompts.
        """)

        st.markdown("**How RAG Context Works:**")
        st.code("""
When RAG is enabled, the system automatically constructs:

## Reference Context (from {collection_name})
[Retrieved document 1]
[Retrieved document 2]
[Retrieved document 3]
---
## User Query/Content
{Your actual input with template variables filled in}
        """, language="text")

        st.info("The RAG context is invisible to your prompt templates. Just write your prompts normally using the available template variables.")

        st.markdown("---")

        # Workflow-specific examples
        st.markdown("### Complete Examples by Workflow")

        with st.expander("Document Analysis Workflow Example", expanded=False):
            st.markdown("**Use Case**: Single-agent compliance checking")
            st.code("""
# System Prompt
You are a compliance expert specializing in military standards and
technical documentation. Your role is to:

- Analyze documents for compliance with specified standards
- Identify violations, gaps, and areas of concern
- Provide clear, actionable recommendations
- Reference specific sections and requirements

# User Prompt Template
Analyze the following document for compliance with MIL-STD requirements:

{data_sample}

Identify any violations, missing requirements, or areas that need attention.
Provide specific references to the standard sections.
            """, language="text")

        with st.expander("Test Plan Generation - Actor Agent Example", expanded=False):
            st.markdown("**Use Case**: First stage agent that extracts requirements")
            st.code("""
# System Prompt
You are a systems engineering expert specializing in test plan development.
Your role is to analyze military standard sections and extract testable
requirements. For each requirement you identify:

- Provide a clear test title
- Specify test methodology
- Define acceptance criteria
- Identify required resources

# User Prompt Template
Analyze the following section and extract all testable requirements:

## Section: {section_title}

{section_content}

For each testable requirement, provide:
1. Test ID and title
2. Test methodology
3. Acceptance criteria
4. Required resources and equipment
            """, language="text")

        with st.expander("Test Plan Generation - Critic Agent Example", expanded=False):
            st.markdown("**Use Case**: Second stage agent that synthesizes actor outputs")
            st.code("""
# System Prompt
You are a senior test engineer responsible for synthesizing and
consolidating test requirements from multiple analysts. Your role is to:

- Review outputs from multiple actor agents
- Identify and remove duplicate test cases
- Resolve conflicts between different interpretations
- Create a unified, coherent test plan
- Ensure comprehensive coverage

# User Prompt Template
Review and synthesize the following test requirement analyses from
multiple actor agents:

{actor_outputs}

Your task:
1. Remove duplicate test cases
2. Resolve any conflicts or contradictions
3. Merge similar requirements
4. Create a consolidated, deduplicated list
5. Ensure all critical requirements are covered

Output a unified test plan with no duplicates.
            """, language="text")

        with st.expander("Test Plan Generation - QA/Gap Analysis Example", expanded=False):
            st.markdown("**Use Case**: Later stage agent using all previous outputs")
            st.code("""
# System Prompt
You are a quality assurance specialist focused on identifying gaps
and missing test coverage. You review synthesized test plans and
identify areas that need additional testing.

# User Prompt Template
Review the following synthesized test plan and identify any gaps:

## Original Section
{section_title}
{section_content}

## Synthesized Test Plan
{critic_output}

Identify:
1. Missing test scenarios
2. Untested edge cases
3. Gaps in coverage
4. Additional verification needs
            """, language="text")

    with help_tab2:
        st.markdown("## Understanding Workflow Type vs Agent Type")

        st.markdown("### Workflow Type (PURPOSE)")
        st.info("**What workflow will use this agent?**")

        st.markdown("""
        #### Direct Query (Single Agent)
        - **Purpose**: Single-agent compliance checks on existing documents
        - **Backend Name**: `document_analysis`
        - **API Endpoint**: `/api/agent/compliance-check`
        - **Available Variables**: `{data_sample}`
        - **Use Cases**:
          - Compliance checking against standards
          - Requirements extraction
          - Technical documentation review
          - Gap analysis on existing documents
          - Direct Chat → Chat with AI tab

        #### Agent Pipeline (Multi-Stage)
        - **Purpose**: Multi-agent pipeline to create comprehensive test plans
        - **Backend Name**: `test_plan_generation`
        - **API Endpoint**: `/api/doc/generate_optimized_test_plan`
        - **Available Variables**: `{section_title}`, `{section_content}`, `{actor_outputs}`, `{critic_output}`, `{context}`
        - **Use Cases**:
          - Generate test plans from military standards
          - Multi-stage analysis with actor/critic pattern
          - Contradiction detection across sections
          - Gap analysis in generated test plans
          - Direct Chat → Agent Pipeline tab

        #### Custom
        - **Purpose**: Flexible agents for custom workflows
        - **Backend Name**: `general`
        - **Available Variables**: Custom placeholders as needed
        - **Use Cases**:
          - Custom analysis workflows
          - Specialized review processes
          - Experimental agent configurations
        """)

        st.markdown("---")

        st.markdown("### Agent Type (ROLE)")
        st.info("**What role does this agent play within its workflow?**")

        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown("#### Test Plan Generation")
            st.markdown("""
            - **Actor**: Extracts testable requirements (runs first, in parallel)
            - **Critic**: Synthesizes actor outputs (runs after actors)
            - **Contradiction**: Detects conflicts across sections
            - **Gap Analysis**: Identifies missing test coverage
            """)

        with col2:
            st.markdown("#### Document Analysis")
            st.markdown("""
            - **Compliance**: Evaluates compliance with standards
            - **Custom**: Specialized analysis tasks
            """)

        with col3:
            st.markdown("#### General")
            st.markdown("""
            - **General**: Multi-purpose engineering agent
            - **Rule Development**: Document analysis specialist
            - **Custom**: User-defined behavior
            """)

        st.markdown("---")

        st.markdown("### Creating Agents: Quick Start")
        st.success("""
        **Recommended Workflow:**

        1. Go to the **Create Agent** tab
        2. Select your **Workflow Type** (determines which placeholders are available)
        3. Select your **Agent Type** (determines the agent's role)
        4. Review the auto-populated template from system defaults
        5. Customize the prompts for your specific needs
        6. Give it a unique, descriptive name
        7. Click **Create Agent**

        **Alternative:** Clone an existing agent from the **Manage Agents** tab
        """)

    with help_tab3:
        st.markdown("## Best Practices")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("### System Prompts")
            st.markdown("""
            **Purpose**: Define the agent's role, expertise, and behavior

            **Best Practices**:
            - Define clear expertise areas
            - Include specific analysis frameworks
            - Specify output formats and structure
            - Reference relevant standards or methodologies
            - Use bullet points for clarity
            - Keep it concise but comprehensive (200-500 words)

            **Example Structure**:
            ```
            You are a [role] specializing in [domain].
            Your expertise includes:
            - [Skill 1]
            - [Skill 2]

            Your responsibilities:
            - [Task 1]
            - [Task 2]

            Output format:
            - [Format requirement 1]
            - [Format requirement 2]
            ```
            """)

            st.markdown("### Temperature Settings")
            st.markdown("""
            - **0.0-0.3**: Highly deterministic, factual
              - Use for: Compliance checking, requirement extraction
            - **0.4-0.7**: Balanced creativity and consistency
              - Use for: General analysis, test plan generation
            - **0.8-1.0**: Creative and varied
              - Use for: Brainstorming, exploratory analysis
            """)

        with col2:
            st.markdown("### User Prompt Templates")
            st.markdown("""
            **Purpose**: Template that gets filled with actual data during execution

            **Critical Rules**:
            - **ALWAYS** use correct placeholders for your workflow type
            - Document Analysis → `{data_sample}` only
            - Test Plan Generation → stage-appropriate variables
            - Provide clear, specific instructions
            - Specify desired output structure
            - Include examples when helpful

            **Example Structure**:
            ```
            Analyze the following [document type]:

            {appropriate_placeholder}

            Your task:
            1. [Specific task 1]
            2. [Specific task 2]

            Output format:
            - [Format details]
            ```
            """)

            st.markdown("### Model Selection")
            st.markdown("""
            - **GPT-4**: Best quality, recommended for complex analysis
            - **GPT-4o**: Faster, good for simpler or repetitive tasks
            - **Claude**: Alternative with different strengths
            - **Consider**: Cost vs. quality trade-offs for your use case
            """)

        st.markdown("---")

        st.markdown("### Management Tips")
        st.info("""
        - Use system default agents as starting templates
        - Clone agents before making major experimental changes
        - Test new agents on sample data before production use
        - Review agent performance regularly
        - Deactivate unused agents to keep the system clean
        - Document custom agents with clear descriptions
        - Version agent names when making significant changes (e.g., "Actor v2")
        """)

    with help_tab4:
        st.markdown("## Common Mistakes to Avoid")

        st.error("""
        ### 1. Using `{rag_context}` as a Placeholder

        **WRONG:**
        ```
        Review the following context:
        {rag_context}

        Now analyze: {data_sample}
        ```

        **WHY IT'S WRONG**: `{rag_context}` is NOT a valid template variable.
        RAG context is automatically prepended by the system when RAG is enabled.

        **CORRECT:**
        ```
        Analyze the following document:
        {data_sample}
        ```

        The RAG context will be automatically added if RAG is enabled.
        """)

        st.error("""
        ### 2. Using Stage-Specific Variables in Wrong Stages

        **WRONG (Actor Agent):**
        ```
        Review the actor outputs:
        {actor_outputs}

        Section: {section_title}
        ```

        **WHY IT'S WRONG**: `{actor_outputs}` doesn't exist yet in the actor stage!
        Actors run FIRST.

        **CORRECT (Actor Agent):**
        ```
        Analyze the following section:

        ## {section_title}
        {section_content}
        ```
        """)

        st.error("""
        ### 3. Forgetting Required Placeholders

        **WRONG (Document Analysis):**
        ```
        Perform a compliance check on the document.
        ```

        **WHY IT'S WRONG**: No `{data_sample}` placeholder!
        The agent won't receive any document content.

        **CORRECT:**
        ```
        Perform a compliance check on the following document:

        {data_sample}
        ```
        """)

        st.error("""
        ### 4. Using Wrong Workflow Type for Your Use Case

        **WRONG**: Creating a test plan generation agent with workflow type = "Direct Query (Single Agent)"

        **WHY IT'S WRONG**: The wrong placeholders will be available.
        You won't have access to `{section_title}`, `{actor_outputs}`, etc.

        **CORRECT**: Match workflow type to your actual use case:
        - Creating test plans → "Agent Pipeline (Multi-Stage)"
        - Checking existing docs → "Direct Query (Single Agent)"
        - Custom workflows → "Custom"
        """)

        st.error("""
        ### 5. Overly Vague Prompts

        **WRONG:**
        ```
        Analyze this: {data_sample}
        ```

        **WHY IT'S WRONG**: Agent doesn't know WHAT to analyze for or HOW to format output.

        **CORRECT:**
        ```
        Analyze the following document for compliance with MIL-STD-810:

        {data_sample}

        Identify:
        1. Sections that violate the standard
        2. Missing required elements
        3. Areas needing clarification

        Format each finding as:
        - Issue: [description]
        - Severity: [High/Medium/Low]
        - Recommendation: [action needed]
        ```
        """)

        st.markdown("---")

        st.success("""
        ### Quick Checklist Before Creating Agent

        - [ ] Selected correct workflow_type for my use case
        - [ ] Selected appropriate agent_type for the role
        - [ ] System prompt defines clear expertise and responsibilities
        - [ ] User prompt template uses correct placeholders
        - [ ] User prompt template has clear instructions
        - [ ] Output format is specified
        - [ ] Temperature is appropriate for the task
        - [ ] Agent has a descriptive, unique name
        - [ ] Description field explains the agent's purpose
        """)

# ======================================================================
# AGENT SET MANAGEMENT FUNCTIONS
# ======================================================================

def render_view_agent_sets():
    """View and manage existing agent sets with detailed agent information"""
    st.subheader("Existing Agent Sets")

    # Filter options
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        search_term = st.text_input("Search by name", key="agent_set_search")
    with col2:
        show_inactive = st.checkbox("Show inactive", value=False, key="show_inactive_sets")
    with col3:
        if st.button("🔄 Refresh", use_container_width=True):
            # Clear any cached data and force rerun
            for key in list(st.session_state.keys()):
                if key.startswith(("clone_set_", "edit_set_", "delete_set_")):
                    st.session_state.pop(key)
            st.rerun()

    # Fetch agent sets with include_inactive parameter
    try:
        response = api_client.get(AGENT_SET_API, params={"include_inactive": show_inactive})
        agent_sets = response.get("agent_sets", [])
    except Exception as e:
        st.error(f"Failed to load agent sets: {e}")
        return

    if not agent_sets:
        if show_inactive:
            st.info("No agent sets found (including inactive). Create your first agent set using the 'Create Agent Set' tab!")
        else:
            st.info("No active agent sets found. Try checking 'Show inactive' or create a new agent set!")
        return

    # Apply search filter
    filtered_sets = agent_sets
    if search_term:
        filtered_sets = [s for s in filtered_sets if search_term.lower() in s.get('name', '').lower()]

    # Show filter stats
    active_count = len([s for s in filtered_sets if s.get('is_active', True)])
    inactive_count = len([s for s in filtered_sets if not s.get('is_active', True)])
    st.write(f"**Total Agent Sets:** {len(filtered_sets)} (Active: {active_count}, Inactive: {inactive_count})")

    # Fetch all agents for detailed display
    try:
        agents_response = api_client.get(TEST_PLAN_AGENT_API)
        all_agents = agents_response.get("agents", [])
        agent_map = {a['id']: a for a in all_agents}
    except Exception as e:
        st.warning(f"Could not load agent details: {e}")
        agent_map = {}

    # Display agent sets
    for agent_set in filtered_sets:
        prefix = "[System Default]" if agent_set.get('is_system_default') else "[Custom]"
        status = "[INACTIVE]" if not agent_set.get('is_active', True) else ""
        with st.expander(f"{prefix} {status} {agent_set['name']}", expanded=False):
            col1, col2 = st.columns([3, 1])

            with col1:
                st.write(f"**Description:** {agent_set.get('description', 'No description')}")
                st.write(f"**Type:** {agent_set.get('set_type', 'sequence')}")
                st.write(f"**Usage Count:** {agent_set.get('usage_count', 0)}")
                st.write(f"**Active:** {'Yes' if agent_set.get('is_active') else 'No'}")
                st.write(f"**System Default:** {'Yes' if agent_set.get('is_system_default') else 'No'}")

                # Show pipeline configuration with detailed agent info
                st.write("**Pipeline Stages:**")
                stages = agent_set.get('set_config', {}).get('stages', [])
                for idx, stage in enumerate(stages, 1):
                    st.markdown(f"**Stage {idx}: {stage.get('stage_name')}**")
                    st.write(f"- Execution Mode: {stage.get('execution_mode')}")
                    if stage.get('description'):
                        st.caption(f"{stage.get('description')}")

                    # Show agent details
                    agent_ids = stage.get('agent_ids', [])
                    if agent_ids:
                        agent_counts = Counter(agent_ids)
                        st.write(f"- Agents ({len(agent_ids)} total):")

                        for agent_id, count in agent_counts.items():
                            agent = agent_map.get(agent_id)
                            if agent:
                                with st.container(border=True):
                                    st.markdown(f"**{agent['name']}** (x{count})")

                                    col_a, col_b = st.columns(2)
                                    with col_a:
                                        st.write(f"Type: {agent.get('agent_type', 'N/A')}")
                                        st.write(f"Model: {agent.get('model_name', 'N/A')}")
                                        st.write(f"Temperature: {agent.get('temperature', 0.0)}")
                                    with col_b:
                                        st.write(f"Max Tokens: {agent.get('max_tokens', 'N/A')}")
                                        st.write(f"Active: {'Yes' if agent.get('is_active') else 'No'}")

                                    # Show prompts
                                    with st.expander(f"View Prompts - {agent['name']}"):
                                        st.markdown("**System Prompt:**")
                                        st.code(agent.get('system_prompt', 'No system prompt'), language="text")
                                        st.markdown("**User Prompt Template:**")
                                        st.code(agent.get('user_prompt_template', 'No user prompt template'), language="text")
                            else:
                                st.warning(f"Agent ID {agent_id} not found (x{count})")
                    st.markdown("---")

            with col2:
                st.write("**Actions:**")

                # Clone button
                if st.button("Clone", key=f"clone_{agent_set['id']}"):
                    st.session_state[f'clone_set_{agent_set["id"]}'] = True

                # Edit button (not for system defaults)
                if not agent_set.get('is_system_default'):
                    if st.button("Edit", key=f"edit_{agent_set['id']}"):
                        st.session_state[f'edit_set_{agent_set["id"]}'] = True

                # Activate/Deactivate button
                if agent_set.get('is_active'):
                    if st.button("Deactivate", key=f"deactivate_{agent_set['id']}"):
                        if deactivate_agent_set(agent_set['id']):
                            st.rerun()
                else:
                    if st.button("Activate", key=f"activate_{agent_set['id']}"):
                        if activate_agent_set(agent_set['id']):
                            st.rerun()

                # Delete button (not for system defaults)
                if not agent_set.get('is_system_default'):
                    if st.button("Delete", key=f"delete_{agent_set['id']}", type="secondary"):
                        st.session_state[f'delete_set_{agent_set["id"]}'] = True

            # Handle clone dialog
            if st.session_state.get(f'clone_set_{agent_set["id"]}'):
                st.write("---")
                st.subheader("Clone Agent Set")
                new_name = st.text_input(
                    "New name for cloned set:",
                    value=f"{agent_set['name']} (Copy)",
                    key=f"clone_name_{agent_set['id']}"
                )

                if not new_name or len(new_name.strip()) < 3:
                    st.warning("Name must be at least 3 characters")

                col_a, col_b = st.columns(2)
                with col_a:
                    if st.button("Confirm Clone", key=f"confirm_clone_{agent_set['id']}", type="primary", disabled=not new_name or len(new_name.strip()) < 3):
                        if clone_agent_set(agent_set['id'], new_name.strip()):
                            st.session_state.pop(f'clone_set_{agent_set["id"]}')
                            st.rerun()
                with col_b:
                    if st.button("Cancel Clone", key=f"cancel_clone_{agent_set['id']}"):
                        st.session_state.pop(f'clone_set_{agent_set["id"]}')
                        st.rerun()

            # Handle edit dialog
            if st.session_state.get(f'edit_set_{agent_set["id"]}'):
                st.write("---")
                st.info("Edit functionality: Use the form below to modify the agent set")
                # TODO: Add full edit implementation
                if st.button("Cancel Edit", key=f"cancel_edit_{agent_set['id']}"):
                    st.session_state.pop(f'edit_set_{agent_set["id"]}')
                    st.rerun()

            # Handle delete confirmation dialog
            if st.session_state.get(f'delete_set_{agent_set["id"]}'):
                st.write("---")

                # Two-step delete process
                if agent_set.get('is_active', True):
                    # Step 1: Deactivate first
                    st.warning("**STEP 1: Deactivate First**")
                    st.info(f"This agent set is currently active. You must deactivate it before permanently deleting it.")

                    col_a, col_b = st.columns(2)
                    with col_a:
                        if st.button("Deactivate Agent Set", key=f"deactivate_for_delete_{agent_set['id']}", type="primary"):
                            if deactivate_agent_set(agent_set['id']):
                                st.success("Agent set deactivated. Refresh to see the permanent delete option.")
                                st.session_state.pop(f'delete_set_{agent_set["id"]}')
                                st.rerun()
                    with col_b:
                        if st.button("Cancel", key=f"cancel_delete_{agent_set['id']}"):
                            st.session_state.pop(f'delete_set_{agent_set["id"]}')
                            st.rerun()
                else:
                    # Step 2: Permanent deletion for inactive sets
                    st.error("**STEP 2: Permanent Deletion**")
                    st.warning(f"This agent set is deactivated. You can now permanently delete it if needed.")
                    st.warning("**⚠️ PERMANENT ACTION**: Deleting an agent set cannot be undone.")

                    confirm_name = st.text_input(
                        f"Type '{agent_set['name']}' to confirm permanent deletion:",
                        key=f"delete_confirm_name_{agent_set['id']}"
                    )

                    col_a, col_b = st.columns(2)
                    with col_a:
                        if confirm_name == agent_set['name']:
                            if st.button("⚠️ Permanently Delete Agent Set", key=f"confirm_delete_{agent_set['id']}", type="secondary"):
                                if delete_agent_set(agent_set['id'], permanent=True):
                                    # Clean up all session state related to this agent set
                                    st.session_state.pop(f'delete_set_{agent_set["id"]}', None)
                                    st.session_state.pop(f'clone_set_{agent_set["id"]}', None)
                                    st.session_state.pop(f'edit_set_{agent_set["id"]}', None)
                                    st.rerun()
                        else:
                            st.button("⚠️ Permanently Delete Agent Set", key=f"confirm_delete_{agent_set['id']}", type="secondary", disabled=True)
                    with col_b:
                        if st.button("Cancel", key=f"cancel_delete_final_{agent_set['id']}"):
                            st.session_state.pop(f'delete_set_{agent_set["id"]}')
                            st.rerun()


def render_create_agent_set():
    """Create a new agent set"""
    st.subheader("Create New Agent Set")

    # Fetch available agents (outside form)
    try:
        agents_response = api_client.get(TEST_PLAN_AGENT_API)
        available_agents = agents_response.get("agents", [])
        active_agents = [a for a in available_agents if a.get('is_active', True)]
    except Exception as e:
        st.error(f"Failed to load agents: {e}")
        active_agents = []

    if not active_agents:
        st.error("No active agents available. Please create agents first in the 'Individual Agents' tab.")
        return

    # Initialize stages in session state
    if 'new_set_stages' not in st.session_state:
        st.session_state.new_set_stages = []

    # Stage builder (OUTSIDE FORM - has buttons)
    st.markdown("---")
    st.subheader("Pipeline Stages")
    st.info("Add stages to define your pipeline. Each stage can have multiple agents.")

    # Display current stages
    for idx, stage in enumerate(st.session_state.new_set_stages):
        with st.container(border=True):
            st.write(f"**Stage {idx + 1}: {stage['stage_name']}**")
            st.write(f"- Agents: {len(stage['agent_ids'])} ({stage['execution_mode']})")
            if stage.get('description'):
                st.caption(stage['description'])

    # Add stage section (OUTSIDE FORM)
    with st.expander("Add New Stage", expanded=len(st.session_state.new_set_stages) == 0):
        stage_name = st.text_input(
            "Stage Name",
            placeholder="e.g., actor, critic, qa",
            key="new_stage_name"
        )

        stage_desc = st.text_input(
            "Stage Description (optional)",
            placeholder="e.g., 3 actor agents analyze sections in parallel",
            key="new_stage_desc"
        )

        execution_mode = st.selectbox(
            "Execution Mode",
            options=["parallel", "sequential", "batched"],
            help="parallel: all agents run concurrently, sequential: one after another",
            key="new_stage_mode"
        )

        # Agent selector with counts
        agent_options = {f"{a['name']} (ID: {a['id']})": a['id'] for a in active_agents}
        selected_agent_keys = st.multiselect(
            "Select Agents for this Stage",
            options=list(agent_options.keys()),
            help="You can select the same agent multiple times by selecting it once and specifying count below",
            key="new_stage_agents"
        )

        # Allow duplicating agents
        if selected_agent_keys:
            agent_count = st.number_input(
                "Number of instances for first selected agent",
                min_value=1,
                max_value=10,
                value=1,
                help="Use this to run the same agent multiple times (e.g., 3 actor agents)",
                key="new_stage_count"
            )

        if st.button("Add Stage to Pipeline", key="add_stage_btn"):
            if stage_name and selected_agent_keys:
                # Build agent_ids list (with duplicates if count > 1)
                agent_ids = []
                first_agent_id = agent_options[selected_agent_keys[0]]
                agent_ids.extend([first_agent_id] * int(agent_count))
                # Add other agents once
                for key in selected_agent_keys[1:]:
                    agent_ids.append(agent_options[key])

                new_stage = {
                    "stage_name": stage_name,
                    "agent_ids": agent_ids,
                    "execution_mode": execution_mode,
                    "description": stage_desc if stage_desc else None
                }
                st.session_state.new_set_stages.append(new_stage)
                st.success(f"Added stage: {stage_name}")
                st.rerun()
            else:
                st.error("Please provide stage name and select at least one agent")

    # Clear stages button (OUTSIDE FORM)
    if st.session_state.new_set_stages:
        if st.button("Clear All Stages", key="clear_stages"):
            st.session_state.new_set_stages = []
            st.rerun()

    # Agent set creation form (ONLY basic info and submit)
    st.markdown("---")
    st.subheader("Create Agent Set")
    with st.form("create_agent_set_form"):
        set_name = st.text_input(
            "Set Name *",
            placeholder="e.g., My Custom Pipeline",
            help="Unique name for this agent set"
        )

        description = st.text_area(
            "Description",
            placeholder="Describe the purpose and use case for this agent set...",
            help="Optional description"
        )

        set_type = st.selectbox(
            "Set Type",
            options=["sequence", "parallel", "custom"],
            help="sequence: stages run in order, parallel: all agents run at once"
        )

        # Submit button
        submitted = st.form_submit_button("Create Agent Set", type="primary")

        if submitted:
            if not set_name:
                st.error("Please provide a set name")
            elif not st.session_state.new_set_stages:
                st.error("Please add at least one stage")
            else:
                # Create agent set
                set_config = {
                    "stages": st.session_state.new_set_stages
                }

                payload = {
                    "name": set_name,
                    "description": description,
                    "set_type": set_type,
                    "set_config": set_config,
                    "is_system_default": False,
                    "is_active": True
                }

                try:
                    response = api_client.post(AGENT_SET_API, data=payload)
                    st.success(f"Agent set '{set_name}' created successfully!")
                    st.session_state.new_set_stages = []
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to create agent set: {e}")


def render_agent_set_analytics():
    """Show analytics for agent sets"""
    st.subheader("Agent Set Analytics")

    try:
        # Get most used sets
        response = api_client.get(f"{AGENT_SET_API}/most-used/top?limit=10")
        top_sets = response.get("agent_sets", [])

        if top_sets:
            st.write("**Most Used Agent Sets:**")
            for idx, agent_set in enumerate(top_sets, 1):
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.write(f"{idx}. **{agent_set['name']}**")
                    st.caption(agent_set.get('description', 'No description'))
                with col2:
                    st.metric("Usage", agent_set.get('usage_count', 0))
        else:
            st.info("No usage data yet. Start generating documents with agent sets!")

    except Exception as e:
        st.error(f"Failed to load analytics: {e}")


# Helper functions for agent set operations
def clone_agent_set(set_id: int, new_name: str) -> bool:
    """Clone an existing agent set. Returns True on success, False on failure."""
    try:
        response = api_client.post(
            f"{AGENT_SET_API}/{set_id}/clone",
            data={"new_name": new_name}
        )
        if response:
            st.success(f"Agent set cloned as '{new_name}'")
            return True
        else:
            st.error("Failed to clone agent set: No response from API")
            return False
    except Exception as e:
        st.error(f"Failed to clone agent set: {e}")
        return False


def delete_agent_set(set_id: int, permanent: bool = False) -> bool:
    """
    Delete an agent set.

    Args:
        set_id: The ID of the agent set to delete
        permanent: If True, permanently delete. If False, just deactivate (soft delete)

    Returns:
        True on success, False on failure
    """
    try:
        if permanent:
            # Permanent deletion
            response = api_client.delete(f"{AGENT_SET_API}/{set_id}?soft_delete=false")
        else:
            # Soft delete (deactivate)
            response = api_client.delete(f"{AGENT_SET_API}/{set_id}")

        if response:
            st.success(f"Agent set {'permanently deleted' if permanent else 'deactivated'} successfully")
            return True
        else:
            st.error("Failed to delete agent set: No response from API")
            return False
    except Exception as e:
        st.error(f"Failed to delete agent set: {e}")
        return False


def activate_agent_set(set_id: int) -> bool:
    """Activate an agent set. Returns True on success, False on failure."""
    try:
        response = api_client.put(
            f"{AGENT_SET_API}/{set_id}",
            data={"is_active": True}
        )
        if response:
            st.success("Agent set activated")
            return True
        else:
            st.error("Failed to activate agent set: No response from API")
            return False
    except Exception as e:
        st.error(f"Failed to activate agent set: {e}")
        return False


def deactivate_agent_set(set_id: int) -> bool:
    """Deactivate an agent set. Returns True on success, False on failure."""
    try:
        response = api_client.put(
            f"{AGENT_SET_API}/{set_id}",
            data={"is_active": False}
        )
        if response:
            st.success("Agent set deactivated")
            return True
        else:
            st.error("Failed to deactivate agent set: No response from API")
            return False
    except Exception as e:
        st.error(f"Failed to deactivate agent set: {e}")
        return False
