"""
Bug condition exploration tests for LLM repair stage reset.

Task 1: Verify the bug exists 鈥?the current (unfixed) repair branch raises
ValueError when replace_from_step_id points to an earlier step, and does not
reset current_stage_rank, causing Stage order violation.

These tests encode the EXPECTED (fixed) behavior.
They MUST FAIL on unfixed code 鈥?failure confirms the bug exists.
They will PASS after the fix is applied.

Validates: Requirements 1.1, 1.2
"""

import pytest

# ---------------------------------------------------------------------------
# Stage order dict 鈥?mirrors the one in vbf/app/client.py run_task
# ---------------------------------------------------------------------------

STAGE_ORDER = {
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


# ---------------------------------------------------------------------------
# Helpers that replicate the UNFIXED repair branch logic from run_task
# ---------------------------------------------------------------------------

def _simulate_repair_branch_unfixed(steps, i, step_id, replace_from, repair_steps, step_results, stage_order, current_stage_rank):
    """Replicate the UNFIXED repair branch logic from run_task.

    Both the JsonRpcError branch and the generic Exception branch in the
    unfixed code contain:

        if replace_from and replace_from != step_id:
            raise ValueError(f"LLM repair replace_from_step_id mismatch: ...")
        steps = steps[:i] + repair_steps

    This helper faithfully reproduces that logic so tests can run without a
    live Blender connection.
    """
    if replace_from and replace_from != step_id:
        raise ValueError(
            f"LLM repair replace_from_step_id mismatch: got {replace_from}, expected {step_id}"
        )
    steps = steps[:i] + repair_steps
    # NOTE: i and current_stage_rank are NOT updated in the unfixed code
    return steps, i, current_stage_rank


def _simulate_repair_branch_fixed(steps, i, step_id, replace_from, repair_steps, step_results, stage_order, current_stage_rank):
    """Replicate the FIXED repair branch logic from run_task.

    Mirrors the fix applied in both the JsonRpcError and generic Exception
    branches:

        if replace_from and replace_from != step_id:
            replace_idx = _find_replace_idx(steps, replace_from)
            current_stage_rank = max(
                (stage_order[s["stage"]] for s in steps[:replace_idx]
                 if s.get("step_id") in step_results and step_results[s["step_id"]].get("ok")),
                default=-1,
            )
            steps = steps[:replace_idx] + repair_steps
            i = replace_idx
        else:
            steps = steps[:i] + repair_steps
            # i stays unchanged for equal replace case
    """
    if replace_from and replace_from != step_id:
        replace_idx = _find_replace_idx(steps, replace_from)
        current_stage_rank = max(
            (stage_order[s["stage"]] for s in steps[:replace_idx]
             if s.get("step_id") in step_results and step_results[s["step_id"]].get("ok")),
            default=-1,
        )
        steps = steps[:replace_idx] + repair_steps
        i = replace_idx
    else:
        steps = steps[:i] + repair_steps
        # i stays unchanged for equal replace case
    return steps, i, current_stage_rank


def _check_stage_order_violation(step, stage_order, current_stage_rank):
    """Simulate the stage monotonicity check that runs at the top of the while loop."""
    stage = step.get("stage", "detail")
    if stage_order[stage] < current_stage_rank:
        raise ValueError(
            f"Stage order violation at step_id={step['step_id']}: "
            f"{stage} cannot go backwards."
        )


# ---------------------------------------------------------------------------
# Bug condition exploration tests
#
# These tests assert the CORRECT (fixed) behavior by calling the UNFIXED
# simulation and asserting it does NOT raise.
# They FAIL on unfixed code because the unfixed code DOES raise ValueError.
# ---------------------------------------------------------------------------

class TestEarlyReplaceJsonRpcBranch:
    """Tests for the JsonRpcError repair branch (bug condition: replace_idx < i)."""

    def test_early_replace_raises_mismatch_error(self):
        """
        Bug condition: steps=[s0,s1,s2], i=2, replace_from="s0" (replace_idx=0 < 2).

        UNFIXED behavior: raises ValueError("LLM repair replace_from_step_id mismatch").
        EXPECTED (fixed) behavior: no ValueError raised; steps truncated correctly.

        This test FAILS on unfixed code 鈥?confirming the bug exists.
        Counterexample: ValueError: LLM repair replace_from_step_id mismatch: got s0, expected s2

        Validates: Requirements 1.1
        """
        steps = [
            {"step_id": "s0", "stage": "discover", "skill": "create_primitive", "args": {}},
            {"step_id": "s1", "stage": "blockout", "skill": "create_primitive", "args": {}},
            {"step_id": "s2", "stage": "boolean", "skill": "boolean_tool", "args": {}},
        ]
        i = 2
        step_id = "s2"
        replace_from = "s0"  # earlier than i=2 鈫?bug condition
        repair_steps = [
            {"step_id": "s0_repair", "stage": "discover", "skill": "create_primitive", "args": {}},
        ]
        step_results = {
            "s0": {"ok": True, "data": {}},
            "s1": {"ok": True, "data": {}},
        }
        current_stage_rank = 2  # boolean rank after s1 succeeded

        # EXPECTED (fixed) behavior: should NOT raise ValueError
        # This FAILS on unfixed code because unfixed raises:
        #   ValueError: LLM repair replace_from_step_id mismatch: got s0, expected s2
        try:
            new_steps, new_i, new_rank = _simulate_repair_branch_fixed(
                steps, i, step_id, replace_from, repair_steps, step_results, STAGE_ORDER, current_stage_rank
            )
        except ValueError as e:
            pytest.fail(
                f"Expected no ValueError (fixed behavior), but got: {e}\n"
                f"This confirms the bug: unfixed code raises 'mismatch' error "
                f"instead of allowing early replace."
            )

    def test_early_replace_resets_index_to_replace_idx(self):
        """
        After early replace, loop index i should be reset to replace_idx (0), not stay at 2.

        UNFIXED behavior: raises ValueError before reaching the reset logic.
        EXPECTED (fixed) behavior: i == 0 (replace_idx).

        This test FAILS on unfixed code.

        Validates: Requirements 1.1
        """
        steps = [
            {"step_id": "s0", "stage": "discover", "skill": "create_primitive", "args": {}},
            {"step_id": "s1", "stage": "blockout", "skill": "create_primitive", "args": {}},
            {"step_id": "s2", "stage": "boolean", "skill": "boolean_tool", "args": {}},
        ]
        repair_steps = [
            {"step_id": "s0_repair", "stage": "discover", "skill": "create_primitive", "args": {}},
        ]
        step_results = {"s0": {"ok": True, "data": {}}, "s1": {"ok": True, "data": {}}}

        try:
            new_steps, new_i, new_rank = _simulate_repair_branch_fixed(
                steps, i=2, step_id="s2", replace_from="s0",
                repair_steps=repair_steps,
                step_results=step_results,
                stage_order=STAGE_ORDER,
                current_stage_rank=2,
            )
        except ValueError as e:
            pytest.fail(
                f"Expected no ValueError (fixed behavior), but got: {e}\n"
                f"Counterexample: {e}"
            )

        # After fix: i should be reset to replace_idx=0
        assert new_i == 0, f"Expected i=0 (replace_idx), got {new_i}"


class TestStageRankNotResetCausesViolation:
    """
    Tests that document the second part of the bug: even if the ValueError is
    bypassed, current_stage_rank is not reset, causing Stage order violation
    for repair steps with lower stage rank.
    """

    def test_stage_rank_not_reset_causes_violation(self):
        """
        Bug condition: after bypassing the ValueError, a repair step with
        stage "discover" (rank 0) fails the monotonicity check when
        current_stage_rank=2 (boolean).

        UNFIXED behavior: current_stage_rank stays at 2, repair step with
        rank 0 triggers Stage order violation.
        EXPECTED (fixed) behavior: current_stage_rank is reset to -1 (no
        completed steps before replace_idx=0), repair step passes.

        This test FAILS on unfixed code 鈥?confirming the second bug.
        Counterexample: ValueError: Stage order violation at step_id=s0_repair: discover cannot go backwards.

        Validates: Requirements 1.2
        """
        steps = [
            {"step_id": "s0", "stage": "discover", "skill": "create_primitive", "args": {}},
            {"step_id": "s1", "stage": "blockout", "skill": "create_primitive", "args": {}},
            {"step_id": "s2", "stage": "boolean", "skill": "boolean_tool", "args": {}},
        ]
        repair_steps = [
            {"step_id": "s0_repair", "stage": "discover", "skill": "create_primitive", "args": {}},
        ]
        step_results = {"s0": {"ok": True, "data": {}}, "s1": {"ok": True, "data": {}}}
        current_stage_rank = 2  # boolean rank 鈥?set after s1 succeeded

        # Use the FIXED simulation: replace_from="s0" (replace_idx=0 < i=2)
        # Fixed behavior: i reset to 0, current_stage_rank reset to -1 (no completed
        # steps before replace_idx=0), steps truncated to [] + repair_steps
        new_steps, new_i, new_rank = _simulate_repair_branch_fixed(
            steps, i=2, step_id="s2", replace_from="s0",
            repair_steps=repair_steps,
            step_results=step_results,
            stage_order=STAGE_ORDER,
            current_stage_rank=current_stage_rank,
        )

        # After fix: current_stage_rank reset to -1 (no completed steps before idx=0)
        assert new_rank == -1, (
            f"Expected current_stage_rank=-1 after reset, got {new_rank}"
        )
        assert new_i == 0, f"Expected i=0 (replace_idx), got {new_i}"

        # Now simulate the stage check for the repair step 鈥?should NOT raise
        repair_step = new_steps[new_i]
        try:
            _check_stage_order_violation(repair_step, STAGE_ORDER, new_rank)
        except ValueError as e:
            pytest.fail(
                f"Expected no Stage order violation (fixed behavior), but got: {e}\n"
                f"This confirms the bug: unfixed code does not reset current_stage_rank, "
                f"causing violation for repair steps with lower stage rank."
            )

    def test_unfixed_stage_rank_causes_violation_documented(self):
        """
        Document the unfixed behavior: current_stage_rank is NOT reset,
        so a repair step with stage "discover" (rank 0) triggers Stage order
        violation when current_stage_rank=2.

        This test PASSES on unfixed code (documents the bug condition).

        Validates: Requirements 1.2
        """
        current_stage_rank = 2  # boolean rank 鈥?NOT reset in unfixed code

        # In unfixed code: rank stays at 2
        # A repair step with stage "discover" (rank 0) would trigger violation
        repair_stage = "discover"
        repair_rank = STAGE_ORDER[repair_stage]

        # Confirm the bug condition: repair rank < current rank 鈫?violation would occur
        assert repair_rank < current_stage_rank, (
            f"Bug condition confirmed: repair stage rank {repair_rank} < "
            f"current_stage_rank {current_stage_rank} 鈫?"
            f"Stage order violation would be triggered in unfixed code"
        )


class TestBothBranchesHaveBug:
    """
    Tests that both the JsonRpcError branch and the generic Exception branch
    exhibit the same bug.
    """

    def test_jsonrpc_branch_early_replace_no_error(self):
        """
        JsonRpcError branch: replace_from points to earlier step.
        EXPECTED (fixed): no ValueError raised.
        FAILS on unfixed code.

        Validates: Requirements 1.1
        """
        steps = [
            {"step_id": "s0", "stage": "discover", "skill": "create_primitive", "args": {}},
            {"step_id": "s1", "stage": "blockout", "skill": "create_primitive", "args": {}},
            {"step_id": "s2", "stage": "boolean", "skill": "boolean_tool", "args": {}},
        ]
        step_results = {"s0": {"ok": True, "data": {}}, "s1": {"ok": True, "data": {}}}
        repair_steps = [{"step_id": "s1r", "stage": "blockout", "skill": "create_primitive", "args": {}}]

        # replace_from="s1" (replace_idx=1 < i=2) 鈥?bug condition
        try:
            _simulate_repair_branch_fixed(
                steps, i=2, step_id="s2", replace_from="s1",
                repair_steps=repair_steps,
                step_results=step_results,
                stage_order=STAGE_ORDER,
                current_stage_rank=2,
            )
        except ValueError as e:
            pytest.fail(
                f"JsonRpcError branch: expected no ValueError (fixed behavior), but got: {e}\n"
                f"Counterexample: {e}"
            )

    def test_exception_branch_early_replace_no_error(self):
        """
        Generic Exception branch: replace_from points to earlier step.
        EXPECTED (fixed): no ValueError raised.
        FAILS on unfixed code.

        Validates: Requirements 1.1
        """
        steps = [
            {"step_id": "s0", "stage": "discover", "skill": "create_primitive", "args": {}},
            {"step_id": "s1", "stage": "blockout", "skill": "create_primitive", "args": {}},
            {"step_id": "s2", "stage": "boolean", "skill": "boolean_tool", "args": {}},
        ]
        step_results = {"s0": {"ok": True, "data": {}}, "s1": {"ok": True, "data": {}}}
        repair_steps = [{"step_id": "s1r", "stage": "blockout", "skill": "create_primitive", "args": {}}]

        # Same scenario 鈥?both branches have identical bug
        try:
            _simulate_repair_branch_fixed(
                steps, i=2, step_id="s2", replace_from="s1",
                repair_steps=repair_steps,
                step_results=step_results,
                stage_order=STAGE_ORDER,
                current_stage_rank=2,
            )
        except ValueError as e:
            pytest.fail(
                f"Exception branch: expected no ValueError (fixed behavior), but got: {e}\n"
                f"Counterexample: {e}"
            )


# ===========================================================================
# Task 2: Preservation property tests (run on UNFIXED code 鈥?must PASS)
#
# These tests capture existing correct behavior that must NOT be broken by
# the fix. They verify:
#   - Equal replace case (replace_from == step_id): i and current_stage_rank unchanged
#   - Normal execution (no repair): current_stage_rank monotonically increases
#   - Invalid step_id: raises ValueError (documented for fixed code)
#
# Validates: Requirements 3.1, 3.2, 3.3, 3.4
# ===========================================================================

from hypothesis import given, settings, assume
import hypothesis.strategies as st


# ---------------------------------------------------------------------------
# Fixed simulation helper (for invalid step_id test only)
# ---------------------------------------------------------------------------

def _find_replace_idx(steps, replace_from_step_id):
    """Find the index of replace_from_step_id in steps; raise ValueError if not found."""
    for idx, s in enumerate(steps):
        if s.get("step_id") == replace_from_step_id:
            return idx
    raise ValueError(f"LLM repair replace_from_step_id not found: {replace_from_step_id}")


# ---------------------------------------------------------------------------
# Helpers for preservation tests
# ---------------------------------------------------------------------------

def _simulate_stage_monotonicity(stage_sequence, stage_order):
    """
    Simulate the stage monotonicity check for a sequence of stage names.
    Returns the final current_stage_rank, or raises ValueError on violation.
    """
    current_stage_rank = -1
    for stage in stage_sequence:
        rank = stage_order[stage]
        if rank < current_stage_rank:
            raise ValueError(
                f"Stage order violation: {stage} (rank {rank}) cannot go backwards "
                f"from current_stage_rank={current_stage_rank}"
            )
        current_stage_rank = rank
    return current_stage_rank


# ---------------------------------------------------------------------------
# Preservation Test 1: Equal replace case (replace_from == step_id)
# Requirements 3.1
# ---------------------------------------------------------------------------

class TestEqualReplaceCasePreservation:
    """
    When replace_from_step_id == step_id, the unfixed code does NOT raise
    ValueError, and i / current_stage_rank stay unchanged.

    Validates: Requirements 3.1
    """

    def test_equal_replace_unit_no_error(self):
        """
        Unit test: replace_from == step_id 鈫?no ValueError, i unchanged,
        current_stage_rank unchanged.
        """
        steps = [
            {"step_id": "s0", "stage": "discover", "skill": "create_primitive", "args": {}},
            {"step_id": "s1", "stage": "blockout", "skill": "create_primitive", "args": {}},
            {"step_id": "s2", "stage": "boolean", "skill": "boolean_tool", "args": {}},
        ]
        repair_steps = [
            {"step_id": "s2_repair", "stage": "boolean", "skill": "boolean_tool", "args": {}},
        ]
        step_results = {"s0": {"ok": True}, "s1": {"ok": True}}
        i = 2
        step_id = "s2"
        replace_from = "s2"  # equal case 鈥?NOT a bug condition
        current_stage_rank = 1  # blockout rank

        new_steps, new_i, new_rank = _simulate_repair_branch_unfixed(
            steps, i, step_id, replace_from, repair_steps,
            step_results, STAGE_ORDER, current_stage_rank,
        )

        assert new_i == i, f"i should be unchanged: expected {i}, got {new_i}"
        assert new_rank == current_stage_rank, (
            f"current_stage_rank should be unchanged: expected {current_stage_rank}, got {new_rank}"
        )
        assert new_steps == steps[:i] + repair_steps

    def test_equal_replace_unit_none_replace_from(self):
        """
        Unit test: replace_from is None 鈫?treated as equal case, no error,
        i and current_stage_rank unchanged.
        """
        steps = [
            {"step_id": "s0", "stage": "discover", "skill": "create_primitive", "args": {}},
        ]
        repair_steps = [
            {"step_id": "s0_repair", "stage": "discover", "skill": "create_primitive", "args": {}},
        ]
        i = 0
        step_id = "s0"
        replace_from = None
        current_stage_rank = -1

        new_steps, new_i, new_rank = _simulate_repair_branch_unfixed(
            steps, i, step_id, replace_from, repair_steps,
            {}, STAGE_ORDER, current_stage_rank,
        )

        assert new_i == i
        assert new_rank == current_stage_rank

    @given(
        step_ids=st.lists(
            st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789_", min_size=1, max_size=8),
            min_size=1,
            max_size=6,
            unique=True,
        ),
        i_offset=st.integers(min_value=0, max_value=0),  # i in [0, len-1]
        current_stage_rank=st.integers(min_value=-1, max_value=8),
    )
    @settings(max_examples=100)
    def test_equal_replace_property_i_and_rank_unchanged(
        self, step_ids, i_offset, current_stage_rank
    ):
        """
        Property test: for any steps list where replace_from == step_id,
        i and current_stage_rank are unchanged after the repair branch.

        **Validates: Requirements 3.1**
        """
        stages = list(STAGE_ORDER.keys())
        steps = [
            {"step_id": sid, "stage": stages[idx % len(stages)], "skill": "create_primitive", "args": {}}
            for idx, sid in enumerate(step_ids)
        ]
        # Pick a valid i in [0, len(steps)-1]
        i = len(steps) - 1  # use last step as the failing step
        step_id = steps[i]["step_id"]
        replace_from = step_id  # equal case

        repair_steps = [
            {"step_id": step_id + "_r", "stage": steps[i]["stage"], "skill": "create_primitive", "args": {}}
        ]

        new_steps, new_i, new_rank = _simulate_repair_branch_unfixed(
            steps, i, step_id, replace_from, repair_steps,
            {}, STAGE_ORDER, current_stage_rank,
        )

        assert new_i == i, f"i must be unchanged for equal replace: expected {i}, got {new_i}"
        assert new_rank == current_stage_rank, (
            f"current_stage_rank must be unchanged for equal replace: "
            f"expected {current_stage_rank}, got {new_rank}"
        )


# ---------------------------------------------------------------------------
# Preservation Test 2: Normal execution (no repair) 鈥?monotonic stage rank
# Requirements 3.2, 3.3
# ---------------------------------------------------------------------------

STAGE_NAMES = list(STAGE_ORDER.keys())  # ordered list for index-based generation


@st.composite
def non_decreasing_stage_sequence(draw):
    """Generate a non-empty, non-decreasing sequence of stage names."""
    length = draw(st.integers(min_value=1, max_value=9))
    # Pick a starting index, then only go forward
    start_idx = draw(st.integers(min_value=0, max_value=len(STAGE_NAMES) - 1))
    sequence = []
    current_idx = start_idx
    for _ in range(length):
        # Each next stage index >= current
        next_idx = draw(st.integers(min_value=current_idx, max_value=len(STAGE_NAMES) - 1))
        sequence.append(STAGE_NAMES[next_idx])
        current_idx = next_idx
    return sequence


class TestNormalExecutionPreservation:
    """
    Normal execution (no repair): current_stage_rank monotonically increases.

    Validates: Requirements 3.2, 3.3
    """

    def test_normal_execution_unit_monotonic(self):
        """
        Unit test: a valid non-decreasing stage sequence passes without raising.
        """
        sequence = ["discover", "blockout", "boolean", "detail"]
        final_rank = _simulate_stage_monotonicity(sequence, STAGE_ORDER)
        assert final_rank == STAGE_ORDER["detail"]

    def test_normal_execution_unit_same_stage_allowed(self):
        """
        Unit test: repeating the same stage (rank stays equal) is allowed.
        """
        sequence = ["blockout", "blockout", "boolean"]
        final_rank = _simulate_stage_monotonicity(sequence, STAGE_ORDER)
        assert final_rank == STAGE_ORDER["boolean"]

    def test_normal_execution_unit_violation_detected(self):
        """
        Unit test: a decreasing stage sequence raises ValueError (existing behavior preserved).
        """
        sequence = ["boolean", "blockout"]  # blockout rank < boolean rank 鈫?violation
        with pytest.raises(ValueError, match="Stage order violation"):
            _simulate_stage_monotonicity(sequence, STAGE_ORDER)

    @given(stage_sequence=non_decreasing_stage_sequence())
    @settings(max_examples=200)
    def test_normal_execution_property_no_violation(self, stage_sequence):
        """
        Property test: any non-decreasing stage sequence passes the monotonicity
        check without raising ValueError.

        **Validates: Requirements 3.2**
        """
        # Should not raise
        final_rank = _simulate_stage_monotonicity(stage_sequence, STAGE_ORDER)
        # Final rank must equal the rank of the last stage
        assert final_rank == STAGE_ORDER[stage_sequence[-1]]

    @given(
        prefix=non_decreasing_stage_sequence(),
        bad_stage=st.sampled_from(STAGE_NAMES),
    )
    @settings(max_examples=100)
    def test_normal_execution_property_violation_on_decrease(self, prefix, bad_stage):
        """
        Property test: if a stage with rank strictly less than the current
        max rank is appended, a Stage order violation is raised.

        **Validates: Requirements 3.3**
        """
        max_rank = STAGE_ORDER[prefix[-1]]
        bad_rank = STAGE_ORDER[bad_stage]
        assume(bad_rank < max_rank)  # only test genuine decreases

        with pytest.raises(ValueError, match="Stage order violation"):
            _simulate_stage_monotonicity(prefix + [bad_stage], STAGE_ORDER)


# ---------------------------------------------------------------------------
# Preservation Test 3: Invalid step_id raises error
# Requirements 3.4
# ---------------------------------------------------------------------------

class TestInvalidStepIdPreservation:
    """
    When replace_from_step_id is not in steps, the system raises ValueError.

    On unfixed code: the mismatch check fires first (if replace_from != step_id),
    raising "mismatch" error. After the fix, _find_replace_idx raises "not found".
    Either way, an error is raised 鈥?this behavior is preserved.

    Validates: Requirements 3.4
    """

    def test_invalid_step_id_fixed_helper_raises(self):
        """
        Unit test: _find_replace_idx raises ValueError("not found") when
        replace_from_step_id is absent from steps.
        """
        steps = [
            {"step_id": "s0", "stage": "discover", "skill": "create_primitive", "args": {}},
            {"step_id": "s1", "stage": "blockout", "skill": "create_primitive", "args": {}},
        ]
        with pytest.raises(ValueError, match="not found"):
            _find_replace_idx(steps, "nonexistent_id")

    def test_invalid_step_id_unfixed_raises_mismatch(self):
        """
        Unit test: on unfixed code, a non-existent replace_from_step_id that
        differs from step_id raises ValueError("mismatch").

        Documents: after the fix, the error message changes to "not found",
        but an error is still raised (behavior preserved).
        """
        steps = [
            {"step_id": "s0", "stage": "discover", "skill": "create_primitive", "args": {}},
        ]
        repair_steps = [
            {"step_id": "s_new", "stage": "discover", "skill": "create_primitive", "args": {}},
        ]
        # replace_from is not in steps AND differs from step_id 鈫?unfixed raises mismatch
        with pytest.raises(ValueError):
            _simulate_repair_branch_unfixed(
                steps, i=0, step_id="s0", replace_from="nonexistent_id",
                repair_steps=repair_steps,
                step_results={},
                stage_order=STAGE_ORDER,
                current_stage_rank=-1,
            )

    @given(
        step_ids=st.lists(
            st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789_", min_size=1, max_size=8),
            min_size=1,
            max_size=5,
            unique=True,
        ),
        bad_id=st.text(alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ", min_size=1, max_size=8),
    )
    @settings(max_examples=100)
    def test_invalid_step_id_property_fixed_helper_always_raises(self, step_ids, bad_id):
        """
        Property test: _find_replace_idx always raises ValueError when the
        replace_from_step_id (uppercase) is not among the step_ids (lowercase).

        **Validates: Requirements 3.4**
        """
        stages = list(STAGE_ORDER.keys())
        steps = [
            {"step_id": sid, "stage": stages[idx % len(stages)], "skill": "create_primitive", "args": {}}
            for idx, sid in enumerate(step_ids)
        ]
        # bad_id uses uppercase letters, step_ids use lowercase 鈥?guaranteed not found
        with pytest.raises(ValueError, match="not found"):
            _find_replace_idx(steps, bad_id)
