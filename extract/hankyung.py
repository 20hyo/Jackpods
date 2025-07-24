from datetime import datetime,time, date
import pytz
import feedparser
import requests

def collect_parse_hankyung_feed(date:datetime.date):
    """
    Collects and parses the Hankyung RSS feed.

    Args:
        feed_url (date) : The date for which to collect the feed.

    Returns:
        list: A list of dictionaries containing parsed feed entries.

    """

    kst=pytz.timezone('Asia/Seoul')
    start = datetime.combine(date, time(9, 0, 0)).replace(tzinfo=kst)
    end = datetime.combine(date, time(15, 30, 0)).replace(tzinfo=kst)

    
    link='https://www.hankyung.com/feed/finance'
    res= requests.get(link)
    res.encoding = 'utf-8'
    html = res.text

    feed = feedparser.parse(html)
    entries = []

    for entry in feed.entries:
        published_time = datetime(*entry.published_parsed[:6], tzinfo=pytz.utc).astimezone(kst)
        #if start <= published_time <= end:
        entries.append({
            'title': entry.title,
            'link': entry.link,
            'published': published_time,
        })
            
    print(f"Collected {len(entries)} entries from Hankyung feed for {date.strftime('%Y-%m-%d')}")

    return entries