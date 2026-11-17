"""Core logic for the Client Audit Lite MCP server.

Standard library only (certifi is used for certificate checks when it is installed). Read-only: it opens only the pages the user names, never writes
anything, stores nothing and needs no keys.

Safety rules (enforced here, covered by tests):
- only http and https, only ports 80 and 443, no credentials inside the URL
- the host is resolved first and every address must be public (no loopback, private,
  link-local, reserved or multicast); the connection goes to that checked address, so a
  DNS answer cannot change between the check and the connection
- every redirect hop is checked again, at most 5 hops
- 10 seconds per read and 20 seconds for the whole request (the address lookup and all redirect
  hops included; a watchdog closes the socket at the deadline), 1.5 MB body cap, no decompression
  (Accept-Encoding: identity)
- a page is decoded only with a normal text charset (TEXT_CHARSETS); any other declared
  charset is ignored and the page is read as UTF-8
- every returned string and list is capped (the MAX_* constants), so a hostile page cannot
  flood the agent with text
- AUDIT_ALLOW_LOCAL=1 switches the address check off. It exists only for the tests and
  is off by default.
"""
from __future__ import annotations

import http.client
import ipaddress
import json
import os
import re
import socket
import ssl
import threading
import time
from html.parser import HTMLParser
from urllib.parse import quote, urljoin, urlsplit

USER_AGENT = "ClientAuditLite/0.1 (read-only page audit; user-requested)"
TIMEOUT = 10          # seconds for one socket read
TOTAL_TIMEOUT = 20    # seconds for the whole request: connect, headers, body and every redirect hop
READ_CHUNK = 16_384
MAX_BYTES = 1_500_000
MAX_REDIRECTS = 5
ALLOWED_PORTS = {80, 443}
AI_AND_SEARCH_BOTS = [
    "*", "Googlebot", "Bingbot", "GPTBot", "ChatGPT-User", "OAI-SearchBot",
    "ClaudeBot", "Claude-User", "PerplexityBot", "Google-Extended", "CCBot",
]


class AuditError(Exception):
    """A problem the user should see in plain words."""


def _too_slow() -> AuditError:
    return AuditError(f"The site took too long to answer (more than {TOTAL_TIMEOUT} seconds in total, "
                      "redirects included), so the page was not read.")


def _allow_local() -> bool:
    return os.environ.get("AUDIT_ALLOW_LOCAL") == "1"


# ---------------------------------------------------------------- address checks
def check_ip(ip: str) -> None:
    addr = ipaddress.ip_address(ip)
    if getattr(addr, "ipv4_mapped", None):
        addr = addr.ipv4_mapped
    if not addr.is_global or addr.is_multicast:
        raise AuditError(f"Blocked: {ip} is not a public internet address, and this tool reads public sites only.")


def _lookup(host: str, port: int, out: list, done: threading.Event) -> None:
    """Runs in a daemon thread. It only appends to its own local list, so after a timeout it cannot
    change anything the request still uses."""
    try:
        out.append((True, socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)))
    except BaseException as exc:  # handed back to the caller, never swallowed
        out.append((False, exc))
    finally:
        done.set()


def resolve_host(host: str, port: int, deadline: float | None = None) -> list[str]:
    """Look up the host's addresses. getaddrinfo cannot be interrupted, so it runs in a daemon thread
    and the wait ends at min(TIMEOUT, the time left before the whole-request deadline)."""
    budget = TIMEOUT if deadline is None else min(TIMEOUT, deadline - time.monotonic())
    out: list = []
    done = threading.Event()
    if budget > 0:
        threading.Thread(target=_lookup, args=(host, port, out, done), daemon=True).start()
    if budget <= 0 or not done.wait(timeout=budget) or not out:
        raise AuditError(f"The site name '{host}' could not be looked up in time, so the page was not read.")
    ok, value = out[0]
    if not ok:
        if isinstance(value, socket.gaierror):
            raise AuditError(f"Could not find the host '{host}' ({value.strerror or value}).") from value
        raise value
    return list(dict.fromkeys(i[4][0] for i in value))


_BARE_HOST = re.compile(r"^[^\s/:?#@\\]+\.[^\s/:?#@\\]+(:\d+)?([/?#]|$)")
_PCT_SAFE = "/%:@!$&'()*+,;=-._~"  # existing %XX escapes are kept


def _with_scheme(url: str) -> str:
    """A bare host such as example.com/page is read as https://example.com/page."""
    u = url.strip()
    if "://" not in u and _BARE_HOST.match(u):
        return "https://" + u
    return u


