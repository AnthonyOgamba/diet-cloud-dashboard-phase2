import io
import json
import logging
import os
import time

import azure.functions as func
import pandas as pd
from recipe_api import get_paginated_recipes
from azure.storage.blob import BlobServiceClient
from data_processing import clean_dataset, generate_cache_data

from data_analysis import (
    calculate_average_nutrition,
    calculate_diet_distribution,
    calculate_summary_statistics,
    filter_by_diet,
    prepare_bar_chart_data,
    prepare_comparison_chart_data,
    prepare_pie_chart_data,
)

app = func.FunctionApp()
def _json_default(value):
    """Convert pandas/numpy/datetime values into JSON-safe values."""
    if hasattr(value, "item"):
        return value.item()

    if hasattr(value, "isoformat"):
        return value.isoformat()

    return str(value)


@app.blob_trigger(
    arg_name="input_blob",
    path="datasets/All_Diets.csv",
    connection="AZURE_STORAGE_CONNECTION_STRING",
    source="EventGrid",
)
def AllDietsBlobTrigger(input_blob: func.InputStream) -> None:
    """
    Phase 3 processing pipeline.

    This function runs only when datasets/All_Diets.csv changes.
    It cleans the dataset once, calculates visualization results once,
    writes the cleaned CSV, and saves precomputed dashboard results.
    """
    logging.info(
        "PHASE3_TRIGGER_START | blob=%s | bytes=%s",
        input_blob.name,
        input_blob.length,
    )

    connection_string = os.environ["AZURE_STORAGE_CONNECTION_STRING"]
    container_name = os.getenv("BLOB_CONTAINER_NAME", "datasets")

    # ---------------------------------------------------------
    # 1. Read the newly uploaded raw dataset
    # ---------------------------------------------------------
    raw_bytes = input_blob.read()
    raw_dataframe = pd.read_csv(io.BytesIO(raw_bytes))

    logging.info(
        "PHASE3_RAW_DATA_LOADED | records=%s",
        len(raw_dataframe),
    )

    # ---------------------------------------------------------
    # 2. Clean the dataset ONCE
    # ---------------------------------------------------------
    cleaned_dataframe, processing_stats = clean_dataset(raw_dataframe)

    logging.info(
        "PHASE3_CLEANING_COMPLETE | initial=%s | final=%s | dropped=%s",
        processing_stats["initial_records"],
        processing_stats["final_records"],
        processing_stats["records_dropped"],
    )

    blob_service_client = BlobServiceClient.from_connection_string(
        connection_string
    )

    # Obtain the current source blob ETag.
    # The ETag changes whenever All_Diets.csv changes.
    source_blob_client = blob_service_client.get_blob_client(
        container=container_name,
        blob="All_Diets.csv",
    )

    source_properties = source_blob_client.get_blob_properties()

    dataset_version = str(source_properties.etag).strip('"')

    # ---------------------------------------------------------
    # 3. Calculate visualization results ONCE
    # ---------------------------------------------------------
    cache_payload = generate_cache_data(
        cleaned_dataframe,
        version=dataset_version,
    )

    cache_payload["processing_stats"] = processing_stats

    cache_payload["source"] = {
        "blob": "All_Diets.csv",
        "etag": dataset_version,
        "last_modified": source_properties.last_modified,
    }

    logging.info(
        "PHASE3_CALCULATIONS_COMPLETE | version=%s | cache_keys=%s",
        dataset_version,
        len(cache_payload),
    )

    # ---------------------------------------------------------
    # 4. Save cleaned dataset
    # ---------------------------------------------------------
    cleaned_csv = cleaned_dataframe.to_csv(
        index=False
    ).encode("utf-8")

    cleaned_blob_client = blob_service_client.get_blob_client(
        container=container_name,
        blob="cleaned_diets_dataset.csv",
    )

    cleaned_blob_client.upload_blob(
        cleaned_csv,
        overwrite=True,
    )

    logging.info(
        "PHASE3_CLEANED_DATA_SAVED | blob=cleaned_diets_dataset.csv"
    )

    # ---------------------------------------------------------
    # 5. Save precomputed dashboard cache
    # ---------------------------------------------------------
    cache_json = json.dumps(
        cache_payload,
        default=_json_default,
    )

    cache_blob_client = blob_service_client.get_blob_client(
        container=container_name,
        blob="dashboard_cache.json",
    )

    cache_blob_client.upload_blob(
        cache_json,
        overwrite=True,
    )

    logging.info(
        "PHASE3_CACHE_SAVED | blob=dashboard_cache.json | version=%s",
        dataset_version,
    )

    logging.info(
        "PHASE3_TRIGGER_COMPLETE | blob=%s",
        input_blob.name,
    )

