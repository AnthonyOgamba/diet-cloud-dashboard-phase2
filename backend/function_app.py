import io
import json
import logging
import os
import time

import azure.functions as func
import pandas as pd
from azure.storage.blob import BlobServiceClient

from data_processing import (
    clean_dataset,
    generate_cache_data,
)

from recipe_api import get_paginated_recipes

from auth_service import (
    create_user,
    find_user_by_email,
    verify_password,
    create_token,
    verify_token,
)


app = func.FunctionApp()


# =========================================================
# JSON HELPER
# =========================================================

def _json_default(value):
    """
    Convert pandas, numpy and datetime values
    into JSON-safe values.
    """

    if hasattr(value, "item"):
        return value.item()

    if hasattr(value, "isoformat"):
        return value.isoformat()

    return str(value)


# =========================================================
# PHASE 3 - BLOB TRIGGER
# =========================================================

@app.blob_trigger(
    arg_name="input_blob",
    path="datasets/All_Diets.csv",
    connection="AZURE_STORAGE_CONNECTION_STRING",
    source="EventGrid",
)
def AllDietsBlobTrigger(
    input_blob: func.InputStream,
) -> None:
    """
    Phase 3 data-processing pipeline.

    Runs only when datasets/All_Diets.csv changes.

    Processing:
    1. Read raw dataset
    2. Clean dataset once
    3. Calculate visualization results once
    4. Save cleaned dataset
    5. Save precomputed dashboard cache
    """

    logging.info(
        "PHASE3_TRIGGER_START | blob=%s | bytes=%s",
        input_blob.name,
        input_blob.length,
    )

    connection_string = os.environ[
        "AZURE_STORAGE_CONNECTION_STRING"
    ]

    container_name = os.getenv(
        "BLOB_CONTAINER_NAME",
        "datasets",
    )

    # -----------------------------------------------------
    # 1. Read newly uploaded raw dataset
    # -----------------------------------------------------

    raw_bytes = input_blob.read()

    raw_dataframe = pd.read_csv(
        io.BytesIO(raw_bytes)
    )

    logging.info(
        "PHASE3_RAW_DATA_LOADED | records=%s",
        len(raw_dataframe),
    )

    # -----------------------------------------------------
    # 2. Clean dataset ONCE
    # -----------------------------------------------------

    cleaned_dataframe, processing_stats = clean_dataset(
        raw_dataframe
    )

    logging.info(
        (
            "PHASE3_CLEANING_COMPLETE | "
            "initial=%s | final=%s | dropped=%s"
        ),
        processing_stats["initial_records"],
        processing_stats["final_records"],
        processing_stats["records_dropped"],
    )

    blob_service_client = (
        BlobServiceClient.from_connection_string(
            connection_string
        )
    )

    # -----------------------------------------------------
    # Read source blob properties
    # -----------------------------------------------------

    source_blob_client = (
        blob_service_client.get_blob_client(
            container=container_name,
            blob="All_Diets.csv",
        )
    )

    source_properties = (
        source_blob_client.get_blob_properties()
    )

    dataset_version = str(
        source_properties.etag
    ).strip('"')

    # -----------------------------------------------------
    # 3. Calculate visualization results ONCE
    # -----------------------------------------------------

    cache_payload = generate_cache_data(
        cleaned_dataframe,
        version=dataset_version,
    )

    cache_payload["processing_stats"] = (
        processing_stats
    )

    cache_payload["source"] = {
        "blob": "All_Diets.csv",
        "etag": dataset_version,
        "last_modified": (
            source_properties.last_modified
        ),
    }

    logging.info(
        (
            "PHASE3_CALCULATIONS_COMPLETE | "
            "version=%s | cache_keys=%s"
        ),
        dataset_version,
        len(cache_payload),
    )

    # -----------------------------------------------------
    # 4. Save cleaned dataset
    # -----------------------------------------------------

    cleaned_csv = cleaned_dataframe.to_csv(
        index=False
    ).encode("utf-8")

    cleaned_blob_client = (
        blob_service_client.get_blob_client(
            container=container_name,
            blob="cleaned_diets_dataset.csv",
        )
    )

    cleaned_blob_client.upload_blob(
        cleaned_csv,
        overwrite=True,
    )

    logging.info(
        (
            "PHASE3_CLEANED_DATA_SAVED | "
            "blob=cleaned_diets_dataset.csv"
        )
    )

    # -----------------------------------------------------
    # 5. Save precomputed dashboard cache
    # -----------------------------------------------------

    cache_json = json.dumps(
        cache_payload,
        default=_json_default,
    )

    cache_blob_client = (
        blob_service_client.get_blob_client(
            container=container_name,
            blob="dashboard_cache.json",
        )
    )

    cache_blob_client.upload_blob(
        cache_json,
        overwrite=True,
    )

    logging.info(
        (
            "PHASE3_CACHE_SAVED | "
            "blob=dashboard_cache.json | version=%s"
        ),
        dataset_version,
    )

    logging.info(
        "PHASE3_TRIGGER_COMPLETE | blob=%s",
        input_blob.name,
    )


