import pandas as pd


def generate_test_datasets(source_csv_path="All_Diets.csv"):
    """
    Generates two source-file versions for the Phase 3 Blob Trigger demo.

    V1 is the original baseline.
    V2 preserves the ORIGINAL All_Diets.csv schema while making controlled
    changes that demonstrate cache refresh, filtering, and keyword search.
    """
    try:
        df_base = pd.read_csv(source_csv_path)

        # ---------------------------------------------------------
        # Version 1: unchanged baseline
        # ---------------------------------------------------------
        df_v1 = df_base.copy()
        df_v1.to_csv("All_Diets_v1.csv", index=False)

        print(
            f"Successfully generated All_Diets_v1.csv "
            f"(Baseline: {len(df_v1)} records)"
        )

        # ---------------------------------------------------------
        # Version 2: controlled modifications
        # IMPORTANT: preserve the RAW source column names.
        # ---------------------------------------------------------
        df_v2 = df_base.copy()

        # Modification 1:
        # Change one nutritional value so calculated results change.
        df_v2.at[0, "Protein(g)"] = 999.99

        # Modification 2:
        # Change one diet classification.
        df_v2.at[1, "Diet_type"] = "vegan"

        # Modification 3:
        # Add one easily searchable recipe.
        test_record = pd.DataFrame([
            {
                "Diet_type": "keto",
                "Recipe_name": "Test Recipe - Cache Validation Update",
                "Cuisine_type": "american",
                "Protein(g)": 50.0,
                "Carbs(g)": 10.0,
                "Fat(g)": 30.0,
                "Extraction_day": "2026-08-01",
                "Extraction_time": "12:00:00",
            }
        ])

        df_v2 = pd.concat(
            [test_record, df_v2],
            ignore_index=True
        )

        df_v2.to_csv(
            "All_Diets_v2.csv",
            index=False
        )

        print(
            f"Successfully generated All_Diets_v2.csv "
            f"(Modified: {len(df_v2)} records)"
        )

        print("\nV2 modifications:")
        print("1. First recipe Protein(g) changed to 999.99")
        print("2. Second recipe Diet_type changed to vegan")
        print("3. Added 'Test Recipe - Cache Validation Update'")

    except FileNotFoundError:
        print(
            f"System Error: Cannot locate '{source_csv_path}'. "
            "Verify file path."
        )


if __name__ == "__main__":
    generate_test_datasets()