def validate_url(url: str) -> tuple[str, str, int, str]:
    """Return (scheme, ascii_host, port, percent_encoded_path_and_query) or raise AuditError."""
    if not isinstance(url, str) or not url.strip():
        raise AuditError("Give a page address such as https://example.com/page.")
    parts = urlsplit(_with_scheme(url))
    if parts.scheme not in ("http", "https"):
        raise AuditError("Only http and https addresses are allowed.")
    if parts.username or parts.password:
        raise AuditError("Addresses with a username or password inside are not allowed.")
    if not parts.hostname:
        raise AuditError("The address has no host name.")
    try:
        port = parts.port or (443 if parts.scheme == "https" else 80)
    except ValueError as exc:
        raise AuditError("The address has an invalid port.") from exc
    if not _allow_local() and port not in ALLOWED_PORTS:
        raise AuditError("Only ports 80 and 443 are allowed.")
    try:
        host = parts.hostname.encode("idna").decode("ascii")  # non-Latin host names become punycode
    except UnicodeError as exc:
        raise AuditError("The host name in the address is not valid.") from exc
    path = quote(parts.path or "/", safe=_PCT_SAFE)
    if parts.query:
        path += "?" + quote(parts.query, safe=_PCT_SAFE + "?")
    return parts.scheme, host, port, path


def pick_address(host: str, port: int, deadline: float | None = None) -> str:
    ips = resolve_host(host, port) if deadline is None else resolve_host(host, port, deadline)
    if not _allow_local():
        for ip in ips:
            check_ip(ip)  # every answer must be public, not only the first
    return ips[0]


