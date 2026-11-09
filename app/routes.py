
from flask import Blueprint, render_template, request, send_file
from sqlalchemy import func
from sqlalchemy.orm import sessionmaker
from io import BytesIO
import pandas as pd
import re

from scripts.models import engine, AnnualRecord, DailyRecord, TraciRecord
from scripts.traci_data import TRACI_COLUMNS, read_traci_workbook


main = Blueprint("main", __name__)

Session = sessionmaker(bind=engine)

PER_PAGE = 100

TRACI_COLUMN_GUIDE = (
    ("CAS registry number", "Chemical Abstracts Service identifier", ""),
    ("Formatted CAS number", "Display format of the CAS identifier", ""),
    ("Substance name", "Name listed in the source workbook", ""),
    ("Acidification potential", "Air emissions", "kg SO2-eq / kg substance"),
    ("Ecotoxicity factor", "Urban air emissions to freshwater", "CTUeco / kg substance"),
    ("Ecotoxicity factor", "Continental air emissions to freshwater", "CTUeco / kg substance"),
    ("Ecotoxicity factor", "Continental freshwater emissions", "CTUeco / kg substance"),
    ("Ecotoxicity factor", "Continental seawater emissions", "CTUeco / kg substance"),
    ("Ecotoxicity factor", "Continental natural-soil emissions", "CTUeco / kg substance"),
    ("Ecotoxicity factor", "Continental agricultural-soil emissions", "CTUeco / kg substance"),
    ("Ecotoxicity data flag", "Source confidence category", ""),
    ("Climate-change potential", "Air emissions", "kg CO2-eq / kg substance"),
    ("Cancer health factor", "Urban air emissions", "CTUcancer / kg substance"),
    ("Non-cancer health factor", "Urban air emissions", "CTUnoncancer / kg substance"),
    ("Cancer health factor", "Continental rural-air emissions", "CTUcancer / kg substance"),
    ("Non-cancer health factor", "Continental rural-air emissions", "CTUnoncancer / kg substance"),
    ("Cancer health factor", "Continental freshwater emissions", "CTUcancer / kg substance"),
    ("Non-cancer health factor", "Continental freshwater emissions", "CTUnoncancer / kg substance"),
    ("Cancer health factor", "Continental seawater emissions", "CTUcancer / kg substance"),
    ("Non-cancer health factor", "Continental seawater emissions", "CTUnoncancer / kg substance"),
    ("Cancer health factor", "Continental natural-soil emissions", "CTUcancer / kg substance"),
    ("Non-cancer health factor", "Continental natural-soil emissions", "CTUnoncancer / kg substance"),
    ("Cancer health factor", "Continental agricultural-soil emissions", "CTUcancer / kg substance"),
    ("Non-cancer health factor", "Continental agricultural-soil emissions", "CTUnoncancer / kg substance"),
    ("Cancer factor data flag", "Source confidence category", ""),
    ("Non-cancer factor data flag", "Source confidence category", ""),
    ("Particulate-matter health potential", "Air emissions", "kg PM2.5-eq / kg substance"),
    ("Ozone-depletion potential", "Air emissions", "kg CFC-11-eq / kg substance"),
    ("Photochemical-smog potential", "Air emissions", "kg O3-eq / kg substance"),
)

TRACI_NUMERIC_FACTORS = tuple(
    (attribute, guide[0], guide[1], guide[2])
    for (attribute, _, value_type), guide in zip(TRACI_COLUMNS, TRACI_COLUMN_GUIDE)
    if value_type == "number"
)


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

    original = description
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
   
    for state_name in sorted(states, key=len, reverse=True):

        if state_name in description:

            result["state"] = states[state_name]
            break

    if not result["state"]:

        for state_code in states.values():

            if re.search(rf"\b{state_code}\b", original):

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


