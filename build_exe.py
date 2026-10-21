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


def _write_build_info():
    """Sinh file build_info.py chứa thời điểm đóng gói exe."""
    import datetime
    ts = datetime.datetime.now().strftime("%Y%m%d%H%M")
    with open("build_info.py", "w", encoding="utf-8") as f:
        f.write(f'"""Build info - tự động sinh bởi build_exe.py. Không sửa tay."""\n')
        f.write(f'BUILD_TIME = "{ts}"\n')
    print(f"Build time: {ts}")
    return ts


def _make_icon():
    """Tạo icon.ico từ icon.png bằng Pillow local (tương thích PyInstaller)."""
    if not os.path.exists("icon.png"):
        return False
    try:
        from PIL import Image
        img = Image.open("icon.png")
        # PyInstaller trên Windows ưa ICO BMP; Pillow local tạo sẽ tương thích
        img.save("icon.ico", sizes=[(16, 16), (32, 32), (48, 48),
                                    (64, 64), (128, 128), (256, 256)])
        print("Đã tạo icon.ico từ icon.png")
        return True
    except Exception as e:
        print(f"Không tạo được icon.ico: {e}")
        return False


def main() -> int:
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",          # 1 file exe duy nhất
        "--windowed",         # không hiện console
        "--name", APP_NAME,
    ]
    # Icon cho file .exe: tạo từ icon.png bằng Pillow trên máy build
    if _make_icon():
        cmd += ["--icon", "icon.ico"]
    # Đóng gói kèm file icon vào trong exe: gui/app.py tìm icon.png /
    # icon.ico trong bundle (sys._MEIPASS) để đặt icon cửa sổ (title bar
    # + taskbar) lúc chạy. Thiếu 2 dòng này là app chạy lên không thấy
    # file icon nào — chỉ còn icon của file .exe trong Explorer.
    for _f in ("icon.png", "icon.ico"):
        if os.path.exists(_f):
            cmd += ["--add-data", f"{_f}{os.pathsep}."]
    cmd += [
        *MATPLOTLIB_HOOKS,
        # ẩn import để PyInstaller không bỏ sót
        "--hidden-import", "matplotlib.backends.backend_tkagg",
        "--hidden-import", "numpy",
        "--hidden-import", "reportlab",
        "--hidden-import", "reportlab.lib.pagesizes",
        "--hidden-import", "reportlab.pdfbase.ttfonts",
        "--hidden-import", "reportlab.platypus",
        "--hidden-import", "ezdxf",
        "--hidden-import", "ezdxf.entities",
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
