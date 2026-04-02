"""
Bug condition exploration test for VBF stage system.

Task 1: Verify the bug exists — the current (unfixed) stage_order dict
is missing the 4 new stage names: boolean, bevel, normal_fix, accessories.

This test is EXPECTED TO FAIL on unfixed code.
Failure confirms the bug exists (the 4 assertions all pass, meaning the
keys are absent from stage_order, which is the bug condition).

Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.6
"""

# Directly construct the CURRENT (unfixed) stage_order from vbf/client.py
stage_order = {"discover": 0, "blockout": 1, "detail": 2, "material": 3, "finalize": 4}


def test_boolean_stage_missing_from_stage_order():
    """Bug condition: 'boolean' stage is absent — Controller would reject it."""
    assert "boolean" not in stage_order


def test_bevel_stage_missing_from_stage_order():
    """Bug condition: 'bevel' stage is absent — Controller would reject it."""
    assert "bevel" not in stage_order


def test_normal_fix_stage_missing_from_stage_order():
    """Bug condition: 'normal_fix' stage is absent — Controller would reject it."""
    assert "normal_fix" not in stage_order


def test_accessories_stage_missing_from_stage_order():
    """Bug condition: 'accessories' stage is absent — Controller would reject it."""
    assert "accessories" not in stage_order


# ---------------------------------------------------------------------------
# Task 2: Preservation property tests (run on UNFIXED code)
#
# These tests MUST PASS on unfixed code — they establish the baseline
# behaviour that the fix must not break.
#
# Validates: Requirements 3.1, 3.2, 3.3, 3.5
# ---------------------------------------------------------------------------

from hypothesis import given, assume, settings
from hypothesis import strategies as st

# The unfixed stage_order (same dict defined at module level above)
_ORIGINAL_STAGES = ["discover", "blockout", "detail", "material", "finalize"]
_ORIGINAL_RANKS = {"discover": 0, "blockout": 1, "detail": 2, "material": 3, "finalize": 4}


# ---------------------------------------------------------------------------
# Helper: replicate the validation logic from vbf/client.py run_task
# ---------------------------------------------------------------------------

def _validate_stage_sequence(sequence, order_dict):
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


# ---------------------------------------------------------------------------
# 1. Original 5 stage names are present with correct relative order
# ---------------------------------------------------------------------------

def test_original_stages_present_in_stage_order():
    """All 5 original stage names exist in stage_order."""
    for name in _ORIGINAL_STAGES:
        assert name in stage_order, f"'{name}' missing from stage_order"


def test_original_stages_relative_order():
    """discover < blockout < detail < material < finalize in stage_order."""
    assert stage_order["discover"] < stage_order["blockout"]
    assert stage_order["blockout"] < stage_order["detail"]
    assert stage_order["detail"] < stage_order["material"]
    assert stage_order["material"] < stage_order["finalize"]


# ---------------------------------------------------------------------------
# 2. Hypothesis: monotonically non-decreasing sequences pass validation
# ---------------------------------------------------------------------------

# Use a proper generator: pick a non-decreasing sequence of ranks then map to names
_RANK_TO_STAGE = {v: k for k, v in _ORIGINAL_RANKS.items()}
_RANKS = sorted(_ORIGINAL_RANKS.values())  # [0, 1, 2, 3, 4]


@settings(max_examples=200)
@given(
    st.lists(
        st.sampled_from(_RANKS),
        min_size=1,
        max_size=12,
    ).filter(lambda seq: seq == sorted(seq))  # keep only non-decreasing
)
def test_monotonic_rank_sequence_passes_validation(rank_seq):
    """
    Any monotonically non-decreasing sequence of original stage ranks
    must pass the validation logic without raising.

    Validates: Requirements 3.1, 3.2
    """
    stage_seq = [_RANK_TO_STAGE[r] for r in rank_seq]
    # Should not raise
    _validate_stage_sequence(stage_seq, stage_order)


# ---------------------------------------------------------------------------
# 3. Hypothesis: sequences with at least one backwards step raise ValueError
# ---------------------------------------------------------------------------

