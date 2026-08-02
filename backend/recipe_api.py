import pandas as pd
import math

def get_paginated_recipes(cleaned_df, diet='all', q=None, page=1, page_size=10):
    """
    Applies diet and keyword filters to the dataset and structures the output
    to match the agreed-upon pagination JSON contract.
    """
    # Isolate the dataframe for filtering operations
    filtered_df = cleaned_df.copy()

    # Apply diet type filter, bypassing if default 'all' is provided
    if diet and diet.lower() != 'all':
        filtered_df = filtered_df[filtered_df['diet_type'].str.lower() == diet.lower()]
    
    # Apply case-insensitive keyword search against the recipe_name column
    if q:
        filtered_df = filtered_df[filtered_df['recipe_name'].str.contains(q, case=False, na=False)]
    
    total_items = len(filtered_df)
    
    # Calculate pagination boundaries
    total_pages = math.ceil(total_items / page_size) if total_items > 0 else 0
    
    # Enforce safe bounds for requested page numbers
    if page < 1:
        page = 1
    elif page > total_pages and total_pages > 0:
        page = total_pages
        
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    
    # Extract the subset of records for the requested page
    paginated_df = filtered_df.iloc[start_idx:end_idx]
    
    # Construct the JSON payload adhering to the required schema
    return {
        "items": paginated_df.to_dict(orient='records'),
        "pagination": {
            "page": page,
            "pageSize": page_size,
            "totalItems": total_items,
            "totalPages": total_pages
        }
    }