import streamlit as st
import requests
from bs4 import BeautifulSoup
import urllib.parse
import json
import random
import concurrent.futures
import time
from datetime import datetime
import pandas as pd
import re

# ==========================================
# 1. CONFIGURATION & SETUP
# ==========================================

st.set_page_config(page_title="ToonSearch Web", layout="wide", page_icon="📺")

# Initialize session state variables
if 'search_history' not in st.session_state:
    st.session_state.search_history = []
if 'favorites' not in st.session_state:
    st.session_state.favorites = []
if 'dark_mode' not in st.session_state:
    st.session_state.dark_mode = False
if 'results_per_page' not in st.session_state:
    st.session_state.results_per_page = 12
if 'current_page' not in st.session_state:
    st.session_state.current_page = 1

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15"
]

DEFAULT_SITES = [
    { "name": "Toonworld4all", "url": "https://toonworld4all.me/?s={}" },
    { "name": "RareToonsIndia", "url": "https://raretoonsindia.rtilinks.com/?s={}" },
    { "name": "DeadToonsIndia", "url": "https://deadtoons.one/?s={}" },
    { "name": "AnimeMafia", "url": "https://animemafia.in/?s={}" },
    { "name": "AnimeKaizoku", "url": "https://animekaizoku.com/?s={}" },
    { "name": "GogoAnime", "url": "https://gogoanime.vc/search.html?keyword={}" }
]

QUERY_EXPANSIONS = {
    "s1": "Season 1", "s2": "Season 2", "s3": "Season 3", "s4": "Season 4", "s5": "Season 5",
    "ep": "Episode", "eps": "Episodes", 
    "mov": "Movie", "movies": "Movie",
    "pkmn": "Pokemon", "dbz": "Dragon Ball Z", "db": "Dragon Ball", "op": "One Piece",
    "nar": "Naruto", "bor": "Boruto", "snk": "Attack on Titan", "aot": "Attack on Titan"
}

# ==========================================
# 2. LOGIC FUNCTIONS
# ==========================================

@st.cache_data
def get_sites():
    return DEFAULT_SITES

def get_headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
    }

def extract_year(title):
    """Extract year from title if present"""
    match = re.search(r'\((\d{4})\)', title)
    return match.group(1) if match else None

def extract_quality(title):
    """Extract quality information from title"""
    qualities = []
    if "480p" in title.lower():
        qualities.append("480p")
    if "720p" in title.lower():
        qualities.append("720p")
    if "1080p" in title.lower():
        qualities.append("1080p")
    if "4k" in title.lower() or "2160p" in title.lower():
        qualities.append("4K")
    return qualities

def extract_audio(title):
    """Extract audio information from title"""
    audio = []
    if "hindi" in title.lower():
        audio.append("Hindi")
    if "english" in title.lower():
        audio.append("English")
    if "japanese" in title.lower() or "jap" in title.lower():
        audio.append("Japanese")
    if "dual" in title.lower():
        audio.append("Dual Audio")
    return audio

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

                    # Extract additional metadata
                    year = extract_year(title)
                    quality = extract_quality(title)
                    audio = extract_audio(title)
                    
                    results.append({
                        'site': site['name'], 
                        'title': title, 
                        'link': link, 
                        'thumb': img_src,
                        'year': year,
                        'quality': quality,
                        'audio': audio,
                        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    })
                except: continue
    except: pass
    return results

def get_deep_links(url):
    found = []
    try:
        resp = requests.get(url, headers=get_headers(), timeout=8)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        keywords = ['download', 'drive', 'mega', '480p', '720p', '1080p', 'watch', 'stream']
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

def toggle_favorite(item):
    """Toggle an item in favorites"""
    item_key = f"{item['title']}_{item['site']}"
    if item_key in [f"{fav['title']}_{fav['site']}" for fav in st.session_state.favorites]:
        st.session_state.favorites = [fav for fav in st.session_state.favorites 
                                     if f"{fav['title']}_{fav['site']}" != item_key]
    else:
        st.session_state.favorites.append(item)

def is_favorite(item):
    """Check if an item is in favorites"""
    item_key = f"{item['title']}_{item['site']}"
    return item_key in [f"{fav['title']}_{fav['site']}" for fav in st.session_state.favorites]

# ==========================================
# 3. STREAMLIT UI
# ==========================================

