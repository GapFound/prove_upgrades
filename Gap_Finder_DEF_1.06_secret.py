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
from bs4 import BeautifulSoup

import yfinance as yf
from finvizfinance.quote import finvizfinance
import streamlit as st
import streamlit.components.v1 as components
import pickle
import os
import sys
import textwrap

# INIZIALIZZAZIONE DELLA SESSIONE GLOBALE PER EVITARE I BLOCCHI DI YAHOO FINANCE
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
})

#%%

# FUNZIONE UTILITY PER FORMATTARE I VALORI NUMERICI IN MILIONI O MILIARDI
def format_millions(val):
    if val is None:
        return ' - '
    try:
        val = float(val)
        if val >= 10**9:
            return f"${val/10**9:.2f}B"
        elif val >= 10**6:
            return f"${val/10**6:.2f}M"
        elif val >= 10**3:
            return f"${val/10**3:.2f}K"
        return f"${val:.2f}"
    except:
        return ' - '

# FUNZIONE INTERNA PER IL RECUPERO A CASCATA (FALLBACK) DEI TAG XBRL DELLA SEC (COMPRESO STANDARD IFRS / 20-F)
def get_latest_fact(us_gaap, tags):
    for tag in tags:
        node = us_gaap.get(tag)
        if node:
            units = node.get('units', {}).get('USD', [])
            if units:
                # Filtra solo i report ufficiali 10-Q (trimestrali), 10-K (annuali) e 20-F (esteri) per evitare duplicati
                official = [u for u in units if u.get('form') in ['10-Q', '10-K', '20-F']]
                if not official:
                    official = units
                # Ritorna il valore dell'ultimo report, il form e la lista completa
                return float(official[-1]['val']), official[-1].get('form', '10-Q'), official
    return None, None, None

# FUNZIONE PER ESTRARRE E CALCOLARE IL BURN RATE SULL'OPERATING CASH FLOW REALE (OCF)
def get_ocf_burn(us_gaap, cash_val):
    ocf_tags = [
        'NetCashProvidedByUsedInOperatingActivities',
        'NetCashProvidedByUsedInOperatingActivitiesContinuingOperations',
        'CashFlowsFromUsedInOperatingActivities',
        'NetCashFlowsFromUsedInOperatingActivities'
    ]
    ocf_val, ocf_form, ocf_units = get_latest_fact(us_gaap, ocf_tags)
    
    # Se il flusso di cassa operativo è positivo (generazione di cassa), ritorniamo 0.0 (nessun burn)
    if ocf_val is not None and ocf_val >= 0:
        return 0.0
        
    if ocf_val is not None and ocf_val < 0:
        # Trova l'ultima voce per calcolare i mesi di copertura reali dell'OCF (duration)
        latest_ocf = ocf_units[-1]
        try:
            start_dt = datetime.strptime(latest_ocf['start'], "%Y-%m-%d").date()
            end_dt = datetime.strptime(latest_ocf['end'], "%Y-%m-%d").date()
            ocf_months = (end_dt - start_dt).days / 30.4375
            if ocf_months < 1.0:
                ocf_months = 3.0 # Fallback trimestre
        except:
            ocf_months = 12.0 if ocf_form in ['10-K', '20-F'] else 3.0
        
        monthly_burn = -ocf_val / ocf_months
        return monthly_burn
    return None

# NORMALIZZAZIONE DEI VALORI NUMERICI DI STOCKANALYSIS PER ALLINEARLI ALLA NOTAZIONE MILIONE DI YFINANCE
def format_sa_numeric_value(val_str):
    if not val_str or val_str == ' - ':
        return ' - '
    val_str = val_str.strip()
    # Se il dato possiede già un suffisso noto, lo lasciamo inalterato
    if val_str.endswith(('M', 'B', 'K', '%')):
        return val_str
    try:
        # Rimuove le virgole per permettere il corretto parsing come float
        cleaned = val_str.replace(',', '')
        num = float(cleaned)
        if num >= 10**9:
            return f"{num/10**9:.2f}B"
        elif num >= 10**6:
            return f"{num/10**6:.2f}M"
        elif num >= 1000:
            # Converte e formatta i valori sotto il milione (es: 665,849 -> 0.67M)
            return f"{num/10**6:.2f}M"
        return f"{num:.2f}"
    except ValueError:
        return val_str

# FUNZIONE PER ESTRARRE I DATI STATISTICI FONDAMENTALI DA STOCKANALYSIS IN SOSTITUZIONE DI FINVIZ
def fetch_stockanalysis_stats(nome_ticker):
    default_stats = {
        'M.Cap': ' - ',
        'Outstand.': ' - ',
        'Float': ' - ',
        'Insider': ' - ',
        'Inst.O.': ' - ',
        'S.Float': ' - '
    }
    try:
        url = f"https://stockanalysis.com/stocks/{nome_ticker.lower()}/statistics/"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            
            stats = {}
            for row in soup.find_all('tr'):
                cells = row.find_all('td')
                if len(cells) >= 2:
                    label = cells[0].get_text(strip=True)
                    val = cells[1].get_text(strip=True)
                    stats[label] = val
            
            def find_val(possible_keys):
                for pk in possible_keys:
                    for k, v in stats.items():
                        if pk.lower() in k.lower():
                            return v
                return ' - '
            
            return {
                'M.Cap': format_sa_numeric_value(find_val(['market cap', 'market capitalization'])),
                'Outstand.': format_sa_numeric_value(find_val(['shares outstanding'])),
                'Float': format_sa_numeric_value(find_val(['float'])),
                'Insider': find_val(['owned by insiders']),
                'Inst.O.': find_val(['owned by institutions']),
                'S.Float': find_val(['short % of float'])
            }
    except Exception as e:
        print("Errore scraping StockAnalysis:", e)
    return default_stats

