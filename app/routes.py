
from flask import Blueprint, render_template, request, send_file
from sqlalchemy import func
from sqlalchemy.orm import sessionmaker
from io import BytesIO
import pandas as pd
import re

from scripts.models import engine, AnnualRecord, DailyRecord


main = Blueprint("main", __name__)

Session = sessionmaker(bind=engine)

PER_PAGE = 100


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
            or f" {state_code.lower()} "
            in f" {description} "
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

    year_match = re.search(
        r"\b(20\d{2})\b",
        description
    )

    if year_match:

        result["year"] = int(
            year_match.group(1)
        )

    if (
        "high co2" in description
        or "high carbon dioxide" in description
    ):

        result["co2_min"] = 500000

    return result


def get_states(session, model):

    return [
        row[0]
        for row in (
            session.query(model.state_code)
            .filter(
                model.state_code.isnot(None)
            )
            .distinct()
            .order_by(model.state_code)
            .all()
        )
    ]


def get_annual_fuels(session):

    return [
        row[0]
        for row in (
            session.query(
                AnnualRecord.primary_fuel
            )
            .filter(
                AnnualRecord.primary_fuel.isnot(None)
            )
            .distinct()
            .order_by(
                AnnualRecord.primary_fuel
            )
            .all()
        )
    ]


def get_daily_fuels(session):

    return [
        row[0]
        for row in (
            session.query(
                DailyRecord.primary_fuel_type
            )
            .filter(
                DailyRecord.primary_fuel_type.isnot(None)
            )
            .distinct()
            .order_by(
                DailyRecord.primary_fuel_type
            )
            .all()
        )
    ]


