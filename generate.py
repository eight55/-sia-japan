import json, math, os
from pathlib import Path
from datetime import datetime, timezone, timedelta
import pandas as pd
import yfinance as yf

import csv, re
from concurrent.futures import ThreadPoolExecutor, as_completed

def load_watch(path='stocks.csv'):
    watch = {}
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or not {'code', 'name'}.issubset(reader.fieldnames):
            raise ValueError('stocks.csvにはcode,name列が必要です')
        for line, row in enumerate(reader, 2):
            code = (row.get('code') or '').strip().upper()
            name = (row.get('name') or '').strip()
            if not code and not name: continue
            if not re.fullmatch(r'[0-9A-Z]{4,5}\.T', code) or not name:
                raise ValueError(f'stocks.csv {line}行目: 証券コードまたは銘柄名が不正です')
            if code in watch: raise ValueError(f'stocks.csv {line}行目: 重複コード {code}')
            watch[code] = name
    if not watch: raise ValueError('stocks.csvに分析対象がありません')
    return watch

def finite(v):
    try:
        v=float(v)
        return round(v,3) if math.isfinite(v) else None
    except (ValueError,TypeError): return None

def collect(code,name):
    df=yf.Ticker(code).history(period='1y',interval='1d',auto_adjust=True)
    if df is None or len(df)<70: raise ValueError('70営業日分のデータを取得できません')
    df=df.dropna(subset=['Close','High','Low','Volume'])
    if len(df)<70: raise ValueError('有効な日足が不足')
    c=df.Close; v=df.Volume
    diff=c.diff(); up=diff.clip(lower=0).ewm(alpha=1/14,adjust=False,min_periods=14).mean(); down=(-diff.clip(upper=0)).ewm(alpha=1/14,adjust=False,min_periods=14).mean()
    rsi=100-100/(1+up/down.replace(0,float('nan')))
    macd=c.ewm(span=12,adjust=False).mean()-c.ewm(span=26,adjust=False).mean(); signal=macd.ewm(span=9,adjust=False).mean()
    tr=pd.concat([df.High-df.Low,(df.High-c.shift()).abs(),(df.Low-c.shift()).abs()],axis=1).max(axis=1); atr=tr.rolling(14).mean().iloc[-1]
    price=float(c.iloc[-1]); ma20=float(c.tail(20).mean()); ma60=float(c.tail(60).mean()); volavg=float(v.tail(20).mean()); ratio=float(v.iloc[-1]/volavg) if volavg>0 else 0
    mom=float(price/c.iloc[-21]-1); year=float(price/c.iloc[0]-1); rv=finite(rsi.iloc[-1]); rv=rv if rv is not None else 50
    scores={'短期':round(max(0,min(100,50+12*(price>ma20)+9*(rv>50)+7*min(ratio,2)+90*mom-15*(rv>75)))), '中期':round(max(0,min(100,48+15*(price>ma60)+13*(ma20>ma60)+110*mom+8*(macd.iloc[-1]>signal.iloc[-1])))), '長期':round(max(0,min(100,45+12*(price>ma60)+9*(ma20>ma60)+28*year)))}
    a=finite(atr) or price*.025; entry=price-.5*a
    return {'code':code,'name':name,'per':None,'pbr':None,'roe':None,'dividendYield':None,'revenueGrowth':None,'earningsGrowth':None,'earningsDate':None,'fundamentalScore':None,'valueScore':None,'growthScore':None,'opportunity':None,'compositeScores':{'短期':None,'中期':None,'長期':None},'assetType':'ETF' if code=='2644.T' else '株式','fundamental_status':'未取得','fundamental_updated':None,'date':str(df.index[-1].date()),'price':finite(price),'change':finite((price/float(c.iloc[-2])-1)*100),'rsi':rv,'macd':finite(macd.iloc[-1]),'ma20':finite(ma20),'ma60':finite(ma60),'volumeRatio':finite(ratio),'atr':finite(a),'entry':finite(entry),'target':finite(entry+3*a),'stop':finite(entry-2*a),'scores':scores,'history':[{'date':str(t.date()),'close':finite(row.Close)} for t,row in df.tail(90).iterrows()]}

