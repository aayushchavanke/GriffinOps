import os
import zipfile
import xml.etree.ElementTree as ET
from typing import Optional

class DOCXReportGenerator:
    """
    Generates a detailed, comprehensive Microsoft Word Document (.docx)
    covering the end-to-end GriffinOps System Architecture, Mathematical Formulations,
    PyTorch TCN Forecasting, RCA Causal Graph Algorithms, Supabase Auth, and Telemetry Pipelines.
    """
    def __init__(self):
        self.output_dir = os.path.join(os.getcwd(), "docs_output")
        os.makedirs(self.output_dir, exist_ok=True)

    def generate_docx(self) -> str:
        filepath = os.path.join(self.output_dir, "GriffinOps_System_Architecture_and_Engineering_Doc.docx")
        
        try:
            import docx
            from docx.shared import Inches, Pt, RGBColor
            from docx.enum.text import WD_ALIGN_PARAGRAPH
            from docx.enum.table import WD_TABLE_ALIGNMENT

            doc = docx.Document()
            
            # Title Page Header
            title = doc.add_paragraph()
            title.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = title.add_run("🦅 GriffinOps Enterprise: Autonomous AI SRE Copilot")
            run.font.name = "Calibri"
            run.font.size = Pt(24)
            run.font.bold = True
            run.font.color.rgb = RGBColor(225, 29, 72) # Crimson Rose

            sub = doc.add_paragraph()
            sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run_sub = sub.add_run("Comprehensive System Architecture, PyTorch TCN Formulations & Engineering Documentation\nSIES GST AI & Data Science Team\n")
            run_sub.font.name = "Calibri"
            run_sub.font.size = Pt(12)
            run_sub.font.italic = True
            run_sub.font.color.rgb = RGBColor(100, 116, 139)

            doc.add_heading("1. Executive Summary & Core Vision", level=1)
            p1 = doc.add_paragraph(
                "GriffinOps is a Human-in-the-Loop AIOps platform designed for cloud-native microservice architectures. "
                "Traditional observability platforms (Datadog, Prometheus, Dynatrace) operate reactively—firing alerts after a server crashes or SLA thresholds breach. "
                "GriffinOps shifts this paradigm to predictive pre-mortems. By combining PyTorch Temporal Convolutional Networks (TCN) with causal graph inference (RCAEval), "
                "GriffinOps forecasts failure trajectories minutes before outages manifest, localizes the downstream root cause microservice, correlates recent CI/CD code deployment commits, "
                "and delivers automated background email alerts and downloadable PDF audit reports to developers."
            )

            doc.add_heading("2. System Architecture & End-to-End Telemetry Pipeline", level=1)
            p2 = doc.add_paragraph(
                "The GriffinOps architecture consists of 5 tightly integrated layers:\n"
                "1. Telemetry Ingestion Layer: Monitors live website HTTP endpoints and OpenTelemetry distributed traces (Latency, Traffic RPS, Error Rate, CPU Saturation, Memory Heap).\n"
                "2. Robust Normalization Engine: Transforms raw heterogeneous metric bounds into application-agnostic Z-scores (z = (x - mu) / (std + epsilon)) with variance smoothing.\n"
                "3. PyTorch TCN Forecaster: Uses 1D dilated causal convolutions with exponential receptive fields (dilation d = 1, 2, 4, 8) to forecast metric Z-score vectors 5–10 minutes into the future.\n"
                "4. Causal Diagnostic Engine: Traverses OpenTelemetry trace call graphs, computes PageRank causal ranking scores, and correlates timestamps with Git commits.\n"
                "5. Automated Background Watchdog: Background daemon loop checking predictions every 5 seconds, dispatching instant transactional email alerts to developers without requiring manual UI clicks."
            )

            doc.add_heading("3. PyTorch Temporal Convolutional Network (TCN) Mathematical Formulation", level=1)
            p3 = doc.add_paragraph(
                "Let X in R^(N x F x T) represent the sliding window tensor containing N microservices, F = 5 Golden Signals, and input history sequence T = 30.\n"
                "Dilated Causal 1D Convolution is defined as:\n"
                "y(t) = sum_{k=0}^{K-1} f(k) . x(t - d . k)\n"
                "where d = 2^l is the dilation factor at layer l, K = 3 is the kernel size, and f is the weight filter.\n"
                "Multi-Step Ahead Output Head maps the temporal representation to future Z-score predictions Z_pred in R^(N x F x H) over forecast horizon H = 10 time steps."
            )

            doc.add_heading("4. Supabase Auth & Multi-Tenant Security Engine", level=1)
            p4 = doc.add_paragraph(
                "User registration and login are authenticated via Supabase Auth (or JWT bearer session fallback). "
                "Multi-Tenant API Keys (gop_live_...) enable developers to assign custom key scopes to microservices, monitor endpoint request volume (RPM), and drill into API-specific AI visual illustrations and code fix recommendations."
            )

            doc.add_heading("5. Real Live Website Monitoring & Automated PDF/DOCX Export", level=1)
            p5 = doc.add_paragraph(
                "The real telemetry fetcher executes live HTTP requests against actual web services (e.g., https://httpbin.org, https://google.com), measuring real network response latency and SSL validity. "
                "Engineers can click 'Visit Live Monitored Website' directly from the portal UI and download detailed PDF audit reports and .docx architectural documentation."
            )

            doc.save(filepath)
            return filepath

        except ImportError:
            # Fallback docx zip builder if python-docx library is not installed
            return self._build_openxml_docx(filepath)

    def _build_openxml_docx(self, filepath: str) -> str:
        """
        Creates a valid Microsoft Word .docx OpenXML archive using Python standard zipfile.
        """
        content_types_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n'
            '  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>\n'
            '  <Default Extension="xml" ContentType="application/xml"/>\n'
            '  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>\n'
            '</Types>'
        )

        rels_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
            '  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>\n'
            '</Relationships>'
        )

        document_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">\n'
            '  <w:body>\n'
            '    <w:p><w:r><w:rPr><w:b/><w:sz w:val="36"/><w:color w:val="E11D48"/></w:rPr><w:t>GriffinOps Enterprise: System Architecture &amp; Engineering Documentation</w:t></w:r></w:p>\n'
            '    <w:p><w:r><w:rPr><w:i/><w:color w:val="64748B"/></w:rPr><w:t>Autonomous AI SRE Copilot &amp; Predictive Pre-Mortem Platform | SIES GST AI &amp; Data Science</w:t></w:r></w:p>\n'
            '    <w:p/><w:p><w:r><w:rPr><w:b/><w:sz w:val="28"/><w:color w:val="F59E0B"/></w:rPr><w:t>1. Executive Summary &amp; Core Vision</w:t></w:r></w:p>\n'
            '    <w:p><w:r><w:t>GriffinOps is an autonomous predictive AIOps platform. Unlike standard reactive monitoring tools (Datadog, Prometheus) that alert after an outage, GriffinOps uses PyTorch Temporal Convolutional Networks (TCN) to forecast metric failures 5-10 minutes in advance and RCAEval causal graph inference to localize root-cause microservices.</w:t></w:r></w:p>\n'
            '    <w:p/><w:p><w:r><w:rPr><w:b/><w:sz w:val="28"/><w:color w:val="F59E0B"/></w:rPr><w:t>2. End-to-End System Architecture</w:t></w:r></w:p>\n'
            '    <w:p><w:r><w:t>1. Telemetry Ingestion Engine: Ingests 4 Golden Signals (Latency, Traffic, Errors, Saturation) from OpenTelemetry traces and real live website pings.\n2. Robust Z-Score Normalizer: Scale-invariant z = (x - mean) / (std + 1e-5) transformation.\n3. PyTorch TCN Forecaster: 1D dilated causal convolution blocks predicting future metric vectors.\n4. Causal RCA Engine: Traces dependency call graphs, computes PageRank causal ranking, and correlates recent CI/CD Git commits.\n5. Automated Watchdog: Background daemon loop dispatching email notifications instantly to developers.</w:t></w:r></w:p>\n'
            '    <w:p/><w:p><w:r><w:rPr><w:b/><w:sz w:val="28"/><w:color w:val="F59E0B"/></w:rPr><w:t>3. PyTorch TCN Mathematical Formulation</w:t></w:r></w:p>\n'
            '    <w:p><w:r><w:t>Dilated Causal 1D Convolution: y(t) = sum(f(k) * x(t - d * k)). Dilation factors d = 2^l expand receptive fields exponentially over sequence history without future data leakage.</w:t></w:r></w:p>\n'
            '    <w:p/><w:p><w:r><w:rPr><w:b/><w:sz w:val="28"/><w:color w:val="F59E0B"/></w:rPr><w:t>4. Supabase Auth &amp; Multi-Tenant Security</w:t></w:r></w:p>\n'
            '    <w:p><w:r><w:t>User accounts authenticated via Supabase Auth. Multi-tenant API Keys (gop_live_...) enable key creation, revocation, and API-specific AI visual illustrations and code fix recommendations.</w:t></w:r></w:p>\n'
            '  </w:body>\n'
            '</w:document>'
        )

        with zipfile.ZipFile(filepath, "w", zipfile.ZIP_DEFLATED) as docx_zip:
            docx_zip.writestr("[Content_Types].xml", content_types_xml)
            docx_zip.writestr("_rels/.rels", rels_xml)
            docx_zip.writestr("word/document.xml", document_xml)

        return filepath
