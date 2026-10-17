# Tính cột BTCT — TCVN 5574:2018

Phần mềm kiểm tra khả năng chịu lực cột bê tông cốt thép tiết diện **chữ nhật / tròn**
chịu **nén uốn xiên** (N + Mx + My) theo **mô hình biến dạng phi tuyến (NDM)** —
Điều 8.1.2.7, TCVN 5574:2018.

## Tính năng

- Vật liệu: bê tông B15–B60, thép CB240-T / CB300-V / CB400-V / CB500-V,
  hệ số điều kiện làm việc γb, γs.
- Mô hình bê tông: 3 đoạn thẳng (parabol–chữ nhật, MH3ĐT) hoặc 2 đoạn thẳng (MH2ĐT);
  thép đàn–dẻo lý tưởng; bỏ qua bê tông chịu kéo; εcu = 0.0035.
- Tiết diện chữ nhật / tròn; lưới fiber; bố trí thép tự động theo chu vi hoặc tùy ý.
- Chiều dài tính toán L₀ = ψ·L theo liên kết 2 đầu; độ mảnh; hệ số φL theo
  công thức (48) (mặc định 2.0 khi không khai báo tải dài hạn).
- Kiểm tra nén uốn xiên bằng mặt tương tác 3D rời rạc (quét góc uốn 0–360°),
  cho hệ số sử dụng (utilization) và kết luận ĐẠT / KHÔNG ĐẠT.
- Vẽ sơ đồ tiết diện + biểu đồ tương tác N–M.

## Cài đặt & chạy (Python)

```bash
pip install -r requirements.txt
python main.py          # mở giao diện
python -m tests.test_engine   # chạy kiểm chứng
```

## Build file .exe (trên Windows)

```bash
pip install -r requirements.txt
python build_exe.py
```

File chạy độc lập nằm tại `dist/RCColumnDesign.exe` (one-file, không cần cài Python).

## Cấu trúc

```
main.py                 Điểm vào (mở GUI)
build_exe.py            Build .exe bằng PyInstaller
rc_column/
  materials.py          Bê tông & thép theo TCVN 5574:2018
  sections.py           Tiết diện, lưới fiber, bố trí cốt thép
  nonlinear.py          Tích phân fiber, đường cong N-M một phương
  interaction.py        Mặt tương tác 3D, kiểm tra nén uốn xiên
  stability.py          L0, độ mảnh, φL
  checker.py            Điều phối kiểm tra
gui/
  app.py                Giao diện tkinter
tests/
  test_engine.py        Kiểm chứng
```

## Ghi chú kỹ thuật

- Đơn vị: mm (kích thước), kN (lực), kN·m (mô men). N > 0 là nén.
- Giả thiết: tiết diện phẳng sau biến dạng; phá hoại khi bê tông đạt εcu.
- Kết quả mang tính tham khảo thiết kế; kiểm chứng lại với ví dụ chuẩn
  trước khi dùng cho công trình thực tế.
