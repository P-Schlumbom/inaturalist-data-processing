import math
import pandas as pd
import requests
from time import sleep
import re
from retrying import retry
from requests.exceptions import RequestException
from os import mkdir
from os.path import exists
from tqdm import tqdm

min_sleep = 0.2
current_sleep = min_sleep
image_sizes = [
    "square",  # 75px
    "thumb",  # 100px
    "small",  # 240px
    "medium",  # 500px
    "large",  # 1024px
    "original" # 2048px
]

data_path = "data"


def get_query(taxon_id, place_id=None, page=None):
    set_place_str = f"&place_id={str(place_id)}"  # additional string to restrict image sources to location ID
    set_page_nbr = f"&page={str(page)}"
    return f"https://api.inaturalist.org/v1/observations?identified=true&photos=true&license=cc-by%2Ccc-by-sa%2Ccc0&photo_license=cc-by%2Ccc-by-sa%2Ccc0{set_place_str if place_id is not None else ''}&taxon_id={str(taxon_id)}&quality_grade=research{set_page_nbr if page is not None else ''}&per_page=200&order=desc&order_by=created_at"


@retry(
    stop_max_attempt_number=10,
    wait_fixed=2000,
    retry_on_exception=lambda ex: isinstance(ex, RequestException),
)
def download_image(url, tgt_path):
    global current_sleep, min_sleep
    try:
        response = requests.get(url)
        if response.status_code == 200:
            current_sleep = max(min_sleep, current_sleep * 0.5)
            with open(tgt_path, 'wb') as file:
                file.write(response.content)
        else:
            if response.status_code == 429:
                print("Too many requests error!")
                current_sleep *= 2
                raise RequestException("Too Many Requests")
            elif response.status_code != 200:
                raise RequestException(f"HTTP Error {response.status_code}")
    except Exception as e:
        raise RequestException()


def extract_images_from_response(data, tgt_path, page=0, get_all_images=False, image_size='medium'):
    """
    Retrieve images for each observation. If 'get_all_images' is True, retrieves all images under the observation.
    :param data:
    :param tgt_path:
    :param page:
    :param get_all_images:
    :param image_size:
    :return:
    """
    if 'results' not in data.keys():
        print(f"page {page}: No result retrieved!")
        return
    num_results = len(data['results'])
    for i in range(num_results):
        n_photos = len(data['results'][i]['photos'])
        for j in range(n_photos):
            url = data['results'][i]['photos'][j]['url']
            image_name = url.split('/')[-1]
            image_format = image_name.split('.')[-1]
            url_path = '/'.join(url.split('/')[:-1])
            orig_url = f"{url_path}/{image_size}.{image_format}"

            im_id = f"{page}-{i}-{j}"
            download_image(orig_url, f"{tgt_path}/{im_id}.{image_format}")
            sleep(current_sleep)
            if not get_all_images:
                break


def main(species_data_src, place_id=None, image_size='medium'):
    species_data = pd.read_csv(species_data_src)
    taxon_ids = species_data['id']

    # Creating a dictionary where 'taxon_key' is the key and 'species_name' is the value
    taxon_species_dict = dict(zip(taxon_ids, species_data['name']))
    print(f"Found {len(taxon_species_dict)} species to download...")

    params = {'format': 'json'}

    for taxon_id in taxon_ids:
        #base_query = f"https://api.inaturalist.org/v1/observations?identified=true&photos=true&taxon_id={str(taxon_id)}&quality_grade=research&per_page=200&order=desc&order_by=created_at"
        base_query = get_query(taxon_id, place_id)
        response = requests.get(base_query, params=params)
        data = response.json()
        n_obs = data['total_results']
        im_data_path = f"{data_path}/{taxon_species_dict[taxon_id]}"
        if not exists(im_data_path):
            mkdir(im_data_path)
        get_all_images = True  # Retrieve all images for each observation

        n_pages = (n_obs // 200) + 1

        print(f"Collecting images for {taxon_species_dict[taxon_id]}...")
        extract_images_from_response(data, im_data_path, 1, get_all_images=get_all_images, image_size=image_size)
        for p in tqdm(range(2, n_pages+1)):
            query = get_query(taxon_id, place_id, page=p)
            response = requests.get(query, params=params)
            data = response.json()
            extract_images_from_response(data, im_data_path, page=p, get_all_images=get_all_images, image_size=image_size)
    print("Done!")


if __name__ == "__main__":
    species_data_src = "data/02_taxon_collected_data.csv"
    place_id = 6803  # New Zealand place ID
    image_size = 'medium'
    main(species_data_src, place_id, image_size=image_size)

