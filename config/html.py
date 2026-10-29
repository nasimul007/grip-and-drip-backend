"""Cleans rich-text HTML before it is stored and later rendered as raw HTML."""
import copy

import nh3

_ATTRIBUTES = copy.deepcopy(nh3.ALLOWED_ATTRIBUTES)
_ATTRIBUTES.setdefault("*", set()).add("style")

# Formatting the admin editor produces; anything else in style="" is dropped.
_STYLE_PROPERTIES = {
    "text-align", "color", "background-color", "font-weight", "font-style",
    "text-decoration", "width", "height", "margin-left", "padding-left",
}


def clean_html(value: str) -> str:
    """Strip scripts, event handlers, javascript: links and unknown tags."""
    if not value:
        return value
    return nh3.clean(
        value,
        attributes=_ATTRIBUTES,
        filter_style_properties=_STYLE_PROPERTIES,
        clean_content_tags={"script", "style"},
        url_schemes={"http", "https", "mailto", "tel"},
    )
