import csv
import io

from django.http import HttpResponse


class ReportExportEngine:
    def response(self, report_result, export_format):
        export_format = (export_format or "csv").lower()
        if export_format == "csv":
            return self.csv_response(report_result)
        if export_format == "print":
            return self.print_response(report_result)
        if export_format == "excel":
            return self.xlsx_response(report_result)
        if export_format == "pdf":
            return self.pdf_response(report_result)
        return self.csv_response(report_result)

    def csv_response(self, report_result, content_type="text/csv", suffix="csv"):
        output = io.StringIO()
        writer = csv.writer(output)
        columns = report_result.get("columns") or []
        writer.writerow(columns)
        for row in report_result.get("rows") or []:
            writer.writerow([row.get(column, "") for column in columns])
        response = HttpResponse(output.getvalue(), content_type=content_type)
        response["Content-Disposition"] = f'attachment; filename="{report_result.get("key", "report")}.{suffix}"'
        return response

    def xlsx_response(self, report_result):
        from openpyxl import Workbook

        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Report"
        columns = report_result.get("columns") or []
        sheet.append(columns)
        for row in report_result.get("rows") or []:
            sheet.append([row.get(column, "") for column in columns])
        output = io.BytesIO()
        workbook.save(output)
        response = HttpResponse(
            output.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = f'attachment; filename="{report_result.get("key", "report")}.xlsx"'
        return response

    def pdf_response(self, report_result):
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet

        output = io.BytesIO()
        doc = SimpleDocTemplate(output, pagesize=landscape(A4), leftMargin=18, rightMargin=18, topMargin=18, bottomMargin=18)
        styles = getSampleStyleSheet()
        columns = report_result.get("columns") or []
        rows = report_result.get("rows") or []
        data = [columns] + [[str(row.get(column, ""))[:80] for column in columns] for row in rows[:500]]
        table = Table(data, repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
                    ("FONT", (0, 0), (-1, -1), "Helvetica", 7),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        doc.build([Paragraph(report_result.get("name") or "Report", styles["Title"]), Spacer(1, 8), table])
        response = HttpResponse(output.getvalue(), content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{report_result.get("key", "report")}.pdf"'
        return response

    def print_response(self, report_result, content_type="text/html", suffix="html"):
        rows = report_result.get("rows") or []
        columns = report_result.get("columns") or []
        head = "".join(f"<th>{column}</th>" for column in columns)
        body = "".join("<tr>" + "".join(f"<td>{row.get(column, '')}</td>" for column in columns) + "</tr>" for row in rows)
        html = f"<html><body><h1>{report_result.get('name')}</h1><table border='1'><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></body></html>"
        response = HttpResponse(html, content_type=content_type)
        response["Content-Disposition"] = f'inline; filename="{report_result.get("key", "report")}.{suffix}"'
        return response
