import logging
import sys

from WritingToolApp import WritingToolApp

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')


def main():
    app = WritingToolApp(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
