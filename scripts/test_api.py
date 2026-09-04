import os
import requests
from dotenv import load_dotenv

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

    print("EPA API connection successful!")
    print("Number of records returned:", len(data))

    print("\nEPA response:")
    print(data)
else:
    print("EPA API request failed.")
    print(response.text)