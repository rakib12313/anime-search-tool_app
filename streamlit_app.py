import streamlit as st
import cloudscraper
from bs4 import BeautifulSoup
import urllib.parse
import concurrent.futures
import time
import re

# ==========================================
# 1. VISUAL REDESIGN (CSS & CONFIG)
# ==========================================

st.set_page_config(
    page_title="ToonSearch X",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Cyberpunk / Modern Dark UI
st.markdown("""
<style>
    /* Main Background */
    .stApp {
        background-color: #050505;
        background-image: radial-gradient(circle at 50% 0%, #1a1a2e 0%, #000000 70%);
    }

    /* Input Fields */
    .stTextInput > div > div > input {
        background-color: #111;
        color: #fff;
        border: 1px solid #333;
        border-radius: 8px;
        padding: 10px;
    }
    .stTextInput > div > div > input:focus {
        border-color: #00e5ff;
        box-shadow: 0 0 10px rgba(0, 229, 255, 0.3);
    }

    /* Cards */
    .anime-card {
        background: #111;
        border: 1px solid #222;
        border-radius: 12px;
        overflow: hidden;
        transition: transform 0.3s ease, box-shadow 0.3s ease;
        margin-bottom: 20px;
        position: relative;
    }
    .anime-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 8px 20px rgba(0, 229, 255, 0.15);
        border-color: #00e5ff;
    }

    /* Images */
    .card-img {
        width: 100%;
        height: 220px;
        object-fit: cover;
        opacity: 0.8;
        transition: opacity 0.3s;
    }
    .anime-card:hover .card-img { opacity: 1; }

    /* Text */
    .card-content { padding: 15px; }
    .card-title {
        font-family: 'Segoe UI', sans-serif;
        font-size: 1.1rem;
        font-weight: 700;
        color: #fff;
        margin-bottom: 8px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    
    /* Badges */
    .source-badge {
        position: absolute;
        top: 10px;
        right: 10px;
        background: rgba(0,0,0,0.8);
        color: #00e5ff;
        padding: 4px 8px;
        border-radius: 4px;
        font-size: 0.7rem;
        font-weight: bold;
        border: 1px solid #00e5ff;
        backdrop-filter: blur(4px);
    }

    /* Status Bar */
    .status-pill-success { color: #00ff00; font-size: 0.8rem; }
    .status-pill-fail { color: #ff0000; font-size: 0.8rem; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. SITE CONFIGURATION
# ==========================================

# Expanded and verified list
SITES = [
    { "name": "ToonWorld4All", "url": "https://toonworld4all.me/?s={}" },
    { "name": "RareToons", "url": "https://raretoonsindia.rtilinks.com/?s={}" },
    { "name": "DeadToons", "url": "https://deadtoons.one/?s={}" },
    { "name": "AnimeMafia", "url": "https://animemafia.in/?s={}" },
    { "name": "PureToons", "url": "https://puretoons.me/?s={}" },
    { "name": "StarToons", "url": "https://startoonsindia.com/?s={}" },
    { "name": "ToonNation", "url": "https://toonnation.in/?s={}" },
    { "name": "CartoonsArea", "url": "https://cartoonsarea.xyz/?s={}" },
    { "name": "AnimeTM", "url": "https://animetm.org/?s={}" },
    { "name": "SeriesOT", "url": "https://seriesot.com/?s={}" }
]

if 'results' not in st.session_state: st.session_state.results = []
if 'link_cache' not in st.session_state: st.session_state.link_cache = {}
if 'scan_log' not in st.session_state: st.session_state.scan_log = {}

# ==========================================
# 3. ADVANCED SCRAPER ENGINE
# ==========================================

def get_scraper():
    """Returns a CloudScraper instance with randomized browser headers."""
    return cloudscraper.create_scraper(
        browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
    )

def is_relevant(query, title):
    """
    STRICT FILTER: Checks if the title actually contains the search terms.
    Prevents 'Pokemon' search showing 'Digimon'.
    """
    q_words = query.lower().split()
    t_lower = title.lower()
    
    # 1. Primary Keyword Check: The first word of query usually MUST exist
    # (e.g., searching "Pokemon" -> Title must have "Pokemon")
    if len(q_words) > 0:
        if q_words[0] not in t_lower:
            return False
            
    # 2. Match Score: At least 50% of query words must appear
    match_count = sum(1 for w in q_words if w in t_lower)
    return (match_count / len(q_words)) >= 0.5

def scrape_site(site, query):
    scraper = get_scraper()
    results = []
    status = "Failed"
    
    try:
        url = site['url'].format(urllib.parse.quote_plus(query))
        resp = scraper.get(url, timeout=12) # Increased timeout
        
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # BROAD SELECTORS: Catches almost all WordPress anime themes
            articles = (
                soup.select('article') or 
                soup.select('.post-summary') or 
                soup.select('.result-item') or 
                soup.select('.post') or
                soup.select('.item') or
                soup.select('div[id^="post-"]')
            )
            
            if not articles:
                # Fallback: Try finding simple links if structural selectors fail
                # This helps with sites that have very weird HTML
                links = soup.find_all('a', href=True)
                # Filter links that look like posts (length > 20, contains title)
                # This is risky but helps "search all sites"
                pass 

            for item in articles:
                try:
                    # Title Extraction
                    title_node = item.find(['h1', 'h2', 'h3', 'h4'], class_=['title', 'entry-title', 'post-title'])
                    if not title_node and item.name == 'a': title_node = item
                    if not title_node: title_node = item.find('a', attrs={'rel': 'bookmark'})
                    
                    if not title_node: continue
                    
                    a_tag = title_node if title_node.name == 'a' else title_node.find('a')
                    if not a_tag: continue
                    
                    title = a_tag.get_text(strip=True)
                    link = a_tag['href']
                    
                    # === SMART FILTERING ===
                    # If strictly irrelevant, skip
                    if not is_relevant(query, title):
                        continue

                    # Image Extraction
                    img_src = "https://via.placeholder.com/300x200/111/333?text=No+Image"
                    img = item.find('img')
                    if img:
                        for attr in ['data-src', 'data-original', 'src', 'data-lazy-src', 'srcset']:
                            val = img.get(attr)
                            if val and 'http' in val:
                                img_src = val.split(' ')[0]
                                break
                    
                    results.append({
                        'site': site['name'], 
                        'title': title, 
                        'link': link, 
                        'thumb': img_src
                    })
                except: continue
            
            status = f"Success ({len(results)})"
        else:
            status = f"Error {resp.status_code}"
            
    except Exception as e:
        status = "Timeout/Block"
        
    return results, status

def get_deep_links(url):
    """Deep scans a page for Magnet/Drive/Mega links."""
    scraper = get_scraper()
    links = []
    try:
        resp = scraper.get(url, timeout=10)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # Expanded keywords
        keywords = ['drive', 'mega', 'download', '480p', '720p', '1080p', 'magnet', 'torrent', 'batch', 'zip', 'rar', 'mediafire']
        content = soup.find('div', class_=['entry-content', 'post-content', 'the-content']) or soup
        
        for a in content.find_all('a', href=True):
            txt = a.get_text(" ", strip=True).lower()
            href = a['href']
            
            # Filter junk
            if 'javascript' in href or len(href) < 5 or '#' in href: continue
            
            # Logic
            if any(k in txt for k in keywords) or 'btn' in str(a.get('class', '')):
                clean_name = txt[:40].title().strip() or "Download Link"
                links.append((clean_name, href))
                
    except: pass
    return list(set(links))

# ==========================================
# 4. UI LOGIC
# ==========================================

# --- HERO SECTION ---
st.markdown("<h1 style='text-align: center; color: #00e5ff; font-weight: 800; font-size: 3rem;'>TOONSEARCH <span style='color: white;'>X</span></h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #aaa; margin-bottom: 30px;'>Next-Gen Anime & Cartoon Indexer</p>", unsafe_allow_html=True)

# --- SEARCH BAR ---
c_search, c_btn = st.columns([5, 1])
with c_search:
    query = st.text_input("Search", placeholder="e.g. Pokemon Indigo League, Ben 10 Classic...", label_visibility="collapsed")
with c_btn:
    search_clicked = st.button("SEARCH", type="primary", use_container_width=True)

# --- FILTERS ---
with st.expander("⚙️ Advanced Filters", expanded=False):
    c1, c2, c3 = st.columns(3)
    f_strict = c1.checkbox("Strict Title Match", value=True, help="Removes results that don't match your keywords exactly.")
    f_hindi = c2.checkbox("Hindi / Dual Audio", value=False)
    f_1080 = c3.checkbox("1080p Only", value=False)
    
    selected_sites = st.multiselect("Active Sources", [s['name'] for s in SITES], default=[s['name'] for s in SITES])

# --- SEARCH EXECUTION ---
if search_clicked and query:
    st.session_state.results = []
    st.session_state.scan_log = {}
    
    active_sites_list = [s for s in SITES if s['name'] in selected_sites]
    
    if not active_sites_list:
        st.error("Select at least one source!")
    else:
        status_box = st.status("Initializing Neural Handshake...", expanded=True)
        results_bucket = []
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            # Launch Threads
            future_map = {executor.submit(scrape_site, s, query): s for s in active_sites_list}
            
            for future in concurrent.futures.as_completed(future_map):
                site_obj = future_map[future]
                site_name = site_obj['name']
                try:
                    data, msg = future.result()
                    st.session_state.scan_log[site_name] = msg
                    if data:
                        results_bucket.extend(data)
                        status_box.write(f"✅ {site_name}: Found {len(data)}")
                    else:
                        if "Timeout" in msg:
                            status_box.write(f"⚠️ {site_name}: Connection Timed Out")
                        else:
                            status_box.write(f"❌ {site_name}: No relevant results")
                except:
                    st.session_state.scan_log[site_name] = "Critical Error"
        
        st.session_state.results = results_bucket
        status_box.update(label="Scan Complete", state="complete", expanded=False)

# --- RESULTS DISPLAY ---
if st.session_state.results:
    data = st.session_state.results
    
    # Apply Filters
    if f_hindi:
        data = [x for x in data if "hindi" in x['title'].lower() or "dual" in x['title'].lower()]
    if f_1080:
        data = [x for x in data if "1080p" in x['title'].lower()]
        
    st.markdown(f"### Found {len(data)} items")
    
    # GRID SYSTEM
    cols = st.columns(3)
    for idx, item in enumerate(data):
        with cols[idx % 3]:
            # HTML Card
            st.markdown(f"""
            <div class="anime-card">
                <div class="source-badge">{item['site']}</div>
                <img src="{item['thumb']}" class="card-img">
                <div class="card-content">
                    <div class="card-title" title="{item['title']}">{item['title']}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Interactive Buttons
            btn_col1, btn_col2 = st.columns(2)
            btn_col1.link_button("🌐 Visit", item['link'], use_container_width=True)
            
            # Deep Link Extractor
            unique_key = f"{idx}_{item['link']}"
            if btn_col2.button("📥 Links", key=unique_key, use_container_width=True):
                if item['link'] not in st.session_state.link_cache:
                    with st.spinner("Decrypting..."):
                        links = get_deep_links(item['link'])
                        st.session_state.link_cache[item['link']] = links
            
            # Show Links if cached
            if item['link'] in st.session_state.link_cache:
                d_links = st.session_state.link_cache[item['link']]
                with st.expander("Download Options", expanded=True):
                    if d_links:
                        for n, l in d_links:
                            st.markdown(f"• [{n}]({l})")
                    else:
                        st.warning("No direct links found.")

# --- CONNECTION DASHBOARD (Footer) ---
if st.session_state.scan_log:
    with st.expander("📡 Network Status Dashboard"):
        st.write("Live status of connected anime repositories:")
        c_log1, c_log2 = st.columns(2)
        
        # Split logs into two columns
        items = list(st.session_state.scan_log.items())
        half = len(items) // 2
        
        for k, v in items[:half]:
            color = "#00ff00" if "Success" in v else "#ff0000"
            c_log1.markdown(f"**{k}**: <span style='color:{color}'>{v}</span>", unsafe_allow_html=True)
            
        for k, v in items[half:]:
            color = "#00ff00" if "Success" in v else "#ff0000"
            c_log2.markdown(f"**{k}**: <span style='color:{color}'>{v}</span>", unsafe_allow_html=True)

# --- EMPTY STATE ---
elif not query:
    st.markdown("""
    <div style='text-align: center; padding: 50px; opacity: 0.5;'>
        <h2>Start your search...</h2>
        <p>Supports: Pokemon, Naruto, Ben 10, Doraemon & More</p>
    </div>
    """, unsafe_allow_html=True)
