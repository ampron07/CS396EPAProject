import os
import requests
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy.orm import sessionmaker
from models import engine, AnnualRecord

load_dotenv()

api_key = os.getenv("EPA_API_KEY")

url = "https://api.epa.gov/easey/emissions-mgmt/emissions/apportioned/annual"

params = {
    "api_key": api_key,
    "year": 2023,
    "page": 1,
    "perPage": 10
}

response = requests.get(url, params=params)

print("Status code:", response.status_code)

if response.ok:
    data = response.json()
    records = data["items"]

    df = pd.DataFrame(records)

    print(f"\nRetrieved {len(df)} EPA records.")

    Session = sessionmaker(bind=engine)
    session = Session()

    for _, row in df.iterrows():
        record = AnnualRecord(
            state_code=row.get("stateCode"),
            facility_name=row.get("facilityName"),
            facility_id=row.get("facilityId"),
            unit_id=row.get("unitId"),
            year=row.get("year"),
            operating_time=row.get("sumOpTime"),
            gross_load=row.get("grossLoad"),
            heat_input=row.get("heatInput"),
            so2_mass=row.get("so2Mass"),
            so2_rate=row.get("so2Rate"),
            co2_mass=row.get("co2Mass"),
            co2_rate=row.get("co2Rate"),
            nox_mass=row.get("noxMass"),
            nox_rate=row.get("noxRate"),
            primary_fuel=row.get("primaryFuelInfo"),
            unit_type=row.get("unitType")
        )

        session.add(record)

    session.commit()
    session.close()

    print("EPA records successfully saved to SQLite!")

else:
    print("EPA API request failed.")
    print(response.text)