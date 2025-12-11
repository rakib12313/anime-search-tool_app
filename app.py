import streamlit as st
import requests
from bs4 import BeautifulSoup
import urllib.parse
import json
import random
import concurrent.futures
import time

# ==========================================
# 1. CONFIGURATION & SETUP
# ==========================================

st.set_page_config(page_title="ToonSearch Web", layout="wide", page_icon="📺")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15"
]

DEFAULT_SITES = [
    { "name": "Toonworld4all", "url": "https://toonworld4all.me/?s={}" },
    { "name": "RareToonsIndia", "url": "https://raretoonsindia.rtilinks.com/?s={}" },
    { "name": "DeadToonsIndia", "url": "https://deadtoons.one/?s={}" },
    { "name": "AnimeMafia", "url": "https://animemafia.in/?s={}" }
]

QUERY_EXPANSIONS = {
    "s1": "Season 1", "s2": "Season 2", "ep": "Episode", 
    "mov": "Movie", "pkmn": "Pokemon", "dbz": "Dragon Ball Z"
}

# ==========================================
# 2. LOGIC FUNCTIONS
# ==========================================

@st.cache_data
def get_sites():
    # In a web app, we usually use the default list or load from a repo file
    # For simplicity, we default to the list defined above
    return DEFAULT_SITES

def get_headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
    }

def scrape_single_site(site, query):
    results = []
    try:
        url = site['url'].format(urllib.parse.quote_plus(query))
        resp = requests.get(url, headers=get_headers(), timeout=6)
        
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            # Selectors based on WordPress anime themes
            articles = (soup.select('article') or soup.select('.post-summary') or 
                        soup.select('.post-item') or soup.select('.item'))

            for item in articles:
                try:
                    title_node = item.find(['h1', 'h2', 'h3', 'a'], class_=['entry-title', 'title'])
                    if not title_node and item.name == 'a': title_node = item
                    if not title_node: continue
                    
                    a_tag = title_node if title_node.name == 'a' else title_node.find('a')
                    if not a_tag: continue

                    link = a_tag['href']
                    title = a_tag.get_text(strip=True)
                    
                    img_src = None
                    img = item.find('img')
                    if img:
                        # Try to find the lazy loaded image or standard src
                        for attr in ['data-src', 'data-original', 'src']:
                            val = img.get(attr)
                            if val and val.startswith('http'):
                                img_src = val
                                break
                    
                    # Fallback image if none found
                    if not img_src: img_src = "https://via.placeholder.com/150?text=No+Img"

                    results.append({'site': site['name'], 'title': title, 'link': link, 'thumb': img_src})
                except: continue
    except: pass
    return results

def get_deep_links(url):
    found = []
    try:
        resp = requests.get(url, headers=get_headers(), timeout=8)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        keywords = ['download', 'drive', 'mega', '480p', '720p', '1080p', 'watch']
        content = soup.find('div', class_=['entry-content', 'post-content']) or soup
        
        for a in content.find_all('a', href=True):
            txt = a.get_text(strip=True).lower()
            href = a['href']
            # Simple heuristic for download links
            if any(k in txt for k in keywords) or 'btn' in str(a.get('class', '')):
                name = txt[:50] if len(txt) > 2 else "Download/Watch Link"
                found.append((name, href))
    except: pass
    return list(set(found)) # Remove duplicates

# ==========================================
# 3. STREAMLIT UI
# ==========================================

st.title("📺 ToonSearch: Anime & Cartoon Hub")

# Sidebar
with st.sidebar:
    st.header("Configuration")
    sites = get_sites()
    selected_sites_names = st.multiselect(
        "Select Sources", 
        [s['name'] for s in sites], 
        default=[s['name'] for s in sites]
    )
    
    st.markdown("---")
    st.write("**Filters**")
    filter_hindi = st.checkbox("Hindi Audio")
    filter_1080 = st.checkbox("1080p Quality")

# Search State
if 'results' not in st.session_state:
    st.session_state.results = []
if 'searching' not in st.session_state:
    st.session_state.searching = False

# Search Bar
query = st.text_input("Enter Anime Name (e.g. Pokemon, Naruto)", placeholder="Search...")
col1, col2 = st.columns([1, 5])
with col1:
    search_clicked = st.button("Search", type="primary", use_container_width=True)

# Search Logic
if search_clicked and query:
    st.session_state.results = []
    st.session_state.searching = True
    
    # Expand query abbreviations
    expanded_query = " ".join([QUERY_EXPANSIONS.get(w.lower(), w) for w in query.split()])
    
    active_sites = [s for s in sites if s['name'] in selected_sites_names]
    
    with st.status(f"Searching for: {expanded_query}...") as status:
        all_results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            # We run scraping in parallel
            futures = [executor.submit(scrape_single_site, s, expanded_query) for s in active_sites]
            for future in concurrent.futures.as_completed(futures):
                all_results.extend(future.result())
        
        st.session_state.results = all_results
        status.update(label="Search Complete!", state="complete", expanded=False)
    
    st.session_state.searching = False

# Display Results
if st.session_state.results:
    results = st.session_state.results
    
    # Apply Filters
    if filter_hindi:
        results = [r for r in results if "hindi" in r['title'].lower() or "dual" in r['title'].lower()]
    if filter_1080:
        results = [r for r in results if "1080p" in r['title'].lower()]

    st.write(f"Found **{len(results)}** results.")
    
    # Grid Layout
    for res in results:
        with st.container(border=True):
            c1, c2 = st.columns([1, 4])
            
            with c1:
                st.image(res['thumb'], use_container_width=True)
                
            with c2:
                st.subheader(res['title'])
                st.caption(f"Source: {res['site']}")
                
                # Buttons
                b1, b2 = st.columns([1, 3])
                with b1:
                    st.link_button("Go to Site", res['link'])
                
                # Expander for Deep Links (Scraping on demand)
                with st.expander("Get Download Links"):
                    if st.button("Scan for Links", key=res['link']):
                        with st.spinner("Scanning..."):
                            deep_links = get_deep_links(res['link'])
                            if deep_links:
                                for name, url in deep_links:
                                    st.markdown(f"- [{name}]({url})")
                            else:
                                st.warning("No direct links found.")

elif query and not st.session_state.searching:
    st.info("No results yet. Try searching.")