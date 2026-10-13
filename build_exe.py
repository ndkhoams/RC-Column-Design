"""Build file .exe bằng PyInstaller (chạy trên Windows).

Cách dùng:
    pip install -r requirements.txt
    python build_exe.py

Kết quả: dist/RCColumnDesign.exe (file chạy độc lập, one-file).
"""

import os
import subprocess
import sys

APP_NAME = "RCColumnDesign"
ENTRY = "main.py"

# PyInstaller cần thu thập dữ liệu của matplotlib
MATPLOTLIB_HOOKS = [
    "--collect-data", "matplotlib",
    "--collect-submodules", "matplotlib",
]


def main() -> int:
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",          # 1 file exe duy nhất
        "--windowed",         # không hiện console
        "--name", APP_NAME,
        *MATPLOTLIB_HOOKS,
        # ẩn import để PyInstaller không bỏ sót
        "--hidden-import", "matplotlib.backends.backend_tkagg",
        "--hidden-import", "numpy",
        "--hidden-import", "reportlab",
        "--hidden-import", "reportlab.lib.pagesizes",
        "--hidden-import", "reportlab.pdfbase.ttfonts",
        "--hidden-import", "reportlab.platypus",
        ENTRY,
    ]
    print("Chạy:", " ".join(cmd))
    r = subprocess.run(cmd)
    if r.returncode == 0:
        exe = os.path.join("dist", APP_NAME + ".exe")
        print(f"\nXong! File exe tại: {os.path.abspath(exe)}")
    return r.returncode


if __name__ == "__main__":
    raise SystemExit(main())
