import pandas as pd
import requests
import time
import os
from dotenv import load_dotenv

load_dotenv()

def analyze_sentiment(description):
    url = os.getenv('CLOVA_STUDIO_URL')

    headers = {
        'Authorization': f"Bearer {os.getenv('NAVER_API_TOKEN')}",
        'X-NCP-CLOVASTUDIO-REQUEST-ID': os.getenv('task_id'),
        'Content-Type': 'application/json; charset=utf-8',
        'Accept': 'text/event-stream'
    }

    data = {
        'messages': [{"role":"system","content":"한문장씩 감정분석하고 참고하여 문단을 최종적으로 감정분석해줘."},{"role": "user", "content": description}],
        "topP" : 0.8,
        "topK" : 0,
        "maxTokens" : 256,
        "temperature" : 0.5,
        "repeatPenalty" : 1.1,
        "stopBefore" : [ ],
        "seed" : 0,
        "includeAiFilters" : True
    }

    try:
        with requests.post(url, headers=headers, json=data, stream=True) as r:
            full_response = ""
            for line in r.iter_lines():
                if line:
                    decoded = line.decode("utf-8")
                    full_response += decoded
        
            print(f"Full response: {full_response}")
            time.sleep(1)  # 잠시 대기하여 응답이 완전히 수

            # 간단하게 텍스트 내 감정 키워드만 추출
            if "positive" in full_response.lower():
                return "positive"
            elif "negative" in full_response.lower():
                return "negative"
            elif "neutral" in full_response.lower():
                return "neutral"
            else:
                return "unknown"

    except Exception as e:
        print(f"오류 발생: {e}")
        return "error"

def filter_data(df):
    return df[df["is_k"] & df["is_nc"]]

def label_data(df):
    df= filter_data(df)
    df["sentiment"] = df["description"].apply(analyze_sentiment)
    return df

def into_prompt(df):
    prompts = []
    for row in df.itertuples():
        prompt = {
        "title": row.title,
        "description": row.description,
        "sentiment": row.sentiment
        }
        prompts.append(prompt)
    return prompts
