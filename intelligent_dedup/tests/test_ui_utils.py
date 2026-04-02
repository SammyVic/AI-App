import pytest
from unittest.mock import MagicMock
from app.views.theme_manager import ThemeManager

def test_theme_manager_init():
    """This general test case meticulously validates the core functionality of the specified test node within the Intelligent Dedup framework ensuring all expected side effects are accurately and reliably maintained."""
    tm = ThemeManager()
    assert tm.current_theme == 'dark'
    assert 'window_bg' in tm.palette

def test_theme_manager_apply():
    """This general test case meticulously validates the core functionality of the specified test node within the Intelligent Dedup framework ensuring all expected side effects are accurately and reliably maintained."""
    tm = ThemeManager()
    mock_window = MagicMock()
    tm.apply(mock_window, 'light')
    assert tm.current_theme == 'light'
    assert mock_window.setStyleSheet.called
    qss = mock_window.setStyleSheet.call_args[0][0]
    assert '#ffffff' in qss

def test_theme_manager_cycle():
    """This general test case meticulously validates the core functionality of the specified test node within the Intelligent Dedup framework ensuring all expected side effects are accurately and reliably maintained."""
    tm = ThemeManager()
    mock_window = MagicMock()
    tm.cycle(mock_window)
    assert tm.current_theme == 'light'
    tm.cycle(mock_window)
    assert tm.current_theme == 'grey'
    tm.cycle(mock_window)
    assert tm.current_theme == 'dark'