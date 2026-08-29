# GriffinOps 🦅

**Predictive Microservice Incident Response & Root Cause Analysis Platform**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Framework](https://img.shields.io/badge/framework-FastAPI-green.svg)](https://fastapi.tiangolo.com/)
[![Deep Learning](https://img.shields.io/badge/model-PyTorch%20TCN-orange.svg)](https://pytorch.org/)
[![RCA Paper](https://img.shields.io/badge/ACM%20FSE%202026-LagRCA-purple.svg)](https://dl.acm.org/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

---

## 📌 Executive Summary

**GriffinOps** is an autonomous, AI-driven predictive observability and Root Cause Analysis (RCA) platform engineered to **predict microservice crashes and downtimes before they occur ($T+240\text{s}$ lead-time)** with high accuracy. 

It synthesizes state-of-the-art 2026 peer-reviewed academic research (**LagRCA – ACM FSE 2026**, **RCASage Granger Causality 2026**, **RCAEval PageRank 2022**) with robust OpenTelemetry/SigNoz data ingestion to eliminate alert fatigue, resolve propagation delay noise, and pinpoint failing root-cause components in complex distributed architectures.

---

## ⚡ Core Key Features

### 1. 🔮 Early Warning Crash Forecasting (PyTorch TCN)
- Uses a **1D Dilated Causal Convolutional Network (Temporal Convolutional Network)** to forecast microservice metric trajectories ($T+30\text{s} \dots T+240\text{s}$) before failure events occur.
- Replaces naive thresholding with pre-mortem failure probability scoring ($0.0 \dots 1.0$).

### 2. ⏱️ LagRCA Spatio-Temporal Causal Inference (*ACM FSE 2026*)
- Implements **Lag-Aware Cross-Correlation** based on the *ACM FSE 2026 Distinguished Paper Award*:
  $$\text{Lag-Aware Score}(u \to v) = \max_{\tau \in [0, \tau_{\max}]} \text{CrossCorr}\Big(X_u(t), X_v(t + \tau)\Big)$$
- Handles propagation delays ($\tau \in [0, 90\text{s}]$) across call trees, preventing downstream symptoms from being falsely accused as the root cause.

### 3. 🎯 Granger Causality Discovery Engine (*RCASage 2026*)
- Pairwise Granger Causality F-tests (`statsmodels` Vector Autoregression):
  $$F_{\text{Granger}}(X \to Y) = \ln \left( \frac{\text{Var}(\varepsilon_{Y \text{ (without } X\text{)}})}{\text{Var}(\varepsilon_{Y \text{ (with } X\text{)}})} \right)$$
- Mathematically proves directional causal dependency ($X \to Y$) vs downstream noise ($Y \leftarrow X$).

### 4. 📊 Robust MAD Metric Normalization (*Leys et al. 2013*)
- Upgraded anomaly detection from baseline-poisoned Gaussian Z-scores to **Robust Median Absolute Deviation (MAD)**:
  $$M_t = \frac{0.6745 \cdot (x_t - \text{Median}(X))}{\text{MAD}(X) + \varepsilon}$$
- Configured adaptive thresholds ($M \ge 3.5$ for internal microservices, $M \ge 5.0$ for public WAN targets).

### 5. 🔌 SigNoz & OpenTelemetry ClickHouse Integration
- Queries SigNoz ClickHouse API (`/api/v5/query_range`) and exports OpenTelemetry OTLP HTTP spans (`/v1/traces`).
- Graceful automatic fallback to live HTTP telemetry monitoring when SigNoz endpoint is unreachable.

### 6. 🌐 Live Real Website Telemetry Monitoring
- Real-time HTTP GET telemetry ping engine for monitoring live external web apps (e.g. GitHub, Google, Wikipedia, REST APIs).

### 7. 🔐 Multi-Tenant Supabase Authentication
- Role-Based Access Control (RBAC) supporting `Admin`, `SRE_Operator`, and `Auditor_Viewer` roles.

### 8. 🔔 Multi-Channel Alerting & Professional Reporting
- Instant Slack Webhook alert notifications with severity categorization (`SEV-1 Critical`, `SEV-2 Warning`).
- Automated generation of downloadable **PDF** and **DOCX** audit reports.

---

## 🛠️ Repository Architecture

```text
GriffinOps/
├── griffinops/
│   ├── alerts/          # Slack Webhook & HTML Email preview generators
│   ├── api/             # FastAPI REST endpoints & routes
│   ├── auth/            # Multi-Tenant Supabase JWT RBAC Authentication
│   ├── frontend/        # Glassmorphic Interactive Dashboard UI
│   ├── models/          # PyTorch 1D Dilated Causal Convolution TCN Engine
│   ├── rca/             # RCAEval PageRank, LagRCA (2026), & Granger Causality (2026)
│   ├── reports/         # ReportLab PDF & python-docx Master Audit Report generators
│   ├── simulation/      # Failure injection & chaos engineering telemetry generator
│   └── telemetry/       # SigNoz ClickHouse Ingestion & Robust MAD Normalizer
├── tests/               # Full Unit & Integration Test Suite (14 Tests)
│   ├── test_all.py
│   ├── test_lag_granger_rca.py
│   ├── test_rcaeval_signoz.py
│   └── test_real_websites.py
├── docs_output/         # Master Architecture & System Diagrams
├── email_previews/      # Rendered HTML email preview templates (.gitkeep)
├── pdf_reports/         # Generated PDF Audit Reports (.gitkeep)
├── .env                 # Environment Configuration
├── requirements.txt     # Python Dependencies Stack
├── run_griffinops.py    # Master Server Entry Point
└── README.md            # Project Documentation
```

---

## 🚀 Quick Start Guide

### 1. Prerequisites
- Python **3.10+** (Python 3.13 supported)
- Pip package manager

### 2. Installation
Clone the repository and install required scientific dependencies:

```bash
git clone https://github.com/aayushchavanke/GriffinOps.git
cd GriffinOps
pip install -r requirements.txt
```

### 3. Launch GriffinOps Server
Run the FastAPI master server:

```bash
python run_griffinops.py
```
- Interactive API Documentation: `http://localhost:8000/docs`
- Glassmorphic Frontend Dashboard: `http://localhost:8000/`

---

## 🧪 Running Automated Tests

Run the complete 14-test suite verifying PyTorch TCN, Robust MAD Z-scores, RCAEval PageRank, LagRCA, Granger Causality, and Live Website Monitoring:

```bash
python -m unittest discover tests
```

To run a live telemetry ping test against real public websites:

```bash
python -m unittest tests/test_real_websites.py
```

---

## 📡 API Reference Overview

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/v1/telemetry/signoz/status` | Check SigNoz ClickHouse API connection status |
| `POST` | `/api/v1/telemetry/ingest` | Ingest OpenTelemetry metric/trace batch |
| `POST` | `/api/v1/rca/analyze` | Execute 2026 SOTA RCA (LagRCA + Granger + RCAEval) |
| `GET` | `/api/v1/real-monitor/targets` | List registered live website monitoring targets |
| `POST` | `/api/v1/real-monitor/live` | Trigger live HTTP telemetry pings & RCA diagnosis |
| `POST` | `/api/v1/reports/pdf` | Generate downloadable PDF pre-mortem audit report |

---

## 📜 Scientific References & Citations

1. **LagRCA (2026)**: Shenglin Zhang, Dan Pei, et al. *"Bridging the Delay: Lag-Aware Spatio-Temporal Causal Inference for Microservice Root Cause Analysis"*. In *Proceedings of the 34th ACM SIGSOFT International Conference on the Foundations of Software Engineering (ACM FSE 2026)*. (**Distinguished Paper Award**)
2. **RCASage (2026)**: *"AI-Driven Root Cause Analysis Framework for Distributed Microservices Architectures"*. Neural Granger Causal Discovery Engine.
3. **RCAEval (2022)**: Luan Pham et al. *"RCAEval: A Benchmark for Root Cause Analysis in Microservices"*. In *ACM ISSTA 2022 / IEEE INFOCOM Microcause*.
4. **MAD Normalization (2013)**: Christophe Leys et al. *"Detecting outliers: Do not use standard deviation around the mean, use absolute deviation around the median"*. In *Journal of Experimental Social Psychology*.

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.
