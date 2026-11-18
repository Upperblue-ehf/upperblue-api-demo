"""Authenticated GET requests to the Upperblue REST API."""

import os
from pathlib import Path

import requests
from dotenv import load_dotenv

BASE = "https://api.upperblue.com"


def get(path, **params):
    load_dotenv(Path(__file__).with_name(".env"), override=False)
    key = os.getenv("UPPERBLUE_API_KEY", "").strip()
    if not key:
        raise ValueError("Set UPPERBLUE_API_KEY in .env or run without --date for the sample.")

    with requests.get(
        f"{BASE}/{path}",
        params=params,
        headers={"X-API-Key": key},
        timeout=(5, 30),
        allow_redirects=False,
    ) as response:
        if response.status_code == 401:
            raise ValueError(
                "The API rejected the key. Check UPPERBLUE_API_KEY in your environment or .env."
            )
        if response.status_code == 429:
            delay = response.headers.get("Retry-After")
            hint = f" Retry-After: {delay}." if delay else " Try again later."
            raise ValueError("Upperblue rate limit reached." + hint)
        if response.is_redirect:
            raise ValueError("Unexpected redirect from the Upperblue API.")
        response.raise_for_status()
        return response.json()
