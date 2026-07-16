import pandas as pd
from data_cleaning import clean_dataset

# Loading raw data
df = pd.read_csv('All_Diets.csv')

# Using the new cleaning function
df_clean = clean_dataset(df)

# Saving it
df_clean.to_csv('cleaned_diets_dataset.csv', index=False)
print("Cleaned dataset saved successfully!")