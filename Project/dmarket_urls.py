"""Shared URL encoding helpers for DMarket API item titles."""

from urllib.parse import quote


def encode_title(title: str) -> str:
    """URL-encode an item title for DMarket query params and signed API paths.

    Handles spaces, pipes, parentheses, Unicode (e.g. 龍王), and symbols
    (e.g. StatTrak™) in one pass instead of manual chained ``.replace()`` calls.
    """
    return quote(title, safe=',=')
