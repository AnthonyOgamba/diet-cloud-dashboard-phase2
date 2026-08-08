import pandas as pd

def generate_test_datasets(source_csv_path="All_Diets.csv"):
    """
    Generates v1 (baseline) and v2 (modified) CSV files. 
    v2 includes specific data anomalies to demonstrate dynamic cache updates.
    """
    try:
        df_base = pd.read_csv(source_csv_path)
        
        # Output the unaltered baseline dataset
        df_v1 = df_base.copy()
        df_v1.to_csv("All_Diets_v1.csv", index=False)
        print("Successfully generated All_Diets_v1.csv (Baseline)")
        
        # Initialize the modified dataset
        df_v2 = df_base.copy()
        
        # Modification 1: Inject a statistical outlier to alter visual charts
        df_v2.at[0, 'protein'] = 999.99 
        
        # Modification 2: Reclassify a diet type to test filtering logic
        df_v2.at[1, 'diet_type'] = 'vegan'
        
        # Modification 3: Insert a newly identifiable record to test pagination/search
        test_record = pd.DataFrame([{
            'diet_type': 'keto',
            'recipe_name': 'Test Recipe - Cache Validation Update',
            'cuisine_type': 'american',
            'protein': 50.0,
            'carbs': 10.0,
            'fat': 30.0,
            'extraction_day': '2026-08-01',
            'extraction_time': '12:00:00'
        }])
        
        df_v2 = pd.concat([test_record, df_v2], ignore_index=True)
        
        # Output the modified dataset
        df_v2.to_csv("All_Diets_v2.csv", index=False)
        print("Successfully generated All_Diets_v2.csv (Modified)")

    except FileNotFoundError:
        print(f"System Error: Cannot locate '{source_csv_path}'. Verify file path.")

if __name__ == "__main__":
    generate_test_datasets()