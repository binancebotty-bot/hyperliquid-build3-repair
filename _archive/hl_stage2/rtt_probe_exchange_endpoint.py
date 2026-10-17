"""Measure the /exchange endpoint's own latency with an INVALID signature.

No key, no valid signature => the exchange can never create an order. This only
measures how long the endpoint takes to answer, so engine cost can be separated
from exchange cost."""
import json, socket, ssl, statistics, time
HOST="api.hyperliquid-testnet.xyz"
CTX=ssl.create_default_context()
ADDR=socket.getaddrinfo(HOST,443,socket.AF_INET,socket.SOCK_STREAM)[0][4]

def conn():
    s=socket.socket(socket.AF_INET,socket.SOCK_STREAM); s.settimeout(20); s.connect(ADDR)
    return CTX.wrap_socket(s,server_hostname=HOST)

def post(ss,path,payload):
    body=json.dumps(payload).encode()
    req=("POST %s HTTP/1.1\r\nHost: %s\r\nContent-Type: application/json\r\nContent-Length: %d\r\n\r\n"%(path,HOST,len(body))).encode()+body
    t=time.monotonic(); ss.sendall(req); buf=b""
    while b"\r\n\r\n" not in buf:
        c=ss.recv(65536)
        if not c: raise ConnectionError("closed")
        buf+=c
    head,_,rest=buf.partition(b"\r\n\r\n"); clen=0
    for line in head.split(b"\r\n")[1:]:
        if line.lower().startswith(b"content-length:"): clen=int(line.split(b":",1)[1])
    while len(rest)<clen:
        c=ss.recv(65536)
        if not c: break
        rest+=c
    return (time.monotonic()-t)*1000, head.split(b"\r\n")[0].decode(), rest[:160].decode(errors="replace")

ss=conn()
info=[]; exch=[]
for _ in range(8):
    ms,st,_=post(ss,"/info",{"type":"allMids"}); info.append(ms)
    ms2,st2,b2=post(ss,"/exchange",{"action":{"type":"order","orders":[]},"nonce":0,"signature":{"r":"0x0","s":"0x0","v":27},"vaultAddress":None})
    exch.append(ms2)
info.sort(); exch.sort()
print("INFO  n=%d p50=%.0f min=%.0f max=%.0f"%(len(info),statistics.median(info),info[0],info[-1]))
print("EXCH  n=%d p50=%.0f min=%.0f max=%.0f"%(len(exch),statistics.median(exch),exch[0],exch[-1]))
print("LAST_EXCH_RESPONSE:",st2,b2.replace(chr(10)," "))
print("RATIO_EXCH_OVER_INFO: %.2f"%(statistics.median(exch)/statistics.median(info)))
ss.close()
