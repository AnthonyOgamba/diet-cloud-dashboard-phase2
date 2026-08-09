import io
import pandas as pd
import azure.functions as func

from data_processing import clean_dataset, generate_cache_data


def main(myblob: func.InputStream):
    print(f"Blob Trigger started for: {myblob.name}")

    # Only process All_Diets.csv
    if not myblob.name.endswith("All_Diets.csv"):
        print("Ignored file because it is not All_Diets.csv")
        return

    # Read CSV directly from Blob Storage
    blob_data = myblob.read()
    raw_df = pd.read_csv(io.BytesIO(blob_data))

    # Use Member 2 cleaning function
    cleaned_df, stats = clean_dataset(raw_df)

    print("Data cleaning completed")
    print(stats)

    # Use Member 2 calculation/cache function
    cached_results = generate_cache_data(cleaned_df)

    print("Visualization calculations completed")
    print("Generated cache keys:")

    for key in cached_results:
        print(key)