from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from xml.sax.saxutils import escape

def generate_certificate(
    output_path: str | Path,
    recipient_name: str,
    event_name: str,
    issuer_name: str,
    certificate_date: str,
) -> Path:
    """Render one personalized PDF using the application's single predefined design."""
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    page = landscape(A4)
    doc = SimpleDocTemplate(
        str(output), pagesize=page,
        rightMargin=54, leftMargin=54, topMargin=48, bottomMargin=48,
        title=f"Certificate - {recipient_name}",
        author=issuer_name,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "CertificateTitle", parent=styles["Title"], fontName="Helvetica-Bold",
        fontSize=30, leading=36, alignment=TA_CENTER, textColor=colors.HexColor("#17365D"),
        spaceAfter=18,
    )
    body_style = ParagraphStyle(
        "CertificateBody", parent=styles["BodyText"], fontName="Helvetica",
        fontSize=15, leading=23, alignment=TA_CENTER, textColor=colors.HexColor("#333333"),
    )
    name_style = ParagraphStyle(
        "RecipientName", parent=styles["Heading1"], fontName="Helvetica-Bold",
        fontSize=26, leading=32, alignment=TA_CENTER, textColor=colors.HexColor("#9A6B17"),
        spaceBefore=14, spaceAfter=14,
    )
    issuer_style = ParagraphStyle(
        "Issuer", parent=styles["BodyText"], fontName="Helvetica-Bold",
        fontSize=14, leading=20, alignment=TA_CENTER, textColor=colors.HexColor("#17365D"),
    )

    story = [
        Spacer(1, 14),
        Paragraph("CERTIFICATE OF COMPLETION", title_style),
        HRFlowable(width="70%", thickness=2, color=colors.HexColor("#C9A44C"), hAlign="CENTER"),
        Spacer(1, 25),
        Paragraph("This certificate is proudly presented to", body_style),
        Paragraph(escape(recipient_name), name_style),
        Paragraph(f"for successfully completing <b>{escape(event_name)}</b>.", body_style),
        Spacer(1, 24),
        Paragraph(f"Issued on {escape(certificate_date)}", body_style),
        Spacer(1, 18),
        Paragraph(escape(issuer_name), issuer_style),
        Spacer(1, 6),
        Paragraph("Authorized Issuer", body_style),
    ]
    doc.build(story)
    return output
