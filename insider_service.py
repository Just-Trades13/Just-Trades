#!/usr/bin/env python3
"""
Insider Signals Service - SEC EDGAR Data Ingestion & Signal Scoring
=====================================================================
Standalone service that polls SEC EDGAR for insider trading filings,
scores them for unusual/high-conviction activity, and stores in SQLite.

Port: 8084
Polling: Every 5 minutes

Part of the Just.Trades. platform.
Created: Dec 8, 2025
"""

import os
import sys
import json
import time
import sqlite3
import logging
import requests
import threading
from datetime import datetime, timedelta
from flask import Flask, jsonify, request
from flask_cors import CORS

# =============================================================================
# CONFIGURATION
# =============================================================================

SERVICE_PORT = 8084
DB_PATH = 'just_trades.db'
POLL_INTERVAL_SECONDS = 300  # 5 minutes

# SEC EDGAR API Configuration
# Using the official SEC EDGAR JSON API
SEC_EDGAR_BASE_URL = "https://efts.sec.gov/LATEST/search-index"
SEC_EDGAR_FILINGS_URL = "https://www.sec.gov/cgi-bin/browse-edgar"
SEC_FORM4_RSS_URL = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=4&company=&dateb=&owner=only&count=100&output=atom"

# User-Agent required by SEC (they block requests without proper identification)
SEC_USER_AGENT = "JustTrades/1.0 (Contact: support@just.trades)"

# Signal scoring weights
SCORING_WEIGHTS = {
    'dollar_value': 0.35,
    'ownership_change': 0.20,
    'insider_role': 0.15,
    'cluster': 0.15,
    'recency': 0.15
}

# Insider role weights for scoring
ROLE_WEIGHTS = {
    'chief executive officer': 1.0,
    'ceo': 1.0,
    'chief financial officer': 0.9,
    'cfo': 0.9,
    'chief operating officer': 0.9,
    'coo': 0.9,
    'president': 0.95,
    'chairman': 0.85,
    'director': 0.7,
    '10% owner': 1.1,
    '10 percent owner': 1.1,
    'beneficial owner': 1.1,
    'strategic investor': 1.2,
    'officer': 0.75,
    'vp': 0.7,
    'vice president': 0.7,
    'general counsel': 0.7,
    'secretary': 0.6,
    'treasurer': 0.7,
}

# Thresholds
HIGHLIGHT_THRESHOLD = 70  # Score >= 70 = highlighted
CONVICTION_THRESHOLD = 85  # Score >= 85 = high conviction

# Processing lock to prevent concurrent database writes
_processing_lock = threading.Lock()

# =============================================================================
# LOGGING SETUP
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [INSIDER] %(levelname)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/tmp/insider_service.log')
    ]
)
logger = logging.getLogger(__name__)

# =============================================================================
# FLASK APP SETUP
# =============================================================================

app = Flask(__name__)
CORS(app)

# =============================================================================
# DATABASE SETUP
# =============================================================================

