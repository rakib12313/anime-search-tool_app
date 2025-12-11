import streamlit as st
import cloudscraper
from bs4 import BeautifulSoup
import urllib.parse
import concurrent.futures
import time

# ==========================================
# 1. SETUP & STYLE
# ==========================================

st.set_page_config(page_title="ToonSearch Unlocked", page_icon="🔓", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #121212; color: #e0e0e0; }
    .header-text { font-size: 2.5rem; font-weight: 800; color: #00e5ff; text-align: center; }
    .card { background-color: #1e1e1e; border: 1px solid #333; border-radius: 8px; padding: 0; margin-bottom: 15px; overflow: hidden; }
    .card-img { width: 100%; height: 180px; object-fit: cover; opacity: 0.9; }
    .card-content { padding: 12px; }
    .card-title { font-size: 1rem; font-weight: bold; margin-bottom: 5px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .badge { background-color: #00e5ff; color: #000; padding: 2px 6px; border-radius: 4px; font-size: 0.75rem; font-weight: bold; }
    .err-msg { color: #ff5252; font-size: 0.8rem; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. SITE CONFIGURATION
# ==========================================

# Using a list of verified sites. 
# Note: Some URLs change frequently.
SITES = [
    { "name": "Toonworld4all", "url": "https://toonworld4all.me/?s={}" },
    { "name": "RareToons", "url": "https://raretoonsindia.rtilinks.com/?s={}" },
    { "name": "DeadToons", "url": "https://deadtoons.one/?s={}" },
    { "name": "AnimeMafia", "url": "https://animemafia.in/?s={}" },
    { "name": "PureToons", "url": "https://puretoons.me/?s={}" },
    { "name": "StarToons", "url": "https://startoonsindia.com/?s={}" },
    { "name": "ToonNation", "url": "https://toonnation.in/?s={}" },
    { "name": "CartoonsArea", "url": "https://cartoonsarea.xyz/?s={}" },
]

# Initialize Session State
if 'results' not in st.session_state: st.session_state.results = []
if 'errors' not in st.session_state: st.session_state.errors = []

# ==========================================
# 3. ADVANCED SCRAPER (CLOUDSCRAPER)
# ==========================================

def create_scraper():
    # Creates a browser-like session to bypass Cloudflare
    scraper = cloudscraper.create_scraper(
        browser={
            'browser': 'chrome',
            'platform': 'windows',
            'desktop': True
        }
    )
    return scraper

def scrape_site_logic(site, query):
    scraper = create_scraper()
    results = []
    error = None
    
    try:
        url = site['url'].format(urllib.parse.quote_plus(query))
        # 10s timeout to prevent hanging
        resp = scraper.get(url, timeout=10)
        
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # Universal Selector Strategy
            # We look for ANY common container used in WordPress themes
            items = (
                soup.select('article') or 
                soup.select('.post-summary') or 
                soup.select('.result-item') or 
                soup.select('.post') or
                soup.select('.item') or
                soup.select('div[id^="post-"]') # IDs starting with "post-"
            )

            for item in items:
                try:
                    # Find Title
                    # Priority: Headings with links -> Links with rel='bookmark' -> Any Link
                    title_node = item.find(['h1', 'h2', 'h3', 'h4'], class_=['title', 'entry-title'])
                    
                    if title_node and title_node.find('a'):
                        a_tag = title_node.find('a')
                    else:
                        a_tag = item.find('a', href=True)
                        # Sanity check: link text length
                        if a_tag and len(a_tag.get_text(strip=True)) < 4: 
                            continue

                    if not a_tag: continue

                    title = a_tag.get_text(strip=True)
                    link = a_tag['href']

                    # Find Image
                    img_src = "https://via.placeholder.com/300x200?text=No+Preview"
                    img = item.find('img')
                    if img:
                        # Handle Lazy Load attributes
                        for attr in ['data-src', 'data-original', 'src']:
                            if img.get(attr) and str(img.get(attr)).startswith('http'):
                                img_src = img.get(attr)
                                break
                    
                    results.append({
                        'site': site['name'],
                        'title': title,
                        'link': link,
                        'thumb': img_src
                    })
                except: continue
        else:
            error = f"Status {resp.status_code}"
            
    except Exception as e:
        error = str(e)

    return results, error

def get_deep_links(url):
    # Extracts Download/Watch links from the inner page
    scraper = create_scraper()
    links = []
    try:
        resp = scraper.get(url, timeout=10)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # Keywords for valid links
        whitelist = ['drive', 'mega', 'download', '480p', '720p', '1080p', 'mediafire', 'batch']
        
        content = soup.find('div', class_=['entry-content', 'post-content', 'the-content']) or soup
        
        for a in content.find_all('a', href=True):
            txt = a.get_text(" ", strip=True).lower()
            href = a['href']
            
            if len(href) < 5 or 'javascript' in href: continue
            
            if any(w in txt for w in whitelist) or 'btn' in str(a.get('class', '')):
                name = txt[:40].title().strip() or "Download Link"
                links.append((name, href))
                
    except: pass
    return list(set(links))

# ==========================================
# 4. UI LOGIC
# ==========================================

st.markdown('<div class="header-text">ToonSearch 🔓</div>', unsafe_allow_html=True)

# Controls
with st.sidebar:
    st.header("Settings")
    selected_sites = st.multiselect("Sources", [s['name'] for s in SITES], default=[s['name'] for s in SITES])
    debug_mode = st.checkbox("Show Debug Errors", value=False)
    st.info("If no results appear, the site might be blocking connections or the anime name is different.")

# Search Bar
c1, c2 = st.columns([4, 1])
query = c1.text_input("Search", placeholder="e.g. Pokemon Indigo", label_visibility="collapsed")
btn = c2.button("Search", type="primary", use_container_width=True)

if btn and query:
    st.session_state.results = []
    st.session_state.errors = []
    
    active_sites = [s for s in SITES if s['name'] in selected_sites]
    
    if not active_sites:
        st.error("Select at least one site.")
    else:
        # Progress UI
        bar = st.progress(0)
        status = st.empty()
        
        results_acc = []
        errors_acc = []
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(scrape_site_logic, s, query): s for s in active_sites}
            
            completed = 0
            for future in concurrent.futures.as_completed(futures):
                site = futures[future]
                res, err = future.result()
                
                if res: results_acc.extend(res)
                if err: errors_acc.append(f"{site['name']}: {err}")
                
                completed += 1
                bar.progress(completed / len(active_sites))
                status.write(f"Scanned {site['name']}...")
        
        st.session_state.results = results_acc
        st.session_state.errors = errors_acc
        bar.empty()
        status.empty()

# Display Results
if st.session_state.results:
    st.write(f"Found {len(st.session_state.results)} results.")
    
    cols = st.columns(3)
    for idx, item in enumerate(st.session_state.results):
        with cols[idx % 3]:
            # Custom Card HTML
            st.markdown(f"""
            <div class="card">
                <img src="{item['thumb']}" class="card-img">
                <div class="card-content">
                    <div class="card-title" title="{item['title']}">{item['title']}</div>
                    <span class="badge">{item['site']}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Interactive Area
            b1, b2 = st.columns(2)
            b1.link_button("🌐 Open", item['link'], use_container_width=True)
            
            # Deep Link Extractor
            key = f"dl_{idx}"
            if b2.button("📥 Links", key=key, use_container_width=True):
                with st.spinner("Bypassing protection..."):
                    d_links = get_deep_links(item['link'])
                    if d_links:
                        for n, l in d_links:
                            st.markdown(f"- [{n}]({l})")
                    else:
                        st.warning("No explicit download buttons found.")

elif btn:
    st.warning("No results found on these sites.")
    
    # Fallback to Google
    st.markdown("### 🕵️ Try External Search")
    st.write("If the internal search failed, use Google to search these specific sites:")
    
    google_query = f'site:toonworld4all.me OR site:raretoonsindia.rtilinks.com "{query}"'
    google_url = f"https://www.google.com/search?q={urllib.parse.quote(google_query)}"
    
    st.link_button(f"Search '{query}' on Google (All Sites)", google_url, type="secondary")

# Debug Info
if debug_mode and st.session_state.errors:
    with st.expander("Debug Errors (Why some sites failed)"):
        for e in st.session_state.errors:
            st.write(e)
