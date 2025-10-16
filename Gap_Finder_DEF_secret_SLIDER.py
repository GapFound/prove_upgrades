#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Dec  5 11:34:33 2024

@author: ninni
"""

import numpy as np
import pandas as pd
import requests
#import matplotlib.pyplot as plt
#import matplotlib.dates as mdates
from datetime import datetime,timedelta,date
from pprint import pprint

from plotly.subplots import make_subplots
import plotly.graph_objects as go

#import ipywidgets as widgets
from IPython.display import display, clear_output

import yfinance as yf
from finvizfinance.quote import finvizfinance


import streamlit as st
import streamlit.components.v1 as components
from html import escape as html_escape


import pickle

import os

#from st_aggrid import AgGrid






#%%


# QUESTO BLOCCO CARICA I DATI DA YAHOO FINANCE E POI ELABORA IL DF DATI_STORICI
# QUINDI COME PRIMA COSA LANCIO LA FUNZIONE CHE FARà L'ELABORAZIONE PER POI CARICARE I DATI DA YFINANCE
# E LANCIARE LA FUNZIONE elaborazione()


#%%


# per prima inserisco la funzione che mette sempre in evidenza la barra di scroll delle tabelle

def render_table_with_slider(
    df,
    min_rows: int = 6,
    max_rows: int = 24,
    row_px: int = 26,      # ↓ righe più compatte (prima 28)
    header_px: int = 34,   # ↓ header più compatto (prima 36)
    padding_px: int = 14,  # ↓ padding verticale contenitore
    key: str = "tbl",
    escape: bool = True,
):
    # indice 1-based più stretto
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
    component_h = scroller_h + 36  # spazio slider

    html = f"""
    <div id="gf-wrap-{key}" style="
      position:relative; z-index:2147483000;
      width:100%; max-width:100%;
      box-sizing:border-box; overflow:visible;
      font-family: system-ui,-apple-system,Segoe UI,Roboto,sans-serif;">
      
      <div id="gf-scroller-{key}" style="
        overflow-y:auto; overflow-x:auto;
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
      /* Tabella più compatta e che non sfora la colonna */
      #gf-wrap-{key} table {{
        border-collapse: separate; border-spacing:0;
        width: max-content;
        max-width: calc(100% - 4px);     /* evita il taglio a destra */
        font-size:11.5px;                  /* ↓ font */
      }}
      #gf-wrap-{key} th, #gf-wrap-{key} td {{
        padding:4px 4.8px;                 /* ↓ padding */
        white-space:nowrap;
        border-bottom:1px solid #eee;    /* righe */
        border-right:1px solid #eee;     /* colonne (linee sottili) */
      }}
      #gf-wrap-{key} th:last-child, #gf-wrap-{key} td:last-child {{ border-right:none; }}
      #gf-wrap-{key} thead th {{
        position: sticky; top: 0;
        background:#fafafa; z-index:1;
      }}

      /* Colonna indice ancora più stretta */
      #gf-wrap-{key} thead th:first-child,
      #gf-wrap-{key} tbody td:first-child {{
        text-align:center;
        width:26px; min-width:26px; max-width:26px;
        color:#444;
      }}

      /* Nascondi SOLO la scrollbar orizzontale nativa in WebKit (rimane lo scroll via slider) */
      #gf-scroller-{key}::-webkit-scrollbar:horizontal {{ height:0px; display:none; }}
      #gf-scroller-{key} {{ scrollbar-gutter: stable both-edges; }}

      /* Slider (resta identico) */
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




# QUI ELABORO il df dati_storici e CREO  le features 'Max % UP' - 'Max % DOWN' - 'Open to Close %' e 'chiusura'


