import feedparser
import pandas as pd
from datetime import datetime, timedelta
import ssl
from bs4 import BeautifulSoup
import warnings
import concurrent.futures
import re
import requests

# Django ile ilgili importlar
from django.core.management.base import BaseCommand
from news.models import News

warnings.filterwarnings("ignore")

URL = "https://www.deeplearning.ai/the-batch/"

# Configure SSL once at the module level
if hasattr(ssl, '_create_unverified_context'):
    ssl._create_default_https_context = ssl._create_unverified_context

def extract_date(date_str):
    """Extract date from various formats using regex patterns"""
    try:
        # Try different patterns to match various date formats
        
        # Pattern 1: Standard RFC format like "Mon, 14 Apr 2025 10:00:00 GMT"
        pattern1 = r'(?:\w+,\s+)?(\d{1,2}\s+\w{3}\s+\d{4})'
        match = re.search(pattern1, date_str)
        if match:
            date_str = match.group(1)
            return pd.to_datetime(date_str, format='%d %b %Y')
        
        # Pattern 2: Simple format like "14 Apr 2025"
        pattern2 = r'(\d{1,2}\s+\w{3}\s+\d{4})'
        match = re.search(pattern2, date_str)
        if match:
            return pd.to_datetime(match.group(1), format='%d %b %Y')
        
        # Pattern 3: ISO format like "2025-04-14"
        pattern3 = r'(\d{4}-\d{2}-\d{2})'
        match = re.search(pattern3, date_str)
        if match:
            return pd.to_datetime(match.group(1))
        
        # Pattern 4: Format like "Mar 12, 2025"
        pattern4 = r'(\w{3}\s+\d{1,2},\s+\d{4})'
        match = re.search(pattern4, date_str)
        if match:
            return pd.to_datetime(match.group(1), format='%b %d, %Y')
        
        # If none of the patterns match, return original parsed date
        return pd.to_datetime(date_str)
    except:
        # If all else fails, return NaT
        return pd.NaT

def clean_html(text):
    """Clean HTML tags from text"""
    try:
        soup = BeautifulSoup(text, "html.parser")
        return soup.get_text()
    except Exception as e:
        print(f"Error cleaning HTML: {e}")
        return text

def extract_image_url(entry, description):
    """Extract image URL from RSS entry if available"""
    try:
        # Check for media:content
        if hasattr(entry, 'media_content') and entry.media_content:
            for media in entry.media_content:
                if isinstance(media, dict) and 'url' in media:
                    return media['url']
        
        # Check for media:thumbnail
        if hasattr(entry, 'media_thumbnail') and entry.media_thumbnail:
            for media in entry.media_thumbnail:
                if isinstance(media, dict) and 'url' in media:
                    return media['url']
        
        # Check for enclosures
        if hasattr(entry, 'enclosures') and entry.enclosures:
            for enclosure in entry.enclosures:
                if isinstance(enclosure, dict) and 'url' in enclosure and enclosure.get('type', '').startswith('image/'):
                    return enclosure['url']
        
        # Try to extract from description using BeautifulSoup
        if description:
            soup = BeautifulSoup(description, "html.parser")
            
            # First, check meta tags for twitter:image
            meta_img = soup.find('meta', attrs={'name': 'twitter:image'})
            if meta_img and meta_img.has_attr('content'):
                return meta_img['content']
            
            # Then check for regular img tags
            img_tag = soup.find('img')
            if img_tag and img_tag.has_attr('src'):
                return img_tag['src']
            
            # Try to extract image URL from HTML
            img_match = re.search(r'<img[^>]+src=[\'"]([^\'"]+)[\'"]', description)
            if img_match:
                return img_match.group(1)
        
        # No image found
        return None
    except Exception as e:
        print(f"Error extracting image URL: {e}")
        return None

def fetch_single_feed(link_source_tuple):
    """Fetch a single RSS feed and return its entries"""
    link, source = link_source_tuple
    entries = {"Title": [], "Link": [], "Published": [], "Description": [], "Source": [], "Image": []}
    
    try:
        feed = feedparser.parse(link)
        
        for entry in feed.entries:
            title = entry.get("title", "No Title")
            link = entry.get("link", "No Link")
            published = entry.get("published", "No Date")
            description = entry.get("description", "No Description")
            
            # Extract image URL
            image_url = extract_image_url(entry, description)
            
            entries["Title"].append(title)
            entries["Link"].append(link)
            entries["Published"].append(published)
            entries["Description"].append(description)
            entries["Source"].append(source)
            entries["Image"].append(image_url)  # Add image URL
            
    except Exception as e:
        print(f"Error fetching {link}: {e}")
    
    return entries

def fetch_feed(links):
    """Fetch multiple RSS feeds in parallel"""
    all_entries = {"Title": [], "Link": [], "Published": [], "Description": [], "Source": [], "Image": []}
    
    # Use ThreadPoolExecutor to fetch feeds in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_to_link = {executor.submit(fetch_single_feed, (link, source)): (link, source) 
                         for link, source in links.items()}
        
        for future in concurrent.futures.as_completed(future_to_link):
            link, source = future_to_link[future]
            try:
                result = future.result()
                # Merge results into all_entries
                for key in all_entries:
                    all_entries[key].extend(result[key])
            except Exception as e:
                print(f"Exception for {link}: {e}")
    
    # Create a DataFrame from all entries
    df = pd.DataFrame(all_entries)
    return df

