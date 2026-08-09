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

from data_processing import clean_dataset, generate_cache_data

from auth_service import (
    create_user,
    find_user_by_email,
    verify_password,
    create_token,
    verify_token,
)


app = func.FunctionApp()


# ---------------------------------------------------------
# Existing HTTP Dashboard Function
# ---------------------------------------------------------

@app.route(
    route="DietAnalysisFunction",
    auth_level=func.AuthLevel.ANONYMOUS,
    methods=["GET"],
)
def DietAnalysisFunction(req: func.HttpRequest) -> func.HttpResponse:
    start_time = time.time()

    try:
        connection_string = os.environ[
            "AZURE_STORAGE_CONNECTION_STRING"
        ]

        container_name = os.getenv(
            "BLOB_CONTAINER_NAME",
            "dataset"
        )

        blob_name = os.getenv(
            "BLOB_FILE_NAME",
            "cleaned_diets_dataset.csv"
        )

        blob_service_client = (
            BlobServiceClient.from_connection_string(
                connection_string
            )
        )

        blob_client = blob_service_client.get_blob_client(
            container=container_name,
            blob=blob_name,
        )

        blob_data = blob_client.download_blob().readall()

        dataframe = pd.read_csv(
            io.BytesIO(blob_data)
        )

        diet_type = req.params.get(
            "diet",
            "all"
        )

        filtered_dataframe = filter_by_diet(
            dataframe,
            diet_type
        )

        response_data = {
            "filter": diet_type,
            "summary": calculate_summary_statistics(
                filtered_dataframe
            ),
            "diet_distribution": calculate_diet_distribution(
                filtered_dataframe
            ),
            "average_nutrition": calculate_average_nutrition(
                filtered_dataframe
            ),
            "charts": {
                "bar_chart": prepare_bar_chart_data(
                    filtered_dataframe
                ),
                "pie_chart": prepare_pie_chart_data(
                    filtered_dataframe
                ),
                "comparison_chart": prepare_comparison_chart_data(
                    filtered_dataframe
                ),
            },
            "metadata": {
                "container": container_name,
                "blob": blob_name,
                "execution_time_seconds": round(
                    time.time() - start_time,
                    3
                ),
            },
        }

        return func.HttpResponse(
            body=json.dumps(response_data),
            status_code=200,
            mimetype="application/json",
        )

    except KeyError:
        return func.HttpResponse(
            body=json.dumps({
                "error":
                "AZURE_STORAGE_CONNECTION_STRING "
                "is missing from application settings."
            }),
            status_code=500,
            mimetype="application/json",
        )

    except Exception as error:
        logging.exception(
            "Diet analysis function failed."
        )

        return func.HttpResponse(
            body=json.dumps({
                "error": str(error)
            }),
            status_code=500,
            mimetype="application/json",
        )


# ---------------------------------------------------------
#  Blob Trigger
# ---------------------------------------------------------

@app.blob_trigger(
    arg_name="myblob",
    path="dataset/All_Diets.csv",
    connection="AZURE_STORAGE_CONNECTION_STRING",
    source=func.BlobSource.EVENT_GRID,
)
def DietBlobTrigger(myblob: func.InputStream):
    start_time = time.time()

    try:
        logging.info(
            f"Blob Trigger started for: {myblob.name}"
        )

        raw_data = myblob.read()

        raw_df = pd.read_csv(
            io.BytesIO(raw_data)
        )

        cleaned_df, stats = clean_dataset(
            raw_df
        )

        logging.info(
            f"Cleaning completed. "
            f"Initial records: {stats['initial_records']}, "
            f"Final records: {stats['final_records']}"
        )

        cache_results = generate_cache_data(
            cleaned_df
        )

        logging.info(
            f"Visualization calculations completed. "
            f"Cache keys: {list(cache_results.keys())}"
        )

        connection_string = os.environ[
            "AZURE_STORAGE_CONNECTION_STRING"
        ]

        blob_service_client = (
            BlobServiceClient.from_connection_string(
                connection_string
            )
        )

        cleaned_blob_client = (
            blob_service_client.get_blob_client(
                container="dataset",
                blob="cleaned_diets_dataset.csv",
            )
        )

        cleaned_csv = cleaned_df.to_csv(
            index=False
        )

        cleaned_blob_client.upload_blob(
            cleaned_csv,
            overwrite=True,
        )

        logging.info(
            "cleaned_diets_dataset.csv "
            "uploaded successfully."
        )

        logging.info(
            f"Blob processing completed in "
            f"{round(time.time() - start_time, 3)} seconds."
        )

    except Exception:
        logging.exception(
            "Blob Trigger processing failed."
        )
        raise


