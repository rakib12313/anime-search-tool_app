import streamlit as st
import concurrent.futures
from utils.settings import load_sites, ITEMS_PER_PAGE
from utils.ai_filters import expand_query
from utils.firebase_helper import db_handler
from scrapers.site_scraper import scrape_single_site, get_deep_links

# ==========================================
# 1. SETUP & THEME
# ==========================================
st.set_page_config(page_title="ToonSearch X", page_icon="🧬", layout="wide")

# Custom CSS for Cyberpunk Look
st.markdown("""
<style>
    .stApp { background-color: #050505; color: #e0e0e0; }
    .stTextInput input { background-color: #111; color: #fff; border: 1px solid #333; }
    
    .anime-card {
        background: #111; border: 1px solid #222; border-radius: 8px;
        overflow: hidden; margin-bottom: 15px; position: relative;
        transition: transform 0.2s;
    }
    .anime-card:hover { transform: translateY(-3px); border-color: #00e5ff; }
    .card-img { width: 100%; height: 160px; object-fit: cover; opacity: 0.8; }
    .card-title { padding: 10px; font-weight: 600; font-size: 0.9rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; color: #fff; }
    
    .badge { display: inline-block; padding: 2px 6px; margin: 0 2px; border-radius: 4px; font-size: 0.7rem; font-weight: bold; }
    .badge-site { background: #333; color: #00e5ff; }
    .badge-q { background: #222; color: #ff007f; border: 1px solid #ff007f; }
</style>
""", unsafe_allow_html=True)

# State Management
if 'results' not in st.session_state: st.session_state.results = []
if 'history' not in st.session_state: st.session_state.history = []
if 'link_cache' not in st.session_state: st.session_state.link_cache = {}
if 'page' not in st.session_state: st.session_state.page = 1

# Load Data
SITES = load_sites()

# ==========================================
# 2. SIDEBAR
# ==========================================
with st.sidebar:
    st.title("🧬 ToonSearch X")
    
    with st.expander("👤 User & Cloud"):
        if st.button("Simulate Login"):
            st.success("Connected to Firebase (Mock)")
            # Example of using the helper
            hist = db_handler.get_user_history("user_123")
            st.caption(f"History: {', '.join(hist)}")

    st.subheader("📡 Sources")
    active_sites_names = st.multiselect(
        "Active Repositories", 
        [s['name'] for s in SITES], 
        default=[s['name'] for s in SITES]
    )
    
    st.subheader("⚡ Filters")
    sort_option = st.selectbox("Sort By", ["Relevance", "Title (A-Z)", "Site Name"])
    filter_1080 = st.checkbox("1080p Only")
    
    if st.session_state.history:
        st.divider()
        st.caption("Recent Searches")
        for h in st.session_state.history[:5]:
            if st.button(f"↺ {h}", use_container_width=True):
                st.session_state.query_temp = h

# ==========================================
# 3. MAIN APP
# ==========================================
st.markdown("<h1 style='text-align: center; color: #00e5ff;'>TOONSEARCH <span style='color:#fff'>X</span></h1>", unsafe_allow_html=True)

query_val = st.session_state.get('query_temp', '')
c1, c2 = st.columns([5, 1])
query = c1.text_input("Search Anime...", value=query_val, placeholder="e.g. Pokemon Indigo")
search_btn = c2.button("SEARCH", type="primary", use_container_width=True)

if 'query_temp' in st.session_state: del st.session_state.query_temp

if search_btn and query:
    st.session_state.page = 1
    
    # History & Logs
    if query not in st.session_state.history:
        st.session_state.history.insert(0, query)
    db_handler.log_search(query)
    
    # Execution
    active_site_objs = [s for s in SITES if s['name'] in active_sites_names]
    expanded_q = expand_query(query)
    
    with st.status(f"Neural Scan: '{expanded_q}'", expanded=True) as status:
        results_pool = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(scrape_single_site, s, expanded_q): s for s in active_site_objs}
            for future in concurrent.futures.as_completed(futures):
                site = futures[future]
                try:
                    data, msg = future.result()
                    if data: results_pool.extend(data)
                    status.write(f"{site['name']}: {msg}")
                except: pass
    
    st.session_state.results = results_pool

# ==========================================
# 4. RESULTS DISPLAY
# ==========================================
if st.session_state.results:
    data = st.session_state.results
    
    # Filters
    if filter_1080: data = [x for x in data if "1080p" in x['badges']]
    
    # Sort
    if sort_option == "Title (A-Z)": data.sort(key=lambda x: x['title'])
    elif sort_option == "Site Name": data.sort(key=lambda x: x['site'])
    
    # Pagination
    total = len(data)
    pages = max(1, (total // ITEMS_PER_PAGE) + (1 if total % ITEMS_PER_PAGE > 0 else 0))
    start = (st.session_state.page - 1) * ITEMS_PER_PAGE
    end = start + ITEMS_PER_PAGE
    page_data = data[start:end]
    
    # Controls
    c_inf, c_pg = st.columns([3, 2])
    c_inf.markdown(f"**Found {total} items** | Page {st.session_state.page}/{pages}")
    
    with c_pg:
        bp, bn = st.columns(2)
        if st.session_state.page > 1:
            if bp.button("◀ Prev"): 
                st.session_state.page -= 1
                st.rerun()
        if st.session_state.page < pages:
            if bn.button("Next ▶"): 
                st.session_state.page += 1
                st.rerun()

    # Grid
    cols = st.columns(3)
    for idx, item in enumerate(page_data):
        with cols[idx % 3]:
            # Badges
            badges_html = "".join([f"<span class='badge badge-q'>{b}</span>" for b in item['badges']])
            site_badge = f"<span class='badge badge-site'>{item['site']}</span>"
            
            st.markdown(f"""
            <div class="anime-card">
                <img src="{item['thumb']}" class="card-img">
                <div style="padding:10px;">
                    <div class="card-title" title="{item['title']}">{item['title']}</div>
                    <div style="margin-top:5px;">{site_badge}{badges_html}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            b_vis, b_dl = st.columns(2)
            b_vis.link_button("🌐 Visit", item['link'], use_container_width=True)
            
            key = f"dl_{idx}_{start}"
            if b_dl.button("📥 Links", key=key, use_container_width=True):
                if item['link'] not in st.session_state.link_cache:
                    with st.spinner("Extracting..."):
                        links = get_deep_links(item['link'])
                        st.session_state.link_cache[item['link']] = links
            
            if item['link'] in st.session_state.link_cache:
                with st.expander("Files", expanded=True):
                    d_links = st.session_state.link_cache[item['link']]
                    if d_links:
                        for n, l in d_links: st.markdown(f"• [{n}]({l})")
                    else: st.warning("No direct links.")
elif not query:
    st.markdown("<div style='text-align:center; opacity:0.5; margin-top:50px;'><h3>Waiting for Input...</h3></div>", unsafe_allow_html=True)