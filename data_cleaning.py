import pandas as pd

def clean_dataset(dataframe):
    # Remove duplicate rows
    dataframe = dataframe.drop_duplicates()

    # Clean column names (strip whitespace, make lowercase, replace spaces with underscores)
    dataframe.columns = [
        column.strip().lower().replace(" ", "_").replace("(", "").replace(")", "").replace("g", "")
        for column in dataframe.columns
    ]

    # Drop rows where critical nutritional data is missing
    dataframe = dataframe.dropna(subset=['protein', 'carbs', 'fat'])
    
    # Ensure nutritional values are treated as numbers
    cols_to_fix = ['protein', 'carbs', 'fat']
    for col in cols_to_fix:
        dataframe[col] = pd.to_numeric(dataframe[col], errors='coerce')
    
    # Final cleanup of any new errors created by conversion
    dataframe = dataframe.dropna(subset=cols_to_fix)

    return dataframe