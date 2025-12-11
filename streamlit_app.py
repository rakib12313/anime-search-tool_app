import streamlit as st
import cloudscraper
from bs4 import BeautifulSoup
import urllib.parse
import concurrent.futures
import random
import difflib
import time

# ==========================================
# 1. CONFIGURATION & CONSTANTS
# ==========================================

st.set_page_config(
    page_title="ToonSearch Ultimate",
    page_icon="📺",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for "Desktop App" feel
st.markdown("""
<style>
    .stApp { background-color: #0f1116; }
    .css-1544g2n { padding-top: 2rem; }
    .card {
        background-color: #1a1c24;
        border: 1px solid #2d2f36;
        border-radius: 8px;
        margin-bottom: 10px;
        transition: transform 0.2s;
    }
    .card:hover { border-color: #3B8ED0; transform: translateY(-2px); }
    .card-img {
        width: 100%;
        height: 180px;
        object-fit: cover;
        border-top-left-radius: 8px;
        border-top-right-radius: 8px;
        opacity: 0.9;
    }
    .card-body { padding: 12px; }
    .title-text { 
        font-size: 0.95rem; 
        font-weight: 600; 
        color: #e0e0e0;
        white-space: nowrap; 
        overflow: hidden; 
        text-overflow: ellipsis; 
        margin-bottom: 4px;
    }
    .site-badge {
        background-color: #3B8ED0;
        color: white;
        padding: 2px 6px;
        font-size: 0.7rem;
        border-radius: 4px;
        font-weight: bold;
    }
    .tag-badge {
        background-color: #2d2f36;
        color: #aaa;
        padding: 2px 6px;
        font-size: 0.7rem;
        border-radius: 4px;
        margin-right: 4px;
    }
</style>
""", unsafe_allow_html=True)

# Data from original App
QUERY_EXPANSIONS = {
    "s1": "Season 1", "s2": "Season 2", "s3": "Season 3", "ep": "Episode", 
    "mov": "Movie", "pkmn": "Pokemon", "dbz": "Dragon Ball Z", "op": "One Piece",
    "mha": "My Hero Academia", "aot": "Attack on Titan", "jjk": "Jujutsu Kaisen",
    "ds": "Demon Slayer", "dora": "Doraemon", "shin": "Shin Chan"
}

POPULAR_TITLES = [
    "pokemon", "doraemon", "shinchan", "dragon ball", "naruto", "one piece", 
    "ben 10", "bleach", "death note", "jujutsu kaisen", "demon slayer", 
    "black clover", "attack on titan", "my hero academia", "chainsaw man"
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

# State Management
if 'results' not in st.session_state: st.session_state.results = []
if 'history' not in st.session_state: st.session_state.history = []
if 'link_cache' not in st.session_state: st.session_state.link_cache = {}

# ==========================================
# 2. LOGIC & SCRAPING
# ==========================================

def get_scraper(proxy_url=None):
    options = {
        'browser': 'chrome',
        'platform': 'windows',
        'desktop': True
    }
    scraper = cloudscraper.create_scraper(browser=options)
    if proxy_url:
        scraper.proxies = {'http': proxy_url, 'https': proxy_url}
    return scraper

def expand_query(query):
    words = query.split()
    expanded = [QUERY_EXPANSIONS.get(w.lower(), w) for w in words]
    return " ".join(expanded)

def scrape_worker(site, query, proxy=None):
    results = []
    scraper = get_scraper(proxy)
    try:
        url = site['url'].format(urllib.parse.quote_plus(query))
        resp = scraper.get(url, timeout=10)
        
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # Universal Selectors (Robust)
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
                    # Title & Link
                    title_node = item.find(['h1', 'h2', 'h3', 'a'], class_=['title', 'entry-title', 'post-title'])
                    if not title_node and item.name == 'a': title_node = item
                    
                    if not title_node: continue
                    a_tag = title_node if title_node.name == 'a' else title_node.find('a')
                    
                    if not a_tag: continue
                    link = a_tag['href']
                    title = a_tag.get_text(strip=True)
                    
                    if not title or len(title) < 3: continue

                    # Image
                    img_src = "https://via.placeholder.com/300x180?text=No+Img"
                    img = item.find('img')
                    if img:
                        for attr in ['data-src', 'data-original', 'src', 'data-lazy-src']:
                            val = img.get(attr)
                            if val and 'http' in val:
                                img_src = val.split(' ')[0]
                                break
                    
                    results.append({'site': site['name'], 'title': title, 'link': link, 'thumb': img_src})
                except: continue
    except: pass
    return results

def get_deep_links(url, proxy=None):
    links = []
    scraper = get_scraper(proxy)
    try:
        resp = scraper.get(url, timeout=12)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        whitelist = ['drive', 'mega', 'download', '480p', '720p', '1080p', 'batch', 'zip', 'watch']
        content = soup.find('div', class_=['entry-content', 'post-content', 'the-content']) or soup
        
        for a in content.find_all('a', href=True):
            txt = a.get_text(" ", strip=True).lower()
            href = a['href']
            
            if 'javascript' in href or len(href) < 5: continue
            
            if any(w in txt for w in whitelist) or 'btn' in str(a.get('class', '')):
                name = txt[:40].title().strip() or "Link"
                links.append((name, href))
    except: pass
    return list(set(links))

# ==========================================
# 3. SIDEBAR (SETTINGS)
# ==========================================

with st.sidebar:
    st.header("⚙️ Configuration")
    
    # Proxy Input
    proxy_input = st.text_input("Proxy (Optional)", placeholder="http://ip:port")
    
    # Site Selector
    st.markdown("### Sources")
    c1, c2 = st.columns(2)
    if c1.button("Select All"): st.session_state['active_sites'] = [s['name'] for s in SITES]
    if c2.button("Clear"): st.session_state['active_sites'] = []
    
    default_sites = st.session_state.get('active_sites', [s['name'] for s in SITES])
    selected_sites = st.multiselect("Active Sites", [s['name'] for s in SITES], default=default_sites, key='active_sites_ms', label_visibility="collapsed")
    st.session_state['active_sites'] = selected_sites # Sync
    
    st.markdown("---")
    
    # Filters
    st.markdown("### Filters")
    f_hindi = st.checkbox("Hindi / Dual Audio", value=False)
    f_eng = st.checkbox("English", value=False)
    f_1080 = st.checkbox("1080p Only", value=False)
    f_720 = st.checkbox("720p Only", value=False)

    st.markdown("---")

    # History
    if st.session_state.history:
        st.markdown("### 🕒 Recent")
        for h in st.session_state.history:
            if st.button(h, key=f"hist_{h}", use_container_width=True):
                st.session_state.search_query_input = h # Hack to fill input
                # Trigger search mechanism manually (conceptually)
                # Streamlit requires a rerun to process the new input state cleanly
                # For this implementation, we just rely on user clicking search again or logic below

# ==========================================
# 4. MAIN INTERFACE
# ==========================================

st.title("📺 ToonSearch Ultimate")

# Search Bar Area
col_in, col_btn = st.columns([5, 1])
with col_in:
    # Check if we clicked history to pre-fill
    def_val = st.session_state.get('search_query_input', "")
    query = st.text_input("Search Anime...", value=def_val, placeholder="e.g. Pokemon s1, Naruto", key="main_search")
with col_btn:
    search_triggered = st.button("SEARCH", type="primary", use_container_width=True)

# Main Logic
if search_triggered and query:
    # 1. Expand Query
    expanded_q = expand_query(query)
    
    # 2. Update History
    if query not in st.session_state.history:
        st.session_state.history.insert(0, query)
        st.session_state.history = st.session_state.history[:8]

    # 3. Execution
    active_s = [s for s in SITES if s['name'] in selected_sites]
    
    if not active_s:
        st.error("No sites selected!")
    else:
        status_c = st.status(f"Searching for: **{expanded_q}**", expanded=True)
        results_acc = []
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(scrape_worker, s, expanded_q, proxy_input): s for s in active_s}
            
            for future in concurrent.futures.as_completed(futures):
                s_name = futures[future]['name']
                try:
                    data = future.result()
                    results_acc.extend(data)
                    status_c.write(f"✅ {s_name}: Found {len(data)}")
                except:
                    status_c.write(f"❌ {s_name}: Error")
        
        st.session_state.results = results_acc
        status_c.update(label="Search Complete", state="complete", expanded=False)

# ==========================================
# 5. RESULTS & TOOLS
# ==========================================

if st.session_state.results:
    data = st.session_state.results
    
    # Filter Logic
    if f_hindi: data = [x for x in data if "hindi" in x['title'].lower() or "dual" in x['title'].lower()]
    if f_eng: data = [x for x in data if "english" in x['title'].lower() or "eng" in x['title'].lower()]
    if f_1080: data = [x for x in data if "1080p" in x['title'].lower()]
    if f_720: data = [x for x in data if "720p" in x['title'].lower()]
    
    # Top Control Bar
    st.divider()
    c_info, c_copy = st.columns([3, 1])
    with c_info:
        st.write(f"Found **{len(data)}** results.")
    with c_copy:
        # Copy All Feature (Restored)
        if data:
            all_links_txt = "\n".join([f"{r['title']} - {r['link']}" for r in data])
            st.download_button("💾 Save Results", all_links_txt, file_name="toonsearch_results.txt")

    # Grid Layout
    cols = st.columns(3)
    for idx, item in enumerate(data):
        with cols[idx % 3]:
            # Card UI
            st.markdown(f"""
            <div class="card">
                <img src="{item['thumb']}" class="card-img">
                <div class="card-body">
                    <div class="title-text" title="{item['title']}">{item['title']}</div>
                    <span class="site-badge">{item['site']}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Buttons
            b1, b2 = st.columns(2)
            with b1:
                st.link_button("🌐 Visit", item['link'], use_container_width=True)
            with b2:
                key = f"dl_{idx}_{item['link']}"
                if st.button("📥 Links", key=key, use_container_width=True):
                    if item['link'] not in st.session_state.link_cache:
                        with st.spinner("Scanning..."):
                            links = get_deep_links(item['link'], proxy_input)
                            st.session_state.link_cache[item['link']] = links
            
            # Expanded Links
            if item['link'] in st.session_state.link_cache:
                links = st.session_state.link_cache[item['link']]
                with st.expander("Download Options", expanded=True):
                    if links:
                        for n, l in links:
                            st.markdown(f"• [{n}]({l})")
                    else:
                        st.caption("No direct links found.")

# Did You Mean? (Restored)
elif search_triggered and not st.session_state.results:
    st.warning("No results found.")
    
    # Fuzzy match from popular list
    closest = difflib.get_close_matches(query.lower(), POPULAR_TITLES, n=1, cutoff=0.5)
    if closest:
        suggestion = closest[0]
        st.info(f"Did you mean **{suggestion}**?")
        if st.button(f"Search for '{suggestion}'"):
            # We can't auto-click, but we can set instructions
            st.caption(f"Please type '{suggestion}' in the box above.")
    
    # Google Fallback (Restored)
    g_url = f"https://www.google.com/search?q={urllib.parse.quote(query + ' anime download')}"
    st.link_button("🔍 Search Google", g_url)

elif not query:
    # Empty State with Popular Chips
    st.markdown("### 🔥 Popular Searches")
    chips = st.columns(5)
    for i, tag in enumerate(POPULAR_TITLES[:10]):
        chips[i % 5].button(tag, key=f"pop_{tag}", use_container_width=True)
