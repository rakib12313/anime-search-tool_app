import streamlit as st
import requests
from bs4 import BeautifulSoup
import urllib.parse
import random
import concurrent.futures
import time

# ==========================================
# 1. PAGE CONFIG & CSS
# ==========================================

st.set_page_config(
    page_title="ToonSearch Pro",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better UI
st.markdown("""
<style>
    .stApp {
        background-color: #0E1117;
    }
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        color: #4facfe;
        text-align: center;
        margin-bottom: 20px;
    }
    .card-title {
        font-size: 1rem;
        font-weight: 600;
        margin-bottom: 5px;
        height: 50px;
        overflow: hidden;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
    }
    .site-badge {
        background-color: #262730;
        color: #ffa500;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.8rem;
        font-weight: bold;
    }
    /* Hide Streamlit default menu/footer for cleaner look */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. CONFIGURATION & STATE
# ==========================================

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15"
]

DEFAULT_SITES = [
    { "name": "Toonworld4all", "url": "https://toonworld4all.me/?s={}" },
    { "name": "RareToons", "url": "https://raretoonsindia.rtilinks.com/?s={}" },
    { "name": "DeadToons", "url": "https://deadtoons.one/?s={}" },
    { "name": "AnimeMafia", "url": "https://animemafia.in/?s={}" },
    { "name": "PureToons", "url": "https://puretoons.me/?s={}" },
    { "name": "ToonNation", "url": "https://toonnation.in/?s={}" }
]

# Initialize Session State
if 'results' not in st.session_state: st.session_state.results = []
if 'history' not in st.session_state: st.session_state.history = []
if 'deep_links_cache' not in st.session_state: st.session_state.deep_links_cache = {}

# ==========================================
# 3. SCRAPING ENGINE
# ==========================================

def get_headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    }

def scrape_site(site, query):
    results = []
    try:
        url = site['url'].format(urllib.parse.quote_plus(query))
        resp = requests.get(url, headers=get_headers(), timeout=5)
        
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            # Generic scraper for WordPress anime themes
            articles = (soup.select('article') or soup.select('.post-summary') or 
                        soup.select('.post-item') or soup.select('.item') or soup.select('.post'))

            for item in articles:
                try:
                    # Find Title
                    title_node = item.find(['h1', 'h2', 'h3', 'a'], class_=['entry-title', 'title', 'post-title'])
                    if not title_node and item.name == 'a': title_node = item
                    if not title_node: continue
                    
                    a_tag = title_node if title_node.name == 'a' else title_node.find('a')
                    if not a_tag: continue

                    link = a_tag['href']
                    title = a_tag.get_text(strip=True)
                    if len(title) < 3: continue

                    # Find Image
                    img_src = "https://via.placeholder.com/300x400.png?text=No+Cover"
                    img = item.find('img')
                    if img:
                        for attr in ['data-src', 'data-original', 'data-lazy-src', 'src']:
                            val = img.get(attr)
                            if val and val.startswith('http'):
                                img_src = val
                                break
                    
                    results.append({'site': site['name'], 'title': title, 'link': link, 'thumb': img_src})
                except: continue
    except: pass
    return results

def extract_download_links(url):
    found = []
    try:
        resp = requests.get(url, headers=get_headers(), timeout=8)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # Look for typical download containers
        content = soup.find('div', class_=['entry-content', 'post-content', 'the-content']) or soup
        
        # Keywords to identify download buttons vs navigation links
        keywords = ['drive', 'mega', 'batch', 'download', '480p', '720p', '1080p', 'zip']
        
        for a in content.find_all('a', href=True):
            txt = a.get_text(" ", strip=True).lower()
            href = a['href']
            
            # Filter Logic
            is_valid = any(k in txt for k in keywords) or 'btn' in str(a.get('class', '')).lower()
            if is_valid and len(href) > 10 and 'javascript' not in href:
                name = txt[:40].title() if len(txt) > 2 else "Download Link"
                found.append((name, href))
    except Exception as e:
        return [("Error scanning link", "#")]
    
    return list(set(found)) # Remove duplicates

# ==========================================
# 4. UI COMPONENTS
# ==========================================

def render_sidebar():
    with st.sidebar:
        st.markdown("## ⚙️ Filters & Settings")
        
        # Source Selection
        all_site_names = [s['name'] for s in DEFAULT_SITES]
        selected_sites = st.multiselect("Active Sources", all_site_names, default=all_site_names)
        
        st.divider()
        
        # Quality Filters
        st.markdown("**Quality Filters**")
        c1, c2 = st.columns(2)
        f_hindi = c1.checkbox("Hindi", value=False)
        f_eng = c2.checkbox("English", value=False)
        f_1080 = c1.checkbox("1080p", value=False)
        f_720 = c2.checkbox("720p", value=False)

        st.divider()
        
        # History
        if st.session_state.history:
            st.markdown("**🕒 Recent Searches**")
            for h in st.session_state.history:
                if st.button(h, key=f"hist_{h}", use_container_width=True):
                    perform_search(h, selected_sites)
                    st.rerun()
            
            if st.button("Clear History"):
                st.session_state.history = []
                st.rerun()

    return {
        "sites": selected_sites,
        "hindi": f_hindi,
        "eng": f_eng,
        "1080": f_1080,
        "720": f_720
    }

def perform_search(query, active_site_names):
    # Add to history
    if query not in st.session_state.history:
        st.session_state.history.insert(0, query)
        st.session_state.history = st.session_state.history[:5] # Keep last 5

    # Filter site objects based on selection
    target_sites = [s for s in DEFAULT_SITES if s['name'] in active_site_names]
    
    # Progress UI
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    results_bucket = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(scrape_site, site, query): site for site in target_sites}
        
        completed = 0
        for future in concurrent.futures.as_completed(futures):
            site_data = futures[future]
            try:
                data = future.result()
                results_bucket.extend(data)
            except: pass
            
            completed += 1
            progress = completed / len(target_sites)
            progress_bar.progress(progress)
            status_text.text(f"Scraping {site_data['name']}... ({completed}/{len(target_sites)})")
            
    progress_bar.empty()
    status_text.empty()
    st.session_state.results = results_bucket

# ==========================================
# 5. MAIN APP LAYOUT
# ==========================================

filters = render_sidebar()

st.markdown('<div class="main-header">🎬 ToonSearch <span style="color:#FFF; font-size:1.5rem;">Pro</span></div>', unsafe_allow_html=True)

# Search Input
c_search, c_btn = st.columns([5, 1])
with c_search:
    search_query = st.text_input("Search Anime...", placeholder="e.g. Pokemon, Jujutsu Kaisen, Ben 10", label_visibility="collapsed")
with c_btn:
    search_trigger = st.button("Search", type="primary", use_container_width=True)

if search_trigger and search_query:
    perform_search(search_query, filters['sites'])

# Results Logic
if st.session_state.results:
    # 1. Apply Filters
    filtered_data = st.session_state.results
    if filters['hindi']:
        filtered_data = [x for x in filtered_data if "hindi" in x['title'].lower() or "dual" in x['title'].lower()]
    if filters['eng']:
        filtered_data = [x for x in filtered_data if "english" in x['title'].lower() or "eng" in x['title'].lower()]
    if filters['1080']:
        filtered_data = [x for x in filtered_data if "1080p" in x['title'].lower()]
    if filters['720']:
        filtered_data = [x for x in filtered_data if "720p" in x['title'].lower()]

    # 2. Sorting
    col_sort_1, col_sort_2 = st.columns([6, 2])
    with col_sort_1:
        st.write(f"Found **{len(filtered_data)}** results.")
    with col_sort_2:
        sort_opt = st.selectbox("Sort By", ["Relevance", "Site Name"], label_visibility="collapsed")
    
    if sort_opt == "Site Name":
        filtered_data.sort(key=lambda x: x['site'])

    st.divider()

    # 3. Render Grid (3 columns per row)
    cols = st.columns(3)
    
    for idx, item in enumerate(filtered_data):
        with cols[idx % 3]:
            # Card Container
            with st.container(border=True):
                # Image
                st.image(item['thumb'], use_container_width=True)
                
                # Title
                st.markdown(f"<div class='card-title' title='{item['title']}'>{item['title']}</div>", unsafe_allow_html=True)
                
                # Badges
                st.markdown(f"<span class='site-badge'>{item['site']}</span>", unsafe_allow_html=True)
                
                st.markdown("---")
                
                # Action Buttons
                c_visit, c_links = st.columns(2)
                
                with c_visit:
                    st.link_button("🌐 Visit", item['link'], use_container_width=True)
                
                with c_links:
                    # Unique key for every item to prevent state collisions
                    btn_key = f"scan_{idx}"
                    if st.button("📥 Links", key=btn_key, use_container_width=True):
                        # Use cached links if available, else scrape
                        if item['link'] not in st.session_state.deep_links_cache:
                            with st.spinner(".."):
                                links = extract_download_links(item['link'])
                                st.session_state.deep_links_cache[item['link']] = links
                        
                # Display Extracted Links (Expandable)
                if item['link'] in st.session_state.deep_links_cache:
                    links = st.session_state.deep_links_cache[item['link']]
                    with st.expander("Download Options", expanded=True):
                        if not links:
                            st.error("No links found.")
                        for name, url in links:
                            st.markdown(f"• [{name}]({url})")

elif search_trigger:
    st.info("No results found. Try adjusting filters or search terms.")
else:
    # Empty State / Hero
    st.markdown("""
    <div style='text-align: center; padding: 50px; color: #555;'>
        <h3>Ready to Watch?</h3>
        <p>Select your sources in the sidebar and search for your favorite anime.</p>
    </div>
    """, unsafe_allow_html=True)
