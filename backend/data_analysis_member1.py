import pandas as pd

def calculate_diet_distribution(dataframe):
    # Counts how many recipes exist for each diet type
    dist = dataframe['diet_type'].value_counts()
    return {
        "labels": dist.index.tolist(),
        "values": dist.values.tolist()
    }

def calculate_average_nutrition(dataframe):
    # Calculates the average protein, carbs, and fat per diet type
    avg = dataframe.groupby('diet_type')[['protein', 'carbs', 'fat']].mean().round(2)
    return {
        "labels": avg.index.tolist(),
        "protein": avg['protein'].tolist(),
        "carbs": avg['carbs'].tolist(),
        "fat": avg['fat'].tolist()
    }

def calculate_summary_statistics(dataframe):
    # Basic summary of the whole dataset
    return {
        "total_records": int(len(dataframe)),
        "avg_protein_overall": round(dataframe['protein'].mean(), 2),
        "avg_carbs_overall": round(dataframe['carbs'].mean(), 2)
    }

def filter_by_diet(dataframe, diet_type):
    # Filtering Logic
    if not diet_type or diet_type.lower() == "all":
        return dataframe
    return dataframe[dataframe["diet_type"].str.lower() == diet_type.lower()]


# Bar Chart Data: Average protein content by diet
def prepare_bar_chart_data(dataframe):
    avg = dataframe.groupby('diet_type')['protein'].mean().round(2)
    return {
        "labels": avg.index.tolist(),
        "values": avg.values.tolist()
    }

# Pie Chart Data: Distribution of records by diet
def prepare_pie_chart_data(dataframe):
    dist = dataframe['diet_type'].value_counts()
    return {
        "labels": dist.index.tolist(),
        "values": dist.values.tolist()
    }

# Comparison Chart Data: Average protein, carbs, and fat
def prepare_comparison_chart_data(dataframe):
    avg = dataframe.groupby('diet_type')[['protein', 'carbs', 'fat']].mean().round(2)
    return {
        "labels": avg.index.tolist(),
        "protein": avg['protein'].tolist(),
        "carbs": avg['carbs'].tolist(),
        "fat": avg['fat'].tolist()
    }