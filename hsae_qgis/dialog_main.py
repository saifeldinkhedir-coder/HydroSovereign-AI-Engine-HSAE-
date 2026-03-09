"""
dialog_main.py — HSAE Main Dashboard Dialog
"""
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem,
    QTabWidget, QWidget, QTextEdit, QHeaderView
)
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QFont, QColor
import webbrowser


class HSAEMainDialog(QDialog):

    def __init__(self, iface, basins):
        super().__init__(iface.mainWindow())
        self.iface = iface
        self.basins = basins
        self.setWindowTitle("🌊 HydroSovereign AI Engine v6.0.0")
        self.setMinimumSize(900, 600)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout()

        # ── Header ────────────────────────────────────────────────────────────
        header = QLabel("🌊 HydroSovereign AI Engine — HSAE v6.0.0")
        header.setAlignment(Qt.AlignCenter)
        font = QFont(); font.setPointSize(14); font.setBold(True)
        header.setFont(font)
        layout.addWidget(header)

        sub = QLabel("26 Basins · 7 Regions · TDI · UN 1997 · GEE · AI  |  Author: Seifeldin M.G. Alkedir · ORCID: 0000-0003-0821-2991")
        sub.setAlignment(Qt.AlignCenter)
        layout.addWidget(sub)

        # ── Tabs ──────────────────────────────────────────────────────────────
        tabs = QTabWidget()

        # Tab 1 — Basin Registry
        tabs.addTab(self._build_basin_tab(), "🌍 26 Basins")

        # Tab 2 — TDI Summary
        tabs.addTab(self._build_tdi_tab(), "📊 TDI Summary")

        # Tab 3 — About
        tabs.addTab(self._build_about_tab(), "ℹ️ About")

        layout.addWidget(tabs)

        # ── Buttons ───────────────────────────────────────────────────────────
        btn_layout = QHBoxLayout()

        btn_app = QPushButton("🚀 Open Live App")
        btn_app.clicked.connect(lambda: webbrowser.open("https://hsae-v600.streamlit.app"))
        btn_layout.addWidget(btn_app)

        btn_github = QPushButton("📦 GitHub Repo")
        btn_github.clicked.connect(lambda: webbrowser.open("https://github.com/saifeldinkhedir-coder/HydroSovereign-AI-Engine-HSAE-"))
        btn_layout.addWidget(btn_github)

        btn_close = QPushButton("✖ Close")
        btn_close.clicked.connect(self.close)
        btn_layout.addWidget(btn_close)

        layout.addLayout(btn_layout)
        self.setLayout(layout)

    def _build_basin_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()

        table = QTableWidget(len(self.basins), 6)
        table.setHorizontalHeaderLabels(["Name", "Region", "Upstream", "Downstream", "TDI %", "Risk"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        RISK_COLORS = {
            "HIGH":    QColor("#FADBD8"),
            "MEDIUM":  QColor("#FDEBD0"),
            "LOW":     QColor("#FEF9E7"),
            "MINIMAL": QColor("#EAFAF1"),
        }

        for i, b in enumerate(self.basins):
            tdi_pct = round(b.get("tdi", 0) * 100, 1)
            if tdi_pct >= 55:   risk = "HIGH"
            elif tdi_pct >= 40: risk = "MEDIUM"
            elif tdi_pct >= 25: risk = "LOW"
            else:               risk = "MINIMAL"

            row_data = [b["name"], b["region"], b.get("country_up",""), b.get("country_dn",""), f"{tdi_pct}%", risk]
            for j, val in enumerate(row_data):
                item = QTableWidgetItem(str(val))
                item.setBackground(RISK_COLORS.get(risk, QColor("white")))
                table.setItem(i, j, item)

        layout.addWidget(table)
        widget.setLayout(layout)
        return widget

    def _build_tdi_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()

        text = QTextEdit()
        text.setReadOnly(True)

        high   = [b for b in self.basins if b.get("tdi",0)*100 >= 55]
        medium = [b for b in self.basins if 40 <= b.get("tdi",0)*100 < 55]
        low    = [b for b in self.basins if 25 <= b.get("tdi",0)*100 < 40]
        minimal= [b for b in self.basins if b.get("tdi",0)*100 < 25]

        html = f"""
        <h2>📊 TDI Summary — 26 Basins</h2>
        <p><b>Formula:</b> TDI = (I_adj − Q_out) / (I_adj + 0.001) | ATDI = mean(TDI) × 100</p>
        <p><b>α = 0.30</b> · I_adj = max(0, I_in − 0.30 × (ET_PM + ET_MODIS))</p>
        <hr>
        <h3 style="color:#C0392B;">🔴 HIGH Risk — Art.9 Violation (≥ 55%) — {len(high)} basins</h3>
        <p>{' · '.join(b['name'] for b in high)}</p>
        <h3 style="color:#E67E22;">🟠 MEDIUM Risk — Art.7 Violation (40–55%) — {len(medium)} basins</h3>
        <p>{' · '.join(b['name'] for b in medium)}</p>
        <h3 style="color:#F1C40F;">🟡 LOW Risk — Art.5 Violation (25–40%) — {len(low)} basins</h3>
        <p>{' · '.join(b['name'] for b in low)}</p>
        <h3 style="color:#27AE60;">🟢 MINIMAL Risk (< 25%) — {len(minimal)} basins</h3>
        <p>{' · '.join(b['name'] for b in minimal)}</p>
        <hr>
        <p><b>Legal Thresholds (UN 1997):</b><br>
        ≥ 25% → Art. 5 Equitable Use | ≥ 40% → Art. 7 No Significant Harm | ≥ 55% → Art. 9 Data Exchange</p>
        """
        text.setHtml(html)
        layout.addWidget(text)
        widget.setLayout(layout)
        return widget

    def _build_about_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()
        text = QTextEdit()
        text.setReadOnly(True)
        text.setHtml("""
        <h2>🌊 HydroSovereign AI Engine — HSAE v6.0.0</h2>
        <p><b>Author:</b> Seifeldin M.G. Alkedir — سيف الدين محمد قسم الله الخضر</p>
        <p><b>ORCID:</b> 0000-0003-0821-2991</p>
        <p><b>Email:</b> saifeldinkhedir@gmail.com</p>
        <p><b>Institution:</b> University of Khartoum · Institute of Environmental Studies</p>
        <hr>
        <p><b>Description:</b> The first open-source platform integrating multi-source satellite
        remote sensing, conceptual rainfall-runoff modelling, machine learning, and international
        water law automation for 26 transboundary river basins across 7 geographic regions.</p>
        <hr>
        <p><b>Live App:</b> https://hsae-v600.streamlit.app</p>
        <p><b>GitHub:</b> https://github.com/saifeldinkhedir-coder/HydroSovereign-AI-Engine-HSAE-</p>
        <p><b>License:</b> MIT</p>
        """)
        layout.addWidget(text)
        widget.setLayout(layout)
        return widget
