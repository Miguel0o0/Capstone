import pytest


def test_dummy_raises():
    with pytest.raises(ZeroDivisionError):
        1 / 0
