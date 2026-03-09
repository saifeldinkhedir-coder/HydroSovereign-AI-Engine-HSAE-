"""
export_tool.py — Export Basin Data to Shapefile or GeoJSON
"""
import os
from qgis.core import QgsProject, QgsVectorFileWriter, QgsCoordinateReferenceSystem
from qgis.PyQt.QtWidgets import QFileDialog, QMessageBox


def export_basin_data(iface):
    """Export HSAE basin layer to shapefile or GeoJSON."""
    layer = _find_hsae_layer()
    if layer is None:
        QMessageBox.warning(
            None, "HSAE Export",
            "No HSAE layer found.\nPlease run '🌊 Load 26 Basins' first."
        )
        return

    # Ask user for file path
    path, fmt = QFileDialog.getSaveFileName(
        None,
        "Export HSAE Basin Data",
        os.path.expanduser("~/HSAE_Basins"),
        "GeoJSON (*.geojson);;Shapefile (*.shp)",
    )

    if not path:
        return

    driver = "GeoJSON" if path.endswith(".geojson") else "ESRI Shapefile"

    error = QgsVectorFileWriter.writeAsVectorFormat(
        layer, path, "UTF-8",
        QgsCoordinateReferenceSystem("EPSG:4326"),
        driver
    )

    if error[0] == QgsVectorFileWriter.NoError:
        iface.messageBar().pushSuccess(
            "HSAE Export",
            f"✅ Exported to: {os.path.basename(path)}"
        )
        QMessageBox.information(
            None, "HSAE Export",
            f"✅ Successfully exported:\n{path}"
        )
    else:
        QMessageBox.critical(
            None, "HSAE Export",
            f"❌ Export failed: {error[1]}"
        )


def _find_hsae_layer():
    for layer in QgsProject.instance().mapLayers().values():
        if "HSAE" in layer.name():
            return layer
    return None