def elaborazione(dati_storici):
    
    #global dati_storici_ADJ 
    
    dati_storici['Gap %'] = ((dati_storici['Open']*100)/dati_storici['Close'].shift(1))-100

    colonna_da_spostare = dati_storici.pop('Gap %')
    dati_storici.insert(1,'Gap %',colonna_da_spostare)
    
    dati_storici['Max % UP'] = ((dati_storici['High']*100)/(dati_storici['Open']))-100
    dati_storici['Max % DOWN'] = ((dati_storici['Low']*100)/(dati_storici['Open']))-100
    dati_storici['Open to Close %'] = ((dati_storici['Close']*100)/(dati_storici['Open']))-100
    dati_storici['Chiusura'] = dati_storici.apply(lambda x: 'RED' if x['Open to Close %']<0 \
                                                  else 'GREEN' if x['Open to Close %']>0 else '=open', axis=1)
        
    
    
    # creo una copia di dati_storici per mantenere inalterati i prezzi corretti che serviranno x il grafico
    dati_storici_ADJ = dati_storici.round(3).copy()
    
   
    
   
    
   
    
    # creo un df transitorio dove inserire i risultati del calolo dello split factor:

    trans = pd.DataFrame(index=range(0,len(dati_storici)))
    trans['split_factor'] = 0



    # inizio con il calcolo:

    split_factor = 1


    for a in range((len(dati_storici)-1),-1,-1):
            if dati_storici['Stock Splits'].iloc[a] > 0:
                    #print(a)
                    
                    #aaa = split_factor
                    trans.loc[a,'split_factor'] = split_factor
                    split_factor = split_factor*dati_storici['Stock Splits'].iloc[a]
                    #print(split_factor)                                                              
                    #trans.loc[a,'split_factor'] = aaa
                          
            else:
                
                    trans.loc[a,'split_factor']=split_factor

                                
                            
                            
                            
    
    dati_storici['Open'] = dati_storici.apply(lambda x: x['Open']*trans.loc[x.name,'split_factor'] if\
                              (trans.loc[x.name,'split_factor']< 1) else \
                                  (x['Open']/trans.loc[x.name,'split_factor']),axis=1)
        
    dati_storici['High'] = dati_storici.apply(lambda x: x['High']*trans.loc[x.name,'split_factor'] if\
                              (trans.loc[x.name,'split_factor']< 1) else \
                                  (x['High']/trans.loc[x.name,'split_factor']),axis=1)
        
    dati_storici['Low'] = dati_storici.apply(lambda x: x['Low']*trans.loc[x.name,'split_factor'] if\
                              (trans.loc[x.name,'split_factor']< 1) else \
                                  (x['Low']/trans.loc[x.name,'split_factor']),axis=1)
        
    dati_storici['Close'] = dati_storici.apply(lambda x: x['Close']*trans.loc[x.name,'split_factor'] if\
                              (trans.loc[x.name,'split_factor']< 1) else \
                                  (x['Close']/trans.loc[x.name,'split_factor']),axis=1) 
        
        
    dati_storici['Volume'] = dati_storici.apply(lambda x: x['Volume']/trans.loc[x.name,'split_factor'] if\
                              (trans.loc[x.name,'split_factor']< 1) else \
                                  (x['Volume']*trans.loc[x.name,'split_factor']),axis=1)    
        
        
        

    
    
    dati_storici = dati_storici.round(3)
    
    
    
    
    
    
    return dati_storici_ADJ,dati_storici




#%%

# QUI RECUPERO I DATI DEGLI SPLITS dal DF dati_storici e li FORMATTO per POTERLI VISUALIZZARE

def formatta_splits(dati_storici):
    
    
    # creo la tabella con gli stock split factors
    split_df = dati_storici[(dati_storici['Stock Splits']>0)].loc[:,['Date','Stock Splits']] 
    split_df.index = split_df['Date']
    split_df.drop('Date',axis=1,inplace=True)
#     split_df.reset_index(drop=True,inplace=True)
#     split_df.index = split_df.index +1

    split_df['Stock Splits'] = split_df['Stock Splits'].apply(lambda x: f'1/{int(1/x)}' \
                                if x<1 else f'{x:.1f}/1'.replace('.',','))
    
    
    split_df.rename(columns={'Stock Splits':'split_factor'},inplace=True)
    
    
    return split_df
    
 
 
 #%%
 
 # PRENDO i DATI API dal PROVIDER 'FINANCIAL MODELING PREP' Creo un DF e lo restituisco
 
