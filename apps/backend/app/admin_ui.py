from __future__ import annotations

from datetime import datetime

from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError

from app.core.database import SessionLocal
from app.models.attendance_log import AttendanceLog
from app.models.attendance_summary import AttendanceSummary
from app.models.device import Device
from app.models.user import User

admin_app = FastAPI(title="Face Smart Admin UI", version="0.1.0")


def _fmt_dt(value: datetime | None) -> str:
    if value is None:
        return ""
    return value.strftime("%Y-%m-%d %H:%M:%S")


def _parse_dt_local(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        # Browser datetime-local format: YYYY-MM-DDTHH:MM
        return datetime.strptime(value, "%Y-%m-%dT%H:%M")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid datetime format: {value}") from exc


@admin_app.get("/", response_class=HTMLResponse)
def dashboard(limit: int = 50, q: str = "", msg: str = "") -> str:
    with SessionLocal() as db:
        users_total = int(db.scalar(select(func.count(User.id))) or 0)
        logs_total = int(db.scalar(select(func.count(AttendanceLog.id))) or 0)
        summaries_total = int(db.scalar(select(func.count(AttendanceSummary.id))) or 0)

        user_query = select(User).order_by(User.created_at.desc()).limit(limit)
        q_clean = q.strip()
        if q_clean:
            like = f"%{q_clean}%"
            user_query = (
                select(User)
                .where(
                    or_(
                        User.employee_code.ilike(like),
                        User.name.ilike(like),
                    )
                )
                .order_by(User.created_at.desc())
                .limit(limit)
            )
        user_rows = db.execute(user_query).scalars().all()

        log_rows = db.execute(
            select(AttendanceLog, User.employee_code, User.name, Device.device_code)
            .outerjoin(User, AttendanceLog.user_id == User.id)
            .outerjoin(Device, AttendanceLog.device_id == Device.id)
            .order_by(AttendanceLog.timestamp.desc())
            .limit(limit)
        ).all()

        summary_rows = db.execute(
            select(AttendanceSummary, User.employee_code, User.name)
            .join(User, AttendanceSummary.user_id == User.id)
            .order_by(AttendanceSummary.date.desc())
            .limit(limit)
        ).all()

        users_html = "".join(
            f"<tr>"
            f"<td>{u.id}</td>"
            f"<td>{u.employee_code}</td>"
            f"<td>{u.name}</td>"
            f"<td>{u.position or ''}</td>"
            f"<td>{u.status}</td>"
            f"<td>{_fmt_dt(u.created_at)}</td>"
            f"<td>"
            f"<form method='post' action='/employees/update' style='display:inline-flex;gap:6px;align-items:center;margin-right:6px'>"
            f"<input type='hidden' name='user_id' value='{u.id}' />"
            f"<input name='name' value='{u.name}' style='width:130px' required />"
            f"<input name='position' value='{u.position or ''}' style='width:110px' />"
            f"<input name='status' value='{u.status}' style='width:90px' required />"
            f"<button type='submit'>Save</button>"
            f"</form>"
            f"<form method='post' action='/employees/delete' style='display:inline'>"
            f"<input type='hidden' name='user_id' value='{u.id}' />"
            f"<button type='submit' class='danger'>Delete</button>"
            f"</form>"
            f"</td>"
            f"</tr>"
            for u in user_rows
        )

    logs_html = "".join(
        f"<tr>"
        f"<td>{log.id}</td>"
        f"<td>{_fmt_dt(log.timestamp)}</td>"
        f"<td>{log.type}</td>"
        f"<td>{emp_code or ''}</td>"
        f"<td>{user_name or ''}</td>"
        f"<td>{dev_code or ''}</td>"
        f"<td>{log.confidence if log.confidence is not None else ''}</td>"
        f"</tr>"
        for log, emp_code, user_name, dev_code in log_rows
    )

    summaries_html = "".join(
        f"<tr>"
        f"<td>{summary.id}</td>"
        f"<td>{summary.date}</td>"
        f"<td>{emp_code}</td>"
        f"<td>{user_name}</td>"
        f"<td>{_fmt_dt(summary.checkin_time)}</td>"
        f"<td>{_fmt_dt(summary.checkout_time)}</td>"
        f"<td>{summary.status}</td>"
        f"</tr>"
        for summary, emp_code, user_name in summary_rows
    )

    msg_html = f"<div class='msg'>{msg}</div>" if msg else ""

    return f"""
<!doctype html>
<html>
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>Face Smart Admin UI</title>
  <style>
    :root {{
      --bg: #f3f7fb;
      --ink: #1f2733;
      --muted: #617086;
      --card: #ffffff;
      --line: #d9e2ee;
      --brand: #0b6bcb;
      --brand-soft: #e8f2ff;
      --danger: #b3261e;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: linear-gradient(180deg, #f8fbff 0%, var(--bg) 100%); color: var(--ink); font-family: Segoe UI, sans-serif; }}
    .shell {{ max-width: 1280px; margin: 0 auto; padding: 20px; }}
    .hero {{ background: radial-gradient(1200px 300px at 20% -20%, #dfeeff 0%, #f8fbff 45%, #f8fbff 100%); border: 1px solid var(--line); border-radius: 14px; padding: 18px 20px; margin-bottom: 14px; }}
    .hero h1 {{ margin: 0 0 6px 0; font-size: 28px; }}
    .hero p {{ margin: 0; color: var(--muted); }}
    .msg {{ background: var(--brand-soft); border: 1px solid #bdd8ff; border-radius: 10px; padding: 10px 12px; margin: 12px 0; color: #194d85; }}

    .stats {{ display: grid; grid-template-columns: repeat(3, minmax(140px, 1fr)); gap: 10px; margin-bottom: 14px; }}
    .stat {{ background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 12px; }}
    .stat .label {{ color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: 0.4px; }}
    .stat b {{ display: block; margin-top: 6px; font-size: 24px; }}

    .tabs {{ display: flex; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; }}
    .tab-btn {{ border: 1px solid var(--line); background: #fff; color: #2a3850; border-radius: 999px; padding: 8px 14px; cursor: pointer; font-weight: 600; }}
    .tab-btn.active {{ background: var(--brand); border-color: var(--brand); color: #fff; }}

    .panel {{ display: none; }}
    .panel.active {{ display: block; }}
    .card {{ background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 14px; margin-bottom: 12px; }}
    .card h2 {{ margin: 0 0 10px 0; font-size: 18px; }}

    .form-row {{ display: grid; grid-template-columns: repeat(4, minmax(120px, 1fr)); gap: 8px; }}
    .form-row input, .form-row button {{ width: 100%; }}

    input {{ padding: 8px; border: 1px solid var(--line); border-radius: 8px; }}
    button {{ padding: 8px 12px; border: 1px solid #c7d4e6; border-radius: 8px; background: #fff; cursor: pointer; }}
    button:hover {{ border-color: #9ab4d4; }}
    .danger {{ background: var(--danger); color: #fff; border: none; }}

    .table-wrap {{ max-height: 360px; overflow: auto; border: 1px solid var(--line); border-radius: 10px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; background: #fff; }}
    th, td {{ border-bottom: 1px solid #edf2f8; padding: 7px 8px; text-align: left; white-space: nowrap; }}
    th {{ position: sticky; top: 0; background: #eef3fa; z-index: 1; }}

    @media (max-width: 900px) {{
      .stats {{ grid-template-columns: 1fr; }}
      .form-row {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <div class=\"shell\">
    <div class=\"hero\">
      <h1>Attendance Admin Dashboard</h1>
      <p>Quan ly nhan vien, theo doi cham cong va cap nhat du lieu truc tiep tren 1 giao dien gon gang.</p>
    </div>

    {msg_html}

    <div class=\"stats\">
      <div class=\"stat\"><span class=\"label\">Total users</span><b>{users_total}</b></div>
      <div class=\"stat\"><span class=\"label\">Attendance logs</span><b>{logs_total}</b></div>
      <div class=\"stat\"><span class=\"label\">Attendance summaries</span><b>{summaries_total}</b></div>
    </div>

    <div class=\"tabs\">
      <button class=\"tab-btn active\" data-tab=\"employees\">Nhan vien</button>
      <button class=\"tab-btn\" data-tab=\"logs\">Cham cong</button>
      <button class=\"tab-btn\" data-tab=\"summary\">Tong hop ngay</button>
    </div>

    <section id=\"employees\" class=\"panel active\">
      <div class=\"card\">
        <h2>Create Employee</h2>
        <form method=\"post\" action=\"/employees/create\" class=\"form-row\">
          <input name=\"employee_code\" placeholder=\"employee_code (EMP001)\" required />
          <input name=\"name\" placeholder=\"name\" required />
          <input name=\"position\" placeholder=\"position\" />
          <input name=\"status\" placeholder=\"status\" value=\"active\" required />
          <button type=\"submit\">Create</button>
        </form>
      </div>

      <div class=\"card\">
        <h2>Employee List</h2>
        <form method=\"get\" action=\"/\" style=\"display:flex;gap:8px;margin-bottom:10px;flex-wrap:wrap\">
          <input name=\"q\" value=\"{q}\" placeholder=\"search employee_code or name\" />
          <input name=\"limit\" value=\"{limit}\" style=\"width:90px\" />
          <button type=\"submit\">Filter</button>
        </form>
        <div class=\"table-wrap\">
          <table>
            <thead>
              <tr><th>ID</th><th>Employee Code</th><th>Name</th><th>Position</th><th>Status</th><th>Created</th><th>Actions</th></tr>
            </thead>
            <tbody>{users_html}</tbody>
          </table>
        </div>
      </div>
    </section>

    <section id=\"logs\" class=\"panel\">
      <div class=\"card\">
        <h2>Attendance Logs</h2>
        <div class=\"table-wrap\">
          <table>
            <thead>
              <tr><th>ID</th><th>Timestamp</th><th>Type</th><th>Employee Code</th><th>Name</th><th>Device</th><th>Confidence</th></tr>
            </thead>
            <tbody>{logs_html}</tbody>
          </table>
        </div>
      </div>
    </section>

    <section id=\"summary\" class=\"panel\">
      <div class=\"card\">
        <h2>Update Attendance Summary</h2>
        <form method=\"post\" action=\"/summary/update\" class=\"form-row\">
          <input name=\"summary_id\" placeholder=\"summary_id\" required />
          <input name=\"checkin_time\" type=\"datetime-local\" />
          <input name=\"checkout_time\" type=\"datetime-local\" />
          <input name=\"status\" placeholder=\"status (checkin_muon;checkout_ve_som)\" />
          <button type=\"submit\">Update</button>
        </form>
      </div>

      <div class=\"card\">
        <h2>Attendance Summaries</h2>
        <div class=\"table-wrap\">
          <table>
            <thead>
              <tr><th>ID</th><th>Date</th><th>Employee Code</th><th>Name</th><th>Checkin</th><th>Checkout</th><th>Status</th></tr>
            </thead>
            <tbody>{summaries_html}</tbody>
          </table>
        </div>
      </div>
    </section>
  </div>

  <script>
    const buttons = Array.from(document.querySelectorAll('.tab-btn'));
    const panels = Array.from(document.querySelectorAll('.panel'));
    buttons.forEach((btn) => {{
      btn.addEventListener('click', () => {{
        const tab = btn.dataset.tab;
        buttons.forEach((b) => b.classList.remove('active'));
        panels.forEach((p) => p.classList.remove('active'));
        btn.classList.add('active');
        document.getElementById(tab).classList.add('active');
      }});
    }});
  </script>
</body>
</html>
"""


@admin_app.post("/employees/create")
def create_employee(
  employee_code: str = Form(...),
  name: str = Form(...),
  position: str | None = Form(default=None),
  status: str = Form(default="active"),
) -> RedirectResponse:
  employee_code = employee_code.strip()
  name = name.strip()
  status = status.strip() or "active"

  if not employee_code or not name:
    return RedirectResponse(url="/?msg=employee_code_and_name_required", status_code=303)

  with SessionLocal() as db:
    db.add(
      User(
        employee_code=employee_code,
        name=name,
        position=(position or "").strip() or None,
        status=status,
      )
    )
    try:
      db.commit()
    except IntegrityError:
      db.rollback()
      return RedirectResponse(url="/?msg=employee_code_exists", status_code=303)

  return RedirectResponse(url="/?msg=employee_created", status_code=303)


@admin_app.post("/employees/update")
def update_employee(
  user_id: str = Form(...),
  name: str = Form(...),
  position: str | None = Form(default=None),
  status: str = Form(...),
) -> RedirectResponse:
  with SessionLocal() as db:
    user = db.scalar(select(User).where(User.id == user_id).limit(1))
    if user is None:
      return RedirectResponse(url="/?msg=user_not_found", status_code=303)

    user.name = name.strip()
    user.position = (position or "").strip() or None
    user.status = status.strip() or "active"
    db.add(user)
    db.commit()

  return RedirectResponse(url="/?msg=employee_updated", status_code=303)


@admin_app.post("/employees/delete")
def delete_employee(user_id: str = Form(...)) -> RedirectResponse:
  with SessionLocal() as db:
    user = db.scalar(select(User).where(User.id == user_id).limit(1))
    if user is None:
      return RedirectResponse(url="/?msg=user_not_found", status_code=303)

    # Safety guard: avoid deleting employee with attendance data.
    has_logs = db.scalar(select(func.count(AttendanceLog.id)).where(AttendanceLog.user_id == user_id)) or 0
    has_summaries = db.scalar(
      select(func.count(AttendanceSummary.id)).where(AttendanceSummary.user_id == user_id)
    ) or 0
    if int(has_logs) > 0 or int(has_summaries) > 0:
      return RedirectResponse(url="/?msg=cannot_delete_user_with_attendance_data", status_code=303)

    db.delete(user)
    db.commit()

  return RedirectResponse(url="/?msg=employee_deleted", status_code=303)


@admin_app.post("/summary/update")
def update_summary(
    summary_id: str = Form(...),
    checkin_time: str | None = Form(default=None),
    checkout_time: str | None = Form(default=None),
    status: str | None = Form(default=None),
) -> RedirectResponse:
    with SessionLocal() as db:
        summary = db.scalar(
            select(AttendanceSummary).where(AttendanceSummary.id == summary_id).limit(1)
        )
        if summary is None:
            raise HTTPException(status_code=404, detail="Summary not found")

        new_checkin = _parse_dt_local(checkin_time)
        new_checkout = _parse_dt_local(checkout_time)

        if checkin_time is not None:
            summary.checkin_time = new_checkin
        if checkout_time is not None:
            summary.checkout_time = new_checkout
        if status is not None and status.strip():
            summary.status = status.strip()

        db.add(summary)
        db.commit()

    return RedirectResponse(url="/", status_code=303)
