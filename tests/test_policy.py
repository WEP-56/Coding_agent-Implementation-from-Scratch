from __future__ import annotations

import pytest

from codinggirl.core.policy import PermissionPolicy


def test_policy_permissions():
    ro = PermissionPolicy(mode="readonly")
    assert ro.can_read() is True
    assert ro.can_write() is False
    with pytest.raises(PermissionError):
        ro.require_write()

    wr = PermissionPolicy(mode="write")
    assert wr.can_write() is True
    assert wr.can_exec() is False

    ex = PermissionPolicy(mode="exec")
    assert ex.can_exec() is True
