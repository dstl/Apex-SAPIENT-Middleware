#
# Copyright (c) 2019-2024 Roke Manor Research Ltd
#

import logging
from pathlib import Path
import os
import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from sapient_apex_gui.main_window import MainWindow


def set_icon(app):
    icon_dir = Path(__file__).parent
    # Path for Nuitka build
    icon_path = icon_dir.joinpath("apex-logo.ico")
    if not icon_path.exists():
        # Path for running in development
        icon_path = icon_dir.parent.joinpath("apex-logo.ico")
        if not icon_path.exists():
            return
    app.setWindowIcon(QIcon(str(icon_path)))


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(threadName)s] %(name)s: %(message)s",
    )
    if not Path("apex_config.json").exists() and Path("..", "apex_config.json").exists():
        # User has started GUI in a nested directory e.g. by just double clicking apex_gui.exe
        os.chdir("..")
    app = QApplication(sys.argv)
    set_icon(app)
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