# FUNZIONE PER SCARICARE I DATI DI CASSA E RISK DILUTION DIRETTAMENTE DALLA SEC EDGAR (100% GRATUITA ED ILLIMITATA)
def fetch_sec_data(cik):
    default_sec = {
        'cash_on_hand': ' - ',
        'monthly_burn': ' - ',
        'runway_months': ' - ',
        'current_assets_ratio': ' - ',
        'liquidity_test': ' - ',
        'risk_status': 'UNKNOWN',
        'active_offering': 'Nessun deposito SEC recente per potenziale emissione di azioni (S-1, S-3, 424B) negli ultimi 180 giorni.',
        'active_offering_date': ' - ',
        'active_offering_form': ' - ',
        'sec_links': []
    }
    if not cik or str(cik).strip() in ['', '-', ' - ']:
        return default_sec
        
    try:
        cik_str = str(cik).strip().zfill(10)
        # SEC richiede obbligatoriamente un User-Agent identificativo chiaro
        headers = {'User-Agent': 'Luca Loiacono lucaloia@gmail.com'}
        
        # 1. Recupero dati finanziari (Company Facts) per Cash & Solvibilità
        facts_url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik_str}.json"
        facts_res = requests.get(facts_url, headers=headers)
        
        cash_val = None
        assets_val = None
        liabilities_val = None
        monthly_burn_val = None
        runway_str = " - "
        risk_status = "GREEN" # Default prudente in salute se c'è cassa
        
        if facts_res.status_code == 200:
            facts = facts_res.json()
            us_gaap = facts.get('facts', {}).get('us-gaap', {})
            
            # Dizionari di tag a cascata (fallback) per massima accuratezza su US-GAAP e IFRS (moduli 20-F straniere)
            cash_tags = [
                'CashAndCashEquivalentsAtCarryingValue',
                'CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents',
                'CashAndCashEquivalents',
                'Cash',
                'CashAndCashEquivalentsAtCarryingValueContinuingOperations'
            ]
            assets_tags = ['AssetsCurrent', 'CurrentAssets']
            liabilities_tags = ['LiabilitiesCurrent', 'CurrentLiabilities']
            
            cash_val, cash_form, cash_units = get_latest_fact(us_gaap, cash_tags)
            assets_val, _, _ = get_latest_fact(us_gaap, assets_tags)
            liabilities_val, _, _ = get_latest_fact(us_gaap, liabilities_tags)
            
            if cash_val is None:
                risk_status = "UNKNOWN"
            
            # Calcolo dei Ratio di solvibilità immediati
            ratio_str = " - "
            ratio_val = None
            if cash_val is not None and assets_val:
                ratio_val = (cash_val / assets_val) * 100
                ratio_str = f"{ratio_val:.2f}%"
                
            liq_str = " - "
            liq_val = None
            if cash_val is not None and liabilities_val:
                liq_val = cash_val / liabilities_val
                liq_str = f"{liq_val:.2f}"
                if liq_val < 1.2:
                    risk_status = "RED" # Sotto 1.2: Rischio insolvenza immediata
                elif liq_val < 1.5 and risk_status != "RED":
                    risk_status = "YELLOW"
            
            # DETERMINAZIONE DEL BURN RATE OPERATIVO REALE (OCF)
            ocf_burn = get_ocf_burn(us_gaap, cash_val)
            
            if ocf_burn is not None and cash_val is not None:
                if ocf_burn == 0.0:
                    # CASSA GENERATA DA OPERAZIONI (Vero Cash Flow Positivo)
                    monthly_burn_val = None
                    runway_str = "Cash Flow +"
                    risk_status = "GREEN"
                else:
                    # OPERAZIONI IN PERDITA (Vero Burn Rate Operativo)
                    monthly_burn_val = ocf_burn
                    runway_val = cash_val / monthly_burn_val
                    runway_str = f"{runway_val:.2f} Mesi"
                    if runway_val < 3.0:
                        risk_status = "RED"
                    elif runway_val < 12.0 and risk_status != "RED":
                        risk_status = "YELLOW"
            else:
                # FALLBACK: Variazione temporale del saldo di cassa se l'OCF è assente
                if cash_units:
                    # Seleziona i report ufficiali per ridurre il rumore, altrimenti usa tutti i record disponibili
                    official_units = [u for u in cash_units if u.get('form') in ['10-Q', '10-K', '20-F']]
                    target_units = official_units if official_units else cash_units
                    
                    unique_cash = {}
                    for u in target_units:
                        end_str = u.get('end')
                        val = u.get('val')
                        if end_str and val is not None:
                            try:
                                end_dt = datetime.strptime(end_str, "%Y-%m-%d").date()
                                # L'iterazione sequenziale sovrascrive i duplicati conservando l'ultimo dato depositato
                                unique_cash[end_str] = {
                                    'val': float(val),
                                    'date': end_dt
                                }
                            except ValueError:
                                pass
                    
                    # Ordina cronologicamente le date distinte ottenute
                    sorted_cash_periods = sorted(unique_cash.values(), key=lambda x: x['date'])
                    
                    if len(sorted_cash_periods) >= 2:
                        latest_period = sorted_cash_periods[-1]
                        prev_period = sorted_cash_periods[-2]
                        
                        latest_cash = latest_period['val']
                        prev_cash = prev_period['val']
                        
                        # Calcola i mesi reali trascorsi tra le due date di bilancio
                        date_diff = latest_period['date'] - prev_period['date']
                        months_diff = date_diff.days / 30.4375
                        
                        # Protezione contro record sovrapposti o anomali
                        if months_diff > 0.5:
                            cash_change = prev_cash - latest_cash # Se positivo, indica decremento (burn di cassa)
                            
                            if cash_change > 0:
                                monthly_burn_val = cash_change / months_diff
                                runway_val = latest_cash / monthly_burn_val
                                runway_str = f"{runway_val:.2f} Mesi"
                                if runway_val < 3.0:
                                    risk_status = "RED"
                                elif runway_val < 12.0 and risk_status != "RED":
                                    risk_status = "YELLOW"
                            elif cash_change < 0:
                                # SOLVENCY OVERRIDE: Se la liquidità è critica e la cassa sale, mostriamo trattino per incertezza sui finanziamenti
                                is_insolvent = False
                                if liq_val is not None and liq_val < 1.2:
                                    is_insolvent = True
                                if ratio_val is not None and ratio_val < 20.0:
                                    is_insolvent = True
                                    
                                if is_insolvent:
                                    monthly_burn_val = None
                                    runway_str = " - "
                                    risk_status = "RED"
                                else:
                                    monthly_burn_val = 0.0
                                    runway_str = "Cash Flow +"
                            else:
                                # Cassa rimasta perfettamente identica
                                monthly_burn_val = 0.0
                                runway_str = " - "
                        else:
                            monthly_burn_val = None
                            runway_str = " - "
                    else:
                        # Elementi insufficienti per calcolare la variazione cronologica (es. 1 solo bilancio)
                        monthly_burn_val = None
                        runway_str = " - "
                else:
                    # Nessun dato temporale di cassa registrato
                    monthly_burn_val = None
                    runway_str = " - "
        
        # 2. Recupero moduli depositati (Submissions) per trovare Offering attive negli ultimi 6 mesi
        sub_url = f"https://data.sec.gov/submissions/CIK{cik_str}.json"
        sub_res = requests.get(sub_url, headers=headers)
        
        active_offering = "Nessun deposito SEC recente per potenziale emissione di azioni (S-1, S-3, 424B) negli ultimi 180 giorni."
        active_offering_date = " - "
        active_offering_form = " - "
        sec_links = []
        
        if sub_res.status_code == 200:
            sub_data = sub_res.json()
            recent = sub_data.get('filings', {}).get('recent', {})
            
            forms = recent.get('form', [])
            dates = recent.get('filingDate', [])
            accessions = recent.get('accessionNumber', [])
            primary_docs = recent.get('primaryDocument', [])
            
            offering_forms = ["S-1", "S-3", "424B3", "424B4", "424B5", "424B7", "S-1/A", "S-3/A"]
            magic_words = ["common stock", "common shares", "ordinary shares", "at-the-market", "at the market"]
            debt_words = ["senior notes", "notes due", "debt securities", "senior debt", "underwritten notes"]
            found_offering = False
            links_count = 0
            seen_filings = set() # SET DI DEDUPLICAZIONE PER I DEPOSITI CONSULTABILI
            
            # Cerchiamo offering e raccogliamo gli ultimi 3 link rilevanti dei depositi
            for i in range(len(forms)):
                form_type = forms[i]
                filing_date = dates[i]
                acc_no = accessions[i].replace('-', '')
                doc = primary_docs[i]
                sec_link = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc_no}/{doc}"
                
                if form_type in ["10-K", "10-Q", "20-F", "S-1", "S-3", "424B3", "424B5"]:
                    filing_id = (filing_date, form_type)
                    if filing_id not in seen_filings:
                        if links_count < 3:
                            sec_links.append({
                                'date': filing_date,
                                'form': form_type,
                                'link': sec_link
                            })
                            seen_filings.add(filing_id)
                            links_count += 1
                        
                if form_type in offering_forms and not found_offering:
                    # Controlliamo che l'offering sia recente (ultimi 6 mesi = 180 giorni)
                    try:
                        filing_dt = datetime.strptime(filing_date, "%Y-%m-%d").date()
                        if (datetime.now().date() - filing_dt).days <= 180:
                            # SCRAPER INTERNO CHIRURGICO: Scarichiamo solo la copertina (primi 40KB) tramite HTTP Range Request per massima efficienza
                            range_headers = {
                                'User-Agent': 'Luca Loiacono lucaloia@gmail.com',
                                'Range': 'bytes=0-40000'
                            }
                            doc_res = requests.get(sec_link, headers=range_headers, timeout=5)
                            is_equity = False
                            
                            if doc_res.status_code in [200, 206]:
                                doc_text = doc_res.text.lower()
                                # Verifichiamo la presenza dei termini azionari e di debito
                                has_equity = any(word in doc_text for word in magic_words)
                                has_debt = any(word in doc_text for word in debt_words)
                                
                                # NUOVA LOGICA CON DISTINZIONE TRA REGISTRAZIONI PRIMARIE E SUPPLEMENTI
                                if form_type in ["S-1", "S-3", "S-1/A", "S-3/A"]:
                                    if has_equity:
                                        is_equity = True
                                else:
                                    # Per i moduli supplementari 424B applichiamo l'esclusione restrittiva dei bond
                                    if has_equity and not has_debt:
                                        is_equity = True
                            else:
                                # Fallback prudenziale di sicurezza in caso di errore della richiesta parziale
                                is_equity = True
                                
                            if is_equity:
                                active_offering = f" Form {form_type} depositato il {filing_date}"
                                active_offering_date = filing_date
                                active_offering_form = form_type
                                found_offering = True
                    except Exception as e:
                        print("Errore nel parsing del testo parziale del documento SEC:", e)
                    
        return {
            'cash_on_hand': format_millions(cash_val) if cash_val is not None else ' - ',
            'monthly_burn': format_millions(monthly_burn_val) if monthly_burn_val is not None else ' - ',
            'runway_months': runway_str,
            'current_assets_ratio': ratio_str,
            'liquidity_test': liq_str,
            'risk_status': risk_status,
            'active_offering': active_offering,
            'active_offering_date': active_offering_date,
            'active_offering_form': active_offering_form,
            'sec_links': sec_links
        }
    except Exception as e:
        print("Errore estrazione SEC EDGAR:", e)
        
    return default_sec

