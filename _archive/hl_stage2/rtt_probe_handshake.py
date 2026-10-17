"""Read-only latency probe against the follower info host (no key, no order, no engine contact)."""
import json, socket, ssl, statistics, time

HOST = "api.hyperliquid-testnet.xyz"
PORT = 443
PAYLOAD = json.dumps({"type": "allMids"}).encode()
N = 12


def tcp_connect(family, addr):
    s = socket.socket(family, socket.SOCK_STREAM)
    s.settimeout(10)
    t = time.monotonic()
    s.connect(addr)
    return s, (time.monotonic() - t) * 1000.0


def http_post_once(sock, path="/info"):
    req = ("POST %s HTTP/1.1\r\nHost: %s\r\nContent-Type: application/json\r\n"
           "Content-Length: %d\r\n\r\n" % (path, HOST, len(PAYLOAD))).encode() + PAYLOAD
    t = time.monotonic()
    sock.sendall(req)
    buf = b""
    while b"\r\n\r\n" not in buf:
        chunk = sock.recv(65536)
        if not chunk:
            raise ConnectionError("closed before headers")
        buf += chunk
    head, _, rest = buf.partition(b"\r\n\r\n")
    clen = 0
    for line in head.split(b"\r\n")[1:]:
        if line.lower().startswith(b"content-length:"):
            clen = int(line.split(b":", 1)[1])
    while len(rest) < clen:
        chunk = sock.recv(65536)
        if not chunk:
            break
        rest += chunk
    return (time.monotonic() - t) * 1000.0, head.split(b"\r\n")[0].decode(errors="replace"), len(rest)


def main():
    infos = socket.getaddrinfo(HOST, PORT, type=socket.SOCK_STREAM)
    fams = {}
    for fam, _t, _p, _c, sa in infos:
        fams.setdefault(fam, sa)
    print("ADDR_FAMILIES:", {("IPv6" if k == socket.AF_INET6 else "IPv4"): v for k, v in fams.items()})

    for fam, sa in fams.items():
        try:
            s, ms = tcp_connect(fam, sa)
            s.close()
            print("TCP_CONNECT_%s: %.1f ms  %s" % ("IPv6" if fam == socket.AF_INET6 else "IPv4", ms, sa))
        except Exception as exc:
            print("TCP_CONNECT_%s: FAILED %r" % ("IPv6" if fam == socket.AF_INET6 else "IPv4", exc))

    ctx = ssl.create_default_context()
    sock, tcp_ms = tcp_connect(socket.AF_INET, fams[socket.AF_INET])
    t = time.monotonic()
    ssock = ctx.wrap_socket(sock, server_hostname=HOST)
    tls_ms = (time.monotonic() - t) * 1000.0
    print("TLS_HANDSHAKE_MS: %.1f (version=%s, session_reused=%s)" % (tls_ms, ssock.version(), ssock.session_reused))

    first_ms, status, n = http_post_once(ssock)
    print("COLD_FIRST_POST_MS: %.1f  %s  body=%dB" % (first_ms, status, n))

    warm = []
    for _ in range(N):
        ms, status, _n = http_post_once(ssock)
        warm.append(ms)
    ssock.close()
    warm.sort()
    print("WARM_KEEPALIVE_POST n=%d p50=%.1f min=%.1f p90=%.1f max=%.1f"
          % (len(warm), statistics.median(warm), warm[0], warm[int(len(warm) * 0.9) - 1], warm[-1]))

    s2, tcp2 = tcp_connect(socket.AF_INET, fams[socket.AF_INET])
    t = time.monotonic()
    ss2 = ctx.wrap_socket(s2, server_hostname=HOST)
    tls2 = (time.monotonic() - t) * 1000.0
    cold2, _s, _n = http_post_once(ss2)
    ss2.close()
    print("NEW_CONN_COST: tcp=%.1f tls=%.1f first_post=%.1f total=%.1f"
          % (tcp2, tls2, cold2, tcp2 + tls2 + cold2))


if __name__ == "__main__":
    main()
