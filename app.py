import streamlit as st
import requests
from bs4 import BeautifulSoup
import logging
import pandas as pd
import sqlite3
import re
import nltk
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import LatentDirichletAllocation
import time # To add slight delay for better UX

# --- NLTK Setup ---
# Download necessary NLTK data (stopwords, punkt tokenizer)
@st.cache_resource # Cache the download check
def download_nltk_data():
    # Check and download NLTK resources if needed
    # Using a list for easy extension
    nltk_packages = {
        'stopwords': 'corpora/stopwords',
        'punkt': 'tokenizers/punkt',
        'punkt_tab': 'tokenizers/punkt_tab'
    }
    downloaded_any = False
    for pkg_name, pkg_path in nltk_packages.items():
        try:
            nltk.data.find(pkg_path)
        except LookupError:
            st.info(f"Downloading NLTK resource: {pkg_name}...")
            try:
                nltk.download(pkg_name, quiet=True)
                st.success(f"Downloaded NLTK resource: {pkg_name}")
                downloaded_any = True
            except Exception as e:
                st.error(f"Failed to download NLTK resource {pkg_name}: {e}")
                st.stop() # Stop execution if critical download fails
    if downloaded_any:
        st.rerun() # Rerun the app after download to ensure imports work
    return True

if download_nltk_data():
    from nltk.corpus import stopwords
    from nltk.tokenize import word_tokenize
else:
    st.error("Failed to initialize NLTK. Please check your internet connection and try again.")
    st.stop()

# --- Logging Setup (Optional for Streamlit, useful for debugging) ---
# Streamlit handles most output, but basic logging can still be helpful
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Configuration ---
CNN_HEALTH_URL = "https://www.cnn.com/health"
# Add other sources here if scrapers are fixed
SOURCES = {
    "CNN Health": CNN_HEALTH_URL
    # "Reuters": REUTERS_NEWS_URL,
    # "The Guardian": GUARDIAN_URL
}
CSV_FILENAME = 'cnn_health_news.csv'
DB_FILENAME = 'news_data.db'
DB_TABLE_NAME = 'articles'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

# --- Scraping Function ---
# Generic scraping logic (adapt selectors per source if needed)
def scrape_cnn_health(url):
    articles = []
    try:
        logging.info(f"Fetching URL: {url}")
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        logging.info("Successfully fetched CNN page.")
        soup = BeautifulSoup(response.content, 'html.parser')

        # Selectors adapted from previous script
        headlines = soup.select('a[data-link-type="article"]')
        if not headlines:
             headline_texts = soup.select('span[data-editable="headline"]')
             processed_headlines = []
             for ht in headline_texts:
                 link_tag = ht.find_parent('a')
                 if link_tag:
                     processed_headlines.append(link_tag)
             headlines = processed_headlines

        logging.info(f"Found {len(headlines)} potential headline elements for CNN.")
        seen_urls = set()
        for headline in headlines:
            title_span = headline.find('span[data-editable="headline"]')
            title = title_span.text.strip() if title_span else headline.text.strip()
            url = headline.get('href')

            if title and url:
                if url.startswith('/'):
                    url = f"https://www.cnn.com{url}"
                elif not url.startswith('http'):
                    continue

                if url.startswith("https://www.cnn.com/") and url not in seen_urls:
                    path_parts = url.split('cnn.com/')[-1].split('/')
                    if len(path_parts) > 3:
                         articles.append({'title': title, 'url': url})
                         seen_urls.add(url)
                         logging.debug(f"Added CNN article: {title} - {url}")

    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching CNN: {e}")
        st.error(f"Error fetching data from CNN: {e}")
    except Exception as e:
        logging.error(f"An error occurred during CNN scraping: {e}", exc_info=True)
        st.error(f"An unexpected error occurred during CNN scraping: {e}")

    logging.info(f"Scraped {len(articles)} articles from CNN.")
    return articles

# --- Data Processing Functions ---
@st.cache_data # Cache the result of cleaning
def clean_data(articles_list):
    if not articles_list:
        return pd.DataFrame(columns=['title', 'url', 'source']) # Return empty DF if no articles

    df = pd.DataFrame(articles_list)
    df = df.dropna(subset=['title', 'url'])
    df = df.drop_duplicates(subset=['url'])

    # Advanced Cleaning
    image_extensions = ['.jpg', '.png', '.gif', '.jpeg', '.svg', '.webp']
    df = df[~df['title'].str.contains('/', na=False)]
    df = df[~df['title'].str.lower().str.endswith(tuple(image_extensions), na=False)]
    df = df[df['title'].str.count(' ') > 0] # Ensure title has at least one space

    df = df.reset_index(drop=True)
    return df

# --- Analysis Functions ---
@st.cache_data
def analyze_keywords(df, keywords):
    results = {}
    if not df.empty:
        for keyword in keywords:
            count = df['title'].str.contains(keyword, case=False, na=False).sum()
            results[keyword] = count
        # Co-occurrence
        co_occurrence_count = df[df['title'].str.contains(keywords[0], case=False, na=False) &
                                 df['title'].str.contains(keywords[1], case=False, na=False)].shape[0]
        results[f"Both '{keywords[0]}' and '{keywords[1]}'"] = co_occurrence_count
    return results

