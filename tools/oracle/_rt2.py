import json,collections
base="runs/"
A=json.load(open(base+"after/m3_oracle_20261030T005055Z.json"))
B=json.load(open(base+"prefix_before/m3_oracle_20261030T004231Z.json"))
key=lambda r:(r["wallet"],r["coin"])
bk={key(r) for r in B["rows"] if r["label"]=="LOST_OBLIGATION"}
rows=[r for r in A["rows"] if r["label"]=="LOST_OBLIGATION"]
brows=[r for r in B["rows"] if r["label"]=="LOST_OBLIGATION"]
print("A",len(rows),"B",len(brows),"stable",len([r for r in rows if key(r) in bk]),"union",len(bk|{key(r) for r in rows}))
def exp(rs,tag):
    per={}
    for r in rs:
        p=per.setdefault(r["coin"],{"v":set(),"pr":float(r["price"])})
        p["v"].add((float(r["actual"]),float(r["in_flight"] or 0)))
    conflict={c:p["v"] for c,p in per.items() if len(p["v"])>1}
    nz=[(c,list(p["v"])[0],p["pr"]) for c,p in per.items() if abs(list(p["v"])[0][0]+list(p["v"])[0][1])>1e-12]
    print(tag,"rows",len(rs),"coins",len(per),"nonzero",len(nz),"signed %.2f"%sum((a+f)*pr for c,(a,f),pr in nz),"gross %.2f"%sum(abs((a+f)*pr) for c,(a,f),pr in nz),"conflict",conflict)
exp(rows,"ALL58")
exp([r for r in rows if key(r) in bk],"STABLE50")
exp(brows,"B55")
dc=collections.Counter(r["coin"] for r in rows)
print("dupcoins",{c:n for c,n in dc.items() if n>1})
