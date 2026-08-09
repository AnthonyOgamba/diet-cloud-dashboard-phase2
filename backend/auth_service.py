import os
import re
import uuid
from datetime import datetime, timezone, timedelta

import bcrypt
import jwt
from azure.cosmos import CosmosClient


COSMOS_ENDPOINT = os.getenv("COSMOS_ENDPOINT")
COSMOS_KEY = os.getenv("COSMOS_KEY")
COSMOS_DATABASE = os.getenv(
    "COSMOS_DATABASE",
    "DietDashboardDB"
)
COSMOS_CONTAINER = os.getenv(
    "COSMOS_CONTAINER",
    "users"
)

JWT_SECRET = os.getenv(
    "JWT_SECRET",
    "change-this-secret"
)


# ---------------------------------------------------------
# Cosmos DB Connection
# ---------------------------------------------------------

def get_users_container():
    if not COSMOS_ENDPOINT or not COSMOS_KEY:
        raise ValueError(
            "Cosmos DB settings are missing."
        )

    client = CosmosClient(
        COSMOS_ENDPOINT,
        credential=COSMOS_KEY
    )

    database = client.create_database_if_not_exists(
        id=COSMOS_DATABASE
    )

    container = database.create_container_if_not_exists(
        id=COSMOS_CONTAINER,
        partition_key="/email"
    )

    return container


# ---------------------------------------------------------
# Email Validation
# ---------------------------------------------------------

def valid_email(email):
    pattern = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"

    return re.match(
        pattern,
        email
    ) is not None


# ---------------------------------------------------------
# Password Validation
# ---------------------------------------------------------

def valid_password(password):
    return (
        len(password) >= 8
        and any(
            character.isupper()
            for character in password
        )
        and any(
            character.islower()
            for character in password
        )
        and any(
            character.isdigit()
            for character in password
        )
    )


# ---------------------------------------------------------
# Password Hashing
# ---------------------------------------------------------

def hash_password(password):
    password_bytes = password.encode(
        "utf-8"
    )

    hashed_password = bcrypt.hashpw(
        password_bytes,
        bcrypt.gensalt()
    )

    return hashed_password.decode(
        "utf-8"
    )


# ---------------------------------------------------------
# Password Verification
# ---------------------------------------------------------

def verify_password(
    password,
    password_hash
):
    return bcrypt.checkpw(
        password.encode("utf-8"),
        password_hash.encode("utf-8")
    )


# ---------------------------------------------------------
# Find User By Email
# ---------------------------------------------------------

def find_user_by_email(email):
    container = get_users_container()

    email = email.strip().lower()

    query = """
    SELECT * FROM c
    WHERE LOWER(c.email) = @email
    """

    parameters = [
        {
            "name": "@email",
            "value": email
        }
    ]

    users = list(
        container.query_items(
            query=query,
            parameters=parameters,
            enable_cross_partition_query=True
        )
    )

    if users:
        return users[0]

    return None


# ---------------------------------------------------------
# Create New User
# ---------------------------------------------------------

def create_user(
    name,
    email,
    password
):
    name = name.strip()
    email = email.strip().lower()

    if not name:
        raise ValueError(
            "Name is required."
        )

    if not valid_email(email):
        raise ValueError(
            "Invalid email address."
        )

    if not valid_password(password):
        raise ValueError(
            "Password must be at least 8 characters "
            "and contain uppercase, lowercase and a number."
        )

    existing_user = find_user_by_email(
        email
    )

    if existing_user:
        raise ValueError(
            "Email is already registered."
        )

    current_time = datetime.now(
        timezone.utc
    ).isoformat()

    user = {
        "id": str(uuid.uuid4()),
        "name": name,
        "email": email,

        # Never store plain password
        "passwordHash": hash_password(
            password
        ),

        "provider": "local",
        "providerId": None,
        "createdAt": current_time,
        "updatedAt": current_time
    }

    container = get_users_container()

    container.create_item(
        body=user
    )

    # Do not return passwordHash
    return {
        "id": user["id"],
        "name": user["name"],
        "email": user["email"]
    }


# ---------------------------------------------------------
# Create Login Token
# ---------------------------------------------------------

def create_token(user):
    expiration_time = datetime.now(
        timezone.utc
    ) + timedelta(hours=2)

    payload = {
        "id": user["id"],
        "name": user["name"],
        "email": user["email"],
        "exp": expiration_time
    }

    token = jwt.encode(
        payload,
        JWT_SECRET,
        algorithm="HS256"
    )

    return token


# ---------------------------------------------------------
# Verify Login Token
# ---------------------------------------------------------

def verify_token(token):
    try:
        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=["HS256"]
        )

        return payload

    except jwt.ExpiredSignatureError:
        return None

    except jwt.InvalidTokenError:
        return None