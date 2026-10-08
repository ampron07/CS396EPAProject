import os
import pandas as pd

from models import engine


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(BASE_DIR, "Daily Emissions 2026.csv")

CHUNK_SIZE = 50000

print("Reading:", CSV_PATH)

connection = engine.connect()
connection.exec_driver_sql("DELETE FROM daily_records")
connection.commit()
connection.close()

total_imported = 0

for chunk in pd.read_csv(CSV_PATH, chunksize=CHUNK_SIZE):
    print("Processing", len(chunk), "rows...")

    chunk["Date"] = pd.to_datetime(chunk["Date"], errors="coerce")
    chunk = chunk.dropna(subset=["Date"])

    daily = pd.DataFrame({
        "state_code": chunk["State"],
        "facility_name": chunk["Facility Name"],
        "facility_id": pd.to_numeric(chunk["Facility ID"], errors="coerce"),
        "unit_id": chunk["Unit ID"].astype(str),
        "associated_stacks": chunk["Associated Stacks"],

        "date": chunk["Date"].dt.strftime("%Y-%m-%d"),
        "year": chunk["Date"].dt.year,
        "quarter": ((chunk["Date"].dt.month - 1) // 3) + 1,
        "month": chunk["Date"].dt.month,

        "operating_time_count": chunk["Operating Time Count"],
        "operating_time": chunk["Sum of the Operating Time"],
        "gross_load": chunk["Gross Load (MWh)"],
        "steam_load": chunk["Steam Load (1000 lb)"],
        "heat_input": chunk["Heat Input (mmBtu)"],

        "so2_mass": chunk["SO2 Mass (short tons)"],
        "so2_rate": chunk["SO2 Rate (lbs/mmBtu)"],

        "co2_mass": chunk["CO2 Mass (short tons)"],
        "co2_rate": chunk["CO2 Rate (short tons/mmBtu)"],

        "nox_mass": chunk["NOx Mass (short tons)"],
        "nox_rate": chunk["NOx Rate (lbs/mmBtu)"],

        "primary_fuel_type": chunk["Primary Fuel Type"],
        "secondary_fuel_type": chunk["Secondary Fuel Type"],
        "unit_type": chunk["Unit Type"],

        "so2_controls": chunk["SO2 Controls"],
        "nox_controls": chunk["NOx Controls"],
        "pm_controls": chunk["PM Controls"],
        "hg_controls": chunk["Hg Controls"],
        "program_code": chunk["Program Code"]
    })

    daily.to_sql(
        "daily_records",
        engine,
        if_exists="append",
        index=False,
        method="multi",
        chunksize=1000
    )

    total_imported = total_imported + len(daily)

    print("Imported", total_imported, "daily records so far.")

print()
print("Finished! Imported", total_imported, "daily records.")
