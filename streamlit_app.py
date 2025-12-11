import streamlit as st
import requests
from bs4 import BeautifulSoup
import urllib.parse
import json
import random
import concurrent.futures
import time
from datetime import datetime
import re

# ==========================================
# 1. CONFIGURATION & SETUP
# ==========================================

st.set_page_config(page_title="ToonSearch Web", layout="wide", page_icon="📺")

# --- Session State Initialization ---
if 'search_history' not in st.session_state:
    st.session_state.search_history = []
if 'favorites' not in st.session_state:
    st.session_state.favorites = []
if 'results' not in st.session_state:
    st.session_state.results = []
if 'searching' not in st.session_state:
    st.session_state.searching = False
if 'selected_item' not in st.session_state:
    st.session_state.selected_item = None
if 'trending_results' not in st.session_state:
    st.session_state.trending_results = []

# --- Constants ---
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
]

# Expanded list of sites
DEFAULT_SITES = [
    { "name": "Toonworld4all", "url": "https://toonworld4all.me/?s={}", "trending_url": "https://toonworld4all.me/" },
    { "name": "RareToonsIndia", "url": "https://raretoonsindia.rtilinks.com/?s={}", "trending_url": "https://raretoonsindia.rtilinks.com/" },
    { "name": "DeadToonsIndia", "url": "https://deadtoons.one/?s={}", "trending_url": "https://deadtoons.one/" },
    { "name": "AnimeMafia", "url": "https://animemafia.in/?s={}", "trending_url": "https://animemafia.in/" },
    { "name": "AnimeKaizoku", "url": "https://animekaizoku.com/?s={}", "trending_url": "https://animekaizoku.com/" },
    { "name": "GogoAnime", "url": "https://gogoanime.vc/search.html?keyword={}", "trending_url": "https://gogoanime.vc/" },
    { "name": "AnimixPlay", "url": "https://animixplay.to/?s={}", "trending_url": "https://animixplay.to/" },
    { "name": "KayoAnime", "url": "https://kayoanime.com/?s={}", "trending_url": "https://kayoanime.com/" },
    { "name": "OngoingAnime", "url": "https://ongoinganime.com/?s={}", "trending_url": "https://ongoinganime.com/" },
]

QUERY_EXPANSIONS = {
    "s1": "Season 1", "s2": "Season 2", "s3": "Season 3", "s4": "Season 4", "s5": "Season 5",
    "ep": "Episode", "eps": "Episodes", "mov": "Movie", "pkmn": "Pokemon", "dbz": "Dragon Ball Z",
    "db": "Dragon Ball", "op": "One Piece", "nar": "Naruto", "bor": "Boruto", "snk": "Attack on Titan",
    "aot": "Attack on Titan", "mha": "My Hero Academia"
}

POPULAR_SEARCHES = [
    "One Piece", "Jujutsu Kaisen", "Frieren", "Spy x Family", "My Hero Academia",
    "Dragon Ball Z", "Pokemon", "Naruto", "Demon Slayer", "Attack on Titan"
]

# ==========================================
# 2. HELPER & LOGIC FUNCTIONS
# ==========================================

@st.cache_data
def get_sites():
    return DEFAULT_SITES

def get_headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
    }

def extract_metadata(title):
    """Extract year, quality, and audio from title."""
    year_match = re.search(r'\b(19|20)\d{2}\b', title)
    year = year_match.group(0) if year_match else None
    
    quality = list(set(re.findall(r'\b(360p|480p|720p|1080p|4K|2160p)\b', title, re.IGNORECASE)))
    audio = []
    if re.search(r'\bhindi\b', title, re.IGNORECASE): audio.append("Hindi")
    if re.search(r'\benglish\b', title, re.IGNORECASE): audio.append("English")
    if re.search(r'\bjapanese\b|\bjap\b', title, re.IGNORECASE): audio.append("Japanese")
    if re.search(r'\bdual\s*audio\b', title, re.IGNORECASE): audio.append("Dual Audio")
    
    return year, quality, audio