# =========================================================
# PHASE 3 - CACHED DASHBOARD ENDPOINT
# =========================================================

@app.route(
    route="DietAnalysisFunction",
    auth_level=func.AuthLevel.ANONYMOUS,
    methods=["GET"],
)
def DietAnalysisFunction(
    req: func.HttpRequest,
) -> func.HttpResponse:
    """
    Optimized Phase 3 dashboard endpoint.

    Data cleaning and visualization calculations
    DO NOT run during dashboard requests.

    The endpoint reads dashboard_cache.json generated
    by AllDietsBlobTrigger.
    """

    start_time = time.time()

    try:
        connection_string = os.environ[
            "AZURE_STORAGE_CONNECTION_STRING"
        ]

        container_name = os.getenv(
            "BLOB_CONTAINER_NAME",
            "datasets",
        )

        blob_service_client = (
            BlobServiceClient.from_connection_string(
                connection_string
            )
        )

        # -------------------------------------------------
        # Read PRECOMPUTED cache
        # -------------------------------------------------

        cache_blob_client = (
            blob_service_client.get_blob_client(
                container=container_name,
                blob="dashboard_cache.json",
            )
        )

        cache_bytes = (
            cache_blob_client
            .download_blob()
            .readall()
        )

        cache_data = json.loads(
            cache_bytes.decode("utf-8")
        )

        # -------------------------------------------------
        # Determine requested diet
        # -------------------------------------------------

        requested_diet = (
            req.params
            .get("diet", "all")
            .strip()
            .lower()
        )

        if requested_diet == "all":
            cache_key = "dashboard:all"

        else:
            cache_key = next(
                (
                    key
                    for key in cache_data.keys()
                    if key.startswith("dashboard:")
                    and (
                        key.split(":", 1)[1].lower()
                        == requested_diet
                    )
                ),
                None,
            )

        # -------------------------------------------------
        # Validate requested diet
        # -------------------------------------------------

        if (
            not cache_key
            or cache_key not in cache_data
        ):
            available_diets = sorted(
                key.split(":", 1)[1]
                for key in cache_data.keys()
                if key.startswith("dashboard:")
            )

            return func.HttpResponse(
                body=json.dumps(
                    {
                        "error":
                            "Unsupported diet type.",
                        "requested":
                            requested_diet,
                        "available":
                            available_diets,
                    }
                ),
                status_code=400,
                mimetype="application/json",
            )

        # -------------------------------------------------
        # Retrieve precomputed dashboard result
        # -------------------------------------------------

        cached_dashboard = cache_data[
            cache_key
        ]

        bar_data = cached_dashboard.get(
            "barChart",
            {},
        )

        pie_data = cached_dashboard.get(
            "pieChart",
            {},
        )

        average_macros = cached_dashboard.get(
            "average_macros",
            {},
        )

        dataset_status = cache_data.get(
            "dataset:status",
            {},
        )

        labels = list(
            bar_data.keys()
        )

        protein_values = [
            float(
                bar_data[label].get(
                    "protein",
                    0,
                )
            )
            for label in labels
        ]

        carbs_values = [
            float(
                bar_data[label].get(
                    "carbs",
                    0,
                )
            )
            for label in labels
        ]

        fat_values = [
            float(
                bar_data[label].get(
                    "fat",
                    0,
                )
            )
            for label in labels
        ]

        # -------------------------------------------------
        # Preserve existing frontend contract
        # -------------------------------------------------

        response_data = {
            "filter":
                requested_diet,

            "summary": {
                "total_records":
                    cached_dashboard.get(
                        "recordCount",
                        0,
                    ),

                "avg_protein_overall":
                    average_macros.get(
                        "protein",
                        0,
                    ),

                "avg_carbs_overall":
                    average_macros.get(
                        "carbs",
                        0,
                    ),

                "avg_fat_overall":
                    average_macros.get(
                        "fat",
                        0,
                    ),
            },

            "diet_distribution":
                pie_data,

            "average_nutrition": {
                "labels":
                    labels,

                "protein":
                    protein_values,

                "carbs":
                    carbs_values,

                "fat":
                    fat_values,
            },

            "charts": {
                "bar_chart": {
                    "labels":
                        labels,

                    "values":
                        protein_values,
                },

                "pie_chart": {
                    "labels":
                        list(
                            pie_data.keys()
                        ),

                    "values":
                        list(
                            pie_data.values()
                        ),
                },

                "comparison_chart": {
                    "labels":
                        labels,

                    "protein":
                        protein_values,

                    "carbs":
                        carbs_values,

                    "fat":
                        fat_values,
                },
            },

            "metadata": {
                "container":
                    container_name,

                "blob":
                    "dashboard_cache.json",

                "execution_time_seconds":
                    round(
                        time.time()
                        - start_time,
                        3,
                    ),

                "source":
                    "precomputed-cache",

                "cache_key":
                    cache_key,

                "dataset_version":
                    dataset_status.get(
                        "datasetVersion"
                    ),

                "last_processed":
                    dataset_status.get(
                        "lastProcessed"
                    ),
            },
        }

        logging.info(
            (
                "PHASE3_CACHE_HIT | "
                "key=%s | version=%s"
            ),
            cache_key,
            dataset_status.get(
                "datasetVersion"
            ),
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
                        "AZURE_STORAGE_CONNECTION_STRING "
                        "is missing from "
                        "application settings."
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
                    "error":
                        str(error)
                }
            ),
            status_code=500,
            mimetype="application/json",
        )


