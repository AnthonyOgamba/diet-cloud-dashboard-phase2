import pandas as pd
from data_cleaning import clean_dataset
from data_analysis import (
    calculate_diet_distribution, 
    calculate_average_nutrition, 
    calculate_summary_statistics, 
    filter_by_diet
)

# 1. Load and clean the data
df = pd.read_csv('cleaned_diets_dataset.csv')

# 2. Test Summary Stats
print("--- Summary Statistics ---")
print(calculate_summary_statistics(df))

# 3. Test Distribution
print("\n--- Diet Distribution ---")
print(calculate_diet_distribution(df))

# 4. Test Filtering (Example: Filter for 'keto')
print("\n--- Testing Filter (Keto) ---")
keto_df = filter_by_diet(df, 'keto')
print(f"Total Keto records: {len(keto_df)}")

# 5. Test Average Nutrition for the filtered data
if not keto_df.empty:
    print(calculate_average_nutrition(keto_df))