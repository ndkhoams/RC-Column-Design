#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Lay noi luc frame (cot/dam) tu ETABS dang mo bang mot lenh.

Cach dung (tren may Windows, ETABS dang mo mo hinh can lay noi luc):
    python etabs_frame_forces.py
    python etabs_frame_forces.py --output noi_luc.xlsx
    python etabs_frame_forces.py --frames C1,C2 --output noi_luc.xlsx

Ket qua:
    - File Excel (.xlsx) de nap bang nut "Import from Excel" o muc 5
      cua RC-Column-Design (bang "Element Forces - Frames").
    - File text (.txt) cung noi dung, dang tab-separated, de dung nut
      "Paste from Clipboard" neu can (copy toan bo file roi paste).

Quy uoc (khop dung muc 5 cua app, khong doi dau):
    - P giu nguyen nhu ETABS: P am = nen. App se tu doi sang N duong
      khi nap (N = -P).
    - Don vi dau ra: luc kN, mo men kN-m, station met.
    - Chi lay to hop (Combination), vi muc 5 chi tinh to hop.
      (Load case rieng le khong duoc app giu lai khi nap.)

Chi doc, khong ghi, khong sua mo hinh:
    Script chi goi cac ham doc cua ETABS (lay danh sach frame, to hop,
    va bang Frame Forces) va chon to hop de xuat ket qua trong phien
    lam viec hien tai. Khong doi hinh hoc, tiet dien, tai trong,
    vat lieu hay bat ky thuoc tinh nao cua mo hinh.

