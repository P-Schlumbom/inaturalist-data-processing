import requests
import json

# Define the endpoint and parameters
url = "https://api.inaturalist.org/v1/observations/species_counts"
params = {
    "photos": "true",
    "sounds": "false",
    "taxon_is_active": "true",
    "place_id": 6803,  # New Zealand
    "hrank": "species",
    "quality_grade": "research",
    "include_ancestors": "false",
    "per_page": 500,
    "page": 1
}

# Send the request
response = requests.get(url, params=params)

# Check if the request was successful
if response.status_code == 200:
    data = response.json()

    # Save the JSON to a file
    with open("data/nz_species_page_1.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("Saved data to nz_species_page_1.json")
else:
    print(f"Failed to retrieve data: {response.status_code}")
