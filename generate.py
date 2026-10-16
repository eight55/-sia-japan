import json, math, os, csv, re
from pathlib import Path
from datetime import datetime, timezone
import pandas as pd
import yfinance as yf

def load_watch(path='stocks.csv'):
    watch = {}
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or not {'code', 'name'}.issubset(reader.fieldnames):
            raise ValueError('stocks.csvにはcode,name列が必要です')
        for line, row in enumerate(reader, 2):
            code = (row.get('code') or '').strip().upper()
            name = (row.get('name') or '').strip()
            if not code and not name:
                continue
            if not re.fullmatch(r'[0-9A-Z]{4,5}\.T', code) or not name:
                raise ValueError(f'stocks.csv {line}行目: 証券コードまたは銘柄名が不正です')
            if code in watch:
                raise ValueError(f'stocks.csv {line}行目: 重複コード {code}')
            watch[code] = name
    if not watch:
        raise ValueError('stocks.csvに分析対象がありません')
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
    return {'code':code,'name':name,'date':str(df.index[-1].date()),'price':finite(price),'change':finite((price/float(c.iloc[-2])-1)*100),'rsi':rv,'macd':finite(macd.iloc[-1]),'ma20':finite(ma20),'ma60':finite(ma60),'volumeRatio':finite(ratio),'atr':finite(a),'entry':finite(entry),'target':finite(entry+3*a),'stop':finite(entry-2*a),'scores':scores,'history':[{'date':str(t.date()),'close':finite(row.Close)} for t,row in df.tail(90).iterrows()]}

def main():
    watch = load_watch(Path(__file__).with_name('stocks.csv'))
    print('Configured stocks:', len(watch))
    rows=[]; errors={}
    for code,name in watch.items():
        try:
            rows.append(collect(code,name)); print('OK',code)
        except Exception as e:
            errors[code]=str(e)[:160]; print('FAILED',code,errors[code])
    if not rows: raise SystemExit('取得全件失敗。架空の株価には切り替えません。')
    data=json.dumps({'updated':datetime.now(timezone.utc).isoformat(),'rows':rows,'errors':errors,'price_dates':sorted(set(r['date'] for r in rows))},ensure_ascii=False,allow_nan=False).replace('</','<\\/')
    template=Path(__file__).with_name('template.html').read_text(encoding='utf-8')
    out=Path('site');out.mkdir(exist_ok=True)
    (out/'index.html').write_text(template.replace('/*SIA_DATA*/','const SIA_DATA='+data+';'),encoding='utf-8')
    print('Generated',out/'index.html',len(rows),'stocks; failed:',len(errors))
if __name__=='__main__':main()
