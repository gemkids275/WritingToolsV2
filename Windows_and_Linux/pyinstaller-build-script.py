import os
import shutil
import subprocess
import sys

IS_WINDOWS = sys.platform == 'win32'

# --add-data separator: ';' on Windows, ':' on Linux/macOS
SEP = ';' if IS_WINDOWS else ':'

def D(src, dest):
    """Tạo argument --add-data cross-platform."""
    return f"{src}{SEP}{dest}"


def run_pyinstaller_build():
    icon = 'icons/app_icon.ico' if IS_WINDOWS else 'icons/app_icon.png'

    excludes = [
        "tkinter", "unittest", "IPython", "jedi", "email_validator",
        "psutil", "pyzmq", "tornado",
        "PySide6.QtNetwork", "PySide6.QtXml", "PySide6.QtQml",
        "PySide6.QtQuick", "PySide6.QtQuickWidgets", "PySide6.QtPrintSupport",
        "PySide6.QtSql", "PySide6.QtTest", "PySide6.QtSvg", "PySide6.QtSvgWidgets",
        "PySide6.QtHelp", "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets",
        "PySide6.QtOpenGL", "PySide6.QtOpenGLWidgets", "PySide6.QtPositioning",
        "PySide6.QtLocation", "PySide6.QtSerialPort", "PySide6.QtWebChannel",
        "PySide6.QtWebSockets", "PySide6.QtNetworkAuth", "PySide6.QtRemoteObjects",
        "PySide6.QtTextToSpeech", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets",
        "PySide6.QtWebEngine", "PySide6.QtBluetooth", "PySide6.QtNfc",
        "PySide6.QtWebView", "PySide6.QtCharts", "PySide6.QtDataVisualization",
        "PySide6.QtPdf", "PySide6.QtPdfWidgets", "PySide6.QtQuick3D",
        "PySide6.QtQuickControls2", "PySide6.QtQuickParticles", "PySide6.QtQuickTest",
        "PySide6.QtSensors", "PySide6.QtStateMachine",
        "PySide6.Qt3DCore", "PySide6.Qt3DRender", "PySide6.Qt3DInput",
        "PySide6.Qt3DLogic", "PySide6.Qt3DAnimation", "PySide6.Qt3DExtras",
    ]

    # PySide6.QtWinExtras chỉ tồn tại trên Windows
    if IS_WINDOWS:
        excludes.append("PySide6.QtWinExtras")

    exclude_args = []
    for mod in excludes:
        exclude_args += ["--exclude-module", mod]

    pyinstaller_command = [
        "pyinstaller",
        "--onefile",
        "--windowed",
        f"--icon={icon}",
        "--name=AI Shortcuts",
        "--clean",
        "--noconfirm",
        *exclude_args,
        "--add-data", D("icons", "icons"),
        "--add-data", D("locales", "locales"),
        "--add-data", D("background.png", "."),
        "--add-data", D("background_dark.png", "."),
        "--add-data", D("background_popup.png", "."),
        "--add-data", D("background_popup_dark.png", "."),
        "--add-data", D("Latest_Version_for_Update_Check.txt", "."),
        "main.py"
    ]

    try:
        for d in ['dist', 'build', '__pycache__']:
            if os.path.exists(d):
                shutil.rmtree(d)

        subprocess.run(pyinstaller_command, check=True)
        print("Build completed successfully!")

        for d in ['build', '__pycache__']:
            if os.path.exists(d):
                shutil.rmtree(d)

    except subprocess.CalledProcessError as e:
        print(f"Build failed with error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    run_pyinstaller_build()