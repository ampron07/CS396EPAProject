from sqlalchemy.orm import sessionmaker
from models import engine, AnnualRecord

Session = sessionmaker(bind=engine)
session = Session()

records = session.query(AnnualRecord).all()

print(f"Total records in database: {len(records)}")

print("\nEPA Records:\n")

for record in records:
    print(
        f"Facility: {record.facility_name} | "
        f"State: {record.state_code} | "
        f"Unit: {record.unit_id} | "
        f"Year: {record.year} | "
        f"CO2: {record.co2_mass}"
    )

session.close()