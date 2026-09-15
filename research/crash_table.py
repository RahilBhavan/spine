import urllib.request,urllib.parse,json,time,datetime as dt
def candles(p,g,s,e):
    out=[];cur=s
    while cur<e:
        nxt=min(e,cur+g*300)
        q=urllib.parse.urlencode(dict(granularity=g,start=dt.datetime.utcfromtimestamp(cur).isoformat(),end=dt.datetime.utcfromtimestamp(nxt).isoformat()))
        req=urllib.request.Request(f'https://api.exchange.coinbase.com/products/{p}/candles?{q}',headers={'User-Agent':'research'})
        out+=json.load(urllib.request.urlopen(req));cur=nxt;time.sleep(0.12)
    return sorted(set(map(tuple,out)))
# windows: (name, pre-peak start, trough search end)
W=[('Mar2020','2020-03-07','2020-03-14'),('May2021','2021-05-08','2021-05-20'),('FTX Nov2022','2022-11-04','2022-11-11'),('Aug2024','2024-07-29','2024-08-06'),('Oct2025','2025-10-06','2025-10-12'),('Feb2026','2026-01-25','2026-02-10'),('Jun2026','2026-06-10','2026-07-05')]
ts=lambda d:int(dt.datetime.fromisoformat(d).replace(tzinfo=dt.timezone.utc).timestamp())
for p in ['BTC-USD','ETH-USD']:
  daily=candles(p,86400,ts('2020-03-01'),ts('2026-09-15'))
  for n,a,b in W:
    c=candles(p,300,ts(a),ts(b)+86400)
    hi=max(c,key=lambda x:x[2]);pk=hi[2];pkt=hi[0]
    after=[x for x in c if x[0]>=pkt];lo=min(after,key=lambda x:x[1]);tr=lo[1];trt=lo[0]
    def maxdrop(h):
        m=0
        for i,x in enumerate(c):
            j=i
            while j<len(c) and c[j][0]-x[0]<=h: 
                m=max(m,(x[2]-c[j][1])/x[2]);j+=1
        return m
    rec=[d for d in daily if d[0]>trt and d[2]>=pk]
    recs=f"{(rec[0][0]-trt)/86400:.0f}d" if rec else 'not yet'
    print(f"{p} {n}: peak {pk:.0f} @{dt.datetime.utcfromtimestamp(pkt):%m-%d %H:%M} trough {tr:.0f} @{dt.datetime.utcfromtimestamp(trt):%m-%d %H:%M} drop {(pk-tr)/pk*100:.1f}% dur {(trt-pkt)/3600:.1f}h | max1h {maxdrop(3600)*100:.1f}% max4h {maxdrop(14400)*100:.1f}% max24h {maxdrop(86400)*100:.1f}% | recover {recs}")
