"""Central, secure loading of the DMarket API keys.

This module loads API keys from JSON file(cuurent) or environment:

Usage:
    import credentials
    public_key, secret_key = credentials.load_api_keys()
"""

import json
import os

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))

PUBLIC_KEY_ENV = "DMARKET_PUBLIC_KEY"
SECRET_KEY_ENV = "DMARKET_SECRET_KEY"


def _candidate_dirs():
    """Directories to search for ``.env`` / ``JSON/config.json``."""
    seen = []
    for d in (_THIS_DIR, os.getcwd(), os.path.dirname(_THIS_DIR)):
        d = os.path.abspath(d)
        if d not in seen:
            seen.append(d)
    return seen


def _load_dotenv():
    """Read the first ``.env`` file found into ``os.environ`` (no overwrite)."""
    for d in _candidate_dirs():
        path = os.path.join(d, ".env")
        if not os.path.isfile(path):
            continue
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                # Do not clobber variables already set in the real environment.
                os.environ.setdefault(key, value)
        return path
    return None


def _load_from_json():
    """Return (public, secret) from a JSON config file, or (None, None)."""
    candidates = []
    for d in _candidate_dirs():
        candidates.append(os.path.join(d, "JSON", "config.json"))
        candidates.append(os.path.join(d, "config.json"))
    for path in candidates:
        if not os.path.isfile(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            return data.get("public_key"), data.get("secret_key")
        except (json.JSONDecodeError, OSError):
            continue
    return None, None


def load_api_keys():
    """Return ``(public_key, secret_key)`` from the most secure source available.

    Raises ``RuntimeError`` with guidance if no keys can be found.
    """
    public = os.environ.get(PUBLIC_KEY_ENV)
    secret = os.environ.get(SECRET_KEY_ENV)

    if not (public and secret):
        _load_dotenv()
        public = os.environ.get(PUBLIC_KEY_ENV)
        secret = os.environ.get(SECRET_KEY_ENV)

    if not (public and secret):
        json_public, json_secret = _load_from_json()
        public = public or json_public
        secret = secret or json_secret

    if not (public and secret):
        searched = []
        for d in _candidate_dirs():
            searched.append(os.path.join(d, ".env"))
            searched.append(os.path.join(d, "JSON", "config.json"))
        raise RuntimeError(
            "DMarket API keys not found. Provide them in one of these ways:\n"
            f"  1. Environment variables {PUBLIC_KEY_ENV} and {SECRET_KEY_ENV}\n"
            "  2. A .env file (copy Project/.env.example to Project/.env)\n"
            "  3. JSON/config.json (copy Project/JSON/config.example.json)\n"
            "Locations searched for .env / config.json:\n    "
            + "\n    ".join(searched)
        )

    return public, secret
