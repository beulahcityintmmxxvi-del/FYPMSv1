from app.services.export_service import build_reports_pdf, build_reports_xlsx


def test_pdf_export_buffer(app):
    data = {
        "cards": [{"label": "Reports Generated", "value": 2}],
        "rows": [
            {
                "student": "Test Student",
                "matric_no": "2460141001",
                "department": "Computer Science",
                "supervisor": "Dr. A",
                "project_title": "Test Project",
                "stage": "chapter1",
                "version": 1,
                "status": "approved",
                "similarity": 18.5,
                "risk": "green",
                "submitted_at": "Jan 01, 2025 10:00",
            }
        ],
    }

    pdf = build_reports_pdf(data)
    assert pdf.read(4) == b"%PDF"


def test_xlsx_export_buffer(app):
    data = {
        "cards": [{"label": "Reports Generated", "value": 2}],
        "rows": [
            {
                "student": "Test Student",
                "matric_no": "2460141001",
                "department": "Computer Science",
                "supervisor": "Dr. A",
                "project_title": "Test Project",
                "stage": "chapter1",
                "version": 1,
                "status": "approved",
                "similarity": 18.5,
                "risk": "green",
                "submitted_at": "Jan 01, 2025 10:00",
            }
        ],
    }

    xlsx = build_reports_xlsx(data)
    assert len(xlsx.read()) > 0