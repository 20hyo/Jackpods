# -*- coding: utf-8 -*-
import os
import requests
import json
import os
from dotenv import load_dotenv
from pymilvus import MilvusClient

load_dotenv()

try:
    from IPython.display import display, Markdown
except ImportError:
    def display(obj):
        if isinstance(obj, Markdown):
            print(obj.text)
        else:
            print(obj)
    class Markdown:
        def __init__(self, text):
            self.text = text
        def __str__(self):
            return self.text
        def _repr_markdown_(self):
            return self.text

client = MilvusClient("./rag_test17_final.db")

NEWS_COLLECTION_NAME = "rag_chunks"
PROMPT_COLLECTION_NAME = "prompt_templates_collection"

API_KEY = f"Bearer {os.getenv('SCRIPT_NAVER_API_TOKEN')}"
EMBED_REQUEST_ID = os.getenv('EMBED_TASK_ID')
GENERATION_REQUEST_ID = os.getenv('GENERATION_TASK_ID')

HEADERS_BASE = {
    "Content-Type": "application/json; charset=utf-8",
    "Authorization": API_KEY
}

def embed_texts(chunks):
    headers = HEADERS_BASE.copy()
    headers["X-NCP-CLOVASTUDIO-REQUEST-ID"] = EMBED_REQUEST_ID

    embeddings = []

    for i, chunk in enumerate(chunks):
        payload = {"text": chunk}
        try:
            res = requests.post(
                "https://clovastudio.stream.ntruss.com/v1/api-tools/embedding/clir-emb-dolphin",
                headers=headers,
                json=payload
            )
            res.raise_for_status()

            response_json = res.json()

            if "result" in response_json and "embedding" in response_json["result"]:
                embeddings.append(response_json["result"]["embedding"])
            else:
                print(f"오류: 청크 {i+1} ({chunk[:50]}...)에 대한 응답에 'result' 안에 'embedding' 키가 없습니다. 응답: {response_json}")
                continue

        except requests.exceptions.HTTPError as e:
            print(f"HTTP 오류 발생 (청크 {i+1}, {chunk[:50]}...): {e.response.status_code} - {e.response.text}")
            continue
        except requests.exceptions.RequestException as e:
            print(f"요청 오류 발생 (청크 {i+1}, {chunk[:50]}...): {e}")
            continue
        except json.JSONDecodeError:
            print(f"JSON 디코딩 오류 (청크 {i+1}, {chunk[:50]}...): API 응답이 유효한 JSON이 아닙니다.")
            continue

    if not embeddings and chunks:
        print("경고: 모든 청크에 대한 임베딩 생성에 실패했습니다. API 키, 모델, 요청 형식을 확인하세요.")

    return embeddings


def search_prompt_template(query_text, top_k=1):
    query_embedding = embed_texts([query_text])
    if not query_embedding or not query_embedding[0]:
        print("오류: 쿼리 임베딩 생성에 실패했습니다.")
        return None

    search_params = {
        "data": query_embedding,
        "collection_name": PROMPT_COLLECTION_NAME,
        "limit": top_k,
        "output_fields": ["template", "name", "description"],
    }

    try:
        res = client.search(**search_params)
        if res and res[0]:
            return res[0][0]["entity"]["template"]
        else:
            print(f"'{query_text}'에 대한 적합한 프롬프트 템플릿을 찾지 못했습니다.")
            return None
    except Exception as e:
        print(f"프롬프트 템플릿 검색 중 오류 발생: {e}")
        return None


