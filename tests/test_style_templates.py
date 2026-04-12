"""Tests for style template system."""

import pytest

from vbf.style_templates import (
    BevelSettings,
    TopologySettings,
    SubdivisionSettings,
    MaterialWorkflow,
    ModelingStyle,
    StyleCategory,
    BUILTIN_TEMPLATES,
    StyleTemplateManager,
    get_style_manager,
    get_default_style,
    validate_style,
    list_available_styles,
    get_style_help_text,
)


class TestBevelSettings:
    """Tests for BevelSettings dataclass."""

    def test_default_values(self):
        """BevelSettings has correct defaults."""
        bs = BevelSettings()
        assert bs.amount == 0.0
        assert bs.segments == 2
        assert bs.profile == 0.5


class TestTopologySettings:
    """Tests for TopologySettings dataclass."""

    def test_default_values(self):
        """TopologySettings has correct defaults."""
        ts = TopologySettings()
        assert ts.type == "quad_preferred"
        assert ts.target_face_count is None
        assert ts.auto_cleanup is True


class TestSubdivisionSettings:
    """Tests for SubdivisionSettings dataclass."""

    def test_default_values(self):
        """SubdivisionSettings has correct defaults."""
        ss = SubdivisionSettings()
        assert ss.type == "catmull_clark"
        assert ss.levels == 2
        assert ss.use_limit_surface is True


class TestMaterialWorkflow:
    """Tests for MaterialWorkflow dataclass."""

    def test_default_values(self):
        """MaterialWorkflow has correct defaults."""
        mw = MaterialWorkflow()
        assert mw.type == "pbr_metallic_roughness"
        assert mw.uv_scale == 1.0
        assert mw.auto_uv_unwrap is True


class TestBuiltinTemplates:
    """Tests for built-in style templates."""

    def test_all_templates_exist(self):
        """All 4 built-in templates exist."""
        assert len(BUILTIN_TEMPLATES) == 4
        assert "hard_surface_realistic" in BUILTIN_TEMPLATES
        assert "stylized_low_poly" in BUILTIN_TEMPLATES
        assert "organic_character" in BUILTIN_TEMPLATES
        assert "prop_industrial" in BUILTIN_TEMPLATES

    def test_hard_surface_realistic(self):
        """Hard surface realistic template configuration."""
        style = BUILTIN_TEMPLATES["hard_surface_realistic"]
        assert style.category == StyleCategory.HARD_SURFACE
        assert style.bevel.amount == 0.02
        assert style.topology.type == "quad_only"
        assert style.subdivision.levels == 2

    def test_stylized_low_poly(self):
        """Stylized low poly template configuration."""
        style = BUILTIN_TEMPLATES["stylized_low_poly"]
        assert style.category == StyleCategory.STYLIZED
        assert style.bevel.amount == 0.0
        assert style.topology.type == "triangle_friendly"

    def test_organic_character(self):
        """Organic character template configuration."""
        style = BUILTIN_TEMPLATES["organic_character"]
        assert style.category == StyleCategory.ORGANIC
        assert style.bevel.amount == 0.1
        assert style.topology.type == "animation_ready"

    def test_template_has_llm_prompt_prefix(self):
        """All templates have LLM prompt prefix."""
        for name, style in BUILTIN_TEMPLATES.items():
            assert len(style.llm_prompt_prefix) > 0


class TestStyleTemplateManager:
    """Tests for StyleTemplateManager."""

    def test_init_loads_builtins(self):
        """Manager loads built-in templates on init."""
        manager = StyleTemplateManager()
        assert len(manager.list_styles()) >= 4

    def test_get_style(self):
        """Can retrieve style by name."""
        manager = StyleTemplateManager()
        style = manager.get_style("hard_surface_realistic")
        assert style is not None
        assert style.name == "hard_surface_realistic"

    def test_get_style_nonexistent(self):
        """Returns None for non-existent style."""
        manager = StyleTemplateManager()
        assert manager.get_style("nonexistent_style") is None

    def test_style_exists(self):
        """Can check if style exists."""
        manager = StyleTemplateManager()
        assert manager.style_exists("hard_surface_realistic") is True
        assert manager.style_exists("fake_style") is False

    def test_list_styles(self):
        """Can list all style names."""
        manager = StyleTemplateManager()
        styles = manager.list_styles()
        assert "hard_surface_realistic" in styles
        assert "stylized_low_poly" in styles

    def test_get_style_display_info(self):
        """Can get display info for a style."""
        manager = StyleTemplateManager()
        info = manager.get_style_display_info("hard_surface_realistic")
        assert info is not None
        assert info["name"] == "hard_surface_realistic"
        assert "display_name" in info
        assert "category" in info

    def test_apply_style_to_prompt(self):
        """Style prefix is applied to prompt."""
        manager = StyleTemplateManager()
        original = "create a radio"
        styled = manager.apply_style_to_prompt("hard_surface_realistic", original)
        assert original in styled
        assert "photorealistic" in styled.lower()

    def test_apply_unknown_style(self):
        """Unknown style returns original prompt."""
        manager = StyleTemplateManager()
        original = "create a cube"
        styled = manager.apply_style_to_prompt("unknown_style", original)
        assert styled == original

    def test_get_style_constraints(self):
        """Can get style constraints as dict."""
        manager = StyleTemplateManager()
        constraints = manager.get_style_constraints("hard_surface_realistic")
        assert constraints["bevel_amount"] == 0.02
        assert constraints["topology_type"] == "quad_only"
        assert "preferred_skills" in constraints


class TestGlobalFunctions:
    """Tests for global module functions."""

    def test_get_default_style(self):
        """Default style is hard_surface_realistic."""
        assert get_default_style() == "hard_surface_realistic"

    def test_validate_style_valid(self):
        """Valid style returns True."""
        assert validate_style("hard_surface_realistic") is True

    def test_validate_style_invalid(self):
        """Invalid style returns False."""
        assert validate_style("fake_style") is False

    def test_list_available_styles(self):
        """Can list available styles globally."""
        styles = list_available_styles()
        assert "hard_surface_realistic" in styles
        assert "stylized_low_poly" in styles

    def test_get_style_help_text(self):
        """Help text includes style names."""
        help_text = get_style_help_text()
        assert "Available modeling styles:" in help_text
        assert "hard_surface_realistic" in help_text

    def test_get_style_manager_singleton(self):
        """get_style_manager returns singleton instance."""
        manager1 = get_style_manager()
        manager2 = get_style_manager()
        assert manager1 is manager2


class TestStyleCategories:
    """Tests for StyleCategory enum."""

    def test_categories(self):
        """All categories exist."""
        assert StyleCategory.HARD_SURFACE.value == "hard_surface"
        assert StyleCategory.ORGANIC.value == "organic"
        assert StyleCategory.STYLIZED.value == "stylized"
        assert StyleCategory.PROP.value == "prop"

    def test_category_in_templates(self):
        """Categories match template definitions."""
        for name, style in BUILTIN_TEMPLATES.items():
            assert isinstance(style.category, StyleCategory)
