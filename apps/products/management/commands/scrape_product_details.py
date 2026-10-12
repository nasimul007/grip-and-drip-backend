import csv
import html
import json
import mimetypes
import re
import time
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.products.models import Product, ProductImage

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)
BASE_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept-Language": "en-US,en;q=0.9",
}
PAGE_ACCEPT = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
IMAGE_ACCEPT = "image/avif,image/webp,image/png,image/jpeg,image/*;q=0.8"

VOID_TAGS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "source", "track", "wbr",
}
DESCRIPTION_HINTS = ("description", "product-detail", "product_detail", "product-info")
SPEC_HINTS = ("specification", "spec-", "specs", "additional-info", "additional_info", "product-attributes", "product_attributes", "tech-spec")
GALLERY_HINTS = ("gallery", "product-image", "product__media", "product-media", "product-photo")
IMAGE_BLOCKLIST = ("logo", "sprite", "icon", "placeholder", "favicon", "badge", "payment")
MIN_IMAGE_BYTES = 2048


# ── HTML parsing ──────────────────────────────────────────────────────────


class PageParser(HTMLParser):
    """Collects JSON-LD, meta tags, title/h1, description blocks and gallery images."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ld_json = []
        self.meta = {}
        self.title = ""
        self.h1 = ""
        self.description_blocks = []
        self.gallery_images = []
        self.spec_rows = []

        self._script_ld = False
        self._script_buf = []
        self._in_title = False
        self._in_h1 = False
        self._h1_done = False
        self._skip_depth = 0  # inside <script>/<style> that we don't want

        # (tag, depth, parts) for an open description capture
        self._desc = None
        # (tag, depth) for an open gallery container
        self._gallery = None
        # (tag, depth) for an open specifications container, plus cell capture
        self._spec = None
        self._cells = []
        self._cell_tag = None
        self._cell_buf = []

    @staticmethod
    def _hint(attrs, hints):
        value = f"{attrs.get('id', '')} {attrs.get('class', '')}".lower()
        return any(h in value for h in hints)

    def handle_starttag(self, tag, attrs_list):
        attrs = {k: (v or "") for k, v in attrs_list}

        if tag == "script":
            if attrs.get("type", "").lower() == "application/ld+json":
                self._script_ld = True
                self._script_buf = []
            else:
                self._skip_depth += 1
            return
        if tag in ("style", "noscript", "template"):
            self._skip_depth += 1
            return

        if tag == "meta":
            key = (attrs.get("property") or attrs.get("name") or "").lower()
            if key and attrs.get("content"):
                self.meta.setdefault(key, []).append(attrs["content"].strip())
        elif tag == "link" and attrs.get("rel", "").lower() == "image_src" and attrs.get("href"):
            self.meta.setdefault("image_src", []).append(attrs["href"])
        elif tag == "title":
            self._in_title = True
        elif tag == "h1" and not self._h1_done:
            self._in_h1 = True

        if self._desc:
            d_tag, depth, parts = self._desc
            if tag == d_tag:
                self._desc = (d_tag, depth + 1, parts)
            parts.append(self.get_starttag_text() or f"<{tag}>")
        elif tag not in VOID_TAGS and self._hint(attrs, DESCRIPTION_HINTS):
            self._desc = (tag, 1, [])

        if self._gallery:
            g_tag, depth = self._gallery
            if tag == g_tag:
                self._gallery = (g_tag, depth + 1)
            if tag in ("img", "a", "div", "source"):
                for key in ("data-zoom-image", "data-large_image", "data-src", "data-srcset", "srcset", "src", "href"):
                    val = attrs.get(key)
                    if not val:
                        continue
                    if key in ("srcset", "data-srcset"):
                        val = val.split(",")[-1].strip().split(" ")[0]
                    if key == "href" and not re.search(r"\.(jpe?g|png|webp|avif)(\?|$)", val, re.I):
                        continue
                    self.gallery_images.append(val)
                    break
        elif tag not in VOID_TAGS and self._hint(attrs, GALLERY_HINTS):
            self._gallery = (tag, 1)

        if self._spec:
            s_tag, depth = self._spec
            if tag == s_tag:
                self._spec = (s_tag, depth + 1)
            if tag == "tr":
                self._cells = []
            elif tag in ("th", "td", "dt", "dd"):
                self._cell_tag, self._cell_buf = tag, []
        elif tag not in VOID_TAGS and self._hint(attrs, SPEC_HINTS):
            self._spec = (tag, 1)
            self._cells = []

    def handle_startendtag(self, tag, attrs_list):
        self.handle_starttag(tag, attrs_list)
        if tag not in VOID_TAGS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag == "script":
            if self._script_ld:
                self.ld_json.append("".join(self._script_buf))
                self._script_ld = False
            elif self._skip_depth:
                self._skip_depth -= 1
            return
        if tag in ("style", "noscript", "template"):
            if self._skip_depth:
                self._skip_depth -= 1
            return

        if tag == "title":
            self._in_title = False
        elif tag == "h1" and self._in_h1:
            self._in_h1 = False
            self._h1_done = bool(self.h1.strip())

        if self._desc:
            d_tag, depth, parts = self._desc
            if tag == d_tag:
                depth -= 1
            if depth == 0:
                self.description_blocks.append("".join(parts))
                self._desc = None
            else:
                parts.append(f"</{tag}>")
                self._desc = (d_tag, depth, parts)

        if self._gallery:
            g_tag, depth = self._gallery
            if tag == g_tag:
                depth -= 1
            self._gallery = (g_tag, depth) if depth else None

        if self._spec:
            s_tag, depth = self._spec
            if tag in ("th", "td", "dt", "dd") and self._cell_tag == tag:
                text = re.sub(r"\s+", " ", "".join(self._cell_buf)).strip()
                self._cell_tag = None
                if tag == "dd":
                    if self._cells and self._cells[-1][0] == "dt":
                        self._add_spec(self._cells[-1][1], text)
                    self._cells = []
                else:
                    self._cells.append((tag, text))
            elif tag == "tr":
                if len(self._cells) == 2:
                    self._add_spec(self._cells[0][1], self._cells[1][1])
                self._cells = []
            if tag == s_tag:
                depth -= 1
            self._spec = (s_tag, depth) if depth else None

    def _add_spec(self, label, value):
        label = label.strip().rstrip(":").strip()
        if label and value and len(label) <= 60 and len(value) <= 300:
            self.spec_rows.append((label, value))

    def handle_data(self, data):
        if self._script_ld:
            self._script_buf.append(data)
            return
        if self._skip_depth:
            return
        if self._in_title:
            self.title += data
        if self._in_h1:
            self.h1 += data
        if self._spec and self._cell_tag:
            self._cell_buf.append(data)
        if self._desc:
            self._desc[2].append(html.escape(data, quote=False))


class DescriptionSanitizer(HTMLParser):
    """Whitelist-based HTML cleaner: keeps structure, strips attributes and links."""

    ALLOWED = {"p", "ul", "ol", "li", "strong", "b", "em", "i", "h3", "h4",
               "table", "thead", "tbody", "tr", "td", "th"}
    BLOCKS = {"p", "ul", "ol", "table", "h3", "h4"}
    # Tags HTML lets authors leave unclosed: a new one closes the previous one.
    SELF_CLOSING_SIBLINGS = {"p": {"p"}, "li": {"li", "p"}, "tr": {"tr", "td", "th"},
                             "td": {"td", "th", "p"}, "th": {"td", "th", "p"}}
    DROP_CONTENT = {"script", "style", "iframe", "noscript", "svg", "button", "form", "select"}
    BREAKS = {"div", "section", "article", "br", "hr"}
    HEADING_MAP = {"h1": "h3", "h2": "h3", "h5": "h4", "h6": "h4"}

    def __init__(self, base_url=""):
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.out = []
        self.stack = []
        self._drop = 0
        self._loose = []  # text outside any block element

    def _emit(self, chunk):
        if self.stack:
            self.out.append(chunk)
        else:
            self._loose.append(chunk)

    def _flush_loose(self):
        text = "".join(self._loose)
        self._loose = []
        for line in re.split(r"\s*\n\s*", text):
            if re.sub(r"<[^>]+>|\s", "", line):
                self.out.append(f"<p>{line.strip()}</p>")

    def _close_until(self, tag):
        while self.stack:
            top = self.stack.pop()
            self.out.append(f"</{top}>")
            if top == tag:
                break

    def handle_starttag(self, tag, attrs):
        if tag in self.DROP_CONTENT:
            self._drop += 1
            return
        if self._drop:
            return
        tag = self.HEADING_MAP.get(tag, tag)
        if tag == "img":
            self._image(dict(attrs))
            return
        if tag in self.BREAKS:
            self._emit("<br>" if self.stack and tag == "br" else "\n")
            return
        if tag not in self.ALLOWED:
            return
        closes = self.SELF_CLOSING_SIBLINGS.get(tag, set())
        if self.stack and self.stack[-1] in closes:
            self._close_until(self.stack[-1])
        if tag in self.BLOCKS and self.stack and self.stack[-1] in ("p", "h3", "h4"):
            self._close_until(self.stack[-1])
        if not self.stack:
            if tag in self.BLOCKS:
                self._flush_loose()
            else:  # inline tag at top level stays in the loose text
                self._loose.append(f"<{tag}>")
                return
        self.out.append(f"<{tag}>")
        self.stack.append(tag)

    def _image(self, attrs):
        src = description_image_src(attrs, self.base_url)
        if not src:
            return
        alt = html.escape(html.unescape(attrs.get("alt") or "").strip()[:200], quote=True)
        tag = f'<img src="{html.escape(src, quote=True)}" alt="{alt}">'
        if self.stack:
            self.out.append(tag)
        else:
            self._flush_loose()
            self.out.append(f"<p>{tag}</p>")

    def handle_startendtag(self, tag, attrs):
        if tag in self.BREAKS or tag == "img":
            self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag in self.DROP_CONTENT:
            self._drop = max(0, self._drop - 1)
            return
        if self._drop:
            return
        tag = self.HEADING_MAP.get(tag, tag)
        if tag in self.BREAKS:
            self._emit("\n")
        elif tag in self.stack:
            self._close_until(tag)
        elif tag in self.ALLOWED and not self.stack and tag not in self.BLOCKS:
            self._loose.append(f"</{tag}>")

    def handle_data(self, data):
        if not self._drop:
            self._emit(html.escape(data, quote=False))

    def result(self):
        while self.stack:
            self._close_until(self.stack[-1])
        self._flush_loose()
        text = "".join(self.out)
        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"\s*(<br>\s*){2,}", "<br><br>", text)
        text = re.sub(r"(<(p|li|td|th|h3|h4)>)\s*(<br>\s*)+|(\s*<br>)+\s*(</(p|li|td|th|h3|h4)>)", r"\1\5", text)
        for _ in range(3):
            text = re.sub(r"<(\w+)>\s*</\1>", "", text)
        return re.sub(r">\s+<", "><", text).strip()


HTML_TAG_RE = re.compile(
    r"</?(p|br|ul|ol|li|div|span|strong|b|em|i|h[1-6]|table|tr|td|section|img)\b[^>]*>", re.I
)


def description_image_src(attrs, base_url):
    """Best usable image URL from an <img> tag's attributes, or ''."""
    attrs = {k.lower(): (v or "") for k, v in attrs.items()}
    candidates = []
    for key in ("data-src", "data-lazy-src", "data-original", "src"):
        candidates.append(attrs.get(key, ""))
    for key in ("data-srcset", "srcset"):
        if attrs.get(key):
            candidates.insert(0, attrs[key].split(",")[-1].strip().split(" ")[0])
    for raw in candidates:
        url = html.unescape(raw.strip())
        if not url or url.startswith("data:"):
            continue
        out = normalize_images([url], base_url)
        if out:
            return out[0]
    return ""


