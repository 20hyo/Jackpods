import asyncio
import json
import pandas as pd
from crawl4ai import *
from transform.model.news import NewsItem
import os
from dotenv import load_dotenv

load_dotenv()

def get_LLM_strategy():

    return LLMExtractionStrategy(
    llm_config=LLMConfig(
        provider=os.getenv("LLM_MODEL"),
        api_token=os.getenv("DEEPSEEK_API_TOKEN")
    ),
    instruction=(
        "title 필드엔 기사 제목 중 가장 대표되는 것 **하나만** 담아줘.\n"
        "description 필드엔 기사 핵심을 좀 자세하게 요약하고, 특히 한국 시장(KOSPI/KOSDAQ)와 관련된 내용이 있다면 ,한국 시장(KOSPI/KOSDAQ) 내용 중심으로 작성해줘.\n"
        "Kospi/Kosdaq 또는 한국 시장,한국 증권과 관련 되어 있다면 is_k 필드를 True로 해줘\n"
        "기사가 증권사 혹은 다른 기업을 광고하고 있는 광고성 기사가 맞다면 is_nc 필드를 False로 해주고 아니면 True 로 해줘\n"
        "불필요한 수식어·기자명은 제거.\n"
        "모든 필드는 문자열(string) 하나씩만 포함해야 합니다."
    ),
    extract_type="schema",
    schema=NewsItem.model_json_schema(),
    verbose=True,
)
def get_selector(newsType: str):
    if newsType == "mk":
        return ["div.news_cnt_detail_wrap", "div.ad_wrap"]
    elif newsType == "hankyung":
        return ["div.article_body"]
    else:
        raise ValueError(f"Unknown news type: {newsType}")

async def fetch(crawler: AsyncWebCrawler, newsType: str, links: list[str], e_s: LLMExtractionStrategy):

    selector_options = get_selector(newsType)

    try:
        results = await crawler.arun_many(
            urls=links,
            config=CrawlerRunConfig(
            css_selector=selector_options[0],             # 본문만 추출
            excluded_tags=selector_options[1:],           # 광고 요소는 제거
            remove_overlay_elements=True,                 # 팝업 제거 (선택)
            extraction_strategy=e_s,                      # 짧은 블록은 필터링 (선택)
            verbose=True
            )
        )

        return results
        
    except Exception as e:
        print(f"Error fetching {links}: {e}")

async def run(links: list, newsType: str):
    async with AsyncWebCrawler() as crawler:
        e_s = get_LLM_strategy()
        results = await fetch(crawler, newsType, links, e_s)
        extracted = []
        for result in results:
            try:
                data = json.loads(result.extracted_content)
                data = data[0][0] if isinstance(data[0], list) else data[0]
                extracted.append(data)
            except Exception as e:
                print(f"❌ Error parsing result from {result.url}: {e}")
        
        return extracted



