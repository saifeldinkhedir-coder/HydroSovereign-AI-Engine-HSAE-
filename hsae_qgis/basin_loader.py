"""
basin_loader.py — Load 26 Basins as Vector Layer in QGIS
"""
from qgis.core import (
    QgsVectorLayer, QgsFeature, QgsGeometry,
    QgsPointXY, QgsField, QgsFields, QgsProject,
    QgsRectangle, QgsCoordinateReferenceSystem
)
from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtWidgets import QMessageBox


def load_basins_layer(iface, basins):
    """Create an in-memory point layer for all 26 basins and add to QGIS."""

    # Create memory layer
    layer = QgsVectorLayer("Point?crs=EPSG:4326", "HSAE — 26 Transboundary Basins", "memory")
    provider = layer.dataProvider()

    # Add fields
    provider.addAttributes([
        QgsField("id",          QVariant.String),
        QgsField("name",        QVariant.String),
        QgsField("region",      QVariant.String),
        QgsField("country_up",  QVariant.String),
        QgsField("country_dn",  QVariant.String),
        QgsField("tdi",         QVariant.Double),
        QgsField("tdi_pct",     QVariant.Double),
        QgsField("risk_level",  QVariant.String),
    ])
    layer.updateFields()

    # Add features
    features = []
    for b in basins:
        f = QgsFeature()
        f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(b["lon"], b["lat"])))
        tdi = b.get("tdi", 0.0)
        tdi_pct = round(tdi * 100, 1)

        if tdi_pct >= 55:
            risk = "HIGH — Art.9 Violation"
        elif tdi_pct >= 40:
            risk = "MEDIUM — Art.7 Violation"
        elif tdi_pct >= 25:
            risk = "LOW — Art.5 Violation"
        else:
            risk = "MINIMAL"

        f.setAttributes([
            b["id"], b["name"], b["region"],
            b.get("country_up", ""), b.get("country_dn", ""),
            tdi, tdi_pct, risk
        ])
        features.append(f)

    provider.addFeatures(features)
    layer.updateExtents()

    # Apply simple categorised style by region
    _apply_region_style(layer)

    QgsProject.instance().addMapLayer(layer)

    iface.messageBar().pushSuccess(
        "HSAE",
        f"✅ Loaded {len(basins)} basins — 7 regions · TDI calculated"
    )
    iface.mapCanvas().zoomToFullExtent()
    return layer


def _apply_region_style(layer):
    """Apply colour-coded style by region."""
    from qgis.core import (
        QgsCategorizedSymbolRenderer, QgsRendererCategory,
        QgsMarkerSymbol, QgsSimpleMarkerSymbolLayer
    )

    region_colors = {
        "Africa":       "#E74C3C",
        "Middle East":  "#F39C12",
        "Central Asia": "#8E44AD",
        "Asia":         "#27AE60",
        "Americas":     "#2980B9",
        "Europe":       "#1ABC9C",
        "Oceania":      "#D35400",
    }

    categories = []
    for region, color in region_colors.items():
        symbol = QgsMarkerSymbol.createSimple({
            "name": "circle",
            "color": color,
            "size": "4",
            "outline_color": "white",
            "outline_width": "0.4",
        })
        cat = QgsRendererCategory(region, symbol, region)
        categories.append(cat)

    renderer = QgsCategorizedSymbolRenderer("region", categories)
    layer.setRenderer(renderer)
    layer.triggerRepaint()
