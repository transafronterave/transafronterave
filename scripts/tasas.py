import json,urllib.request,statistics,datetime,os
def post(t):
    b=json.dumps({"asset":"USDT","fiat":"COP","tradeType":t,"page":1,"rows":10,"payTypes":[],"publisherType":None}).encode()
    r=urllib.request.Request("https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search",b,{"Content-Type":"application/json","User-Agent":"Mozilla/5.0"})
    d=json.load(urllib.request.urlopen(r,timeout=20))["data"]
    return statistics.median([float(x["adv"]["price"]) for x in d[:5]])
old=json.load(open("tasas.json")) if os.path.exists("tasas.json") else {}
out=dict(old)
try: out["usdt_compra"]=post("BUY"); out["usdt_venta"]=post("SELL")
except Exception as e: print("binance",e)
try:
    d=json.load(urllib.request.urlopen("https://www.datos.gov.co/resource/32sa-8pi3.json?$order=vigenciadesde%20DESC&$limit=1",timeout=20))
    out["trm"]=float(d[0]["valor"])
except Exception as e: print("trm",e)
out["actualizado"]=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-5))).strftime("%d/%m/%Y %H:%M")
json.dump(out,open("tasas.json","w"))
print(out)
