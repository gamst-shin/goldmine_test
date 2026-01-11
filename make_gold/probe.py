import os
import sys
import time
import random
import re
import django
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# =========================================================
# 1. Django 환경 설정 (DB 접속용)
# =========================================================
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from make_gold.models import AuctionItem

# =========================================================
# 2. 도우미 함수들 (데이터 정제)
# =========================================================
def extract_weight(text):
    """ 
    '총 중량 : 3.75g' 같은 텍스트에서 숫자(3.75)만 float로 추출 
    """
    try:
        # 숫자 + (점 + 숫자) 패턴 찾기
        match = re.search(r"(\d+(\.\d+)?)", text)
        if match:
            return float(match.group(1))
    except:
        pass
    return 0.0


# =========================================================
# [함수 수정] 줄바꿈 무시하고 전체에서 순도 찾기
# =========================================================
def extract_purity(text):
    """ 
    줄바꿈이 포함된 긴 텍스트에서 순도(24K, 18K, Au995 등)를 찾아냄 
    """
    if not text:
        return "UNKNOWN"

    # 1. 분석하기 좋게 대문자로 변환
    # (줄바꿈 문자는 놔둬도 re.search가 알아서 건너뛰며 찾음)
    target_text = text.upper()
    
    # 2. 우선순위별 검사 (24K > 18K > 14K)
    
    # [24K / 순금] Au999, Au995, 999, 24K, 순금
    if re.search(r'(24K|순금|AU99|999|995)', target_text):
        return "24K"
    
    # [18K] Au750, 750, 18K
    if re.search(r'(18K|AU750|750)', target_text):
        return "18K"
    
    # [14K] Au585, 585, 14K
    if re.search(r'(14K|AU585|585)', target_text):
        return "14K"
    
    # [백금/은]
    if re.search(r'(PT|PLATINUM|백금)', target_text):
        return "PLATINUM"
    if re.search(r'(AG|SILVER|은|그래뉼)', target_text):
        return "SILVER"

    return "UNKNOWN"