# FUNZIONE HELPER PER SCARICARE IL PROFILO AZIENDALE DA MASSIVE/POLYGON CON MAPPATURA MACRO-SETTORI E PAESI ISO
def fetch_polygon_profile(nome_ticker):
    default_profile = {
        'nationality_exchange': {'nation': " - ", 'nation_full': " - ", 'exchange': " - "},
        'sector_industry': {'sector': ' - ', 'industry': ' - '},
        'website': '',
        'cik': ''
    }
    try:
        # Supporta sia POLYGON_api_key che MASSIVE_api_key nei secrets
        api_key = st.secrets.get("POLYGON_api_key", st.secrets.get("MASSIVE_api_key", ""))
        if not api_key:
            return default_profile
            
        url = f"https://api.polygon.io/v3/reference/tickers/{nome_ticker.upper()}?apiKey={api_key}"
        res = requests.get(url).json()
        
        if res.get('status') == 'OK' and 'results' in res:
            results = res['results']
            
            # Mappatura dei codici MIC di Exchange più comuni
            exchange_map = {
                "XNAS": "NASDAQ",
                "XNYS": "NYSE",
                "ARCX": "NYSE ARCA",
                "BATS": "BATS",
                "XOTC": "OTC Markets"
            }
            raw_exchange = results.get('primary_exchange', ' - ')
            exchange_cleaned = exchange_map.get(raw_exchange, raw_exchange)
            
            # Mappatura intelligente del macro-settore tramite le prime due cifre del codice SIC
            sic_code = results.get('sic_code', '')
            sector = " - "
            if sic_code and len(sic_code) >= 2:
                prefix = sic_code[:2]
                try:
                    prefix_val = int(prefix)
                    if 1 <= prefix_val <= 9:
                        sector = "Agriculture, Forestry, Fishing"
                    elif 10 <= prefix_val <= 14:
                        sector = "Mining & Energy Extraction"
                    elif 15 <= prefix_val <= 17:
                        sector = "Construction"
                    elif 20 <= prefix_val <= 39:
                        sector = "Manufacturing"
                    elif 40 <= prefix_val <= 49:
                        sector = "Transportation & Utilities"
                    elif 50 <= prefix_val <= 51:
                        sector = "Wholesale Trade"
                    elif 52 <= prefix_val <= 59:
                        sector = "Retail Trade"
                    elif 60 <= prefix_val <= 67:
                        sector = "Finance, Insurance, Real Estate"
                    elif 70 <= prefix_val <= 89:
                        sector = "Services & Technology"
                    elif 91 <= prefix_val <= 99:
                        sector = "Public Administration"
                except ValueError:
                    pass
            
            # Se la mappatura SIC fallisce, usiamo la sic_description come fallback per il settore
            sic_desc = results.get('sic_description', ' - ').title()
            if sector == " - ":
                sector = sic_desc
                
            raw_locale = results.get('locale', 'US').upper()
            
            # DIZIONARIO OMNICOMPRENSIVO STANDARD ISO 3166-1 alpha-2
            country_map = {
                "AD": "Andorra", "AE": "United Arab Emirates", "AF": "Afghanistan", "AG": "Antigua and Barbuda",
                "AI": "Anguilla", "AL": "Albania", "AM": "Armenia", "AO": "Angola", "AQ": "Antarctica",
                "AR": "Argentina", "AS": "American Samoa", "AT": "Austria", "AU": "Australia", "AW": "Aruba",
                "AX": "Åland Islands", "AZ": "Azerbaijan", "BA": "Bosnia and Herzegovina", "BB": "Barbados",
                "BD": "Bangladesh", "BE": "Belgium", "BF": "Burkina Faso", "BG": "Bulgaria", "BH": "Bahrain",
                "BI": "Burundi", "BJ": "Benin", "BL": "Saint Barthélemy", "BM": "Bermuda", "BN": "Brunei",
                "BO": "Bolivia", "BQ": "Bonaire, Sint Eustatius and Saba", "BR": "Brazil", "BS": "Bahamas",
                "BT": "Bhutan", "BV": "Bouvet Island", "BW": "Botswana", "BY": "Belarus", "BZ": "Belize",
                "CA": "Canada", "CC": "Cocos (Keeling) Islands", "CD": "Congo (DRC)", "CF": "Central African Republic",
                "CG": "Congo (Republic)", "CH": "Switzerland", "CI": "Côte d'Ivoire", "CK": "Cook Islands",
                "CL": "Chile", "CM": "Cameroon", "CN": "China", "CO": "Colombia", "CR": "Costa Rica",
                "CU": "Cuba", "CV": "Cabo Verde", "CW": "Curaçao", "CX": "Christmas Island", "CY": "Cyprus",
                "CZ": "Czechia", "DE": "Germany", "DJ": "Djibouti", "DK": "Denmark", "DM": "Dominica",
                "DO": "Dominican Republic", "DZ": "Algeria", "EC": "Ecuador", "EE": "Estonia", "EG": "Egypt",
                "EH": "Western Sahara", "ER": "Eritrea", "ES": "Spain", "ET": "Ethiopia", "FI": "Finland",
                "FJ": "Fiji", "FK": "Falkland Islands", "FM": "Micronesia", "FO": "Faroe Islands", "FR": "France",
                "GA": "Gabon", "GB": "United Kingdom", "GD": "Grenada", "GE": "Georgia", "GF": "French Guiana",
                "GG": "Guernsey", "GH": "Ghana", "GI": "Gibraltar", "GL": "Greenland", "GM": "Gambia",
                "GN": "Guinea", "GP": "Guadeloupe", "GQ": "Equatorial Guinea", "GR": "Greece",
                "GS": "South Georgia & South Sandwich Islands", "GT": "Guatemala", "GU": "Guam", "GW": "Guinea-Bissau",
                "GY": "Government of Guyana", "HK": "Hong Kong", "HM": "Heard Island and McDonald Islands", "HN": "Honduras",
                "HR": "Croatia", "HT": "Haiti", "HU": "Hungary", "ID": "Indonesia", "IE": "Ireland",
                "IL": "Israel", "IM": "Isle of Man", "IN": "India", "IO": "British Indian Ocean Territory",
                "IQ": "Iraq", "IR": "Iran", "IS": "Iceland", "IT": "Italy", "JE": "Jersey", "JM": "Jamaica",
                "JO": "Jordan", "JP": "Japan", "KE": "Kenya", "KG": "Kyrgyzstan", "KH": "Cambodia",
                "KI": "Kiribati", "KM": "Comoros", "KN": "Saint Kitts and Nevis", "KP": "North Korea",
                "KR": "South Korea", "KW": "Kuwait", "KY": "Cayman Islands", "KZ": "Kazakhstan",
                "LA": "Laos", "LB": "Lebanon", "LC": "Saint Lucia", "LI": "Lichtenstein", "LK": "Sri Lanka",
                "LR": "Liberia", "LS": "Lesotho", "LT": "Lithuania", "LU": "Luxembourg", "LV": "Latvia",
                "LY": "Libya", "MA": "Morocco", "MC": "Monaco", "MD": "Moldova", "ME": "Montenegro",
                "MF": "Saint Martin", "MG": "Madagascar", "MH": "Marshall Islands", "MK": "North Macedonia",
                "ML": "Mali", "MM": "Myanmar", "MN": "Mongolia", "MO": "Macao", "MP": "Northern Mariana Islands",
                "MQ": "Martinique", "MR": "Mauritania", "MS": "Montserrat", "MT": "Malta", "MU": "Mauritius",
                "MV": "Maldives", "MW": "Malawi", "MX": "Mexico", "MY": "Malaysia", "MZ": "Possession", "NA": "Namibia",
                "NC": "New Caledonia", "NE": "Niger", "NF": "Norfolk Island", "NG": "Nigeria",
                "NI": "Nicaragua", "NL": "Netherlands", "NO": "Norway", "NP": "Nepal", "NR": "Nauru",
                "NU": "Niue", "NZ": "New Zealand", "OM": "Oman", "PA": "Panama", "PE": "Peru", "PF": "French Polynesia",
                "PG": "Papua New Guinea", "PH": "Philippines", "PK": "Pakistan", "PL": "Poland",
                "PM": "Saint Pierre and Miquelon", "PN": "Pitcairn Islands", "PR": "Puerto Rico", "PS": "Palestine",
                "PT": "Portugal", "PW": "Palau", "PY": "Paraguay", "QA": "Qatar", "RE": "Réunion", "RO": "Romania",
                "RS": "Serbia", "RU": "Russia", "RW": "Rwanda", "SA": "Saudi Arabia", "SB": "Solomon Islands",
                "SC": "Seychelles", "SD": "Sudan", "SE": "Sweden", "SG": "Singapore", "SH": "Saint Helena",
                "SI": "Slovenia", "SJ": "Svalbard and Jan Mayen", "SK": "Slovakia", "SL": "Sierra Leone",
                "SM": "San Marino", "SN": "Senegal", "SO": "Supporters", "SR": "Suriname", "SS": "South Sudan",
                "ST": "São Tomé and Príncipe", "SV": "El Salvador", "SX": "Sint Maarten", "SY": "Syria",
                "SZ": "Eswatini", "TC": "Turks and Caicos Islands", "TD": "Chad", "TF": "French Southern Territories",
                "TG": "Togo", "TH": "Thailand", "TJ": "Tajikistan", "TK": "Tokelau", "TL": "Timor-Leste",
                "TM": "Turkmenistan", "TN": "Turnip", "TO": "Tonga", "TR": "Turkey", "TT": "Trinidad and Tobago",
                "TV": "Tuvalu", "TW": "Taiwan", "TZ": "Tanzania", "UA": "Ukraine", "UG": "Uganda",
                "UM": "U.S. Outlying Islands", "US": "United States", "UY": "Uruguay", "UZ": "Uzbekistan",
                "VA": "Vatican City", "VC": "Saint Vincent and the Grenadines", "VE": "Venezuela",
                "VG": "British Virgin Islands", "VI": "U.S. Virgin Islands", "VN": "Vietnam", "VU": "Vanuatu",
                "WF": "Wallis and Futuna", "WS": "Samoa", "YE": "Yemen", "YT": "Mayotte", "ZA": "South Africa",
                "ZM": "Zambia", "ZW": "Zimbabwe"
            }
            nation_full = country_map.get(raw_locale, raw_locale)
            
            return {
                'nationality_exchange': {
                    'nation': raw_locale,
                    'nation_full': nation_full,
                    'exchange': exchange_cleaned
                },
                'sector_industry': {
                    'sector': sector,
                    'industry': sic_desc
                },
                'website': results.get('homepage_url', ''),
                'cik': results.get('cik', '') # Estraiamo ed inviamo in cache il CIK
            }
    except Exception as e:
        print("Errore chiamata Polygon/Massive:", e)
        
    return default_profile

