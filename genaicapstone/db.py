import os
from pathlib import Path

from dotenv import load_dotenv
from mssql_python import connect


load_dotenv(Path(__file__).resolve().parent / ".env")


def get_connection():
    connection_string = os.getenv("AZURE_SQL_CONNECTIONSTRING")

    if not connection_string:
        raise RuntimeError(
            "AZURE_SQL_CONNECTIONSTRING is missing. Check your .env file."
        )

    return connect(connection_string)