def sanitize_description(raw, base_url=""):
    if not raw:
        return ""
    raw = raw.strip()
    if not HTML_TAG_RE.search(raw):
        # Plain text (JSON-LD/meta), possibly entity-encoded: one paragraph per line.
        paras = [p.strip() for p in re.split(r"\r?\n+", raw) if p.strip()]
        return "".join(f"<p>{html.escape(html.unescape(p), quote=False)}</p>" for p in paras)
    parser = DescriptionSanitizer(base_url)
    parser.feed(raw)
    parser.close()
    return parser.result()


def plain_length(fragment):
    return len(re.sub(r"<[^>]+>|\s+", "", html.unescape(fragment or "")))


# ── Extraction ────────────────────────────────────────────────────────────


def _iter_ld_nodes(data):
    if isinstance(data, list):
        for item in data:
            yield from _iter_ld_nodes(item)
    elif isinstance(data, dict):
        yield data
        for key in ("@graph", "mainEntity", "itemListElement"):
            if key in data:
                yield from _iter_ld_nodes(data[key])


def _is_product(node):
    t = node.get("@type")
    types = t if isinstance(t, list) else [t]
    return any(str(x).lower() in ("product", "productgroup") for x in types)


def _ld_images(value):
    if not value:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [value.get("contentUrl") or value.get("url") or ""]
    if isinstance(value, list):
        out = []
        for v in value:
            out.extend(_ld_images(v))
        return out
    return []