# FUNZIONE PERSONALIZZATA PER LA BARRA DI SCROLL ORIZZONTALE SULLE TABELLE (CON REATTIVITA' E LIMITAZIONE INGOMBRO AL 95% SENZA SCALARE I CARATTERI)
def render_table_with_slider(
    df,
    min_rows: int = 6,
    max_rows: int = 24,
    row_px: int = 26,
    header_px: int = 34,
    padding_px: int = 14,
    key: str = "tbl",
    escape: bool = True,
    reset_index: bool = True,
    font_px: float = 11.5,
    width_pct: int = 95
):
    try:
        if reset_index:
            df2 = df.copy()
            df2.index = range(1, len(df2) + 1)
            df2.index.name = ""
        else:
            df2 = df.copy()
    except Exception:
        df2 = df

    html_table = df2.to_html(border=0, classes="gf-table", index=True, escape=escape)

    rows = int(df2.shape[0])
    target_rows = max(min_rows, min(rows, max_rows))
    scroller_h = header_px + row_px * target_rows + padding_px
    component_h = scroller_h + 36

    # ALLINEAMENTO DIFFERENZIATO: Centrato per i gappers (col2), allineato rigorosamente a sinistra per i fondamentali (col1)
    margin_style = "margin: 0 auto;" if key == "gaps" else "margin-left: 0; margin-right: auto;"
    
    # RIMOZIONE DI SICUREZZA DI MAX-WIDTH PER I FONDAMENTALI PER EVITARE CHE LE CELLE SI COMPRIMANO (SQUEEZINO) CON DATI CORPOSI
    max_width_style = "max-width: calc(100% - 4px);" if key == "gaps" else "max-width: none !important;"

    html = f"""
    <div id="gf-wrap-{key}" style="
      position:relative; z-index:2147483000;
      width:{width_pct}%; max-width:{width_pct}%; {margin_style}
      box-sizing:border-box; overflow:visible;
      font-family: system-ui,-apple-system,Segoe UI,Roboto,sans-serif;">

      <div id="gf-scroller-{key}" style="
        overflow-y:auto; overflow-x:hidden;
        height:{scroller_h}px;
        width:100%; max-width:100%; box-sizing:border-box;
        padding-bottom:2px; padding-right:2px;">
        <div id="gf-content-{key}">
          {html_table}
        </div>
      </div>

      <div id="gf-slider-wrap-{key}" class="gf-slider">
        <div class="gf-track"></div>
        <div id="gf-fill-{key}" class="gf-fill"></div>
        <div id="gf-handle-{key}" class="gf-handle"></div>
        <input id="gf-range-{key}" class="gf-range-ghost" type="range" min="0" max="1000" value="0">
      </div>
    </div>

    <style>
      /* ANNULLAMENTO MARGINI DI DEFAULT DEL BROWSER NELL'IFRAME PER ALLINEAMENTO MILLIMETRICO */
      body {{
        margin: 0 !important;
        padding: 0 !important;
      }}

      /* MODALITA' CHIARO (Default originaria) */
      #gf-wrap-{key} table {{
        border-collapse: separate; border-spacing:0;
        width: max-content;
        {max_width_style}
        font-size:{font_px}px;
        color: #111;
        background: #ffffff;
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
        color: #111;
        text-align: center !important; /* FORZATA LA CENTRATURA DI TUTTE LE INTESTAZIONI COLONNA */
      }}
      #gf-wrap-{key} thead th:first-child,
      #gf-wrap-{key} tbody td:first-child {{
        text-align:center;
        width:26px; min-width:26px; max-width:26px;
        color:#444;
      }}
      #gf-scroller-{key} {{
        border:1px solid #ddd;
        background: #ffffff;
        -ms-overflow-style: none;        
        scrollbar-width: none;           
      }}
      #gf-scroller-{key}::-webkit-scrollbar:horizontal {{ height:0px; display:none; }}  

      .gf-slider {{ position:relative; height:34px; margin-top:2px; z-index:2147483200; overflow:visible; }}
      .gf-track  {{ position:absolute; left:10px; right:10px; top:40%; height:3px; background:#e5e7eb; transform:translateY(-50%); border-radius:2px; z-index:1; }}
      .gf-fill   {{ position:absolute; left:10px; top:40%; height:3px; background:#d00; transform:translateY(-50%); border-radius:2px; width:0px; z-index:2; }}
      .gf-handle {{ position:absolute; top:40%; width:12px; height:12px; background:#d00; border:2px solid #fff; border-radius:50%; transform:translate(-50%,-50%); left:10px; box-shadow:0 0 0 1px rgba(0,0,0,.15); cursor:grab; z-index:2147483400; }}
      .gf-handle:active {{ cursor:grabbing; }}
      .gf-range-ghost {{ position:absolute; left:0; right:0; top:0; bottom:0; width:100%; height:100%; opacity:0; cursor:ew-resize; z-index:2147483300; }}

      /* MODALITA' SCURO (Overriding reattivo basato sulle preferenze browser/Streamlit) */
      @media (prefers-color-scheme: dark) {{
        #gf-wrap-{key} table {{
          color: #ffffff;
          background: #000000;
        }}
        #gf-wrap-{key} thead th {{
          background: #000000;
          color: #ffffff;
        }}
        #gf-wrap-{key} th, #gf-wrap-{key} td {{
          border-bottom: 1px solid #333;
          border-right: 1px solid #333;
          color: #ffffff;
        }}
        #gf-scroller-{key} {{
          border: 1px solid #333;
          background: #000000;
        }}
        #gf-wrap-{key} thead th:first-child,
        #gf-wrap-{key} tbody td:first-child {{
          color: #cccccc;
        }}
      }}

      /* AGGIUNTA DEL COSTRUTTO DEL TOOLTIP DENTRO L'IFRAME CON GRAFFE DOPPIE PER EVITARE NAMEERROR DI PYTHON */
      .gf-tooltip {{
        position: relative;
        display: inline-block;
        cursor: help;
      }}
      .gf-tooltip .gf-tooltiptext {{
        visibility: hidden;
        width: 140px;
        background-color: #212121;
        color: #ffffff;
        text-align: center;
        border-radius: 4px;
        padding: 6px;
        position: absolute;
        z-index: 2147483647;
        bottom: 130%;
        left: 50%;
        transform: translateX(-50%);
        opacity: 0;
        font-size: 11px;
        font-weight: normal;
        font-family: system-ui, -apple-system, sans-serif;
        line-height: 1.3;
        pointer-events: none;
        box-shadow: 0 2px 6px rgba(0,0,0,0.15);
        border: 1px solid #444;
        transition: opacity 0.1s;
      }}
      .gf-tooltip .gf-tooltiptext.gf-tooltip-down {{
        bottom: auto;
        top: 130%;
        left: 0;
        transform: none;
      }}
      .gf-tooltip:hover .gf-tooltiptext {{
        visibility: visible;
        opacity: 1;
      }}
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
      rangeEl.addEventListener("input",  syncSliderFromScroll);
      rangeEl.addEventListener("change", syncSliderFromScroll);

      new ResizeObserver(syncSliderFromScroll).observe(content);
      new ResizeObserver(syncSliderFromScroll).observe(sliderBox);
      window.addEventListener("load", syncSliderFromScroll);
      setTimeout(syncSliderFromScroll, 120);
    </script>
    """
    
    # RISOLUZIONE BUG DI IMPILAMENTO Z-INDEX: Forziamo la cella d'angolo <th> ad avere z-index: 10 !important per sovrastare permanentemente le celle adiacenti
    if key == "fond":
        corner_html = '<th style="cursor:help; text-align:center; vertical-align:middle; position:sticky; top:0; z-index:10 !important;"><span class="gf-tooltip" style="display:inline-block; width:11px; height:11px; line-height:10px; border:1px solid #000000; border-radius:50%; text-align:center; font-size:7.5px; font-weight:bold; color:#000000; font-family:system-ui;">?<span class="gf-tooltiptext gf-tooltip-down">Sa = StockAnalysis<br>Yf = YahooFinance</span></span></th>'
        html = html.replace('<th></th>', corner_html, 1)

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

