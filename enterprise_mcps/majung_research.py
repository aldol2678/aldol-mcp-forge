"""Bounded live source collection for MAJUNG; no generated market facts.

Tavily's documented Search API is opt-in, one basic search credit per call.
Direct source reads require an operator-owned exact hostname allowlist. TLS
connections pin a previously validated public address, redirects are forbidden,
and robots.txt is checked before a page is read. Caller input cannot alter these
permissions or provide provider credentials.
"""
from __future__ import annotations

import hashlib
import http.client
import ipaddress
import json
import os
import re
import socket
import ssl
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urlsplit
from urllib.parse import urlencode
from urllib.robotparser import RobotFileParser
from urllib.request import Request, HTTPRedirectHandler, build_opener
import xml.etree.ElementTree as ET

USER_AGENT = "ALDOLMajung/1.0"
MAX_PAGE_BYTES = 1_048_576
MAX_PROVIDER_BYTES = 2_097_152
TIMEOUT = 12


def timestamp():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def public_url(url):
    if not isinstance(url, str) or len(url) > 1000:
        raise ValueError("URL must be a bounded HTTPS URL")
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError as exc:
        raise ValueError("Malformed source URL") from exc
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
            or port not in (None, 443) or parsed.fragment or "\\" in url
            or any(ord(c) < 33 for c in url)):
        raise ValueError("Source URL requires public HTTPS without credentials or fragments")
    host = parsed.hostname.encode("idna").decode("ascii").lower().rstrip(".")
    if "." not in host or host.endswith((".local", ".internal", ".localhost")):
        raise ValueError("Private source hostname denied")
    try:
        ip = ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        ip = None
    if ip is not None:
        raise ValueError("IP literal source URLs denied")
    return parsed, host


def _public_address(host):
    entries = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    addresses = list(dict.fromkeys(x[4][0] for x in entries))
    if not addresses or any(not ipaddress.ip_address(x).is_global for x in addresses):
        raise ValueError("DNS includes nonpublic address")
    return addresses[0]


class _PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, host, address):
        super().__init__(host, timeout=TIMEOUT, context=ssl.create_default_context())
        self.address = address

    def connect(self):
        raw = socket.create_connection((self.address, 443), timeout=self.timeout)
        try:
            self.sock = self._context.wrap_socket(raw, server_hostname=self.host)
        except BaseException:
            raw.close()
            raise


def _get(host, address, path, limit):
    conn = _PinnedHTTPS(host, address)
    try:
        conn.request("GET", path, headers={"User-Agent": USER_AGENT,
                     "Accept": "text/html,text/plain,application/json,application/xml",
                     "Accept-Encoding": "identity"})
        response = conn.getresponse()
        if 300 <= response.status < 400:
            raise ValueError("Redirects are not followed")
        if response.status != 200:
            raise ValueError("Source HTTP status " + str(response.status))
        if response.getheader("Content-Encoding", "identity").lower() not in ("identity", ""):
            raise ValueError("Compressed source response denied")
        length = response.getheader("Content-Length")
        if length and (not length.isdigit() or int(length) > limit):
            raise ValueError("Source response too large")
        content_type = response.getheader("Content-Type", "").split(";", 1)[0].lower()
        if content_type not in ("text/html", "text/plain", "application/json", "application/xml", "text/xml"):
            raise ValueError("Unsupported source content type")
        body = response.read(limit + 1)
        if len(body) > limit:
            raise ValueError("Source response too large")
        return body, content_type
    finally:
        conn.close()


class _PageText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip = 0
        self.in_title = False
        self.title = []
        self.text = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript", "template"):
            self.skip += 1
        if tag == "title":
            self.in_title = True

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "template"):
            self.skip = max(0, self.skip - 1)
        if tag == "title":
            self.in_title = False

    def handle_data(self, data):
        if self.in_title:
            self.title.append(data)
        if not self.skip and data.strip():
            self.text.append(data.strip())


def observe_source(url):
    parsed, host = public_url(url)
    allowed = {x.strip().lower() for x in os.getenv("MAJUNG_FETCH_ALLOWED_HOSTS", "").split(",") if x.strip()}
    if host not in allowed:
        raise ValueError("Source hostname is not in server allowlist")
    address = _public_address(host)
    robots_bytes, _ = _get(host, address, "/robots.txt", 65_536)
    robots = RobotFileParser()
    robots.parse(robots_bytes.decode("utf-8", "replace").splitlines())
    if not robots.can_fetch(USER_AGENT, url):
        raise ValueError("Source robots policy denies retrieval")
    path = parsed.path or "/"
    if parsed.query:
        path += "?" + parsed.query
    body, content_type = _get(host, address, path, MAX_PAGE_BYTES)
    text = body.decode("utf-8", "replace")
    if content_type == "text/html":
        page = _PageText()
        page.feed(text)
        title = " ".join(" ".join(page.title).split())[:180]
        text = " ".join(page.text)
    else:
        title = parsed.path.rsplit("/", 1)[-1] or host
    excerpt = " ".join(text.split())[:600]
    if not excerpt:
        raise ValueError("Source has no readable text")
    return {"title": title or host, "url": url, "host": host,
            "observed_at": timestamp()[:10], "checked_at": timestamp(),
            "published_at": None, "claim": excerpt, "method": "direct_https_robots_dns_pinned",
            "retrieval_verified": True, "source_content_verified": True, "claim_verified": False,
            "trust": "publisher_content_observed; independence and truth not established",
            "sha256": hashlib.sha256(body).hexdigest(), "bytes_read": len(body),
            "limitations": ["Excerpt only; no automated fact or price confirmation", "JavaScript not rendered"]}