@app.route(
    route="DietAnalysisFunction",
    auth_level=func.AuthLevel.ANONYMOUS,
    methods=["GET"],
)
def DietAnalysisFunction(req: func.HttpRequest) -> func.HttpResponse:
    """
    Phase 3 optimized dashboard endpoint.

    The HTTP request no longer cleans the CSV or recalculates
    visualization results. It reads the precomputed results created
    by AllDietsBlobTrigger from dashboard_cache.json.
    """
    start_time = time.time()

    try:
        connection_string = os.environ["AZURE_STORAGE_CONNECTION_STRING"]
        container_name = os.getenv("BLOB_CONTAINER_NAME", "datasets")

        blob_service_client = BlobServiceClient.from_connection_string(
            connection_string
        )

        # ---------------------------------------------------------
        # 1. Read PRECOMPUTED dashboard cache
        # ---------------------------------------------------------
        cache_blob_client = blob_service_client.get_blob_client(
            container=container_name,
            blob="dashboard_cache.json",
        )

        cache_bytes = cache_blob_client.download_blob().readall()
        cache_data = json.loads(cache_bytes.decode("utf-8"))

        # ---------------------------------------------------------
        # 2. Determine requested diet
        # ---------------------------------------------------------
        requested_diet = req.params.get("diet", "all").strip().lower()

        if requested_diet == "all":
            cache_key = "dashboard:all"
        else:
            cache_key = next(
                (
                    key
                    for key in cache_data.keys()
                    if key.startswith("dashboard:")
                    and key.split(":", 1)[1].lower() == requested_diet
                ),
                None,
            )

        if not cache_key or cache_key not in cache_data:
            available_diets = sorted(
                key.split(":", 1)[1]
                for key in cache_data.keys()
                if key.startswith("dashboard:")
            )

            return func.HttpResponse(
                body=json.dumps(
                    {
                        "error": "Unsupported diet type.",
                        "requested": requested_diet,
                        "available": available_diets,
                    }
                ),
                status_code=400,
                mimetype="application/json",
            )

        # ---------------------------------------------------------
        # 3. Get precomputed result
        # ---------------------------------------------------------
        cached_dashboard = cache_data[cache_key]

        bar_data = cached_dashboard.get("barChart", {})
        pie_data = cached_dashboard.get("pieChart", {})
        average_macros = cached_dashboard.get("average_macros", {})
        dataset_status = cache_data.get("dataset:status", {})

        labels = list(bar_data.keys())

        protein_values = [
            float(bar_data[label].get("protein", 0))
            for label in labels
        ]

        carbs_values = [
            float(bar_data[label].get("carbs", 0))
            for label in labels
        ]

        fat_values = [
            float(bar_data[label].get("fat", 0))
            for label in labels
        ]

        # ---------------------------------------------------------
        # 4. Preserve existing frontend response structure
        # ---------------------------------------------------------
        response_data = {
            "filter": requested_diet,

            "summary": {
                "total_records": cached_dashboard.get(
                    "recordCount",
                    0,
                ),
                "avg_protein_overall": average_macros.get(
                    "protein",
                    0,
                ),
                "avg_carbs_overall": average_macros.get(
                    "carbs",
                    0,
                ),
                "avg_fat_overall": average_macros.get(
                    "fat",
                    0,
                ),
            },

            "diet_distribution": pie_data,

            "average_nutrition": {
                "labels": labels,
                "protein": protein_values,
                "carbs": carbs_values,
                "fat": fat_values,
            },

            "charts": {
                "bar_chart": {
                    "labels": labels,
                    "values": protein_values,
                },

                "pie_chart": {
                    "labels": list(pie_data.keys()),
                    "values": list(pie_data.values()),
                },

                "comparison_chart": {
                    "labels": labels,
                    "protein": protein_values,
                    "carbs": carbs_values,
                    "fat": fat_values,
                },
            },

            "metadata": {
                "container": container_name,
                "blob": "dashboard_cache.json",
                "execution_time_seconds": round(
                    time.time() - start_time,
                    3,
                ),
                "source": "precomputed-cache",
                "cache_key": cache_key,
                "dataset_version": dataset_status.get(
                    "datasetVersion"
                ),
                "last_processed": dataset_status.get(
                    "lastProcessed"
                ),
            },
        }

        logging.info(
            "PHASE3_CACHE_HIT | key=%s | version=%s",
            cache_key,
            dataset_status.get("datasetVersion"),
        )

        return func.HttpResponse(
            body=json.dumps(
                response_data,
                default=_json_default,
            ),
            status_code=200,
            mimetype="application/json",
        )

    except KeyError:
        return func.HttpResponse(
            body=json.dumps(
                {
                    "error": (
                        "AZURE_STORAGE_CONNECTION_STRING is missing "
                        "from application settings."
                    )
                }
            ),
            status_code=500,
            mimetype="application/json",
        )

    except Exception as error:
        logging.exception(
            "Cached diet analysis request failed."
        )

        return func.HttpResponse(
            body=json.dumps(
                {
                    "error": str(error)
                }
            ),
            status_code=500,
            mimetype="application/json",
        )

