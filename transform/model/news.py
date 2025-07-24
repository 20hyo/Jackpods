from pydantic import BaseModel

class NewsItem(BaseModel):

    title: str
    link: str
    description: str
    pub_date: str
    is_k: bool = False
    is_nc: bool = False
    label: str = "0"  # Default to '0' if not specified