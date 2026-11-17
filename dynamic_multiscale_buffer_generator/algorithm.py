"""
**********************************************************************************************************************
    Dynamic multiscale buffer generator.py                                                                           *
    -----------------------------------------------------------------------------------------------------------------*
    Date                 : August 2025                                                                               *
    Copyright            : (C) 2025 by Henrique Ledo Lopes Pinho, Jéssica Bassani de Oliveira, Yzel Rondon Súarez    *
    Email                : geaaqua@uems.br                                                                           *
**********************************************************************************************************************
*                                                                                                                    *
*   This program is free software; you can redistribute it and/or modify it under the terms of the GNU General       *
*   Public License as published by the Free Software Foundation; either version 2 of the License, or (at your option)*
*   any later version.                                                                                               *
*                                                                                                                    *
**********************************************************************************************************************
"""
# Processing algorithm version of the original script. The helper functions
# and the main processing below are the script code without changes; the paths
# and the apply_difference option that were edited at the top of the script
# are now fields of the algorithm window.

import builtins
import os
import shutil
import stat
import tempfile

import processing
from qgis.core import (QgsVectorLayer, QgsProject, QgsVectorFileWriter, QgsFillSymbol,
                       QgsWkbTypes, QgsRectangle, QgsGeometry, QgsPointXY, QgsFeature, QgsField)
from qgis.core import (
    Qgis,
    QgsProcessingAlgorithm,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterFile,
    QgsProcessingParameterFolderDestination,
)
import pandas as pd
from qgis.PyQt.QtCore import QCoreApplication, QUrl, QVariant
from qgis.PyQt.QtGui import QIcon

# Compatibility between QGIS 3.34 and newer versions (enums moved in 3.36)
try:
    FILE_BEHAVIOR = Qgis.ProcessingFileParameterBehavior.File
    FOLDER_BEHAVIOR = Qgis.ProcessingFileParameterBehavior.Folder
except AttributeError:
    FILE_BEHAVIOR = QgsProcessingParameterFile.File
    FOLDER_BEHAVIOR = QgsProcessingParameterFile.Folder

try:
    FLAG_NO_THREADING = Qgis.ProcessingAlgorithmFlag.NoThreading
except AttributeError:
    FLAG_NO_THREADING = QgsProcessingAlgorithm.FlagNoThreading

PLUGIN_DIR = os.path.dirname(__file__)
EXAMPLE_SPREADSHEET = os.path.join(PLUGIN_DIR, "example", "multiscale_parameters.xlsx")


def example_spreadsheet_copy():
    """Copies the example spreadsheet to a temporary folder and returns the
    path of the copy.

    The link in the help panel opens this copy, so the original file inside
    the plugin folder is never opened (an open file blocks the uninstall and
    the update of the plugin). The copy is read-only, so the user saves the
    filled spreadsheet with another name.
    """
    folder = os.path.join(tempfile.gettempdir(), "dynamic_multiscale_buffer_generator")
    copy_path = os.path.join(folder, "multiscale_parameters.xlsx")
    try:
        os.makedirs(folder, exist_ok=True)
        if os.path.exists(copy_path):
            os.chmod(copy_path, stat.S_IREAD | stat.S_IWRITE)
        shutil.copyfile(EXAMPLE_SPREADSHEET, copy_path)
    except OSError:
        # The copy is open in another program: keep the existing copy
        if not os.path.exists(copy_path):
            return EXAMPLE_SPREADSHEET
    finally:
        if os.path.exists(copy_path):
            try:
                os.chmod(copy_path, stat.S_IREAD)
            except OSError:
                pass
    return copy_path

# The messages of the script (print) are sent to the Log tab of the
# algorithm window.
_FEEDBACK = None


def print(*args, **kwargs):
    message = " ".join(str(arg) for arg in args)
    if _FEEDBACK is not None:
        _FEEDBACK.pushInfo(message)
    else:
        builtins.print(message)


# =======================================================================
# Script functions (unchanged)
# =======================================================================

def calculate_shapefile_area(input_path, output_path, field_area='area_calc'):
    """Calculates the area of each polygon in the shapefile"""
    try:
        layer = QgsVectorLayer(input_path, "temp", "ogr")
        if not layer.isValid():
            print(f"ERROR: Unable to load {input_path}")
            return None

        provider = layer.dataProvider()

        # Add area field if it does not exist
        fields = [field.name() for field in layer.fields()]
        if field_area not in fields:
            layer.startEditing()
            layer.addAttribute(QgsField(field_area, QVariant.Double))
            layer.commitChanges()

        layer.updateFields()

        # Calculates the area for each feature
        layer.startEditing()
        for feature in layer.getFeatures():
            geom = feature.geometry()
            if geom.type() == QgsWkbTypes.PolygonGeometry:
                area = geom.area()
                layer.changeAttributeValue(feature.id(), layer.fields().indexFromName(field_area), area)

        layer.commitChanges()

        QgsVectorFileWriter.writeAsVectorFormat(
            layer,
            output_path,
            "UTF-8",
            layer.crs(),
            "ESRI Shapefile"
        )

        print(f"Area calculated and saved in: {output_path}")
        return output_path

    except Exception as e:
        print(f"ERROR when calculating area for {input_path}: {e}")
        return None


def get_total_area(shapefile_path, field_area='area_calc'):
    """Get the total area of a shapefile"""
    try:
        layer = QgsVectorLayer(shapefile_path, "temp", "ogr")
        if not layer.isValid():
            return None

        total_area = 0
        for feature in layer.getFeatures():
            area_feature = feature[field_area]
            if area_feature is not None:
                total_area += area_feature

        return total_area
    except Exception as e:
        print(f"ERROR when obtaining area of {shapefile_path}: {e}")
        return None


def find_field_id_points(layer_points):
    """Finds the ID field in the point layer"""
    fields = [field.name() for field in layer_points.fields()]
    if not fields:
        return None
    return fields[0]


