import os
from sqlalchemy.orm import sessionmaker

from models import TraciRecord, engine
from traci_data import read_traci_workbook


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKBOOK_PATH = os.path.join(BASE_DIR, "data", "traci_2_2.xlsx")


def main():
    print("Reading:", WORKBOOK_PATH)
    records = read_traci_workbook(WORKBOOK_PATH)
    print(f"Found {len(records):,} TRACI substance records.")

    session = sessionmaker(bind=engine)()
    try:
        session.query(TraciRecord).delete()
        session.bulk_insert_mappings(TraciRecord, records)
        session.commit()
        print(f"Successfully imported {len(records):,} TRACI records.")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
