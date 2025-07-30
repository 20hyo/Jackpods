#!/usr/bin/env python3

import sys
import os
sys.path.append('.')

from transform.generate_speech import detect_xml_format, parse_segment_script_format

def test_parsing():
    xml_file = "test_script.xml"
    
    if not os.path.exists(xml_file):
        print(f"파일이 없습니다: {xml_file}")
        return
    
    print("=== XML 형식 감지 테스트 ===")
    xml_format = detect_xml_format(xml_file)
    print(f"감지된 형식: {xml_format}")
    
    if xml_format == 'segment_script':
        print("\n=== segment_script 파싱 테스트 ===")
        voice_segments, voice_order = parse_segment_script_format(xml_file)
        
        print(f"총 voice 세그먼트: {len(voice_segments)}")
        print(f"순서: {voice_order}")
        
        for key, content in voice_segments.items():
            print(f"\n--- {key} ---")
            print(f"내용 길이: {len(content)}")
            print(f"내용 시작: {content[:100]}...")
    else:
        print(f"예상하지 않은 형식: {xml_format}")

if __name__ == "__main__":
    test_parsing() 