# ---------------------------------------------------------
#  User Registration
# ---------------------------------------------------------

@app.route(
    route="auth/register",
    auth_level=func.AuthLevel.ANONYMOUS,
    methods=["POST"],
)
def register_user(req: func.HttpRequest) -> func.HttpResponse:
    try:
        data = req.get_json()

        name = data.get("name", "").strip()
        email = data.get("email", "").strip()
        password = data.get("password", "")

        if not name or not email or not password:
            return func.HttpResponse(
                json.dumps({
                    "error":
                    "Name, email and password are required."
                }),
                status_code=400,
                mimetype="application/json",
            )

        user = create_user(
            name,
            email,
            password
        )

        return func.HttpResponse(
            json.dumps({
                "message":
                "User registered successfully.",
                "user": user
            }),
            status_code=201,
            mimetype="application/json",
        )

    except ValueError as error:
        return func.HttpResponse(
            json.dumps({
                "error": str(error)
            }),
            status_code=400,
            mimetype="application/json",
        )

    except Exception as error:
        logging.exception(
            "Registration failed."
        )

        return func.HttpResponse(
            json.dumps({
                "error": str(error)
            }),
            status_code=500,
            mimetype="application/json",
        )


# ---------------------------------------------------------
#  User Login
# ---------------------------------------------------------

@app.route(
    route="auth/login",
    auth_level=func.AuthLevel.ANONYMOUS,
    methods=["POST"],
)
def login_user(req: func.HttpRequest) -> func.HttpResponse:
    try:
        data = req.get_json()

        email = data.get(
            "email",
            ""
        ).strip().lower()

        password = data.get(
            "password",
            ""
        )

        if not email or not password:
            return func.HttpResponse(
                json.dumps({
                    "error":
                    "Email and password are required."
                }),
                status_code=400,
                mimetype="application/json",
            )

        user = find_user_by_email(
            email
        )

        if not user or not verify_password(
            password,
            user["passwordHash"]
        ):
            return func.HttpResponse(
                json.dumps({
                    "error":
                    "Invalid email or password."
                }),
                status_code=401,
                mimetype="application/json",
            )

        token = create_token(
            user
        )

        return func.HttpResponse(
            json.dumps({
                "message":
                "Login successful.",
                "token":
                token,
                "user": {
                    "id": user["id"],
                    "name": user["name"],
                    "email": user["email"]
                }
            }),
            status_code=200,
            mimetype="application/json",
        )

    except Exception as error:
        logging.exception(
            "Login failed."
        )

        return func.HttpResponse(
            json.dumps({
                "error": str(error)
            }),
            status_code=500,
            mimetype="application/json",
        )


# ---------------------------------------------------------
#  Current User
# ---------------------------------------------------------

@app.route(
    route="auth/me",
    auth_level=func.AuthLevel.ANONYMOUS,
    methods=["GET"],
)
def get_current_user(req: func.HttpRequest) -> func.HttpResponse:
    try:
        auth_header = req.headers.get(
            "Authorization"
        )

        if not auth_header:
            return func.HttpResponse(
                json.dumps({
                    "error":
                    "Authorization token is required."
                }),
                status_code=401,
                mimetype="application/json",
            )

        if not auth_header.startswith("Bearer "):
            return func.HttpResponse(
                json.dumps({
                    "error":
                    "Invalid authorization format."
                }),
                status_code=401,
                mimetype="application/json",
            )

        token = auth_header.replace(
            "Bearer ",
            "",
            1
        )

        payload = verify_token(
            token
        )

        if not payload:
            return func.HttpResponse(
                json.dumps({
                    "error":
                    "Invalid or expired token."
                }),
                status_code=401,
                mimetype="application/json",
            )

        return func.HttpResponse(
            json.dumps({
                "user": {
                    "id":
                    payload["id"],
                    "name":
                    payload["name"],
                    "email":
                    payload["email"]
                }
            }),
            status_code=200,
            mimetype="application/json",
        )

    except Exception as error:
        logging.exception(
            "Auth/me failed."
        )

        return func.HttpResponse(
            json.dumps({
                "error": str(error)
            }),
            status_code=500,
            mimetype="application/json",
        )


# ---------------------------------------------------------
#  Logout
# ---------------------------------------------------------

@app.route(
    route="auth/logout",
    auth_level=func.AuthLevel.ANONYMOUS,
    methods=["POST"],
)
def logout_user(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse(
        json.dumps({
            "message":
            "Logout successful. Remove the authentication token."
        }),
        status_code=200,
        mimetype="application/json",
    )