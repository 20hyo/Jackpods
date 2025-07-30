from datetime import datetime, timedelta
import requests
import pytz
import asyncio
import pandas as pd
import os
import xml.etree.ElementTree as ET
import subprocess
import shutil

from extract.hankyung import collect_parse_hankyung_feed
from extract.mk_collector import collect_parse_mk_feed
from transform.summarizer import run as summarize_news
from transform.createPrompt import label_data, into_prompt
from script_generation.script import search_prompt_template, generate_draft, convert_to_ssml, display_script
from transform.generate_speech import (
    parse_script_format, 
    parse_segment_script_format,
    detect_xml_format, 
    clean_audio_directory, 
    generate_audio_for_voice, 
    combine_audio_files,
    korean_male_voice_id,
    korean_female_voice_id
)

def process_script_to_audio(script_content, label):
    try:
        cleaned_content = script_content.strip()
        
        if cleaned_content.startswith('```ssml'):
            cleaned_content = cleaned_content[7:]
        
        if cleaned_content.endswith('```'):
            cleaned_content = cleaned_content[:-3]
        
        cleaned_content = cleaned_content.strip()
        
        # XML 선언 제거
        cleaned_content = cleaned_content.replace('<?xml version="1.0"?>', '')
        cleaned_content = cleaned_content.strip()
        
        # <ssml> 태그가 없으면 추가
        if not cleaned_content.startswith('<ssml'):
            cleaned_content = f'<ssml>\n{cleaned_content}\n</ssml>'
        
        print(f"정리된 스크립트 길이: {len(cleaned_content)}")
        print(f"정리된 스크립트 시작 부분: {cleaned_content[:200]}")
        
        temp_xml_file = f"temp_script_{label}.xml"
        with open(temp_xml_file, "w", encoding="utf-8") as f:
            f.write(cleaned_content)
        
        xml_format = detect_xml_format(temp_xml_file)
        print(f"감지된 XML 형식: {xml_format}")
        
        if xml_format == 'segment_script':
            voice_segments, voice_order = parse_segment_script_format(temp_xml_file)
        elif xml_format == 'script':
            voice_segments, voice_order = parse_script_format(temp_xml_file)
            
            voice_mapping = {
                "Seoyeon": korean_female_voice_id,
                "Injoon": korean_male_voice_id,
                "Ava": korean_female_voice_id,
                "Andrew": korean_male_voice_id
            }
            
            print(f"\n=== '{label}' 분류 오디오 생성 시작 ===")
            
            for key, ssml_text in voice_segments.items():
                # key에서 voice_name 추출 (예: "01_Seoyeon" -> "Seoyeon")
                voice_name = key.split("_")[-1]
                
                if voice_name in voice_mapping:
                    voice_id = voice_mapping[voice_name]
                    output_filename = f"{label}_{key}_audio.mp3"
                    generate_audio_for_voice(ssml_text, voice_id, output_filename)
                    print(f"보이스 '{voice_name}' 처리 완료: {key}")
                else:
                    print(f"알 수 없는 보이스: {voice_name}")
            
            print(f"\n=== '{label}' 분류 오디오 합치기 ===")
            combine_audio_files(voice_order, label)
            
            print(f"✅ '{label}' 분류 오디오 생성 완료!")
            
        else:
            print(f"지원하지 않는 XML 형식입니다: {xml_format}")
        
        if os.path.exists(temp_xml_file):
            os.remove(temp_xml_file)
            
    except Exception as e:
        print(f"오디오 생성 중 오류 발생: {e}")

def main():
    kst = pytz.timezone('Asia/Seoul')
    now = datetime.now(kst).date() - timedelta(days=1)

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
        df = pd.read_csv(f"news_summary_2025-07-24.csv") 
    except FileNotFoundError:
        print(f"오류: news_summary_{now}.csv 파일을 찾을 수 없습니다. 뉴스 수집 및 요약 단계를 먼저 실행하거나, 유효한 CSV 파일 경로를 확인하세요.")
        return

    if df.empty:
        print(f"경고: 뉴스 요약 데이터프레임이 비어 있습니다. 대본 생성을 건너뜁니다.")
        return

    df_labeled = label_data(df)
    df_labeled.to_csv(f"news_summary_labeled_2025-07-24.csv", index=False)

    print("\n--- 분류별 SSML 대본 생성 및 오디오 변환 시작 ---")

    if df_labeled.empty:
        print("경고: 레이블링된 뉴스 데이터가 없어 대본 생성을 시작할 수 없습니다.")
        return

    clean_audio_directory()

    grouped_news = {}
    for index, row in df_labeled.iterrows():
        label = row['label_kor']
        sentiment = row['tone']
        description = row['description']

        if label not in grouped_news:
            grouped_news[label] = {
                'descriptions': [],
                'sentiment': sentiment
            }
        grouped_news[label]['descriptions'].append(description)

    for label, data in grouped_news.items():
        combined_description = "\n\n".join(data['descriptions'])
        representative_sentiment = data['sentiment']

        print(f"\n--- 분류: '{label}' ---")
        print(f"[대표 감정]: {representative_sentiment}")
        print(f"[포함된 뉴스 개수]: {len(data['descriptions'])}")

        # 프롬프트 템플릿 검색 쿼리 생성
        # 다이어그램 예시와 일치하도록 쿼리 변경:
        query_for_prompt_template = f"{label}_긍정_PlainText_KR"
        print(f"프롬프트 템플릿 검색 쿼리: '{query_for_prompt_template}'")

        selected_prompt_template_content = search_prompt_template(query_for_prompt_template, top_k=1)

        if not selected_prompt_template_content:
            print(f"적합한 프롬프트 템플릿을 찾지 못하여 '{label}' 분류에 대한 대본 생성을 건너갑니다.")
            continue
        else:
            # ① 초안 생성 ───────────────────────────────
            draft_script = generate_draft(
                summary=combined_description,            # 통합 요약
                label=label,                             # 예: "거시경제"
                tone=representative_sentiment,           # 예: "positive"
                template_text=selected_prompt_template_content["template"]
            )

            print("\n--- 생성된 대본 초안 (Plain) ---")
            display_script(draft_script)

            # ② SSML 변환 ──────────────────────────────
            ssml_script = convert_to_ssml(
                draft_script=draft_script,
                tone=representative_sentiment
            )

            print("\n--- 최종 SSML 대본 ---")
            display_script(ssml_script)
            
            # 파일명에 사용할 수 없는 문자를 안전한 문자로 변경
            safe_label = label.replace("/", "_")
            script_filename = f"script_{safe_label}.xml"
            with open(script_filename, "w", encoding="utf-8") as f:
                f.write(ssml_script)
            
            print(f"대본 파일 저장 완료: {script_filename}")
            
            print(f"\n=== '{label}' 분류 오디오 변환 시작 ===")
            process_script_to_audio(ssml_script, safe_label)

    print("\n--- 전체 대본 생성 및 오디오 변환 파이프라인 완료 ---")
    print("🎵 생성된 오디오 파일들은 'generated_audio' 폴더에서 확인할 수 있습니다.")

if __name__ == "__main__":
    main()
