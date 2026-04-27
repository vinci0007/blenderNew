"""Style template system for VBF modeling.

Provides pre-configured style presets for different modeling workflows.
Styles define parameters like bevel amounts, topology preferences, and material workflows.
"""

import json
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Union


class StyleCategory(Enum):
    """Categories of modeling styles."""

    HARD_SURFACE = "hard_surface"
    ORGANIC = "organic"
    STYLIZED = "stylized"
    PROP = "prop"


@dataclass
class BevelSettings:
    """Bevel/chamfer settings for a style."""

    amount: float = 0.0
    segments: int = 2
    profile: float = 0.5


@dataclass
class TopologySettings:
    """Topology generation preferences."""

    type: str = "quad_preferred"  # quad_only, triangle_friendly, animation_ready
    target_face_count: Optional[int] = None
    auto_cleanup: bool = True


@dataclass
class SubdivisionSettings:
    """Subdivision surface settings."""

    type: str = "catmull_clark"  # none, catmull_clark, simple
    levels: int = 2
    use_limit_surface: bool = True


@dataclass
class MaterialWorkflow:
    """Material and texturing workflow."""

    type: str = "pbr_metallic_roughness"  # pbr_metallic_roughness, pbr_subsurface, vertex_color
    uv_scale: float = 1.0
    auto_uv_unwrap: bool = True


@dataclass
class ModelingStyle:
    """Complete style definition for modeling."""

    name: str
    display_name: str
    category: StyleCategory
    description: str
    bevel: BevelSettings = field(default_factory=BevelSettings)
    topology: TopologySettings = field(default_factory=TopologySettings)
    subdivision: SubdivisionSettings = field(default_factory=SubdivisionSettings)
    material: MaterialWorkflow = field(default_factory=MaterialWorkflow)
    preferred_skills: List[str] = field(default_factory=list)
    llm_prompt_prefix: str = ""


# Built-in style templates
BUILTIN_TEMPLATES: Dict[str, ModelingStyle] = {
    "hard_surface_realistic": ModelingStyle(
        name="hard_surface_realistic",
        display_name="Realistic Hard Surface",
        category=StyleCategory.HARD_SURFACE,
        description="Photorealistic hard surface modeling with precise edges and PBR materials",
        bevel=BevelSettings(amount=0.02, segments=3, profile=0.5),
        topology=TopologySettings(type="quad_only", auto_cleanup=True),
        subdivision=SubdivisionSettings(type="catmull_clark", levels=2),
        material=MaterialWorkflow(type="pbr_metallic_roughness", auto_uv_unwrap=True),
        preferred_skills=[
            "extrude_faces",
            "inset_faces",
            "bevel_edges",
            "boolean_tool",
            "sharp_edge_mark",
        ],
        llm_prompt_prefix="Create a photorealistic hard surface model with precise engineering details. ",
    ),
    "stylized_low_poly": ModelingStyle(
        name="stylized_low_poly",
        display_name="Stylized Low Poly",
        category=StyleCategory.STYLIZED,
        description="Low polygon count stylized models suitable for mobile games",
        bevel=BevelSettings(amount=0.0, segments=1),
        topology=TopologySettings(type="triangle_friendly", target_face_count=500),
        subdivision=SubdivisionSettings(type="none", levels=0),
        material=MaterialWorkflow(type="vertex_color", auto_uv_unwrap=False),
        preferred_skills=[
            "create_primitive",
            "move_object",
            "scale_object",
            "assign_vertex_color",
        ],
        llm_prompt_prefix="Create a stylized low poly model with flat shading. Avoid bevels and rounded edges. ",
    ),
    "organic_character": ModelingStyle(
        name="organic_character",
        display_name="Organic Character",
        category=StyleCategory.ORGANIC,
        description="Character modeling with smooth organic forms and animation-ready topology",
        bevel=BevelSettings(amount=0.1, segments=4, profile=0.6),
        topology=TopologySettings(type="animation_ready", auto_cleanup=True),
        subdivision=SubdivisionSettings(type="catmull_clark", levels=3),
        material=MaterialWorkflow(type="pbr_subsurface", uv_scale=1.0),
        preferred_skills=[
            "subdivide_mesh",
            "smooth_vertices",
            "sculpt_displace",
            "symmetrize",
        ],
        llm_prompt_prefix="Create an organic character model with smooth flowing forms suitable for animation. ",
    ),
    "prop_industrial": ModelingStyle(
        name="prop_industrial",
        display_name="Industrial Props",
        category=StyleCategory.PROP,
        description="Medium-poly game props with realistic wear and details",
        bevel=BevelSettings(amount=0.03, segments=2),
        topology=TopologySettings(type="quad_preferred", target_face_count=2000),
        subdivision=SubdivisionSettings(type="catmull_clark", levels=1),
        material=MaterialWorkflow(type="pbr_metallic_roughness"),
        preferred_skills=[
            "bevel_edges",
            "inset_faces",
            "loop_cut",
            "add_edge_split",
        ],
        llm_prompt_prefix="Create a game-ready industrial prop with realistic proportions and wear details. ",
    ),
}


