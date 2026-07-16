#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Dec  5 11:34:33 2024

@author: ninni
"""

import numpy as np
import pandas as pd
import requests
from datetime import datetime, timedelta, date
from pprint import pprint

from plotly.subplots import make_subplots
import plotly.graph_objects as go

from IPython.display import display, clear_output

import yfinance as yf
from finvizfinance.quote import finvizfinance

import streamlit as st
import streamlit.components.v1 as components
import pickle
import os
import sys

# INIZIALIZZAZIONE DELLA SESSIONE GLOBALE PER EVITARE I BLOCCHI DI YAHOO FINANCE
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
})

#%%

# FUNZIONE PERSONALIZZATA PER LA BARRA DI SCROLL ORIZZONTALE SULLE TABELLE
def render_table_with_slider(
    df,
    min_rows: int = 6,
    max_rows: int = 24,
    row_px: int = 26,
    header_px: int = 34,
    padding_px: int = 14,
    key: str = "tbl",
    escape: bool = True,
):
    try:
        df2 = df.copy()
        df2.index = range(1, len(df2) + 1)
        df2.index.name = ""
    except Exception:
        df2 = df

    html_table = df2.to_html(border=0, classes="gf-table", index=True, escape=escape)

    rows = int(df2.shape[0])
    target_rows = max(min_rows, min(rows, max_rows))
    scroller_h = header_px + row_px * target_rows + padding_px
    component_h = scroller_h + 36

    html = f"""
    <div id="gf-wrap-{key}" style="
      position:relative; z-index:2147483000;
      width:100%; max-width:100%;
      box-sizing:border-box; overflow:visible;
      font-family: system-ui,-apple-system,Segoe UI,Roboto,sans-serif;">

      <!-- IMPORTANT: overflow-x:hidden per eliminare la barra nativa -->
      <div id="gf-scroller-{key}" style="
        overflow-y:auto; overflow-x:hidden;
        border:1px solid #ddd; height:{scroller_h}px;
        width:100%; max-width:100%; box-sizing:border-box;
        padding-bottom:2px; padding-right:2px;">
        <div id="gf-content-{key}">
          {html_table}
        </div>
      </div>

      <!-- Slider -->
      <div id="gf-slider-wrap-{key}" class="gf-slider">
        <div class="gf-track"></div>
        <div id="gf-fill-{key}" class="gf-fill"></div>
        <div id="gf-handle-{key}" class="gf-handle"></div>
        <input id="gf-range-{key}" class="gf-range-ghost" type="range" min="0" max="1000" value="0">
      </div>
    </div>

    <style>
      /* Tabella */
      #gf-wrap-{key} table {{
        border-collapse: separate; border-spacing:0;
        width: max-content;
        max-width: calc(100% - 4px);
        font-size:11.5px;
      }}
      #gf-wrap-{key} th, #gf-wrap-{key} td {{
        padding:6px 4.6px;
        white-space:nowrap;
        border-bottom:1px solid #eee;
        border-right:1px solid #eee;
      }}
      #gf-wrap-{key} th:last-child, #gf-wrap-{key} td:last-child {{ border-right:none; }}
      #gf-wrap-{key} thead th {{
        position: sticky; top: 0;
        background:#fafafa; z-index:1;
      }}

      /* Colonna indice (FIX: max-width corretto) */
      #gf-wrap-{key} thead th:first-child,
      #gf-wrap-{key} tbody td:first-child {{
        text-align:center;
        width:26px; min-width:26px; max-width:26px;
        color:#444;
      }}

      /* Nascondi barra H nativa ovunque */
      #gf-scroller-{key} {{
        -ms-overflow-style: none;        /* IE/Edge legacy */
        scrollbar-width: none;           /* Firefox */
      }}
      #gf-scroller-{key}::-webkit-scrollbar:horizontal {{ height:0px; display:none; }}  /* WebKit */

      /* Slider custom */
      .gf-slider {{ position:relative; height:34px; margin-top:2px; z-index:2147483200; overflow:visible; }}
      .gf-track  {{ position:absolute; left:10px; right:10px; top:40%; height:3px; background:#e5e7eb; transform:translateY(-50%); border-radius:2px; z-index:1; }}
      .gf-fill   {{ position:absolute; left:10px; top:40%; height:3px; background:#d00; transform:translateY(-50%); border-radius:2px; width:0px; z-index:2; }}
      .gf-handle {{ position:absolute; top:40%; width:12px; height:12px; background:#d00; border:2px solid #fff; border-radius:50%; transform:translate(-50%,-50%); left:10px; box-shadow:0 0 0 1px rgba(0,0,0,.15); cursor:grab; z-index:2147483400; }}
      .gf-handle:active {{ cursor:grabbing; }}
      .gf-range-ghost {{ position:absolute; left:0; right:0; top:0; bottom:0; width:100%; height:100%; opacity:0; cursor:ew-resize; z-index:2147483300; }}
    </style>

    <script>
      const scroller  = document.getElementById("gf-scroller-{key}");
      const content   = document.getElementById("gf-content-{key}");
      const rangeEl   = document.getElementById("gf-range-{key}");
      const fillEl    = document.getElementById("gf-fill-{key}");
      const handleEl  = document.getElementById("gf-handle-{key}");
      const sliderBox = document.getElementById("gf-slider-wrap-{key}");
      const PADDING = 10;

      function maxScrollX() {{ return Math.max(0, content.scrollWidth - scroller.clientWidth); }}
      function usableWidth() {{ return Math.max(0, sliderBox.clientWidth - 2*PADDING); }}

      function applyPct(pct) {{
        const W = usableWidth();
        const x = PADDING + (pct/100) * W;
        fillEl.style.width = (x - PADDING) + "px";
        handleEl.style.left = x + "px";
      }}

      function syncSliderFromScroll() {{
        const m = maxScrollX();
        if (m <= 0) {{ rangeEl.disabled = true; applyPct(0); return; }}
        rangeEl.disabled = false;
        const pct = (scroller.scrollLeft / m) * 100;
        rangeEl.value = Math.round((pct/100) * 1000);
        applyPct(pct);
      }}

      function syncScrollFromSlider() {{
        const m = maxScrollX();
        const pct = (rangeEl.value / 1000) * 100;
        scroller.scrollLeft = (pct/100) * m;   
        applyPct(pct);
      }}

      let dragging = false;
      handleEl.addEventListener("mousedown", () => dragging = true);
      window.addEventListener("mouseup",   () => dragging = false);
      window.addEventListener("mousemove", (e) => {{
        if (!dragging) return;
        const rect = sliderBox.getBoundingClientRect();
        let x = Math.min(Math.max(e.clientX - rect.left, PADDING), rect.width - PADDING);
        const pct = ((x - PADDING) / (rect.width - 2*PADDING)) * 100;
        rangeEl.value = Math.round((pct/100) * 1000);
        syncScrollFromSlider();
      }});

      scroller.addEventListener("scroll", syncSliderFromScroll);
      rangeEl.addEventListener("input",  syncScrollFromSlider);
      rangeEl.addEventListener("change", syncScrollFromSlider);

      new ResizeObserver(syncSliderFromScroll).observe(content);
      new ResizeObserver(syncSliderFromScroll).observe(sliderBox);
      window.addEventListener("load", syncSliderFromScroll);
      setTimeout(syncSliderFromScroll, 120);
    </script>
    """
    components.html(html, height=component_h, scrolling=False)

#%%

# QUESTO BLOCCO CARICA I DATI DA YAHOO FINANCE E POI ELABORA IL DF DATI_STORICI

def elaborazione(dati_storici, provider):
    dati_storici['Gap %'] = ((dati_storici['Open']*100)/dati_storici['Close'].shift(1))-100

    colonna_da_spostare = dati_storici.pop('Gap %')
    dati_storici.insert(1, 'Gap %', colonna_da_spostare)
    
    dati_storici['Max % UP'] = ((dati_storici['High']*100)/(dati_storici['Open']))-100
    dati_storici['Max % DOWN'] = ((dati_storici['Low']*100)/(dati_storici['Open']))-100
    dati_storici['Open to Close %'] = ((dati_storici['Close']*100)/(dati_storici['Open']))-100
    dati_storici['Chiusura'] = dati_storici.apply(lambda x: 'RED' if x['Open to Close %']<0 \
                                                  else 'GREEN' if x['Open to Close %']>0 else '=open', axis=1)
        
    dati_storici_ADJ = dati_storici.round(3).copy()
    
    if provider == "yfinance":
            trans = pd.DataFrame(index=range(0, len(dati_storici)))
            trans['split_factor'] = 0
            split_factor = 1
        
            for a in range((len(dati_storici)-1), -1, -1):
                    if dati_storici['Stock Splits'].iloc[a] > 0:
                            trans.loc[a, 'split_factor'] = split_factor
                            split_factor = split_factor*dati_storici['Stock Splits'].iloc[a]
                    else:
                            trans.loc[a, 'split_factor'] = split_factor
        
            dati_storici['Open'] = dati_storici.apply(lambda x: x['Open']*trans.loc[x.name, 'split_factor'] if\
                                      (trans.loc[x.name, 'split_factor']< 1) else \
                                          (x['Open']/trans.loc[x.name, 'split_factor']), axis=1)
                
            dati_storici['High'] = dati_storici.apply(lambda x: x['High']*trans.loc[x.name, 'split_factor'] if\
                                      (trans.loc[x.name, 'split_factor']< 1) else \
                                          (x['High']/trans.loc[x.name, 'split_factor']), axis=1)
                
            dati_storici['Low'] = dati_storici.apply(lambda x: x['Low']*trans.loc[x.name, 'split_factor'] if\
                                      (trans.loc[x.name, 'split_factor']< 1) else \
                                          (x['Low']/trans.loc[x.name, 'split_factor']), axis=1)
                
            dati_storici['Close'] = dati_storici.apply(lambda x: x['Close']*trans.loc[x.name, 'split_factor'] if\
                                      (trans.loc[x.name, 'split_factor']< 1) else \
                                          (x['Close']/trans.loc[x.name, 'split_factor']), axis=1) 
                
            dati_storici['Volume'] = dati_storici.apply(lambda x: x['Volume']/trans.loc[x.name, 'split_factor'] if\
                                      (trans.loc[x.name, 'split_factor']< 1) else \
                                          (x['Volume']*trans.loc[x.name, 'split_factor']), axis=1)    

    dati_storici = dati_storici.round(3)
    return dati_storici_ADJ, dati_storici

#%%

# QUI RECUPERO I DATI DEGLI SPLITS

def formatta_splits(dati_storici):
    split_df = dati_storici[(dati_storici['Stock Splits']>0)].loc[:, ['Date', 'Stock Splits']] 
    split_df.index = split_df['Date']
    split_df.drop('Date', axis=1, inplace=True)

    split_df['Stock Splits'] = split_df['Stock Splits'].apply(lambda x: f'1/{int(1/x)}' \
                                if x<1 else f'{x:.1f}/1'.replace('.', ','))
    
    split_df.rename(columns={'Stock Splits': 'split_factor'}, inplace=True)
    return split_df
    
#%%
 
# PRENDO i DATI API dal PROVIDER 'FINANCIAL MODELING PREP'
 
def stock_split(nome_ticker, cache_file, FMP_api_key):
     try:
         response = requests.get(f'https://financialmodelingprep.com/api/v3/historical-price-full/stock_split/{nome_ticker.upper()}?apikey={FMP_api_key}')
         data = response.json()
         
         if len(data['historical'])>0:
             my_data = []
             for a in data['historical']:
                 single = {'Date': a['date'], 'split_factor': eval(f"{a['numerator']/a['denominator']:.3f}")}
                 my_data.append(single)
                    
             splits_df = pd.DataFrame(my_data)
             splits_df.index = splits_df['Date']
             splits_df.drop('Date', axis=1, inplace=True)
         else:
             splits_df = pd.DataFrame()  
             
         if len(data)>0: 
             with open(cache_file, 'wb') as f:
                   pickle.dump(splits_df, f) 
     except:  
         splits_df = pd.DataFrame()
         
     return splits_df

#%%

# CARICO I DATI FONDAMENTALI DA FINVIZ e YFINANCE

def fondamentali_func(nome_ticker):
    fond_df = nationality = exchange = sector = industry = website = None
    
    market_cap = 'M.Cap'
    outstanding = 'Outstand.'
    shares_float = 'Float'
    insider_own =  'Insider'
    inst_own = 'Inst.O.'
    short_float = 'S.Float'
    
    try:
        # Passata la sessione per evitare blocchi IP
        ticker = yf.Ticker(nome_ticker.upper(), session=session)
        fond = ticker.info

        def prendi_trasforma_valore(voce):
            try:
                if fond[voce]>=10**9:
                    divisore = 1000000000
                    simbolo = 'B'
                else:
                    divisore = 1000000
                    simbolo = 'M'
                stringa = f"{fond[voce]/divisore:.2f}{simbolo}" 
            except:
                stringa = ' - '
            return stringa

        def aggiusto_perc(voce):
            try:
                perc_corretta = f"{fond[voce]*100:.2f}%"
            except:
                perc_corretta = ' - '
            return perc_corretta 
        
        try:        
            website = fond['website']
        except:
            website = ""
            
        fondamentali_yf = {market_cap: prendi_trasforma_valore('marketCap'), 
                            outstanding: prendi_trasforma_valore('sharesOutstanding'),
                            shares_float: prendi_trasforma_valore('floatShares'),
                            insider_own: aggiusto_perc('heldPercentInsiders'),
                            inst_own: aggiusto_perc('heldPercentInstitutions'),
                            short_float: aggiusto_perc('shortPercentOfFloat')}
    except:  
        website = ""
        fondamentali_yf = {market_cap: ' - ',
                        outstanding: ' - ',   
                        shares_float: ' - ',
                        insider_own: ' - ',
                        inst_own: ' - ',
                        short_float: ' - ' }
     
    finvitz_data = None
    tentativi = 1
    while tentativi < 5:
        try:
            finvitz_stampa = st.empty()
            with finvitz_stampa.container():
                st.write('loading...')
                stock = finvizfinance(nome_ticker)
                finvitz_data = stock.ticker_fundament()
                
                def prendi_voce(voce):
                    try:
                        risposta = finvitz_data.get(voce)  
                    except:
                        risposta = ' - '
                    return risposta   
                
                nationality_exchange = {'nation': prendi_voce("Country"), 'exchange': prendi_voce("Exchange")}            
                sector_industry = {'sector': prendi_voce("Sector"), 'industry': prendi_voce("Industry")}
                
                fondamentali_fz = {market_cap: prendi_voce('Market Cap'),
                                 outstanding: prendi_voce('Shs Outstand'),
                                shares_float: prendi_voce('Shs Float'),
                                insider_own: prendi_voce('Insider Own'),
                                inst_own: prendi_voce('Inst Own'),
                                short_float: prendi_voce('Short Float')}
                                                                             
                finvitz_stampa.empty()
                break   
        except:
            finvitz_stampa.empty()
            tentativi += 1
        
    if tentativi == 5: 
        fondamentali_fz = {market_cap: ' - ',
                        outstanding: ' - ',   
                        shares_float: ' - ',
                        insider_own: ' - ',
                        inst_own: ' - ',
                        short_float: ' - ' }
        nationality_exchange = {'nation': " - ", 'exchange': " - "}
        sector_industry = {'sector': ' - ', 'industry': ' - '}
        
    fond_fz_df = pd.DataFrame({'a': fondamentali_fz.keys(), 'Fz': fondamentali_fz.values()})
    fond_yf_df = pd.DataFrame({'a': fondamentali_yf.keys(), 'Yf': fondamentali_yf.values()})
    
    fond_df = fond_fz_df.merge(fond_yf_df, on='a').set_index('a')
    fond_df.index.name = None
    return fond_df, nationality_exchange, sector_industry, website

#%%

# CARICO LE NEWS DA FINVIZ

def news_func(nome_ticker):
    tentativi = 0
    while tentativi < 5:
        try:
            stock = finvizfinance(nome_ticker)
            news = stock.ticker_news()
            break
        except Exception as e:
            if '404' in str(e):
                news = f'<b>{nome_ticker.upper()}</b> has no news'
                break
            elif 'timeout' in str(e):
                tentativi += 1 
            else:
                tentativi += 1
                
    if tentativi == 5:
        news = f'problemi nel caricamento delle news <b>{nome_ticker.upper()}</b> da Finviz'

    return news

#%%

# CARICO I VALORI di PREZZO DA YFINANCE o da ALPHA_VANTAGE

def datagathering_func(nome_ticker):
    dati_storici = pd.DataFrame(); splits_format = pd.DataFrame(); caricato = 0; provider = "" 
    
    CACHE_DIR = "cache"
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_file = os.path.join(CACHE_DIR, f"{nome_ticker.upper()}.pkl")
    print(cache_file)
        
    if os.path.exists(cache_file):
          with open(cache_file, "rb") as fp:
              print(f"Caricamento dati daily e splits {nome_ticker} dalla cache.")
              cache_data = pickle.load(fp)
              dati_storici = cache_data['dati_storici']
              splits_format = cache_data['splits']
              provider = cache_data['provider']
              caricato = 1
   
    if caricato == 0:
        try:     
            print(f'provo a prendere i dati splits di {nome_ticker} da FMP')
            FMP_api_key = st.secrets["FMP_api_key"]
            splits_df = stock_split(nome_ticker, cache_file, FMP_api_key)
        except:
             splits_df=pd.DataFrame()
                
        try:
            # Passata la sessione protetta per evitare blocchi IP
            ticker = yf.Ticker(nome_ticker.upper(), session=session)   
            dati_storici = ticker.history(period="max")
            
            if not dati_storici.empty:
                provider = 'yfinance'
                dati_storici.index = dati_storici.index.tz_localize(None)
                dati_storici.sort_index(ascending=True, inplace=True) 
                print('tolto il fusorario')
                print(f"presi i dati daily di {nome_ticker} da YFINANCE\n")
                
                if len(dati_storici.columns)==8:
                    st.write(f"{nome_ticker.upper()} it's not a stock")
                    dati_storici = pd.DataFrame()
                    return dati_storici, splits_df, provider
        except:
                  pass
            
        if dati_storici.empty:
            provider = 'alphavantage'
            print(f'provo a prendere i dati daily di {nome_ticker} da AlphaVantage')
              
            ALPHA_api_key = st.secrets["ALPHA_api_key"]
            symbol = nome_ticker.upper()
            function = 'TIME_SERIES_DAILY'
            outputsize = 'full'
      
            url = f'https://www.alphavantage.co/query?function={function}&symbol={symbol}&outputsize={outputsize}&apikey={ALPHA_api_key}'
            response = requests.get(url)
            data = response.json()
      
            if 'Time Series (Daily)' in data:
                time_series = data['Time Series (Daily)']
                dati_storici = pd.DataFrame.from_dict(time_series, orient='index')
                dati_storici.rename(columns={
                    '1. open': 'Open',
                    '2. high': 'High',
                    '3. low': 'Low',
                    '4. close': 'Close',
                    '5. volume': 'Volume'}, inplace=True)
                
            print('prima delle trasformazioni')
            print(dati_storici[:5].to_string())
            
            cols = ['Open', 'High', 'Low', 'Close', 'Volume']
            dati_storici[cols] = dati_storici[cols].apply(pd.to_numeric, errors='coerce')
            dati_storici.sort_index(ascending=True, inplace=True) 
            
        if not dati_storici.empty:    
             dati_storici.index = pd.to_datetime(dati_storici.index).normalize()
        else:
             st.write('dati non disponibili\n oppure titolo inesistente o delistato')
        
        if not splits_df.empty:
              if provider == "yfinance":
                  splits_df.index = pd.to_datetime(splits_df.index).normalize()                     
                  dati_storici = dati_storici.merge(splits_df['split_factor'], left_index=True, right_index=True, how='left')
                  dati_storici['split_factor'] = dati_storici['split_factor'].fillna(0)
                  dati_storici.sort_index(ascending=True, inplace=True) 
                      
                  dati_storici.drop('Stock Splits', axis=1, inplace=True)
                  dati_storici.drop('Dividends', axis=1, inplace=True)
                  dati_storici.rename(columns={'split_factor': 'Stock Splits'}, inplace=True)
              
              if provider == "alphavantage":
                  splits_df.index = pd.to_datetime(splits_df.index).normalize()
                  dati_storici = dati_storici.merge(splits_df['split_factor'], left_index=True, right_index=True, how='left')
                  dati_storici['split_factor'] = dati_storici['split_factor'].fillna(0)
                  dati_storici.rename(columns={'split_factor': 'Stock Splits'}, inplace=True)
        else: 
          if provider == "yfinance":
                dati_storici.drop('Dividends', axis=1, inplace=True)   
                                    
          if provider == "alphavantage":  
                print('il ticker non ha splits/reverse splits')
                dati_storici['Stock Splits'] = 0.0
              
        if not dati_storici.empty: 
            dati_storici['Date'] = dati_storici.index
            colonna_da_spostare = dati_storici.pop('Date')
            dati_storici.insert(0, 'Date', colonna_da_spostare)
            dati_storici['Date'] = dati_storici['Date'].dt.date
            dati_storici = dati_storici.reset_index(drop=True)
                    
            print(dati_storici[:5].to_string())
            print(f'caricato = :{caricato}')
                    
            if provider == "yfinance":  
                splits_format = formatta_splits(dati_storici)
                print('qui gli splits formattati')
                print(splits_format)
                      
            if provider == "alphavantage":
                if not splits_df.empty: 
                    splits_format = formatta_splits(dati_storici)
                    print('qui gli splits formattati')
                    print(splits_format)
             
        if caricato == 0:
               with open(cache_file, 'wb') as fp:
                   pickle.dump({'dati_storici': dati_storici, 'splits': splits_format, 'provider': provider}, fp)
               return dati_storici, splits_format, provider
    else:
        if dati_storici.empty:
            st.write('dati non disponibili\n oppure titolo inesistente o delistato')
        return dati_storici, splits_format, provider

#%%

# LA FUNZIONE CHE SEGUE CERCA I GAPS ALL'INTERNO DEL DF dati_storici 

def ricerca_gaps(nome_ticker, dati_storici, gap_perc_A, gap_perc_B, volume, prezzo_A, prezzo_B):
    global gaps
    gaps = dati_storici.iloc[:, [0, 1, 2, 3, 4, 5, 8, 9, 10, -1, 6]].copy()
        
    gaps['day1_extention'] = ((gaps['Close'].shift(1)*100)/gaps['Open'].shift(1))-100 
    gaps['day1_volume'] = gaps['Volume'].shift(1)
    gaps = gaps[(gaps['day1_extention']<30) | ( (gaps['day1_extention']>=30) & (gaps['day1_volume']<=1_000_000) )]
    gaps.pop('day1_extention'); gaps.pop('day1_volume')
    
    gaps = gaps[(gaps['Gap %']>=gap_perc_A)&\
                        (gaps['Gap %']<=gap_perc_B)&\
                        (gaps['Volume']>=volume)&(gaps['Open']>=prezzo_A)&(gaps['Open']<=prezzo_B)]
    
    if not gaps.empty:    
        display_gaps = gaps.copy()
        display_gaps['Volume'] = display_gaps.apply(lambda x: f"{x['Volume']:,.0f}".replace(',', '.'), axis=1)
        display_gaps = display_gaps.round(2)
            
        display_gaps[['Gap %', 'Open', 'High', 'Low', 'Close', 'Max % UP',
               'Max % DOWN', 'Open to Close %']]=\
        display_gaps[['Gap %', 'Open', 'High', 'Low', 'Close', 'Max % UP',
               'Max % DOWN', 'Open to Close %']].astype(str).apply(lambda x: x.str.replace('.', ',', regex=False))
            
        display_gaps.reset_index(drop=True, inplace=True)
        display_gaps.index = display_gaps.index+1
        return display_gaps
    else: 
        print(f' il titolo {nome_ticker} non ha nessun gap superiore o uguale al {gap_perc_A}%')
        return gaps
        
#%%

## VISUALIZZA IL GRAFICO DEL GAP

def visual_gap(nome_ticker, n_gap, dati_storici_ADJ):
    global gaps
    finestra_daily = 100

    elementi_da_inizio_df = gaps.index[n_gap]
    if elementi_da_inizio_df > round(finestra_daily/2):
        finestra_A = round(finestra_daily/2)
    else:
        finestra_A = elementi_da_inizio_df
        
    elementi_da_fine_df = (dati_storici_ADJ.shape[0])-elementi_da_inizio_df
    if elementi_da_fine_df > round(finestra_daily/2):
        finestra_B = round(finestra_daily/2)
    else:
        finestra_B = elementi_da_fine_df
    
    df = dati_storici_ADJ.iloc[gaps.index[n_gap]-(finestra_A)\
                               :gaps.index[n_gap]+(finestra_B), :].copy()
    
    df['hover_text'] = (
        "Data: " + df['Date'].astype(str) + "<br>" +
        "Open: " + df['Open'].astype(str) + "<br>" +
        "High: " + df['High'].astype(str) + "<br>" +
        "Low: " + df['Low'].astype(str) + "<br>" +
        "Close: " + df['Close'].astype(str) + "<br>" +
        "Gap %: " + df['Gap %'].astype(str) + "<br>"
    )
    
    df['volume_text'] = df.apply(lambda x: f"{x['Volume']:,.0f}".replace(",", "."), axis=1)
    df['volume_text'] = ("Volume: "+df['volume_text'].astype(str))
    
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        row_heights=[0.8, 0.2],
        vertical_spacing= 0.15
    )
    
    fig.add_trace(
        go.Candlestick(
            x=df['Date'],
            open=df['Open'],
            high=df['High'],
            low=df['Low'],
            close=df['Close'],
            name="Daily",
            hovertext=df['hover_text'],  
            hoverinfo="text"  
        ),
        row=1, col=1
    )
    
    fig.add_trace(
        go.Bar(
            x=df['Date'],
            y=df['Volume'],
            name="Volume",
            hovertext=df['volume_text'],
            hoverinfo="text",
            marker_color='blue',
            opacity=0.6
        ),
        row=2, col=1
    )
    
    if finestra_A >= 5:
        finestra_visione_A = 5 
    else:
        finestra_visione_A = finestra_A-1   
    
    if finestra_B >= 5:
        finestra_visione_B = 5 
    else:
        finestra_visione_B = finestra_B-1
    
    fig.update_layout(
        title=f"          <b>{nome_ticker.upper()}</b> -  Grafico Gap del    {gaps.iloc[n_gap, 0]}",
        yaxis_title="Prezzo",
        xaxis_rangeslider={'thickness': 0.08, 'visible': True},
        template="plotly_white",
        width=800,
        height=600,
        shapes=[
            {
                'type': "rect",
                'xref': "x",
                'yref': "paper",
                'x0': df['Date'].loc[gaps.index[n_gap]],
                'x1': df['Date'].loc[gaps.index[n_gap] - 1],
                'y0': 0.80,
                'y1': 0.40,
                'fillcolor': 'Orange',
                'opacity': 0.1,
                'layer': "below",
                'line_width': 0
            }
        ]
    )
    
    fig.update_xaxes(
        range=[
            df['Date'].loc[gaps.index[n_gap] - finestra_visione_A], 
            df['Date'].loc[gaps.index[n_gap] + finestra_visione_B]
        ]
    )
    
    st.plotly_chart(fig, use_container_width=False, config={
        'displayModeBar': True,  
        'responsive': True,      
        'scrollZoom': True,      
        'staticPlot': False     
    })

#%%    
        
#  INTERFACCIA UTENTE

st.set_page_config(
    page_title="GAPs Finder",
    page_icon="📈",
    layout="wide",  
    initial_sidebar_state="expanded",  
) 

col1, col2, col3 = st.columns([0.11, 0.45, 0.44])   
    
# INSERISCO il TICKER
global nome_ticker

with col1:
    st.markdown("""
            <style>
                .stTextInput>div>div>input {
                    font-size: 13px !important;  
                }
                .stTextInput input {
                    font-size: 12px !important;  
                }  
            </style>
        """, unsafe_allow_html=True)

    with st.form(key=f'GAPs_Finder'):
            nome_ticker = st.text_input('**GAPsFinder v 1.06mx**', placeholder='Enter the Ticker').strip()
            bottone_ricerca = st.form_submit_button('ricerca GAPs')
         
    stampa_col1 = st.empty()  
        
    if bottone_ricerca:
        st.session_state.clear()
        st.session_state['slider_gaps']=(30, 1000)
        st.session_state['slider_volume']=1
        st.session_state['slider_price']=(2, 200)
        
        CACHE_DIR = "cache"
        os.makedirs(CACHE_DIR, exist_ok=True)
        data_oggi = datetime.now().date()
        data_cache_name = os.path.join(CACHE_DIR, 'data_cache.pkl')
        
        if os.path.exists(data_cache_name):
            with open(data_cache_name, "rb") as f:
                print("Caricamento data dalla cache.")
                data_cache = pickle.load(f)
            
            if data_oggi>data_cache:
                print(os.listdir('cache'))
                print('cancello i files nella cache')
                
                for file in os.listdir('cache'):
                    if file != 'contatore.pkl' and file != 'data_start_contatore.pkl':
                        os.remove(os.path.join(CACHE_DIR, file))
                    
                with open(data_cache_name, "wb") as f:
                    pickle.dump(data_oggi, f)            
        else:
            print('non esiste una data cache, la inserisco per la prima volta')
            with open(data_cache_name, "wb") as f:
                pickle.dump(data_oggi, f)
                
        print(os.listdir('cache'))
            
        if nome_ticker:
            if nome_ticker != 'contatore':
                dati_yfinance, dati_split, provider = datagathering_func(nome_ticker)
                
                CACHE_DIR = "cache"
                path_contatore = os.path.join(CACHE_DIR, 'contatore.pkl')
                path_contatore_daily = os.path.join(CACHE_DIR, 'contatore_daily.pkl')
                path_data_start_contatore = os.path.join(CACHE_DIR, 'data_start_contatore.pkl')
                
                if os.path.exists(path_contatore):
                        with open(path_contatore, 'rb') as f:
                            parziale = pickle.load(f)
                        parziale += 1 
                        with open(path_contatore, 'wb') as f:
                            pickle.dump(parziale, f)
                else:
                    os.makedirs(CACHE_DIR, exist_ok=True)
                    with open(path_contatore, 'wb') as f:
                        pickle.dump(1, f)
                    with open(path_data_start_contatore, 'wb') as f:
                        data_start = datetime.strftime(datetime.now().date(), "%Y-%m-%d")
                        pickle.dump(data_start, f)
                            
                if os.path.exists(path_contatore_daily):
                        with open(path_contatore_daily, 'rb') as f:
                            parziale = pickle.load(f)
                        parziale += 1 
                        with open(path_contatore_daily, 'wb') as f:
                            pickle.dump(parziale, f)    
                else:
                    os.makedirs(CACHE_DIR, exist_ok=True)
                    with open(path_contatore_daily, 'wb') as f:
                        pickle.dump(1, f) 
            else:
                dati_yfinance = pd.DataFrame() 
                CACHE_DIR = "cache"
                path_contatore = os.path.join(CACHE_DIR, 'contatore.pkl')
                path_contatore_daily = os.path.join(CACHE_DIR, 'contatore_daily.pkl')
                path_data_start_contatore = os.path.join(CACHE_DIR, 'data_start_contatore.pkl')
                
                if os.path.exists(path_contatore):
                        with open(path_contatore, 'rb') as f:
                            valore_contatore = pickle.load(f)
                            st.write(valore_contatore)
                else:
                    os.makedirs(CACHE_DIR, exist_ok = True)
                    with open(path_contatore, 'wb') as f:
                        pickle.dump(0, f)
                        
                if os.path.exists(path_data_start_contatore):            
                        with open(path_data_start_contatore, 'rb') as f:
                            data_start = pickle.load(f) 
                        st.write(data_start)
                else:
                     os.makedirs(CACHE_DIR, exist_ok = True)
                     with open(path_data_start_contatore, 'wb') as f:
                         data_start = datetime.strftime(datetime.now().date(), "%Y-%m-%d")
                         pickle.dump(data_start, f)
                         
                if os.path.exists(path_contatore_daily):            
                        with open(path_contatore_daily, 'rb') as f:
                            valore_contatore_daily = pickle.load(f) 
                        st.write(valore_contatore_daily)
                        st.write(os.listdir('cache'))  
                else:
                    os.makedirs(CACHE_DIR, exist_ok = True)
                    with open(path_contatore_daily, 'wb') as f:
                        pickle.dump(0, f)    
            
            if not dati_yfinance.empty:
                dati_storici_ADJ, dati_storici_DEF = elaborazione(dati_yfinance, provider)
                fondamentali, nationality_exchange, sector_industry, website = fondamentali_func(nome_ticker)
                news = news_func(nome_ticker)
                
                st.session_state['dati_storici'] = dati_storici_DEF
                st.session_state['fondamentali'] = fondamentali
                st.session_state['website'] = website
                st.session_state['nationality_exchange'] = nationality_exchange
                st.session_state['sector_industry'] = sector_industry
                st.session_state['news'] = news
                st.session_state['dati_split'] = dati_split
                st.session_state['dati_storici_ADJ'] = dati_storici_ADJ
        else:
            st.warning('Enter the Ticker')
            
    if 'dati_storici' in st.session_state and st.session_state['dati_storici'] is not None:
        with stampa_col1.container():
            st.write("")
            st.write("")
            
            if st.session_state['website']:
                ticker_html = f"""
                    <a href="{st.session_state['website']}" target="_blank" style="text-decoration: none; color: inherit;">
                        {nome_ticker.upper()}
                    </a>
                """
            else:
                ticker_html = f"{nome_ticker.upper()}"

            # USATO ST.HTML CHE RISOLVE I BLOCCHI GRIGI
            st.html(f"""
                <div style="font-size: 22px; font-weight: bold; margin-bottom: 2px;">
                    {ticker_html}
                </div>
                <div style="font-size: 12px;"><b>{st.session_state['nationality_exchange']['nation']} - {st.session_state['nationality_exchange']['exchange']}</b></div>
                <div style="font-size: 13px; font-weight: normal; color: #444;">
                    {st.session_state['sector_industry']['sector']}
                </div>
                <div style="font-size: 13px; font-weight: normal; color: #444;">
                    {st.session_state['sector_industry']['industry']}
                </div>
                <br>
            """)

            st.table(st.session_state['fondamentali'])
            print(st.session_state['fondamentali'])
                   
            if not st.session_state['dati_split'].empty:
                st.write("")
                st.write("")
                st.markdown("<div style='font-size: 14px;'> <b>Splits / Reverse Splits</b> </div>", unsafe_allow_html=True)
                st.write("")
    
                # ACCUMULATORE PER EVITARE GLI SPAZI VERTICALI NEGLI SPLITS
                splits_html = ""
                for a, b in st.session_state['dati_split'].iterrows():
                     splits_html += f"""
                                <div style="font-size: 13px; margin-bottom: 4px;">
                                    {a} <b>&nbsp;&nbsp;--&nbsp;&nbsp;</b> {b['split_factor']}
                                </div>
                            """
                st.html(splits_html)

with col2:
    st.markdown(
            """
            <style>
            table {
                font-size: 12px;  
                width: 100%;  
                margin-left: auto;  
                margin-right: auto; 
            }
            thead th {
                font-size: 14px;  
            }
            tbody td {
                font-size: 13px;  
            }
            .stTable td, .stTable th {
                white-space: nowrap !important;  
            }
            .stSlider {
                margin-bottom: -20px; 
            }
            .stSlider div[data-testid="stMarkdownContainer"] p {
                font-size: 13px !important; 
            }
            </style>
            """,
            unsafe_allow_html=True
        )
    
    if 'dati_storici' in st.session_state and st.session_state['dati_storici'] is not None:
           col2_1, col2_2, col2_3 = st.columns([0.25, 0.5, 0.25])
           with col2_2:
               gap_A, gap_B = st.slider("**Gap %**", 0, 1000, step=5, key='slider_gaps')
               volume = st.slider("**Volume Minimo Mln**", 0, 500, step=1, key='slider_volume')
               prezzo_A, prezzo_B = st.slider('**prezzo minimo $**', 0, 200, step=1, key='slider_price')
               
           v_gaps = ricerca_gaps(nome_ticker, st.session_state['dati_storici'], \
                                 gap_A, gap_B, volume*1_000_000, prezzo_A, prezzo_B) 
           
           st.write(""); st.write("")
           
           if not v_gaps.empty:
               # INTEGRATA LA FUNZIONE RENDER_TABLE_WITH_SLIDER CON SCROLLER ORIZZONTALE SULLE TABELLE
               render_table_with_slider(v_gaps, key="gaps")
           else:
               st.html(f"""
                    <div style="text-align: center; font-size: 14.5px;">
                        <b>{nome_ticker.upper()}</b> non ha giornate rispondenti ai parametri settati
                    </div>
                """)
               
           col2_4, col2_5, col2_6 = st.columns([0.20, 0.83, 0.14])
          
           with col2_5: 
                   st.write(""); st.write(""); st.write(""); st.write(""); st.write("")
                   st.html(f"""
                       <div style="text-align:center; font-size: 14px;">
                           <b>news:</b> <br/> <br/>
                       </div>
                   """)
                                   
                   if isinstance(st.session_state['news'], pd.DataFrame):
                           # ACCUMULATORE PER EVITARE GLI SPAZI VERTICALI NELLE NEWS
                           news_html = ""
                           for a, b in st.session_state['news'].iterrows():
                               ora = datetime.now().hour
                               
                               if ora <= 6:
                                    formatted_date = b['Date'] - timedelta(days=1)
                                    data_ora = datetime.now() - timedelta(days=1)
                               else:
                                    formatted_date = b['Date']
                                    data_ora = datetime.now()
                                    
                               if formatted_date.date() != data_ora.date() and a > 0:
                                    print(formatted_date, data_ora)
                                    break     
                                    
                               data_da_stampa = formatted_date.strftime("%Y-%m-%d | h %H:%M")    
                        
                               link = b['Link']
                               if not link.startswith('http'):
                                    link = "https://finviz.com/" + b['Link']
                                        
                               news_html += f"""
                                    <div style="text-align:left; font-size: 13px; margin-bottom: 6px; line-height: 1.3;">
                                        <strong style="color: red;">{data_da_stampa}</strong>&nbsp;
                                        <a href="{link}" style="text-decoration: none; color: inherit;">
                                            {b['Title']}
                                        </a>
                                    </div>
                               """
                           
                           # STAMPATO UNICAMENTE UNA VOLTA FUORI DAL LOOP
                           st.html(news_html)

                   if isinstance(st.session_state['news'], str):
                           st.html(f"""
                               <div style="text-align:center; font-size: 14px;">
                                   {st.session_state['news']}
                               </div>
                           """)
 
           if not v_gaps.empty:
                with col3:
                    col3_1, col3_2 = st.columns([0.18, 0.82])
                    with col3_1:
                        options = list(v_gaps.index)
                        n_gap = st.selectbox('**gap da visualizzare**', options)
                        
                    if st.button('visualizza'):
                        try:
                            visual_gap(nome_ticker, (n_gap-1), st.session_state['dati_storici_ADJ'])
                        except:
                            st.html(f"""
                                 <div style="text-align: center; font-size: 15px;">
                                     grafico non disponibile
                                 </div>
                             """)

st.markdown("""
    <style>
        .footer {
            position: fixed;
            bottom: 0;
            width: 100%;
            text-align: center;
            background-color: #e0e0e0; 
            padding: 6px;
        }
        .footer a {
            font-size: 12px; 
            text-decoration: none;
            color: blue; 
        }
        .footer a:hover {
            text-decoration: underline;
        }
    </style>
    <div class="footer">
        <a href="https://GapFound.github.io/GAP_Finder_dipendent_files/disclaimer.html" target="_blank">Data Disclaimer</a>
    </div>
""", unsafe_allow_html=True)
