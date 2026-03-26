#!/usr/bin/env python
"""
=============================================================================
main.py — GUI Entry Point
=============================================================================
Launches the Intelligent Dedup Qt6 application.
=============================================================================
"""

import sys
import logging
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon

from app.views.main_window import MainWindow

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Intelligent Dedup")
    app.setOrganizationName("EnterpriseAI")
    app.setApplicationVersion("2.0.0")

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