def init_database():
    """Create insider-related tables if they don't exist"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Raw SEC filings table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS insider_filings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            accession_number TEXT UNIQUE,
            form_type TEXT,
            ticker TEXT,
            company_name TEXT,
            insider_name TEXT,
            insider_title TEXT,
            transaction_type TEXT,
            shares INTEGER,
            price REAL,
            total_value REAL,
            ownership_change_percent REAL,
            shares_owned_after REAL,
            filing_date TEXT,
            transaction_date TEXT,
            filing_url TEXT,
            raw_data TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Scored signals table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS insider_signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filing_id INTEGER,
            ticker TEXT,
            signal_score INTEGER,
            insider_name TEXT,
            insider_role TEXT,
            transaction_type TEXT,
            dollar_value REAL,
            reason_flags TEXT,
            is_highlighted INTEGER DEFAULT 0,
            is_conviction INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (filing_id) REFERENCES insider_filings(id)
        )
    ''')
    
    # Poll status tracking
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS insider_poll_status (
            id INTEGER PRIMARY KEY,
            last_poll_time TEXT,
            last_filing_date TEXT,
            filings_processed INTEGER DEFAULT 0,
            errors_count INTEGER DEFAULT 0,
            last_error TEXT
        )
    ''')
    
    # Initialize poll status if not exists
    cursor.execute('SELECT COUNT(*) FROM insider_poll_status')
    if cursor.fetchone()[0] == 0:
        cursor.execute('''
            INSERT INTO insider_poll_status (id, last_poll_time, filings_processed)
            VALUES (1, ?, 0)
        ''', (datetime.now().isoformat(),))
    
    # Watchlist table - track tickers and insiders to follow
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS insider_watchlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            watch_type TEXT NOT NULL,
            watch_value TEXT NOT NULL,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(watch_type, watch_value)
        )
    ''')
    
    # Create indexes for faster queries
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_filings_ticker ON insider_filings(ticker)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_filings_date ON insider_filings(filing_date)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_filings_type ON insider_filings(transaction_type)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_signals_score ON insider_signals(signal_score)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_signals_ticker ON insider_signals(ticker)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_signals_date ON insider_signals(created_at)')
    
    conn.commit()
    conn.close()
    logger.info("✅ Database tables initialized")


# =============================================================================
# SEC EDGAR API FUNCTIONS
# =============================================================================

def fetch_recent_form4_filings(count=100):
    """
    Fetch recent Form 4 filings from SEC EDGAR
    Returns list of filing dictionaries
    
    Args:
        count: Number of filings to fetch (default 100, max 400)
    """
    filings = []
    
    try:
        # SEC EDGAR API - get recent Form 4 filings
        api_url = "https://www.sec.gov/cgi-bin/browse-edgar"
        params = {
            'action': 'getcurrent',
            'type': '4',
            'owner': 'only',
            'count': str(min(count, 400)),  # SEC caps at 400
            'output': 'atom'
        }
        
        headers = {
            'User-Agent': SEC_USER_AGENT,
            'Accept': 'application/atom+xml'
        }
        
        logger.info(f"📡 Fetching up to {count} Form 4 filings from SEC EDGAR...")
        response = requests.get(api_url, params=params, headers=headers, timeout=30)
        
        if response.status_code == 200:
            # Parse the Atom feed
            filings = parse_edgar_atom_feed(response.text)
            logger.info(f"📊 Fetched {len(filings)} Form 4 filings from SEC")
        else:
            logger.warning(f"⚠️ SEC EDGAR returned status {response.status_code}")
            
    except requests.exceptions.Timeout:
        logger.error("❌ SEC EDGAR request timed out")
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ SEC EDGAR request failed: {e}")
    except Exception as e:
        logger.error(f"❌ Error fetching filings: {e}")
    
    return filings


def fetch_form4_filings_fulltext(days_back=7, max_results=200):
    """
    Fetch Form 4 filings using SEC's full-text search API
    This can search historical filings, not just recent ones
    
    Args:
        days_back: How many days back to search
        max_results: Maximum results to return
    """
    filings = []
    
    try:
        # SEC EDGAR Full-Text Search API
        search_url = "https://efts.sec.gov/LATEST/search-index"
        
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        params = {
            'q': 'formType:"4"',
            'dateRange': 'custom',
            'startdt': start_date.strftime('%Y-%m-%d'),
            'enddt': end_date.strftime('%Y-%m-%d'),
            'forms': '4',
            'from': '0',
            'size': str(min(max_results, 200))
        }
        
        headers = {
            'User-Agent': SEC_USER_AGENT,
            'Accept': 'application/json'
        }
        
        logger.info(f"📡 Searching Form 4 filings from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}...")
        response = requests.get(search_url, params=params, headers=headers, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            hits = data.get('hits', {}).get('hits', [])
            
            for hit in hits:
                source = hit.get('_source', {})
                filing = {
                    'form_type': '4',
                    'accession_number': source.get('adsh', '').replace('-', ''),
                    'filing_url': f"https://www.sec.gov/Archives/edgar/data/{source.get('cik', '')}/{source.get('adsh', '').replace('-', '')}/",
                    'filing_date': source.get('file_date'),
                    'company_name': source.get('display_names', [None])[0] if source.get('display_names') else None,
                    'insider_name': source.get('display_names', [None, None])[1] if len(source.get('display_names', [])) > 1 else None
                }
                filings.append(filing)
            
            logger.info(f"📊 Found {len(filings)} Form 4 filings via full-text search")
        else:
            logger.warning(f"⚠️ SEC full-text search returned status {response.status_code}")
            
    except Exception as e:
        logger.error(f"❌ Error in full-text search: {e}")
    
    return filings


def fetch_13d_13g_filings(count=50):
    """
    Fetch 13D and 13G filings from SEC EDGAR
    These are activist investor and large shareholder filings (5%+ ownership)
    
    13D = Activist investor (intends to influence management)
    13G = Passive investor (no intent to control)
    
    Returns list of filing dictionaries
    """
    all_filings = []
    
    for form_type in ['SC 13D', 'SC 13G']:
        try:
            api_url = "https://www.sec.gov/cgi-bin/browse-edgar"
            params = {
                'action': 'getcurrent',
                'type': form_type,
                'owner': 'include',
                'count': str(count),
                'output': 'atom'
            }
            
            headers = {
                'User-Agent': SEC_USER_AGENT,
                'Accept': 'application/atom+xml'
            }
            
            logger.info(f"📡 Fetching {form_type} filings from SEC EDGAR...")
            response = requests.get(api_url, params=params, headers=headers, timeout=30)
            
            if response.status_code == 200:
                filings = parse_13d_13g_atom_feed(response.text, form_type)
                all_filings.extend(filings)
                logger.info(f"📊 Fetched {len(filings)} {form_type} filings")
            else:
                logger.warning(f"⚠️ SEC EDGAR returned status {response.status_code} for {form_type}")
                
        except Exception as e:
            logger.error(f"❌ Error fetching {form_type} filings: {e}")
    
    return all_filings


def parse_13d_13g_atom_feed(xml_content, form_type):
    """
    Parse SEC EDGAR Atom feed for 13D/13G filings
    """
    import xml.etree.ElementTree as ET
    import re
    
    filings = []
    seen_accessions = set()
    
    try:
        root = ET.fromstring(xml_content)
        ns = {'atom': 'http://www.w3.org/2005/Atom'}
        
        for entry in root.findall('.//atom:entry', ns):
            try:
                title = entry.find('atom:title', ns)
                link = entry.find('atom:link', ns)
                updated = entry.find('atom:updated', ns)
                entry_id = entry.find('atom:id', ns)
                summary = entry.find('atom:summary', ns)
                
                if title is not None and title.text:
                    title_text = title.text
                    
                    # Extract accession number
                    accession_number = None
                    if entry_id is not None and entry_id.text:
                        acc_match = re.search(r'accession-number=(\d{10}-\d{2}-\d{6})', entry_id.text)
                        if acc_match:
                            accession_number = acc_match.group(1)
                    
                    if accession_number and accession_number in seen_accessions:
                        continue
                    if accession_number:
                        seen_accessions.add(accession_number)
                    
                    filing_url = link.get('href') if link is not None else None
                    
                    # Parse company/filer name from title
                    # Format: "SC 13D - Company Name (CIK)"
                    company_name = None
                    if ' - ' in title_text:
                        parts = title_text.split(' - ', 1)
                        if len(parts) > 1:
                            name_part = parts[1]
                            if '(' in name_part:
                                company_name = name_part.split('(')[0].strip()
                            else:
                                company_name = name_part.strip()
                    
                    filing = {
                        'form_type': '13D' if '13D' in form_type else '13G',
                        'title': title_text,
                        'filing_url': filing_url,
                        'filing_date': updated.text if updated is not None else None,
                        'company_name': company_name,
                        'accession_number': accession_number,
                        'is_activist': '13D' in form_type  # 13D = activist, 13G = passive
                    }
                    
                    filings.append(filing)
                    
            except Exception as e:
                logger.debug(f"Error parsing 13D/13G entry: {e}")
                continue
                
    except ET.ParseError as e:
        logger.error(f"❌ XML parse error for 13D/13G: {e}")
    except Exception as e:
        logger.error(f"❌ Error parsing 13D/13G Atom feed: {e}")
    
    return filings


def parse_edgar_atom_feed(xml_content):
    """
    Parse SEC EDGAR Atom feed for Form 4 filings
    Returns list of filing dictionaries with basic info
    """
    import xml.etree.ElementTree as ET
    import re
    
    filings = []
    seen_accessions = set()  # Track unique filings
    
    try:
        # Parse XML
        root = ET.fromstring(xml_content)
        
        # Atom namespace
        ns = {'atom': 'http://www.w3.org/2005/Atom'}
        
        for entry in root.findall('.//atom:entry', ns):
            try:
                title = entry.find('atom:title', ns)
                link = entry.find('atom:link', ns)
                updated = entry.find('atom:updated', ns)
                summary = entry.find('atom:summary', ns)
                entry_id = entry.find('atom:id', ns)
                
                if title is not None and title.text:
                    title_text = title.text
                    
                    # Skip "Issuer" entries - only process "Reporting" (the insider)
                    if '(Issuer)' in title_text:
                        continue
                    
                    # Extract accession number from id element
                    # Format: urn:tag:sec.gov,2008:accession-number=0001831746-25-000017
                    accession_number = None
                    if entry_id is not None and entry_id.text:
                        acc_match = re.search(r'accession-number=(\d{10}-\d{2}-\d{6})', entry_id.text)
                        if acc_match:
                            accession_number = acc_match.group(1)
                    
                    # Skip if we've already seen this accession number
                    if accession_number and accession_number in seen_accessions:
                        continue
                    if accession_number:
                        seen_accessions.add(accession_number)
                    
                    # Get the filing URL
                    filing_url = link.get('href') if link is not None else None
                    
                    # Extract company info from title
                    # Format: "4 - Person Name (CIK) (Reporting)"
                    filing = {
                        'form_type': '4',
                        'title': title_text,
                        'filing_url': filing_url,
                        'filing_date': updated.text if updated is not None else None,
                        'summary': summary.text if summary is not None else None,
                        'accession_number': accession_number
                    }
                    
                    # Parse insider name from title
                    if ' - ' in title_text:
                        parts = title_text.split(' - ', 1)
                        if len(parts) > 1:
                            name_part = parts[1]
                            # Extract name (before CIK)
                            if '(' in name_part:
                                insider_name = name_part.split('(')[0].strip()
                                filing['insider_name'] = insider_name
                    
                    filings.append(filing)
                    
            except Exception as e:
                logger.debug(f"Error parsing entry: {e}")
                continue
        
        logger.info(f"📋 Parsed {len(filings)} unique Form 4 filings (filtered duplicates)")
                
    except ET.ParseError as e:
        logger.error(f"❌ XML parse error: {e}")
    except Exception as e:
        logger.error(f"❌ Error parsing Atom feed: {e}")
    
    return filings


def fetch_form4_details(filing_url):
    """
    Fetch detailed Form 4 data from a specific filing URL
    Parses the XML to extract transaction details
    """
    import re
    
    details = {
        'insider_name': None,
        'insider_title': None,
        'ticker': None,
        'transaction_type': None,
        'shares': 0,
        'price': 0.0,
        'total_value': 0.0,
        'shares_owned_after': 0,
        'ownership_change_percent': 0.0
    }
    
    try:
        if not filing_url:
            return details
            
        headers = {
            'User-Agent': SEC_USER_AGENT,
            'Accept': 'text/html,application/xml'
        }
        
        # The filing_url points to an index page like:
        # https://www.sec.gov/Archives/edgar/data/1831746/000183174625000017/0001831746-25-000017-index.htm
        # We need to find the primary XML document
        
        logger.debug(f"Fetching filing index: {filing_url}")
        response = requests.get(filing_url, headers=headers, timeout=30)
        
        if response.status_code == 200:
            # Look for XML files - the primary Form 4 document
            # Pattern: Look for links to .xml files that are the primary document
            # Usually named like: xslForm4X01/primary_doc.xml or wf-form4_*.xml
            
            # Find all XML file links
            xml_links = re.findall(r'href="([^"]*\.xml)"', response.text, re.IGNORECASE)
            
            # Filter to find the primary document (exclude xsl stylesheets)
            primary_xml = None
            for link in xml_links:
                # Skip XSL stylesheet references
                if 'xsl' in link.lower() and 'form4' not in link.lower():
                    continue
                # Prefer files that look like form4 documents
                if 'form4' in link.lower() or 'primary' in link.lower():
                    primary_xml = link
                    break
                # Otherwise take the first non-xsl XML
                if primary_xml is None:
                    primary_xml = link
            
            if primary_xml:
                # Build absolute URL
                if primary_xml.startswith('http'):
                    xml_url = primary_xml
                elif primary_xml.startswith('/'):
                    xml_url = f"https://www.sec.gov{primary_xml}"
                else:
                    # Relative URL - get base from filing URL
                    base_url = '/'.join(filing_url.rstrip('/').split('/')[:-1])
                    xml_url = f"{base_url}/{primary_xml}"
                
                logger.debug(f"Fetching XML document: {xml_url}")
                xml_response = requests.get(xml_url, headers=headers, timeout=30)
                
                if xml_response.status_code == 200:
                    details = parse_form4_xml(xml_response.text)
                    if details.get('ticker'):
                        logger.debug(f"✅ Parsed Form 4: {details.get('ticker')} - {details.get('transaction_type')}")
                else:
                    logger.debug(f"Failed to fetch XML: {xml_response.status_code}")
            else:
                logger.debug(f"No XML document found in filing index")
        else:
            logger.debug(f"Failed to fetch filing index: {response.status_code}")
                    
    except Exception as e:
        logger.debug(f"Error fetching Form 4 details: {e}")
    
    return details


def parse_form4_xml(xml_content):
    """
    Parse Form 4 XML document to extract transaction details
    """
    import xml.etree.ElementTree as ET
    
    details = {
        'insider_name': None,
        'insider_title': None,
        'ticker': None,
        'transaction_type': None,
        'shares': 0,
        'price': 0.0,
        'total_value': 0.0,
        'shares_owned_after': 0,
        'ownership_change_percent': 0.0,
        'transaction_date': None
    }
    
    try:
        root = ET.fromstring(xml_content)
        
        # Extract issuer info (company)
        issuer = root.find('.//issuer')
        if issuer is not None:
            ticker_elem = issuer.find('issuerTradingSymbol')
            if ticker_elem is not None and ticker_elem.text:
                details['ticker'] = ticker_elem.text.strip().upper()
        
        # Extract reporting owner info (insider)
        owner = root.find('.//reportingOwner')
        if owner is not None:
            # Owner name
            owner_id = owner.find('reportingOwnerId')
            if owner_id is not None:
                name_elem = owner_id.find('rptOwnerName')
                if name_elem is not None and name_elem.text:
                    details['insider_name'] = name_elem.text.strip()
            
            # Owner relationship/title
            relationship = owner.find('reportingOwnerRelationship')
            if relationship is not None:
                # Check various title fields
                for title_field in ['officerTitle', 'otherText']:
                    title_elem = relationship.find(title_field)
                    if title_elem is not None and title_elem.text:
                        details['insider_title'] = title_elem.text.strip()
                        break
                
                # Check if director, officer, 10% owner
                if not details['insider_title']:
                    is_director = relationship.find('isDirector')
                    is_officer = relationship.find('isOfficer')
                    is_ten_pct = relationship.find('isTenPercentOwner')
                    
                    titles = []
                    if is_director is not None and is_director.text == '1':
                        titles.append('Director')
                    if is_officer is not None and is_officer.text == '1':
                        titles.append('Officer')
                    if is_ten_pct is not None and is_ten_pct.text == '1':
                        titles.append('10% Owner')
                    
                    if titles:
                        details['insider_title'] = ', '.join(titles)
        
        # Extract transaction details
        # Look for non-derivative transactions (common stock purchases/sales)
        total_shares = 0
        total_value = 0.0
        transaction_type = None
        transaction_date = None
        shares_after = 0
        
        for trans in root.findall('.//nonDerivativeTransaction'):
            try:
                # Transaction date
                date_elem = trans.find('.//transactionDate/value')
                if date_elem is not None and date_elem.text:
                    transaction_date = date_elem.text
                
                # Transaction code (P=Purchase, S=Sale, etc.)
                code_elem = trans.find('.//transactionCoding/transactionCode')
                if code_elem is not None and code_elem.text:
                    code = code_elem.text.upper()
                    if code == 'P':
                        transaction_type = 'BUY'
                    elif code == 'S':
                        transaction_type = 'SELL'
                    elif code == 'A':
                        transaction_type = 'AWARD'
                    elif code == 'G':
                        transaction_type = 'GIFT'
                    elif code == 'M':
                        transaction_type = 'EXERCISE'
                    else:
                        transaction_type = code
                
                # Shares
                shares_elem = trans.find('.//transactionAmounts/transactionShares/value')
                if shares_elem is not None and shares_elem.text:
                    try:
                        shares = float(shares_elem.text)
                        total_shares += shares
                    except ValueError:
                        pass
                
                # Price per share
                price_elem = trans.find('.//transactionAmounts/transactionPricePerShare/value')
                if price_elem is not None and price_elem.text:
                    try:
                        price = float(price_elem.text)
                        details['price'] = price
                        if shares:
                            total_value += shares * price
                    except ValueError:
                        pass
                
                # Shares owned after transaction
                after_elem = trans.find('.//postTransactionAmounts/sharesOwnedFollowingTransaction/value')
                if after_elem is not None and after_elem.text:
                    try:
                        shares_after = float(after_elem.text)
                    except ValueError:
                        pass
                        
            except Exception as e:
                logger.debug(f"Error parsing transaction: {e}")
                continue
        
        details['shares'] = int(total_shares)
        details['total_value'] = round(total_value, 2)
        details['transaction_type'] = transaction_type
        details['transaction_date'] = transaction_date
        details['shares_owned_after'] = shares_after
        
        # Calculate ownership change percent
        if shares_after > 0 and total_shares > 0:
            shares_before = shares_after - total_shares if transaction_type == 'BUY' else shares_after + total_shares
            if shares_before > 0:
                details['ownership_change_percent'] = round((total_shares / shares_before) * 100, 2)
            else:
                details['ownership_change_percent'] = 100.0  # New position
                
    except ET.ParseError as e:
        logger.debug(f"XML parse error: {e}")
    except Exception as e:
        logger.debug(f"Error parsing Form 4 XML: {e}")
    
    return details


# =============================================================================
# SIGNAL SCORING ENGINE
# =============================================================================

def calculate_signal_score(filing_data):
    """
    Calculate a signal score (0-100) for an insider filing
    Returns score and list of reason flags
    """
    score = 0
    reason_flags = []
    
    transaction_type = filing_data.get('transaction_type', '')
    
    # Only score BUY transactions (most significant for signals)
    if transaction_type != 'BUY':
        return 0, ['not_buy']
    
    # 1. Dollar Value Weight (35%)
    # Adjusted thresholds to be more generous for small-cap stocks
    total_value = filing_data.get('total_value', 0) or 0
    if total_value >= 1000000:  # $1M+
        dollar_score = 100
        reason_flags.append('million_dollar_buy')
    elif total_value >= 500000:  # $500K+
        dollar_score = 95
        reason_flags.append('large_buy_500k')
    elif total_value >= 250000:  # $250K+
        dollar_score = 85
        reason_flags.append('large_buy_250k')
    elif total_value >= 100000:  # $100K+
        dollar_score = 75
        reason_flags.append('significant_buy_100k')
    elif total_value >= 50000:  # $50K+
        dollar_score = 65
        reason_flags.append('notable_buy_50k')
    elif total_value >= 25000:  # $25K+
        dollar_score = 55
        reason_flags.append('buy_25k')
    elif total_value >= 10000:  # $10K+
        dollar_score = 45
    elif total_value >= 5000:  # $5K+
        dollar_score = 35
    else:
        dollar_score = 20
    
    score += dollar_score * SCORING_WEIGHTS['dollar_value']
    
    # 2. Ownership Change Weight (20%)
    # Also check if this is a NEW position (very bullish signal)
    ownership_change = filing_data.get('ownership_change_percent', 0) or 0
    shares_owned_after = filing_data.get('shares_owned_after', 0) or 0
    shares = filing_data.get('shares', 0) or 0
    
    # New position detection (bought shares = total shares owned)
    is_new_position = shares_owned_after > 0 and shares > 0 and abs(shares_owned_after - shares) < 10
    
    if is_new_position:
        ownership_score = 100
        reason_flags.append('new_position')
    elif ownership_change >= 100:  # Doubled position or more
        ownership_score = 100
        reason_flags.append('doubled_position')
    elif ownership_change >= 50:  # 50%+ increase
        ownership_score = 90
        reason_flags.append('major_position_increase')
    elif ownership_change >= 25:
        ownership_score = 75
        reason_flags.append('significant_increase')
    elif ownership_change >= 10:
        ownership_score = 60
        reason_flags.append('position_increase_10pct')
    elif ownership_change >= 5:
        ownership_score = 45
    else:
        ownership_score = 30
    
    score += ownership_score * SCORING_WEIGHTS['ownership_change']
    
    # 3. Insider Role Weight (15%)
    insider_title = (filing_data.get('insider_title') or '').lower()
    role_weight = 0.5  # Default
    
    for role_key, weight in ROLE_WEIGHTS.items():
        if role_key in insider_title:
            role_weight = weight
            if weight >= 0.9:
                reason_flags.append(f'c_suite_purchase')
            elif weight >= 1.1:
                reason_flags.append('strategic_investor')
            break
    
    role_score = role_weight * 100
    score += role_score * SCORING_WEIGHTS['insider_role']
    
    # 4. Cluster Detection (15%) - Check if multiple insiders bought recently
    # This would require checking the database for recent filings
    # For now, we'll use a placeholder
    cluster_score = 0  # Will be calculated in batch processing
    score += cluster_score * SCORING_WEIGHTS['cluster']
    
    # 5. Recency Weight (15%) - Give base score, bonus for any buy
    # All insider buys are somewhat notable
    recency_score = 60  # Base score for any insider buy
    score += recency_score * SCORING_WEIGHTS['recency']
    
    # Bonus: If this is a direct open market purchase (not option exercise)
    if filing_data.get('price', 0) > 0:
        score += 5  # Small bonus for actual cash purchase
        reason_flags.append('open_market_purchase')
    
    # Round to integer
    final_score = min(100, max(0, round(score)))
    
    return final_score, reason_flags


def detect_clusters(ticker, conn):
    """
    Detect if multiple insiders are buying the same ticker recently
    Returns bonus score and flag if cluster detected
    """
    cursor = conn.cursor()
    
    # Check for multiple insiders buying same ticker in last 7 days
    seven_days_ago = (datetime.now() - timedelta(days=7)).isoformat()
    
    cursor.execute('''
        SELECT COUNT(DISTINCT insider_name) as insider_count
        FROM insider_filings
        WHERE ticker = ?
        AND transaction_type = 'BUY'
        AND created_at >= ?
    ''', (ticker, seven_days_ago))
    
    result = cursor.fetchone()
    insider_count = result[0] if result else 0
    
    if insider_count >= 3:
        return 100, 'cluster_3plus_insiders'
    elif insider_count >= 2:
        return 70, 'cluster_2_insiders'
    
    return 0, None


# =============================================================================
# DATA PROCESSING
# =============================================================================

def process_filings():
    """
    Main processing function - fetch, parse, score, and store filings
    """
    # Use lock to prevent concurrent processing
    if not _processing_lock.acquire(blocking=False):
        logger.info("⏳ Processing already in progress, skipping...")
        return
    
    try:
        _process_filings_impl()
    finally:
        _processing_lock.release()

def _process_filings_impl():
    """Internal implementation of filing processing"""
    logger.info("🔄 Starting filing processing cycle...")
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    processed_count = 0
    errors_count = 0
    
    try:
        # Fetch recent filings - get up to 200 to capture more activity
        filings = fetch_recent_form4_filings(count=200)
        logger.info(f"📋 Processing {len(filings)} filings...")
        
        for i, filing in enumerate(filings):
            try:
                # Check if we already have this filing
                filing_url = filing.get('filing_url')
                if not filing_url:
                    logger.debug(f"Filing {i}: No URL, skipping")
                    continue
                
                # Use accession number from parsed data, or extract from URL
                accession_number = filing.get('accession_number')
                if not accession_number:
                    import re
                    accession_match = re.search(r'/(\d{10}-\d{2}-\d{6})/', filing_url)
                    accession_number = accession_match.group(1) if accession_match else filing_url
                
                cursor.execute('SELECT id FROM insider_filings WHERE accession_number = ?', (accession_number,))
                if cursor.fetchone():
                    logger.debug(f"Filing {i}: Duplicate {accession_number}, skipping")
                    continue
                
                # Fetch detailed Form 4 data
                logger.info(f"📄 [{i+1}/{len(filings)}] Fetching details for {accession_number}...")
                details = fetch_form4_details(filing_url)
                
                # Skip if no ticker
                if not details.get('ticker'):
                    logger.debug(f"Filing {i}: No ticker found, skipping")
                    continue
                
                logger.info(f"   → {details.get('ticker')}: {details.get('transaction_type')} {details.get('shares')} shares @ ${details.get('price', 0):.2f}")
                
                # Store the filing
                cursor.execute('''
                    INSERT INTO insider_filings (
                        accession_number, form_type, ticker, company_name,
                        insider_name, insider_title, transaction_type,
                        shares, price, total_value, ownership_change_percent,
                        shares_owned_after, filing_date, transaction_date,
                        filing_url, raw_data
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    accession_number,
                    filing.get('form_type', '4'),
                    details.get('ticker'),
                    filing.get('company_name'),
                    details.get('insider_name'),
                    details.get('insider_title'),
                    details.get('transaction_type'),
                    details.get('shares'),
                    details.get('price'),
                    details.get('total_value'),
                    details.get('ownership_change_percent'),
                    details.get('shares_owned_after'),
                    filing.get('filing_date'),
                    details.get('transaction_date'),
                    filing_url,
                    json.dumps(details)
                ))
                
                filing_id = cursor.lastrowid
                
                # Calculate signal score
                score, reason_flags = calculate_signal_score(details)
                
                # Add cluster detection
                cluster_score, cluster_flag = detect_clusters(details.get('ticker'), conn)
                if cluster_flag:
                    reason_flags.append(cluster_flag)
                    score = min(100, score + (cluster_score * SCORING_WEIGHTS['cluster']))
                
                # Only create signals for BUY transactions with meaningful scores
                if details.get('transaction_type') == 'BUY' and score > 0:
                    is_highlighted = 1 if score >= HIGHLIGHT_THRESHOLD else 0
                    is_conviction = 1 if score >= CONVICTION_THRESHOLD else 0
                    
                    cursor.execute('''
                        INSERT INTO insider_signals (
                            filing_id, ticker, signal_score, insider_name,
                            insider_role, transaction_type, dollar_value,
                            reason_flags, is_highlighted, is_conviction
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        filing_id,
                        details.get('ticker'),
                        score,
                        details.get('insider_name'),
                        details.get('insider_title'),
                        details.get('transaction_type'),
                        details.get('total_value'),
                        json.dumps(reason_flags),
                        is_highlighted,
                        is_conviction
                    ))
                    
                    if is_conviction:
                        logger.info(f"🔥 HIGH CONVICTION: {details.get('ticker')} - {details.get('insider_name')} bought ${details.get('total_value'):,.0f} (Score: {score})")
                    elif is_highlighted:
                        logger.info(f"⭐ HIGHLIGHTED: {details.get('ticker')} - {details.get('insider_name')} (Score: {score})")
                
                processed_count += 1
                
                # Small delay to respect SEC rate limits
                time.sleep(0.1)
                
            except Exception as e:
                logger.error(f"❌ Error processing filing: {e}")
                errors_count += 1
                continue
        
        # Also fetch 13D/13G activist investor filings
        logger.info("📡 Fetching 13D/13G activist filings...")
        activist_filings = fetch_13d_13g_filings(count=30)
        
        for i, filing in enumerate(activist_filings):
            try:
                accession_number = filing.get('accession_number')
                if not accession_number:
                    continue
                
                # Skip if already processed
                cursor.execute('SELECT id FROM insider_filings WHERE accession_number = ?', (accession_number,))
                if cursor.fetchone():
                    continue
                
                # For 13D/13G, we create a high-value signal directly
                # These are always significant (5%+ ownership)
                form_type = filing.get('form_type', '13G')
                is_activist = filing.get('is_activist', False)
                
                # Store the filing (we don't have detailed transaction data for 13D/13G)
                cursor.execute('''
                    INSERT INTO insider_filings (
                        accession_number, form_type, ticker, company_name,
                        insider_name, insider_title, transaction_type,
                        shares, price, total_value, ownership_change_percent,
                        shares_owned_after, filing_date, transaction_date,
                        filing_url, raw_data
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    accession_number,
                    form_type,
                    None,  # Ticker needs to be extracted from filing
                    filing.get('company_name'),
                    filing.get('company_name'),  # Filer name
                    '5%+ Owner' if not is_activist else 'Activist Investor',
                    'STAKE',  # Special type for ownership stake filings
                    0,
                    0,
                    0,
                    5.0,  # Minimum 5% ownership for 13D/13G
                    0,
                    filing.get('filing_date'),
                    None,
                    filing.get('filing_url'),
                    json.dumps(filing)
                ))
                
                filing_id = cursor.lastrowid
                
                # Create signal - 13D/13G are always notable
                score = 85 if is_activist else 70  # Activists score higher
                reason_flags = ['activist_investor' if is_activist else 'large_shareholder', '5pct_ownership']
                
                cursor.execute('''
                    INSERT INTO insider_signals (
                        filing_id, ticker, signal_score, insider_name,
                        insider_role, transaction_type, dollar_value,
                        reason_flags, is_highlighted, is_conviction
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    filing_id,
                    None,  # Will need ticker extraction
                    score,
                    filing.get('company_name'),
                    'Activist' if is_activist else '5%+ Owner',
                    'STAKE',
                    0,
                    json.dumps(reason_flags),
                    1,  # Always highlighted
                    1 if is_activist else 0
                ))
                
                if is_activist:
                    logger.info(f"🦈 ACTIVIST FILING: {filing.get('company_name')} - 13D filed (Score: {score})")
                else:
                    logger.info(f"📊 LARGE SHAREHOLDER: {filing.get('company_name')} - 13G filed (Score: {score})")
                
                processed_count += 1
                
            except Exception as e:
                logger.debug(f"Error processing 13D/13G filing: {e}")
                continue
        
        # Update poll status
        cursor.execute('''
            UPDATE insider_poll_status
            SET last_poll_time = ?,
                filings_processed = filings_processed + ?,
                errors_count = errors_count + ?
            WHERE id = 1
        ''', (datetime.now().isoformat(), processed_count, errors_count))
        
        conn.commit()
        logger.info(f"✅ Processing complete: {processed_count} filings processed, {errors_count} errors")
        
    except Exception as e:
        logger.error(f"❌ Processing cycle failed: {e}")
        cursor.execute('''
            UPDATE insider_poll_status
            SET last_error = ?, errors_count = errors_count + 1
            WHERE id = 1
        ''', (str(e),))
        conn.commit()
    finally:
        conn.close()


def polling_loop():
    """
    Background thread that polls SEC EDGAR at regular intervals
    """
    logger.info(f"🚀 Starting polling loop (interval: {POLL_INTERVAL_SECONDS}s)")
    
    while True:
        try:
            process_filings()
        except Exception as e:
            logger.error(f"❌ Polling loop error: {e}")
        
        # Wait for next poll
        time.sleep(POLL_INTERVAL_SECONDS)


# =============================================================================
# API ENDPOINTS
# =============================================================================

@app.route('/status')
def status():
    """Service status endpoint"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get poll status
    cursor.execute('SELECT * FROM insider_poll_status WHERE id = 1')
    poll_status = cursor.fetchone()
    
    # Get counts
    cursor.execute('SELECT COUNT(*) FROM insider_filings')
    total_filings = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM insider_signals')
    total_signals = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM insider_signals WHERE is_conviction = 1')
    conviction_signals = cursor.fetchone()[0]
    
    # Get today's counts
    today = datetime.now().strftime('%Y-%m-%d')
    cursor.execute('SELECT COUNT(*) FROM insider_signals WHERE DATE(created_at) = ?', (today,))
    today_signals = cursor.fetchone()[0]
    
    conn.close()
    
    return jsonify({
        'service': 'insider_service',
        'status': 'running',
        'port': SERVICE_PORT,
        'poll_interval_seconds': POLL_INTERVAL_SECONDS,
        'last_poll_time': poll_status['last_poll_time'] if poll_status else None,
        'total_filings': total_filings,
        'total_signals': total_signals,
        'conviction_signals': conviction_signals,
        'today_signals': today_signals,
        'filings_processed': poll_status['filings_processed'] if poll_status else 0,
        'errors_count': poll_status['errors_count'] if poll_status else 0,
        'last_error': poll_status['last_error'] if poll_status else None
    })