def extract_identifier_from_name(file_name):
    """Extracts an identifier from the file name"""
    base_name = os.path.splitext(file_name)[0]
    if '_' in base_name:
        parts = base_name.split('_')
        return parts[-1]
    return base_name


def obtain_unique_field_values(layer, field_name):
    """Get all unique values from a field"""
    values = []
    for feature in layer.getFeatures():
        value = feature[field_name]
        if value is not None and value not in values:
            values.append(str(value))
    return values


def detect_file_line(line_or_polygon_dir):
    """Automatically detects the line file"""
    if not line_or_polygon_dir or not os.path.exists(line_or_polygon_dir):
        return None

    files_shp = []
    for file in os.listdir(line_or_polygon_dir):
        if file.endswith(".shp"):
            files_shp.append(os.path.join(line_or_polygon_dir, file))

    if not files_shp:
        print(f"No .shp files found in: {line_or_polygon_dir}")
        return None

    chosen_file = files_shp[0]
    print(f"Line file detected: {os.path.basename(chosen_file)}")

    if len(files_shp) > 1:
        print(f"Multiple files found. Using the first: {os.path.basename(chosen_file)}")

    return chosen_file


def verify_line_geometry(layer_path):
    """Checks whether the layer contains line geometries"""
    layer = QgsVectorLayer(layer_path, "temp", "ogr")
    if not layer.isValid():
        return False

    geometry_type = layer.wkbType()
    return QgsWkbTypes.geometryType(geometry_type) == QgsWkbTypes.LineGeometry


def make_polygons_points_match(paths_polygons, layer_points, field_id_points):
    """Match the polygon files to the points"""
    matching = {}

    points_ids = obtain_unique_field_values(layer_points, field_id_points)
    print(f"IDs found at the points: {points_ids}")

    for path_polygon in paths_polygons:
        file_name = os.path.basename(path_polygon)
        polygon_identifier = extract_identifier_from_name(file_name)

        print(f"File: {file_name} -> Identifier extracted: {polygon_identifier}")

        # Exact match
        match_found = False
        for point_id in points_ids:
            if str(point_id).lower() == str(polygon_identifier).lower():
                matching[point_id] = path_polygon
                match_found = True
                print(f"Correspondência exata: {point_id} -> {file_name}")
                break

        # Partial correspondence
        if not match_found:
            for point_id in points_ids:
                if (str(polygon_identifier).lower() in str(point_id).lower() or
                        str(point_id).lower() in str(polygon_identifier).lower()):
                    matching[point_id] = path_polygon
                    match_found = True
                    print(f"Partial match: {point_id} -> {file_name}")
                    break

        if not match_found:
            print(f"No match found for: {file_name}")

    print(f"\nFinal associations found: {len(matching)}")
    for point_id, path in matching.items():
        print(f" {point_id} -> {os.path.basename(path)}")

    return matching


def apply_difference_operation(input_path, mask_path, output_path):
    """Applies the difference operation"""
    try:
        params = {
            'INPUT': input_path,
            'OVERLAY': mask_path,
            'OUTPUT': output_path
        }

        processing.run("native:difference", params)
        print(f"Applied difference: {os.path.basename(output_path)}")
        return output_path

    except Exception as e:
        print(f"ERROR when applying difference in {input_path}: {e}")
        return None



# =======================================================================
# Processing algorithm
# =======================================================================