def generate_script(news_summary, prompt_template_content):
    headers = HEADERS_BASE.copy()
    headers["X-NCP-CLOVASTUDIO-REQUEST-ID"] = GENERATION_REQUEST_ID

    prompt = f"뉴스 요약: {news_summary}\n\n위 뉴스 요약본을 바탕으로 아래 프롬프트 템플릿에 따라 SSML 형식의 대본을 작성해 주세요.\n\n프롬프트 템플릿: {prompt_template_content}"

    payload = {
        "messages": [
            {"role": "system", "content": f"""
당신은 경제 방송 대본 작가입니다. 다음 지침을 철저히 따라 SSML(Speech Synthesis Markup Language) 형식의 한국어 대본을 작성해야 합니다.
특히 각 대화의 논리적인 흐름에 따라 <segment id='...'> 태그를 사용하여 각 발화나 대화 턴을 명확하게 구분해야 합니다.
화자별 <voice>, <prosody>, <break>, <emphasis>, <sub>, <say-as> 태그를 적극적으로 활용합니다.
- **화자 구분:**
    - 사회자: <voice name="Seoyeon"><prosody rate="medium" pitch="default">내용</prosody></voice> 형식으로 작성합니다. **(pitch 속성 필수 포함)**
    - 전문가: <voice name="Injoon"><prosody rate="medium" pitch="low">내용</prosody></voice> 형식으로 작성합니다. (전문가는 사회자보다 약간 낮은 톤으로 설정) **(pitch 속성 필수 포함)**
- **휴지 (쉼):**
    - 짧은 쉼: `<break time="0.2s"/>`
    - 중간 쉼: `<break time="0.5s"/>`
    - 긴 쉼: `<break time="1s"/>`
    - **명시적인 지침:** 텍스트의 자연스러운 흐름과 의미적 단락에 맞춰 **쉼표(,) 뒤에는 `<break time="0.2s"/>`를, 마침표(.) 뒤에는 `<break time="0.5s"/>`를 기본으로 사용**하되, 문장이나 구절의 **강조, 전환, 또는 청취자의 이해를 돕기 위해 필요하다면 `<break time="0.7s"/>`나 `<break time="1s"/>`와 같은 더 긴 쉼을 적극적으로 사용**합니다. 사람이 대화하는 것처럼 자연스러운 리듬감을 구현해야 합니다. 특히, 문장 중간의 호흡을 위해 짧은 쉼을 더욱 적극적으로 활용하세요.
- **강조:**
    - 중요한 정보나 핵심 키워드는 `<emphasis level="strong">강조할 내용</emphasis>`으로 표현합니다.
    - 일반적인 강조는 `<emphasis level="moderate">강조할 내용</emphasis>`으로 표현합니다.
- **발화 속도 및 음높이:**
    - `<prosody rate="fast">빠르게</prosody>`, `<prosody rate="slow">느리게</prosody>`
    - `<prosody pitch="high">높은 음으로</prosody>`, `<prosody pitch="low">낮은 음으로</prosody>`
- **볼륨:** `<prosody volume="loud">큰 소리로</prosody>`, `<prosody volume="soft">작은 소리로</prosody>`
- **발음 대체:** 고유명사나 약어 등 발음하기 어려운 단어는 `<sub alias="일레븐랩스">ElevenLabs</sub>`와 같이 정확한 발음을 지정합니다.
- **숫자/특수어 발음:**
    - 숫자: `<say-as interpret-as="cardinal">123</say-as>` (기수), `<say-as interpret-as="digits">123</say-as>` (개별 숫자)
    - 약어: `<say-as interpret-as="characters">AI</say-as>` (알파벳 단위 발음)
- **문단/문장:** `<p>` 태그로 문단을, `<s>` 태그로 문장을 구분하면 더 정교한 제어가 가능합니다. (필수 아님, 모델의 자유도 허용)
- **세그먼트:** 각 대화의 논리적인 흐름에 따라 `<segment id="segment_id_name">` 태그를 사용하여 각 발화나 대화 턴을 구분합니다. `segment_id_name`은 해당 세그먼트의 내용을 잘 나타내는 고유한 이름을 사용합니다. **예시: 오프닝은 `intro_host`, 질문은 `host_question_1`, 답변은 `expert_answer_1` 등으로 명시하며, 각 세그먼트 ID 끝에는 순번(N)을 붙여주세요. (예: `host_question_1`, `host_question_2`, `comparison_host_1`, `risk_expert_1` 등)**
모든 응답과 대본 내용은 반드시 한국어로 작성되어야 합니다.
"""},
            {"role": "user", "content": prompt}
        ],
        "topP": 0.8,
        "temperature": 0.7,
        "maxTokens": 2000
    }

    try:
        res = requests.post(
            "https://clovastudio.stream.ntruss.com/v3/chat-completions/HCX-005",
            headers=headers,
            json=payload
        )
        res.raise_for_status()

        response_json = res.json()

        if "result" in response_json and "message" in response_json["result"] and "content" in response_json["result"]["message"]:
            return response_json["result"]["message"]["content"]
        else:
            print("CLOVA Studio 대본 생성 API 응답 오류:", response_json)
            if "status" in response_json and "message" in response_json["status"]:
                print(f"오류 메시지: {response_json['status']['message']}")
            raise ValueError("대본 생성에 실패했습니다. CLOVA Studio 응답을 확인하세요.")

    except requests.exceptions.HTTPError as e:
        print(f"HTTP 오류 발생 (대본 생성): {e.response.status_code} - {e.response.text}")
        return "대본 생성 중 HTTP 오류가 발생했습니다."
    except requests.exceptions.RequestException as e:
        print(f"요청 오류 발생 (대본 생성): {e}")
        return "대본 생성 중 요청 오류가 발생했습니다."
    except json.JSONDecodeError:
        print(f"JSON 디코딩 오류 (대본 생성): API 응답이 유효한 JSON이 아닙니다.")
        return "대본 생성 중 응답 처리 오류가 발생했습니다."


def display_script(script):
    """
    생성된 SSML 스크립트를 터미널에 직접 출력합니다.
    """
    print(script)