@app.route('/api/insiders/today')
def get_today_signals():
    """Get today's insider signals"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    today = datetime.now().strftime('%Y-%m-%d')
    
    cursor.execute('''
        SELECT s.*, f.company_name, f.filing_url, f.shares, f.price,
               f.ownership_change_percent, f.filing_date, f.transaction_date
        FROM insider_signals s
        JOIN insider_filings f ON s.filing_id = f.id
        WHERE DATE(s.created_at) = ?
        ORDER BY s.signal_score DESC
    ''', (today,))
    
    signals = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return jsonify({
        'success': True,
        'date': today,
        'count': len(signals),
        'signals': signals
    })


@app.route('/api/insiders/top')
def get_top_signals():
    """Get top signals with optional limit and filters"""
    limit = request.args.get('limit', 50, type=int)
    min_score = request.args.get('min_score', 0, type=int)
    days = request.args.get('days', 7, type=int)
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    since_date = (datetime.now() - timedelta(days=days)).isoformat()
    
    cursor.execute('''
        SELECT s.*, f.company_name, f.filing_url, f.shares, f.price,
               f.ownership_change_percent, f.filing_date, f.transaction_date
        FROM insider_signals s
        JOIN insider_filings f ON s.filing_id = f.id
        WHERE s.signal_score >= ?
        AND s.created_at >= ?
        ORDER BY s.signal_score DESC, s.created_at DESC
        LIMIT ?
    ''', (min_score, since_date, limit))
    
    signals = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return jsonify({
        'success': True,
        'count': len(signals),
        'filters': {
            'limit': limit,
            'min_score': min_score,
            'days': days
        },
        'signals': signals
    })


@app.route('/api/insiders/ticker/<symbol>')
def get_ticker_signals(symbol):
    """Get signals for a specific ticker"""
    symbol = symbol.upper()
    limit = request.args.get('limit', 20, type=int)
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT s.*, f.company_name, f.filing_url, f.shares, f.price,
               f.ownership_change_percent, f.filing_date, f.transaction_date,
               f.insider_name as filing_insider_name
        FROM insider_signals s
        JOIN insider_filings f ON s.filing_id = f.id
        WHERE s.ticker = ?
        ORDER BY s.created_at DESC
        LIMIT ?
    ''', (symbol, limit))
    
    signals = [dict(row) for row in cursor.fetchall()]
    
    # Get summary stats for this ticker
    cursor.execute('''
        SELECT 
            COUNT(*) as total_signals,
            AVG(signal_score) as avg_score,
            SUM(dollar_value) as total_value,
            COUNT(DISTINCT insider_name) as unique_insiders
        FROM insider_signals
        WHERE ticker = ?
    ''', (symbol,))
    
    stats = dict(cursor.fetchone())
    conn.close()
    
    return jsonify({
        'success': True,
        'ticker': symbol,
        'stats': stats,
        'signals': signals
    })


@app.route('/api/insiders/conviction')
def get_conviction_signals():
    """Get high conviction signals (score >= 85)"""
    limit = request.args.get('limit', 20, type=int)
    days = request.args.get('days', 30, type=int)
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    since_date = (datetime.now() - timedelta(days=days)).isoformat()
    
    cursor.execute('''
        SELECT s.*, f.company_name, f.filing_url, f.shares, f.price,
               f.ownership_change_percent, f.filing_date, f.transaction_date
        FROM insider_signals s
        JOIN insider_filings f ON s.filing_id = f.id
        WHERE s.is_conviction = 1
        AND s.created_at >= ?
        ORDER BY s.signal_score DESC, s.created_at DESC
        LIMIT ?
    ''', (since_date, limit))
    
    signals = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return jsonify({
        'success': True,
        'count': len(signals),
        'signals': signals
    })


@app.route('/api/insiders/refresh', methods=['POST'])
def trigger_refresh():
    """Manually trigger a filing refresh"""
    logger.info("📡 Manual refresh triggered")
    
    # Run processing in background
    thread = threading.Thread(target=process_filings, daemon=True)
    thread.start()
    
    return jsonify({
        'success': True,
        'message': 'Refresh triggered - processing in background'
    })


# =============================================================================
# WATCHLIST API ENDPOINTS
# =============================================================================

@app.route('/api/insiders/watchlist', methods=['GET'])
def get_watchlist():
    """Get all watchlist items"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM insider_watchlist ORDER BY created_at DESC')
    items = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return jsonify({
        'success': True,
        'count': len(items),
        'watchlist': items
    })


