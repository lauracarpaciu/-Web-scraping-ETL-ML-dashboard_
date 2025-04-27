import requests
from bs4 import BeautifulSoup
import logging

# Set up basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

BBC_NEWS_URL = "https://www.bbc.com/news"
CNN_NEWS_URL = "https://www.cnn.com"
REUTERS_NEWS_URL = "https://www.reuters.com/"
GUARDIAN_URL = "https://www.theguardian.com/international"

def scrape_bbc_news():
    articles = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        logging.info(f"Fetching URL: {BBC_NEWS_URL}")
        # Add headers to the request
        response = requests.get(BBC_NEWS_URL, headers=headers, timeout=10)
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
        logging.info("Successfully fetched BBC News page.")

        soup = BeautifulSoup(response.content, 'html.parser')

        # --- Refined Selector Logic ---
        # Try finding headlines using more specific common patterns first
        # Look for h2/h3 tags with an immediate sibling or parent 'a' tag, common in promo blocks
        headlines = soup.select('h3 > a, h2 > a') # Find direct links within h2/h3

        # Fallback: Look for links within common container class patterns (e.g., 'promo', 'media-list__item')
        if not headlines:
            logging.info("Initial selector failed, trying container-based selectors.")
            headlines = soup.select('.gs-c-promo-heading__title, .nw-o-link-split__text') # Selectors observed on BBC
            # Extract the parent 'a' tag if the text element was selected
            processed_headlines = []
            for h in headlines:
                link_tag = h.find_parent('a')
                if link_tag:
                    processed_headlines.append(link_tag)
                elif h.name == 'a': # If the selector already grabbed the link
                     processed_headlines.append(h)
            headlines = processed_headlines

        # Previous selectors as further fallbacks (might be less reliable)
        if not headlines:
             logging.info("Second selector failed, trying older selectors.")
             headlines = soup.find_all('a', class_=lambda x: x and 'headline' in x.lower())
        if not headlines:
            logging.info("Third selector failed, trying data-entityid selector.")
            headlines = soup.select('div[data-entityid] h3 a')
        # --- End Refined Selector Logic ---

        logging.info(f"Found {len(headlines)} potential headline elements after trying selectors.")

        seen_urls = set()
        for headline in headlines:
            # Ensure headline is a tag before accessing attributes/text
            if not hasattr(headline, 'text'): continue
            
            title = headline.text.strip()
            url = headline.get('href')

            # Ensure we have both title and URL
            if title and url:
                # Make URL absolute if relative
                if url.startswith('/'):
                    url = f"https://www.bbc.com{url}"
                elif not url.startswith('http'):
                    # Skip potential javascript or other non-http links
                    continue
                    
                # Basic filtering: Check if it looks like a news article URL and avoid duplicates
                # Allowing links that start with bbc.com or bbc.co.uk domain
                if ('bbc.com/news/' in url or 'bbc.co.uk/news/' in url) and url not in seen_urls:
                     articles.append({'title': title, 'url': url})
                     seen_urls.add(url)
                     logging.debug(f"Added article: {title} - {url}")

    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching BBC News: {e}")
    except Exception as e:
        logging.error(f"An error occurred during BBC scraping: {e}", exc_info=True) # Add traceback info

    logging.info(f"Scraped {len(articles)} articles from BBC News.")
    return articles

def scrape_cnn_news():
    articles = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        logging.info(f"Fetching URL: {CNN_NEWS_URL}")
        response = requests.get(CNN_NEWS_URL, headers=headers, timeout=15) # Increased timeout slightly
        response.raise_for_status()
        logging.info("Successfully fetched CNN page.")

        soup = BeautifulSoup(response.content, 'html.parser')

        # Selectors for CNN (these often change, might need inspection/refinement)
        # Look for links within common headline containers or specific data attributes
        # Example: Links with data-link-type="article"
        headlines = soup.select('a[data-link-type="article"]')

        # Fallback: Look for headlines text within specific span classes, then find parent link
        if not headlines:
             logging.info("Initial CNN selector failed, trying text-based selector.")
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
            # Extract title: try specific headline span first, then link text
            title_span = headline.find('span[data-editable="headline"]')
            title = title_span.text.strip() if title_span else headline.text.strip()
            url = headline.get('href')

            if title and url:
                 # Make URL absolute if relative
                if url.startswith('/'):
                    url = f"https://www.cnn.com{url}"
                elif not url.startswith('http'):
                    continue # Skip non-http links
                
                # Filter for article URLs (basic check) and avoid duplicates
                # CNN articles often follow /YYYY/MM/DD/ pattern
                if url.startswith("https://www.cnn.com/") and url not in seen_urls:
                    # A simple check if it looks like an article path
                    path_parts = url.split('cnn.com/')[-1].split('/')
                    if len(path_parts) > 3: # e.g., YYYY/MM/DD/category/title or section/article-slug
                         articles.append({'title': title, 'url': url})
                         seen_urls.add(url)
                         logging.debug(f"Added CNN article: {title} - {url}")

    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching CNN: {e}")
    except Exception as e:
        logging.error(f"An error occurred during CNN scraping: {e}", exc_info=True)

    logging.info(f"Scraped {len(articles)} articles from CNN.")
    return articles