def scrape_single_site(site, query):
    results = []
    try:
        url = site['url'].format(urllib.parse.quote_plus(query))
        resp = requests.get(url, headers=get_headers(), timeout=10)
        
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            articles = (soup.select('article') or soup.select('.post-summary') or 
                        soup.select('.post-item') or soup.select('.item') or
                        soup.select('.last-items') or soup.select('.video_block')) # More selectors

            for item in articles:
                try:
                    a_tag = item.find('a', href=True)
                    if not a_tag: continue

                    link = a_tag['href']
                    title = a_tag.get_text(strip=True)
                    if not title: continue
                    
                    img = item.find('img')
                    img_src = None
                    if img:
                        for attr in ['data-src', 'data-original', 'src']:
                            val = img.get(attr)
                            if val and val.startswith('http'):
                                img_src = val
                                break
                    
                    if not img_src: img_src = "https://via.placeholder.com/150x225?text=No+Image"

                    year, quality, audio = extract_metadata(title)
                    
                    results.append({
                        'site': site['name'], 'title': title, 'link': link, 'thumb': img_src,
                        'year': year, 'quality': quality, 'audio': audio,
                        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    })
                except Exception as e:
                    # st.write(f"Error parsing item from {site['name']}: {e}")
                    continue
    except requests.exceptions.RequestException as e:
        st.sidebar.warning(f"Could not connect to {site['name']}. It may be down.")
    except Exception as e:
        st.sidebar.error(f"An unexpected error occurred with {site['name']}: {e}")
        
    return results

@st.cache_data(ttl=3600) # Cache for 1 hour
def get_trending_content(selected_sites):
    """Scrapes the homepage of selected sites for the latest posts."""
    all_results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(scrape_trending_site, s) for s in selected_sites if 'trending_url' in s]
        for future in concurrent.futures.as_completed(futures):
            all_results.extend(future.result())
    # Sort by timestamp to get the latest
    all_results.sort(key=lambda x: x['timestamp'], reverse=True)
    return all_results[:50] # Return top 50

