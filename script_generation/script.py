# -*- coding: utf-8 -*-
import os
import json
import requests
import time
from dotenv import load_dotenv
from pymilvus import MilvusClient

load_dotenv()

# =========[ Milvus / API 공통 설정 ]=========
MILVUS_PROMPT_PATH = "./Plain_template.db"
NEWS_COLLECTION_NAME = "rag_chunks"
PROMPT_COLLECTION_NAME = "prompt_templates_collection"

client = MilvusClient(MILVUS_PROMPT_PATH)

# CLOVA / Embedding
API_KEY               = f"Bearer {os.getenv('SCRIPT_NAVER_API_TOKEN')}"
EMBED_REQUEST_ID      = os.getenv('EMBED_TASK_ID')

# CLOVA / Chat (분석용 & 생성용 각각 Request-ID만 다르게)
SCRIPT_ANALYZE_RE_ID    = os.getenv('SCRIPT_ANALYZE_RE_ID')     # 분석
SCRIPT_REQUEST_ID   = os.getenv('SCRIPT_REQUEST_ID')            # 대본 생성
SSML_REQUEST_ID  = os.getenv('SSML_REQUEST_Id')                 # ssml변환


HEADERS_BASE = {
    "Content-Type": "application/json; charset=utf-8",
    "Authorization": API_KEY
}

PROMPT_DIR = os.path.join(os.path.dirname(__file__), "prompts")

def load_prompt(file_name: str) -> str:
    """prompts/ 폴더에서 프롬프트 텍스트 읽어오기"""
    path = os.path.join(PROMPT_DIR, file_name)
    with open(path, encoding="utf-8") as f:
        return f.read()

# ---------- [ 시스템 프롬프트 로드 ] ----------
ANALYZE_SYSTEM = load_prompt("analyze_system.txt")      # 분석용
DRAFT_SYSTEM  = load_prompt("draft_system.txt")       # Stage A
SSML_SYSTEM   = load_prompt("ssml_system.txt")        # Stage B
# ------------------------------------------------

def store_combined_summary_in_milvus(combined_summary: str, label_id: str, tone: str):
    """
    요약문을 통합하고, 임베딩하여 rag_chunks 컬렉션에 저장합니다.
    """
    emb = embed_texts([combined_summary])
    if not emb:
        print("임베딩 실패. combined_summary를 Milvus에 저장할 수 없습니다.")
        return False

    data_to_insert = [
        {
            "vector": emb[0],  # embed_texts가 임베딩 목록을 반환한다고 가정
            "combined_summary": combined_summary,
            "label_id": label_id,
            "tone": tone
            # 고유 ID를 추가할 수도 있습니다. 예: "id": str(uuid.uuid4())
        }
    ]
    try:
        # NEWS_COLLECTION_NAME이 올바른 스키마(vector, combined_summary, label_id, tone)로 초기화되었는지 확인
        # 이 설정 부분은 일반적으로 이 함수 외부에서 Milvus 컬렉션 생성 시 한 번만 수행됩니다.
        # 예시 스키마:
        # fields = [
        #     FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=1024),
        #     FieldSchema(name="combined_summary", dtype=DataType.VARCHAR, max_length=65535),
        #     FieldSchema(name="label_id", dtype=DataType.VARCHAR, max_length=128),
        #     FieldSchema(name="tone", dtype=DataType.VARCHAR, max_length=128)
        # ]
        # schema = CollectionSchema(fields, description="뉴스 요약을 위한 RAG 청크")
        # client.create_collection(NEWS_COLLECTION_NAME, schema) if not client.has_collection(NEWS_COLLECTION_NAME) else None

        client.insert(
            collection_name=NEWS_COLLECTION_NAME,
            data=data_to_insert
        )
        print(f"레이블 '{label_id}', 톤 '{tone}'에 대한 통합 요약이 Milvus에 저장되었습니다.")
        return True
    except Exception as e:
        print(f"[store_combined_summary_in_milvus] 오류: {e}")
        return False

# =========[ Embedding ]=========
def embed_texts(chunks):
    """
    CLOVA 임베딩 호출
    """
    headers = HEADERS_BASE.copy()
    headers["X-NCP-CLOVASTUDIO-REQUEST-ID"] = EMBED_REQUEST_ID

    embs = []
    for i, chunk in enumerate(chunks):
        payload = {"text": chunk}
        try:
            res = requests.post("https://clovastudio.stream.ntruss.com/v1/api-tools/embedding/clir-emb-dolphin", headers=headers, json=payload)
            res.raise_for_status()
            js = res.json()
            embs.append(js["result"]["embedding"])
        except Exception as e:
            print(f"[embed_texts] ERROR on chunk {i}: {e}")
    return embs


def search_prompt_template(query_text, top_k=1):
    """
    query_text 임베딩 → Milvus에서 템플릿 검색
    return: 가장 유사한 템플릿 레코드(dict) or None
    """
    qemb = embed_texts([query_text])
    if not qemb:
        print("임베딩 실패.")
        return None

    try:
        res = client.search(
            data=qemb,
            collection_name=PROMPT_COLLECTION_NAME,
            limit=top_k,
            output_fields=["template", "name", "description", "label_id", "tone"]
        )
        if not res or not res[0]:
            return None
        top = res[0][0]["entity"]
        return {
            "template": top.get("template", ""),
            "name": top.get("name", ""),
            "description": top.get("description", ""),
            "label_id": str(top.get("label_id", "")),
            "tone": top.get("tone", "")
        }
    except Exception as e:
        print(f"[search_prompt_template] ERRR: {e}")
        return None