# =========================================================
# PHASE 3 - RECIPE SEARCH / FILTER / PAGINATION
# =========================================================

@app.route(
    route="recipes",
    auth_level=func.AuthLevel.ANONYMOUS,
    methods=["GET"],
)
def RecipesFunction(
    req: func.HttpRequest,
) -> func.HttpResponse:
    """
    Recipe interaction endpoint.

    Supports:
    - Diet filtering
    - Keyword searching
    - Pagination

    Examples:

    /api/recipes?diet=vegan

    /api/recipes?q=chicken

    /api/recipes?diet=keto&q=chicken&page=1&pageSize=10
    """

    try:
        connection_string = os.environ[
            "AZURE_STORAGE_CONNECTION_STRING"
        ]

        container_name = os.getenv(
            "BLOB_CONTAINER_NAME",
            "datasets",
        )

        blob_service_client = (
            BlobServiceClient.from_connection_string(
                connection_string
            )
        )

        cleaned_blob_client = (
            blob_service_client.get_blob_client(
                container=container_name,
                blob="cleaned_diets_dataset.csv",
            )
        )

        cleaned_bytes = (
            cleaned_blob_client
            .download_blob()
            .readall()
        )

        cleaned_dataframe = pd.read_csv(
            io.BytesIO(
                cleaned_bytes
            )
        )

        # -------------------------------------------------
        # Query parameters
        # -------------------------------------------------

        diet = (
            req.params
            .get("diet", "all")
            .strip()
        )

        keyword = req.params.get(
            "q"
        )

        if keyword:
            keyword = keyword.strip()

        try:
            page = int(
                req.params.get(
                    "page",
                    "1",
                )
            )
        except ValueError:
            page = 1

        try:
            page_size = int(
                req.params.get(
                    "pageSize",
                    "10",
                )
            )
        except ValueError:
            page_size = 10

        page = max(
            page,
            1,
        )

        page_size = max(
            1,
            min(
                page_size,
                100,
            ),
        )

        # -------------------------------------------------
        # Member 2 filtering/search/pagination logic
        # -------------------------------------------------

        result = get_paginated_recipes(
            cleaned_df=cleaned_dataframe,
            diet=diet,
            q=keyword,
            page=page,
            page_size=page_size,
        )

        result["filters"] = {
            "diet":
                diet,

            "keyword":
                keyword or "",
        }

        result["metadata"] = {
            "source":
                "cleaned_diets_dataset.csv",

            "container":
                container_name,
        }

        logging.info(
            (
                "PHASE3_RECIPE_QUERY | "
                "diet=%s | q=%s | "
                "page=%s | pageSize=%s | "
                "total=%s"
            ),
            diet,
            keyword,
            page,
            page_size,
            result["pagination"][
                "totalItems"
            ],
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
                        "AZURE_STORAGE_CONNECTION_STRING "
                        "is missing from "
                        "application settings."
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
                    "error":
                        str(error)
                }
            ),
            status_code=500,
            mimetype="application/json",
        )