def stock_split(nome_ticker,cache_file,FMP_api_key):
     
     try:
         response = requests.get(f'https://financialmodelingprep.com/api/v3/historical-price-full/stock_split/{nome_ticker.upper()}?apikey={FMP_api_key}')
         data = response.json()
         
         
         if len(data['historical'])>0:
             
             #print('chiamata avvenuta con dati trovati')
             
             my_data = []
             for a in data['historical']:
                 single = {'Date':a['date'],'split_factor':eval(f"{a['numerator']/a['denominator']:.3f}")}
                 my_data.append(single)
                    
             
             splits_df = pd.DataFrame(my_data)
             splits_df.index =splits_df['Date']
             splits_df.drop('Date',axis=1,inplace=True)
             
             #print(splits_df) 
                 
             
         else:
             #print('chiamata avvenuta ma risposta vuota')
             splits_df = pd.DataFrame()  
             
             
        
         if len(data)>0: # scrive nella cache splits_df anche se non contiene dati di splits in modo che non venga, anche in questo caso, richiamato
             with open (cache_file,'wb') as f:
                   pickle.dump(splits_df,f) 
      
     
        
     
     
     except:  
         #print('errore di connessione')
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
    
    
    
    # fondamentali da yahoo finance
    
    try:
        ticker = yf.Ticker(nome_ticker.upper())
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
                            outstanding : prendi_trasforma_valore('sharesOutstanding'),
                            shares_float: prendi_trasforma_valore('floatShares'),
                            insider_own: aggiusto_perc('heldPercentInsiders'),
                            inst_own: aggiusto_perc('heldPercentInstitutions'),
                            short_float: aggiusto_perc('shortPercentOfFloat')}

        
    except:  
        
        fondamentali_yf = {market_cap:' - ',
                        outstanding: ' - ',   
                        shares_float:' - ',
                        insider_own:' - ',
                        inst_own:' - ',
                        short_float:' - ' }
    #print(fondamentali_yf)        
     
        
        
   
    # fondamentali da finviz
    finvitz_data = None
    
    tentativi = 1
    while tentativi < 5:

        try:
            
            finvitz_stampa = st.empty()
            
            
            with finvitz_stampa.container():
                
                st.write('loading...')
                
                
                stock = finvizfinance(nome_ticker)
                finvitz_data = stock.ticker_fundament()
                    
                ##
                
                def prendi_voce(voce):
                    try:
                        risposta = finvitz_data.get(voce)  
                    except:
                        risposta = ' - '
                    return risposta   
                
                        
                nationality_exchange = {'nation':prendi_voce("Country"),
                                        'exchange':prendi_voce("Exchange")}            
                    
                sector_industry = {'sector':prendi_voce("Sector"),
                                'industry':prendi_voce("Industry")}
                
                fondamentali_fz = {market_cap: prendi_voce('Market Cap'),
                                 outstanding:prendi_voce('Shs Outstand'),
                                shares_float:prendi_voce('Shs Float'),
                                insider_own:prendi_voce('Insider Own'),
                                inst_own: prendi_voce('Inst Own'),
                                short_float:prendi_voce('Short Float')}
                                                                             
                    
                finvitz_stampa.empty()
                #return fondamentali,news
                break   
                
                

        
        except: #Exception as e:
            
            #print(f'tentativo {tentativi}/5 di accesso ai dati finvitz fallito')
            finvitz_stampa.empty()
            tentativi += 1
            #display(e)
        
        
    if tentativi == 5: 
        #print("caricamento dati fondamentali da FINVITZ fallito")
        fondamentali_fz = {market_cap:' - ',
                        outstanding: ' - ',   
                        shares_float:' - ',
                        insider_own:' - ',
                        inst_own:' - ',
                        short_float:' - ' }
        
        
        nationality_exchange = {'nation':" - ",'exchange':" - "}
        sector_industry = {'sector':' - ','industry':' - '}
        news = 'problemi nel caricamento delle news da Finviz'
        #return fondamentali 
        
    
    
    # print(fondamentali_yf)   
    # print(fondamentali_fz)
     
        
    fond_fz_df = pd.DataFrame({'a':fondamentali_fz.keys(),'Fz':fondamentali_fz.values()})
    #print(fond_fz_df)
    fond_yf_df = pd.DataFrame({'a':fondamentali_yf.keys(),'Yf':fondamentali_yf.values()})
    #print(fond_yf_df)
    
    fond_df = fond_fz_df.merge(fond_yf_df,on='a').set_index('a')
    fond_df.index.name = None
    # fond_df.index = fond_df['a']
    # fond_df.drop('a',axis=1,inplace=True)
    
        

    return fond_df,nationality_exchange,sector_industry,website


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
                #return news 
                break
            
            elif 'timeout' in str(e):
                tentativi += 1 
                
                
            else:
                tentativi +=1
                
              
                
    
    if tentativi == 5:
        news = f'problemi nel caricamento delle news <b>{nome_ticker.upper()}</b> da Finviz'

    return news


#%%


# CARICO I VALORI di PREZZO DA YAHOO FINANCE