def scrape_trending_site(site):
    """Scrapes a single site's homepage for trending items."""
    results = []
    try:
        resp = requests.get(site['trending_url'], headers=get_headers(), timeout=10)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            # Look for links in main content areas and lists
            content_area = soup.find('main') or soup.find('div', class_='content') or soup
            articles = content_area.find_all('a', href=True)
            
            for a_tag in articles[:10]: # Limit to 10 items per site to avoid overload
                title = a_tag.get_text(strip=True)
                if len(title) < 10: continue # Skip short/empty links
                
                link = a_tag['href']
                img = a_tag.find('img')
                img_src = None
                if img:
                    for attr in ['data-src', 'src']:
                        val = img.get(attr)
                        if val and val.startswith('http'):
                            img_src = val
                            break
                if not img_src: img_src = "https://via.placeholder.com/150x225?text=No+Image"
                
                year, quality, audio = extract_metadata(title)
                
                results.append({
                    'site': site['name'], 'title': title, 'link': link, 'thumb': img_src,
                    'year': year, 'quality': quality, 'audio': audio,
                    'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
    except Exception:
        # Silently fail for trending, as it's non-critical
        pass
    return results

def get_deep_links(url):
    found = []
    try:
        resp = requests.get(url, headers=get_headers(), timeout=10)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        keywords = ['download', 'drive', 'mega', '480p', '720p', '1080p', 'watch', 'stream', 'mirror']
        content = soup.find('div', class_=['entry-content', 'post-content']) or soup
        
        for a in content.find_all('a', href=True):
            txt = a.get_text(strip=True).lower()
            href = a['href']
            if any(k in txt for k in keywords) or any(k in href.lower() for k in keywords) or 'btn' in str(a.get('class', '')):
                name = a.get_text(strip=True)[:60] or "Download/Watch Link"
                found.append((name, href))
    except: pass
    return list(set(found))

def toggle_favorite(item):
    item_key = f"{item['title']}_{item['site']}"
    if item_key in [f"{fav['title']}_{fav['site']}" for fav in st.session_state.favorites]:
        st.session_state.favorites = [fav for fav in st.session_state.favorites if f"{fav['title']}_{fav['site']}" != item_key]
    else:
        st.session_state.favorites.append(item)

# ==========================================
# 3. STREAMLIT UI & RESPONSIVE CSS
# ==========================================

def apply_custom_css():
    st.markdown("""
    <style>
        /* Main container for grid layout */
        .div-container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 1.5rem;
        }
        
        /* Result card styling */
        .result-card {
            border: 1px solid #ddd;
            border-radius: 10px;
            padding: 1rem;
            background-color: #fff;
            box-shadow: 0 4px 8px rgba(0,0,0,0.05);
            transition: transform 0.2s;
        }
        .result-card:hover {
            transform: translateY(-5px);
        }

        /* Badges */
        .badge {
            display: inline-block;
            padding: 0.2em 0.6em;
            margin: 0.1em;
            font-size: 0.75em;
            border-radius: 0.5rem;
            font-weight: 500;
        }
        .badge-quality { background-color: #e0f2fe; color: #0369a1; }
        .badge-audio { background-color: #fef3c7; color: #92400e; }
        .badge-year { background-color: #ede9fe; color: #5b21b6; }

        /* Dark mode adjustments */
        .stApp[data-theme="dark"] .result-card {
            background-color: #2b2b2b;
            border-color: #444;
        }
        
        /* Make buttons full width on small screens */
        @media (max-width: 768px) {
            .stButton > button {
                width: 100%;
            }
        }
    </style>
    """, unsafe_allow_html=True)

apply_custom_css()

# --- Main Title ---
st.title("📺 ToonSearch: Anime & Cartoon Hub")

# --- Navigation Tabs ---
search_tab, trending_tab, favorites_tab, history_tab = st.tabs(["🔍 Search", "🔥 Trending", "⭐ Favorites", "🕐 History"])

# --- Sidebar Configuration ---
with st.sidebar:
    st.header("⚙️ Configuration")
    
    selected_sites_names = st.multiselect(
        "Select Sources", [s['name'] for s in get_sites()], 
        default=[s['name'] for s in get_sites()]
    )
    
    st.markdown("---")
    st.subheader("🚀 Popular Searches")
    for search_term in POPULAR_SEARCHES:
        if st.button(search_term, key=f"pop_{search_term}", use_container_width=True):
            st.session_state.popular_search_query = search_term
            st.rerun()

    st.markdown("---")
    st.subheader("🎛️ Filters")
    filter_audio = st.multiselect("Audio", ["Hindi", "English", "Japanese", "Dual Audio"])
    filter_quality = st.multiselect("Quality", ["480p", "720p", "1080p", "4K"])
    
    st.markdown("---")
    st.subheader("ℹ️ About")
    st.info("This app scrapes publicly available websites. It does not host any content.")

# --- Search Tab ---
with search_tab:
    # Use popular search if triggered from sidebar
    query = st.text_input(
        "Enter Anime Name (e.g. Pokemon, Naruto)", 
        placeholder="Search...",
        value=st.session_state.get('popular_search_query', '')
    )
    if 'popular_search_query' in st.session_state:
        del st.session_state.popular_search_query

    if st.button("Search", type="primary", use_container_width=True) and query:
        st.session_state.results = []
        st.session_state.searching = True
        st.session_state.selected_item = None # Clear detail view on new search
        
        if query not in st.session_state.search_history:
            st.session_state.search_history.insert(0, query)
            st.session_state.search_history = st.session_state.search_history[:10]
        
        expanded_query = " ".join([QUERY_EXPANSIONS.get(w.lower(), w) for w in query.split()])
        active_sites = [s for s in get_sites() if s['name'] in selected_sites_names]
        
        with st.status(f"Searching for: `{expanded_query}` across {len(active_sites)} sites..."):
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(scrape_single_site, s, expanded_query) for s in active_sites]
                for future in concurrent.futures.as_completed(futures):
                    st.session_state.results.extend(future.result())
        
        st.session_state.searching = False
        st.rerun()

    # Display Detailed View if an item is selected
    if st.session_state.selected_item:
        with st.container():
            with st.expander("📄 Detailed View", expanded=True):
                item = st.session_state.selected_item
                col1, col2 = st.columns([1, 3])
                with col1:
                    st.image(item['thumb'], width=200)
                with col2:
                    st.markdown(f"### {item['title']}")
                    st.caption(f"**Source:** {item['site']}")
                    deep_links = get_deep_links(item['link'])
                    if deep_links:
                        st.markdown("**Direct Links:**")
                        for name, url in deep_links:
                            st.markdown(f"- [{name}]({url})")
                    else:
                        st.warning("No direct links found on the page.")
                    st.link_button("Go to Original Page", item['link'])
                st.markdown("---")

    # Display Search Results
    if st.session_state.results:
        results_to_show = st.session_state.results
        
        # Apply filters
        if filter_audio:
            results_to_show = [r for r in results_to_show if any(a in r['audio'] for a in filter_audio)]
        if filter_quality:
            results_to_show = [r for r in results_to_show if any(q in r['quality'] for q in filter_quality)]

        st.write(f"Found **{len(results_to_show)}** results.")
        
        st.markdown('<div class="div-container">', unsafe_allow_html=True)
        for i, res in enumerate(results_to_show):
            with st.container():
                # FIX: Removed st.card() and adjusted indentation
                st.markdown(f"""
                <div class="result-card">
                    <img src="{res['thumb']}" style="width:100%; border-radius:5px;">
                    <h4>{res['title']}</h4>
                    <p style="font-size:0.9em; color:grey;">
                        Source: {res['site']}
                        {' | Year: ' + res['year'] if res['year'] else ''}
                    </p>
                    <div>
                        {' '.join([f'<span class="badge badge-quality">{q}</span>' for q in res['quality']])}
                        {' '.join([f'<span class="badge badge-audio">{a}</span>' for a in res['audio']])}
                        {f'<span class="badge badge-year">{res["year"]}</span>' if res['year'] else ''}
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    if st.button("📄 Details", key=f"detail_{i}"):
                        st.session_state.selected_item = res
                        st.rerun()
                with col2:
                    if st.button("⭐", key=f"fav_{i}"):
                        toggle_favorite(res)
                        st.rerun()
                with col3:
                    st.link_button("Visit", res['link'])
        st.markdown('</div>', unsafe_allow_html=True)

    elif not st.session_state.searching and query:
        st.info("No results found. Try different keywords or sources.")

# --- Trending Tab ---
with trending_tab:
    st.header("🔥 Trending Now")
    if not st.session_state.trending_results:
        active_sites = [s for s in get_sites() if s['name'] in selected_sites_names]
        with st.spinner("Fetching latest content..."):
            st.session_state.trending_results = get_trending_content(active_sites)
    
    if st.session_state.trending_results:
        st.write("Showing the latest posts from your selected sources.")
        st.markdown('<div class="div-container">', unsafe_allow_html=True)
        for i, res in enumerate(st.session_state.trending_results):
             with st.container():
                # FIX: Removed st.card() and adjusted indentation
                st.markdown(f"""
                <div class="result-card">
                    <img src="{res['thumb']}" style="width:100%; border-radius:5px;">
                    <h4>{res['title']}</h4>
                    <p style="font-size:0.9em; color:grey;">Source: {res['site']}</p>
                </div>
                """, unsafe_allow_html=True)
                if st.button("View", key=f"trend_view_{i}"):
                    st.session_state.selected_item = res
                    st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.warning("Could not fetch trending content. Check your selected sources.")

# --- Favorites Tab ---
with favorites_tab:
    st.header("⭐ Your Favorites")
    if st.session_state.favorites:
        for fav in st.session_state.favorites:
            with st.container():
                # FIX: Removed st.card() and adjusted indentation
                st.markdown(f"""
                <div class="result-card">
                    <img src="{fav['thumb']}" style="width:100%; border-radius:5px;">
                    <h4>{fav['title']}</h4>
                    <p style="font-size:0.9em; color:grey;">Source: {fav['site']}</p>
                </div>
                """, unsafe_allow_html=True)
                col1, col2 = st.columns(2)
                with col1:
                    st.link_button("Visit", fav['link'], use_container_width=True)
                with col2:
                    if st.button("Remove", key=f"remove_{fav['link']}", use_container_width=True):
                        toggle_favorite(fav)
                        st.rerun()
    else:
        st.info("No favorites yet. Click the star icon on search results to add them here.")

# --- History Tab ---
with history_tab:
    st.header("🕐 Search History")
    if st.session_state.search_history:
        for term in st.session_state.search_history:
            if st.button(term, key=f"hist_{term}", use_container_width=True):
                st.session_state.popular_search_query = term
                st.rerun()
    else:
        st.info("No search history yet.")