def _clean_title(title):
    title = html.unescape(re.sub(r"\s+", " ", title or "")).strip()
    # "Product Name | Store" / "Product Name – Store" → "Product Name"
    parts = re.split(r"\s+[|–—]\s+|\s+-\s+(?=[^-]+$)", title)
    return parts[0].strip() if parts and parts[0].strip() else title


def extract_product(page_html, base_url):
    parser = PageParser()
    parser.feed(page_html)
    parser.close()

    name = description = ""
    images = []
    specs = {}

    for blob in parser.ld_json:
        try:
            data = json.loads(blob.strip().rstrip(";"))
        except (ValueError, TypeError):
            continue
        for node in _iter_ld_nodes(data):
            if not _is_product(node):
                continue
            name = name or str(node.get("name") or "").strip()
            description = description or str(node.get("description") or "").strip()
            images.extend(_ld_images(node.get("image")))
            props = node.get("additionalProperty") or []
            for prop in props if isinstance(props, list) else [props]:
                if isinstance(prop, dict) and prop.get("name") and prop.get("value") not in (None, ""):
                    specs.setdefault(str(prop["name"]).strip(), str(prop["value"]).strip())
            for variant in node.get("hasVariant") or []:
                if isinstance(variant, dict):
                    images.extend(_ld_images(variant.get("image")))

    meta = parser.meta

    def first(*keys):
        for key in keys:
            for value in meta.get(key, []):
                if value:
                    return value
        return ""

    name = name or first("og:title", "twitter:title") or parser.h1.strip() or _clean_title(parser.title)
    name = html.unescape(re.sub(r"\s+", " ", name)).strip()

    # Prefer a rich on-page description block when it is clearly longer than
    # the (often truncated) structured-data/meta description.
    meta_desc = description or first("og:description", "description", "twitter:description")
    best_block = max(parser.description_blocks, key=plain_length, default="")
    if plain_length(best_block) > max(80, plain_length(meta_desc) * 1.2) or not meta_desc:
        description = best_block
    else:
        description = meta_desc
    description = sanitize_description(description, base_url)

    images.extend(meta.get("og:image", []))
    images.extend(meta.get("og:image:secure_url", []))
    images.extend(meta.get("twitter:image", []))
    images.extend(meta.get("image_src", []))
    images.extend(parser.gallery_images)

    for label, value in parser.spec_rows:
        specs.setdefault(label, value)

    return {
        "name": name,
        "description": description,
        "images": normalize_images(images, base_url),
        "specs": specs,
        "meta_description": html.unescape(re.sub(r"\s+", " ", meta_desc or "")).strip(),
        "og_image": next(iter(normalize_images(
            meta.get("og:image", []) + meta.get("og:image:secure_url", []), base_url)), ""),
    }


