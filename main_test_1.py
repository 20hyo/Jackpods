# main.py

from datetime import datetime, timedelta
import requests
import pytz
import asyncio
import pandas as pd

# Import functions from your existing modules
from extract.hankyung import collect_parse_hankyung_feed
from extract.mk_collector import collect_parse_mk_feed
from transform.summarizer import run as summarize_news # Renamed to avoid conflict with main's run
from transform.createPrompt import label_data, into_prompt

# Import script generation functions from the new module
from script_generation.script import search_prompt_template, generate_draft, convert_to_ssml, display_script

def main():
    kst = pytz.timezone('Asia/Seoul')
    now = datetime.now(kst).date() - timedelta(days=1) # Use yesterday's date for consistency with previous runs

    # 1. 뉴스 수집 및 요약
    # 주석 처리된 부분을 필요에 따라 활성화하여 실제 뉴스 수집 및 요약을 수행할 수 있습니다.
    # 현재는 예시 CSV 파일을 읽어옵니다.

    # news_list = collect_parse_mk_feed(now) # 또는 collect_parse_hankyung_feed(now)
    #
    # if not news_list:
    #     print(f"경고: {now} 날짜에 수집된 뉴스가 없습니다. 대본 생성을 건너킵니다.")
    #     return
    #
    # links = list(set(news["link"] for news in news_list))
    # results = asyncio.run(summarize_news(links, "mk")) # 'mk' 또는 'hankyung'
    #
    # if not results:
    #     print(f"경고: {now} 날짜에 요약된 뉴스가 없습니다. 대본 생성을 건너킵니다.")
    #     return
    #
    # df = pd.DataFrame(results)
    # df.to_csv(f"news_summary_{now}.csv", index=False)

    # 예시: 이미 요약된 CSV 파일 읽기
    try:
        # 이 줄은 실제 파일명에 맞게 수정해서 사용(test용이므로 수집을 안하므로)
        df = pd.read_csv(f"news_summary_2025-07-24.csv") 
    except FileNotFoundError:
        print(f"오류: news_summary_{now}.csv 파일을 찾을 수 없습니다. 뉴스 수집 및 요약 단계를 먼저 실행하거나, 유효한 CSV 파일 경로를 확인하세요.")
        return

    # 뉴스 감정 분석 및 프롬프트 생성
    if df.empty:
        print(f"경고: 뉴스 요약 데이터프레임이 비어 있습니다. 대본 생성을 건너뜁니다.")
        return

    df_labeled = label_data(df)
    # print(prompts[:5]) # 검증을 위한 첫 5개 프롬프트 출력
    df_labeled.to_csv(f"news_summary_labeled_2025-07-24.csv", index=False)

    # --- 3. 분류별 SSML 대본 생성 ---
    print("\n--- 분류별 SSML 대본 생성 시작 ---")

    if df_labeled.empty:
        print("경고: 레이블링된 뉴스 데이터가 없어 대본 생성을 시작할 수 없습니다.")
        return

    # 'label'과 'sentiment' 기준으로 그룹화
    # 각 그룹의 뉴스 설명을 합치고, 대표 감정을 선택 (여기서는 첫 번째 기사의 감정을 대표 감정으로 사용)
    grouped_news = {}
    for index, row in df_labeled.iterrows():
        label = row['label_kor']
        sentiment = row['tone']
        description = row['description']

        if label not in grouped_news:
            grouped_news[label] = {
                'descriptions': [],
                'sentiment': sentiment # 그룹의 대표 감정으로 첫 번째 기사의 감정 사용
            }
        grouped_news[label]['descriptions'].append(description)

    for label, data in grouped_news.items():
        combined_description = "\n\n".join(data['descriptions'])
        representative_sentiment = data['sentiment']

        print(f"\n--- 분류: '{label}' ---")
        print(f"[대표 감정]: {representative_sentiment}")
        print(f"[포함된 뉴스 개수]: {len(data['descriptions'])}")

        # 통합 요약을 Milvus에 저장 (새로운 부분)
        # RAG의 '원천 정보'라면 여기에 저장하는 것을 고려
        # store_combined_summary_in_milvus(combined_description, label, representative_sentiment)


        # 프롬프트 템플릿 검색 쿼리 생성
        # 다이어그램 예시와 일치하도록 쿼리 변경:
        query_for_prompt_template = f"{label}_긍정_PlainText_KR" # 다이어그램 예시와 일치하도록 변경
        print(f"프롬프트 템플릿 검색 쿼리: '{query_for_prompt_template}'")

        selected_prompt_template_content = search_prompt_template(query_for_prompt_template, top_k=1)

        if not selected_prompt_template_content:
            print(f"적합한 프롬프트 템플릿을 찾지 못하여 '{label}' 분류에 대한 대본 생성을 건너갑니다.")
            # --- 템플릿 폴백 로직 (새로운 부분) ---
            print(f"템플릿 검색 실패. 폴백 로직 시도: label_id='{label}', tone='{representative_sentiment}'")
            # 이것은 폴백에 대한 플레이스홀더입니다. 실제로는
            # 기본 템플릿을 위한 하드코딩된 딕셔너리 또는 다른 조회 메커니즘이 있을 수 있습니다.
            # 예시 (DEFAULT_PROMPT_TEMPLATES를 어딘가에 정의해야 함):
            # fallback_key = f"{label}_{representative_sentiment}"
            # if fallback_key in DEFAULT_PROMPT_TEMPLATES:
            #     selected_prompt_template_content = {"template": DEFAULT_PROMPT_TEMPLATES[fallback_key]}
            #     print(f"폴백 템플릿 사용: {fallback_key}")
            # else:
            #     print(f"폴백 템플릿도 찾을 수 없어 '{label}' 분류에 대한 대본 생성을 건너갑니다.")
            #     continue # 폴백 후에도 템플릿을 찾지 못하면 건너뜁니다.
            continue # 현재는 찾지 못하면 그냥 건너뜁니다.
            # --- 폴백 로직 끝 ---
        else:
            # SSML 대본 생성 (그룹화된 설명을 사용)
            # generate_script 내부에서 'rag_chunks'에서 RAG를 구현한다면,
            # combined_description을 직접 전달할 필요 없이 쿼리만 전달하거나,
            # generate_script가 스스로 결정하도록 할 수 있습니다.
 # ① 초안 생성 ───────────────────────────────
            draft_script = generate_draft(
                summary=combined_description,            # 통합 요약
                label=label,                             # 예: "거시경제"
                tone=representative_sentiment,           # 예: "positive"
                template_text=selected_prompt_template_content["template"]
            )

            print("\n--- 생성된 대본 초안 (Plain) ---")
            display_script(draft_script)                # 필요 없으면 주석 처리

            # ② SSML 변환 ──────────────────────────────
            ssml_script = convert_to_ssml(
                draft_script=draft_script,
                tone=representative_sentiment
            )

            print("\n--- 최종 SSML 대본 ---")
            display_script(ssml_script)
    print("--- 대본 생성 완료 ---")



if __name__ == "__main__":
    main()
