import asyncio
import json
import pandas as pd
from crawl4ai import *
from transform.model.news import NewsItem
import os
from dotenv import load_dotenv

load_dotenv()

STAGE1_INSTRUCTION = """
[TASK]
기사 원문을 읽고, 지정한 스키마에 맞는 **단 하나의 JSON 객체만** 출력하라.
설명/주석/마크다운/코드블록/자연어 문장은 절대 금지한다.

[FIELDS]
- title        : 대표 제목 1개 (불필요한 수식어·기자명 제거)
- description  : 핵심 요약 (KOSPI/KOSDAQ·한국 시장 언급 시 그 부분을 더 구체적으로)
- pub_date     : 기사 발행일 (가능하면 원문 형식 유지)
- link         : 원문 링크
- is_k         : 한국 시장/증권 관련 여부 (true | false)
- is_nc        : 광고성 기사 여부 (true=정상 기사, false=광고성)
- label        : 숫자 1개만 사용 (1~5)
                 1=거시경제 / 2=산업·기업 / 3=금융시장 / 4=정책·규제 / 5=사회·기타

[CLASSIFICATION RULES]
- label 은 ‘무엇에 대한 기사인가?’(주제) 로 결정하며 **가장 우세한 주제 하나만** 선택한다.
  ─────────────────────────────────────────────────────────────
  1 : 거시경제
      · 국내‧국제 GDP, 물가, 고용, 무역, 경기지표 (CPI·PPI·PMI 등)
      · 중앙은행 통화정책, 금리 인상‧동결‧인하, 환율·외환보유액
      · 국제기구(IMF·OECD 등) 전망, 글로벌 경제·원자재·에너지 동향
  2 : 산업·기업
      · 개별 산업(반도체, 2차전지, 바이오 등) 트렌드, 공급망, 기술전환
      · 상장·비상장 기업 실적·가이던스, 공장 증설, 신사업 진출, M&A
      · 스타트업 투자·VC·유니콘, 기업 인터뷰·CEO 발언
  3 : 금융시장
      · 주식·채권·외환·파생·가상자산·ETF·부동산 가격·거래·수급
      · 공매도, MSCI 편입, IPO 공모가, 금리·스프레드, 크레딧·CDS
      · “◯◯지수 1% 상승” 같은 **시장** 움직임 자체가 포커스일 때
  4 : 정책·규제
      · 정부 부처·국회·금융당국 발표(법안‧예산‧규제‧세제)
      · 국제 협약(FTA·IRA·CBAM 등)·관세·무역분쟁
      · ESG·탄소배출·금융‧산업 규제, 감독강화·완화 정책
  5 : 사회·기타 경제 이슈
      · 노동시장(고용·임금·노사), 소비심리, 인구·복지, 교육·지역경제
      · 환경·ESG 동향의 **사회적 파장** 측면, 기술혁신의 부작용
      · 문화·관광·스타트업 생태계 등 거시·금융과 직접 연결되지 않는 경제 이슈
  ─────────────────────────────────────────────────────────────
- 아래와 같은 **경계 상황**에서는 주제를 우선순위로 판단한다.
  • “금리 인상 → 증시 급락” 기사 → **3 (금융시장)**  
    (시장 반응 자체가 핵심임)
  • “반도체 업황 침체로 수출 감소” 기사 → **2 (산업·기업)**  
    (산업 업황이 주제, 수출·환율 언급은 배경)
  • “정부, 탄소중립 목표 상향” 기사 → **4 (정책·규제)**  
    (정책 변화가 핵심, ESG는 부수적)

[OUTPUT FORMAT]
{
  "title": "...",
  "description": "...",
  "pub_date": "...",
  "link": "...",
  "is_k": true,
  "is_nc": true,
  "label": 2
}
"""

def get_LLM_strategy():
    return LLMExtractionStrategy(
        llm_config=LLMConfig(
            provider=os.getenv("LLM_MODEL"),
            api_token=os.getenv("Deep_Seek_API_TOKEN")
        ),
        instruction=STAGE1_INSTRUCTION,   # ← 여기만 바꾸면 됨
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
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON from extracted content: {e}. Content: {result.extracted_content[:200]}...")
                continue
            except IndexError:
                print(f"IndexError: Extracted content might be empty or in an unexpected format. Content: {result.extracted_content[:200]}...")
                continue
        return extracted
