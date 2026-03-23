from __future__ import annotations

from datetime import datetime, timedelta
import tkinter as tk
from tkinter import messagebox, simpledialog

from app.core.settings import (
    LATE_GRACE_MINUTES,
    SHIFT_END_HOUR,
    SHIFT_END_MINUTE,
    SHIFT_START_HOUR,
    SHIFT_START_MINUTE,
)
from app.pipelines.enroll_camera import run_register_employee
from app.pipelines.infer_camera import run_attendance
from app.vision.face_utils import load_models


def _attendance_status(accepted_at: datetime) -> str:
    shift_start = accepted_at.replace(
        hour=SHIFT_START_HOUR,
        minute=SHIFT_START_MINUTE,
        second=0,
        microsecond=0,
    )
    late_deadline = shift_start + timedelta(minutes=LATE_GRACE_MINUTES)
    return "dung gio" if accepted_at <= late_deadline else "muon"


def _checkout_status(accepted_at: datetime) -> str:
    shift_end = accepted_at.replace(
        hour=SHIFT_END_HOUR,
        minute=SHIFT_END_MINUTE,
        second=0,
        microsecond=0,
    )
    return "ve som" if accepted_at < shift_end else "dung gio"


def _run_attendance(root: tk.Tk, models) -> None:
    result = run_attendance(stop_on_accept=True, models=models)
    root.lift()
    root.focus_force()

    if not result:
        messagebox.showinfo("Cham cong", "Chua co ket qua cham cong.")
        return

    if result.get("error") in {"network_offline", "network_error"}:
        messagebox.showerror("Cham cong", "Khong ket noi duoc backend. Khong the cham cong.")
        return

    if result.get("error") == "backend_error":
        detail = result.get("detail") or "unknown_backend_error"
        messagebox.showerror("Cham cong", f"Backend tra ve loi:\n{detail}")
        return

    if result.get("error") == "camera_error":
        messagebox.showerror("Cham cong", "Khong mo duoc camera.")
        return

    employee_code = result["employee_code"]
    employee_name = (result.get("user_name") or "").strip() or employee_code
    accepted_at = result["accepted_at"]
    attendance_type = str(result.get("attendance_type", "checkin")).lower()
    status = _attendance_status(accepted_at)
    if attendance_type == "checkout":
        checkout_status = _checkout_status(accepted_at)
        messagebox.showinfo(
            "Ket qua cham cong",
            f"Tam biet: Nhan vien {employee_code} - {employee_name} - trang thai {checkout_status}.",
        )
    else:
        messagebox.showinfo(
            "Ket qua cham cong",
            f"Xin cam on: Nhan vien {employee_code} - {employee_name} - trang thai {status}.",
        )


def _run_enroll(root: tk.Tk, models) -> None:
    employee_code = simpledialog.askstring(
        "Dang ky nhan vien moi",
        "Nhap ma nhan vien (vd: EMP001):",
        parent=root,
    )
    if employee_code is None:
        return

    employee_code = employee_code.strip()
    if not employee_code:
        messagebox.showwarning("Dang ky", "Ma nhan vien khong duoc de trong.")
        return

    employee_name = simpledialog.askstring(
        "Dang ky nhan vien moi",
        "Nhap ten nhan vien (vd: Nguyen Van A):",
        parent=root,
    )
    if employee_name is None:
        return

    employee_name = employee_name.strip()
    if not employee_name:
        messagebox.showwarning("Dang ky", "Ten nhan vien khong duoc de trong.")
        return

    result = run_register_employee(employee_code=employee_code, employee_name=employee_name, models=models)
    root.lift()
    root.focus_force()

    if result.get("success"):
        enrolled_name = (result.get("employee_name") or "").strip() or result["employee_code"]
        messagebox.showinfo(
            "Dang ky thanh cong",
            f"Dang ky thanh cong nhan vien {result['employee_code']} - {enrolled_name}.",
        )
        return

    if result.get("reason") == "camera_error":
        messagebox.showerror("Dang ky", "Khong mo duoc camera.")
        return

    if result.get("reason") == "network_error":
        messagebox.showerror("Dang ky", "Khong ket noi duoc backend. Khong the dang ky.")
        return

    if result.get("reason") == "backend_error":
        detail = result.get("detail") or "unknown_backend_error"
        messagebox.showerror("Dang ky", f"Backend tu choi yeu cau dang ky:\n{detail}")
        return

    if result.get("reason") == "incomplete":
        messagebox.showwarning(
            "Dang ky chua hoan tat",
            f"Da luu tam {result.get('captured', 0)} mau cho nhan vien {result.get('employee_code')}",
        )
        return

    messagebox.showinfo("Dang ky", "Da huy dang ky nhan vien moi.")


def main() -> None:
    print("[INFO] Preloading models at app startup...")
    models = load_models(verbose=False)
    print("[INFO] Models preloaded. Ready for enroll/attendance.")

    root = tk.Tk()
    root.title("Face Attendance Desktop")
    root.resizable(False, False)

    title = tk.Label(root, text="He thong cham cong khuon mat", font=("Segoe UI", 16, "bold"))
    title.pack(pady=24)

    btn_attendance = tk.Button(
        root,
        text="Cham cong",
        font=("Segoe UI", 13),
        width=24,
        height=2,
        command=lambda: _run_attendance(root, models),
    )
    btn_attendance.pack(pady=10)

    btn_enroll = tk.Button(
        root,
        text="Dang ky nhan vien moi",
        font=("Segoe UI", 13),
        width=24,
        height=2,
        command=lambda: _run_enroll(root, models),
    )
    btn_enroll.pack(pady=10)

    hint = tk.Label(root, text="Nhan nut de mo camera va thuc hien chuc nang", font=("Segoe UI", 10))
    hint.pack(pady=12)

    root.mainloop()