# Custom CSS for dark mode and other UI improvements
def apply_custom_css():
    st.markdown("""
    <style>
        .main {
            padding-top: 1rem;
        }
        .stSelectbox > div > div > select {
            color: #495057;
        }
        .favorite-btn {
            background-color: transparent;
            border: none;
            color: #ff4b4b;
            cursor: pointer;
            font-size: 1.5rem;
        }
        .result-card {
            border-radius: 10px;
            padding: 15px;
            margin-bottom: 15px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .dark-mode {
            background-color: #1e1e1e;
            color: white;
        }
        .quality-badge {
            display: inline-block;
            padding: 3px 8px;
            margin-right: 5px;
            border-radius: 4px;
            font-size: 0.8rem;
            background-color: #f0f2f6;
        }
        .audio-badge {
            display: inline-block;
            padding: 3px 8px;
            margin-right: 5px;
            border-radius: 4px;
            font-size: 0.8rem;
            background-color: #e3f2fd;
        }
    </style>
    """, unsafe_allow_html=True)

# Apply custom CSS
apply_custom_css()

# Dark mode toggle in sidebar
def toggle_dark_mode():
    st.session_state.dark_mode = not st.session_state.dark_mode

# Main title
st.title("📺 ToonSearch: Anime & Cartoon Hub")

# Navigation tabs
tab1, tab2, tab3 = st.tabs(["Search", "Favorites", "History"])

