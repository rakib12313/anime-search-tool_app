# 🧬 ToonSearch X

A next-generation, cloud-accelerated anime and cartoon scraper built with Python and Streamlit.

## 🚀 Features

*   **Multi-Site Scraping**: Searches 10+ active anime repositories simultaneously.
*   **AI Smart Filters**: Automatically corrects "pkmn" to "Pokemon" and filters irrelevant results.
*   **Deep Link Extraction**: Scrapes the final download page for Google Drive/Mega links.
*   **Cloud Bypassing**: Uses advanced headers to bypass 403 blocks.
*   **Responsive UI**: Cyberpunk-themed interface with mobile-friendly grid.

## 🛠️ Installation

1.  **Clone the repository**
2.  **Install requirements**:
    ```bash
    pip install -r requirements.txt
    ```
3.  **Run the app**:
    ```bash
    streamlit run streamlit_app.py
    ```

## 📂 Structure

*   `streamlit_app.py`: Main UI entry point.
*   `scrapers/`: Core scraping logic.
*   `utils/`: Settings, AI filters, and Cloud helpers.
*   `sources.json`: Configurable list of target websites.