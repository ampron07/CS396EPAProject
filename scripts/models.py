import os
from sqlalchemy import create_engine, Column, Integer, String, Float
from sqlalchemy.orm import declarative_base


Base = declarative_base()


class AnnualRecord(Base):
    __tablename__ = "annual_records"

    id = Column(Integer, primary_key=True)

    state_code = Column(String)
    facility_name = Column(String)
    facility_id = Column(Integer)
    unit_id = Column(String)
    year = Column(Integer)

    operating_time = Column(Float)
    gross_load = Column(Float)
    heat_input = Column(Float)

    so2_mass = Column(Float)
    so2_rate = Column(Float)

    co2_mass = Column(Float)
    co2_rate = Column(Float)

    nox_mass = Column(Float)
    nox_rate = Column(Float)

    primary_fuel = Column(String)
    unit_type = Column(String)


# Create the SQLite database

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATABASE_PATH = os.path.join(BASE_DIR, "epa_data.db")

engine = create_engine(f"sqlite:///{DATABASE_PATH}")

# Create the tables
Base.metadata.create_all(engine)

print("Database created successfully!")