def normalize_images(urls, base_url):
    seen, out = set(), []
    for url in urls:
        url = html.unescape((url or "").strip())
        if not url or url.startswith("data:"):
            continue
        if url.startswith("//"):
            url = "https:" + url
        url = urljoin(base_url, url)
        parts = urlsplit(url)
        path = parts.path.lower()
        if parts.scheme not in ("http", "https"):
            continue
        if path.endswith((".svg", ".gif")) or any(b in path for b in IMAGE_BLOCKLIST):
            continue
        # Dedupe on path without size suffixes (e.g. _100x100, -300x300, @2x).
        key = re.sub(r"([_-]\d+x\d*|@\dx)(?=\.\w+$)", "", parts.netloc + parts.path)
        if key in seen:
            continue
        seen.add(key)
        out.append(url)
    return out


# ── SEO + description images ──────────────────────────────────────────────


def html_to_text(fragment):
    text = re.sub(r"<(?!/?(?:p|li|br)\b)[^>]+>", " ", fragment or "")
    text = re.sub(r"</?(?:p|li|br)\b[^>]*>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _truncate(text, limit):
    if len(text) <= limit:
        return text
    cut = text[:limit]
    stop = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
    if stop >= limit * 0.6:
        return cut[: stop + 1]
    return cut.rsplit(" ", 1)[0].rstrip(" ,;:-") + "…"


def build_meta_title(name, brand=""):
    """<= 60 chars, e.g. 'Anker 20W Charger Price in Bangladesh'."""
    name = re.sub(r"\s+", " ", name or "").strip()
    if brand and brand.lower() not in name.lower():
        name = f"{brand} {name}"
    suffix = " Price in Bangladesh"
    if len(name) + len(suffix) <= 60:
        return name + suffix
    return _truncate(name, 60) if len(name) > 60 else name


def build_meta_description(description_html, fallback="", name="", brand=""):
    text = html_to_text(description_html) or (fallback or "").strip()
    if not text:
        by = f" by {brand}" if brand else ""
        text = f"Buy {name}{by} online in Bangladesh at the best price. Cash on delivery available."
    return _truncate(text, 155)


IMG_SRC_RE = re.compile(r'(<img src=")([^"]*)(")')


def localize_description_images(description, product, page_url, limit, skip_urls=()):
    """Download <img> files in a sanitized description into media storage and
    rewrite their src to the stored copy. Images that fail are removed.
    Returns (html, saved_count)."""
    state = {"n": 0}
    skip = {re.sub(r"([_-]\d+x\d*|@\dx)(?=\.\w+$)", "", u.split("?")[0]) for u in skip_urls}

    def replace(match):
        url = html.unescape(match.group(2))
        if state["n"] >= limit or re.sub(r"([_-]\d+x\d*|@\dx)(?=\.\w+$)", "", url.split("?")[0]) in skip:
            return match.group(1) + "\0" + match.group(3)
        try:
            content, ext = download_image(url, referer=page_url)
        except Exception:
            return match.group(1) + "\0" + match.group(3)
        name = default_storage.save(
            f"products/description/{product.slug}/{state['n']}{ext}", ContentFile(content)
        )
        state["n"] += 1
        return match.group(1) + html.escape(default_storage.url(name), quote=True) + match.group(3)

    out = IMG_SRC_RE.sub(replace, description)
    # Drop any <img> (and an emptied <p> wrapper) whose src was marked for removal.
    out = re.sub(r'<img src="\0"[^>]*>', "", out)
    out = re.sub(r"<p>\s*</p>", "", out)
    return out, state["n"]


# ── Networking ────────────────────────────────────────────────────────────


def http_get(url, accept, referer=None, timeout=20, retries=1):
    headers = dict(BASE_HEADERS, Accept=accept)
    if referer:
        headers["Referer"] = referer
    last_exc = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read(), resp.headers.get_content_type(), resp.headers.get_content_charset()
        except urllib.error.HTTPError as exc:
            last_exc = exc
            if exc.code in (400, 401, 403, 404, 410):
                break
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_exc = exc
        if attempt < retries:
            time.sleep(2)
    raise last_exc


def fetch_page(url):
    body, ctype, charset = http_get(url, PAGE_ACCEPT)
    if ctype and "html" not in ctype and "xml" not in ctype:
        raise ValueError(f"not an HTML page ({ctype})")
    return body.decode(charset or "utf-8", errors="replace")


def download_image(url, referer):
    body, ctype, _ = http_get(url, IMAGE_ACCEPT, referer=referer, timeout=30)
    if not ctype or not ctype.startswith("image/") or ctype in ("image/svg+xml", "image/gif"):
        raise ValueError(f"not a usable image ({ctype})")
    if len(body) < MIN_IMAGE_BYTES:
        raise ValueError(f"too small ({len(body)} bytes)")
    ext = {"image/jpeg": ".jpg", "image/jpg": ".jpg", "image/png": ".png",
           "image/webp": ".webp", "image/avif": ".avif"}.get(ctype)
    ext = ext or mimetypes.guess_extension(ctype) or Path(urlsplit(url).path).suffix or ".jpg"
    return body, ext


# ── Command ───────────────────────────────────────────────────────────────


def _valid_url(url):
    return url.lower().startswith(("http://", "https://"))


TRACKING_PARAMS = {"srsltid", "fbclid", "gclid", "ref", "ref_src", "mc_cid", "mc_eid"}


def clean_url(url):
    """Drops tracking query parameters (srsltid, utm_*, fbclid, ...)."""
    parts = urlsplit(url.strip())
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if k.lower() not in TRACKING_PARAMS and not k.lower().startswith("utm_")]
    return urlunsplit(parts._replace(query=urlencode(query), fragment=""))


