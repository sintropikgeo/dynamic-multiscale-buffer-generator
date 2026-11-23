# BufScale: Dynamic Multiscale Buffer Generator (QGIS plugin)

BufScale (Dynamic multiscale buffer generator) is the plugin version of the script "Dynamic multiscale buffer generator". The processing is the same as the script: the paths and the `apply_difference` option that were edited at the top of the code are now fields of the algorithm window.

Automates batch multi-scale buffer creation in an adaptive way, based on the contents of an .xlsx spreadsheet. It automatically detects the names of delimitations (polygons) and the target file for the riparian buffer (line or polygon), matches polygons with points, identifies the point ID field and separates extrapolated areas.

## Requirements

- QGIS 3.34.5 or higher
- Python packages `pandas` and `openpyxl`

## Usage

`Processing Toolbox > BufScale > Multiscale buffers > BufScale: Dynamic multiscale buffer generator`

| Field | Script variable |
|---|---|
| Parameters spreadsheet (.xlsx) | `spreadsheet_path` |
| Collected points (.shp) | `points` |
| Polygons folder | `polygon_dir` |
| Line or polygon folder for the riparian buffer | `line_or_polygon_dir` |
| Apply difference operations | `apply_difference` |
| Results folder | `result_dir` |

## Spreadsheet format

An example spreadsheet (`example/multiscale_parameters.xlsx`) can be opened from the link in the help panel of the algorithm window. Fill it in and save it with another name in your own folder.

The spreadsheet must contain two columns: `Step` and `Meters`.

- Circular buffer: `1 - Buffer Circular` in the Step column and the distance in meters in the Meters column.
- Riparian buffer: `6 - Riparian Buffer` in the Step column and the distance in meters in the Meters column.

The processes to run are detected from the spreadsheet contents.

## Automatic detection

- Polygons: all .shp files in the polygons folder; the text after the last `_` in the file name is matched with the point ID
- Point ID: first field of the points shapefile
- Riparian target: first .shp file in the line or polygon folder

## Outputs (results folder)

- `1BUFFER_CIRCULAR`, `2SPLIT_LAYERS`, `3CONVERT_FORMAT`, `4LCA_Temporary`: intermediate circular buffer steps
- `ECA_WITH_AREA`: polygons with calculated area
- `5LCA_Definitive`: valid circular buffers clipped by the polygon (LCA)
- `LCA_EXTRAPOLATED_AREAS`: buffers that extrapolate the polygon
- `6TARGET_LAYER_FOR_RIPARIAN_BUFFER`, `7RB_Temporary`: intermediate riparian buffer steps
- `8RB_Definitive`: riparian buffers clipped by the polygon
- `9RBLCA`: riparian buffers clipped by the LCA
- `8RB_Definitive_Dif`, `9RBLCA_ Dif`: results with difference (when enabled)

At the end, all layers of the current project are removed and the results are loaded with customized styles.

## Authors

- Henrique Ledo Lopes Pinho
- Jéssica Bassani de Oliveira
- Yzel Rondon Suarez

Contact: geaaqua@uems.br

## Institutional support

State University of Mato Grosso do Sul (UEMS), Dourados, Brazil: CERNA, PGRN, Bachelor's Degree in Information Systems, GEAAQUA and NIT. Funding: CAPES, CNPq and Fundect.

## License

GNU General Public License v2 or later. See `LICENSE`.