class _Watchdog:
    """Remembers the sockets of one hop; fire() (run by a threading.Timer at the deadline) shuts
    them down, which interrupts a read that is blocked in another thread."""

    def __init__(self, deadline: float):
        self.deadline = deadline
        self.fired = False
        self._socks: list = []
        self._lock = threading.Lock()

    def connect_timeout(self) -> float:
        """TIMEOUT, or less when the deadline is nearer (a closed socket does not wake a waiting
        select() on every system, so the read timeout itself also ends at the deadline)."""
        return max(0.01, min(TIMEOUT, self.deadline - time.monotonic()))

    def add(self, sock) -> None:
        with self._lock:
            self._socks.append(sock)
            fired = self.fired
        if fired:
            self._kill(sock)

    def fire(self) -> None:
        with self._lock:
            self.fired = True
            socks = list(self._socks)
        for s in socks:
            self._kill(s)

    @staticmethod
    def _kill(sock) -> None:
        try:  # the plain socket method, so an SSL socket is cut at the TCP level too
            socket.socket.shutdown(sock, socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            socket.socket.close(sock)
        except OSError:
            pass


def _connect(ip: str, port: int, host: str, https: bool, watch: _Watchdog | None = None) -> http.client.HTTPConnection:
    """Open a connection to the already checked address."""
    timeout = watch.connect_timeout() if watch else TIMEOUT
    sock = socket.create_connection((ip, port), timeout=timeout)
    if watch:
        watch.add(sock)
        sock.settimeout(watch.connect_timeout())
    conn = http.client.HTTPConnection(host, port, timeout=TIMEOUT)
    if https:
        try:
            sock = _tls_context().wrap_socket(sock, server_hostname=host)
        except ssl.SSLCertVerificationError:
            # some Python installs cannot find the system certificate store; retry once with the
            # certifi bundle. Certificate checking is never switched off.
            sock.close()
            ctx2 = _certifi_context()
            if ctx2 is None:
                raise
            sock = socket.create_connection((ip, port), timeout=watch.connect_timeout() if watch else TIMEOUT)
            if watch:
                watch.add(sock)
                sock.settimeout(watch.connect_timeout())
            sock = ctx2.wrap_socket(sock, server_hostname=host)
        if watch:
            watch.add(sock)
    conn.sock = sock
    return conn


def _tls_context() -> ssl.SSLContext:
    return ssl.create_default_context()


def _certifi_context():
    try:
        import certifi
    except ImportError:
        return None
    return ssl.create_default_context(cafile=certifi.where())


# --------------------------------------------------------------------- fetching
def fetch(url: str, accept: str = "text/html,application/xhtml+xml;q=0.9,*/*;q=0.5") -> dict:
    """GET one page, following at most MAX_REDIRECTS checked redirects. The whole request, every
    hop and every address lookup included, must finish within TOTAL_TIMEOUT seconds (one shared
    deadline; resolve_host waits only for the time left): a threading.Timer per hop shuts the
    socket down at the deadline (a blocked read is really interrupted), and the clock is checked
    again between body chunks."""
    deadline = time.monotonic() + TOTAL_TIMEOUT
    chain: list[dict] = []
    current = _with_scheme(url) if isinstance(url, str) else url
    for _ in range(MAX_REDIRECTS + 1):
        scheme, host, port, path = validate_url(current)
        ip = pick_address(host, port, deadline)  # the address lookup counts toward the deadline
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise _too_slow()
        conn = None
        watch = _Watchdog(deadline)
        timer = threading.Timer(remaining, watch.fire)
        timer.daemon = True
        timer.start()
        try:
            conn = _connect(ip, port, host, scheme == "https", watch)
            default_port = 443 if scheme == "https" else 80
            host_header = host if port == default_port else f"{host}:{port}"
            conn.request("GET", path, headers={
                "Host": host_header, "User-Agent": USER_AGENT, "Accept": accept,
                "Accept-Encoding": "identity", "Connection": "close",
            })
            resp = conn.getresponse()
            status = resp.status
            headers = {k.lower(): v for k, v in resp.getheaders()}
            x_robots = [v for k, v in resp.getheaders() if k.lower() == "x-robots-tag"]
            if status in (301, 302, 303, 307, 308) and "location" in headers:
                loc = headers["location"]
                try:  # raw UTF-8 bytes in a Location header arrive decoded as latin-1
                    loc = loc.encode("latin-1").decode("utf-8")
                except UnicodeError:
                    pass
                nxt = urljoin(current, loc)
                chain.append({"url": current, "status": status, "to": nxt})
                current = nxt
                continue
            chunks: list[bytes] = []
            size = 0
            while size <= MAX_BYTES:
                if watch.fired or time.monotonic() >= deadline:
                    raise _too_slow()
                chunk = resp.read(min(READ_CHUNK, MAX_BYTES + 1 - size))
                if not chunk:
                    break
                chunks.append(chunk)
                size += len(chunk)
            if watch.fired:  # the watchdog cut the socket, so what was read may be incomplete
                raise _too_slow()
            body = b"".join(chunks)
        except ssl.SSLCertVerificationError as exc:
            raise AuditError("The site's security certificate could not be verified, so the page was not read.") from exc
        except (OSError, http.client.HTTPException, UnicodeError, ValueError) as exc:
            if watch.fired or time.monotonic() >= deadline:
                raise _too_slow() from exc
            raise AuditError(f"Could not fetch the page: {exc}") from exc
        finally:
            timer.cancel()
            if conn is not None:
                conn.close()
        truncated = len(body) > MAX_BYTES
        return {
            "final_url": current, "status": status, "headers": headers, "x_robots_tags": x_robots,
            "body": body[:MAX_BYTES], "truncated": truncated, "redirects": chain,
        }
    raise AuditError(f"The address redirects more than {MAX_REDIRECTS} times, so the page was not read.")


# ----------------------------------------------------------------- HTML parsing
ROBOTS_META_NAMES = ("robots", "googlebot", "bingbot", "googlebot-news")

# Output caps: every string and list returned to the agent is cut to these sizes (counts and lengths
# are still the real ones), and output_truncated is set to true whenever something was cut.
MAX_TITLE_CHARS = 300
MAX_META_DESCRIPTION_CHARS = 600
MAX_HEADING_CHARS = 200
MAX_HEADINGS_PER_LEVEL = 20
MAX_ROBOTS_DIRECTIVES = 20
MAX_DIRECTIVE_VALUE_CHARS = 200
MAX_X_ROBOTS_CHARS = 500
MAX_JSON_LD_BLOCKS = 20
MAX_JSON_LD_TYPES = 20
MAX_JSON_LD_TYPE_CHARS = 100
MAX_SNIPPET_CHARS = 200
MAX_SITEMAPS = 10
MAX_SITEMAP_CHARS = 300
MAX_REDIRECT_ENTRIES = 6
MAX_REDIRECT_URL_CHARS = 300
MAX_OPEN_GRAPH_CHARS = 300
MAX_URL_CHARS = 500          # canonical, final_url, requested_url, robots_url, page_path
MAX_RULE_TEXT_CHARS = 200
MAX_SHORT_FIELD_CHARS = 300  # content_type, lang, meta_robots, viewport
MAX_OUTPUT_CHARS = 60_000    # JSON size of one whole result

OUTLINE_MAX = MAX_HEADINGS_PER_LEVEL
TEXT_PREVIEW_CHARS = 400


class _Page(HTMLParser):
    def __init__(self, base: str):
        super().__init__(convert_charrefs=True)
        self.base = base
        self.host = urlsplit(base).hostname or ""
        self.lang = None
        self.title = None
        self._in_title = False
        self._capture_title = False
        self._in_head = False
        self._head_closed = False
        self._in_body = False
        self._svg = 0
        self._skip = 0
        self._json_ld_buf: list[str] | None = None
        self.meta: dict[str, str] = {}
        self.robots_meta: list[tuple[str, str]] = []
        self.canonical = None
        self.hreflang = 0
        self.headings: dict[str, list[str]] = {"h1": [], "h2": [], "h3": []}
        self.heading_counts: dict[str, int] = {f"h{i}": 0 for i in range(1, 7)}
        self.outline_truncated = False
        self._head_tag = None
        self._head_buf: list[str] = []
        self.words = 0
        self.img_total = 0
        self.img_no_alt = 0
        self.img_no_alt_srcs: list[str] = []
        self.links_internal = 0
        self.links_external = 0
        self.json_ld_raw: list[str] = []
        self._text: list[str] = []
        self._text_len = 0

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag in self.heading_counts:
            self.heading_counts[tag] += 1
        if tag == "html":
            self.lang = a.get("lang") or None
        elif tag == "head":
            self._in_head = True
        elif tag == "body":
            self._in_head, self._in_body = False, True
        elif tag == "svg":
            self._svg += 1
        elif tag == "title":
            self._in_title = True
            # only the first <title> of the document head counts, never one inside <svg> or the body
            if self.title is None and self._svg == 0 and not self._in_body and not self._head_closed:
                self._capture_title = True
                self.title = ""
        elif tag == "meta":
            key = (a.get("name") or a.get("property") or "").lower()
            if key and "content" in a:
                self.meta.setdefault(key, a["content"])
                if key in ROBOTS_META_NAMES:
                    self.robots_meta.append((key, a["content"]))
        elif tag == "link":
            rel = a.get("rel", "").lower().split()
            if "canonical" in rel and self.canonical is None:
                self.canonical = urljoin(self.base, a.get("href", ""))
            if "alternate" in rel and a.get("hreflang"):
                self.hreflang += 1
        elif tag in ("script", "style", "noscript"):
            self._skip += 1
            if tag == "script" and "ld+json" in a.get("type", "").lower():
                self._json_ld_buf = []
        elif tag in self.headings:
            self._head_tag, self._head_buf = tag, []
        elif tag == "img":
            self.img_total += 1
            if "alt" not in a:
                self.img_no_alt += 1
                if len(self.img_no_alt_srcs) < 20:
                    self.img_no_alt_srcs.append(a.get("src", "")[:200])
        elif tag == "a" and a.get("href"):
            href = a["href"].strip()
            if href.startswith(("#", "mailto:", "tel:", "javascript:")):
                return
            target = urlsplit(urljoin(self.base, href))
            if target.hostname and target.hostname != self.host:
                self.links_external += 1
            else:
                self.links_internal += 1

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
            self._capture_title = False
        elif tag == "head":
            self._in_head, self._head_closed = False, True
        elif tag == "svg":
            self._svg = max(0, self._svg - 1)
        elif tag in ("script", "style", "noscript"):
            self._skip = max(0, self._skip - 1)
            if tag == "script" and self._json_ld_buf is not None:
                self.json_ld_raw.append("".join(self._json_ld_buf))
                self._json_ld_buf = None
        elif tag == self._head_tag:
            text = " ".join("".join(self._head_buf).split())
            if len(self.headings[tag]) < OUTLINE_MAX:
                self.headings[tag].append(text)
            else:
                self.outline_truncated = True
            self._head_tag = None

    def handle_data(self, data):
        if self._capture_title:
            self.title += data
        if self._json_ld_buf is not None:
            self._json_ld_buf.append(data)
        if self._head_tag:
            self._head_buf.append(data)
        if not self._skip and not self._in_title:
            self.words += len(re.findall(r"\w+", data, re.UNICODE))
            if not self._in_head and self._text_len <= TEXT_PREVIEW_CHARS:
                chunk = " ".join(data.split())
                if chunk:
                    self._text.append(chunk)
                    self._text_len += len(chunk) + 1

    def text_preview(self) -> str:
        return " ".join(self._text)[:TEXT_PREVIEW_CHARS]


_LONE_SURROGATE = re.compile(r"[\ud800-\udfff]")


class _Cutter:
    """Cuts strings and lists to a cap and remembers whether anything was cut."""

    def __init__(self):
        self.cut = False

    def text(self, value, limit: int):
        if isinstance(value, str):
            if len(value) > limit:
                self.cut = True
                value = value[:limit]
            # a lone surrogate (a JSON-LD "\ud800" escape) cannot be written as UTF-8 and would break the result
            value = _LONE_SURROGATE.sub("\N{REPLACEMENT CHARACTER}", value)
        return value

    def items(self, values: list, limit: int) -> list:
        if len(values) > limit:
            self.cut = True
            return values[:limit]
        return values


def _json_ld_types(blocks: list[str], cut: _Cutter | None = None) -> list[dict]:
    cut = cut or _Cutter()
    out = []
    for raw in cut.items(blocks, MAX_JSON_LD_BLOCKS):
        try:
            data = json.loads(raw)
        except (ValueError, RecursionError) as exc:  # very deep nesting raises RecursionError
            out.append({"valid_json": False, "error": str(exc)[:120],
                        "snippet": cut.text(" ".join(raw.split()), MAX_SNIPPET_CHARS)})
            continue
        items = data if isinstance(data, list) else data.get("@graph", [data]) if isinstance(data, dict) else []
        if not isinstance(items, list):
            items = [items]
        types = []
        for it in items:
            if isinstance(it, dict):
                t = it.get("@type")
                types.extend(t if isinstance(t, list) else [t] if t else [])
            if len(types) > MAX_JSON_LD_TYPES:
                break
        out.append({"valid_json": True,
                    "types": [cut.text(str(t), MAX_JSON_LD_TYPE_CHARS) for t in cut.items(types, MAX_JSON_LD_TYPES)]})
    return out


def _shrink(value, list_max: int, str_max: int, keep: tuple = ()):
    """Cut every list and string inside a result further (used only when it is still too big)."""
    if isinstance(value, dict):
        return {k: (v if k in keep else _shrink(v, list_max, str_max, keep)) for k, v in value.items()}
    if isinstance(value, list):
        return [_shrink(v, list_max, str_max, keep) for v in value[:list_max]]
    if isinstance(value, str):
        return value[:str_max]
    return value


def _fit(result: dict, cut: _Cutter, keep: tuple = ()) -> dict:
    """Final guard: the JSON of a result stays under MAX_OUTPUT_CHARS; output_truncated marks any cut."""
    for list_max, str_max in ((10, 200), (5, 100), (3, 50), (1, 20)):
        if len(json.dumps(result, ensure_ascii=False)) <= MAX_OUTPUT_CHARS:
            break
        cut.cut = True
        result = _shrink(result, list_max, str_max, keep)
    if cut.cut:
        result["output_truncated"] = True
    return result


_CHARSET = re.compile(r"""charset\s*=\s*["']?\s*([A-Za-z0-9_.:-]+)""", re.I)
_META_CHARSET = re.compile(rb"""<meta[^>]+charset\s*=\s*["']?\s*([A-Za-z0-9_.:-]+)""", re.I)


# The only charsets a page is decoded with: declared name (lower case, _ read as -) -> Python codec.
# Anything else (punycode, idna, rot13, zlib, base64 ... and unknown names) is ignored and the page
# is read as UTF-8: some of those codecs are not text encodings and can take minutes on a large page.
TEXT_CHARSETS = {
    "utf-8": "utf-8", "utf8": "utf-8", "ascii": "ascii", "us-ascii": "ascii",
    "latin-1": "latin-1", "latin1": "latin-1", "l1": "latin-1",
    **{f"iso-8859-{i}": f"iso8859_{i}" for i in range(1, 17) if i != 12},
    **{f"iso8859-{i}": f"iso8859_{i}" for i in range(1, 17) if i != 12},
    **{f"windows-{n}": f"cp{n}" for n in range(1250, 1259)},
    **{f"cp{n}": f"cp{n}" for n in range(1250, 1259)},
    "gbk": "gbk", "gb2312": "gb2312", "gb18030": "gb18030", "big5": "big5",
    "shift-jis": "shift_jis", "sjis": "shift_jis", "euc-jp": "euc_jp", "euc-kr": "euc_kr",
    "koi8-r": "koi8_r", "koi8-u": "koi8_u",
    "utf-16": "utf-16",  # only used when the body starts with a byte order mark
}
MAX_CHARSET_NAME_CHARS = 40


def _decode_text(body: bytes, declared: str) -> str | None:
    """Decode with an allowlisted charset only; None when the name is not allowed."""
    codec = TEXT_CHARSETS.get(declared.strip().lower().replace("_", "-"))
    if codec is None:
        return None
    if codec == "utf-16" and not body.startswith((b"\xff\xfe", b"\xfe\xff")):
        return None
    return body.decode(codec, errors="replace")


def _decode(body: bytes, ctype: str) -> tuple[str, str, str | None]:
    """Decode with the charset from Content-Type, else <meta charset>, else UTF-8 (bad bytes replaced).
    Returns (text, charset used, note or None); the note says when a declared charset was not used."""
    names = []
    m = _CHARSET.search(ctype or "")
    if m:
        names.append(m.group(1))
    m = _META_CHARSET.search(body[:4096])
    if m:
        names.append(m.group(1).decode("ascii"))
    skipped = []
    for name in names:
        text = _decode_text(body, name)
        if text is not None:
            used = name.lower()[:MAX_CHARSET_NAME_CHARS]
            return text, used, _charset_note(skipped, used)
        skipped.append(name[:MAX_CHARSET_NAME_CHARS])
    return body.decode("utf-8", errors="replace"), "utf-8", _charset_note(skipped, "utf-8")


def _charset_note(skipped: list[str], used: str) -> str | None:
    if not skipped:
        return None
    return (f"The page declares charset '{skipped[0]}', which is not a normal text encoding this tool reads "
            f"(or is utf-16 without a byte order mark), so it was not used; the page was read as {used}.")


_VALUED_DIRECTIVES = ("unavailable_after", "max-snippet", "max-image-preview", "max-video-preview")


def _robots_directives(meta: list[tuple[str, str]], headers: list[str]) -> tuple[bool, bool, list[dict]]:
    """Combine every robots-type meta tag and X-Robots-Tag header. 'none' means noindex and nofollow."""
    found: list[dict] = []
    tokens: list[str] = []
    for name, content in meta:
        found.append({"source": f'meta name="{name}"', "value": content})
        tokens += [t.strip().lower() for t in content.split(",")]
    for value in headers:
        found.append({"source": "X-Robots-Tag header", "value": value})
        agent = None
        # "unavailable_after: Fri, 25 Jun 2027 15:00:00 GMT" has a comma inside the date: collapse it first
        value = re.sub(r"unavailable_after\s*:[^,]*(?:,\s*\d[^,]*)?", "unavailable_after: date", value, flags=re.I)
        for t in value.split(","):
            t = t.strip().lower()
            if ":" in t and t.split(":", 1)[0].strip() not in _VALUED_DIRECTIVES:
                agent, t = (s.strip() for s in t.split(":", 1))
            if agent is None or agent in ROBOTS_META_NAMES:
                tokens.append(t)
    noindex = any(t in ("noindex", "none") for t in tokens)
    nofollow = any(t in ("nofollow", "none") for t in tokens)
    return noindex, nofollow, found


def page_facts(url: str) -> dict:
    """Everything an audit needs from one page, as facts (nothing is judged here)."""
    r = fetch(url)
    cut = _Cutter()
    ctype = r["headers"].get("content-type", "")
    redirects = [{"url": cut.text(h["url"], MAX_REDIRECT_URL_CHARS), "status": h["status"],
                  "to": cut.text(h["to"], MAX_REDIRECT_URL_CHARS)}
                 for h in cut.items(r["redirects"], MAX_REDIRECT_ENTRIES)]
    facts: dict = {
        "requested_url": cut.text(url, MAX_URL_CHARS), "final_url": cut.text(r["final_url"], MAX_URL_CHARS),
        "status": r["status"], "redirects": redirects, "content_type": cut.text(ctype, MAX_SHORT_FIELD_CHARS),
        "bytes_read": len(r["body"]), "truncated": r["truncated"],
        "x_robots_tag": cut.text(", ".join(r["x_robots_tags"]), MAX_X_ROBOTS_CHARS) or None,
    }
    if "html" not in ctype.lower():
        facts["note"] = "The response is not HTML, so no page details were read."
        return _fit(facts, cut)
    text, charset, charset_note = _decode(r["body"], ctype)
    p = _Page(r["final_url"])
    p.feed(text)
    p.close()
    meta_robots = p.meta.get("robots", "")
    noindex, nofollow, directives = _robots_directives(p.robots_meta, r["x_robots_tags"])
    directives = [{"source": d["source"], "value": cut.text(d["value"], MAX_DIRECTIVE_VALUE_CHARS)}
                  for d in cut.items(directives, MAX_ROBOTS_DIRECTIVES)]
    title = " ".join((p.title or "").split())
    description = p.meta.get("description", "")
    headings = {level: [cut.text(t, MAX_HEADING_CHARS) for t in cut.items(texts, MAX_HEADINGS_PER_LEVEL)]
                for level, texts in p.headings.items()}
    facts.update({
        "charset": charset,
        "lang": cut.text(p.lang, MAX_SHORT_FIELD_CHARS),
        "title": cut.text(title, MAX_TITLE_CHARS) or None,
        "title_length": len(title),
        "meta_description": cut.text(description, MAX_META_DESCRIPTION_CHARS) or None,
        "meta_description_length": len(description),
        "meta_robots": cut.text(meta_robots, MAX_SHORT_FIELD_CHARS) or None,
        "noindex": noindex,
        "nofollow": nofollow,
        "robots_directives": directives,
        "canonical": cut.text(p.canonical, MAX_URL_CHARS),
        "viewport": cut.text(p.meta.get("viewport"), MAX_SHORT_FIELD_CHARS) or None,
        "open_graph": {k: cut.text(v, MAX_OPEN_GRAPH_CHARS) for k, v in p.meta.items()
                       if k.startswith("og:") and k in ("og:title", "og:description", "og:image")},
        "hreflang_links": p.hreflang,
        "h1_count": p.heading_counts["h1"],
        "heading_counts": p.heading_counts,
        "headings": headings,
        "outline_truncated": p.outline_truncated,
        "visible_word_count": p.words,
        "text_preview": p.text_preview(),
        "images_total": p.img_total,
        "images_missing_alt_attribute": p.img_no_alt,
        "images_missing_alt_srcs": p.img_no_alt_srcs,
        "links_internal": p.links_internal,
        "links_external": p.links_external,
        "json_ld_block_count": len(p.json_ld_raw),
        "json_ld_blocks": _json_ld_types(p.json_ld_raw, cut),
    })
    if charset_note:
        facts["charset_note"] = charset_note
    return _fit(facts, cut)



# ------------------------------------------------------------------- robots.txt
def _pct_ascii(s: str) -> str:
    """Percent-encode non-ASCII characters and spaces so rules and paths compare alike."""
    return "".join(c if 32 < ord(c) < 127 else quote(c, safe="") for c in s)


MAX_RULE_LINES = 5000   # Allow/Disallow lines read from one robots.txt; later ones are ignored and reported
MAX_RULE_CHARS = 1000   # a longer rule is treated as non-matching (and counted in the report)


def parse_robots(lines: list[str], info: dict | None = None) -> tuple[list[dict], list[str]]:
    """Groups of {agents, rules}; consecutive User-agent lines share one group (Google's rules).
    After MAX_RULE_LINES rule lines no more groups or rules are read (sitemaps still are), and
    info["rules_ignored_after_cap"] is set to True when an info dict is given."""
    groups: list[dict] = []
    sitemaps: list[str] = []
    cur = None
    last_was_agent = False
    rule_lines = 0
    for n, raw in enumerate(lines, 1):
        line = raw.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        key, val = (s.strip() for s in line.split(":", 1))
        key = key.lower()
        if key == "sitemap":
            sitemaps.append(val)
        elif rule_lines >= MAX_RULE_LINES:
            if key in ("allow", "disallow") and info is not None:
                info["rules_ignored_after_cap"] = True
            continue
        elif key in ("user-agent", "useragent"):
            if cur is None or not last_was_agent:
                cur = {"agents": [], "rules": []}
                groups.append(cur)
            m = re.match(r"[A-Za-z_*-]+", val)
            cur["agents"].append(m.group(0).lower() if m else val.lower())
            last_was_agent = True
        elif key in ("allow", "disallow"):
            last_was_agent = False
            rule_lines += 1
            if cur is not None:
                cur["rules"].append({"allow": key == "allow", "path": _pct_ascii(val), "line": n,
                                     "text": f"{'Allow' if key == 'allow' else 'Disallow'}: {val}"})
    return groups, sitemaps


def _rule_matches(pattern: str, path: str) -> bool:
    """Google's robots.txt matching without a regular expression: * is any run of characters,
    a trailing $ anchors the end, otherwise the rule matches a prefix of the path. Consecutive
    stars collapse; each literal piece is found left-most after the previous one (greedy, so a
    star only ever backtracks to itself). Every step is a plain str.find, so a hostile rule costs
    about len(rule) + len(path) work, never an exponential search."""
    if len(pattern) > MAX_RULE_CHARS:
        return False
    anchored = pattern.endswith("$")
    body = pattern[:-1] if anchored else pattern
    pieces = body.split("*")
    if len(pieces) == 1:  # no star
        return path == body if anchored else path.startswith(body)
    first, last = pieces[0], pieces[-1]
    if not path.startswith(first):
        return False
    pos = len(first)
    for piece in pieces[1:-1]:
        if not piece:  # collapsed **
            continue
        found = path.find(piece, pos)
        if found < 0:
            return False
        pos = found + len(piece)
    if anchored:
        return path.endswith(last) and len(path) - len(last) >= pos
    return path.find(last, pos) >= 0


def _groups_for(groups: list[dict], bot: str) -> tuple[list[dict], str | None]:
    """The groups that apply to a crawler: its own User-agent groups, else the * groups."""
    name = bot.lower()
    chosen = [g for g in groups if name != "*" and name in g["agents"]]
    if chosen:
        return chosen, bot
    chosen = [g for g in groups if "*" in g["agents"]]
    return chosen, ("*" if chosen else None)


def robots_decide(groups: list[dict], bot: str, path: str) -> tuple[bool, dict | None, str | None]:
    """(allowed, deciding rule or None, group used or None), following Google's matching:
    the most specific matching User-agent group (else *), * and $ in rules, the longest matching
    rule wins, Allow wins a tie, an empty Disallow allows everything."""
    chosen, used = _groups_for(groups, bot)
    path = _pct_ascii(path)
    best = None
    for g in chosen:
        for rule in g["rules"]:
            if not rule["path"] or not _rule_matches(rule["path"], path):
                continue
            if (best is None or len(rule["path"]) > len(best["path"])
                    or (len(rule["path"]) == len(best["path"]) and rule["allow"] and not best["allow"])):
                best = rule
    if best is None:
        return True, None, used
    return best["allow"], {"line": best["line"], "text": best["text"]}, used


def robots_report(url: str) -> dict:
    scheme, host, port, path = validate_url(url)
    default_port = 443 if scheme == "https" else 80
    origin = f"{scheme}://{host}" + ("" if port == default_port else f":{port}")
    r = fetch(origin + "/robots.txt", accept="text/plain,*/*;q=0.5")
    cut = _Cutter()
    report: dict = {"robots_url": cut.text(r["final_url"], MAX_URL_CHARS), "status": r["status"],
                    "page_path": cut.text(path, MAX_URL_CHARS), "bots_checked": AI_AND_SEARCH_BOTS}
    if r["status"] == 404 or r["status"] == 410:
        report["summary"] = "No robots.txt: crawlers are allowed everywhere by default."
        report["robots_complete"] = True
        report["rules"] = {b: {"group": None, "status": "ok", "home_allowed": True, "home_rule": None,
                               "this_page_allowed": True, "this_page_rule": None} for b in AI_AND_SEARCH_BOTS}
        return _fit(report, cut, keep=("bots_checked",))
    if r["status"] >= 400:
        report["robots_complete"] = False
        report["summary"] = f"robots.txt returned HTTP {r['status']}; the real crawler behavior is unknown."
        return _fit(report, cut, keep=("bots_checked",))
    lines = r["body"].decode("utf-8", errors="replace").splitlines()
    info: dict = {}
    groups, sitemaps = parse_robots(lines, info)
    # A cap must never turn "unknown" into "allowed": when part of the file was not read (rule-line cap or
    # body cap), or a too-long rule was skipped, an "allowed" answer becomes null (unknown). A Disallow
    # that was read and matches stays a definite "blocked".
    not_fully_read = bool(info.get("rules_ignored_after_cap") or r["truncated"])
    long_rule_groups = [g for g in groups if any(len(rule["path"]) > MAX_RULE_CHARS for rule in g["rules"])]
    rules = {}

    def short(rule):
        return None if rule is None else {"line": rule["line"], "text": cut.text(rule["text"], MAX_RULE_TEXT_CHARS)}

    for b in AI_AND_SEARCH_BOTS:
        home_ok, home_rule, used = robots_decide(groups, b, "/")
        page_ok, page_rule, _ = robots_decide(groups, b, path)
        if not_fully_read:
            status = "unknown_rules_not_fully_read"
        elif any(g in long_rule_groups for g in _groups_for(groups, b)[0]):
            status = "unknown_long_rule_ignored"
        else:
            status = "ok"
        if status != "ok":
            home_ok = None if home_ok else home_ok
            page_ok = None if page_ok else page_ok
        rules[b] = {"group": used, "status": status, "home_allowed": home_ok, "home_rule": short(home_rule),
                    "this_page_allowed": page_ok, "this_page_rule": short(page_rule)}
    report["rules"] = rules
    report["sitemaps"] = [cut.text(s, MAX_SITEMAP_CHARS) for s in cut.items(sitemaps, MAX_SITEMAPS)]
    report["lines"] = len(lines)
    report["truncated"] = r["truncated"]
    if info.get("rules_ignored_after_cap"):
        report["rules_ignored_after_cap"] = True  # only the first MAX_RULE_LINES rule lines were read
    too_long = sum(1 for g in groups for rule in g["rules"] if len(rule["path"]) > MAX_RULE_CHARS)
    if too_long:
        report["rules_too_long_ignored"] = too_long  # treated as non-matching
    report["robots_complete"] = not (not_fully_read or long_rule_groups)
    report["summary"] = ("Read robots.txt. 'allowed' follows Google's matching rules (most specific User-agent group, "
                         "else *; * and $ in rules; longest rule wins; Allow wins a tie). A rule of null means no line "
                         "matched, so the default is allowed. Other crawlers can differ. Crawlers not in bots_checked "
                         "were not tested.")
    if not_fully_read:
        report["summary"] += (" WARNING: robots.txt was NOT fully read (too many rule lines or too large), so access "
                              "for every crawler is unknown: an allowed value of null means unknown, never allowed. "
                              "Only a false (blocked by a rule that was read) is certain.")
    elif long_rule_groups:
        report["summary"] += (" WARNING: a rule longer than the limit was skipped, so access for the crawlers whose "
                              "status says unknown_long_rule_ignored is unknown: an allowed value of null means "
                              "unknown, never allowed.")
    return _fit(report, cut, keep=("bots_checked",))


# --------------------------------------------------------------------- contrast
_HEX = re.compile(r"^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
_RGB = re.compile(r"^rgb\(\s*(\d{1,3})\s*[, ]\s*(\d{1,3})\s*[, ]\s*(\d{1,3})\s*\)$", re.I)


def parse_color(value: str) -> tuple[int, int, int]:
    v = (value or "").strip()
    m = _HEX.match(v)
    if m:
        h = m.group(1)
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    m = _RGB.match(v)
    if m:
        rgb = tuple(int(x) for x in m.groups())
        if all(0 <= c <= 255 for c in rgb):
            return rgb  # type: ignore[return-value]
    raise AuditError(f"Could not read the color '{value}'. Use #rgb, #rrggbb or rgb(r, g, b); transparency is not supported.")


def _lum(rgb: tuple[int, int, int]) -> float:
    def ch(c: int) -> float:
        s = c / 255
        return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4
    r, g, b = (ch(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(fg: str, bg: str) -> dict:
    a, b = _lum(parse_color(fg)), _lum(parse_color(bg))
    hi, lo = max(a, b), min(a, b)
    ratio = (hi + 0.05) / (lo + 0.05)
    return {
        "foreground": fg, "background": bg, "ratio": round(ratio, 2),
        "passes": {
            "AA_normal_text_4.5": ratio >= 4.5, "AA_large_text_3": ratio >= 3.0,
            "AAA_normal_text_7": ratio >= 7.0, "AAA_large_text_4.5": ratio >= 4.5,
            "ui_components_3": ratio >= 3.0,
        },
        "note": "Solid colors only. Text on gradients, images or with transparency must be checked at its worst point.",
    }
