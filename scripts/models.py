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


class DailyRecord(Base):
    """One row per generating unit per day, from the CAMPD daily emissions CSV download."""
    __tablename__ = "daily_records"

    id = Column(Integer, primary_key=True)

    # Who and where
    state_code = Column(String, index=True)
    facility_name = Column(String)
    facility_id = Column(Integer, index=True)
    unit_id = Column(String, index=True)
    associated_stacks = Column(String)

    # When. The date is stored as text "YYYY-MM-DD" so SQLite's strftime() works on it.
    # year / quarter / month are pre-computed from the date to make grouping easy.
    date = Column(String, index=True)
    year = Column(Integer, index=True)
    quarter = Column(Integer, index=True)
    month = Column(Integer)

    # Operation
    operating_time_count = Column(Float)
    operating_time = Column(Float)
    gross_load = Column(Float)
    steam_load = Column(Float)
    heat_input = Column(Float)

    # Emissions
    so2_mass = Column(Float)
    so2_rate = Column(Float)
    co2_mass = Column(Float)
    co2_rate = Column(Float)
    nox_mass = Column(Float)
    nox_rate = Column(Float)

    # Unit details
    primary_fuel_type = Column(String)
    secondary_fuel_type = Column(String)
    unit_type = Column(String)
    so2_controls = Column(String)
    nox_controls = Column(String)
    pm_controls = Column(String)
    hg_controls = Column(String)
    program_code = Column(String)


# Create the SQLite database

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATABASE_PATH = os.path.join(BASE_DIR, "epa_data.db")

engine = create_engine(f"sqlite:///{DATABASE_PATH}")

# Create the tables
Base.metadata.create_all(engine)

print("Database created successfully!")