"""Hệ thống đa ngôn ngữ VN/EN cho app tính cột BTCT."""

LANG = "VN"  # mặc định tiếng Việt

STRINGS = {
    # Tabs
    "Kết quả tính toán": {"EN": "Calculation Results"},
    "Chi tiết tính toán": {"EN": "Detailed Calculation"},
    # Top buttons
    "OPEN": {"EN": "OPEN"},
    "SAVE": {"EN": "SAVE"},
    "SAVE AS": {"EN": "SAVE AS"},
    "XUẤT PDF": {"EN": "EXPORT PDF"},
    "Tiêu chuẩn:": {"EN": "Code:"},
    "KIỂM TRA KHẢ NĂNG CHỊU LỰC": {"EN": "CHECK LOAD CAPACITY"},
    # Section 1
    "1. Vật liệu": {"EN": "1. Materials"},
    "Bê tông": {"EN": "Concrete"},
    "C. độ thép dọc fyk (MPa)": {"EN": "Long. steel fyk (MPa)"},
    "C. độ thép đai fyk (MPa)": {"EN": "Stirrup fyk (MPa)"},
    "Cường độ bê tông fc (MPa)": {"EN": "Concrete fc (MPa)"},
    "Cường độ thép fy (MPa)": {"EN": "Steel fy (MPa)"},
    "Cường độ thép đai fyt (MPa)": {"EN": "Stirrup fyt (MPa)"},
    "Mác bê tông": {"EN": "Concrete grade"},
    # Section 2
    "2. Tiết diện": {"EN": "2. Section"},
    "Loại tiết diện": {"EN": "Section type"},
    "Chữ nhật": {"EN": "Rectangle"},
    "Tròn": {"EN": "Circular"},
    "Tiết diện bất kỳ (DXF)": {"EN": "Arbitrary (DXF)"},
    "Cạnh t2 (mm) — đứng": {"EN": "Side t2 (mm) — vert"},
    "Cạnh t3 (mm) — ngang": {"EN": "Side t3 (mm) — horiz"},
    "Đường kính D (mm)": {"EN": "Diameter D (mm)"},
    # Section 3
    "3. Bố trí cốt thép dọc": {"EN": "3. Longitudinal Reinforcement"},
    "Lớp bảo vệ cốt dọc c (mm)": {"EN": "Cover c (mm)"},
    "4 thanh thép góc": {"EN": "4 corner bars"},
    "Thép cạnh t2 (2 mặt trái/phải)": {"EN": "Side t2 steel (2 faces)"},
    "Thép cạnh t3 (2 mặt trên/dưới)": {"EN": "Side t3 steel (2 faces)"},
    "Số nhánh": {"EN": "Legs"},
    "Đ.kính": {"EN": "Dia."},
    "K.cách": {"EN": "Spacing"},
    "Đai bao:": {"EN": "Perimeter:"},
    "Đai giữa t2:": {"EN": "Middle t2:"},
    "Đai giữa t3:": {"EN": "Middle t3:"},
    # Section 4
    "4. Chiều dài tính toán": {"EN": "4. Effective Length"},
    "Tham số": {"EN": "Parameter"},
    "Phương 2": {"EN": "Dir. 2"},
    "Phương 3": {"EN": "Dir. 3"},
    "Chiều dài cột L (m)": {"EN": "Column length L (m)"},
    "Liên kết đầu trên": {"EN": "Top restraint"},
    "Liên kết đầu dưới": {"EN": "Bottom restraint"},
    "Hệ số ψ (tự điền theo LK)": {"EN": "Factor ψ (auto)"},
    "Ngàm cứng": {"EN": "Fixed"},
    # Section 5
    "5. Nội lực kiểm tra": {"EN": "5. Design Forces"},
    "Nhập tay": {"EN": "Manual"},
    "Nhập từ ETABS": {"EN": "From ETABS"},
    "Chọn file Excel": {"EN": "Select Excel file"},
    "Paste từ Clipboard": {"EN": "Paste from Clipboard"},
    "Xóa nội lực": {"EN": "Clear forces"},
    "Story": {"EN": "Story"},
    "Label": {"EN": "Label"},
    "Combo": {"EN": "Combo"},
    "Station": {"EN": "Station"},
    # Results
    "BẢNG THÔNG SỐ TÍNH TOÁN": {"EN": "CALCULATION PARAMETERS"},
    "SƠ ĐỒ MẶT CẮT TIẾT DIỆN CỘT": {"EN": "COLUMN SECTION DIAGRAM"},
    "Cấu kiện:": {"EN": "Member:"},
    "Số thanh": {"EN": "Bars"},
    "Tổng As": {"EN": "Total As"},
    "Diện tích Ab": {"EN": "Area Ab"},
    "Hàm lượng μ": {"EN": "Ratio μ"},
    "Ký hiệu": {"EN": "Symbol"},
    "Thông số": {"EN": "Parameter"},
    "Giá trị": {"EN": "Value"},
    "Biểu đồ tương tác N–Mα": {"EN": "N–Mα Interaction Diagram"},
    "Mặt cắt M2-M3": {"EN": "M2-M3 Section"},
    "Góc xem:": {"EN": "View angle:"},
    "KIỂM TRA KHẢ NĂNG CHỊU CẮT": {"EN": "SHEAR CAPACITY CHECK"},
    "Phương V2": {"EN": "Dir. V2"},
    "Phương V3": {"EN": "Dir. V3"},
    "Kết luận": {"EN": "Conclusion"},
    "ĐẠT": {"EN": "PASS"},
    "KHÔNG ĐẠT": {"EN": "FAIL"},
}

def T(vi: str) -> str:
    """Trả về chuỗi theo ngôn ngữ hiện tại."""
    if LANG == "EN":
        return STRINGS.get(vi, {}).get("EN", vi)
    return vi

def set_lang(lang: str):
    global LANG
    LANG = lang
