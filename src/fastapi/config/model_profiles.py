"""
Model Profiles Configuration

Defines different model profiles for test plan generation:
- FAST: Uses smaller models (llama3.2:3b) with shorter timeouts for quick drafts
- QUALITY: Uses larger models (gpt-oss:latest) with longer timeouts for production quality
- BALANCED: Middle ground with phi3:mini

These profiles can be selected per-generation to trade off speed vs quality.
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional
from enum import Enum


class ModelProfileType(Enum):
    """Available model profile types"""
    FAST = "fast"
    BALANCED = "balanced"
    QUALITY = "quality"


@dataclass
class ModelProfile:
    """Configuration for a model profile"""
    profile_id: str
    display_name: str
    description: str
    model_name: str
    actor_timeout: int  # seconds per actor call
    critic_timeout: int  # seconds per critic call
    final_critic_timeout: int  # seconds for final consolidation
    temperature: float
    max_tokens: int
    recommended_max_sections: int  # Recommended max sections for reasonable processing time
    chunks_per_section: int  # How many chunks to group per section (smaller = smaller context)
    sectioning_strategy: str  # Sectioning strategy: auto, by_chunks, by_metadata
    max_workers: int = 4  # Max concurrent workers (lower for CPU-only environments)


# Profile definitions - optimized for CPU-only environments
MODEL_PROFILES: Dict[str, ModelProfile] = {
    "fast": ModelProfile(
        profile_id="fast",
        display_name="Fast (CPU-friendly)",
        description="Fastest CPU processing with llama3.2:1b (1.2B). Single worker, minimal overhead.",
        model_name="llama3.2:1b",
        actor_timeout=180,  # 3 minutes (longer for CPU)
        critic_timeout=240,  # 4 minutes
        final_critic_timeout=420,  # 7 minutes
        temperature=0.7,
        max_tokens=1000,  # Reduced for faster generation
        recommended_max_sections=100,
        chunks_per_section=20,  # Larger chunks = fewer sections
        sectioning_strategy="by_chunks",
        max_workers=1  # Single worker to avoid CPU contention
    ),
    "balanced": ModelProfile(
        profile_id="balanced",
        display_name="Balanced",
        description="Better quality with llama3.2:3b (3.2B). Moderate CPU speed.",
        model_name="llama3.2:3b",
        actor_timeout=300,  # 5 minutes
        critic_timeout=420,  # 7 minutes
        final_critic_timeout=600,  # 10 minutes
        temperature=0.7,
        max_tokens=2000,
        recommended_max_sections=100,
        chunks_per_section=10,  # Medium chunks
        sectioning_strategy="by_chunks",
        max_workers=2  # Low concurrency for CPU
    ),
    "quality": ModelProfile(
        profile_id="quality",
        display_name="Quality (Production)",
        description="Best quality with phi3:mini (3.8B). Slower on CPU but thorough.",
        model_name="phi3:mini",
        actor_timeout=420,  # 7 minutes
        critic_timeout=600,  # 10 minutes
        final_critic_timeout=900,  # 15 minutes
        temperature=0.5,
        max_tokens=2500,
        recommended_max_sections=50,
        chunks_per_section=5,  # Smaller chunks for better context
        sectioning_strategy="by_chunks",
        max_workers=1  # Single worker for largest model on CPU
    )
}

# Default profile
DEFAULT_PROFILE = "fast"


def get_model_profile(profile_id: Optional[str] = None) -> ModelProfile:
    """
    Get a model profile by ID.

    Args:
        profile_id: Profile ID (fast, balanced, quality). Defaults to 'fast'.

    Returns:
        ModelProfile configuration
    """
    if profile_id is None:
        profile_id = DEFAULT_PROFILE

    profile_id = profile_id.lower()

    if profile_id not in MODEL_PROFILES:
        # Fall back to default
        profile_id = DEFAULT_PROFILE

    return MODEL_PROFILES[profile_id]


def get_all_profiles() -> Dict[str, ModelProfile]:
    """Get all available model profiles"""
    return MODEL_PROFILES


def get_profile_choices() -> list:
    """
    Get profile choices formatted for UI dropdowns.

    Returns:
        List of dicts with 'value', 'label', 'description' keys
    """
    return [
        {
            "value": profile.profile_id,
            "label": profile.display_name,
            "description": profile.description,
            "model": profile.model_name,
            "recommended_max_sections": profile.recommended_max_sections
        }
        for profile in MODEL_PROFILES.values()
    ]


def estimate_processing_time(num_sections: int, num_actors: int, profile_id: str = "fast") -> Dict[str, Any]:
    """
    Estimate processing time for a generation job.

    Args:
        num_sections: Number of document sections
        num_actors: Number of actor agents (typically 2-4)
        profile_id: Model profile to use

    Returns:
        Dict with estimated times and recommendations
    """
    profile = get_model_profile(profile_id)

    # Rough estimates based on profile
    time_estimates = {
        "fast": {"per_section_min": 10, "per_section_max": 30},
        "balanced": {"per_section_min": 30, "per_section_max": 60},
        "quality": {"per_section_min": 120, "per_section_max": 300}
    }

    est = time_estimates.get(profile_id, time_estimates["fast"])

    # Total calls: sections * actors + sections (critic) + 1 (final critic)
    total_calls = num_sections * num_actors + num_sections + 1

    min_time_seconds = num_sections * est["per_section_min"]
    max_time_seconds = num_sections * est["per_section_max"]

    def format_time(seconds: int) -> str:
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            return f"{seconds // 60}m {seconds % 60}s"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            return f"{hours}h {minutes}m"

    return {
        "profile": profile.display_name,
        "model": profile.model_name,
        "num_sections": num_sections,
        "num_actors": num_actors,
        "total_llm_calls": total_calls,
        "estimated_time_min": format_time(min_time_seconds),
        "estimated_time_max": format_time(max_time_seconds),
        "estimated_seconds_min": min_time_seconds,
        "estimated_seconds_max": max_time_seconds,
        "recommended_max_sections": profile.recommended_max_sections,
        "exceeds_recommendation": num_sections > profile.recommended_max_sections
    }