# =========================================================
# 3. 메인 크롤러 로직
# =========================================================
def run_scraper():
    print("=== 🛸 [Probe] 정찰 및 상세 성분 수집을 시작합니다 ===")
    
    options = webdriver.ChromeOptions()
    options.add_argument('--headless') # 브라우저 안 띄우려면 주석 해제
    options.add_argument('window-size=1920x1080')
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    
    # 수집할 타겟 리스트 (1차 수집 정보)
    scraped_targets = []

    try:
        # --- [Phase 1] 리스트 페이지에서 목록 확보 ---
        url = "https://www.kapao.co.kr/ver2/p/item/item"
        driver.get(url)
        time.sleep(2)

        # '귀금속' 카테고리 체크 및 검색
        try:
            target_xpath = "//*[@id='cate-info']//label[contains(., '귀금속')]"
            checkbox = driver.find_element(By.XPATH, target_xpath)
            driver.execute_script("arguments[0].click();", checkbox)
            time.sleep(1)
            
            search_form = driver.find_element(By.ID, "frm_item_search")
            search_form.submit()
            print(">> 리스트 갱신 중...")
            time.sleep(3) 
        except Exception as e:
            print(f"!! 검색 설정 실패: {e}")
            return

        # 리스트 아이템 가져오기
        items = driver.find_elements(By.XPATH, "/html/body/div[4]/main/div[2]/div[5]/ul/li")
        print(f">> 발견된 매물: {len(items)}개 (상세 수집 대기중)")

        # 리스트 루프: URL과 기본 정보만 빠르게 저장
        for item in items:
            try:
                a_tag = item.find_element(By.XPATH, "./a")
                link = a_tag.get_attribute("href")
                
                # 이미지
                try: img_src = item.find_element(By.XPATH, "./a/div[1]/div/img").get_attribute("src")
                except: img_src = ""

                # 리스트 상의 요약 텍스트 파싱
                dl_tag = item.find_element(By.XPATH, "./a/div[2]/dl")
                raw_text = dl_tag.text 
                
                title = "제목 없음"
                price = 0
                location = "미분류"
                
                lines = raw_text.split('\n')
                for line in lines:
                    if "물품명" in line: title = line.replace("물품명", "").strip()
                    if "감정평가액" in line or "최저입찰가" in line: 
                        # 가격 숫자만 추출
                        nums = re.findall(r'\d+', line.replace(",", ""))
                        if nums: price = int(nums[-1])
                    if "보관장소" in line: location = line.replace("보관장소", "").strip()

                scraped_targets.append({
                    "url": link,
                    "title": title,
                    "price": price,
                    "location": location,
                    "image_url": img_src,
                    "list_text": raw_text
                })
            except Exception as e:
                print(f"   ⚠️ 리스트 파싱 건너뜀: {e}")
                continue

        # --- [Phase 2] 상세 페이지 순회 (방문판매) ---
        print(f"\n>> 🔍 상세 페이지 진입 시작 ({len(scraped_targets)}개)")
        
        for idx, target in enumerate(scraped_targets):
            current_url = target['url']
            
            try:
                print(f"[{idx+1}/{len(scraped_targets)}] 이동: {target['title'][:10]}...", end="")
                
                driver.get(current_url)
                time.sleep(random.uniform(1.5, 3.5)) # 랜덤 휴식

                # --- 데이터 추출 ---
                weight_g = 0.0
                full_description = target['list_text'] # 기본값
                purity_val = "UNKNOWN"

                # 1. 무게 추출
                try:
                    weight_element = driver.find_element(By.XPATH, "/html/body/div[4]/main/div[3]/div[1]/div[2]/dl[3]/dd/span")
                    weight_g = extract_weight(weight_element.text)
                    if weight_g > 0:
                        print(f" -> ⚖️ {weight_g}g", end="")
                except:
                    pass

                # 2. 상세 설명 및 순도 추출 (★ 핵심 수정 부분)
                # div 위치가 9번일 수도, 13번일 수도 있으니 리스트로 순회하며 찾음
                possible_xpaths = [
                    "/html/body/div[4]/main/div[3]/div[4]/div[1]/div[13]", # 네가 새로 발견한 곳
                    "/html/body/div[4]/main/div[3]/div[4]/div[1]/div[9]",  # 아까 발견한 곳
                    "/html/body/div[4]/main/div[3]/div[4]/div[1]"          # 전체 박스 (최후의 수단)
                ]

                for xpath in possible_xpaths:
                    try:
                        element = driver.find_element(By.XPATH, xpath)
                        text = element.text.strip()
                        
                        # 내용이 비어있지 않으면 이걸 상세 설명으로 채택!
                        if text:
                            full_description = text
                            # 전체 텍스트 안에서 순도 검색 (줄바꿈 포함)
                            purity_found = extract_purity(full_description)
                            
                            if purity_found != "UNKNOWN":
                                purity_val = purity_found
                            break # 찾았으면 루프 탈출
                    except:
                        continue

                if purity_val != "UNKNOWN":
                    print(f" / 🥇 {purity_val}", end="")

                # --- DB 저장 ---
                AuctionItem.objects.update_or_create(
                    url=current_url,
                    defaults={
                        'title': target['title'],
                        'price': target['price'],
                        'location': target['location'],
                        'image_url': target['image_url'],
                        
                        # [중요] 전체 내용을 다 저장해둠 (나중에 AI가 다시 분석 가능)
                        'description': full_description, 
                        'weight_g': weight_g,            
                        'purity': purity_val,            
                    }
                )
                print(" [저장완료]")

            except Exception as e:
                print(f"\n   ⚠️ 상세 페이지 에러 ({current_url}): {e}")
                continue
                
    except Exception as e:
        print(f"!! 치명적 에러 발생: {e}")
    
    finally:
        driver.quit()
        print("\n=== 🏁 정찰 종료 ===")

if __name__ == "__main__":
    run_scraper()