def call_clova_chat(
        messages,
        request_id,
        effort="medium",
        max_tokens=2000,
        temperature=0.7,
        top_p=0.8,
        top_k=0,
        repeat_penalty=1.1,
        seed=0,
        model_id="HCX-007"):
    
    time.sleep(10)

    headers = HEADERS_BASE.copy()
    headers["X-NCP-CLOVASTUDIO-REQUEST-ID"] = request_id

    payload = {
        "messages": messages,
        "effort" : effort,
        "maxCompletionTokens": max_tokens,
        "temperature": temperature,
        "topP": top_p,
        "topK": top_k,
        "repeatPenalty": repeat_penalty,
        "seed": seed,
        # 필요 시 stopBefore / includeAiFilters 등 추가
    }

    try:
        url = f"https://clovastudio.stream.ntruss.com/v3/chat-completions/{model_id}"
        r = requests.post(url, headers=headers, json=payload, timeout=60)
        r.raise_for_status()
        js = r.json()
        return js["result"]["message"]["content"]
    except Exception as e:
        print(f"[call_clova_chat] ERROR: {e}")
        return ""

def analyze_and_plan(combined_summary:str, label_kor:str, tone:str):
    """
    뉴스 합본과 메타정보(라벨, 톤)를 바탕으로 JSON 계획을 생성합니다.
    """
    user_prompt = f"""[CATEGORY]: {label_kor}
[TONE]: {tone}
[NEWS_SUMMARY]:
{combined_summary}
"""
    messages = [
        {"role":"system","content": ANALYZE_SYSTEM},
        {"role":"user",  "content": user_prompt}
    ]
    raw = call_clova_chat(messages, SCRIPT_ANALYZE_RE_ID, effort="high", max_tokens=20480, temperature=0.2)
    plan = {"raw_output": raw} # 파싱 실패 시 원본 출력을 초기화
    try:
        parsed_plan = json.loads(raw)
        # 중요 필드가 누락된 경우 기본 유효성 검사/기본값 설정
        plan["core_message"] = parsed_plan.get("core_message", "핵심 메시지를 찾을 수 없습니다.")
        plan["key_points"] = parsed_plan.get("key_points", [])
        plan["key_numbers"] = parsed_plan.get("key_numbers", [])
        plan["risk"] = parsed_plan.get("risk", "")
        plan["opportunity"] = parsed_plan.get("opportunity", "")
        plan["chapters"] = parsed_plan.get("chapters", [])
        # 예상되는 다른 필드와 해당 기본값을 추가합니다.
    except json.JSONDecodeError:
        print("[analyze_and_plan] JSON 파싱 실패. 원문 포함 반환.")
        # 파싱이 완전히 실패하면, raw 텍스트에서 일부 기본 정보를 추출하거나
        # 일반적인 기본값을 사용하도록 시도할 수 있습니다.
        # 단순화를 위해 현재는 원본 출력만 제공됩니다.
    except Exception as e:
        print(f"[analyze_and_plan] 예상치 못한 오류: {e}. 원문 포함 반환.")

    print("### DEBUG PLAN ###\n",
        json.dumps(plan, indent=2, ensure_ascii=False))
    
    return plan


def build_draft_prompt(summary, plan, template_text, label, tone):
    return (
        f"[CONTEXT_SUMMARY]\n{summary}\n\n"
        f"[LABEL]: {label}\n[TONE]: {tone}\n\n"
        "[PLAN_JSON]\n" + json.dumps(plan, ensure_ascii=False, indent=2) + "\n\n"
        "[CHAPTER_CONTENT_GUIDE]\n" + template_text + "\n\n"
        "[INSTRUCTION]\n"
        "가이드를 따르되 SSML 태그는 절대 쓰지 말고 구어체 대본만 작성."\
    )

def generate_draft(summary, label, tone, template_text):
    plan = analyze_and_plan(summary, label, tone)
    prompt = build_draft_prompt(summary, plan, template_text, label, tone)
    msgs = [
        {"role": "system", "content": DRAFT_SYSTEM},
        {"role": "user", "content": prompt},
    ]
    return call_clova_chat(msgs, SCRIPT_REQUEST_ID, effort="high", max_tokens=32768, temperature=0.55, model_id="HCX-007")

# =========  Stage B – SSML 변환  ============================================

def build_ssml_prompt(draft_script, tone):
    return (
        "[PLAIN_SCRIPT]\n" + draft_script + "\n\n"
        "[TONE_HINT]\n" + tone + "\n\n"
        "[INSTRUCTION]\n"
        "문장 내용은 바꾸지 않고 SSML 태그만 삽입해 변환."\
    )

def convert_to_ssml(draft_script, tone):
    msgs = [
        {"role": "system", "content": SSML_SYSTEM},
        {"role": "user", "content": build_ssml_prompt(draft_script, tone)},
    ]
    return call_clova_chat(msgs, SSML_REQUEST_ID, max_tokens=10240, temperature=0.8)

def display_script(script: str) -> None:
    """SSML(또는 초안)을 콘솔에 그대로 출력"""
    print(script)

# =========  Top‑level helper  ===============================================

def run_one_block(summary, label, tone):
    tpl = search_prompt_template(f"{label} 대본 템플릿 {tone}")
    if not tpl:
        print("[run_one_block] Template not found")
        return None, None

    draft = generate_draft(summary, label, tone, tpl["template"])
    ssml  = convert_to_ssml(draft, tone)
    return draft, ssml