class DynamicMultiscaleBufferGeneratorAlgorithm(QgsProcessingAlgorithm):

    SPREADSHEET = "SPREADSHEET"
    POINTS = "POINTS"
    POLYGON_DIR = "POLYGON_DIR"
    LINE_OR_POLYGON_DIR = "LINE_OR_POLYGON_DIR"
    APPLY_DIFFERENCE = "APPLY_DIFFERENCE"
    RESULT_DIR = "RESULT_DIR"

    def tr(self, text):
        return QCoreApplication.translate("DynamicMultiscaleBufferGenerator", text)

    def createInstance(self):  # noqa: N802
        return DynamicMultiscaleBufferGeneratorAlgorithm()

    def name(self):
        return "dynamicmultiscalebuffergenerator"

    def displayName(self):  # noqa: N802
        return self.tr("Dynamic multiscale buffer generator")

    def group(self):
        return self.tr("Multiscale buffers")

    def groupId(self):  # noqa: N802
        return "multiscalebuffers"

    def icon(self):
        return QIcon(os.path.join(PLUGIN_DIR, "icon.png"))

    def flags(self):
        # Runs in the main thread, like the script in the Python console,
        # because it adds and removes layers of the project.
        return super().flags() | FLAG_NO_THREADING

    def shortHelpString(self):  # noqa: N802
        link = QUrl.fromLocalFile(example_spreadsheet_copy()).toString()
        return self.tr(
            "Automates batch multi-scale buffer creation in an adaptive way, "
            "based on the contents of an .xlsx spreadsheet. It automatically "
            "detects the polygons (delimitations) and the target file for "
            "the riparian buffer (line or polygon), matches polygons with "
            "points and separates extrapolated areas.<br><br>"
            "<b>Example spreadsheet</b><br>"
            "<a href=\"{0}\">Open the example spreadsheet</a><br>"
            "The example opens as read-only. Fill it in and save it with "
            "another name in your own folder, "
            "then select it in the <i>Parameters spreadsheet</i> field.<br><br>"
            "<b>Spreadsheet format</b><br>"
            "Two columns: \"Step\" and \"Meters\".<br>"
            "Circular buffer: \"1 - Buffer Circular\" in the Step column and "
            "the distance in meters in the Meters column.<br>"
            "Riparian buffer: \"6 - Riparian Buffer\" in the Step column and "
            "the distance in meters in the Meters column.<br>"
            "The processes to run are detected from the spreadsheet contents "
            "(circular only, riparian only or both).<br><br>"
            "<b>Inputs</b><br>"
            "<i>Collected points</i>: .shp of the points collected on site; "
            "the first field is used as the point ID.<br>"
            "<i>Polygons folder</i>: folder with the .shp polygons (watersheds, "
            "contribution areas, areas of influence); the text after the last "
            "\"_\" in the file name must match the point ID.<br>"
            "<i>Line or polygon folder</i>: folder with the .shp used for the "
            "riparian buffer (rivers, drainage, reservoirs); the first .shp "
            "found is used. Needed only for the riparian buffer.<br><br>"
            "<b>Attention</b>: at the end, all layers of the current project "
            "are removed and the results are loaded."
            "<br><br><hr><br>"
            "<b>PORTUGUÊS</b><br><br>"
            "Automatiza a criação de buffers multiescala em lote, de forma "
            "adaptativa, a partir do conteúdo de uma planilha .xlsx. Detecta "
            "automaticamente os polígonos (delimitações) e o arquivo alvo do "
            "buffer ripário (linha ou polígono), associa os polígonos aos "
            "pontos e separa as áreas extrapoladas.<br><br>"
            "<b>Planilha de exemplo</b><br>"
            "<a href=\"{0}\">Abrir a planilha de exemplo</a><br>"
            "O exemplo abre como somente leitura. Preencha e salve com outro "
            "nome numa pasta sua, depois "
            "selecione no campo <i>Parameters spreadsheet</i>.<br><br>"
            "<b>Formato da planilha</b><br>"
            "Duas colunas: \"Step\" e \"Meters\".<br>"
            "Buffer circular: \"1 - Buffer Circular\" na coluna Step e a "
            "distância em metros na coluna Meters.<br>"
            "Buffer ripário: \"6 - Riparian Buffer\" na coluna Step e a "
            "distância em metros na coluna Meters.<br>"
            "Os processos executados são definidos pelo conteúdo da planilha "
            "(só circular, só ripário ou os dois).<br><br>"
            "<b>Entradas</b><br>"
            "<i>Collected points</i>: .shp dos pontos coletados em campo; o "
            "primeiro campo é usado como identificador do ponto.<br>"
            "<i>Polygons folder</i>: pasta com os polígonos .shp (bacias, "
            "áreas de contribuição, áreas de influência); o texto depois do "
            "último \"_\" no nome do arquivo deve corresponder ao "
            "identificador do ponto.<br>"
            "<i>Line or polygon folder</i>: pasta com o .shp usado no buffer "
            "ripário (rios, drenagem, reservatórios); é usado o primeiro .shp "
            "encontrado. Só é necessária para o buffer ripário.<br><br>"
            "<b>Atenção</b>: no final, todas as camadas do projeto atual são "
            "removidas e os resultados são carregados."
        ).format(link)

    def initAlgorithm(self, config=None):  # noqa: N802
        self.addParameter(QgsProcessingParameterFile(
            self.SPREADSHEET, self.tr("Parameters spreadsheet (.xlsx)"),
            behavior=FILE_BEHAVIOR, fileFilter="Excel (*.xlsx *.xls)"))

        self.addParameter(QgsProcessingParameterFile(
            self.POINTS, self.tr("Collected points (.shp)"),
            behavior=FILE_BEHAVIOR, fileFilter="Shapefile (*.shp)"))

        self.addParameter(QgsProcessingParameterFile(
            self.POLYGON_DIR,
            self.tr("Polygons folder (watersheds, contribution areas, etc.)"),
            behavior=FOLDER_BEHAVIOR))

        self.addParameter(QgsProcessingParameterFile(
            self.LINE_OR_POLYGON_DIR,
            self.tr("Line or polygon folder for the riparian buffer (rivers, dams, etc.)"),
            behavior=FOLDER_BEHAVIOR, optional=True))

        self.addParameter(QgsProcessingParameterBoolean(
            self.APPLY_DIFFERENCE, self.tr("Apply difference operations"),
            defaultValue=False))

        self.addParameter(QgsProcessingParameterFolderDestination(
            self.RESULT_DIR, self.tr("Results folder")))

    def processAlgorithm(self, parameters, context, feedback):  # noqa: N802
        global _FEEDBACK
        _FEEDBACK = feedback
        try:
            self.run_script(
                spreadsheet_path=self.parameterAsFile(parameters, self.SPREADSHEET, context),
                result_dir=self.parameterAsString(parameters, self.RESULT_DIR, context),
                points=self.parameterAsFile(parameters, self.POINTS, context),
                line_or_polygon_dir=self.parameterAsFile(
                    parameters, self.LINE_OR_POLYGON_DIR, context),
                polygon_dir=self.parameterAsFile(parameters, self.POLYGON_DIR, context),
                apply_difference=self.parameterAsBoolean(
                    parameters, self.APPLY_DIFFERENCE, context),
            )
        finally:
            _FEEDBACK = None
        return {self.RESULT_DIR: self.parameterAsString(parameters, self.RESULT_DIR, context)}

    def run_script(self, spreadsheet_path, result_dir, points, line_or_polygon_dir,
                   polygon_dir, apply_difference):
        # ==== Script main processing (unchanged) ====
        # Create the directories
        print("Creating directory structure...")
        if not os.path.exists(result_dir):
            os.makedirs(result_dir)

        # Load the parameters from the Excel spreadsheet
        print("Loading parameters from the Excel spreadsheet...")
        try:
            if spreadsheet_path.endswith('.xls'):
                engine = 'xlrd'
            elif spreadsheet_path.endswith('.xlsx'):
                engine = 'openpyxl'
            else:
                engine = None

            df_parameters = pd.read_excel(spreadsheet_path, engine=engine)

            if "Step" not in df_parameters.columns or "Meters" not in df_parameters.columns:
                raise Exception(
                    f"The ‘Step’ and ‘Meters’ columns are required. Columns found: {list(df_parameters.columns)}")

            # Get distances
            filter_circular_buffer = df_parameters["Step"].str.contains("1 - Buffer Circular", na=False)
            circular_distance_buffer = df_parameters.loc[filter_circular_buffer, "Meters"].dropna().tolist()

            filter_riparian_buffer = df_parameters["Step"].str.contains("6 - Riparian Buffer", na=False)
            distances_riparian_buffer = df_parameters.loc[filter_riparian_buffer, "Meters"].dropna().tolist()

            # Determines the operating mode
            tem_buffer_circular = len(circular_distance_buffer) > 0
            tem_riparian_buffer = len(distances_riparian_buffer) > 0

            if not tem_buffer_circular and not tem_riparian_buffer:
                raise Exception("The spreadsheet must contain at least one type of buffer.")

            if tem_buffer_circular and tem_riparian_buffer:
                operation_mode = "FULL"
                print("OPERATING MODE: FULL")
            elif tem_buffer_circular:
                operation_mode = "CIRCULAR"
                print("OPERATING MODE: CIRCULAR BUFFER ONLY")
            else:
                operation_mode = "RIPARIAN"
                print("OPERATING MODE: RIPARIAN BUFFER ONLY")

            if tem_buffer_circular:
                print(f"Meterss de buffer circular: {circular_distance_buffer}")
            if tem_riparian_buffer:
                print(f"Riparian buffer distances: {distances_riparian_buffer}")

            print(f"DIFFERENCE OPERATIONS: {'ENABLED' if apply_difference else 'DISABLED'}")

        except Exception as e:
            print(f"ERROR: Unable to load Excel spreadsheet parameters. Details: {e}")
            raise Exception("Error loading spreadsheet. Processing interrupted.")

        # Creates directory structure based on operating mode
        if operation_mode in ["CIRCULAR", "FULL"]:
            buffer_circular_dir = os.path.join(result_dir, "1BUFFER_CIRCULAR")
            if not os.path.exists(buffer_circular_dir):
                os.makedirs(buffer_circular_dir)

            split_layers_dir = os.path.join(result_dir, "2SPLIT_LAYERS")
            if not os.path.exists(split_layers_dir):
                os.makedirs(split_layers_dir)

            convert_format_dir = os.path.join(result_dir, "3CONVERT_FORMAT")
            if not os.path.exists(convert_format_dir):
                os.makedirs(convert_format_dir)

            buffer_circ_area_dir = os.path.join(result_dir, "4LCA_Temporary")
            if not os.path.exists(buffer_circ_area_dir):
                os.makedirs(buffer_circ_area_dir)

            final_polygons_area_dir = os.path.join(result_dir, "ECA_WITH_AREA")
            if not os.path.exists(final_polygons_area_dir):
                os.makedirs(final_polygons_area_dir)

            extrapolated_areas_dir = os.path.join(result_dir, "LCA_EXTRAPOLATED_AREAS")
            if not os.path.exists(extrapolated_areas_dir):
                os.makedirs(extrapolated_areas_dir)

            lca_dir = os.path.join(result_dir, "5LCA_Definitive")
            if not os.path.exists(lca_dir):
                os.makedirs(lca_dir)

        if operation_mode in ["RIPARIAN", "FULL"]:
            clipped_line_dir = os.path.join(result_dir, "6TARGET_LAYER_FOR_RIPARIAN_BUFFER")
            if not os.path.exists(clipped_line_dir):
                os.makedirs(clipped_line_dir)

            riparian_buffer_dir = os.path.join(result_dir, "7RB_Temporary")
            if not os.path.exists(riparian_buffer_dir):
                os.makedirs(riparian_buffer_dir)

            amortec_recort_dir = os.path.join(result_dir, "8RB_Definitive")
            if not os.path.exists(amortec_recort_dir):
                os.makedirs(amortec_recort_dir)

            if apply_difference:
                amortec_recort_dif_dir = os.path.join(result_dir, "8RB_Definitive_Dif")
                if not os.path.exists(amortec_recort_dif_dir):
                    os.makedirs(amortec_recort_dif_dir)

        if operation_mode == "FULL":
            riparian_lca_dir = os.path.join(result_dir, "9RBLCA")
            if not os.path.exists(riparian_lca_dir):
                os.makedirs(riparian_lca_dir)

            if apply_difference:
                amortec_lca_dif_dir = os.path.join(result_dir, "9RBLCA_ Dif")
                if not os.path.exists(amortec_lca_dif_dir):
                    os.makedirs(amortec_lca_dif_dir)

        # Checks the input layers
        print("Checking input layers...")
        points_layer = QgsVectorLayer(points, "Points_Collected", "ogr")
        if not points_layer.isValid():
            raise Exception(f"ERROR: Could not load the points in {points}")

        file_line_detected = None
        if operation_mode in ["RIPARIAN", "FULL"]:
            print("Detecting line file...")
            file_line_detected = detect_file_line(line_or_polygon_dir)

            if not file_line_detected:
                raise Exception("ERROR: Could not find line file for riparian buffer.")

            layer_line = QgsVectorLayer(file_line_detected, "temp_line", "ogr")
            if not layer_line.isValid():
                raise Exception(f"ERROR: Invalid line file: {file_line_detected}")

            if not verify_line_geometry(file_line_detected):
                print(f"WARNING: The file {os.path.basename(file_line_detected)} might not contain line geometries.")

            print(f"✓ Validated line file: {os.path.basename(file_line_detected)}")

        # AUTOMATIC POLYGON DETECTION AND MATCHING WITH POINTS
        print("\n" + "=" * 50)
        print("STARTING AUTOMATIC DETECTION OF POLYGONS AND POINTS")
        print("=" * 50)

        print("Searching for polygon files...")
        paths_polygons = []
        for file in os.listdir(polygon_dir):
            if file.endswith(".shp"):
                paths_polygons.append(os.path.join(polygon_dir, file))

        if not paths_polygons:
            raise Exception(f"ERROR: No .shp files were found in {polygon_dir}")

        print(f"Found {len(paths_polygons)} .shp files in the polygon directory.")

        field_id = find_field_id_points(points_layer)
        if not field_id:
            raise Exception("ERROR: Could not find a suitable ID field in the point layer.")

        print(f"ID field identified in the point layer: '{field_id}'")

        polygons_points_match = make_polygons_points_match(paths_polygons, points_layer, field_id)

        if not polygons_points_match:
            raise Exception("ERROR: Could not match polygons and points.")

        point_names = list(polygons_points_match.keys())
        print(f"\nPoints to be processed: {point_names}")

        # Initialization of control variables
        circular_buffers = {}
        split_buffers = {}
        clipped_buffers_temp = {}
        polygon_areas = {}
        lca_buffers = {}
        extrapolated_areas = {}
        clipped_line = {}
        riparian_buffers = {}
        cropped_riparian = {}
        cropped_riparian_dif = {}
        riparian_lca_dif = {}

        # Calculation of polygon area
        if operation_mode in ["CIRCULAR", "FULL"]:
            print("\nCalculating polygon areas...")

            for point_id in point_names:
                poligono_path = polygons_points_match.get(point_id)

                if not poligono_path:
                    print(f"ERROR: Polygon to point {point_id} not found!")
                    continue

                output_area = os.path.join(final_polygons_area_dir, f"ECA_{point_id}.shp")
                area_calculada = calculate_shapefile_area(poligono_path, output_area)

                if area_calculada:
                    polygon_areas[point_id] = {
                        'path': output_area,
                        'total_area': get_total_area(output_area)
                    }

        # STEPS 1-3: Buffer Circular
        if operation_mode in ["CIRCULAR", "FULL"]:
            # STEP 1: Generate buffer circular
            print("\n1. Generating circular buffers...")

            for distance in circular_distance_buffer:
                print(f"Creating a circular buffer of {distance}m...")
                output_buffer = os.path.join(buffer_circular_dir, f"circular_{int(distance)}m.shp")

                params = {
                    'INPUT': points,
                    'DISTANCE': distance,
                    'SEGMENTS': 5,
                    'END_CAP_STYLE': 0,
                    'JOIN_STYLE': 0,
                    'MITER_LIMIT': 2,
                    'DISSOLVE': False,
                    'OUTPUT': output_buffer
                }

                processing.run("native:buffer", params)
                circular_buffers[distance] = output_buffer

            # STEP 2 e 3: Split layers and convert format
            print("\n2 e 3. Splitting layers and converting formats...")

            for distance, buffer_path in circular_buffers.items():
                print(f"Processing buffer from {distance}m...")

                buffer_dist_dir = os.path.join(split_layers_dir, f"circular{int(distance)}m_buffer")
                if not os.path.exists(buffer_dist_dir):
                    os.makedirs(buffer_dist_dir)

                buffer_convert_dir = os.path.join(convert_format_dir, f"{int(distance)}m_circ")
                if not os.path.exists(buffer_convert_dir):
                    os.makedirs(buffer_convert_dir)

                try:
                    params_dividir = {
                        'INPUT': buffer_path,
                        'FIELD': field_id,
                        'PREFIX': '',
                        'OUTPUT': buffer_dist_dir
                    }

                    processing.run("native:splitvectorlayer", params_dividir)
                    print(f"Layer successfully split using field '{field_id}'")

                    for point_id in point_names:
                        if point_id not in split_buffers:
                            split_buffers[point_id] = {}

                        gpkg_found = False
                        for file in os.listdir(buffer_dist_dir):
                            if file.endswith(".gpkg") and str(point_id) in file:
                                gpkg_path = os.path.join(buffer_dist_dir, file)
                                converted_output = os.path.join(buffer_convert_dir, f"{int(distance)}m_circ{point_id}.shp")

                                print(f"Converting {file} for shapefile...")

                                layer = QgsVectorLayer(gpkg_path, "temp", "ogr")
                                if not layer.isValid():
                                    print(f"WARNING: Invalid GPKG layer: {gpkg_path}")
                                    continue

                                QgsVectorFileWriter.writeAsVectorFormat(
                                    layer,
                                    converted_output,
                                    "UTF-8",
                                    layer.crs(),
                                    "ESRI Shapefile"
                                )

                                split_buffers[point_id][distance] = converted_output
                                gpkg_found = True
                                break

                        if not gpkg_found:
                            print(f"WARNING: Using an alternative approach for the point {point_id}")

                            individual_buffer = os.path.join(buffer_convert_dir, f"{int(distance)}m_circ{point_id}.shp")

                            try:
                                params_buffer = {
                                    'INPUT': points,
                                    'DISTANCE': distance,
                                    'SEGMENTS': 5,
                                    'END_CAP_STYLE': 0,
                                    'JOIN_STYLE': 0,
                                    'MITER_LIMIT': 2,
                                    'DISSOLVE': False,
                                    'OUTPUT': individual_buffer
                                }

                                processing.run("native:buffer", params_buffer)
                                split_buffers[point_id][distance] = individual_buffer

                            except Exception as e_buffer:
                                print(f"ERROR creating individual buffer for {point_id}: {e_buffer}")

                except Exception as e:
                    print(f"ERROR when splitting/converting buffer from {distance}m: {e}")

            # STEP 4: Crop circular buffer by polygon
            print("\n4. Clipping circular buffer by polygon...")

            for point_id in point_names:
                if point_id not in clipped_buffers_temp:
                    clipped_buffers_temp[point_id] = {}

                poligono_path = polygons_points_match.get(point_id)

                if not poligono_path:
                    print(f"ERROR: Polygon to point {point_id} not found!")
                    continue

                for distance in circular_distance_buffer:
                    if point_id not in split_buffers or distance not in split_buffers[point_id]:
                        print(f"ERRO: Buffer circular de {distance}m to point {point_id} not found!")
                        continue

                    buffer_path = split_buffers[point_id][distance]
                    temp_output = os.path.join(buffer_circ_area_dir, f"temp_recorte_{int(distance)}m_circ{point_id}.shp")

                    params_recortar = {
                        'INPUT': buffer_path,
                        'OVERLAY': poligono_path,
                        'OUTPUT': temp_output
                    }

                    processing.run("native:clip", params_recortar)
                    clipped_buffers_temp[point_id][distance] = temp_output

            # STEP 5: Calculate area and classify
            print("\n5. Calculating areas and classifying buffers...")

            for point_id in point_names:
                if point_id not in lca_buffers:
                    lca_buffers[point_id] = {}
                if point_id not in extrapolated_areas:
                    extrapolated_areas[point_id] = {}

                for distance in circular_distance_buffer:
                    if point_id not in clipped_buffers_temp or distance not in clipped_buffers_temp[point_id]:
                        continue

                    buffer_temp_path = clipped_buffers_temp[point_id][distance]

                    buffer_area_path = os.path.join(buffer_circ_area_dir, f"area_buffer_{int(distance)}m_{point_id}.shp")
                    area_calculada = calculate_shapefile_area(buffer_temp_path, buffer_area_path)

                    if not area_calculada:
                        continue

                    area_buffer = get_total_area(buffer_area_path)

                    if point_id not in polygon_areas:
                        print(f"ERRO: Área do polígono to point {point_id} not found!")
                        continue

                    area_poligono = polygon_areas[point_id]['total_area']

                    if area_buffer is not None and area_poligono is not None:
                        if abs(area_buffer - area_poligono) < 0.01:
                            #Extrapolated area
                            extrapolated_output = os.path.join(extrapolated_areas_dir, f"LCA_{int(distance)}m_{point_id}.shp")

                            layer = QgsVectorLayer(buffer_area_path, "temp", "ogr")
                            QgsVectorFileWriter.writeAsVectorFormat(
                                layer,
                                extrapolated_output,
                                "UTF-8",
                                layer.crs(),
                                "ESRI Shapefile"
                            )

                            extrapolated_areas[point_id][distance] = extrapolated_output
                            print(f"EXTRAPOLATED AREA: {point_id} - {distance}m")

                        elif area_buffer < area_poligono:
                            # Valid area (LCA)
                            lca_output = os.path.join(lca_dir, f"LCA_{int(distance)}m_{point_id}.shp")

                            layer = QgsVectorLayer(buffer_area_path, "temp", "ogr")
                            QgsVectorFileWriter.writeAsVectorFormat(
                                layer,
                                lca_output,
                                "UTF-8",
                                layer.crs(),
                                "ESRI Shapefile"
                            )

                            lca_buffers[point_id][distance] = lca_output
                            print(f"VALID AREA (LCA): {point_id} - {distance}m")
                        else:
                            print(f"WARNING: Buffer area larger than polygon area for {point_id} - {distance}m")

        # STEPS 6-8: Riparian Buffer
        if operation_mode in ["RIPARIAN", "FULL"]:
            # STEP 6: Clip line file by polygon
            print(f"\n6. Clipping {os.path.basename(file_line_detected)} by polygon...")

            for point_id in point_names:
                poligono_path = polygons_points_match.get(point_id)

                if not poligono_path:
                    print(f"ERROR: Polygon to point {point_id} not found!")
                    continue

                linha_output = os.path.join(clipped_line_dir, f"layer_point{point_id}.shp")

                params_recortar = {
                    'INPUT': file_line_detected,
                    'OVERLAY': poligono_path,
                    'OUTPUT': linha_output
                }

                processing.run("native:clip", params_recortar)
                clipped_line[point_id] = linha_output

            # STEP 7: Generate riparian buffer
            print("\n7. Generating riparian buffer...")

            for point_id, clipped_line_path in clipped_line.items():
                if point_id not in riparian_buffers:
                    riparian_buffers[point_id] = {}

                for distance in distances_riparian_buffer:
                    riparian_output = os.path.join(riparian_buffer_dir, f"temp_RB_{int(distance)}_{point_id}.shp")

                    params_buffer = {
                        'INPUT': clipped_line_path,
                        'DISTANCE': distance,
                        'SEGMENTS': 5,
                        'END_CAP_STYLE': 0,
                        'JOIN_STYLE': 0,
                        'MITER_LIMIT': 2,
                        'DISSOLVE': True,
                        'OUTPUT': riparian_output
                    }

                    processing.run("native:buffer", params_buffer)
                    riparian_buffers[point_id][distance] = riparian_output

            # STEP 8: Crop riparian buffer by polygon
            print("\n8. Clipping riparian buffer by polygon...")

            for point_id in point_names:
                if point_id not in cropped_riparian:
                    cropped_riparian[point_id] = {}

                poligono_path = polygons_points_match.get(point_id)

                if not poligono_path:
                    print(f"ERROR: Polygon to point {point_id} not found!")
                    continue

                for riparian_distance in distances_riparian_buffer:
                    if point_id not in riparian_buffers or riparian_distance not in riparian_buffers[point_id]:
                        print(f"ERROR: Riparian buffer from {riparian_distance}m to point {point_id} not found!")
                        continue

                    riparian_path = riparian_buffers[point_id][riparian_distance]
                    cropped_output = os.path.join(amortec_recort_dir, f"RB_{int(riparian_distance)}_{point_id}.shp")

                    params_recortar = {
                        'INPUT': riparian_path,
                        'OVERLAY': poligono_path,
                        'OUTPUT': cropped_output
                    }

                    processing.run("native:clip", params_recortar)
                    cropped_riparian[point_id][riparian_distance] = cropped_output

            # STEP 8.1: Apply difference to clipped riparian
            if apply_difference:
                print("\n8.1. Applying difference on clipped riparian buffer...")

                for point_id in point_names:
                    if point_id not in cropped_riparian_dif:
                        cropped_riparian_dif[point_id] = {}

                    if point_id not in clipped_line:
                        print(f"AVISO: layer alvo to point {point_id} not found!")
                        continue

                    target_layer_path = clipped_line[point_id]

                    for riparian_distance in distances_riparian_buffer:
                        if point_id not in cropped_riparian or riparian_distance not in cropped_riparian[point_id]:
                            continue

                        riparian_path = cropped_riparian[point_id][riparian_distance]
                        dif_output = os.path.join(amortec_recort_dif_dir, f"RB_{int(riparian_distance)}_{point_id}_dif.shp")

                        resultado_dif = apply_difference_operation(riparian_path, target_layer_path, dif_output)
                        if resultado_dif:
                            cropped_riparian_dif[point_id][riparian_distance] = resultado_dif

        # STEP 9: Cut riparian buffer by LCA
        if operation_mode == "FULL":
            print("\n9. Clipping riparian buffer by LCA..")

            for point_id in point_names:
                for circular_distance in circular_distance_buffer:
                    if point_id not in lca_buffers or circular_distance not in lca_buffers[point_id]:
                        print(f"WARNING: Valid LCA of {circular_distance}m to point {point_id} not found!")
                        continue

                    lca_path = lca_buffers[point_id][circular_distance]

                    for riparian_distance in distances_riparian_buffer:
                        if point_id not in cropped_riparian or riparian_distance not in cropped_riparian[point_id]:
                            print(f"ERROR: Cropped riparian from {riparian_distance}m to point {point_id} not found!")
                            continue

                        riparian_path = cropped_riparian[point_id][riparian_distance]
                        final_output = os.path.join(riparian_lca_dir,
                                                    f"LCA_{int(circular_distance)}_RB_{int(riparian_distance)}_{point_id}.shp")

                        params_recortar = {
                            'INPUT': riparian_path,
                            'OVERLAY': lca_path,
                            'OUTPUT': final_output
                        }

                        processing.run("native:clip", params_recortar)

            # STEP 9.1: Apply difference in riparian buffer regarding LCA range
            if apply_difference:
                print("\n9.1. Applying difference in LCA riparian buffer...")

                for point_id in point_names:
                    if point_id not in riparian_lca_dif:
                        riparian_lca_dif[point_id] = {}

                    if point_id not in clipped_line:
                        print(f"WARNING: Target layer for point {point_id} not found!")
                        continue

                    target_layer_path = clipped_line[point_id]

                    for circular_distance in circular_distance_buffer:
                        for riparian_distance in distances_riparian_buffer:
                            file_amort_lca = os.path.join(riparian_lca_dir,
                                                             f"LCA_{int(circular_distance)}_RB_{int(riparian_distance)}_{point_id}.shp")

                            if not os.path.exists(file_amort_lca):
                                continue

                            dif_output = os.path.join(amortec_lca_dif_dir,
                                                      f"LCA_{int(circular_distance)}_RB_{int(riparian_distance)}_{point_id}_dif.shp")

                            resultado_dif = apply_difference_operation(file_amort_lca, target_layer_path, dif_output)
                            if resultado_dif:
                                if circular_distance not in riparian_lca_dif[point_id]:
                                    riparian_lca_dif[point_id][circular_distance] = {}
                                riparian_lca_dif[point_id][circular_distance][riparian_distance] = resultado_dif

        # Load layers in QGIS
        print("\nLoading layers in QGIS...")

        QgsProject.instance().removeAllMapLayers()

        #1. Load Points_Collected
        points_layer = QgsVectorLayer(points, "Points_Collected", "ogr")
        QgsProject.instance().addMapLayer(points_layer)

        #2. Load polygons
        print("Loading polygons...")
        for point_id, path_polygon in polygons_points_match.items():
            layer_name = f"Poligono_{point_id}"
            layer = QgsVectorLayer(path_polygon, layer_name, "ogr")
            if layer.isValid():
                simbolo = QgsFillSymbol.createSimple({
                    'color': '255,255,255,0',
                    'outline_color': '0,0,0,255',
                    'outline_width': '0.5'
                })
                layer.renderer().setSymbol(simbolo)
                QgsProject.instance().addMapLayer(layer)

        #3. Load polygon areas
        if operation_mode in ["CIRCULAR", "FULL"]:
            print("Loading polygon areas...")
            if os.path.exists(final_polygons_area_dir):
                for file in os.listdir(final_polygons_area_dir):
                    if file.endswith(".shp"):
                        path = os.path.join(final_polygons_area_dir, file)
                        layer = QgsVectorLayer(path, f"Area_{file}", "ogr")
                        if layer.isValid():
                            simbolo = QgsFillSymbol.createSimple({
                                'color': '255,255,0,100',
                                'outline_color': '255,255,0,255',
                                'outline_width': '0.7'
                            })
                            layer.renderer().setSymbol(simbolo)
                            QgsProject.instance().addMapLayer(layer)

        #4. Load target layer
        if operation_mode in ["RIPARIAN", "FULL"]:
            print("Loading target layers for riparian...")
            if os.path.exists(clipped_line_dir):
                for file in os.listdir(clipped_line_dir):
                    if file.endswith(".shp"):
                        path = os.path.join(clipped_line_dir, file)
                        layer = QgsVectorLayer(path, f"Target_{file}", "ogr")
                        if layer.isValid():
                            QgsProject.instance().addMapLayer(layer)

        #5. Load specific layers based on mode
        if operation_mode in ["CIRCULAR", "FULL"]:
            # Carregar LCA válidas
            print("Loading valid LCA layers...")
            if os.path.exists(lca_dir):
                for file in os.listdir(lca_dir):
                    if file.endswith(".shp"):
                        path = os.path.join(lca_dir, file)
                        layer = QgsVectorLayer(path, f"LCA_Valid_{file}", "ogr")
                        if layer.isValid():
                            simbolo = QgsFillSymbol.createSimple({
                                'color': '0,255,0,100',
                                'outline_color': '0,128,0,255',
                                'outline_width': '0.7'
                            })
                            layer.renderer().setSymbol(simbolo)
                            QgsProject.instance().addMapLayer(layer)

            # Load extrapolated areas
            print("Loading extrapolated areas...")
            if os.path.exists(extrapolated_areas_dir):
                for file in os.listdir(extrapolated_areas_dir):
                    if file.endswith(".shp"):
                        path = os.path.join(extrapolated_areas_dir, file)
                        layer = QgsVectorLayer(path, f"Extrapolated_{file}", "ogr")
                        if layer.isValid():
                            simbolo = QgsFillSymbol.createSimple({
                                'color': '255,0,0,100',
                                'outline_color': '128,0,0,255',
                                'outline_width': '0.7'
                            })
                            layer.renderer().setSymbol(simbolo)
                            QgsProject.instance().addMapLayer(layer)

        if operation_mode == "FULL":
            # Load riparian LCA
            print("Loading LCA riparian layers....")
            if os.path.exists(riparian_lca_dir):
                for file in os.listdir(riparian_lca_dir):
                    if file.endswith(".shp"):
                        path = os.path.join(riparian_lca_dir, file)
                        layer = QgsVectorLayer(path, f"RB_LCA_{file}", "ogr")
                        if layer.isValid():
                            simbolo = QgsFillSymbol.createSimple({
                                'color': '0,0,255,100',
                                'outline_color': '0,0,128,255',
                                'outline_width': '0.7'
                            })
                            layer.renderer().setSymbol(simbolo)
                            QgsProject.instance().addMapLayer(layer)

            # Load LCA difference
            if apply_difference and os.path.exists(amortec_lca_dif_dir):
                print("Loading LCA riparian layers with difference...")
                for file in os.listdir(amortec_lca_dif_dir):
                    if file.endswith(".shp"):
                        path = os.path.join(amortec_lca_dif_dir, file)
                        layer = QgsVectorLayer(path, f"RB_LCA_Dif_{file}", "ogr")
                        if layer.isValid():
                            simbolo = QgsFillSymbol.createSimple({
                                'color': '128,0,128,100',
                                'outline_color': '64,0,64,255',
                                'outline_width': '0.7'
                            })
                            layer.renderer().setSymbol(simbolo)
                            QgsProject.instance().addMapLayer(layer)

        elif operation_mode == "RIPARIAN":
            # Carregar riparian recortado
            print("Loading cropped riparian layers...")
            if os.path.exists(amortec_recort_dir):
                for file in os.listdir(amortec_recort_dir):
                    if file.endswith(".shp"):
                        path = os.path.join(amortec_recort_dir, file)
                        layer = QgsVectorLayer(path, f"RB_{file}", "ogr")
                        if layer.isValid():
                            simbolo = QgsFillSymbol.createSimple({
                                'color': '0,0,255,100',
                                'outline_color': '0,0,128,255',
                                'outline_width': '0.7'
                            })
                            layer.renderer().setSymbol(simbolo)
                            QgsProject.instance().addMapLayer(layer)

            # Load riparian difference
            if apply_difference and os.path.exists(amortec_recort_dif_dir):
                print("Loading cropped riparian layers with difference...")
                for file in os.listdir(amortec_recort_dif_dir):
                    if file.endswith(".shp"):
                        path = os.path.join(amortec_recort_dif_dir, file)
                        layer = QgsVectorLayer(path, f"RB_Dif_{file}", "ogr")
                        if layer.isValid():
                            simbolo = QgsFillSymbol.createSimple({
                                'color': '0,255,255,100',
                                'outline_color': '0,128,128,255',
                                'outline_width': '0.7'
                            })
                            layer.renderer().setSymbol(simbolo)
                            QgsProject.instance().addMapLayer(layer)

        # Centralize view
        print("Centralizing visualization...")
        try:
            from qgis.utils import iface

            if iface:
                iface.mapCanvas().zoomToFullExtent()
        except:
            print("WARNING: Automatic centering was not possible.")

        # Final report
        print("\n" + "=" * 70)
        print("PROCESSING SUCCESSFULLY COMPLETED!")
        print("=" * 70)
        print(f"MODO: {operation_mode}")
        print(f"DIFFERENCE: {'APPLIED' if apply_difference else 'NOT APPLIED'}")
        print(f"Results {result_dir}")

        print(f"\nMATCHINGS:")
        for point_id, path_polygon in polygons_points_match.items():
            print(f"  {point_id} -> {os.path.basename(path_polygon)}")

        # Statistics
        if operation_mode in ["CIRCULAR", "FULL"]:
            total_lca = sum(len(buffers) for buffers in lca_buffers.values())
            total_extrapolated = sum(len(buffers) for buffers in extrapolated_areas.values())
            print(f"\nSTATISTICS:")
            print(f"- Valid LCAs: {total_lca}")
            print(f"- Areas extrapolated: {total_extrapolated}")
            print(f"- Points processed: {len(point_names)}")

        if operation_mode in ["RIPARIAN", "FULL"]:
            total_riparian = sum(len(buffers) for buffers in cropped_riparian.values())
            print(f"- Riparians: {total_riparian}")

            if apply_difference:
                total_RB_dif = sum(len(buffers) for buffers in cropped_riparian_dif.values())
                print(f"- Riparian with a difference: {total_RB_dif}")

        if file_line_detected:
            print(f"\nLINE ARCHIVE: {os.path.basename(file_line_detected)}")

        print("\nThe layers were loaded in QGIS with customized styles.")
        print("=" * 70)
