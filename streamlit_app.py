import streamlit as st
import cloudscraper
from bs4 import BeautifulSoup
import urllib.parse
import concurrent.futures
import time
import re
import random

# ==========================================
# 1. CONFIGURATION & STYLING
# ==========================================

st.set_page_config(
    page_title="ToonSearch Pro",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Clean, Modern Dark UI
st.markdown("""
<style>
    .stApp { background-color: #0e1117; }
    
    /* Card Container */
    .result-card {
        background-color: #1a1c24;
        border: 1px solid #333;
        border-radius: 8px;
        margin-bottom: 10px;
        overflow: hidden;
        transition: transform 0.2s;
    }
    .result-card:hover {
        border-color: #f63366;
        transform: translateY(-3px);
    }
    
    /* Image */
    .card-img {
        width: 100%;
        height: 180px;
        object-fit: cover;
        opacity: 0.9;
    }
    
    /* Typography */
    .card-title {
        padding: 10px;
        font-size: 1rem;
        font-weight: 600;
        color: #fff;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .card-meta {
        padding: 0 10px 10px 10px;
        font-size: 0.75rem;
        color: #aaa;
        display: flex;
        justify-content: space-between;
    }
    .site-tag {
        background-color: #f63366;
        color: white;
        padding: 2px 6px;
        border-radius: 4px;
        font-weight: bold;
    }
    
    /* Hide Streamlit Menu */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. SITE DATA & MAPPINGS
# ==========================================

# Mappings to fix "Indigo" -> "Season 1" issues
QUERY_MAP = {
    "indigo": "Season 1",
    "orange": "Season 2",
    "johto": "Season 3",
    "s1": "Season 1", "s2": "Season 2", "s3": "Season 3",
    "gen 1": "Season 1",
    "pkmn": "Pokemon",
    "dbz": "Dragon Ball Z"
}

# Verified Working Sites (as of Dec 2023/Jan 2024)
SITES = [
    { "name": "Toonworld4all", "url": "https://toonworld4all.me/?s={}" },
    { "name": "RareToons", "url": "https://raretoonsindia.rtilinks.com/?s={}" },
    { "name": "DeadToons", "url": "https://deadtoons.one/?s={}" },
    { "name": "PureToons", "url": "https://puretoons.me/?s={}" },
    { "name": "AnimeMafia", "url": "https://animemafia.in/?s={}" },
    { "name": "StarToons", "url": "https://startoonsindia.com/?s={}" },
    { "name": "ToonNation", "url": "https://toonnation.in/?s={}" },
    { "name": "CartoonsArea", "url": "https://cartoonsarea.xyz/?s={}" },
    { "name": "AnimeTM", "url": "https://animetm.org/?s={}" }
]

if 'results' not in st.session_state: st.session_state.results = []
if 'history' not in st.session_state: st.session_state.history = []
if 'link_cache' not in st.session_state: st.session_state.link_cache = {}

# ==========================================
# 3. ROBUST SCRAPER ENGINE
# ==========================================

def get_scraper():
    """Returns a CloudScraper session configured to mimic a real user."""
    return cloudscraper.create_scraper(
        browser={
            'browser': 'chrome',
            'platform': 'windows',
            'desktop': True
        }
    )

def smart_filter(query, title):
    """
    Decides if a result is relevant.
    1. Expands abbreviations (pkmn -> pokemon).
    2. Checks if at least ONE major word from query exists in title.
    """
    # 1. Expand Query
    words = query.lower().split()
    expanded_words = []
    for w in words:
        expanded_words.append(w)
        if w in QUERY_MAP:
            expanded_words.extend(QUERY_MAP[w].lower().split())
            
    # 2. Check Title
    title_lower = title.lower()
    
    # If the title contains the EXACT full query, it's a match
    if query.lower() in title_lower:
        return True
        
    # Check intersection (at least one significant word matches)
    # Filter out common stop words
    stop_words = {'season', 'episode', 'series', 'movie', 'dub', 'sub', 'hindi'}
    sig_words = [w for w in expanded_words if w not in stop_words and len(w) > 2]
    
    if not sig_words: return True # Query was only stop words, show everything
    
    # Check if ANY significant word is in the title
    for sw in sig_words:
        if sw in title_lower:
            return True
            
    return False

def scrape_worker(site, query):
    scraper = get_scraper()
    results = []
    
    try:
        url = site['url'].format(urllib.parse.quote_plus(query))
        resp = scraper.get(url, timeout=10)
        
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # === UNIVERSAL SCRAPING LOGIC ===
            # Instead of looking for specific tags, look for patterns.
            # Most themes have an <article> or <div> with class 'post'
            
            # 1. Broad Selection
            containers = (
                soup.select('article') or 
                soup.select('.post') or 
                soup.select('.result-item') or 
                soup.select('div[id^="post-"]') or
                soup.find_all('div', class_=re.compile(r'(post|entry|item)'))
            )
            
            for item in containers:
                try:
                    # Find Title & Link
                    # Prioritize Heading tags
                    title_tag = item.find(re.compile(r'^h[1-6]$'))
                    a_tag = None
                    
                    if title_tag:
                        a_tag = title_tag.find('a')
                    
                    # Fallback: Find any link with text
                    if not a_tag:
                        # Find all links in this container
                        links = item.find_all('a', href=True)
                        for l in links:
                            if len(l.get_text(strip=True)) > 5: # Assume titles are > 5 chars
                                a_tag = l
                                break
                    
                    if not a_tag: continue
                    
                    title = a_tag.get_text(strip=True)
                    link = a_tag['href']
                    
                    # Clean title
                    if not title or len(title) < 3: continue
                    
                    # === APPLY SMART FILTER ===
                    if not smart_filter(query, title):
                        continue

                    # Find Thumbnail
                    img_src = "https://via.placeholder.com/300x180?text=No+Img"
                    img = item.find('img')
                    if img:
                        # Handle lazy loading
                        for attr in ['data-src', 'data-original', 'src', 'data-lazy-src', 'srcset']:
                            val = img.get(attr)
                            if val and 'http' in val:
                                img_src = val.split(' ')[0]
                                break
                    
                    results.append({'site': site['name'], 'title': title, 'link': link, 'thumb': img_src})
                except: continue
                
    except Exception:
        pass
        
    return results

def get_deep_links(url):
    """Scans for download buttons (Magnet, Mega, Drive)."""
    scraper = get_scraper()
    links = []
    try:
        resp = scraper.get(url, timeout=12)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        keywords = ['drive', 'mega', 'download', '480p', '720p', '1080p', 'batch', 'zip', 'watch', 'magnet']
        content = soup.find('div', class_=re.compile(r'(content|entry)')) or soup
        
        for a in content.find_all('a', href=True):
            txt = a.get_text(" ", strip=True).lower()
            href = a['href']
            
            if 'javascript' in href or len(href) < 5 or '#' in href: continue
            
            # Check if keyword in text OR class contains 'btn'/'button'
            is_download = any(k in txt for k in keywords) or 'btn' in str(a.get('class', '')) or 'button' in str(a.get('class', ''))
            
            if is_download:
                name = txt[:40].title().strip() or "Download Link"
                links.append((name, href))
    except: pass
    return list(set(links))

# ==========================================
# 4. UI LOGIC
# ==========================================

# --- Sidebar ---
with st.sidebar:
    st.header("⚙️ Settings")
    
    # Site Selector
    st.subheader("Sources")
    active_sites_names = st.multiselect("Active Sites", [s['name'] for s in SITES], default=[s['name'] for s in SITES])
    
    st.markdown("---")
    
    # Filters
    st.subheader("Filters")
    f_hindi = st.checkbox("Hindi Audio", value=False)
    f_1080 = st.checkbox("1080p Only", value=False)
    
    st.markdown("---")
    
    # History
    if st.session_state.history:
        st.subheader("History")
        for h in st.session_state.history:
            if st.button(f"↺ {h}", key=f"hist_{h}", use_container_width=True):
                # We will handle the click in the main logic by checking session state
                st.session_state.query_override = h
                st.rerun()

# --- Main Area ---
st.title("⚡ ToonSearch Pro")

# Search Bar Handling
query_val = ""
if 'query_override' in st.session_state:
    query_val = st.session_state.query_override
    del st.session_state.query_override

c1, c2 = st.columns([5, 1])
query = c1.text_input("Search Anime...", value=query_val, placeholder="e.g. Pokemon Indigo, Naruto Shippuden")
do_search = c2.button("SEARCH", type="primary", use_container_width=True)

# --- Search Execution ---
if do_search and query:
    # Update History
    if query not in st.session_state.history:
        st.session_state.history.insert(0, query)
        st.session_state.history = st.session_state.history[:5]
    
    # Prepare Search
    active_sites = [s for s in SITES if s['name'] in active_sites_names]
    
    # Expand Query for "Indigo" cases
    # We pass the raw query to scraper, but we can also append expanded terms if needed
    # Ideally, we search "Pokemon Indigo" and the Smart Filter allows "Pokemon Season 1" through
    # if we mapped it correctly.
    
    search_q = query
    # If user types "Pokemon Indigo", we want to ensure we find "Pokemon Season 1"
    # The scraping URL usually does a fuzzy search on the site.
    
    st.session_state.results = []
    
    # Progress UI
    progress = st.progress(0)
    status = st.empty()
    status.write(f"Searching for **{search_q}**...")
    
    results_acc = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(scrape_worker, s, search_q): s for s in active_sites}
        
        completed = 0
        for future in concurrent.futures.as_completed(futures):
            site = futures[future]
            completed += 1
            progress.progress(completed / len(active_sites))
            
            try:
                data = future.result()
                if data:
                    results_acc.extend(data)
                    status.write(f"✅ {site['name']}: Found {len(data)} results")
            except: pass
            
    st.session_state.results = results_acc
    progress.empty()
    status.empty()

# --- Results Display ---
if st.session_state.results:
    data = st.session_state.results
    
    # Apply Filters
    if f_hindi:
        data = [r for r in data if "hindi" in r['title'].lower() or "dual" in r['title'].lower()]
    if f_1080:
        data = [r for r in data if "1080p" in r['title'].lower()]
    
    # Header & Tools
    c_res, c_tool = st.columns([3, 1])
    c_res.markdown(f"### Found {len(data)} Results")
    
    if data:
        clip_text = "\n".join([f"{r['title']} -> {r['link']}" for r in data])
        c_tool.download_button("💾 Save List", clip_text, "links.txt", use_container_width=True)
    
    # Grid Layout
    cols = st.columns(3)
    for i, item in enumerate(data):
        with cols[i % 3]:
            # HTML Card
            st.markdown(f"""
            <div class="result-card">
                <img src="{item['thumb']}" class="card-img">
                <div class="card-title" title="{item['title']}">{item['title']}</div>
                <div class="card-meta">
                    <span class="site-tag">{item['site']}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Interactive Buttons
            b1, b2 = st.columns(2)
            b1.link_button("🌐 Open", item['link'], use_container_width=True)
            
            key = f"dl_{i}_{item['link']}"
            if b2.button("📥 Links", key=key, use_container_width=True):
                if item['link'] not in st.session_state.link_cache:
                    with st.spinner("Scanning..."):
                        links = get_deep_links(item['link'])
                        st.session_state.link_cache[item['link']] = links
            
            # Show Links
            if item['link'] in st.session_state.link_cache:
                d_links = st.session_state.link_cache[item['link']]
                with st.expander("Downloads", expanded=True):
                    if d_links:
                        for n, l in d_links:
                            st.markdown(f"• [{n}]({l})")
                    else:
                        st.warning("No direct links found.")

elif do_search:
    st.warning("No results found. Try simplifying your query.")
    st.markdown("### Suggestions")
    st.markdown("- Instead of 'Pokemon Indigo League Full Episodes', try **'Pokemon Season 1'**")
    st.markdown("- Instead of 'Ben 10 Classic', try **'Ben 10'** and look for Season 1.")

# --- Empty State ---
elif not query:
    st.markdown("### Popular Searches")
    pop_cols = st.columns(5)
    populars = ["Pokemon", "Naruto", "Dragon Ball Z", "Ben 10", "Doraemon", "Shinchan", "One Piece", "Jujutsu Kaisen", "Demon Slayer", "Avengers"]
    
    for i, p in enumerate(populars):
        if pop_cols[i % 5].button(p, use_container_width=True):
            st.session_state.query_override = p
            st.rerun()