def yfinance_func(nome_ticker):
    
    
    dati_storici = pd.DataFrame ; splits_format = []
    # inserisci un TRY QUI. TRY a prendere i dati storici EXCEPT: STORICO sul PREZZO non disponibile.
    # dopo qualche mese e qualche errore...Inserito!
    
    try:
    
        # CARICO DA YFINANCE I DATI STORICI DI PREZZO
        ticker = yf.Ticker(nome_ticker.upper())   
        dati_storici = ticker.history(period="max")  # dati periodo massimo disponibile   
        #dati_storici.index = dati_storici.index.tz_localize(None)
        
        
        
        if len(dati_storici.columns)==7:  
            
            dati_storici.index = dati_storici.index.tz_localize(None)
            
    
    
            CACHE_DIR = "cache"
            os.makedirs(CACHE_DIR, exist_ok=True)
            #print(os.listdir('cache'))
        
            
            cache_file = os.path.join(CACHE_DIR, f"{nome_ticker.upper()}.pkl") #nomina il file + la posizione che avrà quando sarà salvato nella cache
            #print(cache_file)
            
            
            
            if os.path.exists(cache_file):
                with open(cache_file, "rb") as f:
                    #print(f"Caricamento dati splits {nome_ticker} dalla cache.")
                    splits_df = pickle.load(f)
            else:
                
                #print('provo a prendere i dati dal provider')
                FMP_api_key = st.secrets["FMP_api_key"]
                splits_df = stock_split(nome_ticker,cache_file,FMP_api_key)
               
            
                
                
                
                
                
        
            if not splits_df.empty:
                
                dati_storici.index = pd.to_datetime(dati_storici.index).normalize()
                splits_df.index = pd.to_datetime(splits_df.index).normalize()
                
               
        
                dati_storici = dati_storici.merge(splits_df['split_factor'],left_index=True,right_index=True,how='left')
                dati_storici['split_factor'] = dati_storici['split_factor'].fillna(0)
                
               
        
                dati_storici.drop('Stock Splits',axis=1,inplace=True)
                dati_storici.rename(columns={'split_factor':'Stock Splits'},inplace=True)
                
                dati_storici['Stock Splits'] = pd.to_numeric(dati_storici['Stock Splits'],errors='coerce')
                
                
            # else: 
            #     print('il ticker non ha splits/reverse splits, oppure...')
            #     print('non ho trovato i dati splits dal provider e quindi uso quelli base di YFINANCE')
                
            
            
            
            
            
            # APPORTO dei CORRETTIVI al DF dati_storici ORIGINALE e creo un DF splits_format per VISUALIZZARE gli SPLITS
            dati_storici = dati_storici.reset_index()
            dati_storici['Data'] = dati_storici['Date'].dt.date
            dati_storici.drop('Date',inplace=True,axis=1)
            dati_storici.rename(columns={'Data':'Date'},inplace=True)
            colonna_da_spostare = dati_storici.pop('Date')
            dati_storici.insert(0,'Date',colonna_da_spostare)
            
            splits_format = formatta_splits(dati_storici)
            
            # if not splits_df.empty:
            #     splits_df = splits_df.sort_index()
            #     splits_df.index = pd.to_datetime(splits_df.index).date
            #     splits_df['split_factor'] = splits_df['split_factor'].apply(lambda x: f'1/{int(1/x)}' \
            #                                             if x<1 else f'{x:.1f}/1'.replace('.',','))
            
            
                
                
            
            return dati_storici,splits_format
       
        
        
        
               
        
            
        else:
            
            splits_df = pd.DataFrame()
            
            if dati_storici.empty:
                st.write('Nonexistent or delisted title')
                return dati_storici,splits_df
        
            if len(dati_storici.columns)==8:
                st.write(f"{nome_ticker.upper()} it's not a stock")
                dati_storici = pd.DataFrame()
                return dati_storici,splits_df





    except:
        
        st.write('Yfinance server busy at the moment - try again') 
        return dati_storici,splits_format
        

#%%




                

# LA FUNZIONE CHE SEGUE CERCA I GAPS ALL'INTERNO DEL DF dati_storici 
# e CREA UN NUOVO DF GAPS CHE LI CONTIENE, 
# VEDIAMO IL RISULTATO ATTRAVERSO IL DF visual_gaps CHE E' UNA COPIA OTTIMIZZATA PER LA VISIONE 




def ricerca_gaps(nome_ticker,dati_storici,gap_perc_A,gap_perc_B,volume,prezzo_A,prezzo_B):
    

    # print(nome_ticker.upper(),'\n')
    # print(f'Storico GAPs >= {gap_perc_A}%')
    # print(f'con Volume minimo >= {volume/1000000:.2f} mln \n')
    
    global gaps
    
    gaps = dati_storici.iloc[:,[0,1,2,3,4,5,9,10,11,-1,6]].copy()
    
    
    #------------------------------------
    # verifico che non siano day 2 o più

    gaps['day1_extention'] = ((gaps['Close'].shift(1)*100)/gaps['Open'].shift(1))-100 
    
    # le righe qui sotto commentate servono a fare un eventuale controllo anche sul volume
    # controllo per adesso scartato
    #gaps['day1_volume'] = gaps['Volume'].shift(1)
    #gaps = gaps[(gaps['day1_volume']<=10_000_000)&(gaps['day1_extention']<30)] 
    
    gaps = gaps[(gaps['day1_extention']<30)]
    gaps.pop('day1_extention')
    
    # in queste rige sopra abbiamo eliminato dal gruppo dei gaps tutti i gaps che hanno una giornata precedente 
    # di  con estensionedi prezzo >= 30% e che quindi rendono il gaps da considerare già in Day 2 e non più day 1
    #-----------------------------------

    
        
    gaps = gaps[(gaps['Gap %']>=gap_perc_A)&\
                        (gaps['Gap %']<=gap_perc_B)&\
                        (gaps['Volume']>=volume)&(gaps['Open']>=prezzo_A)&(gaps['Open']<=prezzo_B)]
    
    
    if not gaps.empty:    
        # Effettuo adesso una copia del df gaps - solamente per poterla visualizzare
    
        display_gaps = gaps.copy()
            
            
        display_gaps['Volume'] = display_gaps.apply(lambda x: f"{x['Volume']:,.0f}".replace(',','.'),axis=1)
            
        display_gaps = display_gaps.round(2)
            
            
        display_gaps[['Gap %', 'Open', 'High', 'Low', 'Close', 'Max % UP',
               'Max % DOWN', 'Open to Close %']]=\
        display_gaps[['Gap %', 'Open', 'High', 'Low', 'Close', 'Max % UP',
               'Max % DOWN', 'Open to Close %']].astype(str).apply(lambda x: x.str.replace('.',',',regex=False))
            
            
            
        display_gaps.reset_index(drop=True,inplace=True)
        display_gaps.index = display_gaps.index+1
        
            
        
    
        return(display_gaps)
        
        
        
    else: 
        #print(f' il titolo {nome_ticker} non ha nessun gap superiore o uguale al {gap_perc_A}%')
        return gaps
        
        
