"""
legal_layer.py — UN 1997 Legal Risk Overlay Layer
"""
from qgis.core import (
    QgsVectorLayer, QgsFeature, QgsGeometry,
    QgsPointXY, QgsField, QgsProject,
    QgsCategorizedSymbolRenderer, QgsRendererCategory,
    QgsMarkerSymbol
)
from qgis.PyQt.QtCore import QVariant


UN_ARTICLES = {
    "HIGH":   ["Art. 5 — Equitable Use", "Art. 7 — No Significant Harm", "Art. 9 — Data Exchange"],
    "MEDIUM": ["Art. 5 — Equitable Use", "Art. 7 — No Significant Harm"],
    "LOW":    ["Art. 5 — Equitable Use"],
    "MINIMAL": [],
}

RISK_COLORS = {
    "HIGH":    "#C0392B",
    "MEDIUM":  "#E67E22",
    "LOW":     "#F1C40F",
    "MINIMAL": "#27AE60",
}


def load_legal_layer(iface, basins):
    """Create UN 1997 legal risk overlay layer."""

    layer = QgsVectorLayer("Point?crs=EPSG:4326", "HSAE — UN 1997 Legal Risk", "memory")
    provider = layer.dataProvider()

    provider.addAttributes([
        QgsField("name",       QVariant.String),
        QgsField("region",     QVariant.String),
        QgsField("tdi_pct",    QVariant.Double),
        QgsField("risk",       QVariant.String),
        QgsField("articles",   QVariant.String),
        QgsField("country_up", QVariant.String),
        QgsField("country_dn", QVariant.String),
    ])
    layer.updateFields()

    features = []
    for b in basins:
        tdi = b.get("tdi", 0.0) * 100

        if tdi >= 55:
            risk = "HIGH"
        elif tdi >= 40:
            risk = "MEDIUM"
        elif tdi >= 25:
            risk = "LOW"
        else:
            risk = "MINIMAL"

        articles_str = " · ".join(UN_ARTICLES.get(risk, []))

        f = QgsFeature()
        f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(b["lon"], b["lat"])))
        f.setAttributes([
            b["name"], b["region"], round(tdi, 1),
            risk, articles_str,
            b.get("country_up", ""), b.get("country_dn", "")
        ])
        features.append(f)

    provider.addFeatures(features)
    layer.updateExtents()

    # Categorised by risk
    categories = []
    for risk, color in RISK_COLORS.items():
        symbol = QgsMarkerSymbol.createSimple({
            "name":          "triangle",
            "color":         color,
            "size":          "5",
            "outline_color": "white",
            "outline_width": "0.4",
        })
        cat = QgsRendererCategory(risk, symbol, risk)
        categories.append(cat)

    renderer = QgsCategorizedSymbolRenderer("risk", categories)
    layer.setRenderer(renderer)

    QgsProject.instance().addMapLayer(layer)
    iface.messageBar().pushSuccess(
        "HSAE Legal",
        "✅ UN 1997 legal risk layer loaded — 17 articles evaluated"
    )
    return layer
