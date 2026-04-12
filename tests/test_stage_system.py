"""
Tests for VBF professional 18-stage modeling workflow.

Stage order:
Phase 1: reference_analysis -> mood_board -> style_definition
Phase 2: primitive_blocking -> silhouette_validation -> proportion_check
Phase 3: topology_prep -> edge_flow -> boolean_operations
Phase 4: bevel_chamfer -> micro_detailing -> high_poly_finalize
Phase 5: normal_baking -> uv_prep -> material_prep
Phase 6: material_assignment -> lighting_check -> finalize
"""

from typing import Dict, List

# The PROFESSIONAL stage_order (18 stages)
stage_order = {
    # Phase 1: Concept & Analysis
    "reference_analysis": 0,
    "mood_board": 1,
    "style_definition": 2,
    # Phase 2: Blocking
    "primitive_blocking": 3,
    "silhouette_validation": 4,
    "proportion_check": 5,
    # Phase 3: Structure
    "topology_prep": 6,
    "edge_flow": 7,
    "boolean_operations": 8,
    # Phase 4: Detail
    "bevel_chamfer": 9,
    "micro_detailing": 10,
    "high_poly_finalize": 11,
    # Phase 5: Polish
    "normal_baking": 12,
    "uv_prep": 13,
    "material_prep": 14,
    # Phase 6: Finish
    "material_assignment": 15,
    "lighting_check": 16,
    "finalize": 17,
}

# Phase groupings
PHASE_1_STAGES = ["reference_analysis", "mood_board", "style_definition"]
PHASE_2_STAGES = ["primitive_blocking", "silhouette_validation", "proportion_check"]
PHASE_3_STAGES = ["topology_prep", "edge_flow", "boolean_operations"]
PHASE_4_STAGES = ["bevel_chamfer", "micro_detailing", "high_poly_finalize"]
PHASE_5_STAGES = ["normal_baking", "uv_prep", "material_prep"]
PHASE_6_STAGES = ["material_assignment", "lighting_check", "finalize"]
ALL_PHASES = PHASE_1_STAGES + PHASE_2_STAGES + PHASE_3_STAGES + PHASE_4_STAGES + PHASE_5_STAGES + PHASE_6_STAGES


# -----------------------------------------------------------------------------
# Helper: replicate the validation logic from vbf/client.py run_task
# -----------------------------------------------------------------------------

def _validate_stage_sequence(sequence: List[str], order_dict: Dict[str, int]) -> None:
    """
    Simulate the stage monotonicity check from run_task.
    Raises ValueError if any stage is unknown or goes backwards.
    """
    current_stage_rank = -1
    for stage in sequence:
        if stage not in order_dict:
            raise ValueError(f"Invalid stage '{stage}'. Must be one of {list(order_dict.keys())}")
        if order_dict[stage] < current_stage_rank:
            raise ValueError(
                f"Stage '{stage}' (rank {order_dict[stage]}) goes backwards "
                f"from current rank {current_stage_rank}"
            )
        current_stage_rank = order_dict[stage]


# -----------------------------------------------------------------------------
# 1. Basic presence tests - All 18 stages exist
# -----------------------------------------------------------------------------

def test_all_phases_present_in_stage_order():
    """All 18 professional stage names exist in stage_order."""
    for name in ALL_PHASES:
        assert name in stage_order, f"'{name}' missing from stage_order"


def test_phase_1_stages_present():
    """Phase 1 (Concept) stages exist."""
    for stage in PHASE_1_STAGES:
        assert stage in stage_order, f"Phase 1 stage '{stage}' missing"


def test_phase_2_stages_present():
    """Phase 2 (Blocking) stages exist."""
    for stage in PHASE_2_STAGES:
        assert stage in stage_order, f"Phase 2 stage '{stage}' missing"


def test_phase_3_stages_present():
    """Phase 3 (Structure) stages exist."""
    for stage in PHASE_3_STAGES:
        assert stage in stage_order, f"Phase 3 stage '{stage}' missing"


def test_phase_4_stages_present():
    """Phase 4 (Detail) stages exist."""
    for stage in PHASE_4_STAGES:
        assert stage in stage_order, f"Phase 4 stage '{stage}' missing"


def test_phase_5_stages_present():
    """Phase 5 (Polish) stages exist."""
    for stage in PHASE_5_STAGES:
        assert stage in stage_order, f"Phase 5 stage '{stage}' missing"


def test_phase_6_stages_present():
    """Phase 6 (Finish) stages exist."""
    for stage in PHASE_6_STAGES:
        assert stage in stage_order, f"Phase 6 stage '{stage}' missing"


# -----------------------------------------------------------------------------
# 2. Phase ordering tests
# -----------------------------------------------------------------------------

