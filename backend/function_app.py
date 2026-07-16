import io
import json
import logging
import os
import time

import azure.functions as func
import pandas as pd
from azure.storage.blob import BlobServiceClient

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