@app.route(
    route="recipes",
    auth_level=func.AuthLevel.ANONYMOUS,
    methods=["GET"],
)
def RecipesFunction(req: func.HttpRequest) -> func.HttpResponse:
    """
    Phase 3 recipe interaction API.

    Supports:
    - Diet type filtering
    - Keyword searching
    - Pagination

    Examples:
    /api/recipes?diet=vegan
    /api/recipes?q=chicken
    /api/recipes?diet=keto&q=chicken&page=1&pageSize=10
    """

    try:
        connection_string = os.environ["AZURE_STORAGE_CONNECTION_STRING"]
        container_name = os.getenv("BLOB_CONTAINER_NAME", "datasets")

        blob_service_client = BlobServiceClient.from_connection_string(
            connection_string
        )

        # Use the cleaned dataset generated by AllDietsBlobTrigger.
        cleaned_blob_client = blob_service_client.get_blob_client(
            container=container_name,
            blob="cleaned_diets_dataset.csv",
        )

        cleaned_bytes = cleaned_blob_client.download_blob().readall()

        cleaned_dataframe = pd.read_csv(
            io.BytesIO(cleaned_bytes)
        )

        # ---------------------------------------------------------
        # Read query parameters
        # ---------------------------------------------------------
        diet = req.params.get("diet", "all").strip()

        keyword = req.params.get("q")

        if keyword:
            keyword = keyword.strip()

        try:
            page = int(req.params.get("page", "1"))
        except ValueError:
            page = 1

        try:
            page_size = int(req.params.get("pageSize", "10"))
        except ValueError:
            page_size = 10

        # Safe pagination limits
        page = max(page, 1)
        page_size = max(1, min(page_size, 100))

        # ---------------------------------------------------------
        # Use Member 2's existing filtering/search/pagination logic
        # ---------------------------------------------------------
        result = get_paginated_recipes(
            cleaned_df=cleaned_dataframe,
            diet=diet,
            q=keyword,
            page=page,
            page_size=page_size,
        )

        result["filters"] = {
            "diet": diet,
            "keyword": keyword or "",
        }

        result["metadata"] = {
            "source": "cleaned_diets_dataset.csv",
            "container": container_name,
        }

        logging.info(
            "PHASE3_RECIPE_QUERY | diet=%s | q=%s | page=%s | pageSize=%s | total=%s",
            diet,
            keyword,
            page,
            page_size,
            result["pagination"]["totalItems"],
        )

        return func.HttpResponse(
            body=json.dumps(
                result,
                default=_json_default,
            ),
            status_code=200,
            mimetype="application/json",
        )

    except KeyError:
        return func.HttpResponse(
            body=json.dumps(
                {
                    "error": (
                        "AZURE_STORAGE_CONNECTION_STRING is missing "
                        "from application settings."
                    )
                }
            ),
            status_code=500,
            mimetype="application/json",
        )

    except Exception as error:
        logging.exception(
            "Recipe interaction request failed."
        )

        return func.HttpResponse(
            body=json.dumps(
                {
                    "error": str(error)
                }
            ),
            status_code=500,
            mimetype="application/json",
        )