class StyleTemplateManager:
    """Manages style templates including loading custom templates."""

    def __init__(self, config_path: Optional[str] = None):
        self._templates: Dict[str, ModelingStyle] = {}
        self._config_path = config_path or self._default_config_path()
        self._load_templates()

    def _default_config_path(self) -> str:
        """Get default path for custom templates config."""
        package_root = os.path.dirname(os.path.dirname(__file__))
        return os.path.join(
            package_root, "config", "style_templates.json"
        )

    def _load_templates(self) -> None:
        """Load built-in templates and custom templates."""
        # Start with built-in templates
        self._templates = dict(BUILTIN_TEMPLATES)

        # Load custom templates from config file
        if os.path.exists(self._config_path):
            try:
                with open(self._config_path, "r", encoding="utf-8") as f:
                    custom = json.load(f)
                    for name, data in custom.items():
                    # Skip non-dict entries (like _comment)
                        if name.startswith("_") or not isinstance(data, dict):
                            continue
                        if name not in self._templates:
                            self._templates[name] = self._dict_to_style(name, data)
            except (json.JSONDecodeError, KeyError) as e:
                print(f"[VBF] Warning: Failed to load custom templates: {e}")

    def _dict_to_style(self, name: str, data: Dict) -> ModelingStyle:
        """Convert dictionary to ModelingStyle."""
        return ModelingStyle(
            name=name,
            display_name=data.get("display_name", name),
            category=StyleCategory(data.get("category", "prop")),
            description=data.get("description", ""),
            bevel=BevelSettings(**data.get("bevel", {})),
            topology=TopologySettings(**data.get("topology", {})),
            subdivision=SubdivisionSettings(**data.get("subdivision", {})),
            material=MaterialWorkflow(**data.get("material", {})),
            preferred_skills=data.get("preferred_skills", []),
            llm_prompt_prefix=data.get("llm_prompt_prefix", ""),
        )

    def get_style(self, name: str) -> Optional[ModelingStyle]:
        """Get a style by name."""
        return self._templates.get(name)

    def list_styles(self) -> List[str]:
        """List all available style names."""
        return list(self._templates.keys())

    def style_exists(self, name: str) -> bool:
        """Check if a style exists."""
        return name in self._templates

    def get_style_display_info(self, name: str) -> Optional[Dict[str, str]]:
        """Get display information for a style."""
        style = self._templates.get(name)
        if style is None:
            return None
        return {
            "name": style.name,
            "display_name": style.display_name,
            "category": style.category.value,
            "description": style.description,
        }

    def list_all_display_info(self) -> List[Dict[str, str]]:
        """List display info for all styles."""
        return [
            {
                "name": style.name,
                "display_name": style.display_name,
                "category": style.category.value,
                "description": style.description,
            }
            for style in self._templates.values()
        ]

    def apply_style_to_prompt(self, style_name: str, prompt: str) -> str:
        """Apply style prefix to user prompt."""
        style = self._templates.get(style_name)
        if style is None:
            return prompt
        return f"{style.llm_prompt_prefix}{prompt}"

    def get_style_constraints(self, style_name: str) -> Dict[str, Any]:
        """Get style constraints as dictionary for LLM."""
        style = self._templates.get(style_name)
        if style is None:
            return {}

        return {
            "bevel_amount": style.bevel.amount,
            "bevel_segments": style.bevel.segments,
            "bevel_profile": style.bevel.profile,
            "topology_type": style.topology.type,
            "subdivision_type": style.subdivision.type,
            "subdivision_levels": style.subdivision.levels,
            "material_workflow": style.material.type,
            "preferred_skills": style.preferred_skills,
        }


# Global style manager instance
_style_manager: Optional[StyleTemplateManager] = None


def get_style_manager() -> StyleTemplateManager:
    """Get the global style template manager."""
    global _style_manager
    if _style_manager is None:
        _style_manager = StyleTemplateManager()
    return _style_manager


def get_default_style() -> Optional[str]:
    """Get the default style name, if one is enforced globally."""
    return None


def validate_style(style_name: str) -> bool:
    """Validate if a style name is valid."""
    return get_style_manager().style_exists(style_name)


def list_available_styles() -> List[str]:
    """List all available style names."""
    return get_style_manager().list_styles()


def get_style_help_text() -> str:
    """Generate help text for available styles."""
    manager = get_style_manager()
    styles = manager.list_all_display_info()

    lines = ["Available modeling styles:"]
    for style in styles:
        lines.append(f"  - {style['name']}: {style['display_name']} ({style['category']})")
        lines.append(f"    {style['description']}")
    return "\n".join(lines)