# CARICO I DATI FONDAMENTALI DA YFINANCE ED ESEGUO LO SCRAPING DI STATISTICA DA STOCKANALYSIS

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
        fondamentali_yf = {market_cap: ' - ', outstanding: ' - ', shares_float: ' - ', insider_own: ' - ', inst_own: ' - ', short_float: ' - ' }
     
    # Carichiamo direttamente il profilo (Settore, Exchange, Website, Nazione) gestito dalla Cache in datagathering_func
    cached_profile = st.session_state.get('cached_profile', None)
    
    # Inizializzazione sicura dei valori di default
    nationality_exchange = {'nation': " - ", 'nation_full': " - ", 'exchange': " - "}
    sector_industry = {'sector': ' - ', 'industry': ' - '}
    
    # Se il profilo in cache è un dizionario valido, lo processiamo in sicurezza per evitare KeyError/TypeError da cache corrotte
    if isinstance(cached_profile, dict):
        raw_nat_exc = cached_profile.get('nationality_exchange')
        if isinstance(raw_nat_exc, dict):
            nationality_exchange = raw_nat_exc
            
            # SUPER FALLBACK: Se nation_full è assente o è un trattino vuoto, lo ricalcoliamo all'istante dalla sigla 'nation'
            if 'nation_full' not in nationality_exchange or nationality_exchange.get('nation_full') in [' - ', '---', '-', '', None]:
                raw_locale = nationality_exchange.get('nation', 'US')
                if not isinstance(raw_locale, str):
                    raw_locale = 'US'
                raw_locale = raw_locale.upper()
                
                country_map_short = {
                    "US": "United States", "CN": "China", "KY": "Cayman Islands", 
                    "GB": "United Kingdom", "CA": "Canada", "IL": "Israel", 
                    "SG": "Singapore", "HK": "Hong Kong", "AU": "Australia"
                }
                nationality_exchange['nation_full'] = country_map_short.get(raw_locale, raw_locale)
            
        raw_sec_ind = cached_profile.get('sector_industry')
        if isinstance(raw_sec_ind, dict):
            sector_industry = raw_sec_ind
            
        if not website:
            website = cached_profile.get('website', '')
        
    # 3. Fondamentali da StockAnalysis (in sostituzione permanente di Finviz)
    fondamentali_sa = fetch_stockanalysis_stats(nome_ticker)
        
    fond_sa_df = pd.DataFrame({'a': fondamentali_sa.keys(), 'Sa': fondamentali_sa.values()})
    fond_yf_df = pd.DataFrame({'a': fondamentali_yf.keys(), 'Yf': fondamentali_yf.values()})
    
    fond_df = fond_sa_df.merge(fond_yf_df, on='a').set_index('a')
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

# CARICO I VALORI di PREZZO (E GESTIONE LAZY-LOAD CACHE DEL PROFILO CON MAPPATURA MACRO-SETTORI POLGYON/MASSIVE)

def datagathering_func(nome_ticker):
    dati_storici = pd.DataFrame(); splits_format = pd.DataFrame(); caricato = 0; provider = "" 
    
    CACHE_DIR = "cache"
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_file = os.path.join(CACHE_DIR, f"{nome_ticker.upper()}.pkl")
    print(cache_file)
        
    if os.path.exists(cache_file):
          with open(cache_file, "rb") as fp:
              print(f"Caricamento dati daily, splits e profilo {nome_ticker} dalla cache.")
              cache_data = pickle.load(fp)
              dati_storici = cache_data['dati_storici']
              splits_format = cache_data['splits']
              provider = cache_data['provider']
              
              profile_data = cache_data.get('profile', None)
              
              # Controllo profilo (anagrafica fissa immobile, i dati SEC non vengono scritti per renderli 100% real-time)
              needs_profile_update = False
              if profile_data is None or not isinstance(profile_data, dict):
                  needs_profile_update = True
              elif not profile_data.get('cik') or str(profile_data.get('cik')).strip() in ['', '-', ' - ']:
                  needs_profile_update = True
              
              if needs_profile_update and not dati_storici.empty:
                  print("Profilo incompleto o obsoleto in cache. Aggiorno i dati anagrafici.")
                  profile_data = fetch_polygon_profile(nome_ticker)
                  try:
                      cache_data['profile'] = profile_data
                      with open(cache_file, 'wb') as out_fp:
                          pickle.dump(cache_data, out_fp)
                  except Exception as e:
                      print("Errore nell'aggiornamento della cache profilo:", e)
              
              st.session_state['cached_profile'] = profile_data
              caricato = 1
   
    if caricato == 0:
        # Ticker totalmente nuovo: scarichiamo il profilo da MASSIVE/Polygon una sola volta e lo scriviamo in cache
        print("Nuovo Ticker. Scarico il profilo da Massive/Polygon.")
        fmp_profile = fetch_polygon_profile(nome_ticker)
        
        st.session_state['cached_profile'] = fmp_profile
        
        try:     
            print(f'provo a prendere i dati splits di {nome_ticker} da FMP')
            FMP_api_key = st.secrets["FMP_api_key"]
            splits_df = stock_split(nome_ticker, cache_file, FMP_api_key)
        except:
             splits_df=pd.DataFrame()
                
        try:
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
                
                # SPOSTATA DEFINITIVAMENTE LA CONVERSIONE NUMERICA DENTRO LA PROTEZIONE DI SICUREZZA PER PREVENIRE IL KEYERROR
                cols = ['Open', 'High', 'Low', 'Close', 'Volume']
                dati_storici[cols] = dati_storici[cols].apply(pd.to_numeric, errors='coerce')
                dati_storici.sort_index(ascending=True, inplace=True) 
                
            print('prima delle trasformazioni')
            print(dati_storici[:5].to_string() if not dati_storici.empty else "Dati vuoti")
            
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
                   pickle.dump({
                       'dati_storici': dati_storici, 
                       'splits': splits_format, 
                       'provider': provider,
                       'profile': fmp_profile
                   }, fp)
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

## VISUALIZZA IL GRAFICO DEL GAP (NON PIÙ USATO MA MANTENUTO PER COMPATIBILITÀ)

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
) 

# MOTORE REATTIVO CSS (Imposta le variabili in base al tema scuro o chiaro rilevato, con Tooltip istantaneo)
st.markdown("""
    <style>
      :root {
        --card-bg: #fafafa;
        --card-border: #eee;
        --badge-bg: #ffffff;
        --badge-border: #e0e0e0;
        --text-news: #111111;
        --date-color: #666666;
        --sec-link-color: #d00;
      }
      @media (prefers-color-scheme: dark) {
        :root {
          --card-bg: #000000;
          --card-border: #333333;
          --badge-bg: #000000;
          --badge-border: #333333;
          --text-news: #ffffff;
          --date-color: #aaaaaa;
          --sec-link-color: #ff4b4b;
        }
      }

      /* STILE DEL TOOLTIP ISTANTANEO IN PURO CSS */
      .gf-tooltip {
        position: relative;
        display: inline-block;
        cursor: help;
      }
      .gf-tooltip .gf-tooltiptext {
        visibility: hidden;
        width: 160px;
        background-color: #212121;
        color: #ffffff;
        text-align: center;
        border-radius: 4px;
        padding: 6px;
        position: absolute;
        z-index: 2147483647;
        bottom: 130%; /* mostrato sopra di default */
        left: 50%;
        transform: translateX(-50%);
        opacity: 0;
        font-size: 11px;
        font-weight: normal;
        font-family: system-ui, -apple-system, sans-serif;
        line-height: 1.3;
        pointer-events: none;
        box-shadow: 0 2px 6px rgba(0,0,0,0.15);
        border: 1px solid #444;
        transition: opacity 0.1s;
      }
      /* Posizionamento specifico verso il basso per l'angolo a sinistra */
      .gf-tooltip .gf-tooltiptext.gf-tooltip-down {
        bottom: auto;
        top: 130%;
        left: 0;
        transform: none;
      }
      .gf-tooltip:hover .gf-tooltiptext {
        visibility: visible;
        opacity: 1;
      }
    </style>
""", unsafe_allow_html=True)

