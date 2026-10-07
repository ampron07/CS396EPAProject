from flask import Blueprint, render_template, request
from sqlalchemy import func, literal
from sqlalchemy.orm import sessionmaker
from scripts.models import engine, AnnualRecord, DailyRecord

main = Blueprint("main", __name__)


@main.route("/")
def home():
    Session = sessionmaker(bind=engine)
    session = Session()

    facility = request.args.get("facility", "").strip()
    state = request.args.get("state", "").strip().upper()
    year = request.args.get("year", "").strip()

    query = session.query(AnnualRecord)

    if facility:
        query = query.filter(AnnualRecord.facility_name.ilike(f"%{facility}%"))

    if state:
        query = query.filter(AnnualRecord.state_code == state)

    if year:
        query = query.filter(AnnualRecord.year == int(year))

    all_records = session.query(AnnualRecord).all()
    print("Total records Flask sees:", len(all_records))

    records = query.all()
    print("Records found:", len(records))

    session.close()

    return render_template(
        "index.html",
        records=records,
        facility=facility,
        state=state,
        year=year
    )

# ---------------------------------------------------------------------------
# Daily emissions explorer: filter by day / month / quarter, and choose
# whether results are shown per day, per month, per quarter, or per year.
# ---------------------------------------------------------------------------

PER_PAGE = 100

# Which columns define one "time bucket" for each view.
PERIOD_COLUMNS = {
    "day": [DailyRecord.date],
    "month": [DailyRecord.year, DailyRecord.month],
    "quarter": [DailyRecord.year, DailyRecord.quarter],
    "year": [DailyRecord.year],
}


def int_or_none(value):
    """Turn a form value like '3' into 3, or '' into None."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


@main.route("/daily")
def daily():
    # 1. Read the form values from the URL (?state=KY&quarter=1&view=month ...)
    facility = request.args.get("facility", "").strip()
    state = request.args.get("state", "").strip().upper()
    year = int_or_none(request.args.get("year"))
    quarter = int_or_none(request.args.get("quarter"))
    month = int_or_none(request.args.get("month"))
    day = request.args.get("day", "").strip()          # "YYYY-MM-DD" from the date picker
    view = request.args.get("view", "day")
    if view not in PERIOD_COLUMNS:
        view = "day"
    page = max(int_or_none(request.args.get("page")) or 1, 1)

    period_cols = PERIOD_COLUMNS[view]

    # 2. Pick what to show: the unit's identity + the time bucket + totals for that bucket.
    #    In "day" view each row already IS one day, so we show the values as they are.
    #    In the other views we add up (SUM) all the days inside each bucket.
    grouped = view != "day"

    def total_of(column):
        return (func.sum(column) if grouped else column).label(column.key)

    query = sessionmaker(bind=engine)().query(
        DailyRecord.state_code,
        DailyRecord.facility_name,
        DailyRecord.facility_id,
        DailyRecord.unit_id,
        *period_cols,
        (func.count() if grouped else literal(1)).label("days"),
        total_of(DailyRecord.operating_time),
        total_of(DailyRecord.gross_load),
        total_of(DailyRecord.heat_input),
        total_of(DailyRecord.co2_mass),
        total_of(DailyRecord.so2_mass),
        total_of(DailyRecord.nox_mass),
    )

    # 3. Filters: each one only applies if the user filled it in.
    if facility:
        query = query.filter(DailyRecord.facility_name.ilike(f"%{facility}%"))
    if state:
        query = query.filter(DailyRecord.state_code == state)
    if year:
        query = query.filter(DailyRecord.year == year)
    if quarter:
        query = query.filter(DailyRecord.quarter == quarter)
    if month:
        query = query.filter(DailyRecord.month == month)
    if day:
        query = query.filter(DailyRecord.date == day)

    # 4. Group rows into one row per unit per time bucket, then sort.
    if grouped:
        query = query.group_by(DailyRecord.facility_id, DailyRecord.unit_id, *period_cols)
    query = query.order_by(
        *period_cols, DailyRecord.state_code, DailyRecord.facility_name, DailyRecord.unit_id
    )

    # 5. Only fetch one page of results.
    total = query.count()
    rows = query.limit(PER_PAGE).offset((page - 1) * PER_PAGE).all()
    query.session.close()

    return render_template(
        "daily.html",
        rows=rows,
        total=total,
        page=page,
        pages=max((total + PER_PAGE - 1) // PER_PAGE, 1),
        view=view,
        facility=facility,
        state=state,
        year=year,
        quarter=quarter,
        month=month,
        day=day,
    )