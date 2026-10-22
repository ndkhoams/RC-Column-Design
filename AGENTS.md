# AGENTS.md — RC-Column-Design

Hướng dẫn cho AI coding agent (Muse Code / Muse) làm việc trong repo này.
Đọc hết file này trước khi sửa bất kỳ dòng code nào. Ngôn ngữ trao đổi với chủ dự án: **tiếng Việt**.

## 1. Dự án là gì

- App desktop Python (tkinter) kiểm tra cột BTCT theo **3 tiêu chuẩn**: TCVN 5574:2018, ACI 318-19, EC2 EN 1992-1-1.
- Engine: fiber model + mặt tương tác 3D (N + M2 + M3), hệ trục 2/3 kiểu ETABS.
- Đóng gói .exe bằng PyInstaller: `python build_exe.py` → `dist/RCColumnDesign.exe`. Chạy từ source: `python main.py`.
- Đang mở rộng module Vách/Lõi (GĐ1: chỉ vách chữ nhật đặc) — file `rc_column/wall_*.py`, `gui/wall_mixin.py`.
- Chủ dự án là kỹ sư kết cấu, tự test mọi thay đổi trên máy Windows. Mọi kết quả tính đều phải đối chiếu được với ETABS / CSiCol / Prokon.

## 2. Bản đồ code (head kiểm chứng: 3babf0f)

- `main.py` — entry point, rất mỏng.
- `build_exe.py`, `RCColumnDesign.spec` — build .exe, có `--add-data` cho icon; title bar hiện hash commit đọc trực tiếp từ `.git/HEAD` + refs.
- `gui/app.py` — lớp `App` gầy (~14.5KB), kế thừa 9 mixin, 15 method lõi. **Không nhồi code vào app.py**; thêm tính năng GUI thì sửa/ tạo mixin tương ứng:
  - `build_mixin.py` (dựng UI, hằng `DIAS`), `data_mixin.py`, `dxf_mixin.py` (import DXF + Prokon), `etabs_mixin.py` (bảng nội lực ETABS, 4 nút Import/Add/Replace/Delete), `preview_mixin.py`, `tcvn_mixin.py`, `aci_mixin.py`, `ec2_mixin.py`, `pdf_mixin.py`, `wall_mixin.py`.
  - `gui/result_renderer.py` — renderer CHUNG cho tab Kết quả của ACI + EC2. TCVN còn giữ renderer riêng `_redraw_old` (đừng migrate khi chưa được yêu cầu — lần thử trước crash ở chế độ ETABS).
  - Bẫy đã biết: `_LBL_WIDTH` thuộc `App`, `DIAS` thuộc `BuildMixin`.
- `rc_column/` — engine thuần tính toán, không phụ thuộc GUI:
  - TCVN: `checker.py`, `materials.py`, `sections.py`, `interaction.py`, `stability.py`, `stirrup.py`, `report.py`, `pdf_export.py`, `chart_draw.py`.
  - ACI: `aci_checker.py`, `aci_materials.py`, `aci_pdf_report.py`, `aci_pdf_summary.py`, `aci_report_v2.py`, `aci_chart_draw.py`.
  - EC2: `ec2_checker.py`, `ec2_materials.py`, `ec2_pdf_report.py`, `ec2_pdf_summary.py`, `ec2_report.py`, `ec2_report_v2.py`, `ec2_chart_draw.py`.
  - Dùng chung: `etabs_import.py`, `prokon_import.py`, `dxf_import.py`, `batch_dc.py` (đường batch OPEN/CHECK), `pdf_report_cards.py`, `report_widgets.py`, `lang.py` (khung i18n `T()` — tiếng Anh đang TẠM BỎ, chỉ giữ khung).
  - Vách: `wall_section.py`, `wall_input.py`, `wall_engine.py`.

## 3. Luật kiến trúc — BẮT BUỘC