# =========================================================
# PHASE 3 - EMAIL/PASSWORD REGISTRATION
# =========================================================

@app.route(
    route="auth/register",
    auth_level=func.AuthLevel.ANONYMOUS,
    methods=["POST"],
)
def register_user(
    req: func.HttpRequest,
) -> func.HttpResponse:
    """
    Register a local user.

    Password hashing and Cosmos DB storage
    are handled by auth_service.create_user().
    """

    try:
        data = req.get_json()

        name = data.get(
            "name",
            "",
        ).strip()

        email = data.get(
            "email",
            "",
        ).strip().lower()

        password = data.get(
            "password",
            "",
        )

        if (
            not name
            or not email
            or not password
        ):
            return func.HttpResponse(
                body=json.dumps(
                    {
                        "error": (
                            "Name, email and "
                            "password are required."
                        )
                    }
                ),
                status_code=400,
                mimetype="application/json",
            )

        user = create_user(
            name,
            email,
            password,
        )

        # Do NOT return passwordHash to frontend.
        safe_user = {
            "id":
                user.get("id"),

            "name":
                user.get("name"),

            "email":
                user.get("email"),

            "provider":
                user.get(
                    "provider",
                    "local",
                ),

            "createdAt":
                user.get(
                    "createdAt"
                ),
        }

        logging.info(
            "PHASE3_USER_REGISTERED | email=%s",
            email,
        )

        return func.HttpResponse(
            body=json.dumps(
                {
                    "message":
                        "User registered successfully.",

                    "user":
                        safe_user,
                },
                default=_json_default,
            ),
            status_code=201,
            mimetype="application/json",
        )

    except ValueError as error:
        return func.HttpResponse(
            body=json.dumps(
                {
                    "error":
                        str(error)
                }
            ),
            status_code=400,
            mimetype="application/json",
        )

    except Exception as error:
        logging.exception(
            "Registration failed."
        )

        return func.HttpResponse(
            body=json.dumps(
                {
                    "error":
                        str(error)
                }
            ),
            status_code=500,
            mimetype="application/json",
        )


# =========================================================
# PHASE 3 - EMAIL/PASSWORD LOGIN
# =========================================================