def scrape_the_batch_articles():
    all_entries = {"Title": [], "Link": [], "Published": [], "Description": [], "Source": [], "Image": []}
    
    try:
        res = requests.get(URL)
        soup = BeautifulSoup(res.text, "html.parser")

        articles = soup.find_all("article")

        for article in articles:
            # Link
            link_tag = article.find("a", href=True)
            link = "https://www.deeplearning.ai" + link_tag["href"] if link_tag else "#"

            # Title
            title_tag = article.find("h2")
            title = title_tag.get_text(strip=True) if title_tag else "No title"

            # Summary
            summary_tag = article.find("div", class_="text-sm")
            summary = summary_tag.get_text(strip=True) if summary_tag else ""

            # Date (based on div with specific class)
            date_tag = article.find("div", class_="text-slate-500")
            date_str = date_tag.get_text(strip=True) if date_tag else ""
            
            # Image
            img_tag = article.find("img")
            image_url = img_tag["src"] if img_tag and img_tag.has_attr("src") else None

            try:
                parsed_date = datetime.strptime(date_str, "%b %d, %Y")
            except Exception as e:
                parsed_date = None

            if parsed_date:
                all_entries["Title"].append(title)
                all_entries["Description"].append(summary)
                all_entries["Link"].append(link)
                all_entries["Published"].append(date_str)
                all_entries["Source"].append("deeplearning.ai")
                all_entries["Image"].append(image_url)
        
        return pd.DataFrame(all_entries)
    except Exception as e:
        print(f"Error scraping The Batch: {e}")
        return pd.DataFrame()

def extract_and_clean_data(df):
    """Process and clean the feed data"""
    if df.empty:
        return df
        
    try:
        # Apply the custom date extraction function
        df['date'] = df['Published'].apply(extract_date)
        
        # Drop rows with invalid dates
        df = df.dropna(subset=['date'])
        
        # Drop the original 'Published' column
        df.drop(columns=['Published'], inplace=True)
        
        # Filter for the last 30 days (increased from 7 for more content)
        today = datetime.now()
        thirty_days_ago = today - timedelta(days=30)
        df_filtered = df[(df['date'] >= thirty_days_ago) & (df['date'] <= today)]
        
        # Sort by date in descending order
        df_filtered = df_filtered.sort_values(by='date', ascending=False)
        
        # Clean HTML and limit description length in one step
        df_filtered['Description'] = df_filtered['Description'].apply(
            lambda x: clean_html(x)[:500].replace("\n", "")
        )
        
        return df_filtered
        
    except Exception as e:
        print(f"An error occurred while processing the data: {e}")
        return pd.DataFrame()
    


class Command(BaseCommand):
    help = 'RSS kaynaklarından en son yapay zeka haberlerini çeker ve veritabanına kaydeder.'

    def handle(self, *args, **kwargs):
        self.stdout.write('Haberler çekiliyor...')
        
        # Orijinal main() fonksiyonunuzdaki mantık buraya gelecek
        links = {
            "https://bair.berkeley.edu/blog/feed.xml": "The Berkeley Artificial Intelligence Research Blog",
            "https://feeds.feedburner.com/nvidiablog": "NVDIA Blog",
            "https://www.microsoft.com/en-us/research/feed/": "Microsoft Research",
            "https://www.sciencedaily.com/rss/computers_math/artificial_intelligence.xml": "Science Daily",
            "https://research.facebook.com/feed/": "META Research",
            "https://openai.com/news/rss.xml": "OpenAI News",
            "https://deepmind.google/blog/feed/basic/": "Google DeepMind Blog",
            "https://news.mit.edu/rss/topic/artificial-intelligence2": "MIT News - Artificial intelligence",
            "https://www.technologyreview.com/topic/artificial-intelligence/feed": "MIT Technology Review - Artificial intelligence",
            "https://www.wired.com/feed/tag/ai/latest/rss": "Wired: Artificial Intelligence Latest",
            "https://raw.githubusercontent.com/Olshansk/rss-feeds/refs/heads/main/feeds/feed_ollama.xml": "Ollama Blog",
            "https://newsroom.ibm.com/press-releases-artificial-intelligence?pagetemplate=rss": "IBM - Announcements (Artificial intelligence)",
            "https://www.amazon.science/index.rss" : "Amazon Science"
        }
        
        # fetch_feed fonksiyonunuzu buraya uyarlayın
        # Bu fonksiyon artık bir DataFrame döndürmek yerine doğrudan kayıt yapacak

        for link, source in links.items():
            feed = feedparser.parse(link)
            for entry in feed.entries:
                # Haberin linkine göre veritabanında olup olmadığını kontrol et
                if News.objects.filter(link=entry.get("link")).exists():
                    continue # Eğer haber zaten varsa, bir sonrakine geç

                try:
                    title = entry.get("title", "No Title")
                    link = entry.get("link", "No Link")
                    published = entry.get("published", "No Date")
                    description = entry.get("description", "No Description")

                    image_url = extract_image_url(entry, description)

                    News.objects.create(
                        title=title,
                        link=link,
                        description=clean_html(description),
                        source=source,
                        published=pd.to_datetime(extract_date(published)), 
                        image_url=image_url
                    )
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'Hata: {entry.get("link")} kaydedilemedi - {e}'))

        self.stdout.write(self.style.SUCCESS('Haberler başarıyla veritabanına kaydedildi.'))