1. **"Tính 1 lần, hiển thị nhiều nơi"**: mỗi tiêu chuẩn chỉ có MỘT hàm tính duy nhất — `_tcvn_calculate_full`, `_aci_calculate_full`, `_ec2_calculate_full`. Chế độ nhập tay và batch ETABS dùng chung hàm này. Tab Kết quả, tab Chi tiết và 2 PDF (tóm tắt 1 trang + thuyết minh chi tiết) chỉ ĐỌC từ dict kết quả đã lưu, **không tính lại**.
2. Cắt TCVN cũng một nguồn duy nhất: `compute_shear_cols(inp, sec)` trong `rc_column/stirrup.py`.
3. **Parity 3 tiêu chuẩn**: TCVN có chức năng/layout/nhãn gì thì ACI/EC2 có đó (gồm 2 PDF và tab Kết quả). Khi sửa 1 chỗ, phải grep cả 3 tiêu chuẩn × 2 chế độ (tay/ETABS) và sửa đủ.
4. **Không hardcode** giá trị tính toán (đai, d, Is...). Mọi thứ lấy từ input hoặc tính từ dữ liệu thật.
5. Khi fix một lỗi, quét **cả lớp lỗi** tương tự trong cùng vòng (mọi biến thể song song), không fix điểm rồi dừng.
6. Giữ nguyên solver exact họ CSiCol/ETABS (chủ dự án đã chốt). Kết luận ĐẠT/KHÔNG ĐẠT theo **D/C tia 3D**. Không tự ý đổi mô hình/phương pháp làm thay đổi kết quả — nếu cần đổi, trình số liệu trước/sau và chờ duyệt.

## 4. Quy ước kỹ thuật đã chốt (đừng "sửa" lại)

- Góc uốn xiên α đo từ trục M3: `α = atan2(M2, M3)`, **giữ dấu** ở cả 3 TC (TCVN dùng mô men đã phóng đại Mx*/My*, ACI dùng Mc2/Mc3, EC2 dùng M2/M3 gốc — không dùng `abs()`).
- Import Prokon (.C13): **Prokon Mx → app M2, Prokon My → app M3**, giữ dấu. ψ app Ngàm–Ngàm = 0.5 ≠ β Prokon 0.75 → phải cảnh báo khi import.
- EC2: αcc = 1.0; φef lấy theo tổ hợp TX_* (`φef = φ(∞,t0) × M_TX/M_Ed`), không có TX_* thì fallback 1.21; Qsway = 0.
- Cắt TCVN: φb1 = 0.3 (hằng số bản 2018); φn §8.1.3.3.2 chỉ nhân số hạng bê tông; kiểm tra (96)/(98) theo `stirrup.py` hiện tại.
- Hiển thị lực cắt: chỉ 1 hàng; bảng Kết quả chỉ hiện giá trị, thẻ Chi tiết + PDF chi tiết hiện kèm combo/vị trí, PDF tóm tắt như bảng Kết quả.
- Tiết diện bất kỳ: vùng nén bằng Sutherland–Hodgman trong `draw_compression_zone_ax` (`pdf_export.py`), dùng chung cho app + 6 PDF.
- JSON lưu toàn bộ nội lực đã import + khóa `member_name`, `member_type`/`wall`/`pier_forces` (tương thích ngược — không đổi tên khóa cũ).

## 5. Cổng kiểm chứng trước khi báo "xong"

- Chạy tests: **14/14 PASS** và hồi quy D/C không trôi so với trước khi sửa (nêu rõ số D/C trước/sau khi giao).
- Đổi engine → đối chiếu độc lập (ETABS/CSiCol/Prokon) kèm bảng so sánh.
- Kiểm tra trùng key trong dict literal khi thêm field (đã từng có bug 2 key `"dia"`).
- Không báo xong khi chưa verify từng mục user yêu cầu, mục nào chưa kiểm chứng được phải nói rõ.

## 6. Git & môi trường máy chủ dự án

- **Luôn lấy bản mới nhất từ GitHub trước khi sửa** — chủ dự án có thể đã tự sửa khác bản local. Lệch lớn thì báo trước, đừng sửa đè.
- Git trên máy chủ dự án **không có trong PATH** — thao tác git qua VS Git UI; đừng hướng dẫn chạy lệnh git CLI. Xác định bản đang chạy bằng hash commit trên title bar.
- Sau khi pull mà app "vẫn lỗi cũ": nghi `__pycache__` cũ trước tiên.
- File nhị phân (`icon.png`, `icon.ico`...) **không đẩy qua API dạng text/base64** — chúng phải được chép tay và commit qua VS Git UI. File text luôn đẩy dạng văn bản thuần.
- Chủ dự án đã duyệt trước việc push commit lên repo này — push xong phải fetch lại file từ remote, đọc dạng văn bản đã giải mã và đối chiếu với bản local mới được kết luận khớp.