#%%

## VISUALIZZA IL GRAFICO DEL GAP

def visual_gap(nome_ticker,n_gap,dati_storici_ADJ):
    
    global gaps
    #global dati_storici_ADJ
    
    finestra_daily = 100

    elementi_da_inizio_df = gaps.index[n_gap]
    if elementi_da_inizio_df > round(finestra_daily/2):
        finestra_A = round(finestra_daily/2)
    else:
        finestra_A = elementi_da_inizio_df
        
    #print(finestra_A )
    
        
    elementi_da_fine_df = (dati_storici_ADJ.shape[0])-elementi_da_inizio_df
    if elementi_da_fine_df > round(finestra_daily/2):
        finestra_B = round(finestra_daily/2)
    else:
        finestra_B = elementi_da_fine_df
    #print(finestra_B )    
    
    
    
    
    
    df = dati_storici_ADJ.iloc[gaps.index[n_gap]-(finestra_A)\
                               :gaps.index[n_gap]+(finestra_B),:].copy()
    
    
    # Crea una colonna con il testo da mostrare nel tooltip
    df['hover_text'] = (
        "Data: " + df['Date'].astype(str) + "<br>" +
        "Open: " + df['Open'].astype(str) + "<br>" +
        "High: " + df['High'].astype(str) + "<br>" +
        "Low: " + df['Low'].astype(str) + "<br>" +
        "Close: " + df['Close'].astype(str) + "<br>" +
        "Gap %: " + df['Gap %'].astype(str) + "<br>"
    )
    
    df['volume_text'] = df.apply(lambda x: f"{x['Volume']:,.0f}".replace(",","."),axis=1)
    df['volume_text'] = ("Volume: "+df['volume_text'].astype(str))
    
    
    
    # Crea il grafico con il testo personalizzato
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        row_heights=[0.8, 0.2],
        vertical_spacing= 0.15
    )
    
    # Aggiunta delle candele
    fig.add_trace(
        go.Candlestick(
            x=df['Date'],
            open=df['Open'],
            high=df['High'],
            low=df['Low'],
            close=df['Close'],
            name="Daily",
            hovertext=df['hover_text'],  # Assegna il testo personalizzato
            hoverinfo="text"  # Specifica di mostrare solo il testo personalizzato
        ),
        row=1, col=1
    )
    
    # Aggiunta del volume
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
    
    
    
    
    # Layout
    fig.update_layout(
    title=f"          <b>{nome_ticker.upper()}</b> -  Grafico Gap del {gaps.iloc[n_gap, 0]}",
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
    

    
    
    ## Riposiziona lo slider manualmente per metterlo sotto i volumi
    #fig.update_layout(
    #    xaxis_rangeslider=dict(
    #        visible=True,
    #        yanchor="bottom",  # Posiziona lo slider sotto
    #        thickness=0.1      # Spessore dello slider
    #    ),
    #    height=700  # Aumenta l'altezza per fare spazio allo slider
    #)
    
    
    # Configura il grafico per migliorare l'interattività
    st.plotly_chart(fig, use_container_width=False, config={
        'displayModeBar': True,  # Mostra la barra degli strumenti
        'responsive': True,      # Adatta il grafico al contenitore
        'scrollZoom': True,      # Abilita lo zoom con scroll
        'staticPlot': False     # Permette interazioni
    })




        


        
#%%    
        
#  INTERFACCIA UTENTE:
    
    
# QUI SETTO COME UTILIZZARE LO SPAZIO DELLA PAGINA WEB



st.set_page_config(
    page_title="GAPs Finder",
    page_icon="📈",
    layout="wide",  # 'centered' o 'wide'
    initial_sidebar_state="expanded",  # 'expanded' o 'collapsed'
                 ) 






col1,col2,col3 = st.columns([0.11,0.45,0.44])   
    
    
    

# INSERISCO il TICKER
global nome_ticker






with col1:
    
    
    
    st.markdown("""
            <style>
                .stTextInput>div>div>input {
                    font-size: 13px !important;  /* Riduce la dimensione del font */
                }
                
                /* Modifica il campo di input del testo */
                
                .stTextInput input {
                    font-size: 12px !important;  /* Riduce la dimensione del testo nell'input */
                    }  
            </style>
        """, unsafe_allow_html=True)

   
    
            
        
          
        
    with st.form(key=f'GAPs_Finder'):
            nome_ticker = st.text_input('**GAPs Finder v1.04pr**',placeholder='Enter the Ticker').strip()
            bottone_ricerca = st.form_submit_button('ricerca GAPs')
         
    
    stampa_col1 = st.empty()  
        
    
    
    if bottone_ricerca:
        
        #stampa_col1.empty()
        st.session_state.clear()
        
        st.session_state['slider_gaps']=(30,1000)
        st.session_state['slider_volume']=1
        st.session_state['slider_price']=(2,200)
        
        # verifico lo stato della chache
        
        CACHE_DIR = "cache"
        os.makedirs(CACHE_DIR, exist_ok=True)
        
        data_oggi = datetime.now().date()
        #data_oggi = date(2025,1,5)
        data_cache_name = os.path.join(CACHE_DIR,'data_cache.pkl')
        
        if os.path.exists(data_cache_name):
            with open(data_cache_name, "rb") as f:
                #print("Caricamento data dalla cache.")
                data_cache = pickle.load(f)
            
            if data_oggi>data_cache:
                #print(os.listdir('cache'))
                #print('cancello i files nerlla cache')#cancella la cache
                
                for file in os.listdir('cache'):
                    if file != 'contatore.pkl':
                        os.remove(os.path.join('cache', file))
                    
                with open(data_cache_name,"wb") as f:
                    pickle.dump(data_oggi,f)            
                
        else:
            #print('non esiste una data cache, la inserisco per la prima volta')
            with open(data_cache_name,"wb") as f:
                pickle.dump(data_oggi,f)
                
       
        #print(os.listdir('cache'))
            
        #------------------------------
        
        
        
        
        if nome_ticker:
            
            
            if nome_ticker != 'contatore':
                
                dati_yfinance,dati_split = yfinance_func(nome_ticker)
                
                ## INCREMENTO o CREO il CONTATORE VISITE
                CACHE_DIR = "cache"
                path_contatore = os.path.join(CACHE_DIR,'contatore.pkl')
                path_contatore_daily = os.path.join(CACHE_DIR,'contatore_daily.pkl')
                path_data_start_contatore = os.path.join(CACHE_DIR,'data_start_contatore.pkl')
                
                if os.path.exists(path_contatore):
                        with open(path_contatore,'rb') as f:
                            parziale = pickle.load(f)
                        
                        parziale +=1 
                    
                        with open(path_contatore,'wb') as f:
                            pickle.dump(parziale,f)
                            
                else:
                    os.makedirs(CACHE_DIR,exist_ok=True)
                    with open(path_contatore,'wb') as f:
                        pickle.dump(1,f)
                        
                    with open(path_data_start_contatore,'wb') as f:
                        data_start = datetime.strftime(datetime.now().date(),"%Y-%m-%d")
                        pickle.dump(data_start,f)
                        
                #----        
                            
                if os.path.exists(path_contatore_daily):
                    
                        with open(path_contatore_daily,'rb') as f:
                            parziale = pickle.load(f)
                        
                        parziale +=1 
                    
                        with open(path_contatore_daily,'wb') as f:
                            pickle.dump(parziale,f)    
                            
                        
                else:
                    os.makedirs(CACHE_DIR,exist_ok=True)
                        
                    with open(path_contatore_daily,'wb') as f:
                        pickle.dump(1,f) 
                        
                        
                #-------------------------------------------- 
                
            
                
            else:
                
                dati_yfinance= pd.DataFrame() # contatore è una chiamata particolare, per superare i successivi controlli ho bisogno del df dati_yfinance vuoto 
                CACHE_DIR = "cache"
                path_contatore = os.path.join(CACHE_DIR,'contatore.pkl')
                path_contatore_daily = os.path.join(CACHE_DIR,'contatore_daily.pkl')
                path_data_start_contatore = os.path.join(CACHE_DIR,'data_start_contatore.pkl')
                
                if os.path.exists(path_contatore):
                        with open(path_contatore,'rb') as f:
                            valore_contatore = pickle.load(f)
                            st.write(valore_contatore)
                            
                            
                else:
                    os.makedirs(CACHE_DIR,exist_ok = True)
                    with open(path_contatore,'wb') as f:
                        pickle.dump(0,f)
                        
                        
                
                if os.path.exists(path_data_start_contatore):            
                        with open(path_data_start_contatore,'rb') as f:
                            data_start = pickle.load(f) 
                             
                        st.write(data_start)
                                
                else:
                     os.makedirs(CACHE_DIR,exist_ok = True)
                     with open(path_data_start_contatore,'wb') as f:
                         data_start = datetime.strftime(datetime.now().date(),"%Y-%m-%d")
                         pickle.dump(data_start,f)
                         
                         
                        
                            
                if os.path.exists(path_contatore_daily):            
                        with open(path_contatore_daily,'rb') as f:
                            valore_contatore_daily = pickle.load(f) 
                             
                        st.write(valore_contatore_daily)
                        st.write(os.listdir('cache'))  
                        
                        
                                  
                else:
                    os.makedirs(CACHE_DIR,exist_ok = True)
                    with open(path_contatore_daily,'wb') as f:
                        pickle.dump(0,f)    
                        
            
            
            
            
            
            
            
            if not dati_yfinance.empty:
             
                dati_storici_ADJ,dati_storici_DEF = elaborazione(dati_yfinance)
                #dati_split = stock_split(dati_yfinance)
                fondamentali,nationality_exchange,sector_industry,website = fondamentali_func(nome_ticker)
                news = news_func(nome_ticker)
                
                
                st.session_state['dati_storici'] = dati_storici_DEF #dati_yfinance
                st.session_state['fondamentali'] = fondamentali
                st.session_state['website'] = website
                st.session_state['nationality_exchange'] = nationality_exchange
                st.session_state['sector_industry'] = sector_industry
                st.session_state['news'] = news
                st.session_state['dati_split'] = dati_split
                st.session_state['dati_storici_ADJ'] = dati_storici_ADJ
                
                
            #else: 
             #   st.write('non trovo dati su questo titolo')
                
        else:
            st.warning('Enter the Ticker')
            
            
            
            
            
            
    if 'dati_storici' in st.session_state and st.session_state['dati_storici'] is not None: #and 'dati_split' in st.session_state:
        
        
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

            

            st.markdown(f"""
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
                    """, unsafe_allow_html=True)

                    # <div style="font-size: 14px;">  
                    # <b>market cap</b>: {st.session_state['fondamentali_finvitz']['market cap']}<br>
                    # <b>shares float</b>: {st.session_state['fondamentali_finvitz']['shares float']}<br>
                    # <b>insider Own</b>: {st.session_state['fondamentali_finvitz']['insider Own.']}<br>
                    # <b>inst. Own</b>: {st.session_state['fondamentali_finvitz']['inst. Own.']}<br>
                    # <b>Short Float</b>: {st.session_state['fondamentali_finvitz']['Short Float']}
                    # </div>
            
            
            st.table(st.session_state['fondamentali'])
            #print(st.session_state['fondamentali'])
                   
                
            if not st.session_state['dati_split'].empty:
                st.write("")
                st.write("")
                st.markdown("<div style='font-size: 14px;'> <b>Splits / Reverse Splits</b> </div>", unsafe_allow_html=True)
                st.write("")
    
                for a,b in  st.session_state['dati_split'].iterrows():
                    #st.write(f"{b['Date']} - {b['Splits / REV Splits']}")
                     st.markdown(f"""
                                <div style="font-size: 13px;">
                                    {a} <b>&nbsp;&nbsp;--&nbsp;&nbsp;</b> {b['split_factor']}
                                </div>
                            """, unsafe_allow_html=True)


                    
               
                
               
                
with col2:
    
    st.markdown(
            """
            <style>
            table {
                font-size: 12px;  /* Dimensione del carattere */
                width: 100%;  /* Larghezza della tabella */
                margin-left: auto;  /* Allinea al centro */
                margin-right: auto; /* Allinea al centro */
            }
            thead th {
                font-size: 14px;  /* Dimensione del carattere dell'intestazione della tabella  */
            }
            tbody td {
                font-size: 13px;  /* Dimensione del carattere del contenuto della tabella */
            }
            
            
            
            
            .stTable td, .stTable th {
                white-space: nowrap !important;  /* Impedisce il ritorno a capo */   
            }
            
            # .stTable {
            #     font-size: 16px;  /* Imposta la dimensione del font */
            #     table-layout: fixed;  /* Fissa la larghezza delle colonne */
            #     width: 100%;
            #}
            
            
            .stSlider {
                margin-bottom: -20px; /* Riduce lo spazio verticale tra gli slider */
            }

            
  
            .stSlider div[data-testid="stMarkdownContainer"] p {
                font-size: 13px !important; /* Riduce l'etichetta dello slider */
            }
            </style>
            """,
            unsafe_allow_html=True
        )
    
   
    
     
    if 'dati_storici' in st.session_state and st.session_state['dati_storici'] is not None:
        
        

            # Slider per gestire i parametri di ricerca
            
            
           col2_1,col2_2,col2_3 = st.columns([0.25,0.5,0.25])
           with col2_2:
               gap_A,gap_B = st.slider("**Gap %**",0,1000,step=5,key='slider_gaps')
                    
               volume = st.slider("**Volume Minimo Mln**", 0,500,step=1,key='slider_volume')
                    
               prezzo_A,prezzo_B = st.slider('**prezzo minimo $**',0,200,step=1,key='slider_price')
               
               
               
              
           v_gaps = ricerca_gaps(nome_ticker,st.session_state['dati_storici'],\
                                 gap_A,gap_B,volume*1_000_000,prezzo_A,prezzo_B) 


           
           st.write("");st.write("")
           
           
               
           if not v_gaps.empty:
               #st.table(v_gaps)
               render_table_with_slider(
               v_gaps,
               min_rows=6,
               max_rows=24,
               row_px=28,
               key=f"gaps_{nome_ticker}")
               
               
               
               
           else:
               st.markdown(
                f"""
                <div style="text-align: center; font-size: 14.5px;">
                    <b>{nome_ticker.upper()}</b> non ha giornate rispondenti ai parametri settati
                </div>
                """,
                unsafe_allow_html=True)
               
               
           col2_4,col2_5,col2_6 = st.columns([0.20,0.83,0.14])
          
           with col2_5: 
                   
                   st.write("");st.write("");st.write("");st.write("");st.write("");#st.write("")
                   st.markdown(f"""
                                   <div style="text-align:center; font-size: 14px;">
                                   <b>{'news:'}<b/> <br/> <br/>
                                   </div>
                                   """, unsafe_allow_html=True)
                                   
                
                   # try:
                       
                   if isinstance(st.session_state['news'], pd.DataFrame):
                           for a,b in st.session_state['news'].iterrows():
                               
                                # #formatted_date = b['Date'].strftime("%d-%m-%y | h %H:%M")
                                # formatted_date = datetime.strptime(b['Date'], "%Y-%m-%d %H:%M:%S")
                               
                                ora = datetime.now().hour
                                
                                
                                
                                if ora <=6:
                                    formatted_date = b['Date'] - timedelta(days=1)
                                    data_ora = datetime.now()- timedelta(days=1)
                                else:
                                    formatted_date = b['Date']
                                    data_ora = datetime.now()
                                    
                                    
                                    
                                if formatted_date.date() != data_ora.date() and a > 0:
                                    #print(formatted_date,data_ora)
                                    break     
                                    
                               
                                data_da_stampa = formatted_date.strftime("%Y-%m-%d | h %H:%M")    
                        
                                  # Mostra l'output con la data formattata
                                   
                                with col2_5: 
                                    # st.markdown(f"""
                                    #             <div style="text-align:left; font-size: 13px;">
                                    #             <strong style="color: red;">{data_da_stampa}</strong>&nbsp;
                                    #             <a href="{b['Link']}" style="text-decoration: none; color: black;">
                                    #             {b['Title']}
                                    #             </a>
                                    #             </div>
                                            
                                    #             """, unsafe_allow_html=True)
                                    
                                    st.markdown(f"""
                                                <div style="text-align:left; font-size: 13px;">
                                                    <strong style="color: red;">{data_da_stampa}</strong>&nbsp;
                                                    <a href="{b['Link']}" style="text-decoration: none; color: inherit;">
                                                        {b['Title']}
                                                    </a>
                                                </div>
                                            """, unsafe_allow_html=True)
                                            
                                            
                                            
                                            
                                                
                   if isinstance(st.session_state['news'],str): #and len(st.session_state['news'])>0:
                           st.markdown(f"""
                                       <div style="text-align:center; font-size: 14px;">
                                       {st.session_state['news']}
                                       </a>
                                       </div>
                                   
                                       """, unsafe_allow_html=True)
 
                    
                   # except:
                   #      #st.write("");st.write("");st.write("");st.write("");st.write("");st.write("")
                   #      st.markdown(f"""
                   #                  <div style="text-align: center; font-size: 14px;">
                   #                  {f'<b>{nome_ticker.upper()}</b> has no news'}
                   #                  </div>
                   #                  """, unsafe_allow_html=True)
        
    
            
    
    
    
    
           
           if not v_gaps.empty:
                
                with col3:
                    
                    col3_1,col3_2 = st.columns([0.18,0.82])
                    with col3_1:
                        
                        options = list(v_gaps.index)
                        n_gap = st.selectbox('**gap da visualizzare**',options)
                        
                    if st.button('visualizza'):
                        try:
                            visual_gap(nome_ticker,(n_gap-1),st.session_state['dati_storici_ADJ'])
                        except:
                            st.markdown(
                             f"""
                             <div style="text-align: center; font-size: 15px;">
                                 grafico non disponibile
                             </div>
                             """,
                             unsafe_allow_html=True)

        
        






st.markdown("""
    <style>
        .footer {
            position: fixed;
            bottom: 0;
            width: 100%;
            text-align: center;
            background-color: #e0e0e0; /* Grigio chiaro neutro */
            padding: 6px;
        }
        .footer a {
            font-size: 12px; /* Scritta più piccola */
            text-decoration: none;
            color: blue; /* Puoi cambiare il colore del link se lo desideri */
        }
        .footer a:hover {
            text-decoration: underline;
        }
    </style>
    <div class="footer">
        <a href="https://GapFound.github.io/GAP_Finder_dipendent_files/disclaimer.html" target="_blank">Data Disclaimer</a>
    </div>
""", unsafe_allow_html=True)


#%%


