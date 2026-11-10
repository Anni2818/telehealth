import asyncio
import json
import os
from datetime import date
from pathlib import Path

import httpx
from dotenv import load_dotenv
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


load_dotenv(Path(__file__).resolve().parent / ".env")


async def main():
    api_key = os.getenv("MCP_API_KEY", "").strip()

    if not api_key:
        raise RuntimeError(
            "MCP_API_KEY is missing. Add it to your .env file."
        )

    specialty = input("Specialty: ").strip()
    city = input("City: ").strip()
    requested_date = input("Date (YYYY-MM-DD): ").strip()
    doctor_code = input(
        "Doctor code, or press Enter for all: "
    ).strip()

    try:
        date.fromisoformat(requested_date)
    except ValueError:
        print("Enter a valid date in YYYY-MM-DD format.")
        return

    arguments = {
        "specialty": specialty,
        "city": city,
        "requested_date": requested_date,
    }

    if doctor_code:
        arguments["doctor_code"] = doctor_code

    async with httpx.AsyncClient(
        headers={"x-api-key": api_key},
        timeout=60.0,
    ) as http_client:
        async with streamable_http_client(
            os.getenv(
                "MCP_TEST_URL",
                "http://127.0.0.1:8001/mcp",
            ).strip(),
            http_client=http_client,
        ) as (read_stream, write_stream, _):
            async with ClientSession(
                read_stream,
                write_stream,
            ) as session:
                await session.initialize()

                tools = await session.list_tools()

                print(
                    "\nAvailable tools:",
                    [tool.name for tool in tools.tools],
                )

                result = await session.call_tool(
                    "search_available_slots",
                    arguments=arguments,
                )

                if result.isError:
                    print("\nTool reported an error:")
                else:
                    print("\nTool succeeded:")

                if result.structuredContent is not None:
                    print(
                        json.dumps(
                            result.structuredContent,
                            indent=2,
                        )
                    )
                else:
                    for content in result.content:
                        if content.type == "text":
                            print(content.text)


if __name__ == "__main__":
    asyncio.run(main())