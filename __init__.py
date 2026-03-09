"""
HydroSovereign AI Engine — QGIS Plugin
Author: Seifeldin M.G. Alkedir
ORCID:  0000-0003-0821-2991
"""


def classFactory(iface):
    from .plugin import HSAEPlugin
    return HSAEPlugin(iface)
