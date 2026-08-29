import os
import time
from typing import Optional

class PDFReportGenerator:
    """
    Generates professional PDF Pre-Mortem Audit Reports for GriffinOps SRE teams.
    Includes threat status badges, forecasted time-to-failure countdown, PyTorch TCN Z-score metrics,
    correlated Git commit details, and step-by-step developer remediation actions.
    """
    def __init__(self):
        self.output_dir = os.path.join(os.getcwd(), "pdf_reports")
        os.makedirs(self.output_dir, exist_ok=True)

    def generate_pdf_report(self, audit_report: dict) -> str:
        """
        Generates a PDF report document and returns the file path.
        Uses ReportLab if installed, otherwise creates a structured PDF binary document.
        """
        report_id = audit_report.get("report_id", "GO-REPORT")
        filename = f"GriffinOps_Audit_Report_{report_id}.pdf"
        filepath = os.path.join(self.output_dir, filename)

        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.lib import colors
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

            doc = SimpleDocTemplate(filepath, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
            styles = getSampleStyleSheet()
            
            title_style = ParagraphStyle(
                'DocTitle',
                parent=styles['Heading1'],
                fontName='Helvetica-Bold',
                fontSize=22,
                leading=26,
                textColor=colors.HexColor('#ff0055')
            )
            
            subtitle_style = ParagraphStyle(
                'SubTitle',
                parent=styles['Normal'],
                fontName='Helvetica',
                fontSize=10,
                leading=14,
                textColor=colors.HexColor('#64748b')
            )
            
            heading_style = ParagraphStyle(
                'SectionHead',
                parent=styles['Heading2'],
                fontName='Helvetica-Bold',
                fontSize=13,
                leading=16,
                textColor=colors.HexColor('#00f2fe'),
                spaceBefore=12,
                spaceAfter=6
            )
            
            body_style = ParagraphStyle(
                'BodyTextCustom',
                parent=styles['Normal'],
                fontName='Helvetica',
                fontSize=10,
                leading=14,
                textColor=colors.HexColor('#1e293b')
            )
            
            code_style = ParagraphStyle(
                'CodeCustom',
                parent=styles['Normal'],
                fontName='Courier',
                fontSize=9,
                leading=12,
                textColor=colors.HexColor('#0f172a')
            )

            elements = []

            # Header
            elements.append(Paragraph("🦅 GriffinOps Autonomous AI SRE Copilot", title_style))
            elements.append(Paragraph(f"PRE-MORTEM AUDIT REPORT &bull; Document ID: {report_id} &bull; Generated: {audit_report.get('generated_at')}", subtitle_style))
            elements.append(Spacer(1, 10))
            elements.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor('#ff0055'), spaceAfter=15))

            # Threat Status Banner
            rca = audit_report.get("root_cause_analysis", {})
            commit = audit_report.get("ci_cd_correlation", {})
            
            banner_text = f"<b>SYSTEM STATUS: {audit_report.get('system_status')}</b><br/>" \
                          f"Predicted Time to Failure: <b>{audit_report.get('forecasted_time_to_failure_human')}</b>"
            
            banner_table = Table([[Paragraph(banner_text, ParagraphStyle('Banner', parent=styles['Normal'], textColor=colors.white, fontName='Helvetica-Bold', fontSize=12, leading=16))]], colWidths=[540])
            banner_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#ef4444')),
                ('PADDING', (0, 0), (-1, -1), 10),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            elements.append(banner_table)
            elements.append(Spacer(1, 15))

            # Root Cause Diagnosis Grid
            elements.append(Paragraph("1. ROOT CAUSE DIAGNOSIS (PyTorch TCN & RCAEval)", heading_style))
            
            data_grid = [
                [Paragraph("<b>Target Microservice</b>", body_style), Paragraph(str(rca.get("service")), body_style)],
                [Paragraph("<b>Primary Metric Breach</b>", body_style), Paragraph(f"{rca.get('primary_metric')} (+{rca.get('max_z_score_deviation')} σ)", body_style)],
                [Paragraph("<b>Causal Confidence</b>", body_style), Paragraph(f"{int(rca.get('causal_confidence_score', 0.9) * 100)}%", body_style)],
                [Paragraph("<b>Impacted Blast Radius</b>", body_style), Paragraph(f"{audit_report.get('blast_radius', {}).get('affected_microservices_count', 2)} services", body_style)],
            ]
            
            t_grid = Table(data_grid, colWidths=[200, 340])
            t_grid.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
                ('PADDING', (0, 0), (-1, -1), 8),
            ]))
            elements.append(t_grid)
            elements.append(Spacer(1, 15))

            # Correlated CI/CD Commit
            elements.append(Paragraph("2. CORRELATED CI/CD DEPLOYMENT COMMIT", heading_style))
            commit_text = f"<b>Commit ID:</b> {commit.get('commit_id')}<br/>" \
                          f"<b>Author:</b> {commit.get('author')}<br/>" \
                          f"<b>Commit Message:</b> {commit.get('message')}<br/>" \
                          f"<b>Changed Files:</b> {', '.join(commit.get('changed_files', []))}"
            elements.append(Paragraph(commit_text, code_style))
            elements.append(Spacer(1, 15))

            # Actionable Remediation
            elements.append(Paragraph("3. RECOMMENDED SRE REMEDIATION ACTION", heading_style))
            action_text = f"<b>Developer Resolution Steps:</b><br/>{audit_report.get('suggested_action')}"
            
            action_table = Table([[Paragraph(action_text, body_style)]], colWidths=[540])
            action_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#e0f2fe')),
                ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#0284c7')),
                ('PADDING', (0, 0), (-1, -1), 12),
            ]))
            elements.append(action_table)

            doc.build(elements)
            return filepath

        except ImportError:
            # Fallback simple text PDF generator if reportlab is absent
            return self._generate_fallback_pdf(filepath, audit_report)

    def _generate_fallback_pdf(self, filepath: str, audit_report: dict) -> str:
        rca = audit_report.get("root_cause_analysis", {})
        commit = audit_report.get("ci_cd_correlation", {})
        
        pdf_content = (
            f"%PDF-1.4\n"
            f"1 0 obj <</Type /Catalog /Pages 2 0 R>> endobj\n"
            f"2 0 obj <</Type /Pages /Kids [3 0 R] /Count 1>> endobj\n"
            f"3 0 obj <</Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources <</Font <</F1 5 0 R>>>> >> endobj\n"
            f"4 0 obj <</Length 400>> stream\n"
            f"BT /F1 18 Tf 50 730 Td (GriffinOps Pre-Mortem Audit Report) Tj ET\n"
            f"BT /F1 12 Tf 50 700 Td (Report ID: {audit_report.get('report_id')}) Tj ET\n"
            f"BT /F1 12 Tf 50 680 Td (Status: {audit_report.get('system_status')}) Tj ET\n"
            f"BT /F1 12 Tf 50 660 Td (Time-to-Failure: {audit_report.get('forecasted_time_to_failure_human')}) Tj ET\n"
            f"BT /F1 12 Tf 50 630 Td (Target Service: {rca.get('service')}) Tj ET\n"
            f"BT /F1 12 Tf 50 610 Td (Primary Metric Breach: {rca.get('primary_metric')}) Tj ET\n"
            f"BT /F1 12 Tf 50 580 Td (Commit: {commit.get('commit_id')} by {commit.get('author')}) Tj ET\n"
            f"BT /F1 10 Tf 50 540 Td (Action: {audit_report.get('suggested_action')[:60]}...) Tj ET\n"
            f"endstream endobj\n"
            f"5 0 obj <</Type /Font /Subtype /Type1 /BaseFont /Helvetica>> endobj\n"
            f"xref\n0 6\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n0000000242 00000 n \n0000000695 00000 n \n"
            f"trailer <</Size 6 /Root 1 0 R>>\nstartxref\n770\n%%EOF\n"
        )
        with open(filepath, "w", encoding="latin-1") as f:
            f.write(pdf_content)
        return filepath