def build_daily_chart(session, query, view):

    if view == "month":
        period_columns = (
            DailyRecord.year,
            DailyRecord.month,
        )
    elif view == "quarter":
        period_columns = (
            DailyRecord.year,
            DailyRecord.quarter,
        )
    elif view == "year":
        period_columns = (
            DailyRecord.year,
        )
    else:
        period_columns = (
            DailyRecord.date,
        )

    chart_rows = (
        session.query(
            *period_columns,
            func.coalesce(
                func.sum(DailyRecord.co2_mass),
                0,
            ).label("co2_mass"),
        )
        .filter(
            DailyRecord.id.in_(
                query.with_entities(DailyRecord.id)
            )
        )
        .group_by(*period_columns)
        .order_by(*period_columns)
        .all()
    )

    chart_data = []

    for row in chart_rows:
        if view == "month":
            label = f"{row.year}-{row.month:02d}"
        elif view == "quarter":
            label = f"{row.year} Q{row.quarter}"
        elif view == "year":
            label = str(row.year)
        else:
            label = row.date

        chart_data.append(
            (label, float(row.co2_mass or 0))
        )

    chart_max = max(
        (value for _, value in chart_data),
        default=0,
    )
    chart_scale = chart_max or 1
    chart_width = 960
    chart_height = 320
    plot_left = 72
    plot_right = 20
    plot_top = 24
    plot_bottom = 58
    plot_width = chart_width - plot_left - plot_right
    plot_height = chart_height - plot_top - plot_bottom
    step = plot_width / len(chart_data) if chart_data else plot_width
    bar_width = max(1, min(18, step * 0.72))
    label_interval = max(1, (len(chart_data) + 7) // 8)

    bars = []

    for index, (label, value) in enumerate(chart_data):
        bar_height = value / chart_scale * plot_height
        x = plot_left + index * step + (step - bar_width) / 2
        bars.append({
            "x": round(x, 2),
            "y": round(plot_top + plot_height - bar_height, 2),
            "width": round(bar_width, 2),
            "height": round(bar_height, 2),
            "label": label,
            "value": f"{value:,.2f}",
            "show_label": (
                index % label_interval == 0
                or index == len(chart_data) - 1
            ),
            "label_x": round(x + bar_width / 2, 2),
        })

    ticks = []

    for index in range(5):
        value = chart_scale * (4 - index) / 4
        y = plot_top + plot_height * index / 4
        ticks.append({
            "y": round(y, 2),
            "value": f"{value:,.0f}",
        })

    return {
        "bars": bars,
        "ticks": ticks,
        "max": chart_max,
        "period": {
            "month": "month",
            "quarter": "quarter",
            "year": "year",
        }.get(view, "day"),
        "height": chart_height,
    }


@main.route("/")
def home():

    return render_template("home.html")


@main.route("/annual")
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

        emissions_chart = build_daily_chart(
            session=session,
            query=query,
            view=view,
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
            emissions_chart=emissions_chart,
        )

    finally:

        session.close()


@main.route("/traci")
def traci():
    session = Session()

    try:
        search = request.args.get("search", "").strip()
        factor_options = {
            attribute: {
                "attribute": attribute,
                "title": title,
                "context": context,
                "unit": unit,
            }
            for attribute, title, context, unit in TRACI_NUMERIC_FACTORS
        }
        selected_factor = request.args.get(
            "factor",
            "photochemical_oxidation_air",
        )
        if selected_factor not in factor_options:
            selected_factor = "photochemical_oxidation_air"

        factor_column = getattr(TraciRecord, selected_factor)
        reported_factor_count = (
            session.query(func.count(factor_column))
            .scalar()
            or 0
        )
        top_factor_rows = (
            session.query(
                TraciRecord.substance_name,
                TraciRecord.formatted_cas_number,
                TraciRecord.cas_number,
                factor_column,
            )
            .filter(factor_column.isnot(None))
            .order_by(factor_column.desc(), TraciRecord.substance_name)
            .limit(10)
            .all()
        )
        maximum_factor = max(
            (abs(float(row[3])) for row in top_factor_rows),
            default=0,
        )
        top_factors = [
            {
                "rank": rank,
                "substance_name": row.substance_name,
                "cas_number": row.formatted_cas_number or row.cas_number,
                "value": float(row[3]),
                "value_display": f"{float(row[3]):.4g}",
                "bar_width": (
                    max(1, abs(float(row[3])) / maximum_factor * 100)
                    if maximum_factor
                    else 0
                ),
            }
            for rank, row in enumerate(top_factor_rows, start=1)
        ]

        page = max(1, int_or_none(request.args.get("page")) or 1)

        query = session.query(TraciRecord)
        if search:
            pattern = f"%{search}%"
            query = query.filter(
                (TraciRecord.substance_name.ilike(pattern))
                | (TraciRecord.cas_number.ilike(pattern))
                | (TraciRecord.formatted_cas_number.ilike(pattern))
            )

        total = query.count()
        total_pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
        page = min(page, total_pages)
        rows = (
            query.order_by(TraciRecord.substance_name)
            .offset((page - 1) * PER_PAGE)
            .limit(PER_PAGE)
            .all()
        )

        columns = [(attribute, label) for attribute, label, _ in TRACI_COLUMNS]
        return render_template(
            "traci.html",
            rows=rows,
            columns=columns,
            headers=[
                {
                    "attribute": attribute,
                    "source_label": label,
                    "title": guide[0],
                    "context": guide[1],
                    "unit": guide[2],
                }
                for (attribute, label), guide in zip(columns, TRACI_COLUMN_GUIDE)
            ],
            search=search,
            factor_options=TRACI_NUMERIC_FACTORS,
            selected_factor=selected_factor,
            selected_factor_info=factor_options[selected_factor],
            reported_factor_count=reported_factor_count,
            top_factors=top_factors,
            total=total,
            total_display=f"{total:,}",
            page=page,
            total_pages=total_pages,
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
                "import_mode",
                "append"
            )

            if data_type not in {"annual", "daily", "traci"}:

                error = "Please select a supported data type."

            elif not file:

                error = (
                    "Please select a data file."
                )

            elif data_type == "traci":

                if not (file.filename or "").lower().endswith(".xlsx"):

                    error = "TRACI data must be uploaded as an .xlsx workbook."

                else:

                    try:
                        records = read_traci_workbook(file.stream)

                        if mode == "replace":
                            session.query(TraciRecord).delete()

                        session.bulk_insert_mappings(TraciRecord, records)
                        session.commit()
                        message = (
                            f"Successfully imported {len(records):,} TRACI "
                            "record(s). View them on the TRACI 2.2 page."
                        )
                    except Exception as exc:
                        session.rollback()
                        error = f"Import failed: {exc}"

            elif not (file.filename or "").lower().endswith(".csv"):

                error = "Annual and daily data must be uploaded as CSV files."

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
