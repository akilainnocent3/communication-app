"""Call-log export (CSV or XLSX). Needs `calls.export`; numbers are masked (+2557•••••331) on every phone where the user
lacks `can_export` (admins have it everywhere). Notes are never exported. Every export is audited with its filters.

XLSX is written directly (a minimal Office Open XML workbook: one sheet, inline strings), so no spreadsheet library is
needed on the server (decision 69).
"""

from __future__ import annotations

import csv
import io
import zipfile
from xml.sax.saxutils import escape

from modules.audit.services import record
from modules.devices.services.phone import display_number, mask

from . import access

MAX_ROWS = 50_000
HEADERS = ["Date", "Time", "Direction", "Result", "Number", "Name", "Phone", "Office", "SIM", "Ring (s)", "Talk (s)", "After hours", "Outcome", "Origin", "Returned at"]


def rows(user, calls, tz) -> list[list]:
    exportable = {}
    result = []
    for call in calls.select_related("device", "device__office", "sim_line", "customer").prefetch_related("annotations__outcome")[:MAX_ROWS]:
        if call.device_id not in exportable:
            exportable[call.device_id] = access.permissions_for(user, call.device)[access.EXPORT]
        number = display_number(call.number_e164) if exportable[call.device_id] else mask(call.number_e164)
        local = call.started_at.astimezone(tz)
        outcome = next((a.outcome.name for a in call.annotations.all() if a.outcome_id), "")
        name = (call.customer.display_name if call.customer_id else "") or call.contact_name_on_phone
        result.append([
            local.date().isoformat(), local.strftime("%H:%M:%S"), call.get_direction_display(), call.get_result_display(), number if call.number_e164 else "Private number",
            name, call.device.name, call.device.office.name, call.sim_line.label if call.sim_line_id else "", call.ring_seconds, call.talk_seconds,
            "yes" if call.is_after_hours else "no", outcome, call.get_origin_display(), call.returned_at.astimezone(tz).isoformat(timespec="minutes") if call.returned_at else "",
        ])
    return result


def to_csv(data: list[list]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(HEADERS)
    for row in data:
        # Spreadsheet formula injection: a cell starting with = + - @ is text, not a formula.
        writer.writerow([f"'{v}" if isinstance(v, str) and v[:1] in ("=", "+", "-", "@") and not v[1:2].isdigit() else v for v in row])
    return buffer.getvalue().encode("utf-8-sig")


def _cell(ref: str, value) -> str:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f'<c r="{ref}"><v>{value}</v></c>'
    return f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{escape(str(value))}</t></is></c>'


def _col(index: int) -> str:
    name = ""
    index += 1
    while index:
        index, rem = divmod(index - 1, 26)
        name = chr(65 + rem) + name
    return name


def to_xlsx(data: list[list]) -> bytes:
    lines = []
    for r, row in enumerate([HEADERS, *data], start=1):
        lines.append(f'<row r="{r}">' + "".join(_cell(f"{_col(c)}{r}", v) for c, v in enumerate(row)) + "</row>")
    sheet = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
             f'<sheetData>{"".join(lines)}</sheetData></worksheet>')
    files = {
        "[Content_Types].xml": ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                                '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>'
                                '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                                '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>'),
        "_rels/.rels": ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>'),
        "xl/workbook.xml": ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Calls" sheetId="1" r:id="rId1"/></sheets></workbook>'),
        "xl/_rels/workbook.xml.rels": ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                                       '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>'),
        "xl/worksheets/sheet1.xml": sheet,
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def export(user, calls, tz, fmt: str, filters: dict, request=None) -> tuple[bytes, str, str]:
    data = rows(user, calls, tz)
    record("calls.export", request=request, actor=user, target_type="calls", metadata={"format": fmt, "rows": len(data), "filters": filters})
    if fmt == "xlsx":
        return to_xlsx(data), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "calls.xlsx"
    return to_csv(data), "text/csv; charset=utf-8", "calls.csv"
