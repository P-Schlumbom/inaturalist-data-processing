import pandas as pd

taxa = pd.read_csv("taxa.csv", delimiter='\t')

print(taxa.head())
print(taxa.columns)
print(len(taxa))
print(pd.value_counts(taxa['rank']))

import pandas as pd

ref_df = pd.read_csv("02_taxon_collected_data.csv")

chunk_size = 100_000  # adjust as needed
keep_cols = ['photo_uuid', 'taxon_id']  # example relevant columns
target_ids = list(ref_df['id']) #set(['123', '456', '789'])  # your target species IDs

filtered_rows = []

for chunk in pd.read_csv("photos.csv", usecols=keep_cols, chunksize=chunk_size):
    filtered_chunk = chunk[chunk['taxon_id'].isin(target_ids)]
    filtered_rows.append(filtered_chunk)

# Combine and save the filtered result
filtered_df = pd.concat(filtered_rows)
filtered_df.to_csv("photos_filtered.csv", index=False)
