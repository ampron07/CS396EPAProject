# CS396EPAProject# epaData — EPA Power Plant Emissions Data Management System

**CS 396 — Phase 1**  
**Team:** Luke Brown and Am Pron  
**Western Kentucky University**

## Project Overview

epaData is a web application that helps users search and manage power plant emissions data from the U.S. Environmental Protection Agency (EPA). Instead of opening and searching through large CSV files manually, users can import the data into a SQLite database and explore it through a web interface.

The application supports annual and daily emissions records, filtering, sorting, description-based searching, CSV uploads, and CSV downloads.

## Tools Used

- **Python** — main programming language
- **Flask** — web application and routes
- **SQLite** — stores emissions records
- **SQLAlchemy** — database models and queries
- **pandas** — reads and imports CSV data
- **HTML, CSS, and Jinja2** — web pages and result displays

## Requirements

- Python 3 with `pip` installed
- An internet connection to download the EPA data and install Python packages
- A web browser
- EPA CAMPD CSV files if you want to load the datasets used during development

## Setup Instructions

### 1. Download and open the project

Download or clone the repository, then open a terminal in the folder containing `run.py`.

### 2. Create a virtual environment (recommended)

On Windows (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

On macOS or Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install the required libraries

```bash
python -m pip install Flask SQLAlchemy pandas requests python-dotenv
```

**Note:** The `requirements.txt` in the current project ZIP is encoded as UTF-16. To install directly with `python -m pip install -r requirements.txt`, first save that file as UTF-8, or use the command above.

### 4. Get the EPA emissions datasets

The project's datasets come from the EPA **Clean Air Markets Program Data (CAMPD)** Custom Data Download tool:

https://campd.epa.gov/data/custom-data-download

Download annual unit-level emissions data for **2025** and daily unit-level emissions data for **2026** in CSV format, using the appropriate columns expected by the import scripts. Place both files in the same folder as `run.py` and rename them exactly:

- `CAMPD_2025.csv` — annual data
- `Daily Emissions 2026.csv` — daily data

These large CSV files are **not included** in the project ZIP. The source and column names must match what the import scripts expect; different export selections may require adjustments.

### 5. Import the data

From the project folder, run:

```bash
python scripts/import_campd.py
python scripts/import_daily_csv.py
```

The import scripts create the SQLite database (`epa_data.db`) and the `annual_records` and `daily_records` tables as needed. The scripts print import progress or record counts. **Warning:** Rerunning either import script removes the existing records in its respective table before importing the new file.

### 6. Start the application

```bash
python run.py
```

Open this address in your browser:

http://127.0.0.1:5000

To stop the local server, press **Ctrl+C** in the terminal.

## How to Use the Application

**Annual Data:** Search annual emissions by facility name, state, year, fuel type, and minimum CO2 emissions. Sort results or download the filtered records as a CSV.

**Daily Data:** Search daily emissions using the available filters, including date-related options. View and compare records or grouped totals.

**Description Search:** Type a short search description using recognized keywords, such as `coal Kentucky 2025 high CO2`. The application uses those keywords to fill in search conditions. This is keyword-based, not unrestricted natural-language understanding.

**Upload:** Open the Upload page, select whether the CSV contains annual or daily records, and choose a file. The application checks the file extension and required columns. Use caution with any option that replaces existing data.

**Pagination and Downloads:** Move between result pages and export filtered records using the download controls.

## Reproducing Sample Results

1. Import the EPA CSV files and run the application.
2. Open the Annual Data page.
3. Choose **Kentucky** as the state and **Coal** as the fuel type, if those options are present in the imported dataset.
4. Run the search and check that the displayed records match the filters.
5. Sort the results by CO2 emissions, then download the filtered CSV.
6. Open the downloaded file and compare its records with the search filters.
7. On the Daily Data page, try a year, month, or quarter filter and review the results.
8. Test uploading a small, correctly formatted CSV. For an invalid-file test, remove a required column and confirm that the application displays an error.

The exact record counts depend on the downloaded EPA datasets. No specific output counts are guaranteed by this README.

## Project Files

| File or folder | Purpose |
|---|---|
| `run.py` | Starts the Flask application |
| `app/routes.py` | Handles pages, searches, uploads, and downloads |
| `app/templates/` | HTML templates for the user interface |
| `app/static/style.css` | Styles the pages |
| `scripts/models.py` | Defines the database tables and connection |
| `scripts/import_campd.py` | Imports annual emissions CSV data |
| `scripts/import_daily_csv.py` | Imports daily emissions CSV data |
| `scripts/view_database.py` | Helps inspect stored records |
| `scripts/test_api.py` | Separate script used to test the EPA API |
| `phase1-ERD.html` | Proposed database design diagram |

## Data Source

U.S. Environmental Protection Agency (EPA), **Clean Air Markets Program Data (CAMPD)**: https://campd.epa.gov/

## Acknowledgments

Developed for CS 396 at Western Kentucky University. The project uses publicly available EPA emissions data and open-source Python libraries.
