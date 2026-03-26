"""
=============================================================================
app/views/theme_manager.py
=============================================================================
Standalone theme manager — decoupled from the main window.
Supports dark | light | grey themes via QSS injection.
=============================================================================
"""

from __future__ import annotations

from typing import Literal

from PyQt6.QtWidgets import QMainWindow

ThemeName = Literal["dark", "light", "grey"]

_PALETTES: dict[str, dict[str, str]] = {
    "dark": {
        "window_bg":           "#0d1117",
        "panel_bg":            "#161b22",
        "text_color":          "#e6edf3",
        "border_color":        "#30363d",
        "button_bg":           "#238636",
        "button_text":         "#ffffff",
        "button_border":       "#2ea043",
        "button_hover":        "#2ea043",
        "button_pressed":      "#196127",
        "button_disabled_bg":  "#21262d",
        "button_disabled_fg":  "#6e7681",
        "accent":              "#58a6ff",
        "group_bg":            "#1e3a5f",
        "group_fg":            "#cdd9e5",
        "group_sel_bg":        "#264f78",
        "status_color":        "#8b949e",
        "progress_chunk":      "#1f6feb",
    },
    "light": {
        "window_bg":           "#ffffff",
        "panel_bg":            "#f6f8fa",
        "text_color":          "#24292f",
        "border_color":        "#d0d7de",
        "button_bg":           "#2da44e",
        "button_text":         "#ffffff",
        "button_border":       "#1a7f37",
        "button_hover":        "#2c974b",
        "button_pressed":      "#298e46",
        "button_disabled_bg":  "#eaeef2",
        "button_disabled_fg":  "#8c959f",
        "accent":              "#0969da",
        "group_bg":            "#ddf4ff",
        "group_fg":            "#0550ae",
        "group_sel_bg":        "#b6e3ff",
        "status_color":        "#57606a",
        "progress_chunk":      "#0969da",
    },
    "grey": {
        "window_bg":           "#1c1c1e",
        "panel_bg":            "#2c2c2e",
        "text_color":          "#e5e5ea",
        "border_color":        "#3a3a3c",
        "button_bg":           "#3a3a3c",
        "button_text":         "#ffffff",
        "button_border":       "#636366",
        "button_hover":        "#48484a",
        "button_pressed":      "#2c2c2e",
        "button_disabled_bg":  "#1c1c1e",
        "button_disabled_fg":  "#636366",
        "accent":              "#636366",
        "group_bg":            "#3a3a3c",
        "group_fg":            "#e5e5ea",
        "group_sel_bg":        "#48484a",
        "status_color":        "#aeaeb2",
        "progress_chunk":      "#636366",
    },
}


class ThemeManager:
    """
    Applies a named theme to a QMainWindow via QSS.
    Stores the palette dict for programmatic use by renderers.
    """

    def __init__(self) -> None:
        self.current_theme: ThemeName = "dark"
        self.palette: dict[str, str] = _PALETTES["dark"]

    def apply(self, window: QMainWindow, theme: ThemeName = "dark") -> None:
        self.current_theme = theme
        self.palette = _PALETTES.get(theme, _PALETTES["dark"])
        p = self.palette
        qss = f"""
        QMainWindow, QWidget {{
            background-color: {p['panel_bg']};
            color: {p['text_color']};
            font-family: 'Segoe UI', 'Inter', sans-serif;
            font-size: 12px;
        }}
        QMainWindow {{
            background-color: {p['window_bg']};
        }}
        QPushButton {{
            background-color: {p['button_bg']};
            color: {p['button_text']};
            border: 1px solid {p['button_border']};
            border-radius: 6px;
            padding: 6px 14px;
            font-weight: 600;
        }}
        QPushButton:hover {{ background-color: {p['button_hover']}; }}
        QPushButton:pressed {{ background-color: {p['button_pressed']}; }}
        QPushButton:disabled {{
            background-color: {p['button_disabled_bg']};
            color: {p['button_disabled_fg']};
            border-color: {p['border_color']};
        }}
        QTreeView, QTableView, QListView {{
            background-color: {p['panel_bg']};
            color: {p['text_color']};
            border: 1px solid {p['border_color']};
            border-radius: 4px;
            gridline-color: {p['border_color']};
        }}
        QTreeView::item:selected, QTableView::item:selected {{
            background-color: {p['group_sel_bg']};
        }}
        QHeaderView::section {{
            background-color: {p['window_bg']};
            color: {p['text_color']};
            border: 1px solid {p['border_color']};
            padding: 4px;
            font-weight: 600;
        }}
        QLineEdit, QTextEdit, QSpinBox, QComboBox {{
            background-color: {p['window_bg']};
            color: {p['text_color']};
            border: 1px solid {p['border_color']};
            border-radius: 4px;
            padding: 4px 6px;
        }}
        QProgressBar {{
            border: 1px solid {p['border_color']};
            border-radius: 4px;
            background-color: {p['window_bg']};
            color: {p['text_color']};
            text-align: center;
        }}
        QProgressBar::chunk {{ background-color: {p['progress_chunk']}; border-radius: 3px; }}
        QMenuBar, QMenu {{
            background-color: {p['panel_bg']};
            color: {p['text_color']};
            border-bottom: 1px solid {p['border_color']};
        }}
        QMenu::item:selected {{ background-color: {p['group_sel_bg']}; }}
        QStatusBar {{ background-color: {p['window_bg']}; color: {p['status_color']}; }}
        QSplitter::handle {{ background-color: {p['border_color']}; }}
        QLabel {{ color: {p['text_color']}; }}
        QDialog {{ background-color: {p['panel_bg']}; }}
        """
        window.setStyleSheet(qss)

    def cycle(self, window: QMainWindow) -> ThemeName:
        """Cycle: dark → light → grey → dark."""
        order: list[ThemeName] = ["dark", "light", "grey"]
        idx = order.index(self.current_theme) if self.current_theme in order else 0
        next_theme = order[(idx + 1) % len(order)]
        self.apply(window, next_theme)
        return next_theme