@app.route('/api/insiders/watchlist', methods=['POST'])
def add_to_watchlist():
    """Add a ticker or insider to watchlist"""
    data = request.get_json()
    
    watch_type = data.get('type', 'ticker')  # 'ticker' or 'insider'
    watch_value = data.get('value', '').strip().upper() if watch_type == 'ticker' else data.get('value', '').strip()
    notes = data.get('notes', '')
    
    if not watch_value:
        return jsonify({'success': False, 'error': 'Value is required'}), 400
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO insider_watchlist (watch_type, watch_value, notes)
            VALUES (?, ?, ?)
        ''', (watch_type, watch_value, notes))
        conn.commit()
        watchlist_id = cursor.lastrowid
        conn.close()
        
        logger.info(f"👁️ Added to watchlist: {watch_type} = {watch_value}")
        
        return jsonify({
            'success': True,
            'id': watchlist_id,
            'message': f'Added {watch_value} to watchlist'
        })
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({'success': False, 'error': 'Already in watchlist'}), 409


@app.route('/api/insiders/watchlist/<int:item_id>', methods=['DELETE'])
def remove_from_watchlist(item_id):
    """Remove item from watchlist"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM insider_watchlist WHERE id = ?', (item_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    
    if deleted:
        return jsonify({'success': True, 'message': 'Removed from watchlist'})
    else:
        return jsonify({'success': False, 'error': 'Item not found'}), 404


@app.route('/api/insiders/watchlist/signals')
def get_watchlist_signals():
    """Get signals that match watchlist items"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get watchlist
    cursor.execute('SELECT watch_type, watch_value FROM insider_watchlist')
    watchlist = cursor.fetchall()
    
    if not watchlist:
        conn.close()
        return jsonify({'success': True, 'count': 0, 'signals': []})
    
    # Build query for matching signals
    ticker_list = [w['watch_value'] for w in watchlist if w['watch_type'] == 'ticker']
    insider_list = [w['watch_value'] for w in watchlist if w['watch_type'] == 'insider']
    
    signals = []
    
    if ticker_list:
        placeholders = ','.join(['?' for _ in ticker_list])
        cursor.execute(f'''
            SELECT s.*, f.company_name, f.filing_url, f.shares, f.price,
                   f.ownership_change_percent, f.filing_date, f.transaction_date,
                   'ticker' as match_type
            FROM insider_signals s
            JOIN insider_filings f ON s.filing_id = f.id
            WHERE s.ticker IN ({placeholders})
            ORDER BY s.created_at DESC
            LIMIT 50
        ''', ticker_list)
        signals.extend([dict(row) for row in cursor.fetchall()])
    
    if insider_list:
        for insider_name in insider_list:
            cursor.execute('''
                SELECT s.*, f.company_name, f.filing_url, f.shares, f.price,
                       f.ownership_change_percent, f.filing_date, f.transaction_date,
                       'insider' as match_type
                FROM insider_signals s
                JOIN insider_filings f ON s.filing_id = f.id
                WHERE s.insider_name LIKE ?
                ORDER BY s.created_at DESC
                LIMIT 20
            ''', (f'%{insider_name}%',))
            signals.extend([dict(row) for row in cursor.fetchall()])
    
    conn.close()
    
    # Remove duplicates and sort by date
    seen = set()
    unique_signals = []
    for s in signals:
        if s['id'] not in seen:
            seen.add(s['id'])
            unique_signals.append(s)
    
    unique_signals.sort(key=lambda x: x['created_at'], reverse=True)
    
    return jsonify({
        'success': True,
        'count': len(unique_signals),
        'signals': unique_signals[:50]
    })


# =============================================================================
# PRICE LOOKUP
# =============================================================================

# Simple price cache to avoid hammering APIs
_price_cache = {}
_price_cache_time = {}
PRICE_CACHE_TTL = 300  # 5 minutes

def get_stock_price(ticker):
    """
    Get current stock price using Yahoo Finance API (free, no key needed)
    Returns price and change info or None if unavailable
    """
    if not ticker:
        return None
    
    ticker = ticker.upper()
    
    # Check cache
    now = time.time()
    if ticker in _price_cache and (now - _price_cache_time.get(ticker, 0)) < PRICE_CACHE_TTL:
        return _price_cache[ticker]
    
    try:
        # Use Yahoo Finance API (no auth required)
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
        params = {'interval': '1d', 'range': '5d'}
        headers = {'User-Agent': SEC_USER_AGENT}
        
        response = requests.get(url, params=params, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            result = data.get('chart', {}).get('result', [])
            
            if result:
                meta = result[0].get('meta', {})
                price = meta.get('regularMarketPrice')
                prev_close = meta.get('previousClose') or meta.get('chartPreviousClose')
                
                if price:
                    change = None
                    change_pct = None
                    if prev_close:
                        change = price - prev_close
                        change_pct = (change / prev_close) * 100
                    
                    price_data = {
                        'price': round(price, 2),
                        'change': round(change, 2) if change else None,
                        'change_pct': round(change_pct, 2) if change_pct else None,
                        'currency': meta.get('currency', 'USD')
                    }
                    
                    # Cache it
                    _price_cache[ticker] = price_data
                    _price_cache_time[ticker] = now
                    
                    return price_data
                    
    except Exception as e:
        logger.debug(f"Price lookup failed for {ticker}: {e}")
    
    return None


@app.route('/api/insiders/price/<ticker>')
def get_price(ticker):
    """Get current price for a ticker"""
    price_data = get_stock_price(ticker)
    
    if price_data:
        return jsonify({
            'success': True,
            'ticker': ticker.upper(),
            **price_data
        })
    else:
        return jsonify({
            'success': False,
            'ticker': ticker.upper(),
            'error': 'Price unavailable'
        }), 404


@app.route('/api/insiders/signals-with-prices')
def get_signals_with_prices():
    """Get top signals with current prices added"""
    limit = request.args.get('limit', 20, type=int)
    min_score = request.args.get('min_score', 0, type=int)
    days = request.args.get('days', 7, type=int)
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    since_date = (datetime.now() - timedelta(days=days)).isoformat()
    
    cursor.execute('''
        SELECT s.*, f.company_name, f.filing_url, f.shares, f.price as purchase_price,
               f.ownership_change_percent, f.filing_date, f.transaction_date
        FROM insider_signals s
        JOIN insider_filings f ON s.filing_id = f.id
        WHERE s.signal_score >= ?
        AND s.created_at >= ?
        ORDER BY s.signal_score DESC, s.created_at DESC
        LIMIT ?
    ''', (min_score, since_date, limit))
    
    signals = []
    for row in cursor.fetchall():
        signal = dict(row)
        
        # Get current price if ticker exists
        if signal.get('ticker'):
            price_data = get_stock_price(signal['ticker'])
            if price_data:
                signal['current_price'] = price_data['price']
                signal['price_change'] = price_data['change']
                signal['price_change_pct'] = price_data['change_pct']
                
                # Calculate gain/loss since insider purchase
                purchase_price = signal.get('purchase_price')
                if purchase_price and purchase_price > 0:
                    gain = price_data['price'] - purchase_price
                    gain_pct = (gain / purchase_price) * 100
                    signal['gain_since_purchase'] = round(gain, 2)
                    signal['gain_since_purchase_pct'] = round(gain_pct, 2)
        
        signals.append(signal)
    
    conn.close()
    
    return jsonify({
        'success': True,
        'count': len(signals),
        'signals': signals
    })


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

if __name__ == '__main__':
    logger.info("=" * 60)
    logger.info("🚀 INSIDER SIGNALS SERVICE STARTING")
    logger.info("=" * 60)
    
    # Initialize database
    init_database()
    
    # Start polling thread (handles initial fetch and subsequent polls)
    polling_thread = threading.Thread(target=polling_loop, daemon=True)
    polling_thread.start()
    logger.info("📡 Polling thread started (will fetch immediately, then every 5 min)")
    
    # Start Flask server
    logger.info(f"🌐 Starting API server on port {SERVICE_PORT}")
    app.run(host='0.0.0.0', port=SERVICE_PORT, debug=False, threaded=True)
