import math
import posixpath
import re
import zipfile
import xml.etree.ElementTree as ET


NAMESPACE = {
    "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "relationships": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}

TRACI_COLUMNS = (
    ("cas_number", "CAS #", "text"),
    ("formatted_cas_number", "Formatted CAS #", "text"),
    ("substance_name", "Substance Name", "text"),
    ("acidification_air", "Acidification Air (kg SO2 eq / kg substance)", "number"),
    ("ecotox_air_urban_freshwater", "Ecotox. CF [CTUeco/kg], Em.airU, freshwater", "number"),
    ("ecotox_air_continental_freshwater", "Ecotox. CF [CTUeco/kg], Em.airC, freshwater", "number"),
    ("ecotox_freshwater_continental_freshwater", "Ecotox. CF [CTUeco/kg], Em.fr.waterC, freshwater", "number"),
    ("ecotox_seawater_continental_freshwater", "Ecotox. CF [CTUeco/kg], Em.sea waterC, freshwater", "number"),
    ("ecotox_natural_soil_continental_freshwater", "Ecotox. CF [CTUeco/kg], Em.nat.soilC, freshwater", "number"),
    ("ecotox_agricultural_soil_continental_freshwater", "Ecotox. CF [CTUeco/kg], Em.agr.soilC, freshwater", "number"),
    ("ecotox_flag", "CF Flag Ecotox", "text"),
    ("global_climate_air", "Global Climate Air (kg CO2 eq / kg substance)", "number"),
    ("human_health_urban_air_cancer", "Human health CF  [CTUcancer/kg], Emission to urban air, cancer", "number"),
    ("human_health_urban_air_non_cancer", "Human health CF  [CTUnoncancer/kg], Emission to urban air, non-canc.", "number"),
    ("human_health_rural_air_cancer", "Human health CF  [CTUcancer/kg], Emission to cont. rural air, cancer", "number"),
    ("human_health_rural_air_non_cancer", "Human health CF  [CTUnoncancer/kg], Emission to cont. rural air, non-canc.", "number"),
    ("human_health_freshwater_cancer", "Human health CF  [CTUcancer/kg], Emission to cont. freshwater, cancer", "number"),
    ("human_health_freshwater_non_cancer", "Human health CF  [CTUnoncancer/kg], Emission to cont. freshwater, non-canc.", "number"),
    ("human_health_seawater_cancer", "Human health CF  [CTUcancer/kg], Emission to cont. sea water, cancer", "number"),
    ("human_health_seawater_non_cancer", "Human health CF  [CTUnoncancer/kg], Emission to cont. sea water, non-canc.", "number"),
    ("human_health_natural_soil_cancer", "Human health CF  [CTUcancer/kg], Emission to cont. natural soil, cancer", "number"),
    ("human_health_natural_soil_non_cancer", "Human health CF  [CTUnoncancer/kg], Emission to cont. natural soil, non-canc.", "number"),
    ("human_health_agricultural_soil_cancer", "Human health CF  [CTUcancer/kg], Emission to cont. agric. Soil, cancer", "number"),
    ("human_health_agricultural_soil_non_cancer", "Human health CF  [CTUnoncancer/kg], Emission to cont. agric. Soil, non-canc.", "number"),
    ("human_health_cancer_flag", "CF Flag HH carcinogenic", "text"),
    ("human_health_non_cancer_flag", "CF Flag HH non-carcinogenic", "text"),
    ("human_health_particulate_air", "HH Particulate Air (PM2.5 eq / kg substance)", "number"),
    ("ozone_depletion_air", "Ozone Depletion Air (kg CFC-11 eq / kg substance)", "number"),
    ("photochemical_oxidation_air", "Photochemical Oxidation Formation Air (kg O3 eq / kg substance)", "number"),
)


def _column_index(cell_reference):
    letters = re.match(r"[A-Z]+", cell_reference)
    if not letters:
        raise ValueError(f"Invalid spreadsheet cell reference: {cell_reference}")

    index = 0
    for letter in letters.group():
        index = index * 26 + ord(letter) - ord("A") + 1
    return index - 1


def _shared_strings(archive):
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []

    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    return [
        "".join(text.text or "" for text in item.findall(".//main:t", NAMESPACE))
        for item in root.findall("main:si", NAMESPACE)
    ]


def _cell_value(cell, shared_strings):
    cell_type = cell.attrib.get("t")

    if cell_type == "inlineStr":
        return "".join(text.text or "" for text in cell.findall(".//main:t", NAMESPACE))

    value = cell.find("main:v", NAMESPACE)
    if value is None or value.text is None:
        return ""

    if cell_type == "s":
        try:
            return shared_strings[int(value.text)]
        except (ValueError, IndexError) as exc:
            raise ValueError("Workbook contains an invalid shared-string reference.") from exc

    return value.text


def _read_rows(worksheet, shared_strings):
    rows = []
    sheet_data = worksheet.find("main:sheetData", NAMESPACE)
    if sheet_data is None:
        return rows

    for row in sheet_data.findall("main:row", NAMESPACE):
        values = []
        for cell in row.findall("main:c", NAMESPACE):
            column = _column_index(cell.attrib.get("r", ""))
            if column >= len(values):
                values.extend([""] * (column + 1 - len(values)))
            values[column] = _cell_value(cell, shared_strings)
        rows.append((int(row.attrib.get("r", "0")), values))

    return rows


def _substances_sheet_path(archive):
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    relationship_targets = {
        relationship.attrib["Id"]: relationship.attrib["Target"]
        for relationship in relationships
    }

    for sheet in workbook.findall("main:sheets/main:sheet", NAMESPACE):
        if sheet.attrib.get("name") != "Substances":
            continue

        relationship_id = sheet.attrib.get(
            f"{{{NAMESPACE['relationships']}}}id"
        )
        target = relationship_targets.get(relationship_id)
        if not target:
            raise ValueError("Workbook has no file reference for the Substances sheet.")

        if target.startswith("/"):
            return target.lstrip("/")
        return posixpath.normpath(posixpath.join("xl", target))

    raise ValueError("Workbook does not contain a Substances sheet.")


def _clean_value(value, value_type, row_number, column_name):
    value = str(value).strip()
    if not value or value.lower() in {"n/a", "na"}:
        return None

    if value_type == "text":
        return value

    try:
        number = float(value)
    except ValueError as exc:
        raise ValueError(
            f"Invalid number in row {row_number}, column {column_name}: {value}"
        ) from exc

    if not math.isfinite(number):
        raise ValueError(
            f"Invalid number in row {row_number}, column {column_name}: {value}"
        )
    return number


def read_traci_workbook(source):
    """Read TRACI 2.2 substance rows from an Excel workbook."""
    try:
        archive = zipfile.ZipFile(source)
    except (zipfile.BadZipFile, OSError) as exc:
        raise ValueError("The uploaded file is not a valid .xlsx workbook.") from exc

    with archive:
        try:
            worksheet_path = _substances_sheet_path(archive)
            worksheet = ET.fromstring(archive.read(worksheet_path))
        except KeyError as exc:
            raise ValueError(f"Workbook is missing a required sheet file: {exc}") from exc
        except ET.ParseError as exc:
            raise ValueError("Workbook contains invalid spreadsheet XML.") from exc

        rows = _read_rows(worksheet, _shared_strings(archive))

    header_row_index = next(
        (index for index, (_, values) in enumerate(rows) if any(value.strip() for value in values)),
        None,
    )
    if header_row_index is None:
        raise ValueError("The Substances sheet is empty.")

    header_number, headers = rows[header_row_index]
    required_headers = {header for _, header, _ in TRACI_COLUMNS}
    missing_headers = required_headers - set(headers)
    if missing_headers:
        raise ValueError(
            "The Substances sheet is missing required columns: "
            + ", ".join(sorted(missing_headers))
        )

    header_positions = {
        header: headers.index(header)
        for _, header, _ in TRACI_COLUMNS
    }
    records = []
    for row_number, values in rows[header_row_index + 1:]:
        record = {}
        for attribute, header, value_type in TRACI_COLUMNS:
            position = header_positions[header]
            value = values[position] if position < len(values) else ""
            record[attribute] = _clean_value(
                value,
                value_type,
                row_number,
                header,
            )

        if record["cas_number"] is None and record["substance_name"] is None:
            continue
        if record["substance_name"] is None:
            raise ValueError(f"Missing substance name in row {row_number}.")
        records.append(record)

    if not records:
        raise ValueError(f"No substance records found after header row {header_number}.")

    return records
