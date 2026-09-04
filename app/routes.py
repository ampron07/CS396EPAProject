from flask import Blueprint, render_template, request
from sqlalchemy.orm import sessionmaker
from scripts.models import engine, AnnualRecord

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