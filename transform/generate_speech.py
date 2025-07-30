from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
from elevenlabs import play
import os
import xml.etree.ElementTree as ET
import re
import subprocess
import glob
import shutil

load_dotenv()

hyo_api = os.getenv("HYO_ELEVEN_API_KEY")

elevenlabs = ElevenLabs(
  api_key=hyo_api,
)

korean_male_voice_id = os.getenv("KOREAN_MALE")
korean_female_voice_id = os.getenv("KOREAN_FEMALE")

def parse_script_format(xml_file_path):
    """
    스크립트 형식의 XML 파일을 읽어서 각 voice 태그별로 SSML을 분리하는 메소드 (순서 유지)
    
    Args:
        xml_file_path (str): XML 파일 경로
        
    Returns:
        tuple: (voice_segments_dict, voice_order_list)
    """
    try:
        with open(xml_file_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        print(f"파일 내용 길이: {len(content)}")
        print(f"파일 내용 시작 부분: {content[:200]}")
        
        # XML 파싱
        root = ET.fromstring(content)
        
        # 각 voice 태그를 찾아서 분리 (순서 유지)
        voice_segments = {}
        voice_order = []
        
        # 모든 voice 태그를 순서대로 찾기
        voice_elements = root.findall(".//voice")
        print(f"찾은 voice 태그 개수: {len(voice_elements)}")
        
        for i, voice_elem in enumerate(voice_elements):
            voice_name = voice_elem.get("name")
            print(f"Voice {i+1}: name='{voice_name}'")
            
            if voice_name:
                # voice 태그 내부의 모든 내용을 추출
                voice_content = ""
                for child in voice_elem:
                    voice_content += ET.tostring(child, encoding='unicode')
                
                # 텍스트 노드도 포함
                if voice_elem.text:
                    voice_content = voice_elem.text + voice_content
                if voice_elem.tail:
                    voice_content += voice_elem.tail
                
                # speak 태그로 감싸기
                ssml_text = f"<speak>{voice_content}</speak>"
                
                # 키를 (순서_voice_name)으로 설정 (원래 대소문자 유지)
                key = f"{i+1:02d}_{voice_name}"
                voice_segments[key] = ssml_text
                voice_order.append(key)  # 순서대로 추가
                
                print(f"  - 키: {key}")
                print(f"  - 내용 길이: {len(voice_content)}")
        
        print(f"총 생성된 세그먼트: {len(voice_segments)}")
        return voice_segments, voice_order
        
    except FileNotFoundError:
        print(f"파일을 찾을 수 없습니다: {xml_file_path}")
        return {}, []
    except ET.ParseError as e:
        print(f"XML 파싱 오류: {e}")
        print(f"파일 경로: {xml_file_path}")
        # 파일 내용의 처음 부분을 출력하여 문제 파악
        try:
            with open(xml_file_path, "r", encoding="utf-8") as f:
                content = f.read()
                print(f"파일 내용 (처음 500자): {content[:500]}")
        except Exception as read_error:
            print(f"파일 읽기 오류: {read_error}")
        return {}, []
    except Exception as e:
        print(f"오류 발생: {e}")
        return {}, []

def parse_mstts_by_speaker(xml_file_path):
    """
    MSTTS 형식의 XML 파일을 읽어서 각 speaker별로 SSML을 분리하는 메소드 (순서 유지)
    
    Args:
        xml_file_path (str): XML 파일 경로
        
    Returns:
        tuple: (speaker_segments_dict, speaker_order_list)
    """
    try:
        with open(xml_file_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # XML 파싱
        root = ET.fromstring(content)
        
        # MSTTS 네임스페이스 정의
        namespaces = {
            'mstts': 'https://www.w3.org/2001/mstts'
        }
        
        # 각 mstts:turn 태그를 찾아서 분리 (순서 유지)
        speaker_segments = {}
        speaker_order = []
        
        # mstts:dialog 내부의 모든 mstts:turn 찾기
        dialog_elem = root.find('.//mstts:dialog', namespaces)
        if dialog_elem is not None:
            for i, turn_elem in enumerate(dialog_elem.findall('.//mstts:turn', namespaces)):
                speaker_name = turn_elem.get("speaker")
                if speaker_name:
                    # turn 태그 내부의 모든 내용을 추출
                    turn_content = ""
                    for child in turn_elem:
                        turn_content += ET.tostring(child, encoding='unicode')
                    
                    # 텍스트 노드도 포함
                    if turn_elem.text:
                        turn_content = turn_elem.text + turn_content
                    if turn_elem.tail:
                        turn_content += turn_elem.tail
                    
                    # speak 태그로 감싸기
                    ssml_text = f"<speak>{turn_content}</speak>"
                    
                    # 키를 (순서_speaker_name)으로 설정
                    key = f"{i+1:02d}_{speaker_name.lower()}"
                    speaker_segments[key] = ssml_text
                    speaker_order.append(key)  # 순서대로 추가
        
        return speaker_segments, speaker_order
        
    except FileNotFoundError:
        print(f"파일을 찾을 수 없습니다: {xml_file_path}")
        return {}, []
    except ET.ParseError as e:
        print(f"XML 파싱 오류: {e}")
        return {}, []
    except Exception as e:
        print(f"오류 발생: {e}")
        return {}, []

def parse_ssml_by_voice_ordered(xml_file_path):
    """
    XML 파일을 읽어서 각 voice 태그별로 SSML을 분리하는 메소드 (순서 유지)
    
    Args:
        xml_file_path (str): XML 파일 경로
        
    Returns:
        tuple: (voice_segments_dict, voice_order_list)
    """
    try:
        with open(xml_file_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # XML 파싱
        root = ET.fromstring(content)
        
        # 각 voice 태그를 찾아서 분리 (순서 유지)
        voice_segments = {}
        voice_order = []
        
        for segment_elem in root.findall(".//segment"):
            segment_id = segment_elem.get("id")
            if segment_id:
                # segment 내부의 각 voice 태그를 찾기
                for voice_elem in segment_elem.findall(".//voice"):
                    voice_name = voice_elem.get("name")
                    if voice_name:
                        # voice 태그 내부의 모든 내용을 추출
                        voice_content = ""
                        for child in voice_elem:
                            voice_content += ET.tostring(child, encoding='unicode')
                        
                        # 텍스트 노드도 포함
                        if voice_elem.text:
                            voice_content = voice_elem.text + voice_content
                        if voice_elem.tail:
                            voice_content += voice_elem.tail
                        
                        # speak 태그로 감싸기
                        ssml_text = f"<speak>{voice_content}</speak>"
                        
                        # 키를 (segment_id, voice_name)으로 설정
                        key = f"{segment_id}_{voice_name.lower()}"
                        voice_segments[key] = ssml_text
                        voice_order.append(key)  # 순서대로 추가
        
        return voice_segments, voice_order
        
    except FileNotFoundError:
        print(f"파일을 찾을 수 없습니다: {xml_file_path}")
        return {}, []
    except ET.ParseError as e:
        print(f"XML 파싱 오류: {e}")
        return {}, []
    except Exception as e:
        print(f"오류 발생: {e}")
        return {}, []

def parse_ssml_by_voice(xml_file_path):
    """
    XML 파일을 읽어서 각 보이스별로 SSML을 분리하는 메소드
    
    Args:
        xml_file_path (str): XML 파일 경로
        
    Returns:
        dict: 보이스 이름을 키로 하고 SSML 텍스트를 값으로 하는 딕셔너리
    """
    try:
        with open(xml_file_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # XML 파싱
        root = ET.fromstring(content)
        
        # 각 voice 태그를 찾아서 분리
        voice_segments = {}
        
        for voice_elem in root.findall(".//voice"):
            voice_name = voice_elem.get("name")
            if voice_name:
                # voice 태그 내부의 텍스트와 태그들을 추출
                voice_content = ""
                for child in voice_elem:
                    voice_content += ET.tostring(child, encoding='unicode')
                
                # 텍스트 노드도 포함
                if voice_elem.text:
                    voice_content = voice_elem.text + voice_content
                if voice_elem.tail:
                    voice_content += voice_elem.tail
                
                # speak 태그로 감싸기
                ssml_text = f"<speak>{voice_content}</speak>"
                voice_segments[voice_name] = ssml_text
        
        return voice_segments
        
    except FileNotFoundError:
        print(f"파일을 찾을 수 없습니다: {xml_file_path}")
        return {}
    except ET.ParseError as e:
        print(f"XML 파싱 오류: {e}")
        return {}
    except Exception as e:
        print(f"오류 발생: {e}")
        return {}

def parse_segment_script_format(xml_file_path):
    """
    segment 기반 스크립트 형식의 XML 파일을 읽어서 각 voice 태그별로 SSML을 분리하는 메소드 (순서 유지)
    
    Args:
        xml_file_path (str): XML 파일 경로
        
    Returns:
        tuple: (voice_segments_dict, voice_order_list)
    """
    try:
        with open(xml_file_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        print(f"파일 내용 길이: {len(content)}")
        print(f"파일 내용 시작 부분: {content[:200]}")
        
        # <ssml> 태그가 없으면 추가
        if not content.strip().startswith('<ssml>'):
            content = f'<ssml>\n{content.strip()}'
        
        # XML이 제대로 닫히지 않았을 수 있으므로 임시로 닫는 태그 추가
        if not content.strip().endswith('</ssml>'):
            content = content.strip() + '\n</ssml>'
        
        # XML 파싱 전에 내용 확인
        print(f"수정된 XML 내용 시작: {content[:200]}")
        print(f"수정된 XML 내용 끝: {content[-200:]}")
        
        try:
            # XML 파싱
            root = ET.fromstring(content)
        except ET.ParseError as e:
            print(f"XML 파싱 오류: {e}")
            # 더 강력한 XML 정리 시도
            import re
            
            # 한글 텍스트를 보존하면서 XML만 정리
            # 줄바꿈과 공백 정리
            content = content.replace('\n', ' ').replace('\r', ' ')
            content = re.sub(r'\s+', ' ', content)  # 연속된 공백 제거
            
            # XML 태그 사이의 공백 정리
            content = re.sub(r'>\s+<', '><', content)
            
            # 다시 <ssml> 태그 추가
            if not content.strip().startswith('<ssml>'):
                content = f'<ssml>\n{content.strip()}'
            if not content.strip().endswith('</ssml>'):
                content = content.strip() + '\n</ssml>'
            
            print(f"정리된 XML 내용: {content[:200]}")
            try:
                root = ET.fromstring(content)
            except ET.ParseError as e2:
                print(f"두 번째 XML 파싱 오류: {e2}")
                # 최후의 수단: 정규식으로 voice 태그 추출
                print("정규식으로 voice 태그 추출 시도...")
                return parse_with_regex(content)
        
        # 각 voice 태그를 찾아서 분리 (순서 유지)
        voice_segments = {}
        voice_order = []
        
        # 모든 voice 태그를 순서대로 찾기
        voice_elements = root.findall(".//voice")
        print(f"찾은 voice 태그 개수: {len(voice_elements)}")
        
        for i, voice_elem in enumerate(voice_elements):
            voice_name = voice_elem.get("name")
            print(f"Voice {i+1}: name='{voice_name}'")
            
            if voice_name:
                # voice 태그 내부의 모든 내용을 추출
                voice_content = ""
                for child in voice_elem:
                    voice_content += ET.tostring(child, encoding='unicode')
                
                # 텍스트 노드도 포함
                if voice_elem.text:
                    voice_content = voice_elem.text + voice_content
                if voice_elem.tail:
                    voice_content += voice_elem.tail
                
                # speak 태그로 감싸기
                ssml_text = f"<speak>{voice_content}</speak>"
                
                # 키를 (순서_voice_name)으로 설정 (원래 대소문자 유지)
                key = f"{i+1:02d}_{voice_name}"
                voice_segments[key] = ssml_text
                voice_order.append(key)  # 순서대로 추가
                
                print(f"  - 키: {key}")
                print(f"  - 내용 길이: {len(voice_content)}")
        
        print(f"총 생성된 세그먼트: {len(voice_segments)}")
        return voice_segments, voice_order
        
    except FileNotFoundError:
        print(f"파일을 찾을 수 없습니다: {xml_file_path}")
        return {}, []
    except ET.ParseError as e:
        print(f"XML 파싱 오류: {e}")
        print(f"파일 경로: {xml_file_path}")
        # 파일 내용의 처음 부분을 출력하여 문제 파악
        try:
            with open(xml_file_path, "r", encoding="utf-8") as f:
                content = f.read()
                print(f"파일 내용 (처음 500자): {content[:500]}")
        except Exception as read_error:
            print(f"파일 읽기 오류: {read_error}")
        return {}, []
    except Exception as e:
        print(f"오류 발생: {e}")
        return {}, []

def parse_with_regex(content):
    """
    XML 파싱이 실패할 때 정규식으로 voice 태그를 추출하는 백업 함수
    
    Args:
        content (str): XML 내용
        
    Returns:
        tuple: (voice_segments_dict, voice_order_list)
    """
    import re
    
    voice_segments = {}
    voice_order = []
    
    # voice 태그를 정규식으로 찾기
    voice_pattern = r'<voice name="([^"]+)">(.*?)</voice>'
    matches = re.findall(voice_pattern, content, re.DOTALL)
    
    print(f"정규식으로 찾은 voice 태그 개수: {len(matches)}")
    
    for i, (voice_name, voice_content) in enumerate(matches):
        print(f"Voice {i+1}: name='{voice_name}'")
        
        # speak 태그로 감싸기
        ssml_text = f"<speak>{voice_content}</speak>"
        
        # 키를 (순서_voice_name)으로 설정
        key = f"{i+1:02d}_{voice_name}"
        voice_segments[key] = ssml_text
        voice_order.append(key)
        
        print(f"  - 키: {key}")
        print(f"  - 내용 길이: {len(voice_content)}")
    
    print(f"총 생성된 세그먼트: {len(voice_segments)}")
    return voice_segments, voice_order

def clean_audio_directory():
    """
    generated_audio 폴더의 기존 파일들을 모두 삭제하는 함수
    """
    output_dir = "generated_audio"
    if os.path.exists(output_dir):
        try:
            shutil.rmtree(output_dir)
            print(f"기존 오디오 폴더 삭제 완료: {output_dir}")
        except Exception as e:
            print(f"폴더 삭제 오류: {e}")
    
    # 폴더 다시 생성
    os.makedirs(output_dir, exist_ok=True)
    print(f"새 오디오 폴더 생성 완료: {output_dir}")

def generate_audio_for_voice(ssml_text, voice_id, output_filename):
    """
    SSML 텍스트를 오디오로 변환하는 메소드
    
    Args:
        ssml_text (str): SSML 텍스트
        voice_id (str): 보이스 ID
        output_filename (str): 출력 파일명
    """
    try:
        # 출력 폴더 생성
        output_dir = "generated_audio"
        os.makedirs(output_dir, exist_ok=True)
        
        # 전체 파일 경로 생성
        full_path = os.path.join(output_dir, output_filename)
        
        audio = elevenlabs.text_to_speech.convert(
            text=ssml_text,
            voice_id=voice_id,
            model_id="eleven_multilingual_v2",
            output_format="mp3_44100_128",
        )
        
        # Convert generator to bytes
        audio_bytes = b"".join(audio)
        
        with open(full_path, "wb") as f:
            f.write(audio_bytes)
            
        print(f"오디오 파일 생성 완료: {full_path}")
        
    except Exception as e:
        print(f"오디오 생성 오류: {e}")

def combine_audio_files(segment_order, label=None):
    """
    오디오 파일들을 순서대로 합치는 함수 (ffmpeg 사용)
    
    Args:
        segment_order (list): 세그먼트 ID 순서 리스트
        label (str): 뉴스 분류 라벨 (선택사항)
    """
    try:
        output_dir = "generated_audio"
        
        print("\n=== 오디오 파일 합치는 중 ===")
        
        # 존재하는 파일들만 필터링
        existing_files = []
        for segment_id in segment_order:
            if label:
                audio_file = os.path.join(output_dir, f"{label}_{segment_id}_audio.mp3")
            else:
                audio_file = os.path.join(output_dir, f"{segment_id}_audio.mp3")
            
            if os.path.exists(audio_file):
                existing_files.append(audio_file)
                print(f"추가됨: {os.path.basename(audio_file)}")
            else:
                print(f"파일을 찾을 수 없음: {audio_file}")
        
        if not existing_files:
            print("합칠 파일이 없습니다.")
            return
        
        # ffmpeg로 오디오 합치기 (파일들을 직접 나열)
        if label:
            combined_file = f"combined_podcast_{label}.mp3"
        else:
            combined_file = "combined_podcast.mp3"
        
        # 파일들을 공백으로 구분해서 나열 (상대 경로 사용)
        input_files = " ".join([f"-i '{os.path.basename(file)}'" for file in existing_files])
        filter_complex = f"-filter_complex '[0:0]"
        
        for i in range(1, len(existing_files)):
            filter_complex += f"[{i}:0]"
        
        filter_complex += f"concat=n={len(existing_files)}:v=0:a=1[out]' -map '[out]'"
        
        cmd = f"ffmpeg {input_files} {filter_complex} '{combined_file}' -y"
        
        # output_dir에서 ffmpeg 실행
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=output_dir)
        
        if result.returncode == 0:
            full_combined_path = os.path.join(output_dir, combined_file)
            print(f"\n🎵 합쳐진 오디오 저장 완료: {full_combined_path}")
            
            # 파일 크기 정보
            if os.path.exists(full_combined_path):
                file_size = os.path.getsize(full_combined_path) / (1024 * 1024)  # MB
                print(f"파일 크기: {file_size:.1f} MB")
        else:
            print(f"ffmpeg 오류: {result.stderr}")
        
    except Exception as e:
        print(f"오디오 합치기 오류: {e}")

def detect_xml_format(xml_file_path):
    """
    XML 파일의 형식을 감지하는 함수
    
    Args:
        xml_file_path (str): XML 파일 경로
        
    Returns:
        str: 'mstts', 'segment_script', 'script', 'segment' 또는 'unknown'
    """
    try:
        with open(xml_file_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # MSTTS 형식인지 확인
        if 'mstts:dialog' in content and 'mstts:turn' in content:
            return 'mstts'
        
        # segment 기반 script 형식인지 확인 (segment 태그 안에 voice 태그가 있는 경우)
        elif '<segment id=' in content and '<voice name=' in content:
            # segment 태그 안에 voice 태그가 있는 새로운 형식
            return 'segment_script'
        
        # 기존 script 형식인지 확인 (voice 태그가 직접 사용되고 segment는 마커로만 사용되는 경우)
        elif '<voice name=' in content and '<segment id=' in content:
            # voice 태그가 segment 태그보다 많거나 비슷한 경우 script 형식
            voice_count = content.count('<voice')
            segment_count = content.count('<segment')
            
            # script 형식: voice 태그가 직접 사용되고 segment는 마커로만 사용
            if voice_count > 0 and segment_count > 0:
                return 'script'
            else:
                return 'segment'
        
        # <ssml> 태그로 감싸진 voice 태그들인 경우 script 형식
        elif '<ssml>' in content and '<voice name=' in content:
            return 'script'
        
        # segment 형식인지 확인 (segment 태그 내부에 voice가 있는 경우)
        elif 'segment' in content and 'voice' in content:
            return 'segment'
        
        else:
            return 'unknown'
            
    except Exception as e:
        print(f"파일 형식 감지 오류: {e}")
        return 'unknown'

if __name__ == "__main__":
    # 기존 오디오 폴더 정리
    clean_audio_directory()

    # XML 파일 형식 감지
    xml_file = "script_기업동향.xml"  # 스크립트 형식 파일 사용
    xml_format = detect_xml_format(xml_file)

    print(f"감지된 XML 형식: {xml_format}")

    if xml_format == 'script':
        # 스크립트 형식 파싱
        voice_segments, voice_order = parse_script_format(xml_file)
        
        # 보이스별 매핑
        voice_mapping = {
            "seoyeon": korean_female_voice_id,
            "injoon": korean_male_voice_id,
            "ava": korean_female_voice_id,
            "andrew": korean_male_voice_id
        }
        
        # 각 보이스별로 오디오 생성
        for key, ssml_text in voice_segments.items():
            # key에서 voice_name 추출 (예: "01_seoyeon" -> "seoyeon")
            voice_name = key.split("_")[-1]
            
            if voice_name in voice_mapping:
                voice_id = voice_mapping[voice_name]
                output_filename = f"{key}_audio.mp3"
                generate_audio_for_voice(ssml_text, voice_id, output_filename)
                print(f"보이스 '{voice_name}' 처리 완료: {key}")
            else:
                print(f"알 수 없는 보이스: {voice_name}")
        
        print("\n=== 생성된 오디오 파일들 ===")
        for key in voice_segments.keys():
            voice_name = key.split("_")[-1]
            if voice_name in voice_mapping:
                print(f"- {key}_audio.mp3")
        
        # XML 순서대로 오디오 파일들을 합치기
        print(f"\n=== XML 순서대로 합치기 ===")
        for i, key in enumerate(voice_order, 1):
            print(f"{i}. {key}")
        
        combine_audio_files(voice_order)

    elif xml_format == 'mstts':
        # MSTTS 형식 파싱
        speaker_segments, speaker_order = parse_mstts_by_speaker(xml_file)
        
        # speaker별 매핑
        speaker_mapping = {
            "seoyeon": korean_female_voice_id,
            "injoon": korean_male_voice_id,
            "ava": korean_female_voice_id,
            "andrew": korean_male_voice_id
        }
        
        # 각 speaker별로 오디오 생성
        for key, ssml_text in speaker_segments.items():
            # key에서 speaker_name 추출 (예: "01_seoyeon" -> "seoyeon")
            speaker_name = key.split("_")[-1]
            
            if speaker_name in speaker_mapping:
                voice_id = speaker_mapping[speaker_name]
                output_filename = f"{key}_audio.mp3"
                generate_audio_for_voice(ssml_text, voice_id, output_filename)
                print(f"Speaker '{speaker_name}' 처리 완료: {key}")
            else:
                print(f"알 수 없는 speaker: {speaker_name}")
        
        print("\n=== 생성된 오디오 파일들 ===")
        for key in speaker_segments.keys():
            speaker_name = key.split("_")[-1]
            if speaker_name in speaker_mapping:
                print(f"- {key}_audio.mp3")
        
        # XML 순서대로 오디오 파일들을 합치기
        print(f"\n=== XML 순서대로 합치기 ===")
        for i, key in enumerate(speaker_order, 1):
            print(f"{i}. {key}")
        
        combine_audio_files(speaker_order)

    elif xml_format == 'segment':
        # 기존 segment 형식 파싱
        voice_segments, voice_order = parse_ssml_by_voice_ordered(xml_file)
        
        # 보이스별 매핑
        voice_mapping = {
            "ava": korean_female_voice_id,
            "andrew": korean_male_voice_id
        }
        
        # 각 보이스별로 오디오 생성
        for key, ssml_text in voice_segments.items():
            # key에서 voice_name 추출 (예: "intro_host_seoyeon" -> "seoyeon")
            voice_name = key.split("_")[-1]
            
            if voice_name in voice_mapping:
                voice_id = voice_mapping[voice_name]
                output_filename = f"{key}_audio.mp3"
                generate_audio_for_voice(ssml_text, voice_id, output_filename)
                print(f"보이스 '{voice_name}' 처리 완료: {key}")
            else:
                print(f"알 수 없는 보이스: {voice_name}")
        
        print("\n=== 생성된 오디오 파일들 ===")
        for key in voice_segments.keys():
            voice_name = key.split("_")[-1]
            if voice_name in voice_mapping:
                print(f"- {key}_audio.mp3")
        
        # XML 순서대로 오디오 파일들을 합치기
        print(f"\n=== XML 순서대로 합치기 ===")
        for i, key in enumerate(voice_order, 1):
            print(f"{i}. {key}")
        
        combine_audio_files(voice_order)

    else:
        print("지원하지 않는 XML 형식입니다.")



