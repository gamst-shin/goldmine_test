import os
import json
import google.generativeai as genai
from django.conf import settings

# 1. API 키 설정 (나중에 settings.py나 환경변수로 빼는 게 정석이지만 일단 테스트용)
# ★여기에 네 API 키를 넣어야 해 (발급 방법은 아래에 설명)
GOOGLE_API_KEY = "API Key" 

genai.configure(api_key=GOOGLE_API_KEY)

def analyze_spec(description):
    """
    공매 물품 설명을 분석하여 순수 금 무게와 가치를 평가하기 위한 JSON 데이터를 반환함.
    """
    
    # 사용할 모델 선택 (Gemini 1.5 Flash가 빠르고 무료 쿼터에 최적)
    model = genai.GenerativeModel('gemini-flash-latest')

    # 프롬프트 설계 (JSON 포맷 강제)
    prompt = f"""
    너는 전문 귀금속 감정사야. 아래의 [공매 물품 설명]을 분석해서 정확한 JSON 데이터를 추출해.
    
    [분석 규칙]
    1. material: "GOLD", "SILVER", "DIAMOND", "OTHERS" 중 하나.
    2. purity: 금일 경우 "24K", "18K", "14K", "UNKNOWN". (순금=24K)
    3. weight_g: 전체 중량이 아니라 '순수 금의 추정 무게'를 그램(g) 단위로 환산해서 숫자만 출력.
       - 1돈 = 3.75g
       - "큐빅", "알" 등이 포함된 경우, 장식 무게를 제외하고 보수적으로(Min) 추정해.
    4. confidence: 너의 분석 확신도 (0.0 ~ 1.0). 설명이 모호하면 낮게 잡아.
    
    [공매 물품 설명]
    {description}
    
    [출력 형식]
    오직 JSON 포맷만 출력해. 마크다운 코드블럭(```json) 쓰지 말고 순수 텍스트 JSON만 줘.
    """

    try:
        response = model.generate_content(prompt)
        result_text = response.text.strip()
        
        # 가끔 ```json ... ``` 이렇게 줄 때가 있어서 제거 처리
        if result_text.startswith("```"):
            result_text = result_text.replace("```json", "").replace("```", "").strip()

        # JSON 파싱
        data = json.loads(result_text)
        return data

    except Exception as e:
        print(f"!! AI 분석 실패: {e}")
        # 에러 나면 기본값 반환 (죽지 않게)
        return {"material": "UNKNOWN", "weight_g": 0, "risk": "HIGH"}

# --- 테스트 실행용 ---
if __name__ == "__main__":
    # 테스트 케이스
    sample_text = "순금 24k 골드바 10돈 (보증서 있음)"
    print(f"입력: {sample_text}")
    
    result = analyze_spec(sample_text)
    print("결과:", result)
    
    print("-" * 30)
    
    sample_text2 = "18k 금반지 및 큐빅 등 총중량 5.0g"
    print(f"입력: {sample_text2}")
    result2 = analyze_spec(sample_text2)
    print("결과:", result2)