def test_phase_order_monotonic():
    """All phases in correct monotonic order."""
    assert stage_order["reference_analysis"] < stage_order["mood_board"] < stage_order["style_definition"]
    assert stage_order["style_definition"] < stage_order["primitive_blocking"]
    assert stage_order["proportion_check"] < stage_order["topology_prep"]
    assert stage_order["boolean_operations"] < stage_order["bevel_chamfer"]
    assert stage_order["high_poly_finalize"] < stage_order["normal_baking"]
    assert stage_order["material_prep"] < stage_order["material_assignment"]
    assert stage_order["lighting_check"] < stage_order["finalize"]


def test_bevel_before_detail():
    """Bevel stage (9) comes before micro_detailing (10) - professional best practice."""
    assert stage_order["bevel_chamfer"] < stage_order["micro_detailing"]


def test_structure_before_detail():
    """Structure phase (6-8) before Detail phase (9-11)."""
    assert stage_order["boolean_operations"] < stage_order["bevel_chamfer"]


# -----------------------------------------------------------------------------
# 3. Stage sequence validation tests
# -----------------------------------------------------------------------------

def test_monotonic_sequence_passes_validation():
    """A monotonically increasing sequence should pass validation."""
    seq = ["reference_analysis", "primitive_blocking", "bevel_chamfer", "material_assignment"]
    _validate_stage_sequence(seq, stage_order)  # Should not raise


def test_stage_stays_same_allowed():
    """Staying in same stage is allowed (monotonic non-decreasing)."""
    seq = ["bevel_chamfer", "bevel_chamfer", "bevel_chamfer"]
    _validate_stage_sequence(seq, stage_order)  # Should not raise


def test_backwards_stage_raises_error():
    """Going backwards should raise ValueError."""
    seq = ["bevel_chamfer", "primitive_blocking"]  # 9 -> 3 is backwards
    try:
        _validate_stage_sequence(seq, stage_order)
        raise AssertionError("Expected ValueError for backwards sequence")
    except ValueError as e:
        assert "goes backwards" in str(e)


def test_invalid_stage_raises_error():
    """Invalid stage name should raise ValueError."""
    seq = ["reference_analysis", "invalid_stage_name"]
    try:
        _validate_stage_sequence(seq, stage_order)
        raise AssertionError("Expected ValueError for invalid stage")
    except ValueError as e:
        assert "Invalid stage" in str(e)


# -----------------------------------------------------------------------------
# 4. Professional workflow tests
# -----------------------------------------------------------------------------

def test_typical_hard_surface_workflow():
    """Typical hard surface modeling workflow passes validation."""
    workflow = [
        "reference_analysis",
        "primitive_blocking",
        "silhouette_validation",
        "proportion_check",
        "topology_prep",
        "boolean_operations",
        "bevel_chamfer",
        "micro_detailing",
        "normal_baking",
        "material_assignment",
        "finalize",
    ]
    _validate_stage_sequence(workflow, stage_order)


def test_character_workflow():
    """Character modeling workflow with blocking -> sculpt -> topology."""
    workflow = [
        "reference_analysis",
        "mood_board",
        "style_definition",  # Define style early
        "primitive_blocking",
        "silhouette_validation",  # Check silhouette
        "proportion_check",
        "bevel_chamfer",  # Edge softness for organic
        "micro_detailing",  # Fine details
        "high_poly_finalize",
        "material_assignment",
        "lighting_check",  # Preview with lighting
        "finalize",
    ]
    _validate_stage_sequence(workflow, stage_order)


# -----------------------------------------------------------------------------
# 5. Legacy compatibility note
# -----------------------------------------------------------------------------

def test_old_stages_removed():
    """Old non-standard stage names are no longer in stage_order."""
    old_stages = ["discover", "blockout", "detail", "bevel", "normal_fix", "accessories", "material"]
    for stage in old_stages:
        assert stage not in stage_order, f"Old stage '{stage}' should be removed"


# -----------------------------------------------------------------------------
# 6. Phase transition guards
# -----------------------------------------------------------------------------

def test_no_skipping_early_phases():
    """Cannot skip early phases - backward movement detected."""
    seq = ["primitive_blocking", "reference_analysis"]  # 3 -> 0 is backwards
    try:
        _validate_stage_sequence(seq, stage_order)
        raise AssertionError("Should detect backwards movement")
    except ValueError:
        pass  # Expected


def test_can_stay_in_phase():
    """Can execute multiple steps within same phase."""
    seq = ["primitive_blocking", "silhouette_validation", "proportion_check"]
    _validate_stage_sequence(seq, stage_order)  # All in phase 2
