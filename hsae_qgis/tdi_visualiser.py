"""
tdi_visualiser.py — Apply TDI Graduated Colour Map to Basin Layer
"""
from qgis.core import (
    QgsGraduatedSymbolRenderer, QgsRendererRange,
    QgsMarkerSymbol, QgsStyle, QgsClassificationQuantile,
    QgsProject
)
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtWidgets import QMessageBox


# ATDI thresholds (UN 1997 legal triggers)
TDI_BREAKS = [
    (0.00,  25.0,  "#2ECC71", "MINIMAL  (< 25%)"),
    (25.0,  40.0,  "#F1C40F", "LOW      — Art. 5  (25–40%)"),
    (40.0,  55.0,  "#E67E22", "MEDIUM   — Art. 7  (40–55%)"),
    (55.0, 100.0,  "#E74C3C", "HIGH     — Art. 9  (≥ 55%)"),
]


def apply_tdi_style(iface):
    """Find HSAE basin layer and apply TDI graduated style."""
    layer = _find_basin_layer()
    if layer is None:
        QMessageBox.warning(
            None, "HSAE",
            "No HSAE basin layer found.\nPlease run '🌊 Load 26 Basins' first."
        )
        return

    ranges = []
    for lo, hi, color, label in TDI_BREAKS:
        symbol = QgsMarkerSymbol.createSimple({
            "name":            "circle",
            "color":           color,
            "size":            "5",
            "outline_color":   "white",
            "outline_width":   "0.5",
        })
        rng = QgsRendererRange(lo, hi, symbol, label)
        ranges.append(rng)

    renderer = QgsGraduatedSymbolRenderer("tdi_pct", ranges)
    layer.setRenderer(renderer)
    layer.triggerRepaint()

    iface.messageBar().pushSuccess(
        "HSAE TDI",
        "✅ TDI colour map applied — 4 risk tiers · UN 1997 thresholds"
    )


def _find_basin_layer():
    """Return the first HSAE basin layer in the project."""
    for layer in QgsProject.instance().mapLayers().values():
        if "HSAE" in layer.name() and "Basin" in layer.name():
            return layer
    return None