with tab1:
    # Sidebar
    with st.sidebar:
        st.header("Configuration")
        
        # Dark mode toggle
        st.checkbox("Dark Mode", value=st.session_state.dark_mode, on_change=toggle_dark_mode)
        
        sites = get_sites()
        selected_sites_names = st.multiselect(
            "Select Sources", 
            [s['name'] for s in sites], 
            default=[s['name'] for s in sites]
        )
        
        st.markdown("---")
        st.write("**Filters**")
        filter_hindi = st.checkbox("Hindi Audio")
        filter_english = st.checkbox("English Audio")
        filter_japanese = st.checkbox("Japanese Audio")
        filter_dual = st.checkbox("Dual Audio")
        
        st.write("**Quality Filters**")
        filter_480 = st.checkbox("480p")
        filter_720 = st.checkbox("720p")
        filter_1080 = st.checkbox("1080p")
        filter_4k = st.checkbox("4K")
        
        st.write("**Year Range**")
        year_min, year_max = st.slider(
            "Release Year", 
            min_value=1980, 
            max_value=2023, 
            value=(2000, 2023)
        )
        
        st.markdown("---")
        st.write("**Display Options**")
        st.session_state.results_per_page = st.selectbox(
            "Results per page", 
            [6, 12, 24, 48], 
            index=1
        )
        
        sort_by = st.selectbox(
            "Sort by", 
            ["Relevance", "Newest First", "Oldest First", "Title A-Z", "Title Z-A"]
        )

    # Search State
    if 'results' not in st.session_state:
        st.session_state.results = []
    if 'searching' not in st.session_state:
        st.session_state.searching = False

    # Search Bar with autocomplete suggestions
    col1, col2 = st.columns([4, 1])
    with col1:
        query = st.text_input("Enter Anime Name (e.g. Pokemon, Naruto)", placeholder="Search...")
    with col2:
        search_clicked = st.button("Search", type="primary", use_container_width=True)

    # Search Logic
    if search_clicked and query:
        st.session_state.results = []
        st.session_state.searching = True
        st.session_state.current_page = 1
        
        # Add to search history
        if query not in st.session_state.search_history:
            st.session_state.search_history.insert(0, query)
            # Keep only last 10 searches
            st.session_state.search_history = st.session_state.search_history[:10]
        
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
        results = st.session_state.results.copy()
        
        # Apply Filters
        if filter_hindi:
            results = [r for r in results if "Hindi" in r['audio']]
        if filter_english:
            results = [r for r in results if "English" in r['audio']]
        if filter_japanese:
            results = [r for r in results if "Japanese" in r['audio']]
        if filter_dual:
            results = [r for r in results if "Dual Audio" in r['audio']]
            
        if filter_480:
            results = [r for r in results if "480p" in r['quality']]
        if filter_720:
            results = [r for r in results if "720p" in r['quality']]
        if filter_1080:
            results = [r for r in results if "1080p" in r['quality']]
        if filter_4k:
            results = [r for r in results if "4K" in r['quality']]
            
        # Year filter
        results = [r for r in results if r['year'] is None or (year_min <= int(r['year']) <= year_max)]
        
        # Sorting
        if sort_by == "Newest First":
            results.sort(key=lambda x: x['year'] if x['year'] else "0", reverse=True)
        elif sort_by == "Oldest First":
            results.sort(key=lambda x: x['year'] if x['year'] else "9999")
        elif sort_by == "Title A-Z":
            results.sort(key=lambda x: x['title'])
        elif sort_by == "Title Z-A":
            results.sort(key=lambda x: x['title'], reverse=True)
        
        # Pagination
        total_pages = max(1, (len(results) + st.session_state.results_per_page - 1) // st.session_state.results_per_page)
        
        # Page selector
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.session_state.current_page = st.selectbox(
                "Page", 
                range(1, total_pages + 1), 
                index=min(st.session_state.current_page - 1, total_pages - 1),
                format_func=lambda x: f"Page {x} of {total_pages}"
            )
        
        # Get current page results
        start_idx = (st.session_state.current_page - 1) * st.session_state.results_per_page
        end_idx = start_idx + st.session_state.results_per_page
        page_results = results[start_idx:end_idx]
        
        st.write(f"Found **{len(results)}** results (showing {len(page_results)}).")
        
        # Grid Layout
        cols = st.columns(3)
        for i, res in enumerate(page_results):
            with cols[i % 3]:
                with st.container(border=True):
                    # Favorite button
                    col1, col2 = st.columns([1, 9])
                    with col1:
                        if st.button("⭐", key=f"fav_{res['link']}", help="Add to favorites"):
                            toggle_favorite(res)
                            st.rerun()
                    
                    with col2:
                        # Thumbnail
                        st.image(res['thumb'], use_container_width=True)
                        
                        # Title and metadata
                        st.subheader(res['title'])
                        
                        # Metadata badges
                        meta_col1, meta_col2 = st.columns(2)
                        with meta_col1:
                            if res['year']:
                                st.caption(f"Year: {res['year']}")
                        with meta_col2:
                            st.caption(f"Source: {res['site']}")
                        
                        # Quality and audio badges
                        if res['quality']:
                            st.write("Quality: " + " ".join([f"<span class='quality-badge'>{q}</span>" for q in res['quality']]), unsafe_allow_html=True)
                        
                        if res['audio']:
                            st.write("Audio: " + " ".join([f"<span class='audio-badge'>{a}</span>" for a in res['audio']]), unsafe_allow_html=True)
                        
                        # Buttons
                        b1, b2 = st.columns([1, 1])
                        with b1:
                            st.link_button("Go to Site", res['link'], use_container_width=True)
                        
                        with b2:
                            # Expander for Deep Links (Scraping on demand)
                            if st.button("Get Links", key=f"deep_{res['link']}", use_container_width=True):
                                with st.spinner("Scanning..."):
                                    deep_links = get_deep_links(res['link'])
                                    if deep_links:
                                        for name, url in deep_links:
                                            st.markdown(f"- [{name}]({url})")
                                    else:
                                        st.warning("No direct links found.")
    elif query and not st.session_state.searching:
        st.info("No results found. Try different keywords or sources.")

with tab2:
    st.header("⭐ Favorites")
    if st.session_state.favorites:
        for fav in st.session_state.favorites:
            with st.container(border=True):
                col1, col2 = st.columns([1, 4])
                with col1:
                    st.image(fav['thumb'], width=150)
                with col2:
                    st.subheader(fav['title'])
                    st.caption(f"Source: {fav['site']}")
                    if fav['year']:
                        st.caption(f"Year: {fav['year']}")
                    
                    b1, b2 = st.columns([1, 1])
                    with b1:
                        st.link_button("Go to Site", fav['link'], use_container_width=True)
                    with b2:
                        if st.button("Remove", key=f"remove_{fav['link']}", use_container_width=True):
                            toggle_favorite(fav)
                            st.rerun()
    else:
        st.info("No favorites yet. Click the star icon on search results to add them here.")

with tab3:
    st.header("🕐 Search History")
    if st.session_state.search_history:
        for i, term in enumerate(st.session_state.search_history):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.write(term)
            with col2:
                if st.button("Search", key=f"history_{i}"):
                    query = term
                    st.rerun()
    else:
        st.info("No search history yet.")

# Footer
st.markdown("---")
st.markdown("© 2023 ToonSearch Web. Not affiliated with any of the listed sites.")