def _is_header(ref, url):
    return not ref.isdigit() and not _valid_url(url)


def parse_input(path):
    """Returns ([(ref, url)], errors). ref is a product ID or SKU string.

    Accepts a .csv with an id or sku column plus a url column, or text lines
    of 'ID: URL'.
    """
    entries, errors = [], []
    p = Path(path)
    if p.suffix.lower() == ".csv":
        with p.open(newline="", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh)
            for lineno, row in enumerate(reader, 2):
                row = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
                ref = row.get("id") or row.get("sku")
                url = row.get("url") or row.get("source_url") or row.get("link") or ""
                if not ref and not url:
                    continue
                if not ref or not _valid_url(url):
                    errors.append(f"line {lineno}: need an id or sku and a valid url")
                    continue
                entries.append((ref, clean_url(url)))
        return _dedupe(entries, errors)

    for lineno, raw in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        pid, sep, url = line.partition(":")
        pid, url = pid.strip(), url.strip()
        if sep and _is_header(pid, url) and not entries:
            continue  # header row such as 'ID: Product_Link'
        if not sep or not pid.isdigit() or not _valid_url(url):
            errors.append(f"line {lineno}: cannot parse '{line}' (expected 'ID: https://...')")
            continue
        entries.append((pid, clean_url(url)))
    return _dedupe(entries, errors)