def scrape_reuters_news():
    articles = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        logging.info(f"Fetching URL: {REUTERS_NEWS_URL}")
        response = requests.get(REUTERS_NEWS_URL, headers=headers, timeout=15)
        response.raise_for_status()
        logging.info("Successfully fetched Reuters page.")

        soup = BeautifulSoup(response.content, 'html.parser')

        # Selectors for Reuters (based on observed data-testid attributes)
        # Try finding links directly with relevant testids
        headlines = soup.select('a[data-testid*="Heading"], a[data-testid*="Link"], a[data-testid*="Title"]')

        # Fallback: Find story containers and then the link within them
        if not headlines:
            logging.info("Initial Reuters selector failed, trying container-based selector.")
            story_containers = soup.select('div[data-testid*="StoryCard"], article[data-testid]')
            processed_headlines = []
            for container in story_containers:
                link = container.find('a', href=True)
                if link:
                    processed_headlines.append(link)
            headlines = processed_headlines

        logging.info(f"Found {len(headlines)} potential headline elements for Reuters.")
        
        seen_urls = set()
        for headline in headlines:
            title = headline.text.strip()
            url = headline.get('href')

            if title and url:
                # Make URL absolute if relative
                if url.startswith('/'):
                    url = f"https://www.reuters.com{url}"
                elif not url.startswith('http'):
                    continue # Skip non-http links

                # Filter for article URLs (e.g., containing /world/, /business/, /technology/) and avoid duplicates
                # Basic check for common Reuters article paths
                if url.startswith("https://www.reuters.com/") and any(s in url for s in ['/world/', '/business/', '/legal/', '/markets/', '/technology/', '/lifestyle/', '/sports/', '/graphics/']) and url not in seen_urls:
                    articles.append({'title': title, 'url': url})
                    seen_urls.add(url)
                    logging.debug(f"Added Reuters article: {title} - {url}")

    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching Reuters: {e}")
    except Exception as e:
        logging.error(f"An error occurred during Reuters scraping: {e}", exc_info=True)

    logging.info(f"Scraped {len(articles)} articles from Reuters.")
    return articles

def scrape_guardian_news():
    articles = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        logging.info(f"Fetching URL: {GUARDIAN_URL}")
        # Using the international edition URL
        response = requests.get(GUARDIAN_URL, headers=headers, timeout=15)
        response.raise_for_status()
        logging.info("Successfully fetched The Guardian page.")

        soup = BeautifulSoup(response.content, 'html.parser')

        # Selectors for The Guardian (based on common class names)
        # Try finding links within elements with class containing 'fc-item__link' or 'js-headline-text'
        headlines = soup.select('.fc-item__link, a[data-link-name*="headline"]')

        # Fallback: Look for specific headline text elements and get parent link
        if not headlines:
            logging.info("Initial Guardian selector failed, trying js-headline-text.")
            headline_texts = soup.select('.js-headline-text')
            processed_headlines = []
            for ht in headline_texts:
                link_tag = ht.find_parent('a')
                if link_tag:
                    processed_headlines.append(link_tag)
            headlines = processed_headlines
            
        logging.info(f"Found {len(headlines)} potential headline elements for The Guardian.")

        seen_urls = set()
        for headline in headlines:
            # Extract title preferentially from '.js-headline-text' if available within the link
            title_elem = headline.find('.js-headline-text')
            title = title_elem.text.strip() if title_elem else headline.text.strip()
            url = headline.get('href')

            if title and url:
                # The Guardian usually uses absolute URLs, but check just in case
                if not url.startswith('http'):
                    # Simple check if it's a protocol-relative URL (starts with //)
                    if url.startswith('//'):
                         url = f"https:{url}"
                    # Or if it's a relative path (less common on Guardian main pages)
                    elif url.startswith('/'):
                         url = f"https://www.theguardian.com{url}"
                    else:
                        continue # Skip other non-standard URLs

                # Filter for article URLs (usually contain date path YYYY/mon/DD) and avoid duplicates
                # Only add if it looks like a valid Guardian article URL and hasn't been seen
                if url.startswith("https://www.theguardian.com/") and url not in seen_urls:
                    # Basic check: Guardian articles often have a structure like /section/YYYY/mon/DD/slug
                    if len(url.split('/')) > 5: 
                        articles.append({'title': title, 'url': url})
                        seen_urls.add(url)
                        logging.debug(f"Added Guardian article: {title} - {url}")

    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching The Guardian: {e}")
    except Exception as e:
        logging.error(f"An error occurred during Guardian scraping: {e}", exc_info=True)

    logging.info(f"Scraped {len(articles)} articles from The Guardian.")
    return articles

if __name__ == "__main__":
    # bbc_articles = scrape_bbc_news() # Commented out for now
    cnn_articles = scrape_cnn_news()
    reuters_articles = scrape_reuters_news()
    guardian_articles = scrape_guardian_news()

    # TODO: Process and combine articles
    # if bbc_articles:
    #     print("\n--- BBC News Articles ---")
    #     for article in bbc_articles:
    #         print(f"Title: {article['title']}\nURL: {article['url']}\n")
    # else:
    #     print("\nCould not scrape any articles from BBC News.")
        
    if cnn_articles:
        print("\n--- CNN Articles ---")
        for article in cnn_articles:
            print(f"Title: {article['title']}\nURL: {article['url']}\n")
    else:
        print("\nCould not scrape any articles from CNN.")
        
    if reuters_articles:
        print("\n--- Reuters Articles ---")
        for article in reuters_articles:
            print(f"Title: {article['title']}\nURL: {article['url']}\n")
    else:
        print("\nCould not scrape any articles from Reuters.")
        
    if guardian_articles:
        print("\n--- The Guardian Articles ---")
        for article in guardian_articles:
            print(f"Title: {article['title']}\nURL: {article['url']}\n")
    else:
        print("\nCould not scrape any articles from The Guardian.") 