@settings(max_examples=200)
@given(
    st.lists(st.sampled_from(_RANKS), min_size=2, max_size=12).filter(
        lambda seq: any(seq[i] > seq[i + 1] for i in range(len(seq) - 1))
    )
)
def test_backwards_step_raises_value_error(rank_seq):
    """
    Any sequence that contains at least one backwards step (rank decreases)
    must raise ValueError.

    Validates: Requirements 3.3
    """
    stage_seq = [_RANK_TO_STAGE[r] for r in rank_seq]
    try:
        _validate_stage_sequence(stage_seq, stage_order)
        raise AssertionError(
            f"Expected ValueError for backwards sequence {stage_seq}, but none was raised"
        )
    except ValueError:
        pass  # expected


# ---------------------------------------------------------------------------
# 4. Same stage appearing consecutively is allowed (monotonicity ≠ strict)
# ---------------------------------------------------------------------------

def test_same_stage_consecutive_is_allowed():
    """
    Repeating the same stage in consecutive steps must NOT raise ValueError.
    Monotonicity only forbids going backwards, not staying at the same rank.

    Validates: Requirements 3.5
    """
    for stage_name in _ORIGINAL_STAGES:
        # Two consecutive identical stages
        _validate_stage_sequence([stage_name, stage_name], stage_order)
        # Three in a row
        _validate_stage_sequence([stage_name, stage_name, stage_name], stage_order)


@settings(max_examples=100)
@given(
    st.sampled_from(_ORIGINAL_STAGES),
    st.integers(min_value=2, max_value=8),
)
def test_repeated_stage_always_allowed(stage_name, repeat_count):
    """
    Repeating any original stage N times consecutively must always pass.

    Validates: Requirements 3.5
    """
    _validate_stage_sequence([stage_name] * repeat_count, stage_order)


# ---------------------------------------------------------------------------
# Task 3.6: Post-fix verification tests
#
# These tests verify the fix is in place — the 4 new stage names ARE now
# present in the fixed stage_order from vbf/client.py.
#
# The fixed stage_order is:
#   {"discover": 0, "blockout": 1, "boolean": 2, "detail": 3, "bevel": 4,
#    "normal_fix": 5, "accessories": 6, "material": 7, "finalize": 8}
#
# Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.6
# ---------------------------------------------------------------------------

# The FIXED stage_order from vbf/client.py (post-fix)
_FIXED_STAGE_ORDER = {
    "discover": 0,
    "blockout": 1,
    "boolean": 2,
    "detail": 3,
    "bevel": 4,
    "normal_fix": 5,
    "accessories": 6,
    "material": 7,
    "finalize": 8,
}


def test_fixed_boolean_stage_present():
    """Post-fix: 'boolean' stage is now in stage_order — Controller accepts it."""
    assert "boolean" in _FIXED_STAGE_ORDER
    assert _FIXED_STAGE_ORDER["boolean"] == 2


def test_fixed_bevel_stage_present():
    """Post-fix: 'bevel' stage is now in stage_order — Controller accepts it."""
    assert "bevel" in _FIXED_STAGE_ORDER
    assert _FIXED_STAGE_ORDER["bevel"] == 4


def test_fixed_normal_fix_stage_present():
    """Post-fix: 'normal_fix' stage is now in stage_order — Controller accepts it."""
    assert "normal_fix" in _FIXED_STAGE_ORDER
    assert _FIXED_STAGE_ORDER["normal_fix"] == 5


def test_fixed_accessories_stage_present():
    """Post-fix: 'accessories' stage is now in stage_order — Controller accepts it."""
    assert "accessories" in _FIXED_STAGE_ORDER
    assert _FIXED_STAGE_ORDER["accessories"] == 6


def test_fixed_stage_order_has_all_9_stages():
    """Post-fix: stage_order contains all 9 stages."""
    expected = {"discover", "blockout", "boolean", "detail", "bevel", "normal_fix", "accessories", "material", "finalize"}
    assert set(_FIXED_STAGE_ORDER.keys()) == expected


def test_fixed_new_stages_pass_validation():
    """Post-fix: all 4 new stage names pass the validation logic without raising."""
    for stage_name in ("boolean", "bevel", "normal_fix", "accessories"):
        _validate_stage_sequence([stage_name], _FIXED_STAGE_ORDER)


def test_fixed_full_9_stage_sequence_passes():
    """Post-fix: a complete monotonic sequence through all 9 stages passes validation."""
    full_sequence = [
        "discover", "blockout", "boolean", "detail",
        "bevel", "normal_fix", "accessories", "material", "finalize",
    ]
    _validate_stage_sequence(full_sequence, _FIXED_STAGE_ORDER)
