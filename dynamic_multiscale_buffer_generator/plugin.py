"""
Dynamic multiscale buffer generator - QGIS plugin.

Copyright (C) 2025 by Henrique Ledo Lopes Pinho, Jessica Bassani de Oliveira,
Yzel Rondon Suarez

This program is free software; you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation; either version 2 of the License, or (at your option) any later
version.
"""

from qgis.core import QgsApplication

from .provider import DynamicMultiscaleBufferProvider


class DynamicMultiscaleBufferGeneratorPlugin:

    def __init__(self, iface):
        self.iface = iface
        self.provider = None

    def initProcessing(self):  # noqa: N802
        self.provider = DynamicMultiscaleBufferProvider()
        QgsApplication.processingRegistry().addProvider(self.provider)

    def initGui(self):  # noqa: N802
        self.initProcessing()

    def unload(self):
        if self.provider is not None:
            QgsApplication.processingRegistry().removeProvider(self.provider)
            self.provider = None