@app.route(
    route="auth/login",
    auth_level=func.AuthLevel.ANONYMOUS,
    methods=["POST"],
)
def login_user(
    req: func.HttpRequest,
) -> func.HttpResponse:
    """
    Authenticate a local user and issue a JWT.
    """

    try:
        data = req.get_json()

        email = data.get(
            "email",
            "",
        ).strip().lower()

        password = data.get(
            "password",
            "",
        )

        if (
            not email
            or not password
        ):
            return func.HttpResponse(
                body=json.dumps(
                    {
                        "error":
                            "Email and password are required."
                    }
                ),
                status_code=400,
                mimetype="application/json",
            )

        user = find_user_by_email(
            email
        )

        if (
            not user
            or not verify_password(
                password,
                user["passwordHash"],
            )
        ):
            return func.HttpResponse(
                body=json.dumps(
                    {
                        "error":
                            "Invalid email or password."
                    }
                ),
                status_code=401,
                mimetype="application/json",
            )

        token = create_token(
            user
        )

        logging.info(
            "PHASE3_USER_LOGIN_SUCCESS | email=%s",
            email,
        )

        return func.HttpResponse(
            body=json.dumps(
                {
                    "message":
                        "Login successful.",

                    "token":
                        token,

                    "user": {
                        "id":
                            user["id"],

                        "name":
                            user["name"],

                        "email":
                            user["email"],
                    },
                }
            ),
            status_code=200,
            mimetype="application/json",
        )

    except Exception as error:
        logging.exception(
            "Login failed."
        )

        return func.HttpResponse(
            body=json.dumps(
                {
                    "error":
                        str(error)
                }
            ),
            status_code=500,
            mimetype="application/json",
        )


# =========================================================
# PHASE 3 - CURRENT AUTHENTICATED USER
# =========================================================

@app.route(
    route="auth/me",
    auth_level=func.AuthLevel.ANONYMOUS,
    methods=["GET"],
)
def get_current_user(
    req: func.HttpRequest,
) -> func.HttpResponse:
    """
    Validate the Bearer JWT and return
    the currently authenticated user.
    """

    try:
        auth_header = req.headers.get(
            "Authorization"
        )

        if not auth_header:
            return func.HttpResponse(
                body=json.dumps(
                    {
                        "error":
                            "Authorization token is required."
                    }
                ),
                status_code=401,
                mimetype="application/json",
            )

        if not auth_header.startswith(
            "Bearer "
        ):
            return func.HttpResponse(
                body=json.dumps(
                    {
                        "error":
                            "Invalid authorization format."
                    }
                ),
                status_code=401,
                mimetype="application/json",
            )

        token = auth_header.replace(
            "Bearer ",
            "",
            1,
        )

        payload = verify_token(
            token
        )

        if not payload:
            return func.HttpResponse(
                body=json.dumps(
                    {
                        "error":
                            "Invalid or expired token."
                    }
                ),
                status_code=401,
                mimetype="application/json",
            )

        return func.HttpResponse(
            body=json.dumps(
                {
                    "user": {
                        "id":
                            payload["id"],

                        "name":
                            payload["name"],

                        "email":
                            payload["email"],
                    }
                }
            ),
            status_code=200,
            mimetype="application/json",
        )

    except Exception as error:
        logging.exception(
            "Auth/me failed."
        )

        return func.HttpResponse(
            body=json.dumps(
                {
                    "error":
                        str(error)
                }
            ),
            status_code=500,
            mimetype="application/json",
        )


# =========================================================
# PHASE 3 - LOGOUT
# =========================================================

@app.route(
    route="auth/logout",
    auth_level=func.AuthLevel.ANONYMOUS,
    methods=["POST"],
)
def logout_user(
    req: func.HttpRequest,
) -> func.HttpResponse:
    """
    JWT authentication is stateless.

    The frontend logs out by removing its stored token.
    """

    return func.HttpResponse(
        body=json.dumps(
            {
                "message": (
                    "Logout successful. "
                    "Remove the authentication token."
                )
            }
        ),
        status_code=200,
        mimetype="application/json",
    )