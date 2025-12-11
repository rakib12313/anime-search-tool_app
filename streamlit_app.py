import streamlit as st
import cloudscraper
from bs4 import BeautifulSoup
import urllib.parse
import concurrent.futures
import random
import difflib
import time

# ==========================================
# 1. PAGE CONFIGURATION & CSS
# ==========================================

st.set_page_config(
    page_title="ToonSearch Ultimate",
    page_icon="📺",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Modern Dark UI CSS
st.markdown("""
<style>
    /* General App Styling */
    .stApp { background-color: #0e1117; }
    
    /* Card Styling */
    .card {
        background-color: #1a1c24;
        border: 1px solid #2d2f36;
        border-radius: 10px;
        padding: 0;
        margin-bottom: 15px;
        transition: all 0.2s ease-in-out;
        overflow: hidden;
    }
    .card:hover {
        border-color: #ff4b4b;
        transform: translateY(-3px);
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
    }
    
    /* Image Styling */
    .card-img {
        width: 100%;
        height: 160px;
        object-fit: cover;
        opacity: 0.85;
        transition: opacity 0.2s;
    }
    .card:hover .card-img { opacity: 1; }
    
    /* Text Styling */
    .card-body { padding: 12px; }
    .title-text {
        font-size: 1rem;
        font-weight: 600;
        color: #f0f2f6;
        margin-bottom: 5px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    
    /* Badges */
    .site-badge {
        background-color: #ff4b4b;
        color: white;
        padding: 3px 8px;
        border-radius: 4px;
        font-size: 0.75rem;
        font-weight: 700;
        text-transform: uppercase;
        display: inline-block;
    }
    
    /* Button Overrides */
    div.stButton > button {
        width: 100%;
        border-radius: 6px;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. CONSTANTS & DATA
# ==========================================

QUERY_EXPANSIONS = {
    "s1": "Season 1", "s2": "Season 2", "s3": "Season 3", "ep": "Episode", 
    "mov": "Movie", "pkmn": "Pokemon", "dbz": "Dragon Ball Z", "op": "One Piece",
    "mha": "My Hero Academia", "aot": "Attack on Titan", "jjk": "Jujutsu Kaisen",
    "ds": "Demon Slayer", "dora": "Doraemon", "shin": "Shin Chan"
}

POPULAR_TITLES = [
    "Pokemon", "Doraemon", "Shinchan", "Dragon Ball Z", "Naruto Shippuden", 
    "One Piece", "Ben 10", "Jujutsu Kaisen", "Demon Slayer", "Chainsaw Man"
]

SITES = [
    { "name": "Toonworld4all", "url": "https://toonworld4all.me/?s={}" },
    { "name": "RareToons", "url": "https://raretoonsindia.rtilinks.com/?s={}" },
    { "name": "DeadToons", "url": "https://deadtoons.one/?s={}" },
    { "name": "AnimeMafia", "url": "https://animemafia.in/?s={}" },
    { "name": "PureToons", "url": "https://puretoons.me/?s={}" },
    { "name": "StarToons", "url": "https://startoonsindia.com/?s={}" },
    { "name": "CartoonsArea", "url": "https://cartoonsarea.xyz/?s={}" },
    { "name": "ToonNation", "url": "https://toonnation.in/?s={}" },
    { "name": "AnimeTM", "url": "https://animetm.org/?s={}" }
]

# Initialize Session State
if 'results' not in st.session_state: st.session_state.results = []
if 'history' not in st.session_state: st.session_state.history = []
if 'link_cache' not in st.session_state: st.session_state.link_cache = {}
if 'search_active' not in st.session_state: st.session_state.search_active = False

# ==========================================
# 3. CORE LOGIC (SCRAPING)
# ==========================================

def get_scraper(proxy_url=None):
    """Creates a browser session that looks like a real user."""
    options = {
        'browser': 'chrome',
        'platform': 'windows',
        'mobile': False
    }
    scraper = cloudscraper.create_scraper(browser=options)
    if proxy_url:
        scraper.proxies = {'http': proxy_url, 'https': proxy_url}
    return scraper

def expand_query(query):
    """Converts 'pkmn s1' to 'Pokemon Season 1'."""
    words = query.split()
    expanded = [QUERY_EXPANSIONS.get(w.lower(), w) for w in words]
    return " ".join(expanded)

def scrape_worker(site, query, proxy=None):
    """Runs in a background thread to scrape a single site."""
    results = []
    scraper = get_scraper(proxy)
    try:
        url = site['url'].format(urllib.parse.quote_plus(query))
        # 10s timeout to avoid hanging the app
        resp = scraper.get(url, timeout=10)
        
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # Universal Selector: Finds articles, posts, or result items
            items = (
                soup.select('article') or 
                soup.select('.post-summary') or 
                soup.select('.result-item') or 
                soup.select('.post') or
                soup.select('.item') or
                soup.select('div[class*="post"]')
            )

            for item in items:
                try:
                    # Find Title & Link
                    title_node = item.find(['h1', 'h2', 'h3', 'a'], class_=['title', 'entry-title', 'post-title'])
                    
                    # Fallback strategies
                    if not title_node and item.name == 'a': title_node = item
                    if not title_node: 
                        title_node = item.find('a', attrs={'rel': 'bookmark'})
                    
                    if not title_node: continue
                    
                    # Extract Anchor Tag
                    a_tag = title_node if title_node.name == 'a' else title_node.find('a')
                    if not a_tag: a_tag = item.find('a', href=True)
                    
                    if not a_tag: continue
                    link = a_tag['href']
                    title = a_tag.get_text(strip=True)
                    
                    # Basic validation
                    if not title or len(title) < 3: continue

                    # Find Thumbnail
                    img_src = "https://via.placeholder.com/300x180?text=No+Preview"
                    img = item.find('img')
                    if img:
                        # Handle Lazy Loading (common in these sites)
                        for attr in ['data-src', 'data-original', 'src', 'data-lazy-src', 'data-srcset']:
                            val = img.get(attr)
                            if val and 'http' in val:
                                img_src = val.split(' ')[0] # take first url if multiple
                                break
                    
                    results.append({'site': site['name'], 'title': title, 'link': link, 'thumb': img_src})
                except: continue
    except Exception as e:
        # Silently fail for individual sites to keep app running
        pass
    return results

def get_deep_links(url, proxy=None):
    """Scrapes the download page for Mega, Drive, etc."""
    links = []
    scraper = get_scraper(proxy)
    try:
        resp = scraper.get(url, timeout=12)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        whitelist = ['drive', 'mega', 'download', '480p', '720p', '1080p', 'batch', 'zip', 'watch', 'magnet', 'torrent']
        
        # Look in the main content area
        content = soup.find('div', class_=['entry-content', 'post-content', 'the-content']) or soup
        
        for a in content.find_all('a', href=True):
            txt = a.get_text(" ", strip=True).lower()
            href = a['href']
            
            if 'javascript' in href or len(href) < 5 or href.startswith('#'): continue
            
            # Check keywords or button classes
            if any(w in txt for w in whitelist) or 'btn' in str(a.get('class', '')):
                name = txt[:40].title().strip() 
                if len(name) < 3: name = "Download Link"
                links.append((name, href))
    except: pass
    return list(set(links))

# ==========================================
# 4. CALLBACKS (Input Handling)
# ==========================================

def set_search_query(text):
    """Updates the search bar and triggers search state."""
    st.session_state['main_search'] = text
    st.session_state['search_active'] = True

# ==========================================
# 5. SIDEBAR
# ==========================================

with st.sidebar:
    st.title("⚙️ Settings")
    
    proxy_input = st.text_input("Proxy (Optional)", placeholder="http://ip:port")
    
    st.subheader("Sources")
    
    # Select All / Clear Logic
    col_s1, col_s2 = st.columns(2)
    if col_s1.button("Select All"): st.session_state['selected_sites'] = [s['name'] for s in SITES]
    if col_s2.button("Clear"): st.session_state['selected_sites'] = []
    
    # Multiselect with State
    default_opts = st.session_state.get('selected_sites', [s['name'] for s in SITES])
    selected_sites = st.multiselect("Active Sites", [s['name'] for s in SITES], default=default_opts, key='selected_sites')

    st.subheader("Filters")
    f_hindi = st.checkbox("Hindi / Dual Audio", value=False)
    f_1080 = st.checkbox("1080p Only", value=False)
    
    st.markdown("---")
    
    if st.session_state.history:
        st.subheader("🕒 History")
        for h in st.session_state.history:
            # Use callback to fill input
            st.button(f"↺ {h}", on_click=set_search_query, args=(h,), use_container_width=True)
            
    if st.button("🗑️ Clear History"):
        st.session_state.history = []
        st.rerun()

# ==========================================
# 6. MAIN INTERFACE
# ==========================================

st.title("📺 ToonSearch Ultimate")

# Search Bar
col_input, col_btn = st.columns([5, 1])
with col_input:
    query = st.text_input("Search Anime...", placeholder="e.g. Pokemon Season 1", key="main_search")

with col_btn:
    # Button just triggers rerun, logic handles the rest
    if st.button("SEARCH", type="primary", use_container_width=True):
        st.session_state.search_active = True

# Logic: Perform Search
if st.session_state.search_active and query:
    st.session_state.search_active = False # Reset trigger
    
    # 1. Expand Query
    expanded_q = expand_query(query)
    
    # 2. Update History
    if query not in st.session_state.history:
        st.session_state.history.insert(0, query)
        st.session_state.history = st.session_state.history[:8]

    # 3. Filter Sites
    active_site_objs = [s for s in SITES if s['name'] in selected_sites]
    
    if not active_site_objs:
        st.error("⚠️ Please select at least one site from the sidebar.")
    else:
        # 4. Run Scrapers
        status_container = st.status(f"🔍 Searching for: **{expanded_q}**", expanded=True)
        results_accumulator = []
        
        start_time = time.time()
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            # Submit tasks
            future_to_site = {executor.submit(scrape_worker, s, expanded_q, proxy_input): s for s in active_site_objs}
            
            # Process results as they come in
            for future in concurrent.futures.as_completed(future_to_site):
                site = future_to_site[future]
                try:
                    data = future.result()
                    if data:
                        results_accumulator.extend(data)
                        status_container.write(f"✅ **{site['name']}**: Found {len(data)} results")
                    else:
                        status_container.write(f"❌ **{site['name']}**: No results")
                except Exception as e:
                    status_container.write(f"⚠️ **{site['name']}**: Connection Error")
        
        duration = time.time() - start_time
        status_container.update(label=f"Search Complete in {duration:.2f}s", state="complete", expanded=False)
        st.session_state.results = results_accumulator

# ==========================================
# 7. DISPLAY RESULTS
# ==========================================

if st.session_state.results:
    data = st.session_state.results
    
    # Apply Filters
    if f_hindi: 
        data = [r for r in data if "hindi" in r['title'].lower() or "dual" in r['title'].lower()]
    if f_1080: 
        data = [r for r in data if "1080p" in r['title'].lower()]

    # Result Header
    st.divider()
    c1, c2 = st.columns([3, 1])
    c1.subheader(f"Results ({len(data)})")
    
    # "Save Links" Feature
    if data:
        text_data = "\n".join([f"{r['title']} | {r['link']}" for r in data])
        c2.download_button("💾 Save List", text_data, "anime_links.txt")

    # Grid Display
    cols = st.columns(3)
    for idx, item in enumerate(data):
        with cols[idx % 3]:
            # HTML Card
            st.markdown(f"""
            <div class="card">
                <img src="{item['thumb']}" class="card-img">
                <div class="card-body">
                    <div class="title-text" title="{item['title']}">{item['title']}</div>
                    <span class="site-badge">{item['site']}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Action Buttons
            b1, b2 = st.columns(2)
            with b1:
                st.link_button("🌐 Visit", item['link'], use_container_width=True)
            
            with b2:
                # Unique key for every button
                btn_key = f"dl_{idx}_{hash(item['link'])}"
                if st.button("📥 Links", key=btn_key, use_container_width=True):
                    # Check cache
                    if item['link'] not in st.session_state.link_cache:
                        with st.spinner("Extracting..."):
                            links = get_deep_links(item['link'], proxy_input)
                            st.session_state.link_cache[item['link']] = links
            
            # Show Extracted Links
            if item['link'] in st.session_state.link_cache:
                links = st.session_state.link_cache[item['link']]
                with st.expander("Downloads", expanded=True):
                    if links:
                        for name, url in links:
                            st.markdown(f"• [{name}]({url})")
                    else:
                        st.info("No direct links found. Visit site.")

# ==========================================
# 8. EMPTY STATE & SUGGESTIONS
# ==========================================

elif not query:
    st.markdown("### 🔥 Popular Now")
    
    # 5 Column Grid for Chips
    chip_cols = st.columns(5)
    for i, title in enumerate(POPULAR_TITLES):
        # Use callback to handle click
        chip_cols[i % 5].button(title, on_click=set_search_query, args=(title,), use_container_width=True)

elif query and not st.session_state.results and not st.session_state.search_active:
    st.warning(f"No results found for '{query}'.")
    
    # "Did You Mean" Logic
    match = difflib.get_close_matches(query, POPULAR_TITLES, n=1, cutoff=0.5)
    if match:
        st.info(f"Did you mean **{match[0]}**?")
        st.button(f"Search {match[0]}", on_click=set_search_query, args=(match[0],))
    
    # Google Fallback
    st.markdown("---")
    st.markdown("### 🕵️ Try External Search")
    g_query = urllib.parse.quote(f"{query} anime download dual audio")
    st.link_button("Search on Google", f"https://www.google.com/search?q={g_query}", type="primary")
