import streamlit as st
import requests
from bs4 import BeautifulSoup
import urllib.parse
import random
import concurrent.futures

# ==========================================
# 1. PAGE CONFIG & CSS
# ==========================================

st.set_page_config(
    page_title="ToonSearch Ultimate",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .stApp { background-color: #0E1117; }
    .main-title { font-size: 3rem; font-weight: 800; background: -webkit-linear-gradient(45deg, #FF512F, #DD2476); -webkit-background-clip: text; -webkit-text-fill-color: transparent; text-align: center; margin-bottom: 10px; }
    .card-container { background-color: #1E1E1E; border-radius: 10px; padding: 10px; margin-bottom: 10px; border: 1px solid #333; transition: transform 0.2s; }
    .card-container:hover { border-color: #DD2476; }
    .movie-title { font-size: 1rem; font-weight: 700; color: #fff; margin: 8px 0; height: 45px; overflow: hidden; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
    .site-tag { background-color: #DD2476; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.7rem; font-weight: bold; text-transform: uppercase; }
    .meta-tag { font-size: 0.75rem; color: #aaa; margin-right: 8px; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. CONFIGURATION
# ==========================================

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0"
]

# EXTENDED SITE LIST
SITES = [
    { "name": "Toonworld4all", "url": "https://toonworld4all.me/?s={}" },
    { "name": "RareToons", "url": "https://raretoonsindia.rtilinks.com/?s={}" },
    { "name": "DeadToons", "url": "https://deadtoons.one/?s={}" },
    { "name": "AnimeMafia", "url": "https://animemafia.in/?s={}" },
    { "name": "PureToons", "url": "https://puretoons.me/?s={}" },
    { "name": "StarToons", "url": "https://startoonsindia.com/?s={}" },
    { "name": "AnimeWorld", "url": "https://animeworldindia.com/?s={}" },
    { "name": "CartoonsArea", "url": "https://cartoonsarea.xyz/?s={}" },
    { "name": "ToonNation", "url": "https://toonnation.in/?s={}" },
    { "name": "ToonNetwork", "url": "https://toonnetworkindia.co.in/?s={}" },
    { "name": "HindiDubbed", "url": "https://hindidubbed4u.in/?s={}" },
    { "name": "AnimeTM", "url": "https://animetm.org/?s={}" }
]

if 'results' not in st.session_state: st.session_state.results = []
if 'link_cache' not in st.session_state: st.session_state.link_cache = {}

# ==========================================
# 3. ROBUST SCRAPING ENGINE
# ==========================================

def get_headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Referer": "https://www.google.com/"
    }

def scrape_site(site, query):
    results = []
    try:
        # 1. Prepare URL
        url = site['url'].format(urllib.parse.quote_plus(query))
        
        # 2. Request with longer timeout
        resp = requests.get(url, headers=get_headers(), timeout=10)
        
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # 3. BROADER SELECTORS (Fixes "No Results" issue)
            # Many themes use different container names. We grab them all.
            articles = (
                soup.select('article') or 
                soup.select('.post-summary') or 
                soup.select('.result-item') or 
                soup.select('.post-item') or 
                soup.select('.item') or
                soup.select('.post') or
                soup.select('div.post-content')
            )

            for item in articles:
                try:
                    # A. Find Title and Link
                    # Look for heading tags first, then generic anchors
                    title_node = item.find(['h1', 'h2', 'h3', 'h4'], class_=['entry-title', 'title', 'post-title'])
                    
                    # Fallback: Find first logical link if no heading
                    if not title_node: 
                        title_node = item.find('a', attrs={'rel': 'bookmark'})
                    if not title_node and item.name == 'a': 
                        title_node = item
                        
                    if not title_node: continue
                    
                    a_tag = title_node if title_node.name == 'a' else title_node.find('a')
                    if not a_tag: continue

                    link = a_tag['href']
                    title = a_tag.get_text(strip=True)
                    
                    # Filter junk results
                    if not title or len(title) < 3: continue

                    # B. Find Image (Handle Lazy Loading)
                    img_src = "https://via.placeholder.com/300x450?text=No+Image"
                    img = item.find('img')
                    if img:
                        # Priority: data-src (lazy) -> src (standard)
                        for attr in ['data-src', 'data-original', 'data-lazy-src', 'data-srcset', 'src']:
                            val = img.get(attr)
                            if val and 'http' in val:
                                # Sometimes srcset has multiple links, take the first one
                                img_src = val.split(' ')[0] 
                                break
                    
                    results.append({'site': site['name'], 'title': title, 'link': link, 'thumb': img_src})
                except: continue
    except Exception as e:
        # print(f"Error scraping {site['name']}: {e}") 
        pass
        
    return results

def get_deep_links(url):
    found = []
    try:
        resp = requests.get(url, headers=get_headers(), timeout=12)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        content = soup.find('div', class_=['entry-content', 'post-content', 'the-content']) or soup
        keywords = ['drive', 'mega', 'download', '480p', '720p', '1080p', 'batch', 'watch', 'zip']
        
        for a in content.find_all('a', href=True):
            txt = a.get_text(" ", strip=True).lower()
            href = a['href']
            
            if 'javascript' in href or len(href) < 5: continue

            # Logic: If keyword exists OR it looks like a button
            is_valid = any(k in txt for k in keywords) or 'btn' in str(a.get('class', '')).lower()
            
            if is_valid:
                name = txt[:50].title() if len(txt) > 2 else "Download/Watch"
                found.append((name, href))
                
    except: pass
    return list(set(found))

# ==========================================
# 4. APP UI
# ==========================================

st.markdown('<div class="main-title">⚡ ToonSearch <span style="font-weight:300">Ultimate</span></div>', unsafe_allow_html=True)

# --- Sidebar Controls ---
with st.sidebar:
    st.header("🔍 Sources & Filters")
    
    # Select All / None
    c1, c2 = st.columns(2)
    if c1.button("Select All"):
        st.session_state['selected_sites'] = [s['name'] for s in SITES]
    if c2.button("Unselect All"):
        st.session_state['selected_sites'] = []
        
    # Site Selector
    default_sites = st.session_state.get('selected_sites', [s['name'] for s in SITES])
    selected_names = st.multiselect("Active Sites", [s['name'] for s in SITES], default=default_sites, key='site_selector')
    
    st.divider()
    st.caption("Filters")
    f_hindi = st.checkbox("Hindi Audio Only")
    f_1080 = st.checkbox("1080p Only")

# --- Search Area ---
col_search, col_act = st.columns([4, 1])
with col_search:
    query = st.text_input("Search Anime...", placeholder="e.g. Pokemon Indigo, Ben 10, Naruto", label_visibility="collapsed")
with col_act:
    search_btn = st.button("SEARCH", type="primary", use_container_width=True)

# --- Search Logic ---
if search_btn and query:
    active_sites = [s for s in SITES if s['name'] in selected_names]
    
    if not active_sites:
        st.error("Please select at least one site from the sidebar.")
    else:
        progress = st.progress(0)
        status = st.empty()
        
        results_pool = []
        
        # Threaded Search
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(scrape_site, s, query): s for s in active_sites}
            
            done_count = 0
            for future in concurrent.futures.as_completed(futures):
                site = futures[future]
                try:
                    data = future.result()
                    results_pool.extend(data)
                except: pass
                
                done_count += 1
                progress.progress(done_count / len(active_sites))
                status.caption(f"Scraping {site['name']}...")
        
        st.session_state.results = results_pool
        progress.empty()
        status.empty()

# --- Display Results ---
if st.session_state.results:
    data = st.session_state.results
    
    # Filter Data
    if f_hindi:
        data = [x for x in data if "hindi" in x['title'].lower() or "dual" in x['title'].lower()]
    if f_1080:
        data = [x for x in data if "1080p" in x['title'].lower()]

    st.write(f"Found **{len(data)}** results.")

    # Grid Display
    cols = st.columns(3) # 3 Column Grid
    
    for i, item in enumerate(data):
        with cols[i % 3]:
            # HTML Card
            st.markdown(f"""
            <div class="card-container">
                <img src="{item['thumb']}" style="width:100%; height:200px; object-fit:cover; border-radius:5px;">
                <div class="movie-title" title="{item['title']}">{item['title']}</div>
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <span class="site-tag">{item['site']}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Interactive Buttons (Streamlit native)
            b1, b2 = st.columns(2)
            with b1:
                st.link_button("🌐 Visit Site", item['link'], use_container_width=True)
            with b2:
                # Cache Key Logic
                key = f"btn_{i}_{item['link']}"
                if st.button("📥 Get Links", key=key, use_container_width=True):
                    if item['link'] not in st.session_state.link_cache:
                        with st.spinner("Scanning..."):
                            links = get_deep_links(item['link'])
                            st.session_state.link_cache[item['link']] = links
            
            # Show Links if Cached
            if item['link'] in st.session_state.link_cache:
                links = st.session_state.link_cache[item['link']]
                with st.expander("Download Links", expanded=True):
                    if links:
                        for n, l in links:
                            st.markdown(f"• [{n}]({l})")
                    else:
                        st.warning("No direct links found on page.")

elif search_btn:
    st.info("No results found. Try simplifying your search (e.g., 'Pokemon' instead of 'Pokemon Indigo').")
