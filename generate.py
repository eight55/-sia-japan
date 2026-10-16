import json, math, os
from pathlib import Path
from datetime import datetime, timezone
import pandas as pd
import yfinance as yf

WATCH = {'7203.T': 'トヨタ自動車', '6758.T': 'ソニーグループ', '8306.T': '三菱UFJ FG', '6501.T': '日立製作所', '8035.T': '東京エレクトロン', '9984.T': 'ソフトバンクグループ', '6861.T': 'キーエンス', '7974.T': '任天堂', '8058.T': '三菱商事', '6098.T': 'リクルートHD', '9432.T': 'NTT', '4063.T': '信越化学工業', '4502.T': '武田薬品工業', '8766.T': '東京海上HD', '7011.T': '三菱重工業', '2914.T': '日本たばこ産業', '3382.T': 'セブン＆アイHD', '8267.T': 'イオン', '9843.T': 'ニトリHD', '4452.T': '花王', '4911.T': '資生堂', '2502.T': 'アサヒグループHD', '2503.T': 'キリンHD', '2802.T': '味の素', '2269.T': '明治HD', '2282.T': '日本ハム', '2002.T': '日清製粉グループ', '9020.T': 'JR東日本', '9021.T': 'JR西日本', '9022.T': 'JR東海', '9005.T': '東急', '9101.T': '日本郵船', '9104.T': '商船三井', '9107.T': '川崎汽船', '9202.T': 'ANA HD', '9201.T': '日本航空', '7201.T': '日産自動車', '7267.T': 'ホンダ', '7269.T': 'スズキ', '7270.T': 'SUBARU', '7202.T': 'いすゞ自動車', '6902.T': 'デンソー', '7259.T': 'アイシン', '6594.T': 'ニデック', '6981.T': '村田製作所', '6762.T': 'TDK', '6971.T': '京セラ', '6503.T': '三菱電機', '6504.T': '富士電機', '6702.T': '富士通', '6701.T': 'NEC', '7751.T': 'キヤノン', '7733.T': 'オリンパス', '7741.T': 'HOYA', '4543.T': 'テルモ', '4519.T': '中外製薬', '4568.T': '第一三共', '4503.T': 'アステラス製薬', '4507.T': '塩野義製薬', '4523.T': 'エーザイ', '4151.T': '協和キリン', '3407.T': '旭化成', '3402.T': '東レ', '4005.T': '住友化学', '4188.T': '三菱ケミカルグループ', '6988.T': '日東電工', '4901.T': '富士フイルムHD', '5802.T': '住友電気工業', '5803.T': 'フジクラ', '5401.T': '日本製鉄', '5411.T': 'JFE HD', '5713.T': '住友金属鉱山', '5020.T': 'ENEOS HD', '1605.T': 'INPEX', '5019.T': '出光興産', '8031.T': '三井物産', '8001.T': '伊藤忠商事', '8002.T': '丸紅', '8053.T': '住友商事', '8308.T': 'りそなHD', '8316.T': '三井住友FG', '8411.T': 'みずほFG', '8591.T': 'オリックス', '8604.T': '野村HD', '8601.T': '大和証券グループ', '8750.T': '第一生命HD', '8725.T': 'MS&AD', '8630.T': 'SOMPO HD', '9433.T': 'KDDI', '9434.T': 'ソフトバンク', '4689.T': 'LINEヤフー', '4755.T': '楽天グループ', '9983.T': 'ファーストリテイリング', '7970.T': '信越ポリマー', '6367.T': 'ダイキン工業', '6301.T': 'コマツ', '6305.T': '日立建機', '7012.T': '川崎重工業', '7013.T': 'IHI', '1801.T': '大成建設'}
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
    rows=[]; errors={}
    for code,name in WATCH.items():
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
