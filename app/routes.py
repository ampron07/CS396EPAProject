from flask import Blueprint, render_template, request, send_file
from sqlalchemy import func, literal
from sqlalchemy.orm import sessionmaker
from io import BytesIO
import pandas as pd
import re

from scripts.models import engine, AnnualRecord, DailyRecord


main = Blueprint("main", __name__)

Session = sessionmaker(bind=engine)

PER_PAGE = 100


PERIOD_COLUMNS = {
    "day": [DailyRecord.date],
    "month": [DailyRecord.year, DailyRecord.month],
    "quarter": [DailyRecord.year, DailyRecord.quarter],
    "year": [DailyRecord.year],
}


def int_or_none(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def float_or_none(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Description-based search
# ---------------------------------------------------------------------------

def parse_description(description):
    description = description.lower()

    states = {
        "alabama": "AL",
        "alaska": "AK",
        "arizona": "AZ",
        "arkansas": "AR",
        "california": "CA",
        "colorado": "CO",
        "florida": "FL",
        "georgia": "GA",
        "illinois": "IL",
        "indiana": "IN",
        "kentucky": "KY",
        "michigan": "MI",
        "mississippi": "MS",
        "missouri": "MO",
        "ohio": "OH",
        "tennessee": "TN",
        "texas": "TX",
        "virginia": "VA",
        "west virginia": "WV",
        "wisconsin": "WI",
    }

    result = {
        "state": "",
        "fuel": "",
        "year": None,
        "co2_min": None,
    }

    for state_name, state_code in states.items():
        if (
            state_name in description
            or f" {state_code.lower()} " in f" {description} "
        ):
            result["state"] = state_code
            break

    fuel_keywords = {
        "natural gas": "Natural Gas",
        "coal": "Coal",
        "gas": "Natural Gas",
        "oil": "Oil",
        "petroleum": "Oil",
    }

    for keyword, fuel in fuel_keywords.items():
        if keyword in description:
            result["fuel"] = fuel
            break

    year_match = re.search(r"\b(20\d{2})\b", description)

    if year_match:
        result["year"] = int(year_match.group(1))

    if (
        "high co2" in description
        or "high carbon dioxide" in description
    ):
        result["co2_min"] = 500000

    return result


# ---------------------------------------------------------------------------
# Helper functions for dropdowns
# ---------------------------------------------------------------------------

def get_states():
    session = Session()

    states = [
        row[0]
        for row in session.query(AnnualRecord.state_code)
        .distinct()
        .order_by(AnnualRecord.state_code)
        .all()
        if row[0]
    ]

    session.close()

    return states


def get_annual_fuels():
    session = Session()

    fuels = [
        row[0]
        for row in session.query(AnnualRecord.primary_fuel)
        .distinct()
        .order_by(AnnualRecord.primary_fuel)
        .all()
        if row[0]
    ]

    session.close()

    return fuels


def get_daily_fuels():
    session = Session()

    fuels = [
        row[0]
        for row in session.query(DailyRecord.primary_fuel_type)
        .distinct()
        .order_by(DailyRecord.primary_fuel_type)
        .all()
        if row[0]
    ]

    session.close()

    return fuels


# ---------------------------------------------------------------------------
# Daily query builder
# ---------------------------------------------------------------------------

def build_daily_query(
    facility="",
    states=None,
    year=None,
    quarter=None,
    month=None,
    day="",
    fuel="",
    co2_min=None,
    view="day",
):
    session = Session()

    period_cols = PERIOD_COLUMNS[view]

    grouped = view != "day"

    def total_of(column):
        if grouped:
            return func.sum(column).label(column.key)

        return column.label(column.key)

    query = session.query(
        DailyRecord.state_code,
        DailyRecord.facility_name,
        DailyRecord.facility_id,
        DailyRecord.unit_id,
        *period_cols,
        (
            func.count()
            if grouped
            else literal(1)
        ).label("days"),
        total_of(DailyRecord.operating_time),
        total_of(DailyRecord.gross_load),
        total_of(DailyRecord.heat_input),
        total_of(DailyRecord.co2_mass),
        total_of(DailyRecord.so2_mass),
        total_of(DailyRecord.nox_mass),
    )

    if facility:
        query = query.filter(
            DailyRecord.facility_name.ilike(
                f"%{facility}%"
            )
        )

    if states:
        query = query.filter(
            DailyRecord.state_code.in_(states)
        )

    if year is not None:
        query = query.filter(
            DailyRecord.year == year
        )

    if quarter is not None:
        query = query.filter(
            DailyRecord.quarter == quarter
        )

    if month is not None:
        query = query.filter(
            DailyRecord.month == month
        )

    if day:
        query = query.filter(
            DailyRecord.date == day
        )

    if fuel:
        query = query.filter(
            DailyRecord.primary_fuel_type == fuel
        )

    if co2_min is not None:
        query = query.filter(
            DailyRecord.co2_mass >= co2_min
        )

    if grouped:
        query = query.group_by(
            DailyRecord.facility_id,
            DailyRecord.unit_id,
            *period_cols,
        )

    query = query.order_by(
        *period_cols,
        DailyRecord.state_code,
        DailyRecord.facility_name,
        DailyRecord.unit_id,
    )

    return query, session


# ---------------------------------------------------------------------------
# Annual data page
# ---------------------------------------------------------------------------

@main.route("/")
def index():
    session = Session()

    facility = request.args.get(
        "facility",
        ""
    ).strip()

    description = request.args.get(
        "description",
        ""
    ).strip()

    states = request.args.getlist("state")

    if not states:
        single_state = request.args.get(
            "state",
            ""
        ).strip().upper()

        if single_state:
            states = [single_state]

    year = int_or_none(
        request.args.get("year")
    )

    fuel = request.args.get(
        "fuel",
        ""
    ).strip()

    co2_min = float_or_none(
        request.args.get("co2_min")
    )

    # Apply description-based search.
    if description:
        parsed = parse_description(
            description
        )

        if parsed["state"]:
            states = [parsed["state"]]

        if parsed["fuel"]:
            fuel = parsed["fuel"]

        if parsed["year"]:
            year = parsed["year"]

        if parsed["co2_min"] is not None:
            co2_min = parsed["co2_min"]

    query = session.query(
        AnnualRecord
    )

    if facility:
        query = query.filter(
            AnnualRecord.facility_name.ilike(
                f"%{facility}%"
            )
        )

    if states:
        query = query.filter(
            AnnualRecord.state_code.in_(states)
        )

    if year is not None:
        query = query.filter(
            AnnualRecord.year == year
        )

    if fuel:
        query = query.filter(
            AnnualRecord.primary_fuel == fuel
        )

    if co2_min is not None:
        query = query.filter(
            AnnualRecord.co2_mass >= co2_min
        )

    records = query.all()

    available_states = get_states()
    available_fuels = get_annual_fuels()

    session.close()

    return render_template(
        "index.html",
        records=records,
        facility=facility,
        states=states,
        state=states[0] if states else "",
        year=request.args.get(
            "year",
            ""
        ),
        fuel=fuel,
        co2_min=request.args.get(
            "co2_min",
            ""
        ),
        description=description,
        available_states=available_states,
        available_fuels=available_fuels,
    )


# ---------------------------------------------------------------------------
# Daily data page
# ---------------------------------------------------------------------------

@main.route("/daily")
def daily():
    facility = request.args.get(
        "facility",
        ""
    ).strip()

    states = request.args.getlist("state")

    if not states:
        single_state = request.args.get(
            "state",
            ""
        ).strip().upper()

        if single_state:
            states = [single_state]

    year = int_or_none(
        request.args.get("year")
    )

    quarter = int_or_none(
        request.args.get("quarter")
    )

    month = int_or_none(
        request.args.get("month")
    )

    day = request.args.get(
        "day",
        ""
    ).strip()

    fuel = request.args.get(
        "fuel",
        ""
    ).strip()

    co2_min = float_or_none(
        request.args.get("co2_min")
    )

    view = request.args.get(
        "view",
        "day"
    )

    if view not in PERIOD_COLUMNS:
        view = "day"

    page = max(
        int_or_none(
            request.args.get("page")
        ) or 1,
        1,
    )

    query, session = build_daily_query(
        facility=facility,
        states=states,
        year=year,
        quarter=quarter,
        month=month,
        day=day,
        fuel=fuel,
        co2_min=co2_min,
        view=view,
    )

    total = query.count()

    rows = (
        query
        .limit(PER_PAGE)
        .offset(
            (page - 1) * PER_PAGE
        )
        .all()
    )

    pages = max(
        (total + PER_PAGE - 1) // PER_PAGE,
        1,
    )

    available_states = get_states()
    available_fuels = get_daily_fuels()

    session.close()

    return render_template(
        "daily.html",
        rows=rows,
        total=total,
        page=page,
        pages=pages,
        view=view,
        facility=facility,
        states=states,
        state=states[0] if states else "",
        year=request.args.get(
            "year",
            ""
        ),
        quarter=request.args.get(
            "quarter",
            ""
        ),
        month=request.args.get(
            "month",
            ""
        ),
        day=day,
        fuel=fuel,
        co2_min=request.args.get(
            "co2_min",
            ""
        ),
        available_states=available_states,
        available_fuels=available_fuels,
    )


# ---------------------------------------------------------------------------
# Upload data
# ---------------------------------------------------------------------------

@main.route(
    "/upload",
    methods=["GET", "POST"]
)
def upload():
    message = None
    error = None

    if request.method == "POST":
        file = request.files.get("file")

        data_type = request.form.get(
            "data_type",
            "annual"
        )

        mode = request.form.get(
            "mode",
            "append"
        )

        if not file or file.filename == "":
            error = "Please select a CSV file."

        elif not file.filename.lower().endswith(".csv"):
            error = "Only CSV files are supported."

        else:
            try:
                if data_type == "annual":

                    file.stream.seek(0)

                    df = pd.read_csv(file)

                    required_columns = [
                        "State",
                        "Facility Name",
                        "Facility ID",
                        "Unit ID",
                        "Year",
                        "Sum of the Operating Time",
                        "Gross Load (MWh)",
                        "Heat Input (mmBtu)",
                        "SO2 Mass (short tons)",
                        "SO2 Rate (lbs/mmBtu)",
                        "CO2 Mass (short tons)",
                        "CO2 Rate (short tons/mmBtu)",
                        "NOx Mass (short tons)",
                        "NOx Rate (lbs/mmBtu)",
                        "Primary Fuel Type",
                        "Unit Type",
                    ]

                    missing = [
                        column
                        for column in required_columns
                        if column not in df.columns
                    ]

                    if missing:
                        error = (
                            "The uploaded file is missing "
                            "required columns: "
                            + ", ".join(missing)
                        )

                    else:
                        session = Session()

                        if mode == "replace":
                            session.query(
                                AnnualRecord
                            ).delete()

                        for _, row in df.iterrows():

                            record = AnnualRecord(
                                state_code=row.get(
                                    "State"
                                ),
                                facility_name=row.get(
                                    "Facility Name"
                                ),
                                facility_id=row.get(
                                    "Facility ID"
                                ),
                                unit_id=(
                                    str(
                                        row.get("Unit ID")
                                    )
                                    if pd.notna(
                                        row.get("Unit ID")
                                    )
                                    else None
                                ),
                                year=row.get(
                                    "Year"
                                ),
                                operating_time=row.get(
                                    "Sum of the Operating Time"
                                ),
                                gross_load=row.get(
                                    "Gross Load (MWh)"
                                ),
                                heat_input=row.get(
                                    "Heat Input (mmBtu)"
                                ),
                                so2_mass=row.get(
                                    "SO2 Mass (short tons)"
                                ),
                                so2_rate=row.get(
                                    "SO2 Rate (lbs/mmBtu)"
                                ),
                                co2_mass=row.get(
                                    "CO2 Mass (short tons)"
                                ),
                                co2_rate=row.get(
                                    "CO2 Rate (short tons/mmBtu)"
                                ),
                                nox_mass=row.get(
                                    "NOx Mass (short tons)"
                                ),
                                nox_rate=row.get(
                                    "NOx Rate (lbs/mmBtu)"
                                ),
                                primary_fuel=row.get(
                                    "Primary Fuel Type"
                                ),
                                unit_type=row.get(
                                    "Unit Type"
                                ),
                            )

                            session.add(record)

                        session.commit()

                        count = session.query(
                            AnnualRecord
                        ).count()

                        session.close()

                        message = (
                            "Successfully imported annual "
                            "data. The database now contains "
                            f"{count:,} annual records."
                        )

                elif data_type == "daily":

                    required_columns = [
                        "State",
                        "Facility Name",
                        "Facility ID",
                        "Unit ID",
                        "Associated Stacks",
                        "Date",
                        "Operating Time Count",
                        "Sum of the Operating Time",
                        "Gross Load (MWh)",
                        "Steam Load (1000 lb)",
                        "SO2 Mass (short tons)",
                        "SO2 Rate (lbs/mmBtu)",
                        "CO2 Mass (short tons)",
                        "CO2 Rate (short tons/mmBtu)",
                        "NOx Mass (short tons)",
                        "NOx Rate (lbs/mmBtu)",
                        "Heat Input (mmBtu)",
                        "Primary Fuel Type",
                        "Secondary Fuel Type",
                        "Unit Type",
                        "SO2 Controls",
                        "NOx Controls",
                        "PM Controls",
                        "Hg Controls",
                        "Program Code",
                    ]

                    file.stream.seek(0)

                    header_df = pd.read_csv(
                        file,
                        nrows=0
                    )

                    missing = [
                        column
                        for column in required_columns
                        if column not in header_df.columns
                    ]

                    if missing:
                        error = (
                            "The uploaded file is missing "
                            "required columns: "
                            + ", ".join(missing)
                        )

                    else:
                        file.stream.seek(0)

                        connection = engine.connect()

                        if mode == "replace":
                            connection.exec_driver_sql(
                                "DELETE FROM daily_records"
                            )
                            connection.commit()

                        connection.close()

                        total_imported = 0

                        for chunk in pd.read_csv(
                            file,
                            chunksize=50000
                        ):

                            chunk["Date"] = pd.to_datetime(
                                chunk["Date"],
                                errors="coerce"
                            )

                            chunk = chunk.dropna(
                                subset=["Date"]
                            )

                            daily_df = pd.DataFrame({
                                "state_code": chunk[
                                    "State"
                                ],
                                "facility_name": chunk[
                                    "Facility Name"
                                ],
                                "facility_id": pd.to_numeric(
                                    chunk[
                                        "Facility ID"
                                    ],
                                    errors="coerce"
                                ),
                                "unit_id": chunk[
                                    "Unit ID"
                                ].astype(str),
                                "associated_stacks": chunk[
                                    "Associated Stacks"
                                ],
                                "date": chunk[
                                    "Date"
                                ].dt.strftime(
                                    "%Y-%m-%d"
                                ),
                                "year": chunk[
                                    "Date"
                                ].dt.year,
                                "quarter": (
                                    (
                                        chunk[
                                            "Date"
                                        ].dt.month - 1
                                    ) // 3
                                ) + 1,
                                "month": chunk[
                                    "Date"
                                ].dt.month,
                                "operating_time_count": chunk[
                                    "Operating Time Count"
                                ],
                                "operating_time": chunk[
                                    "Sum of the Operating Time"
                                ],
                                "gross_load": chunk[
                                    "Gross Load (MWh)"
                                ],
                                "steam_load": chunk[
                                    "Steam Load (1000 lb)"
                                ],
                                "heat_input": chunk[
                                    "Heat Input (mmBtu)"
                                ],
                                "so2_mass": chunk[
                                    "SO2 Mass (short tons)"
                                ],
                                "so2_rate": chunk[
                                    "SO2 Rate (lbs/mmBtu)"
                                ],
                                "co2_mass": chunk[
                                    "CO2 Mass (short tons)"
                                ],
                                "co2_rate": chunk[
                                    "CO2 Rate (short tons/mmBtu)"
                                ],
                                "nox_mass": chunk[
                                    "NOx Mass (short tons)"
                                ],
                                "nox_rate": chunk[
                                    "NOx Rate (lbs/mmBtu)"
                                ],
                                "primary_fuel_type": chunk[
                                    "Primary Fuel Type"
                                ],
                                "secondary_fuel_type": chunk[
                                    "Secondary Fuel Type"
                                ],
                                "unit_type": chunk[
                                    "Unit Type"
                                ],
                                "so2_controls": chunk[
                                    "SO2 Controls"
                                ],
                                "nox_controls": chunk[
                                    "NOx Controls"
                                ],
                                "pm_controls": chunk[
                                    "PM Controls"
                                ],
                                "hg_controls": chunk[
                                    "Hg Controls"
                                ],
                                "program_code": chunk[
                                    "Program Code"
                                ],
                            })

                            daily_df.to_sql(
                                "daily_records",
                                engine,
                                if_exists="append",
                                index=False,
                                method="multi",
                                chunksize=1000,
                            )

                            total_imported += len(
                                daily_df
                            )

                        session = Session()

                        count = session.query(
                            DailyRecord
                        ).count()

                        session.close()

                        message = (
                            "Successfully imported daily "
                            "data. The database now contains "
                            f"{count:,} daily records."
                        )

            except Exception as e:
                error = f"Upload failed: {e}"

    return render_template(
        "upload.html",
        message=message,
        error=error,
    )


# ---------------------------------------------------------------------------
# Download annual results
# ---------------------------------------------------------------------------

@main.route("/download/annual")
def download_annual():

    facility = request.args.get(
        "facility",
        ""
    ).strip()

    states = request.args.getlist("state")

    if not states:
        single_state = request.args.get(
            "state",
            ""
        ).strip().upper()

        if single_state:
            states = [single_state]

    year = int_or_none(
        request.args.get("year")
    )

    fuel = request.args.get(
        "fuel",
        ""
    ).strip()

    co2_min = float_or_none(
        request.args.get("co2_min")
    )

    session = Session()

    query = session.query(
        AnnualRecord
    )

    if facility:
        query = query.filter(
            AnnualRecord.facility_name.ilike(
                f"%{facility}%"
            )
        )

    if states:
        query = query.filter(
            AnnualRecord.state_code.in_(states)
        )

    if year is not None:
        query = query.filter(
            AnnualRecord.year == year
        )

    if fuel:
        query = query.filter(
            AnnualRecord.primary_fuel == fuel
        )

    if co2_min is not None:
        query = query.filter(
            AnnualRecord.co2_mass >= co2_min
        )

    records = query.all()

    data = []

    for record in records:
        data.append({
            "State": record.state_code,
            "Facility Name": record.facility_name,
            "Facility ID": record.facility_id,
            "Unit ID": record.unit_id,
            "Year": record.year,
            "Primary Fuel Type": record.primary_fuel,
            "Unit Type": record.unit_type,
            "CO2 Mass": record.co2_mass,
            "CO2 Rate": record.co2_rate,
            "NOx Mass": record.nox_mass,
            "NOx Rate": record.nox_rate,
            "SO2 Mass": record.so2_mass,
            "SO2 Rate": record.so2_rate,
            "Gross Load": record.gross_load,
            "Heat Input": record.heat_input,
        })

    session.close()

    df = pd.DataFrame(data)

    output = BytesIO()

    df.to_csv(
        output,
        index=False
    )

    output.seek(0)

    return send_file(
        output,
        mimetype="text/csv",
        as_attachment=True,
        download_name="annual_results.csv",
    )


# ---------------------------------------------------------------------------
# Download daily results
# ---------------------------------------------------------------------------

@main.route("/download/daily")
def download_daily():

    facility = request.args.get(
        "facility",
        ""
    ).strip()

    states = request.args.getlist("state")

    if not states:
        single_state = request.args.get(
            "state",
            ""
        ).strip().upper()

        if single_state:
            states = [single_state]

    year = int_or_none(
        request.args.get("year")
    )

    quarter = int_or_none(
        request.args.get("quarter")
    )

    month = int_or_none(
        request.args.get("month")
    )

    day = request.args.get(
        "day",
        ""
    ).strip()

    fuel = request.args.get(
        "fuel",
        ""
    ).strip()

    co2_min = float_or_none(
        request.args.get("co2_min")
    )

    view = request.args.get(
        "view",
        "day"
    )

    if view not in PERIOD_COLUMNS:
        view = "day"

    query, session = build_daily_query(
        facility=facility,
        states=states,
        year=year,
        quarter=quarter,
        month=month,
        day=day,
        fuel=fuel,
        co2_min=co2_min,
        view=view,
    )

    rows = query.all()

    data = []

    for row in rows:
        item = {}

        for index, column in enumerate(
            query.column_descriptions
        ):
            item[column["name"]] = row[index]

        data.append(item)

    session.close()

    df = pd.DataFrame(data)

    output = BytesIO()

    df.to_csv(
        output,
        index=False
    )

    output.seek(0)

    return send_file(
        output,
        mimetype="text/csv",
        as_attachment=True,
        download_name="daily_results.csv",
    )