def _dedupe(entries, errors):
    """Keeps the last link for a repeated product reference."""
    last = {}
    for ref, url in entries:
        if ref in last and last[ref] != url:
            errors.append(f"{ref} appears more than once; using the last link")
        last[ref] = url
    return list(last.items()), errors


class Command(BaseCommand):
    help = (
        "Scrape description, images and specs from product links ('ID: URL' "
        "lines or a CSV with id/sku + url columns). By default only missing "
        "data is filled; use --overwrite to replace existing name, description, "
        "specs and gallery images."
    )

    def add_arguments(self, parser):
        parser.add_argument("file", help="Path to the file with 'ID: URL' lines")
        parser.add_argument("--dry-run", action="store_true",
                            help="Fetch and extract only; do not download images or write to the DB")
        parser.add_argument("--only", nargs="+", type=int, metavar="ID",
                            help="Process only these product IDs")
        parser.add_argument("--max-images", type=int, default=6)
        parser.add_argument("--delay", type=float, default=1.5,
                            help="Minimum seconds between requests to the same website (default 1.5)")
        parser.add_argument("--overwrite", action="store_true",
                            help="Replace existing name, description, specs and images (default: fill only what is missing)")
        parser.add_argument("--keep-name", action="store_true", help="With --overwrite: keep product names")
        parser.add_argument("--keep-description", action="store_true",
                            help="With --overwrite: keep product descriptions")
        parser.add_argument("--max-desc-images", type=int, default=10,
                            help="Max images to keep from the description (default 10)")
        parser.add_argument("--no-desc-images", action="store_true",
                            help="Strip images from the description instead of saving them")
        parser.add_argument("--keep-seo", action="store_true",
                            help="Do not touch meta_title, meta_description and og_image")
        parser.add_argument("--resume", action="store_true",
                            help="Skip products already marked ok in the report file (retry only failures)")
        parser.add_argument("--report", default="scrape_report.csv",
                            help="CSV file listing the result for every product (default scrape_report.csv)")

    def handle(self, *args, **opts):
        if not Path(opts["file"]).is_file():
            raise CommandError(f"File not found: {opts['file']}")

        entries, parse_errors = parse_input(opts["file"])
        for err in parse_errors:
            self.stderr.write(self.style.WARNING(f"  skip {err}"))
        if not entries:
            raise CommandError("No valid 'ID: URL' lines to process.")

        by_id = {int(r): u for r, u in entries if r.isdigit()}
        skus = [r for r, _ in entries if not r.isdigit()]
        products = Product.objects.in_bulk(list(by_id))
        by_sku = {p.sku: p for p in Product.objects.filter(sku__in=skus)}
        resolved = []
        for ref, url in entries:
            product = products.get(int(ref)) if ref.isdigit() else by_sku.get(ref)
            resolved.append((ref, product, url))
        if opts["only"]:
            wanted = set(opts["only"])
            resolved = [r for r in resolved if r[1] and r[1].pk in wanted]

        done = set()
        rows = {}
        if opts["resume"] and not opts["dry_run"] and Path(opts["report"]).is_file():
            with open(opts["report"], newline="", encoding="utf-8") as fh:
                for r in csv.DictReader(fh):
                    rows[r["ref"]] = (r["ref"], r["product_id"], r["status"], r["detail"])
                    if r["status"] == "ok":
                        done.add(r["ref"])
            before = len(resolved)
            resolved = [r for r in resolved if r[0] not in done]
            self.stdout.write(f"Resuming: {before - len(resolved)} already done, {len(resolved)} left\n")

        def save_report():
            if opts["dry_run"] or not rows:
                return
            with open(opts["report"], "w", newline="", encoding="utf-8") as fh:
                w = csv.writer(fh)
                w.writerow(["ref", "product_id", "status", "detail"])
                w.writerows(rows.values())

        ok = failed = 0
        failures = []
        last_hit = {}  # host -> time of the previous request
        total = len(resolved)
        mode = "DRY RUN — " if opts["dry_run"] else ""
        self.stdout.write(f"{mode}Processing {total} product link(s)\n")

        for index, (ref, product, url) in enumerate(resolved, 1):
            tag = f"[{index}/{total}]"
            if not product:
                failed += 1
                rows[ref] = (ref, "", "failed", "product not found in DB")
                failures.append((ref, "product not found in DB"))
                self.stderr.write(self.style.ERROR(f"{tag} ✗ {ref}: product not found in DB"))
                save_report()
                continue
            # Wait only if the previous request to this same site was too recent.
            host = urlsplit(url).netloc.lower()
            wait = opts["delay"] - (time.monotonic() - last_hit.get(host, -1e9))
            if wait > 0:
                time.sleep(wait)
            try:
                summary = self.process(product, url, opts)
            except Exception as exc:  # one bad site must not stop the run
                last_hit[host] = time.monotonic()
                failed += 1
                rows[ref] = (ref, product.pk, "failed", str(exc))
                failures.append((product.pk, str(exc)))
                self.stderr.write(self.style.ERROR(f"{tag} ✗ #{product.pk} {url}: {exc}"))
                save_report()
                continue
            last_hit[host] = time.monotonic()
            ok += 1
            rows[ref] = (ref, product.pk, "ok", summary.splitlines()[0])
            self.stdout.write(self.style.SUCCESS(f"{tag} ✓ #{product.pk} {summary}"))
            save_report()

        if rows and not opts["dry_run"]:
            self.stdout.write(f"Report written to {opts['report']}")

        self.stdout.write(f"\nDone: {ok} updated, {failed} failed, {len(parse_errors)} input warning(s).")
        if failures:
            self.stdout.write("Failed products (fix the link or upload manually, then re-run with --resume):")
            for pid, reason in failures:
                self.stdout.write(f"  #{pid}: {reason}")

    def process(self, product, url, opts):
        overwrite = opts["overwrite"]
        page = fetch_page(url)
        data = extract_product(page, url)

        name = data["name"][:255] if overwrite and not opts["keep_name"] else ""
        has_desc = plain_length(product.description) > 0
        description = data["description"] if (overwrite and not opts["keep_description"]) or not has_desc else ""
        specs = data["specs"]
        if not overwrite:
            existing = {k.lower() for k in (product.attributes or {})}
            specs = {k: v for k, v in specs.items() if k.lower() not in existing}
        want_images = overwrite or not product.images.exists()
        image_urls = data["images"] if want_images else []

        seo_wanted = not opts["keep_seo"]
        final_name = name or product.name
        final_desc = description or product.description
        fill_title = seo_wanted and (overwrite or not product.meta_title)
        fill_meta_desc = seo_wanted and (overwrite or not product.meta_description)
        fill_og = seo_wanted and (overwrite or not product.og_image)
        meta_title = build_meta_title(final_name, product.brand) if fill_title else ""
        meta_desc = (build_meta_description(final_desc, data["meta_description"], final_name, product.brand)
                     if fill_meta_desc else "")

        if not (name or description or image_urls or specs):
            if want_images or not has_desc or data["specs"]:
                raise ValueError("nothing found on page (blocked or JavaScript-rendered?)")
            return f"{product.name} — already complete, skipped"

        if opts["dry_run"]:
            lines = [
                f"{product.name!r} → {name or '(name unchanged)'!r}",
                f"    description: {plain_length(description)} chars" if description else "    description: (unchanged)",
                f"    specs: {len(specs)} found" + "".join(f"\n      {k}: {v}" for k, v in list(specs.items())[:8]),
                f"    description images: {description.count('<img ')}"
                + (" (stripped: --no-desc-images)" if opts["no_desc_images"] else ""),
                f"    meta_title: {meta_title or '(unchanged)'}",
                f"    meta_description: {meta_desc or '(unchanged)'}",
                f"    og_image: {(data['og_image'] or 'first gallery image') if fill_og else '(unchanged)'}",
                f"    images found: {len(image_urls)} (would use {min(len(image_urls), opts['max_images'])})",
            ]
            lines += [f"      {u}" for u in image_urls[: opts["max_images"]]]
            return "\n".join(lines)

        # Download first so a product keeps its old images if every download fails.
        downloaded, image_errors = [], []
        for img_url in image_urls:
            if len(downloaded) >= opts["max_images"]:
                break
            try:
                downloaded.append(download_image(img_url, referer=url))
            except Exception as exc:
                image_errors.append(f"{img_url}: {exc}")

        alt = name or product.name

        desc_images = 0
        if description:
            if opts["no_desc_images"]:
                description = re.sub(r"<img [^>]*>", "", description)
                description = re.sub(r"<p>\s*</p>", "", description)
            else:
                description, desc_images = localize_description_images(
                    description, product, url, opts["max_desc_images"], skip_urls=image_urls
                )

        og_file = None
        if fill_og:
            for cand in ([data["og_image"]] if data["og_image"] else []):
                try:
                    og_file = download_image(cand, referer=url)
                    break
                except Exception:
                    pass
            if og_file is None and downloaded:
                og_file = downloaded[0]

        with transaction.atomic():
            update_fields = ["updated_at"]
            if name:
                product.name = name
                update_fields.append("name")
            if description:
                product.description = description
                update_fields.append("description")
            if specs:
                merged = dict(product.attributes or {})
                merged.update(specs)
                product.attributes = merged
                update_fields.append("attributes")
            if description:
                # keep meta description in sync with the new description text
                if fill_meta_desc:
                    meta_desc = build_meta_description(
                        description, data["meta_description"], final_name, product.brand)
            if meta_title:
                product.meta_title = meta_title
                update_fields.append("meta_title")
            if meta_desc:
                product.meta_description = meta_desc
                update_fields.append("meta_description")
            if og_file:
                product.og_image.save(f"og{og_file[1]}", ContentFile(og_file[0]), save=False)
                update_fields.append("og_image")
            product.save(update_fields=update_fields)

            removed = 0
            if downloaded:
                if overwrite:
                    for old in list(product.images.all()):
                        old.image.delete(save=False)
                        old.delete()
                        removed += 1
                for i, (content, ext) in enumerate(downloaded):
                    ProductImage.objects.create(
                        product=product,
                        image=ContentFile(content, name=f"{i}{ext}"),
                        alt_text=alt[:255],
                        is_primary=(i == 0),
                        sort_order=i,
                    )

        msg = (f"{product.name} — {len(downloaded)} new image(s), {removed} old removed, "
               f"{len(specs)} spec(s), description {'set' if description else 'kept'}"
               f" ({desc_images} image(s)), SEO {'set' if (meta_title or meta_desc or og_file) else 'kept'}")
        if want_images and not downloaded:
            msg += " (no image downloaded)"
        if image_errors:
            msg += "".join(f"\n    image skipped: {e}" for e in image_errors)
        return msg
