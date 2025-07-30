# transform/model/news.py  (예시)
from typing import List, Literal, Optional
from pydantic import BaseModel, Field

Tone = Literal["positive", "negative", "neutral"]

class NewsItem(BaseModel):
    # 기본 메타
    title: str
    link: str
    pub_date: str
    description: str                           # 핵심 요약(3~5문장)
    
    # 분류 관련
    label: int = Field(..., ge=1, le=5, description="1~5 카테고리")
    # tone: Tone                                 # positive | negative | neutral
    is_k: bool = False                         # 한국 시장 관련 여부
    is_nc: bool = True                         # 광고성 기사면 False

    # 대본 재료
    core_message: str = ""                     # 한 문장 핵심 메시지
    key_numbers: List[str] = Field(default_factory=list)   # "매출 22조", "영업이익 9조" 등
    risk: str = ""                             # 한 문장 리스크
    opportunity: str = ""                      # 한 문장 기회/의미
    entities: List[str] = Field(default_factory=list)      # 기업명/기관/산업 키워드
    quotes: List[str] = Field(default_factory=list)        # 필요 시 인용구(최대 2개)
    extra: Optional[dict] = None               # 기타 잡다한 정보 저장용(선택)
