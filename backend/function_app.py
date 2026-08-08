import io
import json
import logging
import os
import time

import azure.functions as func
import pandas as pd
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
    start_time = time.time()

    try:
        connection_string = os.environ["AZURE_STORAGE_CONNECTION_STRING"]
        container_name = os.getenv("BLOB_CONTAINER_NAME", "datasets")
        blob_name = os.getenv("BLOB_FILE_NAME", "cleaned_diets_dataset.csv")

        blob_service_client = BlobServiceClient.from_connection_string(
            connection_string
        )
        blob_client = blob_service_client.get_blob_client(
            container=container_name,
            blob=blob_name,
        )

        blob_data = blob_client.download_blob().readall()
        dataframe = pd.read_csv(io.BytesIO(blob_data))

        diet_type = req.params.get("diet", "all")
        filtered_dataframe = filter_by_diet(dataframe, diet_type)

        response_data = {
            "filter": diet_type,
            "summary": calculate_summary_statistics(filtered_dataframe),
            "diet_distribution": calculate_diet_distribution(filtered_dataframe),
            "average_nutrition": calculate_average_nutrition(filtered_dataframe),
            "charts": {
                "bar_chart": prepare_bar_chart_data(filtered_dataframe),
                "pie_chart": prepare_pie_chart_data(filtered_dataframe),
                "comparison_chart": prepare_comparison_chart_data(
                    filtered_dataframe
                ),
            },
            "metadata": {
                "container": container_name,
                "blob": blob_name,
                "execution_time_seconds": round(time.time() - start_time, 3),
            },
        }

        return func.HttpResponse(
            body=json.dumps(response_data),
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
        logging.exception("Diet analysis function failed.")

        return func.HttpResponse(
            body=json.dumps({"error": str(error)}),
            status_code=500,
            mimetype="application/json",
        )