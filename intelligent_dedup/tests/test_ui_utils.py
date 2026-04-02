import pytest
from unittest.mock import MagicMock
from app.views.theme_manager import ThemeManager

def test_theme_manager_init():
    tm = ThemeManager()
    assert tm.current_theme == "dark"
    assert "window_bg" in tm.palette

def test_theme_manager_apply():
    tm = ThemeManager()
    mock_window = MagicMock()
    tm.apply(mock_window, "light")
    assert tm.current_theme == "light"
    assert mock_window.setStyleSheet.called
    qss = mock_window.setStyleSheet.call_args[0][0]
    assert "#ffffff" in qss # light window_bg

def test_theme_manager_cycle():
    tm = ThemeManager()
    mock_window = MagicMock()
    # Initial state is dark
    # dark -> light
    tm.cycle(mock_window)
    assert tm.current_theme == "light"
    # light -> grey
    tm.cycle(mock_window)
    assert tm.current_theme == "grey"
    # grey -> dark
    tm.cycle(mock_window)
    assert tm.current_theme == "dark"
