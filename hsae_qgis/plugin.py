"""
plugin.py — HSAE QGIS Plugin Main Class
"""
import os
from qgis.PyQt.QtWidgets import QAction, QMenu
from qgis.PyQt.QtGui import QIcon
from qgis.core import QgsProject

from .basins_data import BASINS_26
from .basin_loader import load_basins_layer
from .tdi_visualiser import apply_tdi_style
from .legal_layer import load_legal_layer
from .export_tool import export_basin_data
from .dialog_main import HSAEMainDialog


class HSAEPlugin:

    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.actions = []
        self.menu = "HydroSovereign AI Engine"
        self.toolbar = None
        self.main_dialog = None

    def initGui(self):
        """Create menu entries and toolbar icons."""
        icon_path = os.path.join(self.plugin_dir, "icon.png")

        # ── Main toolbar ──────────────────────────────────────────────────────
        self.toolbar = self.iface.addToolBar("HSAE Toolbar")
        self.toolbar.setObjectName("HSAEToolbar")

        # Action 1 — Load 26 Basins
        self._add_action(
            icon_path,
            text="🌊 Load 26 Basins",
            callback=self.run_load_basins,
            tooltip="Load all 26 transboundary river basins as vector layers",
            add_to_toolbar=True,
        )

        # Action 2 — TDI Visualiser
        self._add_action(
            icon_path,
            text="📊 TDI Colour Map",
            callback=self.run_tdi_visualiser,
            tooltip="Apply Transparency Deficit Index graduated colour map",
            add_to_toolbar=True,
        )

        # Action 3 — Legal Risk Layer
        self._add_action(
            icon_path,
            text="⚖️ Legal Risk Layer",
            callback=self.run_legal_layer,
            tooltip="Overlay UN 1997 article violation status per basin",
            add_to_toolbar=True,
        )

        # Action 4 — Export
        self._add_action(
            icon_path,
            text="📥 Export Data",
            callback=self.run_export,
            tooltip="Export basin + TDI data to shapefile or GeoJSON",
            add_to_toolbar=True,
        )

        # Action 5 — Open Full Dashboard
        self._add_action(
            icon_path,
            text="🚀 Open HSAE Dashboard",
            callback=self.run_dashboard,
            tooltip="Open full HSAE main dialog",
            add_to_toolbar=True,
        )

    def _add_action(self, icon_path, text, callback, tooltip="", add_to_toolbar=False):
        icon = QIcon(icon_path)
        action = QAction(icon, text, self.iface.mainWindow())
        action.triggered.connect(callback)
        action.setToolTip(tooltip)
        if add_to_toolbar and self.toolbar:
            self.toolbar.addAction(action)
        self.iface.addPluginToMenu(self.menu, action)
        self.actions.append(action)
        return action

    def unload(self):
        """Remove the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(self.menu, action)
            self.iface.removeToolBarIcon(action)
        if self.toolbar:
            del self.toolbar

    # ── Callbacks ─────────────────────────────────────────────────────────────

    def run_load_basins(self):
        load_basins_layer(self.iface, BASINS_26)

    def run_tdi_visualiser(self):
        apply_tdi_style(self.iface)

    def run_legal_layer(self):
        load_legal_layer(self.iface, BASINS_26)

    def run_export(self):
        export_basin_data(self.iface)

    def run_dashboard(self):
        if self.main_dialog is None:
            self.main_dialog = HSAEMainDialog(self.iface, BASINS_26)
        self.main_dialog.show()
