import os
import pandas as pd
from sqlalchemy.orm import sessionmaker

from models import engine, AnnualRecord


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(BASE_DIR, "CAMPD_2025.csv")


print("Reading:", CSV_PATH)

df = pd.read_csv(CSV_PATH)

print(f"Found {len(df)} CSV records.")
print("Columns:")
print(df.columns.tolist())


Session = sessionmaker(bind=engine)
session = Session()

# Clear existing annual records before importing
session.query(AnnualRecord).delete()

for _, row in df.iterrows():

    record = AnnualRecord(
        state_code=row.get("State"),
        facility_name=row.get("Facility Name"),
        facility_id=row.get("Facility ID"),
        unit_id=str(row.get("Unit ID")) if pd.notna(row.get("Unit ID")) else None,
        year=row.get("Year"),

        operating_time=row.get("Sum of the Operating Time"),
        gross_load=row.get("Gross Load (MWh)"),
        heat_input=row.get("Heat Input (mmBtu)"),

        so2_mass=row.get("SO2 Mass (short tons)"),
        so2_rate=row.get("SO2 Rate (lbs/mmBtu)"),

        co2_mass=row.get("CO2 Mass (short tons)"),
        co2_rate=row.get("CO2 Rate (short tons/mmBtu)"),

        nox_mass=row.get("NOx Mass (short tons)"),
        nox_rate=row.get("NOx Rate (lbs/mmBtu)"),

        primary_fuel=row.get("Primary Fuel Type"),
        unit_type=row.get("Unit Type")
    )

    session.add(record)


session.commit()

count = session.query(AnnualRecord).count()

print(f"Successfully imported {count} annual records.")

session.close()