def main():
    watch=load_watch(Path(__file__).with_name('stocks.csv'))
    rows=[]; errors={}
    # Six workers limits concurrency; external data can still fail or throttle.
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures={pool.submit(collect,code,name):code for code,name in watch.items()}
        for future in as_completed(futures):
            code=futures[future]
            try:
                rows.append(future.result()); print('OK',code,flush=True)
            except Exception as exc:
                errors[code]=str(exc)[:160]; print('FAILED',code,errors[code],flush=True)
    order={code:i for i,code in enumerate(watch)}
    rows.sort(key=lambda r:order[r['code']])
    # Independent candidate paths: technical leaders plus a rotating fundamental coverage pool.
    # Cache is a repository-side JSON file; the workflow must persist it between runs.
    cache_path=Path(__file__).with_name('fundamentals-cache.json')
    try:
        cache=json.loads(cache_path.read_text(encoding='utf-8')) if cache_path.exists() else {}
        if not isinstance(cache,dict):cache={}
    except (ValueError,OSError):cache={}
    priority={'2644.T','5586.T','6748.T'}
    technical={r['code'] for term in ('短期','中期','長期') for r in sorted(rows,key=lambda r:r['scores'][term],reverse=True)[:20]}
    # Round-robin coverage eventually makes all equities eligible for fundamental selection.
    # Oldest/missing cache records are fetched first; daily request budget is bounded.
    now=datetime.now(timezone.utc)
    def age(code):
        try:return datetime.fromisoformat(cache[code]['fundamental_updated'])
        except (KeyError,TypeError,ValueError):return datetime.min.replace(tzinfo=timezone.utc)
    due=sorted((r['code'] for r in rows if r['code']!='2644.T'),key=lambda c:(age(c),order[c]))
    refresh=set(due[:45]) | priority | technical
    fields=('per','pbr','roe','dividendYield','revenueGrowth','earningsGrowth','earningsDate','fundamentalScore','valueScore','growthScore','assetType','fundamental_status','fundamental_updated')
    for row in rows:
        old=cache.get(row['code'])
        if isinstance(old,dict):
            for field in fields:
                if field in old:row[field]=old[field]
        if row['code'] not in refresh:continue
        try:
            info=yf.Ticker(row['code']).get_info()
            fresh={'assetType':'ETF' if row['code']=='2644.T' or info.get('quoteType')=='ETF' else '株式','fundamental_updated':now.isoformat()}
            if fresh['assetType']=='ETF':
                fresh['fundamental_status']='ETF：企業業績スコア対象外'
            else:
                for field,key in [('per','trailingPE'),('pbr','priceToBook'),('roe','returnOnEquity'),('dividendYield','dividendYield'),('revenueGrowth','revenueGrowth'),('earningsGrowth','earningsGrowth')]:
                    v=finite(info.get(key))
                    if field in ('per','pbr') and (v is None or v<=0):v=None
                    fresh[field]=v
                ed=info.get('earningsTimestampStart') or info.get('earningsTimestamp')
                fresh['earningsDate']=datetime.fromtimestamp(ed,timezone.utc).date().isoformat() if isinstance(ed,(int,float)) and ed>0 else None
                vals=[fresh[k] for k in ('per','pbr','roe','dividendYield','revenueGrowth','earningsGrowth')]
                fresh['fundamental_status']='取得済み（一部欠損あり）' if any(v is not None for v in vals) else '企業指標欠損'
                if sum(v is not None for v in vals)>=3 and fresh['roe'] is not None and (fresh['revenueGrowth'] is not None or fresh['earningsGrowth'] is not None):
                    value=50
                    if fresh['per'] is not None:value+=max(-12,min(12,(18-fresh['per'])*1.1))
                    if fresh['pbr'] is not None:value+=max(-8,min(8,(2-fresh['pbr'])*4))
                    growth=50+max(-20,min(20,fresh['roe']*100*.7))
                    for key in ('revenueGrowth','earningsGrowth'):
                        if fresh[key] is not None:growth+=max(-15,min(15,fresh[key]*100*.45))
                    if fresh['dividendYield'] is not None and 0<fresh['dividendYield']<.12:growth+=min(5,fresh['dividendYield']*100)
                    fresh['valueScore']=round(max(0,min(100,value)))
                    fresh['growthScore']=round(max(0,min(100,growth)))
                    fresh['fundamentalScore']=round(.4*fresh['valueScore']+.6*fresh['growthScore'])
                else:
                    fresh.update(valueScore=None,growthScore=None,fundamentalScore=None)
                    fresh['fundamental_status']+='・総合評価にはデータ不足'
            row.update(fresh)
            cache[row['code']]={k:row.get(k) for k in fields}
        except Exception as exc:
            if not old:row['fundamental_status']='取得失敗'
            print('FUNDAMENTALS UNAVAILABLE',row['code'],str(exc)[:100],flush=True)
    weights={'短期':(.75,.10,.15),'中期':(.45,.25,.30),'長期':(.20,.35,.45)}
    for row in rows:
        if row['assetType']=='ETF' or row['valueScore'] is None or row['growthScore'] is None:continue
        for term,(t,v,g) in weights.items():
            row['compositeScores'][term]=round(t*row['scores'][term]+v*row['valueScore']+g*row['growthScore'])
        row['opportunity']=row['compositeScores']['中期']
    # Export cache as an artifact; persist it to the repository to reuse across Actions runs.
    out=Path('site');out.mkdir(exist_ok=True)
    (out/'fundamentals-cache.json').write_text(json.dumps(cache,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    print('Fundamental coverage:',sum(r['compositeScores']['中期'] is not None for r in rows),'of',len(rows),flush=True)
    if not rows: raise SystemExit('取得全件失敗。架空の株価には切り替えません。')
    data=json.dumps({'updated':datetime.now(timezone.utc).isoformat(),'rows':rows,'errors':errors,'price_dates':sorted(set(r['date'] for r in rows)),'configured_count':len(watch)},ensure_ascii=False,allow_nan=False).replace('</','<\\/')
    template=Path(__file__).with_name('template.html').read_text(encoding='utf-8')
    out=Path('site');out.mkdir(exist_ok=True)
    (out/'index.html').write_text(template.replace('/*SIA_DATA*/','const SIA_DATA='+data+';'),encoding='utf-8')
    import csv
    with (out/'recommendations.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.writer(f)
        writer.writerow(['run_utc','price_date','period','rank','code','name','price','score','entry','target','stop','per','pbr','fundamental_updated'])
        for p in ('短期','中期','長期'):
            for rank,r in enumerate(sorted(rows,key=lambda r:r['scores'][p],reverse=True)[:5],1):
                writer.writerow([datetime.now(timezone.utc).isoformat(),r['date'],p,rank,r['code'],r['name'],r['price'],r['scores'][p],r['entry'],r['target'],r['stop'],r['per'],r['pbr'],r['fundamental_updated']])
    with (out/'composite-recommendations.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.writer(f)
        writer.writerow(['run_utc','price_date','period','rank','code','name','price','composite_score','technical_score','value_score','growth_score','fundamental_updated'])
        for term in ('短期','中期','長期'):
            eligible=[r for r in rows if r['compositeScores'][term] is not None]
            for rank,r in enumerate(sorted(eligible,key=lambda r:r['compositeScores'][term],reverse=True)[:5],1):
                writer.writerow([now.isoformat(),r['date'],term,rank,r['code'],r['name'],r['price'],r['compositeScores'][term],r['scores'][term],r['valueScore'],r['growthScore'],r['fundamental_updated']])
    print('Generated', out/'index.html' ,len(rows),'stocks; failed:',len(errors))
if __name__=='__main__':main()
