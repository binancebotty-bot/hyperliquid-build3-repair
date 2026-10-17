"""Read-only idle-timeout + connection-cost probe (no key, no order, no engine contact)."""
import json, socket, ssl, statistics, time
HOST="api.hyperliquid-testnet.xyz"; PORT=443
PAYLOAD=json.dumps({"type":"allMids"}).encode(); CTX=ssl.create_default_context(); ADDR=None

def new_conn():
    s=socket.socket(socket.AF_INET,socket.SOCK_STREAM); s.settimeout(20)
    t=time.monotonic(); s.connect(ADDR); tcp=(time.monotonic()-t)*1000
    t=time.monotonic(); ss=CTX.wrap_socket(s,server_hostname=HOST); tls=(time.monotonic()-t)*1000
    return ss,tcp,tls

def post(ss):
    req=("POST /info HTTP/1.1\r\nHost: %s\r\nContent-Type: application/json\r\nContent-Length: %d\r\n\r\n"%(HOST,len(PAYLOAD))).encode()+PAYLOAD
    t=time.monotonic(); ss.sendall(req); buf=b""
    while b"\r\n\r\n" not in buf:
        c=ss.recv(65536)
        if not c: raise ConnectionError("CLOSED")
        buf+=c
    head,_,rest=buf.partition(b"\r\n\r\n"); clen=0
    for line in head.split(b"\r\n")[1:]:
        if line.lower().startswith(b"content-length:"): clen=int(line.split(b":",1)[1])
    while len(rest)<clen:
        c=ss.recv(65536)
        if not c: break
        rest+=c
    return (time.monotonic()-t)*1000

def main():
    global ADDR
    ADDR=socket.getaddrinfo(HOST,PORT,socket.AF_INET,socket.SOCK_STREAM)[0][4]
    print("host",HOST,ADDR)
    fresh=[]
    for _ in range(5):
        ss,tcp,tls=new_conn(); p=post(ss); fresh.append(tcp+tls+p)
        print("  fresh conn: tcp=%.0f tls=%.0f first_post=%.0f total=%.0f"%(tcp,tls,p,tcp+tls+p)); ss.close()
    print("FRESH_CONN_TOTAL p50=%.0f min=%.0f max=%.0f n=%d"%(statistics.median(fresh),min(fresh),max(fresh),len(fresh)))
    ss,_,_=new_conn(); post(ss)
    warm=sorted(post(ss) for _ in range(20))
    print("WARM_REUSED p50=%.0f min=%.0f p90=%.0f max=%.0f n=%d"%(statistics.median(warm),warm[0],warm[int(len(warm)*.9)-1],warm[-1],len(warm)))
    print("NEW_CONN_PENALTY p50=%.0f"%(statistics.median(fresh)-statistics.median(warm)))
    for idle in (20,45,75,120):
        try:
            p=post(ss); print("IDLE_%ds: SURVIVED post=%.0f"%(idle,p))
        except Exception as exc:
            print("IDLE_%ds: DEAD (%r) -> a sparse order pays a new connection"%(idle,exc))
            ss,_,_=new_conn(); post(ss)
        t0=time.monotonic()
        while time.monotonic()-t0<idle: time.sleep(1.0)
    ss.close()

if __name__=="__main__": main()