@st.cache_data
def perform_topic_modeling(df, num_topics=5):
    topic_results = {}
    if not df.empty and 'title' in df.columns:
        stop_words = set(stopwords.words('english'))
        custom_stop_words = {'say', 'courtesy'} # Keep custom stop words
        stop_words.update(custom_stop_words)

        def preprocess_text(text):
            if not isinstance(text, str): return ""
            text = text.lower()
            text = re.sub(r'[\W\d_]+', ' ', text)
            tokens = word_tokenize(text)
            tokens = [word for word in tokens if word not in stop_words and len(word) > 2]
            return " ".join(tokens)

        df['processed_title'] = df['title'].apply(preprocess_text)
        processed_titles = df[df['processed_title'].str.len() > 0]['processed_title']

        if not processed_titles.empty:
            vectorizer = TfidfVectorizer(max_df=0.90, min_df=2, stop_words='english')
            try:
                tf = vectorizer.fit_transform(processed_titles)
                feature_names = vectorizer.get_feature_names_out()
                lda = LatentDirichletAllocation(n_components=num_topics, max_iter=10,
                                            learning_method='online', random_state=42)
                lda.fit(tf)

                for topic_idx, topic in enumerate(lda.components_):
                    top_words_indices = topic.argsort()[:-10 - 1:-1]
                    top_words = [feature_names[i] for i in top_words_indices]
                    topic_results[f"Topic #{topic_idx + 1}"] = ", ".join(top_words)

            except ValueError as ve:
                st.warning(f"Could not perform topic modeling. Reason: {ve}")
            except Exception as e:
                 st.error(f"An error occurred during topic modeling: {e}")
        else:
            st.warning("No valid titles remaining after preprocessing for topic modeling.")
    else:
         st.warning("DataFrame is empty or lacks 'title' column for topic modeling.")
    return topic_results

# --- Saving Function ---
def save_data(df):
    saved_files = []
    # Save to CSV
    try:
        df.to_csv(CSV_FILENAME, index=False, encoding='utf-8')
        saved_files.append(CSV_FILENAME)
    except Exception as e:
        logging.error(f"Error saving data to CSV: {e}")
        st.error(f"Error saving data to {CSV_FILENAME}: {e}")

    # Save to SQLite
    try:
        conn = sqlite3.connect(DB_FILENAME)
        df.to_sql(DB_TABLE_NAME, conn, if_exists='replace', index=False)
        conn.close()
        saved_files.append(DB_FILENAME)
    except Exception as e:
        logging.error(f"Error saving data to SQLite: {e}")
        st.error(f"Error saving data to SQLite database '{DB_FILENAME}': {e}")

    return saved_files

# --- Streamlit App UI ---
st.set_page_config(layout="wide")
st.title("📰 News Scraper and Analyzer")

# Initialize session state
if 'scraped_data' not in st.session_state:
    st.session_state.scraped_data = pd.DataFrame()
if 'cleaned_data' not in st.session_state:
    st.session_state.cleaned_data = pd.DataFrame()
if 'analysis_done' not in st.session_state:
    st.session_state.analysis_done = False

# Scrape Button
if st.button("Scrape Latest News", type="primary"):
    st.session_state.analysis_done = False # Reset analysis flag
    all_raw_articles = []
    with st.spinner("Scraping news..."):
        # Currently only scrapes CNN Health
        cnn_articles = scrape_cnn_health(CNN_HEALTH_URL)
        if cnn_articles:
            for article in cnn_articles:
                article['source'] = 'CNN Health'
                all_raw_articles.extend(cnn_articles)
        else:
             st.warning("Could not scrape any articles from CNN Health.")
        # Add other sources here when fixed

    st.session_state.scraped_data = pd.DataFrame(all_raw_articles) # Store raw data if needed later
    st.success(f"Scraping finished. Found {len(all_raw_articles)} raw articles.")

    # --- Auto-trigger Cleaning and Analysis after Scraping ---
    if not st.session_state.scraped_data.empty:
        st.subheader("Data Cleaning")
        with st.spinner("Cleaning data..."):
             # Pass the raw list of dicts for caching
             cleaned_df = clean_data(all_raw_articles)
             st.session_state.cleaned_data = cleaned_df
             st.success(f"Cleaning complete. {len(cleaned_df)} articles remaining.")

        if not cleaned_df.empty:
            st.subheader("Keyword Analysis")
            with st.spinner("Analyzing keywords..."):
                keywords_to_analyze = ["Covid", "vaccine"]
                keyword_results = analyze_keywords(cleaned_df, keywords_to_analyze)
                # Store results if needed, or display directly
                st.session_state.keyword_results = keyword_results

            st.subheader("Topic Modeling")
            with st.spinner("Performing topic modeling..."):
                topic_results = perform_topic_modeling(cleaned_df.copy(), num_topics=5) # Pass copy for safety
                # Store results if needed, or display directly
                st.session_state.topic_results = topic_results

            st.subheader("Saving Data")
            with st.spinner("Saving data..."):
                saved_files = save_data(cleaned_df)
                if saved_files:
                    st.success(f"Data saved to: {', '.join(saved_files)}")

            st.session_state.analysis_done = True # Set flag when all steps complete
        else:
            st.warning("No data remaining after cleaning. Skipping analysis and saving.")
    else:
         st.warning("No data scraped. Cannot proceed with cleaning or analysis.")

# --- Display Area ---
st.divider()

if not st.session_state.cleaned_data.empty:
    st.header("Cleaned Articles")
    st.dataframe(st.session_state.cleaned_data, use_container_width=True)

    if st.session_state.analysis_done:
        st.header("Analysis Results")
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Keyword Frequency")
            if 'keyword_results' in st.session_state:
                st.write(st.session_state.keyword_results)
            else:
                st.write("Keyword analysis not performed yet.")

        with col2:
            st.subheader("Topic Modeling (Top Words)")
            if 'topic_results' in st.session_state:
                 st.write(st.session_state.topic_results)
            else:
                st.write("Topic modeling not performed yet.")
else:
    st.info("Click the 'Scrape Latest News' button to fetch and analyze data.") 