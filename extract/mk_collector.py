from datetime import datetime, date, time
import pytz
import feedparser
import requests

def collect_parse_mk_feed(date: date):
    """
    Collects and parses the MK News RSS feed.

    Args:
        date (date): The date for which to collect the feed.

    Returns:
        list: A list of dictionaries containing parsed feed entries.
    """
    kst = pytz.timezone('Asia/Seoul')
    start = datetime.combine(date, time(14, 0, 0)).replace(tzinfo=kst)
    end = datetime.combine(date, time(14, 45, 0)).replace(tzinfo=kst)

    link = 'https://www.mk.co.kr/rss/50200011/'
    res = requests.get(link)
    res.encoding = 'utf-8'
    html = res.text

    feed = feedparser.parse(html)
    entries = []

    for entry in feed.entries:
        published_time = datetime(*entry.published_parsed[:6], tzinfo=pytz.utc).astimezone(kst)
        if start <= published_time <= end:
            entries.append({
            'title': entry.title,
            'link': entry.link,
            'published': published_time,
            })

    print(f"Collected {len(entries)} entries from MK News feed for {date.strftime('%Y-%m-%d')}")

    return entries