import os
import json
import math
import time
from datetime import timedelta
import pandas as pd
import requests
from time import sleep
from retrying import retry
from requests.exceptions import RequestException
from os import mkdir
from os.path import exists
from tqdm import tqdm

min_sleep = 0.2
current_sleep = min_sleep
image_sizes = ["square", "thumb", "small", "medium", "large", "original"]

def get_query(taxon_id, place_id=None, page=None):
    set_place_str = f"&place_id={str(place_id)}" if place_id else ''
    set_page_nbr = f"&page={str(page)}" if page else ''
    return f"https://api.inaturalist.org/v1/observations?identified=true&photos=true&license=cc-by%2Ccc-by-sa%2Ccc0&photo_license=cc-by%2Ccc-by-sa%2Ccc0{set_place_str}&taxon_id={str(taxon_id)}&quality_grade=research{set_page_nbr}&per_page=200&order=desc&order_by=created_at"

@retry(stop_max_attempt_number=10, wait_fixed=2000, retry_on_exception=lambda ex: isinstance(ex, RequestException))
def download_image(url, tgt_path):
    global current_sleep, min_sleep
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            current_sleep = max(min_sleep, current_sleep * 0.5)
            with open(tgt_path, 'wb') as file:
                file.write(response.content)
        else:
            if response.status_code == 429:
                print("Too many requests error!", flush=True)
                current_sleep = min(current_sleep * 2, 60)
                if current_sleep > 10:
                    print(f"current_sleep set to {current_sleep}", flush=True)
                raise RequestException("Too Many Requests")
            else:
                raise RequestException(f"HTTP Error {response.status_code}")
    except Exception:
        raise RequestException()

def extract_images_from_response(data, tgt_path, page=0, species_id=None, get_all_images=False, image_size='medium'):
    """
    Retrieve images for each observation. If 'get_all_images' is True, retrieves all images under the observation.
    :param data:
    :param tgt_path:
    :param page:
    :param get_all_images:
    :param image_size:
    :return:
    """
    species_id_prefix = f"{str(species_id)}_" if species_id else ""
    if 'results' not in data.keys():
        print(f"page {page}: No result retrieved!", flush=True)
        return
    #for i, obs in enumerate(data['results'][:3]):  # FOR TESTING ONLY ---------------
    for i, obs in enumerate(tqdm(data['results'], desc=f"page {page} results:")):
        for j, photo in enumerate(obs.get('photos', [])):
            url = photo['url']
            image_name = url.split('/')[-1]
            image_format = image_name.split('.')[-1]
            url_path = '/'.join(url.split('/')[:-1])
            orig_url = f"{url_path}/{image_size}.{image_format}"
            im_id = f"{species_id_prefix}{page}-{i}-{j}"
            #print(f"{i}, {j}: downloading image...", flush=True)
            download_image(orig_url, f"{tgt_path}/{im_id}.{image_format}")
            sleep(current_sleep)
            if not get_all_images:
                break

def save_checkpoint(data_path, checkpoint_path, index, page):
    os.makedirs(data_path, exist_ok=True)
    with open(checkpoint_path, 'w') as f:
        json.dump({'species_index': index, 'current_page': page}, f)

def load_checkpoint(checkpoint_path):
    if exists(checkpoint_path):
        with open(checkpoint_path, 'r') as f:
            return json.load(f)
    return None

def main(data_tgt, species_data_src, place_id=None, image_size='medium', force_restart=False):
    checkpoint_path = os.path.join(data_tgt, "checkpoint.json")

    species_data = pd.read_csv(species_data_src)
    #species_data = species_data[:2]  # FOR TESTING ONLY------------------------------
    taxon_ids = species_data['id'].tolist()
    taxon_species_dict = dict(zip(taxon_ids, species_data['name']))
    print(f"Found {len(taxon_ids)} species to download...", flush=True)

    os.makedirs(data_tgt, exist_ok=True)

    # Create all directories up front
    for species_name in taxon_species_dict.values():
        species_path = os.path.join(data_tgt, species_name)
        os.makedirs(species_path, exist_ok=True)

    start_index, start_page = 0, 1
    if not force_restart:
        checkpoint = load_checkpoint(checkpoint_path)
        if checkpoint:
            start_index = checkpoint.get('species_index', 0)
            start_page = checkpoint.get('current_page', 1)
            print(f"Resuming from checkpoint: species index {start_index}, page {start_page}", flush=True)

    total_elapsed = 0  # Track total time across taxons
    taxons_processed = 0
    for idx, taxon_id in enumerate(taxon_ids[start_index:], start=start_index):
        species_name = taxon_species_dict[taxon_id]
        im_data_path = os.path.join(data_tgt, species_name)

        start_time = time.time()  # Start timing

        query = get_query(taxon_id, place_id)
        response = requests.get(query)
        data = response.json()
        n_obs = data.get('total_results', 0)
        n_pages = (n_obs // 200) + 1
        #n_pages = 1  # FOR TESTING ONLY ------------------

        print(f"Collecting images for {species_name} (ID {taxon_id}) - {n_obs} observations, {n_pages} pages", flush=True)
        get_all_images = True

        # Resume from correct page
        for page in tqdm(range(start_page, n_pages + 1), desc=f"{species_name} ({idx+1}/{len(taxon_ids[start_index:])})"):
            print()
            #print("getting query...", flush=True)
            query = get_query(taxon_id, place_id, page=page)
            #print("getting response...", flush=True)
            response = requests.get(query)
            data = response.json()
            #print("extracting images...", flush=True)
            extract_images_from_response(data, im_data_path, page=page, species_id=taxon_id, get_all_images=get_all_images, image_size=image_size)
            save_checkpoint(data_tgt, checkpoint_path, idx, page + 1)  # Save after each page

        # End timing
        elapsed = time.time() - start_time
        total_elapsed += elapsed
        taxons_processed += 1
        average_time = total_elapsed / taxons_processed
        remaining_taxons = len(taxon_ids) - (idx + 1)
        eta = timedelta(seconds=int(average_time * remaining_taxons))

        print(f"Finished {species_name}: took {timedelta(seconds=int(elapsed))}, "
              f"average per taxon: {timedelta(seconds=int(average_time))}, "
              f"ETA for remaining {remaining_taxons} taxons: {eta}", flush=True)

        start_page = 1  # Reset for next species

    print("All downloads completed.", flush=True)

if __name__ == "__main__":
    species_data_src = "data/02_taxon_collected_data.csv"
    dataset_tgt = "../20250611_medium_inaturalist_data"  #"data/species-test"

    place_id = 6803  # New Zealand
    image_size = 'medium'
    force_restart = False  # Set to True to ignore checkpoint
    main(dataset_tgt, species_data_src, place_id, image_size=image_size, force_restart=force_restart)

