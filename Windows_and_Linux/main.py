import logging
import sys
import os
from PySide6 import QtCore, QtWidgets
from WritingToolApp import WritingToolApp

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')


def main():
    app = WritingToolApp(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
