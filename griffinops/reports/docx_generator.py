import os
import time
from typing import Optional

class DOCXReportGenerator:
    """
    Generates a detailed, comprehensive Microsoft Word Document (.docx)
    covering the end-to-end GriffinOps System Architecture, Mathematical Formulations,
    PyTorch TCN Forecasting, RCA Causal Graph Algorithms, Supabase Auth, and Telemetry Pipelines,
    complete with embedded high-resolution visual diagrams.
    """
    def __init__(self):
        self.output_dir = os.path.join(os.getcwd(), "docs_output")
        os.makedirs(self.output_dir, exist_ok=True)
        self.diagrams_dir = os.path.join(self.output_dir, "diagrams")
        os.makedirs(self.diagrams_dir, exist_ok=True)

    def _generate_diagram_images(self) -> dict:
        """
        Uses matplotlib to render 3 high-resolution architecture & neural network diagrams.
        Returns a dictionary of image file paths.
        """
        import matplotlib
        matplotlib.use("Agg") # Non-interactive backend
        import matplotlib.pyplot as plt
        import matplotlib.patches as patches

        image_paths = {}

        # -------------------------------------------------------------
        # Diagram 1: System Architecture & End-to-End Pipeline
        # -------------------------------------------------------------
        fig, ax = plt.subplots(figsize=(10, 6), dpi=300)
        ax.set_facecolor("#0b0f19")
        fig.patch.set_facecolor("#0b0f19")
        ax.axis("off")

        plt.title("GriffinOps Enterprise: End-to-End System Architecture & Telemetry Pipeline", 
                  fontsize=14, fontweight="bold", color="#f59e0b", pad=20)

        boxes = [
            {"title": "1. Telemetry Ingestion", "desc": "Live Site Pings (Latency/SSL)\nOpenTelemetry Traces (RPS/CPU)", "x": 0.05, "y": 0.6, "color": "#1e293b", "border": "#3b82f6"},
            {"title": "2. Z-Score Normalizer", "desc": "Robust Scale-Invariant Z-Score\nz = (x - μ) / (σ + 1e-5)", "x": 0.35, "y": 0.6, "color": "#1e293b", "border": "#8b5cf6"},
            {"title": "3. PyTorch TCN Forecaster", "desc": "1D Dilated Causal Convolutions\nPredicts Z-Scores t+1 to t+10", "x": 0.65, "y": 0.6, "color": "#1e293b", "border": "#ec4899"},
            {"title": "4. Causal RCA Engine", "desc": "PageRank Call Tree Traversal\nCI/CD Git Commit Correlation", "x": 0.35, "y": 0.15, "color": "#1e293b", "border": "#e11d48"},
            {"title": "5. Background Watchdog", "desc": "Real Email Dispatch (SMTP/Brevo)\nInteractive Dashboard & PDF/DOCX", "x": 0.65, "y": 0.15, "color": "#1e293b", "border": "#10b981"},
        ]

        for b in boxes:
            rect = patches.FancyBboxPatch((b["x"], b["y"]), 0.25, 0.28, boxstyle="round,pad=0.03", 
                                         linewidth=2, edgecolor=b["border"], facecolor=b["color"])
            ax.add_patch(rect)
            ax.text(b["x"] + 0.125, b["y"] + 0.21, b["title"], color="#ffffff", fontsize=10, fontweight="bold", ha="center")
            ax.text(b["x"] + 0.125, b["y"] + 0.08, b["desc"], color="#94a3b8", fontsize=8, ha="center", va="center")

        # Connective arrows
        arrowprops = dict(arrowstyle="->", color="#f59e0b", lw=2.5, mutation_scale=15)
        ax.annotate("", xy=(0.34, 0.74), xytext=(0.31, 0.74), arrowprops=arrowprops)
        ax.annotate("", xy=(0.64, 0.74), xytext=(0.61, 0.74), arrowprops=arrowprops)
        ax.annotate("", xy=(0.475, 0.44), xytext=(0.775, 0.59), arrowprops=arrowprops)
        ax.annotate("", xy=(0.64, 0.29), xytext=(0.61, 0.29), arrowprops=arrowprops)

        d1_path = os.path.join(self.diagrams_dir, "system_architecture_diagram.png")
        plt.tight_layout()
        plt.savefig(d1_path, facecolor=fig.get_facecolor(), edgecolor="none")
        plt.close(fig)
        image_paths["sys_arch"] = d1_path

        # -------------------------------------------------------------
        # Diagram 2: PyTorch TCN Neural Network Architecture
        # -------------------------------------------------------------
        fig, ax = plt.subplots(figsize=(10, 5), dpi=300)
        ax.set_facecolor("#0f172a")
        fig.patch.set_facecolor("#0f172a")
        ax.axis("off")

        plt.title("PyTorch Temporal Convolutional Network (TCN): Dilated Causal 1D Convolutions", 
                  fontsize=13, fontweight="bold", color="#38bdf8", pad=15)

        layers = [
            ("Input Sequence (t-30 to t)", 0.8, "#64748b"),
            ("Dilated Conv Layer 1 (d = 1)", 0.6, "#3b82f6"),
            ("Dilated Conv Layer 2 (d = 2)", 0.4, "#8b5cf6"),
            ("Dilated Conv Layer 3 (d = 4)", 0.2, "#ec4899"),
            ("Forecast Output (t+1 to t+10)", 0.02, "#10b981")
        ]

        for name, y, color in layers:
            rect = patches.FancyBboxPatch((0.15, y), 0.7, 0.1, boxstyle="round,pad=0.02",
                                         linewidth=1.5, edgecolor=color, facecolor="#1e293b")
            ax.add_patch(rect)
            ax.text(0.5, y + 0.05, name, color="#f8fafc", fontsize=10, fontweight="bold", ha="center", va="center")

        # Downward dilated connections
        for i in range(len(layers) - 1):
            y_start = layers[i][1]
            y_end = layers[i+1][1] + 0.1
            ax.annotate("", xy=(0.5, y_end), xytext=(0.5, y_start),
                        arrowprops=dict(arrowstyle="->", color="#f59e0b", lw=2))

        d2_path = os.path.join(self.diagrams_dir, "tcn_network_diagram.png")
        plt.tight_layout()
        plt.savefig(d2_path, facecolor=fig.get_facecolor(), edgecolor="none")
        plt.close(fig)
        image_paths["tcn_arch"] = d2_path

        # -------------------------------------------------------------
        # Diagram 3: Microservice Causal Graph (RCAEval)
        # -------------------------------------------------------------
        fig, ax = plt.subplots(figsize=(9, 5), dpi=300)
        ax.set_facecolor("#111827")
        fig.patch.set_facecolor("#111827")
        ax.axis("off")

        plt.title("Microservice Call Graph & PageRank Causal Localization (RCAEval)", 
                  fontsize=13, fontweight="bold", color="#e11d48", pad=15)

        nodes = {
            "Frontend Gateway": (0.2, 0.5, "#3b82f6", "Z-Score: +1.2 (Normal)"),
            "Checkout Service\n[ROOT CAUSE]": (0.5, 0.5, "#e11d48", "Z-Score: +4.8 (ANOMALY)\nCommit: 8f2a1b9"),
            "Payment Gateway": (0.8, 0.7, "#10b981", "Z-Score: +0.4 (Normal)"),
            "Inventory Service": (0.8, 0.3, "#10b981", "Z-Score: +0.8 (Normal)"),
        }

        for name, (x, y, color, subtext) in nodes.items():
            circle = patches.Circle((x, y), 0.12, linewidth=2, edgecolor=color, facecolor="#1f2937")
            ax.add_patch(circle)
            ax.text(x, y + 0.02, name, color="#ffffff", fontsize=9, fontweight="bold", ha="center", va="center")
            ax.text(x, y - 0.18, subtext, color="#9ca3af", fontsize=7.5, ha="center", va="center")

        # Causal dependency arrows
        arrow_style = dict(arrowstyle="->", color="#f59e0b", lw=2, mutation_scale=12)
        ax.annotate("", xy=(0.37, 0.5), xytext=(0.32, 0.5), arrowprops=arrow_style)
        ax.annotate("", xy=(0.67, 0.65), xytext=(0.62, 0.55), arrowprops=arrow_style)
        ax.annotate("", xy=(0.67, 0.35), xytext=(0.62, 0.45), arrowprops=arrow_style)

        d3_path = os.path.join(self.diagrams_dir, "causal_graph_diagram.png")
        plt.tight_layout()
        plt.savefig(d3_path, facecolor=fig.get_facecolor(), edgecolor="none")
        plt.close(fig)
        image_paths["causal_graph"] = d3_path

        return image_paths

    def generate_docx(self) -> str:
        filepath = os.path.join(self.output_dir, "GriffinOps_System_Architecture_and_Engineering_Doc.docx")
        
        # Render visual diagram images
        diagram_paths = self._generate_diagram_images()

        import docx
        from docx.shared import Inches, Pt, RGBColor
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.enum.table import WD_TABLE_ALIGNMENT

        doc = docx.Document()
        
        # Set standard margins (1 inch)
        for section in doc.sections:
            section.top_margin = Inches(1.0)
            section.bottom_margin = Inches(1.0)
            section.left_margin = Inches(1.0)
            section.right_margin = Inches(1.0)

        # -------------------------------------------------------------
        # Title & Document Header
        # -------------------------------------------------------------
        title = doc.add_paragraph()
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = title.add_run("🦅 GriffinOps Enterprise: Autonomous AI SRE Copilot")
        run.font.name = "Calibri"
        run.font.size = Pt(24)
        run.font.bold = True
        run.font.color.rgb = RGBColor(225, 29, 72) # Crimson Rose

        sub = doc.add_paragraph()
        sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run_sub = sub.add_run(
            "System Architecture, PyTorch TCN Mathematical Formulations & Engineering Specifications\n"
            "SIES Graduate School of Technology — AI & Data Science Department\n"
            f"Generated: {time.strftime('%B %d, %Y')} | Platform Status: ACTIVE OPERATIONAL\n"
        )
        run_sub.font.name = "Calibri"
        run_sub.font.size = Pt(11)
        run_sub.font.italic = True
        run_sub.font.color.rgb = RGBColor(100, 116, 139)

        doc.add_paragraph().paragraph_format.space_after = Pt(12)

        # -------------------------------------------------------------
        # Section 1: Executive Summary & Core Vision
        # -------------------------------------------------------------
        h1 = doc.add_heading("1. Executive Summary & Core Vision", level=1)
        h1.runs[0].font.color.rgb = RGBColor(245, 158, 11) # Warm Amber

        p1 = doc.add_paragraph(
            "GriffinOps is a Human-in-the-Loop AIOps platform engineered for cloud-native microservice architectures. "
            "Traditional observability platforms (Datadog, Prometheus, Dynatrace) operate reactively—firing alerts after a server crashes, "
            "database connections saturate, or SLA thresholds breach. GriffinOps shifts this paradigm to predictive pre-mortems. "
            "By combining PyTorch Temporal Convolutional Networks (TCN) with causal graph inference (RCAEval), GriffinOps forecasts failure trajectories "
            "5–10 minutes before outages manifest, localizes the downstream root-cause microservice, correlates recent CI/CD code deployment commits, "
            "and dispatches automated background email alerts with kubectl remediation commands to developers."
        )
        p1.paragraph_format.space_after = Pt(12)

        # -------------------------------------------------------------
        # Section 2: End-to-End System Architecture
        # -------------------------------------------------------------
        h2 = doc.add_heading("2. System Architecture & Telemetry Pipeline Flow", level=1)
        h2.runs[0].font.color.rgb = RGBColor(245, 158, 11)

        p2 = doc.add_paragraph(
            "The GriffinOps platform consists of 5 modular, tightly coupled engineering subsystems:\n\n"
            "• Telemetry Ingestion Layer: Monitors live website HTTP endpoints and OpenTelemetry distributed traces (Latency, Traffic RPS, Error Rate, CPU Saturation, Memory Heap).\n"
            "• Robust Normalization Engine: Converts heterogeneous metric scale bounds into application-agnostic Z-scores (z = (x - μ) / (σ + ε)) with variance smoothing.\n"
            "• PyTorch TCN Forecaster: Uses 1D dilated causal convolutions with exponential receptive fields (d = 1, 2, 4, 8) to predict metric vectors 5–10 minutes into the future.\n"
            "• Causal Diagnostic Engine: Traverses OpenTelemetry trace call graphs, computes PageRank causal ranking scores, and correlates timestamps with Git commits.\n"
            "• Automated Background Watchdog: Background daemon checking predictions every 5 seconds, dispatching instant transactional email alerts to developers."
        )
        p2.paragraph_format.space_after = Pt(12)

        # Insert Diagram 1
        if "sys_arch" in diagram_paths and os.path.exists(diagram_paths["sys_arch"]):
            p_img1 = doc.add_paragraph()
            p_img1.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p_img1.add_run().add_picture(diagram_paths["sys_arch"], width=Inches(6.2))
            cap1 = doc.add_paragraph()
            cap1.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run_c1 = cap1.add_run("Figure 1: GriffinOps End-to-End System Architecture & Data Pipeline Flow")
            run_c1.font.size = Pt(9.5)
            run_c1.font.italic = True
            run_c1.font.color.rgb = RGBColor(100, 116, 139)
            cap1.paragraph_format.space_after = Pt(18)

        # -------------------------------------------------------------
        # Section 3: PyTorch TCN Mathematical Formulation
        # -------------------------------------------------------------
        h3 = doc.add_heading("3. PyTorch Temporal Convolutional Network (TCN) Mathematical Formulation", level=1)
        h3.runs[0].font.color.rgb = RGBColor(245, 158, 11)

        p3 = doc.add_paragraph(
            "Let X in R^(N x F x T) represent the sliding window tensor containing N microservices, F = 5 Golden Signals (Latency, Error Rate, RPS, CPU, Memory), and input history sequence T = 30.\n\n"
            "1. Dilated Causal 1D Convolution:\n"
            "   y(t) = sum_{k=0}^{K-1} f(k) . x(t - d . k)\n"
            "   where d = 2^l is the dilation factor at layer l, K = 3 is kernel size, and f is the weight filter.\n\n"
            "2. Scale-Invariant Z-Score Normalization:\n"
            "   z_i(t) = (x_i(t) - μ_i) / (σ_i + 1e-5)\n\n"
            "3. Forecast Horizon Output Head:\n"
            "   Z_pred in R^(N x F x H) maps hidden representations to future predictions across forecast horizon H = 10 time steps."
        )
        p3.paragraph_format.space_after = Pt(12)

        # Insert Diagram 2
        if "tcn_arch" in diagram_paths and os.path.exists(diagram_paths["tcn_arch"]):
            p_img2 = doc.add_paragraph()
            p_img2.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p_img2.add_run().add_picture(diagram_paths["tcn_arch"], width=Inches(6.0))
            cap2 = doc.add_paragraph()
            cap2.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run_c2 = cap2.add_run("Figure 2: PyTorch 1D Dilated Causal Convolution Receptive Field Expansion")
            run_c2.font.size = Pt(9.5)
            run_c2.font.italic = True
            run_c2.font.color.rgb = RGBColor(100, 116, 139)
            cap2.paragraph_format.space_after = Pt(18)

        # -------------------------------------------------------------
        # Section 4: Microservice Causal Graph & RCAEval Localization
        # -------------------------------------------------------------
        h4 = doc.add_heading("4. Microservice Call Graph & Root Cause Evaluation (RCAEval)", level=1)
        h4.runs[0].font.color.rgb = RGBColor(245, 158, 11)

        p4 = doc.add_paragraph(
            "When the PyTorch TCN forecaster detects an anomaly threshold breach (Z-score > +3.0), "
            "GriffinOps constructs a directed dependency call graph G = (V, E) from OpenTelemetry trace headers. "
            "A personalized PageRank algorithm traverses downstream nodes, calculating root cause probabilities R_v for each microservice v in V. "
            "The microservice with the highest causal score is flagged alongside its correlated Git commit hash."
        )
        p4.paragraph_format.space_after = Pt(12)

        # Insert Diagram 3
        if "causal_graph" in diagram_paths and os.path.exists(diagram_paths["causal_graph"]):
            p_img3 = doc.add_paragraph()
            p_img3.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p_img3.add_run().add_picture(diagram_paths["causal_graph"], width=Inches(5.8))
            cap3 = doc.add_paragraph()
            cap3.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run_c3 = cap3.add_run("Figure 3: Directed Microservice Dependency Call Graph & Root Cause Causal Ranking")
            run_c3.font.size = Pt(9.5)
            run_c3.font.italic = True
            run_c3.font.color.rgb = RGBColor(100, 116, 139)
            cap3.paragraph_format.space_after = Pt(18)

        # -------------------------------------------------------------
        # Section 5: Architectural Performance & Feature Comparison Table
        # -------------------------------------------------------------
        h5 = doc.add_heading("5. Platform Comparison & Performance Benchmarks", level=1)
        h5.runs[0].font.color.rgb = RGBColor(245, 158, 11)

        table = doc.add_table(rows=5, cols=4)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        hdr_cells = table.rows[0].cells
        headers = ["Capability / Feature", "Datadog / Dynatrace", "Standard Prometheus", "GriffinOps Enterprise"]
        for i, text in enumerate(headers):
            hdr_cells[i].text = text
            hdr_cells[i].paragraphs[0].runs[0].font.bold = True
            hdr_cells[i].paragraphs[0].runs[0].font.color.rgb = RGBColor(225, 29, 72)

        row_data = [
            ("Detection Timing", "Reactive (Post-Failure)", "Reactive (Threshold Alert)", "Predictive (5-10m Pre-Mortem)"),
            ("Root Cause Localization", "Manual Log Search", "Manual Metric Graphing", "Automated PageRank Call Tree"),
            ("CI/CD Git Correlation", "Add-on Module", "Not Available", "Automated Git Commit Match"),
            ("Email & Report Automation", "Basic Email", "Webhook / PagerDuty", "Dual Email (SMTP/Brevo) & PDF/DOCX")
        ]

        for row_idx, data in enumerate(row_data):
            row_cells = table.rows[row_idx + 1].cells
            for col_idx, text in enumerate(data):
                row_cells[col_idx].text = text

        doc.add_paragraph().paragraph_format.space_after = Pt(18)

        # Save document
        doc.save(filepath)
        return filepath