def search_market(topic, region="unspecified"):
    """Return provider observations; never present snippets as independently true."""
    key = os.getenv("TAVILY_API_KEY", "")
    if not key:
        return search_public_feed(topic, region)
    if os.getenv("MAJUNG_SEARCH_ALLOW_CREDIT_USE", "false").lower() != "true":
        return {"status": "BLOCKED_COST_APPROVAL", "provider": "tavily", "sources": [],
                "reason": "Basic search needs up to one Tavily credit; server credit-use approval is disabled",
                "estimated_credits": 1, "credits_used": 0}
    # Only the documented provider endpoint is reachable through this path.
    query = topic if region == "unspecified" else topic + " " + region
    request = json.dumps({"query": query[:400], "search_depth": "basic", "max_results": 5,
                          "include_answer": False, "include_raw_content": False,
                          "include_usage": True, "auto_parameters": False}).encode()
    conn = http.client.HTTPSConnection("api.tavily.com", timeout=20,
                                       context=ssl.create_default_context())
    try:
        conn.request("POST", "/search", body=request,
                     headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
        response = conn.getresponse()
        if response.status != 200:
            return {"status": "FAILED", "provider": "tavily", "sources": [],
                    "reason": "Provider HTTP status " + str(response.status), "credits_used": "UNKNOWN"}
        body = response.read(MAX_PROVIDER_BYTES + 1)
        if len(body) > MAX_PROVIDER_BYTES:
            raise ValueError("Provider response exceeds limit")
        data = json.loads(body)
        if not isinstance(data, dict) or not isinstance(data.get("results"), list):
            raise ValueError("Provider returned invalid results")
        sources = []
        for item in data["results"][:5]:
            if not isinstance(item, dict):
                continue
            try:
                _, host = public_url(item.get("url"))
            except ValueError:
                continue
            title = str(item.get("title") or host)[:180]
            snippet = str(item.get("content") or "")[:600]
            sources.append({"title": title, "url": item["url"], "host": host,
                            "claim": snippet, "observed_at": timestamp()[:10], "checked_at": timestamp(),
                            "published_at": item.get("published_date"), "method": "tavily_search_basic",
                            "retrieval_verified": True, "source_content_verified": False, "claim_verified": False,
                            "trust": "search_provider_excerpt; original page and claim unverified"})
        return {"status": "SUCCESS" if sources else "INSUFFICIENT_SOURCES", "provider": "tavily",
                "sources": sources, "request_id": str(data.get("request_id", ""))[:100],
                "credits_used": data.get("usage", {}).get("credits", "UNKNOWN"),
                "checked_at": timestamp(), "estimated_credits": 1}
    except (OSError, ValueError, http.client.HTTPException):
        return {"status": "FAILED", "provider": "tavily", "sources": [],
                "reason": "Provider transport or response validation failed", "credits_used": "UNKNOWN"}
    finally:
        conn.close()


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Search feed redirects are denied")


def search_public_feed(topic, region="unspecified"):
    """Best-effort public Bing RSS, not a contracted API or uptime guarantee."""
    query = topic if region == "unspecified" else topic + " " + region
    url = "https://www.bing.com/search?" + urlencode({"q": query[:400], "format": "rss"})
    try:
        opener = build_opener(_NoRedirect())
        with opener.open(Request(url, headers={"User-Agent": USER_AGENT,
                          "Accept": "application/rss+xml,application/xml,text/xml"}), timeout=15) as response:
            body = response.read(262_145)
        if len(body) > 262_144 or b"<!DOCTYPE" in body.upper() or b"<!ENTITY" in body.upper():
            raise ValueError("Unsafe or oversized RSS response")
        root = ET.fromstring(body)
        if root.tag != "rss":
            raise ValueError("Provider did not return RSS")
        sources = []
        for item in root.findall("./channel/item")[:5]:
            link = (item.findtext("link") or "").strip()
            try:
                _, host = public_url(link)
            except ValueError:
                continue
            excerpt = _PageText()
            excerpt.feed(item.findtext("description") or "")
            sources.append({"title": (item.findtext("title") or host)[:180], "url": link, "host": host,
                            "claim": " ".join(excerpt.text)[:600], "observed_at": timestamp()[:10],
                            "checked_at": timestamp(), "published_at": None,
                            "feed_item_date": item.findtext("pubDate"),
                            "method": "bing_public_rss_best_effort", "retrieval_verified": True,
                            "source_content_verified": False, "claim_verified": False,
                            "trust": "search_feed_candidate; original page unverified"})
        keywords = set(re.findall(r"[a-zA-Z]{3,}|[가-힣]{2,}", topic.lower())) - {"the", "and", "for", "with", "what", "how", "current", "market", "pricing", "price"}
        for source in sources:
            haystack = (source["title"] + " " + source["claim"]).lower()
            source["topic_matches"] = sorted(word for word in keywords if word in haystack)
            source["relevance"] = "CANDIDATE_MATCH" if source["topic_matches"] or not keywords else "UNCONFIRMED"
        relevant = sum(source["relevance"] == "CANDIDATE_MATCH" for source in sources)
        status = "SUCCESS" if sources and relevant else "LOW_RELEVANCE" if sources else "INSUFFICIENT_SOURCES"
        return {"status": status, "provider": "bing_public_rss",
                "sources": sources, "credits_used": 0, "checked_at": timestamp(),
                "relevance_heuristic": "keyword overlap only; not a semantic relevance verdict",
                "limitations": ["Experimental public feed; no API SLA", "Ranking and snippets may be incomplete",
                                "Feed item date is not asserted to be original publication date"]}
    except (OSError, ValueError, ET.ParseError):
        return {"status": "FAILED", "provider": "bing_public_rss", "sources": [],
                "reason": "Public search feed unavailable or invalid", "credits_used": 0,
                "limitations": ["Best-effort public feed; caller-supplied evidence is separate"]}
