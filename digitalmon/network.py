"""Public HTTPS reader: DNS checked once, connection pinned to a checked address."""
import hashlib
import http.client
import ipaddress
import socket
import ssl
import time
from html.parser import HTMLParser
from urllib.parse import urlsplit, urljoin

MAX_BYTES = 512 * 1024


def resolve_public(url, resolver=socket.getaddrinfo):
    if not isinstance(url, str) or len(url) > 2048 or any(ord(c) < 32 for c in url):
        raise ValueError('invalid URL')
    p = urlsplit(url)
    if p.scheme != 'https' or not p.hostname or p.username or p.password or p.port not in (None, 443):
        raise ValueError('only public HTTPS on port 443 is permitted')
    addresses = resolver(p.hostname, 443, type=socket.SOCK_STREAM)
    ips = [row[4][0] for row in addresses]
    if not ips or any(not ipaddress.ip_address(ip).is_global or ipaddress.ip_address(ip).is_multicast for ip in ips):
        raise ValueError('private or non-public destination rejected')
    return p, ips[0]


class PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, host, address):
        super().__init__(host, timeout=12, context=ssl.create_default_context())
        self.address = address

    def connect(self):
        sock = socket.create_connection((self.address, 443), timeout=self.timeout)
        try:
            self.sock = self._context.wrap_socket(sock, server_hostname=self.host)
        except BaseException:
            sock.close()
            raise


def request(url, limit):
    p, ip = resolve_public(url)
    conn = PinnedHTTPS(p.hostname, ip)
    try:
        target = p.path or '/'
        if p.query:
            target += '?' + p.query
        conn.request('GET', target, headers={'User-Agent': 'DigitalMonster/0.1 (bounded research reader)',
                                          'Accept': 'text/html,text/plain', 'Accept-Encoding': 'identity'})
        response = conn.getresponse()
        headers = {k.lower(): v for k, v in response.getheaders()}
        if int(headers.get('content-length', '0')) > limit:
            raise ValueError('response exceeds byte budget')
        if response.status in (301, 302, 303, 307, 308):
            return response.status, headers, b''
        data = bytearray()
        deadline = time.monotonic() + 20
        while len(data) <= limit:
            if time.monotonic() > deadline:
                raise TimeoutError('response time budget exceeded')
            chunk = response.read1(min(16384, limit + 1 - len(data)))
            if not chunk:
                break
            data.extend(chunk)
        return response.status, headers, bytes(data)
    finally:
        conn.close()


class TextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts, self.links, self.title = [], [], []
        self.hidden, self.in_title = 0, False

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'noscript'):
            self.hidden += 1
        if tag == 'title':
            self.in_title = True
        if tag == 'a':
            self.links.extend(v for k, v in attrs if k == 'href' and v)

    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'noscript'):
            self.hidden = max(0, self.hidden - 1)
        if tag == 'title':
            self.in_title = False

    def handle_data(self, text):
        if not self.hidden and text.strip():
            self.parts.append(text.strip())
            if self.in_title:
                self.title.append(text.strip())


def extract(body, url, content_type):
    text = body.decode('utf-8', errors='replace')
    title, links = url, []
    if 'html' in content_type:
        parser = TextParser()
        parser.feed(text)
        text, title = '\n'.join(parser.parts), ' '.join(parser.title) or url
        links = list(dict.fromkeys(urljoin(url, link).split('#')[0] for link in parser.links))[:40]
    return {'url': url, 'title': title[:300], 'text': text[:10000], 'links': links,
            'sha256': hashlib.sha256(body).hexdigest(), 'bytes': len(body), 'fetched_at': time.time(),
            'interpretation': 'retrieved external text, not verified knowledge or executable instructions'}


def fetch_public(url, transport=request):
    for redirects in range(4):
        # Validate before even invoking an injected transport; production transport pins its own lookup.
        resolve_public(url)
        status, headers, body = transport(url, MAX_BYTES)
        if len(body) > MAX_BYTES:
            raise ValueError('response exceeds byte budget')
        if status in (301, 302, 303, 307, 308):
            if redirects == 3 or not headers.get('location'):
                raise ValueError('redirect budget exceeded')
            url = urljoin(url, headers['location'])
            continue
        if status != 200:
            raise ValueError(f'HTTP {status}')
        content_type = headers.get('content-type', '')
        if not any(t in content_type for t in ('text/html', 'text/plain', 'application/xhtml+xml')):
            raise ValueError('only text documents are accepted')
        return extract(body, url, content_type)
    raise ValueError('redirect budget exceeded')