# PROPORZIONI RIPRISTINATE: COLONNA 1 AL PESO ORIGINALE DI 0.11, COLONNA 2 AL 49% E COLONNA 3 AL 40% PER MASSIMA OMOGENEITA' VISIVA
col1, col2, col3 = st.columns([0.11, 0.49, 0.40])   
    
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

            # MODIFICA APPORTATA: Distanziamento impostato a 10px precisi per l'industria per separarla armoniosamente dalla tabella
            ticker_info_html = (
                f'<div style="font-size: 22px; font-weight: bold; margin-bottom: 0px; line-height: 1.1;">{ticker_html}</div>'
                f'<div style="font-size: 13.5px; font-weight: bold; color: #d00; margin-bottom: 8px;">{st.session_state.get("nationality_exchange", {}).get("nation_full", " - ")}</div>'
                f'<div style="font-size: 12px; margin-bottom: 5px;"><b>{st.session_state.get("nationality_exchange", {}).get("nation", " - ")} - {st.session_state.get("nationality_exchange", {}).get("exchange", " - ")}</b></div>'
                f'<div style="font-size: 12px; font-weight: normal; color: #444;">{st.session_state.get("sector_industry", {}).get("sector", " - ")}</div>'
                f'<div style="font-size: 12px; font-weight: normal; color: #444; margin-bottom: 10px;">{st.session_state.get("sector_industry", {}).get("industry", " - ")}</div>'
            )
            st.markdown(ticker_info_html, unsafe_allow_html=True)

            # COPIA DEL DATAFRAME PER INIETTARE L'HTML DEL PUNTO INTERROGATIVO CON TOOLTIP NELLA CELLA IN ALTO A SINISTRA (escape=False)
            fond_df_copy = st.session_state['fondamentali'].copy()

            # INTEGRATA LA FUNZIONE RENDER_TABLE_WITH_SLIDER SULLA COLONNA 1 DEI FONDAMENTALI (reset_index=False per mantenere M.Cap, Outstand, ecc. e font_px=10.0 per massima leggibilita' ed ingombro al 100% della colonna stretta 0.11)
            render_table_with_slider(fond_df_copy, key="fond", reset_index=False, font_px=10.0, min_rows=6, max_rows=6, width_pct=100, escape=False)
            print(st.session_state['fondamentali'])
                   
            if not st.session_state['dati_split'].empty:
                # Spazio verticale ridotto elegantemente tramite CSS margin-top e margin-bottom
                st.markdown("<div style='font-size: 14px; margin-top: 15px; margin-bottom: 8px;'><b>Splits / Reverse Splits</b></div>", unsafe_allow_html=True)
    
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
            .stTable {
                max-width: 100% !important;
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
               # INTEGRATA LA FUNZIONE RENDER_TABLE_WITH_SLIDER SULLA COLONNA 2 DEI GAPPERS (reset_index=True, ingombro riallineato stabilmente al 95% per simmetria perfetta)
               render_table_with_slider(v_gaps, key="gaps", reset_index=True, font_px=11.5, width_pct=95)
               
               # CALCOLO E VISUALIZZAZIONE DELLE STATISTICHE DI CHIUSURA RED/GREEN DEI GAPPER FILTRATI (CON CONTEGGIO MINIMALISTA IN REGULAR)
               total_gaps = len(v_gaps)
               red_count = len(v_gaps[v_gaps['Chiusura'] == 'RED'])
               green_count = len(v_gaps[v_gaps['Chiusura'] == 'GREEN'])
               
               red_pct = (red_count / total_gaps) * 100
               green_pct = (green_count / total_gaps) * 100
               
               # CALCOLO ROBUSTO E DINAMICO DELLE MEDIANE DELLE COLONNE RICHIESTE SUL DATAFRAME NUMERICO "GAPS"
               med_gap = gaps['Gap %'].median()
               med_up = gaps['Max % UP'].median()
               med_down = gaps['Max % DOWN'].median()
               med_otc = gaps['Open to Close %'].median()
               
               # FORMATTAZIONE COERENTE IN STANDARD ITALIANO (SOSTITUZIONE PUNTO CON VIRGOLA)
               med_gap_str = f"{med_gap:.2f}".replace('.', ',')
               med_up_str = f"{med_up:.2f}".replace('.', ',')
               med_down_str = f"{med_down:.2f}".replace('.', ',')
               med_otc_str = f"{med_otc:.2f}".replace('.', ',')
               
               st.html(f"""
                   <div style="text-align: center; font-size: 15px; font-weight: normal; margin-top: 10px; margin-bottom: 2px;">
                       {red_count} vs {green_count}
                   </div>
                   <div style="text-align: center; font-size: 13.5px; margin-top: 0px; margin-bottom: 5px; font-weight: bold;">
                       🟥 RED: {red_pct:.2f}% &nbsp;|&nbsp; GREEN: {green_pct:.2f}% 🟩
                   </div>
                   <div style="text-align: center; font-size: 12.5px; margin-top: 6px; color: var(--text-news); font-family: system-ui,-apple-system; font-weight: normal;">
                       Mediana Gap: <b>{med_gap_str}%</b> &nbsp;|&nbsp; 
                       Mediana Max UP: <b>{med_up_str}%</b> &nbsp;|&nbsp; 
                       Mediana Max DOWN: <b>{med_down_str}%</b> &nbsp;|&nbsp; 
                       Mediana Open to Close: <b>{med_otc_str}%</b>
                   </div>
               """)
           else:
               # ABBIAMO AGGIORNATO CON ST.HTML
               st.html(f"""
                    <div style="text-align: center; font-size: 14.5px;">
                        <b>{nome_ticker.upper()}</b> non ha giornate rispondenti ai parametri settati
                    </div>
                """)
               
           # SOTTO-COLONNE SIMMETRICHE PER CENTRARE PERFETTAMENTE IL BLOCCO DELLE NEWS SOTTO LE STATISTICHE
           col2_4, col2_5, col2_6 = st.columns([0.10, 0.80, 0.10])
          
           with col2_5: 
                   st.write(""); st.write(""); st.write(""); st.write(""); st.write("")
                   st.html(f"""
                       <div style="text-align:center; font-size: 14px; color: var(--text-news); font-family: system-ui,-apple-system;">
                           <b>ultime news:</b> <br/> <br/>
                       </div>
                   """)
                                   
                   if isinstance(st.session_state['news'], pd.DataFrame):
                           # ACCUMULATORE PER EVITARE GLI SPAZI VERTICALI NELLE NEWS (STRINGHE PIATTE SENZA ANDARE A CAPO)
                           news_html = ""
                           # RIMOZIONE DEL FILTRO DATA: RECUPERA SEMPRE LE ULTIME 5 NEWS IN ORDINE CRONOLOGICO
                           latest_news = st.session_state['news'].head(5)
                           for a, b in latest_news.iterrows():
                               formatted_date = b['Date']
                               data_da_stampa = formatted_date.strftime("%Y-%m-%d | h %H:%M")    
                        
                               link = b['Link']
                               if not link.startswith('http'):
                                    link = "https://finviz.com/" + b['Link']
                                        
                               # USATO ST.MARKDOWN BLINDATO PER RISOLVERE ALL'ORIGINE I CONFLITTI DI APERTURA IN NUOVA SCHEDA E ADATTARSI AL TEMA
                               news_html += f'<div style="text-align:left; font-size:13px; margin-bottom:6px; line-height:1.3;"><strong style="color:red;">{data_da_stampa}</strong>&nbsp;<a href="{link}" style="text-decoration:none; color: var(--text-news);" target="_blank">{b["Title"]}</a></div>'
                           
                           # STAMPATO UNICAMENTE UNA VOLTA FUORI DAL LOOP ATTRAVERSO ST.MARKDOWN
                           st.markdown(news_html, unsafe_allow_html=True)

                   if isinstance(st.session_state['news'], str):
                           # USATO ST.MARKDOWN PROTETTO CON STRINGA PIATTA
                           news_str_html = f'<div style="text-align:center; font-size:14px; color: var(--text-news);">{st.session_state["news"]}</div>'
                           st.markdown(news_str_html, unsafe_allow_html=True)

with col3:
    # ---------------------------------------------------------------------------------
    # LA PARTE DESTRA (COL3) DIVENTATA IL COCKPIT GRAFICO DI ANALISI DILUIZIONE & RISK SEC
    # ---------------------------------------------------------------------------------
    if 'dati_storici' in st.session_state and st.session_state['dati_storici'] is not None:
        
        # SPACER VERTICALE ALLINEATO A 95PX PER ALLINEARE IL COCKPIT ALL'ALTEZZA DELLA TABELLA DI COLONNA 2
        st.markdown("<div style='height: 95px;'></div>", unsafe_allow_html=True)
        
        cached_profile = st.session_state.get('cached_profile', None)
        cik = ""
        if isinstance(cached_profile, dict):
            cik = cached_profile.get('cik', '')
            
        # CHIAMATA 100% DINAMICA IN REAL-TIME AD OGNI RICHIESTA (NESSUNA CACHE SU SEC EDGAR)
        sec_data = fetch_sec_data(cik)
            
        if isinstance(sec_data, dict):
            # 1. VALUTAZIONE E SCRITTURA DELLA SEZIONE CASSA / SOLVIBILITÀ (PIANO COMPLETAMENTE INDIPENDENTE)
            cash_msg = "Dati di cassa insufficienti o non disponibili"
            cash_color = "var(--text-news)" # Default Nero reattivo
            
            raw_runway = sec_data.get('runway_months', ' - ')
            liq_val_str = sec_data.get('liquidity_test', ' - ')
            ratio_val_str = sec_data.get('current_assets_ratio', ' - ')
            
            is_insolvent_ltr = False
            is_insolvent_assets = False
            try:
                l_val = float(liq_val_str)
                if l_val < 1.2:
                    is_insolvent_ltr = True
            except:
                pass
            try:
                rt_val = float(ratio_val_str.replace('%', ''))
                if rt_val < 20.0:
                    is_insolvent_assets = True
            except:
                pass

            # GERARCHIA DELLE VALUTAZIONI (IL CASO APPLE/BLUE CHIP È RISOLTO CON PRIORITÀ ASSOLUTA)
            if "Cash Flow" in raw_runway or "Positive" in raw_runway or "+" in raw_runway:
                cash_msg = "Trend finanziario solido - flusso di cassa operativo OCF positivo"
                cash_color = "#2e7d32" # Verde
            elif "Critico" in raw_runway or "Illiquido" in raw_runway:
                cash_msg = "Solvibilità critica - LTR < 1.2 - rischio diluizione"
                cash_color = "#c62828" # Rosso
            elif is_insolvent_ltr or is_insolvent_assets:
                # Gestione splittata delle due allerte di solvibilità
                if is_insolvent_ltr and is_insolvent_assets:
                    cash_msg = "Solvibilità critica - LTR < 1.2 - rischio diluizione<br>Solvibilità critica - Cash / Current Assets < 20% - rischio diluizione"
                elif is_insolvent_ltr:
                    cash_msg = "Solvibilità critica - LTR < 1.2 - rischio diluizione"
                else:
                    cash_msg = "Solvibilità critica - Cash / Current Assets < 20% - rischio diluizione"
                cash_color = "#c62828" # Rosso
            else:
                try:
                    r_val = float(raw_runway.split()[0])
                    if r_val < 3.0:
                        cash_msg = "Autonomia di cassa critica - inferiore a 3 mesi"
                        cash_color = "#c62828" # Rosso
                    elif r_val < 12.0:
                        cash_msg = "Autonomia di cassa limitata - inferiore a 12 mesi"
                        cash_color = "#f57f17" # Arancione
                    else:
                        cash_msg = "Autonomia di cassa stabile - superiore a 12 mesi"
                        cash_color = "#2e7d32" # Verde
                except:
                    cash_msg = "Dati di cassa insufficienti o non disponibili"
                    cash_color = "var(--text-news)"

            # 2. VALUTAZIONE E SCRITTURA DELLA SEZIONE OFFERING / DILUIZIONE
            offering_msg = "Nessun deposito SEC recente per potenziale emissione di azioni (S-1, S-3, 424B) negli ultimi 180 giorni."
            offering_date_str = sec_data.get('active_offering_date', ' - ')
            form_type = sec_data.get('active_offering_form', ' - ')
            
            if offering_date_str and str(offering_date_str).strip() not in ['', '-', ' - ']:
                try:
                    off_date_dt = pd.to_datetime(offering_date_str).date()
                    if 'gaps' in globals() and isinstance(gaps, pd.DataFrame) and not gaps.empty:
                        gaps_df = gaps.copy()
                        gaps_df['Date_dt'] = pd.to_datetime(gaps_df['Date']).dt.date
                        
                        # Criterio: Gap >= 30% cronologicamente successivi all'offering
                        gaps_after_30 = gaps_df[(gaps_df['Gap %'] >= 30.0) & (gaps_df['Date_dt'] > off_date_dt)]
                        
                        if gaps_after_30.empty:
                            # Scenario 1 (3 righe simmetriche, con accapo e punti)
                            offering_msg = f"Form {form_type} depositato il {offering_date_str}<br>Successivamente al deposito - Nessuna giornata in gap ≥ 30% con Volume.<br>Pressione di vendita possibile."
                        else:
                            red_gaps = gaps_after_30[gaps_after_30['Chiusura'] == 'RED']
                            green_gaps = gaps_after_30[gaps_after_30['Chiusura'] == 'GREEN']
                            
                            n_red = len(red_gaps)
                            n_green = len(green_gaps)
                            
                            if n_red > 0:
                                # Scenario 3 (3 righe simmetriche, con accapo e punti)
                                offering_msg = f"Form {form_type} depositato il {offering_date_str}<br>Successivamente al deposito - Registrate {n_red} giornate in gap ≥ 30% con Volume e chiusura RED.<br>Offering parzialmente o interamente scaricata."
                            else:
                                # Scenario 2 (3 righe simmetriche, con accapo e punti)
                                offering_msg = f"Form {form_type} depositato il {offering_date_str}<br>Successivamente al deposito - Registrate {n_green} giornate in gap ≥ 30% con Volume e chiusura GREEN.<br>Offering potenzialmente ancora pendente."
                    else:
                        offering_msg = f"Form {form_type} depositato il {offering_date_str}<br>Successivamente al deposito - Nessuna giornata in gap ≥ 30% con Volume.<br>Pressione di vendita possibile."
                except Exception as e:
                    offering_msg = f"Form {form_type} depositato il {offering_date_str}."

            # Determinazione dei colori delle card in base alle soglie di solvibilità
            runway_val_str = sec_data.get('runway_months', ' - ')
            runway_color = "#333"
            if "Cash Flow" in runway_val_str or "Positive" in runway_val_str or "+" in runway_val_str:
                runway_color = "#2e7d32"
                runway_val_str = "Cash Flow +"
            elif "Critico" in runway_val_str or "Illiquido" in runway_val_str:
                runway_color = "#c62828"
            else:
                try:
                    r_val = float(runway_val_str.split()[0])
                    if r_val < 3.0:
                        runway_color = "#c62828"
                    elif r_val < 12.0:
                        runway_color = "#f57f17"
                    else:
                        runway_color = "#2e7d32"
                except:
                    pass
                
            liq_val_str = sec_data.get('liquidity_test', ' - ')
            liq_color = "#333"
            try:
                l_val = float(liq_val_str)
                if l_val < 1.2:
                    liq_color = "#c62828"
                elif l_val < 1.5:
                    liq_color = "#f57f17"
                else:
                    liq_color = "#2e7d32"
            except:
                pass
                
            ratio_val_str = sec_data.get('current_assets_ratio', ' - ')
            ratio_color = "#333"
            try:
                rt_val = float(ratio_val_str.replace('%', ''))
                if rt_val < 20.0:
                    ratio_color = "#c62828"
                else:
                    ratio_color = "#2e7d32"
            except:
                pass

            # Estrazione variabili locali per evitare conflitti di apici
            cash_on_hand_val = sec_data.get('cash_on_hand', ' - ')
            monthly_burn_val_str = sec_data.get('monthly_burn', ' - ')
            curr_assets_ratio_val = sec_data.get('current_assets_ratio', ' - ')
            liquidity_test_val = sec_data.get('liquidity_test', ' - ')

            # DEFINIZIONE DELLE FRASI DI HELP (TOOLTIP) REVISIONATE (MINUSCOLO, NO PUNTI FINALI, VIRGOLA AGGIUNTA)
            coh_tooltip = 'Cash on Hand <span class="gf-tooltip" style="display:inline-block; width:11px; height:11px; line-height:10px; border:1px solid #000000; border-radius:50%; text-align:center; font-size:7.5px; font-weight:bold; color:#000000; font-family:system-ui; vertical-align:middle; margin-left:4px; cursor:help;">?<span class="gf-tooltiptext">ultima cassa liquida disponibile dichiarata nel report SEC</span></span>'
            mb_tooltip = 'Monthly Burn <span class="gf-tooltip" style="display:inline-block; width:11px; height:11px; line-height:10px; border:1px solid #000000; border-radius:50%; text-align:center; font-size:7.5px; font-weight:bold; color:#000000; font-family:system-ui; vertical-align:middle; margin-left:4px; cursor:help;">?<span class="gf-tooltiptext">velocità media mensile di utilizzo delle riserve liquide</span></span>'
            rc_tooltip = 'Runway Cassa <span class="gf-tooltip" style="display:inline-block; width:11px; height:11px; line-height:10px; border:1px solid #000000; border-radius:50%; text-align:center; font-size:7.5px; font-weight:bold; color:#000000; font-family:system-ui; vertical-align:middle; margin-left:4px; cursor:help;">?<span class="gf-tooltiptext">autonomia di cassa in mesi, prima del completo esaurimento delle riserve</span></span>'
            car_tooltip = 'Cash / Current Assets % <span class="gf-tooltip" style="display:inline-block; width:11px; height:11px; line-height:10px; border:1px solid #000000; border-radius:50%; text-align:center; font-size:7.5px; font-weight:bold; color:#000000; font-family:system-ui; vertical-align:middle; margin-left:4px; cursor:help;">?<span class="gf-tooltiptext">indica la percentuale delle attività correnti, sostenuta da cassa liquida reale</span></span>'
            ltr_tooltip = 'Liquidity Test Ratio <span class="gf-tooltip" style="display:inline-block; width:11px; height:11px; line-height:10px; border:1px solid #000000; border-radius:50%; text-align:center; font-size:7.5px; font-weight:bold; color:#000000; font-family:system-ui; vertical-align:middle; margin-left:4px; cursor:help;">?<span class="gf-tooltiptext">rapporto tra cassa liquida e passività correnti (debiti entro l\'anno), un valore inferiore a 1.2 indica un alto rischio di insolvenza immediata e diluizione forzata</span></span>'

            # 1. AUTONOMIA DI CASSA (CASH RUNWAY) IN CIMA AL COCKPIT
            st.markdown("<div style='font-size: 14.5px; font-weight: bold; margin-bottom: 10px;'>📊 AUTONOMIA DI CASSA (CASH RUNWAY)</div>", unsafe_allow_html=True)
            
            # Griglia di metriche superiori (Cassa, Burn, Runway)
            metrics_top_html = f"""
            <div style="display: flex; gap: 10px; margin-bottom: 15px; font-family: system-ui,-apple-system; box-sizing: border-box;">
                <div style="flex: 1; background: var(--card-bg); border: 1px solid var(--card-border); padding: 10px; border-radius: 4px; text-align: center;">
                    <div style="font-size: 11px; color: var(--date-color); font-weight: bold; margin-bottom: 4px; text-transform: uppercase;">{coh_tooltip}</div>
                    <div style="font-size: 18px; font-weight: bold; color: var(--text-news);">{cash_on_hand_val}</div>
                </div>
                <div style="flex: 1; background: var(--card-bg); border: 1px solid var(--card-border); padding: 10px; border-radius: 4px; text-align: center;">
                    <div style="font-size: 11px; color: var(--date-color); font-weight: bold; margin-bottom: 4px; text-transform: uppercase;">{mb_tooltip}</div>
                    <div style="font-size: 18px; font-weight: bold; color: var(--text-news);">{monthly_burn_val_str}</div>
                </div>
                <div style="flex: 1; background: var(--card-bg); border: 1px solid var(--card-border); padding: 10px; border-radius: 4px; text-align: center;">
                    <div style="font-size: 11px; color: var(--date-color); font-weight: bold; margin-bottom: 4px; text-transform: uppercase;">{rc_tooltip}</div>
                    <div style="font-size: 18px; font-weight: bold; color: {runway_color};">{runway_val_str}</div>
                </div>
            </div>
            """
            st.markdown(metrics_top_html, unsafe_allow_html=True)
            
            # Griglia di metriche inferiori di solvibilità (Ratio e Liquidity Test)
            metrics_bottom_html = f"""
            <div style="display: flex; gap: 10px; margin-bottom: 12px; font-family: system-ui,-apple-system; box-sizing: border-box;">
                <div style="flex: 1; background: var(--card-bg); border: 1px solid var(--card-border); padding: 10px; border-radius: 4px; text-align: center;">
                    <div style="font-size: 11px; color: var(--date-color); font-weight: bold; margin-bottom: 4px; text-transform: uppercase;">{car_tooltip}</div>
                    <div style="font-size: 18px; font-weight: bold; color: {ratio_color};">{curr_assets_ratio_val}</div>
                </div>
                <div style="flex: 1; background: var(--card-bg); border: 1px solid var(--card-border); padding: 10px; border-radius: 4px; text-align: center;">
                    <div style="font-size: 11px; color: var(--date-color); font-weight: bold; margin-bottom: 4px; text-transform: uppercase;">{ltr_tooltip}</div>
                    <div style="font-size: 18px; font-weight: bold; color: {liq_color};">{liquidity_test_val}</div>
                </div>
            </div>
            """
            st.markdown(metrics_bottom_html, unsafe_allow_html=True)

            # COMMENTO INERENTE LA CASSA: Posizionato immediatamente sotto le metriche con colore indipendente ed esatto
            st.markdown(f"<div style='font-size: 13.5px; font-weight: bold; color: {cash_color}; margin-top: 0px; margin-bottom: 25px; font-family: system-ui,-apple-system; text-align: center;'>{cash_msg}</div>", unsafe_allow_html=True)

            # 2. BOX OFFERINGS: Titolo pulito "OFFERINGS" senza alcun simbolo di pericolo (⚠️ eliminata)
            risk_badge_html = f"""
            <div style="background-color: var(--badge-bg); border: 1px solid var(--badge-border); border-left: 5px solid #757575; padding: 12px; margin-top: 15px; margin-bottom: 20px; border-radius: 4px; font-family: system-ui,-apple-system;">
                <div style="font-size: 13.5px; font-weight: bold; color: var(--text-news); margin-bottom: 6px;">OFFERINGS</div>
                <div style="color: var(--text-news); font-size: 13px; line-height: 1.4;">{offering_msg}</div>
            </div>
            """
            st.markdown(risk_badge_html, unsafe_allow_html=True)
            
            # 3. Tabella degli ultimi link ai depositi SEC (I link sono applicati direttamente sul nome del modulo con colore var(--sec-link-color))
            st.markdown("<div style='font-size: 14.5px; font-weight: bold; margin-top: 25px; margin-bottom: 8px;'>📂 ULTIMI DEPOSITI SEC RILEVANTI</div>", unsafe_allow_html=True)
            sec_links = sec_data.get('sec_links', [])
            if sec_links:
                sec_html = ""
                for item in sec_links:
                    date_val = item["date"]
                    form_val = item["form"]
                    link_val = item["link"]
                    sec_html += f"""
                    <div style="font-size: 13px; margin-bottom: 6px; padding-bottom: 6px; border-bottom: 1px solid var(--card-border); font-family: system-ui,-apple-system;">
                        <span style="color: var(--date-color);">[{date_val}]</span>&nbsp;&nbsp;
                        <a href="{link_val}" style="text-decoration: none; color: var(--sec-link-color); font-weight: bold;" target="_blank">Form {form_val}</a>
                    </div>
                    """
                st.markdown(sec_html, unsafe_allow_html=True)
            else:
                st.write("Nessun deposito SEC recente catalogato per questo ticker.")
        else:
            # Se il CIK non esiste o Polygon non ha profilato il titolo (es. ETF o Warrants)
            error_sec_html = f'<div style="background-color: #f9f9f9; border-left: 5px solid #ccc; padding: 12px; margin-top: 15px; border-radius: 4px; font-size: 13.5px; color: var(--text-news);"><b>Dati SEC Non Disponibili</b><br>Il titolo cercato non possiede un codice CIK o i dati di bilancio standard SEC non sono registrati (comune per Warrant, ETF, SPAC o OTC molto illiquidi).</div>'
            st.markdown(error_sec_html, unsafe_allow_html=True)

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
