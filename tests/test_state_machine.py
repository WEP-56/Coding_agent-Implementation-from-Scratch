from __future__ import annotations

import pytest

from codinggirl.core.state_machine import RunState


def test_state_machine_happy_path():
    s = RunState(run_id="r1")
    s.transition("PLANNED")
    s.transition("PATCHED")
    s.transition("VERIFIED")
    s.transition("APPLIED")
    s.transition("DONE")
    assert s.status == "DONE"


def test_state_machine_invalid_transition():
    s = RunState(run_id="r2")
    with pytest.raises(ValueError):
        s.transition("DONE")
