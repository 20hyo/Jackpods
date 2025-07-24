# main.py

from datetime import datetime,timedelta

import requests
from extract.hankyung import collect_parse_hankyung_feed
from extract.mk_collector import collect_parse_mk_feed  
import pytz
from transform.summarizer import run
from transform.model.news import NewsItem
from transform.createPrompt import label_data, into_prompt
import asyncio
import pandas as pd

def main():
    kst=pytz.timezone('Asia/Seoul')
    now = datetime.now(kst).date()- timedelta(days=1)
    # news_list = collect_parse_mk_feed(now)
    # #news_list = collect_parse_hankyung_feed(now)

   
    # for news in news_list:
    #     print(f"[{news['published']}] {news['title']}")
    #     print(f"📎 {news['link']}\n")

    # links = list(set(news["link"] for news in news_list))

    # results = asyncio.run(run(links, "mk"))
    # print(f"✅ 수집된 기사 개수: {len(results)}\n")

    # #df = pd.DataFrame([item.dict() for item in results])
    # df = pd.DataFrame(results)
    # df.to_csv(f"news_summary_{now}.csv", index=False)
    df= pd.read_csv(f"news_summary_{now}.csv")
    df_1=label_data(df)
    prompts = into_prompt(df_1)
    print(prompts[:5])  # Print first 5 prompts for verification
    df_1.to_csv(f"news_summary_labeled_{now}.csv", index=False)


if __name__ == "__main__":
    main()
    # import requests
    