Yeu cau: Windows + ETABS dang chay + Python co comtypes (hoac pywin32)
va openpyxl. Neu ETABS chua mo, script bao loi ro rang va dung lai,
khong tao file rong.
"""

import argparse
import os
import sys

# ---------------------------------------------------------------------------
# Don vi: doi tu don vi co so du lieu cua ETABS ve kN / kN-m / met.
# Ma enum theo tai lieu ETABS OAPI (eForce / eLength):
#   eForce:  1=lb, 2=kip, 3=N, 4=kN, 5=kgf, 6=tonf
#   eLength: 1=inch, 2=ft, 3=mm, 4=cm, 5=m
# ---------------------------------------------------------------------------

_FORCE_TO_KN = {1: 0.0044482216, 2: 4.4482216, 3: 0.001,
                4: 1.0, 5: 0.00980665, 6: 9.80665}
_LENGTH_TO_M = {1: 0.0254, 2: 0.3048, 3: 0.001, 4: 0.01, 5: 1.0}


def unit_factors(force_code, length_code):
    """Tra ve (he_so_luc_ve_kN, he_so_momen_ve_kN-m, he_so_dai_ve_m).

    Neu ma don vi khong nhan ra thi bao loi thay vi doan mo, vi sai
    don vi se lam sai toan bo noi luc ma khong de lai dau vet.
    """
    try:
        f_force = _FORCE_TO_KN[int(force_code)]
        f_length = _LENGTH_TO_M[int(length_code)]
    except (KeyError, TypeError, ValueError):
        raise ValueError(
            "Khong nhan ra don vi co so du lieu cua ETABS "
            "(force=%r, length=%r). Hay doi don vi mo hinh ve kN/m "
            "roi chay lai." % (force_code, length_code))
    return f_force, f_force * f_length, f_length


def step_type_name(step_type):
    """Doi ma StepType cua ETABS sang chu de app gan hau to max/min.

    ETABS: 1 = Max, 2 = Min, con lai (to hop tinh) = rong.
    """
    try:
        code = int(step_type)
    except (TypeError, ValueError):
        return ""
    if code == 1:
        return "Max"
    if code == 2:
        return "Min"
    return ""


# ---------------------------------------------------------------------------
# Doc tu ETABS (doi tuong SapModel, de mock duoc khi kiem thu)
# ---------------------------------------------------------------------------

def _call_first_tuple(result):
    """Chuan hoa ket qua goi ham COM ve dang tuple.

    Voi comtypes, cac tham so out tra ve thanh tuple theo thu tu
    khai bao, phan tu cuoi la ma tra ve (ret). Ham nay chi boc tach
    cho gon; logic chinh khong phu thuoc vao comtypes.
    """
    if isinstance(result, tuple):
        return result
    return (result,)


def get_database_units(sap_model):
    """Doc don vi co so du lieu (khong doi don vi hien thi)."""
    out = _call_first_tuple(sap_model.GetDatabaseUnits())
    if len(out) < 3:
        raise ValueError("GetDatabaseUnits tra ve khong du thong tin.")
    # out chua ca ma tra ve (0 = thanh cong) lan voi cac ma don vi,
    # nen quet cap ke nhau dau tien ma phan tu thu nhat nam trong
    # bang ma luc va phan tu thu hai nam trong bang ma dai.
    ints = [v for v in out if isinstance(v, int)
            and not isinstance(v, bool)]
    for a, b in zip(ints, ints[1:]):
        if a in _FORCE_TO_KN and b in _LENGTH_TO_M:
            return a, b
    raise ValueError(
        "Khong doc duoc don vi co so du lieu cua ETABS (ket qua: %r)." % (out,))


def list_frames(sap_model):
    out = _call_first_tuple(sap_model.FrameObj.GetNameList())
    names = None
    for v in out:
        if isinstance(v, (list, tuple)):
            names = list(v)
            break
    if names is None:
        raise ValueError("Khong lay duoc danh sach frame tu ETABS.")
    return names


def frame_label_story(sap_model, name):
    """Tra ve (label, story) cua mot frame."""
    out = _call_first_tuple(sap_model.FrameObj.GetLabelFromName(name))
    texts = [v for v in out if isinstance(v, str)]
    if len(texts) >= 2:
        return texts[0], texts[1]
    if len(texts) == 1:
        return texts[0], ""
    return name, ""


def list_combos(sap_model):
    out = _call_first_tuple(sap_model.LoadCombos.GetNameList())
    for v in out:
        if isinstance(v, (list, tuple)):
            return list(v)
    raise ValueError("Khong lay duoc danh sach to hop tu ETABS.")


def select_combos_for_output(sap_model, combos):
    """Chon to hop de xuat ket qua (chi anh huong phien xuat, khong
    sua mo hinh)."""
    setup = sap_model.Results.Setup
    setup.DeselectAllCasesAndCombosForOutput()
    for combo in combos:
        setup.SetComboSelectedForOutput(combo, True)


def frame_force_rows(sap_model, frame_name):
    """Doc bang Frame Forces cua 1 frame, tra ve list dict tho.

    Moi dict: load_case, step_type (so), station (don vi goc),
    p, v2, v3, t, m2, m3 (don vi goc).
    """
    out = _call_first_tuple(
        sap_model.Results.FrameForce(frame_name, 0))
    # Thu tu out theo API: NumberResults, Obj, ObjStation, Elm,
    # ElmStation, LoadCase, StepType, StepNum, P, V2, V3, T, M2, M3, ret
    if len(out) < 15:
        raise ValueError(
            "FrameForce tra ve khong du cot cho frame %r." % (frame_name,))
    (_n, _obj, obj_station, _elm, _elm_station, load_case, step_type,
     _step_num, p, v2, v3, t, m2, m3, _ret) = out[:15]
    rows = []
    for i in range(len(load_case)):
        rows.append({
            "load_case": load_case[i],
            "step_type": step_type[i],
            "station": obj_station[i],
            "p": p[i], "v2": v2[i], "v3": v3[i], "t": t[i],
            "m2": m2[i], "m3": m3[i],
        })
    return rows


def export_forces(sap_model, frame_names=None):
    """Doc toan bo noi luc frame, tra ve (rows, units).

    rows: list dict da doi ve kN / kN-m / met, dung dinh dang muc 5:
    story, frame, case, case_type, step, station, p, v2, v3, t, m2, m3.
    P GIU NGUYEN dau ETABS (am = nen); app se doi N = -P khi nap.
    """
    force_code, length_code = get_database_units(sap_model)
    f_force, f_moment, f_length = unit_factors(force_code, length_code)
    combos = list_combos(sap_model)
    if not combos:
        raise ValueError("Mo hinh khong co to hop (Combination) nao.")
    select_combos_for_output(sap_model, combos)
    names = frame_names or list_frames(sap_model)
    if not names:
        raise ValueError("Mo hinh khong co frame nao.")
    rows = []
    for name in names:
        label, story = frame_label_story(sap_model, name)
        for r in frame_force_rows(sap_model, name):
            rows.append({
                "story": story, "frame": label,
                "case": r["load_case"], "case_type": "Combination",
                "step": step_type_name(r["step_type"]),
                "station": r["station"] * f_length,
                "p": r["p"] * f_force,
                "v2": r["v2"] * f_force,
                "v3": r["v3"] * f_force,
                "t": r["t"] * f_moment,
                "m2": r["m2"] * f_moment,
                "m3": r["m3"] * f_moment,
            })
    if not rows:
        raise ValueError("Khong doc duoc dong noi luc nao tu ETABS.")
    return rows, {"force": "kN", "moment": "kN-m", "length": "m"}


# ---------------------------------------------------------------------------
# Ghi file
# ---------------------------------------------------------------------------

HEADER = ["Story", "Frame", "Output Case", "Case Type", "Step Type",
          "Station", "P", "V2", "V3", "T", "M2", "M3"]
UNITS_ROW = ["", "", "", "", "", "m",
             "kN", "kN", "kN", "kN-m", "kN-m", "kN-m"]
KEYS = ["story", "frame", "case", "case_type", "step", "station",
        "p", "v2", "v3", "t", "m2", "m3"]


def write_excel(rows, path):
    try:
        import openpyxl
    except ImportError:
        raise ImportError("Can cai openpyxl: pip install openpyxl")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Element Forces - Frames"
    ws.append(HEADER)
    ws.append(UNITS_ROW)
    for r in rows:
        ws.append([r[k] for k in KEYS])
    wb.save(path)


def write_text(rows, path):
    lines = ["\t".join(HEADER), "\t".join(UNITS_ROW)]
    for r in rows:
        vals = []
        for k in KEYS:
            v = r[k]
            if isinstance(v, float):
                vals.append(repr(v))
            else:
                vals.append(str(v))
        lines.append("\t".join(vals))
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# Gan vao ETABS dang chay (chi Windows)
# ---------------------------------------------------------------------------

def attach_etabs():
    """Gan vao ETABS dang chay, tra ve SapModel. Loi ro rang neu chua mo."""
    if os.name != "nt":
        raise RuntimeError(
            "Script nay chi chay tren Windows noi ETABS dang mo. "
            "Ban dang chay tren %r." % (os.name,))
    last_error = None
    try:
        import comtypes.client
        etabs = comtypes.client.GetActiveObject("CSI.ETABS.API.ETABSObject")
        return etabs.SapModel
    except Exception as ex:  # noqa: BLE001 - thu phuong an tiep theo
        last_error = ex
    try:
        import win32com.client
        etabs = win32com.client.GetActiveObject(
            "CSI.ETABS.API.ETABSObject")
        return etabs.SapModel
    except Exception as ex:  # noqa: BLE001
        raise RuntimeError(
            "Khong gan duoc vao ETABS dang chay. Hay mo ETABS va mo "
            "mo hinh truoc roi chay lai. (comtypes: %r; pywin32: %r)"
            % (last_error, ex))


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Lay noi luc frame tu ETABS dang mo, xuat file "
                    "cho muc 5 cua RC-Column-Design.")
    ap.add_argument("--output", default="noi_luc_etabs.xlsx",
                    help="Duong dan file Excel dau ra "
                         "(mac dinh: noi_luc_etabs.xlsx)")
    ap.add_argument("--frames", default="",
                    help="Chi lay cac frame nay, cach nhau boi dau phay "
                         "(mac dinh: tat ca frame)")
    ap.add_argument("--no-txt", action="store_true",
                    help="Khong ghi them file .txt cung noi dung")
    args = ap.parse_args(argv)

    sap_model = attach_etabs()
    frame_names = ([f.strip() for f in args.frames.split(",") if f.strip()]
                   if args.frames else None)
    rows, _units = export_forces(sap_model, frame_names)

    out_xlsx = args.output
    if not out_xlsx.lower().endswith((".xlsx", ".xls")):
        out_xlsx += ".xlsx"
    write_excel(rows, out_xlsx)
    txt_path = None
    if not args.no_txt:
        txt_path = os.path.splitext(out_xlsx)[0] + ".txt"
        write_text(rows, txt_path)

    cases = sorted(set(r["case"] for r in rows))
    print("Da doc %d dong, %d to hop, %d frame." % (
        len(rows), len(cases), len(set(r["frame"] for r in rows))))
    if rows:
        first = rows[0]
        print("Dong dau: %s | %s | %s | Station %.3f | P %.3f | "
              "V2 %.3f | V3 %.3f | M2 %.3f | M3 %.3f" % (
                  first["story"], first["frame"], first["case"],
                  first["station"], first["p"], first["v2"],
                  first["v3"], first["m2"], first["m3"]))
    print("File Excel: %s" % (os.path.abspath(out_xlsx),))
    if txt_path:
        print("File text: %s" % (os.path.abspath(txt_path),))
    print("Nap bang nut 'Import from Excel' o muc 5 cua "
          "RC-Column-Design, chon file Excel tren.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
