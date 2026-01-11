import os
import sys
import json
import django
import google.generativeai as genai

# =========================================================
# [Portable Path] 어디서 실행하든 찰떡같이 경로 찾기
# =========================================================

# 1. 현재 파일(agent.py)의 위치를 기준으로 경로 계산
#    (예: /home/ubuntu/project/make_gold/make_gold/agent.py)
current_file_path = os.path.abspath(__file__)

# 2. 앱 폴더 (make_gold)
app_dir = os.path.dirname(current_file_path)

# 3. 프로젝트 루트 (상위 폴더)
project_root = os.path.dirname(app_dir)

# 4. 시스템 경로에 추가 (이제 파이썬이 프로젝트 전체를 인식함)
if project_root not in sys.path:
    sys.path.append(project_root)

# ---------------------------------------------------------
# Django 환경 설정
# ---------------------------------------------------------
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from make_gold.models import AuctionItem

# ---------------------------------------------------------
# Secrets 로드 (안전하게 Import)
# ---------------------------------------------------------
# sys.path에 app_dir가 포함되어 있으므로 바로 import 가능
try:
    # app_dir를 sys.path에 잠시 추가해서 확실하게 찾기
    if app_dir not in sys.path:
        sys.path.append(app_dir)
        
    import secrets as my_secrets
    GOOGLE_API_KEY = getattr(my_secrets, "GOOGLE_API_KEY", "")
    print(f"✅ 설정 파일 로드 성공")
except ImportError:
    GOOGLE_API_KEY = ""
    print(f"⚠️ 설정 파일(secrets.py)을 찾을 수 없습니다.")

# ---------------------------------------------------------
# AI 설정
# ---------------------------------------------------------
if not GOOGLE_API_KEY:
    print("🚨 API 키가 없습니다. secrets.py를 확인해주세요.")
else:
    print(f"🔑 API Key 확인 완료: {GOOGLE_API_KEY[:5]}*****")

genai.configure(api_key=GOOGLE_API_KEY)

def analyze_spec(description):
    """
    텍스트 설명(description)을 분석하여 JSON 데이터를 반환
    """
    model = genai.GenerativeModel('gemini-flash-latest')

    prompt = f"""
    너는 전문 귀금속 감정사야. 아래 [공매 물품 설명]을 분석해서 JSON 데이터를 추출해.
    
    [규칙]
    1. material: "GOLD", "SILVER", "DIAMOND", "OTHERS" 중 하나.
    2. purity: "24K", "18K", "14K", "UNKNOWN". (순금=24K)
    3. weight_g: 순수 금 무게(g)로 환산. (1돈=3.75g). 숫자만 출력.
    4. risk_factor: 설명이 명확하면 "LOW", 애매하면 "HIGH".
    
    [입력]
    {description}
    
    [출력]
    JSON 포맷만 출력 (Markdown backtick 없이).
    """

    try:
        response = model.generate_content(prompt)
        text = response.text.strip().replace("```json", "").replace("```", "")
        return json.loads(text)
    except Exception as e:
        print(f"   ⚠️ AI 분석 에러: {e}")
        return {"material": "UNKNOWN", "weight_g": 0, "risk_factor": "HIGH"}

def run_batch_analysis():
    print("\n=== 🤖 AI 분석 요원 투입 (Batch Start) ===")
    
    # 분석 안 된(risk_factor가 UNKNOWN인) 아이템만 가져오기
    target_items = AuctionItem.objects.filter(risk_factor="UNKNOWN")
    
    count = target_items.count()
    print(f">> 분석 대기 물량: {count}개")

    if count == 0:
        print(">> 모든 물건이 분석 완료 상태입니다. 퇴근합니다.")
        return

    for item in target_items:
        print(f"   🔍 분석 중: {item.title[:20]}...", end=" ")
        
        try:
            # 1. AI 분석 수행
            result = analyze_spec(item.description)
            
            # 2. 결과 DB 업데이트
            item.material = result.get('material', 'OTHERS')
            item.purity = result.get('purity', 'UNKNOWN')
            item.weight_g = result.get('weight_g', 0.0)
            item.risk_factor = result.get('risk_factor', 'HIGH')
            
            item.save()
            print(f"-> [완료] {item.weight_g}g / {item.purity}")
            
        except Exception as e:
            print(f"-> [실패] {e}")
            continue

    print("=== 분석 작업 종료 ===")

if __name__ == "__main__":
    run_batch_analysis()