import os
from pathlib import Path

import msal
from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parent / ".env")


def main():
    required_settings = (
        "ENTRA_TENANT_ID",
        "ENTRA_TEST_CLIENT_ID",
        "ENTRA_API_SCOPE",
    )

    settings = {}

    for name in required_settings:
        value = os.getenv(name, "").strip()

        if not value:
            raise RuntimeError(f"{name} is missing from .env.")

        settings[name] = value

    application = msal.PublicClientApplication(
        client_id=settings["ENTRA_TEST_CLIENT_ID"],
        authority=(
            "https://login.microsoftonline.com/"
            + settings["ENTRA_TENANT_ID"]
        ),
    )

    flow = application.initiate_device_flow(
        scopes=[settings["ENTRA_API_SCOPE"]]
    )

    if "user_code" not in flow:
        print("Could not start sign-in.")
        print("Error:", flow.get("error", "Unknown error"))
        print("Details:", flow.get("error_description", ""))
        return

    print(flow["message"])
    print("\nWaiting for you to complete sign-in...")

    result = application.acquire_token_by_device_flow(flow)

    if "access_token" not in result:
        print("\nSign-in or token acquisition failed.")
        print("Error:", result.get("error", "Unknown error"))
        print("Details:", result.get("error_description", ""))
        print("Correlation ID:", result.get("correlation_id", ""))
        return

    print("\nSUCCESS: An access token was acquired.")
    print("Granted scopes:", result.get("scope", "Not returned"))
    print("Expires in seconds:", result.get("expires_in", "Not returned"))
    print("The token has not been printed or saved.")


if __name__ == "__main__":
    main()