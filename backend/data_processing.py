import pandas as pd
import time
from datetime import datetime, timezone

def clean_dataset(dataframe):
    """
    Executes data cleaning operations on the raw dataset.
    Returns the cleaned dataframe alongside a dictionary of processing statistics.
    """
    start_time = time.time()
    initial_count = len(dataframe)

    # Remove duplicate records
    dataframe = dataframe.drop_duplicates()

    # Standardize column naming conventions
    dataframe.columns = [
        column.strip().lower().replace(" ", "_").replace("(", "").replace(")", "").replace("g", "")
        for column in dataframe.columns
    ]

    # Define critical nutritional columns required for visualizations
    cols_to_fix = ['protein', 'carbs', 'fat']
    
    # Remove records missing critical data prior to type conversion
    dataframe = dataframe.dropna(subset=cols_to_fix)
    
    # Coerce nutritional data types to numeric, resolving any string anomalies
    for col in cols_to_fix:
        dataframe[col] = pd.to_numeric(dataframe[col], errors='coerce')
    
    # Execute a final pass to remove any records that failed numeric conversion
    dataframe = dataframe.dropna(subset=cols_to_fix)

    final_count = len(dataframe)
    duration = time.time() - start_time

    # Construct processing statistics required by the system architecture
    processing_stats = {
        "processing_date": datetime.now(timezone.utc).isoformat(),
        "initial_records": initial_count,
        "final_records": final_count,
        "records_dropped": initial_count - final_count,
        "processing_duration_seconds": round(duration, 4)
    }

    return dataframe, processing_stats

def calculate_visualizations(df):
    """
    Computes aggregated metrics required for frontend visualizations.
    This prevents the frontend from performing heavy computations locally.
    """
    # Compute average macronutrients grouped by diet type (For UI Bar Chart)
    bar_chart_data = df.groupby('diet_type')[['protein', 'carbs', 'fat']].mean().to_dict(orient='index')
    
    # Compute recipe distribution counts (For UI Pie Chart)
    pie_chart_data = df['diet_type'].value_counts().to_dict()
    
    # Compute correlation matrix for macronutrients (For UI Heatmap)
    heatmap_data = df[['protein', 'carbs', 'fat']].corr().to_dict()
    
    # Generate scatter plot data. Capped at 1000 records to ensure UI rendering performance.
    scatter_sample = df if len(df) < 1000 else df.sample(1000, random_state=42)
    scatter_data = scatter_sample[['protein', 'carbs', 'diet_type']].to_dict(orient='records')
    
    return {
        "recordCount": len(df),
        "average_macros": df[['protein', 'carbs', 'fat']].mean().to_dict(),
        "barChart": bar_chart_data,
        "pieChart": pie_chart_data,
        "heatmap": heatmap_data,
        "scatterPlot": scatter_data
    }

def generate_cache_data(cleaned_df, version="v1"):
    """
    Structures the calculated data into the required cache dictionary format.
    Generates keys for the global dataset and individual diet categories.
    """
    caches = {}
    
    # Initialize baseline dataset status metadata
    caches["dataset:status"] = {
        "datasetVersion": version,
        "lastProcessed": datetime.now(timezone.utc).isoformat(),
        "recordCount": len(cleaned_df),
        "cacheAvailable": True
    }
    
    # Populate the global cache key
    caches["dashboard:all"] = calculate_visualizations(cleaned_df)
    
    # Populate specific cache keys for isolated diet types
    unique_diets = cleaned_df['diet_type'].unique()
    for diet in unique_diets:
        diet_df = cleaned_df[cleaned_df['diet_type'] == diet]
        caches[f"dashboard:{diet}"] = calculate_visualizations(diet_df)
        
    return caches

# --- Integration Simulation (Blob Trigger Entry Point) ---
# This block simulates how the Azure Function will invoke the methods 
# when a new CSV is uploaded to Blob Storage.

if __name__ == "__main__":
    try:
        # 1. Simulate loading the raw file from Blob Storage
        print("Initializing pipeline simulation...")
        raw_df = pd.read_csv("All_Diets_v1.csv")
        
        # 2. Execute the data cleaning pipeline
        cleaned_df, stats = clean_dataset(raw_df)
        print("\n--- Data Cleaning Complete ---")
        print(f"Processing Statistics: {stats}")
        
        # 3. Execute the calculation and caching function
        cached_results = generate_cache_data(cleaned_df, version="v1")
        
        print("\n--- Cache Payload Generated ---")
        print("The following keys are structured and ready for database insertion:")
        for key in cached_results.keys():
            print(f" - {key}")
            
        # Optional: Print a subset of the dashboard data to verify calculations
        # print(cached_results["dashboard:all"]["barChart"])
            
    except FileNotFoundError:
        print("System Error: 'All_Diets_v1.csv' not found. Please execute 'generate_test_datasets.py' first to provision the required files.")