def build_daily_query(
    session,
    states=None,
    facility="",
    year=None,
    quarter=None,
    month=None,
    day="",
    fuel="",
    co2_min=None,
):

    query = session.query(
        DailyRecord
    )

    if states:

        query = query.filter(
            DailyRecord.state_code.in_(states)
        )

    if facility:

        query = query.filter(
            DailyRecord.facility_name.ilike(
                f"%{facility}%"
            )
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

    return query


@main.route("/")
def index():

    session = Session()

    try:

        facility = request.args.get(
            "facility",
            ""
        ).strip()

        states = request.args.getlist(
            "state"
        )

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

        description = request.args.get(
            "description",
            ""
        ).strip()

        page = int_or_none(
            request.args.get("page")
        ) or 1

        sort = request.args.get(
            "sort",
            "year"
        )

        direction = request.args.get(
            "direction",
            "desc"
        )

        if description:

            parsed = parse_description(
                description
            )

            if parsed["state"]:

                states = [
                    parsed["state"]
                ]

            if parsed["fuel"]:

                fuel = parsed["fuel"]

            if parsed["year"]:

                year = parsed["year"]

            if parsed["co2_min"] is not None:

                co2_min = parsed["co2_min"]

        query = session.query(
            AnnualRecord
        )

        if states:

            query = query.filter(
                AnnualRecord.state_code.in_(
                    states
                )
            )

        if facility:

            query = query.filter(
                AnnualRecord.facility_name.ilike(
                    f"%{facility}%"
                )
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

        total = query.count()

        total_pages = max(
            1,
            (total + PER_PAGE - 1)
            // PER_PAGE
        )

        if page > total_pages:

            page = total_pages

        sort_columns = {

            "year":
                AnnualRecord.year,

            "facility":
                AnnualRecord.facility_name,

            "state":
                AnnualRecord.state_code,

            "co2":
                AnnualRecord.co2_mass,

            "nox":
                AnnualRecord.nox_mass,

            "so2":
                AnnualRecord.so2_mass,

        }

        sort_column = sort_columns.get(
            sort,
            AnnualRecord.year
        )

        if direction == "asc":

            sort_expression = (
                sort_column.asc()
            )

        else:

            sort_expression = (
                sort_column.desc()
            )

        rows = (
            query
            .order_by(sort_expression)
            .offset(
                (page - 1) * PER_PAGE
            )
            .limit(PER_PAGE)
            .all()
        )

        available_states = get_states(
            session,
            AnnualRecord
        )

        available_fuels = get_annual_fuels(
            session
        )

        return render_template(
            "index.html",
            rows=rows,
            total=total,
            page=page,
            total_pages=total_pages,
            facility=facility,
            states=states,
            year=(
                str(year)
                if year is not None
                else ""
            ),
            fuel=fuel,
            co2_min=(
                str(co2_min)
                if co2_min is not None
                else ""
            ),
            description=description,
            available_states=available_states,
            available_fuels=available_fuels,
            sort=sort,
            direction=direction,
        )

    finally:

        session.close()


@main.route("/daily")
def daily():

    session = Session()

    try:

        facility = request.args.get(
            "facility",
            ""
        ).strip()

        states = request.args.getlist(
            "state"
        )

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
        ).strip()

        description = request.args.get(
            "description",
            ""
        ).strip()

        page = int_or_none(
            request.args.get("page")
        ) or 1

        sort = request.args.get(
            "sort",
            "date"
        )

        direction = request.args.get(
            "direction",
            "desc"
        )

        if description:

            parsed = parse_description(
                description
            )

            if parsed["state"]:

                states = [
                    parsed["state"]
                ]

            if parsed["fuel"]:

                fuel = parsed["fuel"]

            if parsed["year"]:

                year = parsed["year"]

            if parsed["co2_min"] is not None:

                co2_min = 1000

        query = build_daily_query(
            session=session,
            states=states,
            facility=facility,
            year=year,
            quarter=quarter,
            month=month,
            day=day,
            fuel=fuel,
            co2_min=co2_min,
        )

        if view == "month":

            grouped_query = (
                session.query(

                    DailyRecord.state_code.label(
                        "state_code"
                    ),

                    DailyRecord.facility_name.label(
                        "facility_name"
                    ),

                    DailyRecord.unit_id.label(
                        "unit_id"
                    ),

                    DailyRecord.year.label(
                        "year"
                    ),

                    DailyRecord.month.label(
                        "month"
                    ),

                    func.count(
                        DailyRecord.id
                    ).label(
                        "days"
                    ),

                    func.sum(
                        DailyRecord.operating_time
                    ).label(
                        "operating_time"
                    ),

                    func.sum(
                        DailyRecord.gross_load
                    ).label(
                        "gross_load"
                    ),

                    func.sum(
                        DailyRecord.heat_input
                    ).label(
                        "heat_input"
                    ),

                    func.sum(
                        DailyRecord.co2_mass
                    ).label(
                        "co2_mass"
                    ),

                    func.sum(
                        DailyRecord.so2_mass
                    ).label(
                        "so2_mass"
                    ),

                    func.sum(
                        DailyRecord.nox_mass
                    ).label(
                        "nox_mass"
                    ),

                )
                .filter(
                    DailyRecord.id.in_(
                        query.with_entities(
                            DailyRecord.id
                        )
                    )
                )
                .group_by(

                    DailyRecord.state_code,
                    DailyRecord.facility_name,
                    DailyRecord.unit_id,
                    DailyRecord.year,
                    DailyRecord.month,

                )
            )

            sort_columns = {

                "facility":
                    DailyRecord.facility_name,

                "co2":
                    func.sum(
                        DailyRecord.co2_mass
                    ),

                "nox":
                    func.sum(
                        DailyRecord.nox_mass
                    ),

                "so2":
                    func.sum(
                        DailyRecord.so2_mass
                    ),

            }

            sort_column = sort_columns.get(
                sort,
                DailyRecord.year
            )

            if sort == "date":

                sort_column = DailyRecord.year

            if direction == "asc":

                grouped_query = (
                    grouped_query
                    .order_by(
                        sort_column.asc()
                    )
                )

            else:

                grouped_query = (
                    grouped_query
                    .order_by(
                        sort_column.desc()
                    )
                )

            total = grouped_query.count()

            total_pages = max(
                1,
                (total + PER_PAGE - 1)
                // PER_PAGE
            )

            if page > total_pages:

                page = total_pages

            rows = (
                grouped_query
                .offset(
                    (page - 1) * PER_PAGE
                )
                .limit(PER_PAGE)
                .all()
            )

        elif view == "quarter":

            grouped_query = (
                session.query(

                    DailyRecord.state_code.label(
                        "state_code"
                    ),

                    DailyRecord.facility_name.label(
                        "facility_name"
                    ),

                    DailyRecord.unit_id.label(
                        "unit_id"
                    ),

                    DailyRecord.year.label(
                        "year"
                    ),

                    DailyRecord.quarter.label(
                        "quarter"
                    ),

                    func.count(
                        DailyRecord.id
                    ).label(
                        "days"
                    ),

                    func.sum(
                        DailyRecord.operating_time
                    ).label(
                        "operating_time"
                    ),

                    func.sum(
                        DailyRecord.gross_load
                    ).label(
                        "gross_load"
                    ),

                    func.sum(
                        DailyRecord.heat_input
                    ).label(
                        "heat_input"
                    ),

                    func.sum(
                        DailyRecord.co2_mass
                    ).label(
                        "co2_mass"
                    ),

                    func.sum(
                        DailyRecord.so2_mass
                    ).label(
                        "so2_mass"
                    ),

                    func.sum(
                        DailyRecord.nox_mass
                    ).label(
                        "nox_mass"
                    ),

                )
                .filter(
                    DailyRecord.id.in_(
                        query.with_entities(
                            DailyRecord.id
                        )
                    )
                )
                .group_by(

                    DailyRecord.state_code,
                    DailyRecord.facility_name,
                    DailyRecord.unit_id,
                    DailyRecord.year,
                    DailyRecord.quarter,

                )
            )

            sort_columns = {

                "facility":
                    DailyRecord.facility_name,

                "co2":
                    func.sum(
                        DailyRecord.co2_mass
                    ),

                "nox":
                    func.sum(
                        DailyRecord.nox_mass
                    ),

                "so2":
                    func.sum(
                        DailyRecord.so2_mass
                    ),

            }

            sort_column = sort_columns.get(
                sort,
                DailyRecord.year
            )

            if direction == "asc":

                grouped_query = (
                    grouped_query
                    .order_by(
                        sort_column.asc()
                    )
                )

            else:

                grouped_query = (
                    grouped_query
                    .order_by(
                        sort_column.desc()
                    )
                )

            total = grouped_query.count()

            total_pages = max(
                1,
                (total + PER_PAGE - 1)
                // PER_PAGE
            )

            if page > total_pages:

                page = total_pages

            rows = (
                grouped_query
                .offset(
                    (page - 1) * PER_PAGE
                )
                .limit(PER_PAGE)
                .all()
            )

        elif view == "year":

            grouped_query = (
                session.query(

                    DailyRecord.state_code.label(
                        "state_code"
                    ),

                    DailyRecord.facility_name.label(
                        "facility_name"
                    ),

                    DailyRecord.unit_id.label(
                        "unit_id"
                    ),

                    DailyRecord.year.label(
                        "year"
                    ),

                    func.count(
                        DailyRecord.id
                    ).label(
                        "days"
                    ),

                    func.sum(
                        DailyRecord.operating_time
                    ).label(
                        "operating_time"
                    ),

                    func.sum(
                        DailyRecord.gross_load
                    ).label(
                        "gross_load"
                    ),

                    func.sum(
                        DailyRecord.heat_input
                    ).label(
                        "heat_input"
                    ),

                    func.sum(
                        DailyRecord.co2_mass
                    ).label(
                        "co2_mass"
                    ),

                    func.sum(
                        DailyRecord.so2_mass
                    ).label(
                        "so2_mass"
                    ),

                    func.sum(
                        DailyRecord.nox_mass
                    ).label(
                        "nox_mass"
                    ),

                )
                .filter(
                    DailyRecord.id.in_(
                        query.with_entities(
                            DailyRecord.id
                        )
                    )
                )
                .group_by(

                    DailyRecord.state_code,
                    DailyRecord.facility_name,
                    DailyRecord.unit_id,
                    DailyRecord.year,

                )
            )

            sort_columns = {

                "facility":
                    DailyRecord.facility_name,

                "co2":
                    func.sum(
                        DailyRecord.co2_mass
                    ),

                "nox":
                    func.sum(
                        DailyRecord.nox_mass
                    ),

                "so2":
                    func.sum(
                        DailyRecord.so2_mass
                    ),

            }

            sort_column = sort_columns.get(
                sort,
                DailyRecord.year
            )

            if direction == "asc":

                grouped_query = (
                    grouped_query
                    .order_by(
                        sort_column.asc()
                    )
                )

            else:

                grouped_query = (
                    grouped_query
                    .order_by(
                        sort_column.desc()
                    )
                )

            total = grouped_query.count()

            total_pages = max(
                1,
                (total + PER_PAGE - 1)
                // PER_PAGE
            )

            if page > total_pages:

                page = total_pages

            rows = (
                grouped_query
                .offset(
                    (page - 1) * PER_PAGE
                )
                .limit(PER_PAGE)
                .all()
            )

        else:

            total = query.count()

            total_pages = max(
                1,
                (total + PER_PAGE - 1)
                // PER_PAGE
            )

            if page > total_pages:

                page = total_pages

            sort_columns = {

                "date":
                    DailyRecord.date,

                "facility":
                    DailyRecord.facility_name,

                "co2":
                    DailyRecord.co2_mass,

                "nox":
                    DailyRecord.nox_mass,

                "so2":
                    DailyRecord.so2_mass,

            }

            sort_column = sort_columns.get(
                sort,
                DailyRecord.date
            )

            if direction == "asc":

                sort_expression = (
                    sort_column.asc()
                )

            else:

                sort_expression = (
                    sort_column.desc()
                )

            rows = (
                query
                .order_by(
                    sort_expression
                )
                .offset(
                    (page - 1) * PER_PAGE
                )
                .limit(PER_PAGE)
                .all()
            )

            class DailyRow:
                pass

            formatted_rows = []

            for row in rows:

                item = DailyRow()

                item.state_code = (
                    row.state_code
                )

                item.facility_name = (
                    row.facility_name
                )

                item.unit_id = (
                    row.unit_id
                )

                item.date = (
                    row.date
                )

                item.year = (
                    row.year
                )

                item.month = (
                    row.month
                )

                item.quarter = (
                    row.quarter
                )

                item.days = 1

                item.operating_time = (
                    row.operating_time
                )

                item.gross_load = (
                    row.gross_load
                )

                item.heat_input = (
                    row.heat_input
                )

                item.co2_mass = (
                    row.co2_mass
                )

                item.so2_mass = (
                    row.so2_mass
                )

                item.nox_mass = (
                    row.nox_mass
                )

                formatted_rows.append(
                    item
                )

            rows = formatted_rows

        available_states = get_states(
            session,
            DailyRecord
        )

        available_fuels = get_daily_fuels(
            session
        )

        return render_template(
            "daily.html",
            rows=rows,
            total=total,
            page=page,
            total_pages=total_pages,
            facility=facility,
            states=states,
            year=(
                str(year)
                if year is not None
                else ""
            ),
            quarter=(
                str(quarter)
                if quarter is not None
                else ""
            ),
            month=(
                str(month)
                if month is not None
                else ""
            ),
            day=day,
            fuel=fuel,
            co2_min=(
                str(co2_min)
                if co2_min is not None
                else ""
            ),
            view=view,
            description=description,
            available_states=available_states,
            available_fuels=available_fuels,
            sort=sort,
            direction=direction,
        )

    finally:

        session.close()


@main.route(
    "/upload",
    methods=["GET", "POST"]
)
def upload():

    session = Session()

    try:

        message = ""
        error = ""

        if request.method == "POST":

            file = request.files.get(
                "file"
            )

            data_type = request.form.get(
                "data_type",
                "annual"
            )

            mode = request.form.get(
                "mode",
                "append"
            )

            if not file:

                error = (
                    "Please select a CSV file."
                )

            elif not file.filename.lower().endswith(
                ".csv"
            ):

                error = (
                    "Only CSV files are supported."
                )

            else:

                try:

                    chunks = pd.read_csv(
                        file,
                        chunksize=10000
                    )

                    first_chunk = True
                    imported = 0

                    if mode == "replace":

                        if data_type == "annual":

                            session.query(
                                AnnualRecord
                            ).delete()

                        else:

                            session.query(
                                DailyRecord
                            ).delete()

                        session.commit()

                    for chunk in chunks:

                        if first_chunk:

                            if data_type == "annual":

                                required_columns = {
                                    "State",
                                    "Facility Name",
                                    "Facility ID",
                                    "Unit ID",
                                    "Year",
                                    "CO2 Mass (short tons)",
                                    "NOx Mass (short tons)",
                                    "SO2 Mass (short tons)",
                                }

                            else:

                                required_columns = {
                                    "State",
                                    "Facility Name",
                                    "Facility ID",
                                    "Unit ID",
                                    "Date",
                                    "CO2 Mass (short tons)",
                                    "NOx Mass (short tons)",
                                    "SO2 Mass (short tons)",
                                }

                            missing = (
                                required_columns
                                - set(chunk.columns)
                            )

                            if missing:

                                error = (
                                    "Missing required columns: "
                                    + ", ".join(
                                        sorted(missing)
                                    )
                                )

                                break

                            first_chunk = False

                        if data_type == "annual":

                            for _, row in chunk.iterrows():

                                record = AnnualRecord(

                                    state_code=row.get(
                                        "State"
                                    ),

                                    facility_name=row.get(
                                        "Facility Name"
                                    ),

                                    facility_id=int_or_none(
                                        row.get(
                                            "Facility ID"
                                        )
                                    ),

                                    unit_id=str(
                                        row.get(
                                            "Unit ID",
                                            ""
                                        )
                                    ),

                                    year=int_or_none(
                                        row.get(
                                            "Year"
                                        )
                                    ),

                                    operating_time=float_or_none(
                                        row.get(
                                            "Sum of the Operating Time"
                                        )
                                    ),

                                    gross_load=float_or_none(
                                        row.get(
                                            "Gross Load (MWh)"
                                        )
                                    ),

                                    heat_input=float_or_none(
                                        row.get(
                                            "Heat Input (mmBtu)"
                                        )
                                    ),

                                    so2_mass=float_or_none(
                                        row.get(
                                            "SO2 Mass (short tons)"
                                        )
                                    ),

                                    so2_rate=float_or_none(
                                        row.get(
                                            "SO2 Rate (lbs/mmBtu)"
                                        )
                                    ),

                                    co2_mass=float_or_none(
                                        row.get(
                                            "CO2 Mass (short tons)"
                                        )
                                    ),

                                    co2_rate=float_or_none(
                                        row.get(
                                            "CO2 Rate (short tons/mmBtu)"
                                        )
                                    ),

                                    nox_mass=float_or_none(
                                        row.get(
                                            "NOx Mass (short tons)"
                                        )
                                    ),

                                    nox_rate=float_or_none(
                                        row.get(
                                            "NOx Rate (lbs/mmBtu)"
                                        )
                                    ),

                                    primary_fuel=row.get(
                                        "Primary Fuel Type"
                                    ),

                                    unit_type=row.get(
                                        "Unit Type"
                                    ),

                                )

                                session.add(
                                    record
                                )

                                imported += 1

                        else:

                            for _, row in chunk.iterrows():

                                date_value = row.get(
                                    "Date"
                                )

                                date_string = (
                                    str(date_value)
                                    if pd.notna(
                                        date_value
                                    )
                                    else ""
                                )

                                year_value = None
                                month_value = None
                                quarter_value = None

                                try:

                                    parsed_date = (
                                        pd.to_datetime(
                                            date_value
                                        )
                                    )

                                    year_value = (
                                        parsed_date.year
                                    )

                                    month_value = (
                                        parsed_date.month
                                    )

                                    quarter_value = (
                                        (
                                            parsed_date.month
                                            - 1
                                        )
                                        // 3
                                    ) + 1

                                except Exception:

                                    pass

                                record = DailyRecord(

                                    state_code=row.get(
                                        "State"
                                    ),

                                    facility_name=row.get(
                                        "Facility Name"
                                    ),

                                    facility_id=int_or_none(
                                        row.get(
                                            "Facility ID"
                                        )
                                    ),

                                    unit_id=str(
                                        row.get(
                                            "Unit ID",
                                            ""
                                        )
                                    ),

                                    associated_stacks=row.get(
                                        "Associated Stacks"
                                    ),

                                    date=date_string,

                                    year=year_value,

                                    quarter=quarter_value,

                                    month=month_value,

                                    operating_time_count=float_or_none(
                                        row.get(
                                            "Operating Time Count"
                                        )
                                    ),

                                    operating_time=float_or_none(
                                        row.get(
                                            "Sum of the Operating Time"
                                        )
                                    ),

                                    gross_load=float_or_none(
                                        row.get(
                                            "Gross Load (MWh)"
                                        )
                                    ),

                                    steam_load=float_or_none(
                                        row.get(
                                            "Steam Load (1000 lb)"
                                        )
                                    ),

                                    heat_input=float_or_none(
                                        row.get(
                                            "Heat Input (mmBtu)"
                                        )
                                    ),

                                    so2_mass=float_or_none(
                                        row.get(
                                            "SO2 Mass (short tons)"
                                        )
                                    ),

                                    so2_rate=float_or_none(
                                        row.get(
                                            "SO2 Rate (lbs/mmBtu)"
                                        )
                                    ),

                                    co2_mass=float_or_none(
                                        row.get(
                                            "CO2 Mass (short tons)"
                                        )
                                    ),

                                    co2_rate=float_or_none(
                                        row.get(
                                            "CO2 Rate (short tons/mmBtu)"
                                        )
                                    ),

                                    nox_mass=float_or_none(
                                        row.get(
                                            "NOx Mass (short tons)"
                                        )
                                    ),

                                    nox_rate=float_or_none(
                                        row.get(
                                            "NOx Rate (lbs/mmBtu)"
                                        )
                                    ),

                                    primary_fuel_type=row.get(
                                        "Primary Fuel Type"
                                    ),

                                    secondary_fuel_type=row.get(
                                        "Secondary Fuel Type"
                                    ),

                                    unit_type=row.get(
                                        "Unit Type"
                                    ),

                                    so2_controls=row.get(
                                        "SO2 Controls"
                                    ),

                                    nox_controls=row.get(
                                        "NOx Controls"
                                    ),

                                    pm_controls=row.get(
                                        "PM Controls"
                                    ),

                                    hg_controls=row.get(
                                        "Hg Controls"
                                    ),

                                    program_code=row.get(
                                        "Program Code"
                                    ),

                                )

                                session.add(
                                    record
                                )

                                imported += 1

                        session.commit()

                    if not error:

                        message = (
                            f"Successfully imported "
                            f"{imported:,} record(s)."
                        )

                except Exception as exc:

                    session.rollback()

                    error = (
                        f"Import failed: {exc}"
                    )

        return render_template(
            "upload.html",
            message=message,
            error=error,
        )

    finally:

        session.close()


@main.route(
    "/download/annual"
)
def download_annual():

    session = Session()

    try:

        facility = request.args.get(
            "facility",
            ""
        ).strip()

        states = request.args.getlist(
            "state"
        )

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

        description = request.args.get(
            "description",
            ""
        ).strip()

        if description:

            parsed = parse_description(
                description
            )

            if parsed["state"]:

                states = [
                    parsed["state"]
                ]

            if parsed["fuel"]:

                fuel = parsed["fuel"]

            if parsed["year"]:

                year = parsed["year"]

            if parsed["co2_min"] is not None:

                co2_min = parsed["co2_min"]

        query = session.query(
            AnnualRecord
        )

        if states:

            query = query.filter(
                AnnualRecord.state_code.in_(
                    states
                )
            )

        if facility:

            query = query.filter(
                AnnualRecord.facility_name.ilike(
                    f"%{facility}%"
                )
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

        rows = query.all()

        data = []

        for row in rows:

            data.append({

                "State":
                    row.state_code,

                "Facility Name":
                    row.facility_name,

                "Facility ID":
                    row.facility_id,

                "Unit ID":
                    row.unit_id,

                "Year":
                    row.year,

                "Operating Time":
                    row.operating_time,

                "Gross Load":
                    row.gross_load,

                "Heat Input":
                    row.heat_input,

                "SO2 Mass":
                    row.so2_mass,

                "SO2 Rate":
                    row.so2_rate,

                "CO2 Mass":
                    row.co2_mass,

                "CO2 Rate":
                    row.co2_rate,

                "NOx Mass":
                    row.nox_mass,

                "NOx Rate":
                    row.nox_rate,

                "Primary Fuel":
                    row.primary_fuel,

                "Unit Type":
                    row.unit_type,

            })

        df = pd.DataFrame(
            data
        )

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

    finally:

        session.close()


@main.route(
    "/download/daily"
)
def download_daily():

    session = Session()

    try:

        facility = request.args.get(
            "facility",
            ""
        ).strip()

        states = request.args.getlist(
            "state"
        )

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

        description = request.args.get(
            "description",
            ""
        ).strip()

        if description:

            parsed = parse_description(
                description
            )

            if parsed["state"]:

                states = [
                    parsed["state"]
                ]

            if parsed["fuel"]:

                fuel = parsed["fuel"]

            if parsed["year"]:

                year = parsed["year"]

            if parsed["co2_min"] is not None:

                co2_min = 1000

        query = build_daily_query(
            session=session,
            states=states,
            facility=facility,
            year=year,
            quarter=quarter,
            month=month,
            day=day,
            fuel=fuel,
            co2_min=co2_min,
        )

        rows = query.all()

        data = []

        for row in rows:

            data.append({

                "State":
                    row.state_code,

                "Facility Name":
                    row.facility_name,

                "Facility ID":
                    row.facility_id,

                "Unit ID":
                    row.unit_id,

                "Associated Stacks":
                    row.associated_stacks,

                "Date":
                    row.date,

                "Year":
                    row.year,

                "Quarter":
                    row.quarter,

                "Month":
                    row.month,

                "Operating Time Count":
                    row.operating_time_count,

                "Operating Time":
                    row.operating_time,

                "Gross Load":
                    row.gross_load,

                "Steam Load":
                    row.steam_load,

                "Heat Input":
                    row.heat_input,

                "SO2 Mass":
                    row.so2_mass,

                "SO2 Rate":
                    row.so2_rate,

                "CO2 Mass":
                    row.co2_mass,

                "CO2 Rate":
                    row.co2_rate,

                "NOx Mass":
                    row.nox_mass,

                "NOx Rate":
                    row.nox_rate,

                "Primary Fuel":
                    row.primary_fuel_type,

                "Secondary Fuel":
                    row.secondary_fuel_type,

                "Unit Type":
                    row.unit_type,

                "SO2 Controls":
                    row.so2_controls,

                "NOx Controls":
                    row.nox_controls,

                "PM Controls":
                    row.pm_controls,

                "Hg Controls":
                    row.hg_controls,

                "Program Code":
                    row.program_code,

            })

        df = pd.DataFrame(
            data
        )

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

    finally:

        session.close()

