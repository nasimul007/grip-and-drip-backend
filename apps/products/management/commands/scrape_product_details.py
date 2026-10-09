import html
import json
import mimetypes
import re
import time
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from django.core.files.base import ContentFile
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

    def __init__(self):
        super().__init__(convert_charrefs=True)
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

    def handle_startendtag(self, tag, attrs):
        if tag in self.BREAKS:
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
    r"</?(p|br|ul|ol|li|div|span|strong|b|em|i|h[1-6]|table|tr|td|section)\b[^>]*>", re.I
)


def sanitize_description(raw):
    if not raw:
        return ""
    raw = raw.strip()
    if not HTML_TAG_RE.search(raw):
        # Plain text (JSON-LD/meta), possibly entity-encoded: one paragraph per line.
        paras = [p.strip() for p in re.split(r"\r?\n+", raw) if p.strip()]
        return "".join(f"<p>{html.escape(html.unescape(p), quote=False)}</p>" for p in paras)
    parser = DescriptionSanitizer()
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
    description = sanitize_description(description)

    images.extend(meta.get("og:image", []))
    images.extend(meta.get("og:image:secure_url", []))
    images.extend(meta.get("twitter:image", []))
    images.extend(meta.get("image_src", []))
    images.extend(parser.gallery_images)

    return {"name": name, "description": description, "images": normalize_images(images, base_url)}


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


def parse_input(path):
    entries, errors = [], []
    for lineno, raw in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        pid, sep, url = line.partition(":")
        url = url.strip()
        if not sep or not pid.strip().isdigit() or not url.lower().startswith(("http://", "https://")):
            errors.append(f"line {lineno}: cannot parse '{line}' (expected 'ID: https://...')")
            continue
        entries.append((int(pid.strip()), url))
    return entries, errors


class Command(BaseCommand):
    help = (
        "Scrape name, description and images from product links "
        "('ID: URL' per line) and overwrite the matching products. "
        "Existing product gallery images are deleted and replaced."
    )

    def add_arguments(self, parser):
        parser.add_argument("file", help="Path to the file with 'ID: URL' lines")
        parser.add_argument("--dry-run", action="store_true",
                            help="Fetch and extract only; do not download images or write to the DB")
        parser.add_argument("--only", nargs="+", type=int, metavar="ID",
                            help="Process only these product IDs")
        parser.add_argument("--max-images", type=int, default=6)
        parser.add_argument("--delay", type=float, default=1.5,
                            help="Seconds to wait between products (default 1.5)")
        parser.add_argument("--keep-name", action="store_true", help="Do not overwrite product names")
        parser.add_argument("--keep-description", action="store_true",
                            help="Do not overwrite product descriptions")

    def handle(self, *args, **opts):
        if not Path(opts["file"]).is_file():
            raise CommandError(f"File not found: {opts['file']}")

        entries, parse_errors = parse_input(opts["file"])
        for err in parse_errors:
            self.stderr.write(self.style.WARNING(f"  skip {err}"))
        if opts["only"]:
            wanted = set(opts["only"])
            entries = [e for e in entries if e[0] in wanted]
        if not entries:
            raise CommandError("No valid 'ID: URL' lines to process.")

        products = Product.objects.in_bulk([pid for pid, _ in entries])
        ok = failed = 0
        mode = "DRY RUN — " if opts["dry_run"] else ""
        self.stdout.write(f"{mode}Processing {len(entries)} product link(s)\n")

        for index, (pid, url) in enumerate(entries):
            if index:
                time.sleep(opts["delay"])
            product = products.get(pid)
            if not product:
                failed += 1
                self.stderr.write(self.style.ERROR(f"✗ #{pid}: product not found in DB"))
                continue
            try:
                summary = self.process(product, url, opts)
            except Exception as exc:  # one bad site must not stop the run
                failed += 1
                self.stderr.write(self.style.ERROR(f"✗ #{pid} {url}: {exc}"))
                continue
            ok += 1
            self.stdout.write(self.style.SUCCESS(f"✓ #{pid} {summary}"))

        self.stdout.write(f"\nDone: {ok} updated, {failed} failed, {len(parse_errors)} unparsable line(s).")

    def process(self, product, url, opts):
        page = fetch_page(url)
        data = extract_product(page, url)

        name = "" if opts["keep_name"] else data["name"][:255]
        description = "" if opts["keep_description"] else data["description"]
        image_urls = data["images"]

        if not (name or description or image_urls):
            raise ValueError("nothing found on page (blocked or JavaScript-rendered?)")

        if opts["dry_run"]:
            lines = [
                f"{product.name!r} → {name or '(unchanged)'!r}",
                f"    description: {plain_length(description)} chars" if description else "    description: (unchanged)",
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
        with transaction.atomic():
            update_fields = ["updated_at"]
            if name:
                product.name = name
                update_fields.append("name")
            if description:
                product.description = description
                update_fields.append("description")
            product.save(update_fields=update_fields)

            removed = 0
            if downloaded:
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

        msg = f"{product.name} — {len(downloaded)} new image(s), {removed} old removed"
        if not downloaded:
            msg += " (no image downloaded; old images kept)"
        if image_errors:
            msg += "".join(f"\n    image skipped: {e}" for e in image_errors)
        return msg
