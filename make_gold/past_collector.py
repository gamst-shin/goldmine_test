import time
import sqlite3
import re
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ==========================================
# 1. DB 초기화 (auction_history)
# ==========================================
def get_db_connection():
    """상위 폴더에 있는 db.sqlite3에 연결"""
    # 1. 현재 파일(collect_history.py)의 절대 경로를 구함
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 2. 부모 폴더(상위 폴더) 경로 구하기
    parent_dir = os.path.dirname(current_dir)
    
    # 3. 경로 합치기 (부모폴더 + db.sqlite3)
    db_path = os.path.join(parent_dir, 'db.sqlite3')
    
    return sqlite3.connect(db_path)

def init_history_db():
    conn = get_db_connection()
    cur = conn.cursor()
    
    # season: 회차
    # weight: 중량 (실수형)
    # price: 공매가/감정가 (정수형)
    # purity_info: 순금 함량 정보 (텍스트)
    cur.execute('''
        CREATE TABLE IF NOT EXISTS auction_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            season INTEGER,
            title TEXT,
            price INTEGER,
            weight REAL,
            purity_info TEXT,
            url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def save_item_to_db(item):
    conn = get_db_connection()
    cur = conn.cursor()
    
    # 중복 방지 (같은 URL이면 저장 안 함)
    cur.execute("SELECT count(*) FROM auction_history WHERE url=?", (item['url'],))
    if cur.fetchone()[0] == 0:
        cur.execute('''
            INSERT INTO auction_history (season, title, price, weight, purity_info, url)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (item['season'], item['title'], item['price'], item['weight'], item['purity_info'], item['url']))
        print(f"   💾 [저장완료] {item['title']} | {item['weight']}g | {item['price']:,}원")
    else:
        print(f"   PASS (이미 저장됨): {item['title']}")
            
    conn.commit()
    conn.close()

# ==========================================
# 2. 데이터 정제 함수 (Helper)
# ==========================================
def parse_price(text):
    """ '1,234,000 원' -> 1234000 """
    try:
        # 숫자만 남기고 제거
        clean = re.sub(r'[^\d]', '', text)
        return int(clean)
    except:
        return 0

def parse_weight(text):
    """ '중량 : 3.75g' -> 3.75 """
    try:
        # 소수점 포함 숫자 추출
        clean = re.sub(r'[^\d.]', '', text)
        return float(clean)
    except:
        return 0.0

# ==========================================
# 3. 크롤링 메인 로직
# ==========================================
def collect_past_auctions():
    options = webdriver.ChromeOptions()
    options.add_argument('window-size=1920x1080')
    options.add_argument("--log-level=3")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    wait = WebDriverWait(driver, 10)
    
    try:
        # 시작 URL
        base_url = "https://www.kapao.co.kr/ver2/p/item/item"
        driver.get(base_url)
        time.sleep(2)
        
        # 12회차 ~ 20회차 수집 (범위는 필요에 따라 수정)
        for season in range(12, 21): 
            print(f"\n====================================")
            print(f" 🔄 [제 {season} 회차] 데이터 수집 시작")
            print(f"====================================")
            
            driver.get(base_url)
            time.sleep(2) # 페이지 로딩 대기
            
            # 1. 회차 변경 (JS 실행)
            try:
                driver.execute_script(f"set_ps('{season}', '{season}회차');")
                time.sleep(2) # 페이지 로딩 대기 (필수)
                
                # -----------------------------------------------------------
                # [수정된 부분] 2. '귀금속' 카테고리 선택 (메뉴 열기 -> JS 강제 클릭)
                # -----------------------------------------------------------
                
                # (1) 카테고리 메뉴 버튼(상위 버튼) 클릭해서 열기
                try:
                    # 알려주신 Full XPath 사용
                    menu_btn_xpath = "/html/body/div[4]/main/div[2]/div[2]/div/ul/li[2]/button"
                    menu_btn = driver.find_element(By.XPATH, menu_btn_xpath)
                    menu_btn.click()
                    time.sleep(0.5) # 메뉴 열리는 애니메이션 대기
                except Exception as e:
                    # 메뉴가 이미 열려있거나 버튼을 못 찾아도, 일단 input 클릭 시도해봄
                    print(f"   (메뉴 버튼 클릭 건너뜀/실패: {e})")
                    pass

                # (2) '귀금속' 체크박스(input) 찾아서 JS로 강제 클릭
                target_input_xpath = "/html/body/div[4]/main/div[2]/div[2]/div/ul/li[2]/div/div/div[4]/label/input"
                
                # 화면에 안 보여도 DOM에 있으면 찾아냄 (presence_of_element_located)
                jewelry_checkbox = wait.until(EC.presence_of_element_located((By.XPATH, target_input_xpath)))
                
                # JS로 클릭 (가장 확실한 방법)
                driver.execute_script("arguments[0].click();", jewelry_checkbox)
                
                print(f"   >> '귀금속' 필터 적용 완료")
                time.sleep(1.5) # 리스트 갱신 대기
                
                try:
                    # 찾아주신 그 버튼 XPath
                    search_btn_xpath = "/html/body/div[4]/main/div[2]/div[2]/div/button"
                    search_btn = driver.find_element(By.XPATH, search_btn_xpath)
                    
                    # 그냥 클릭하거나, 혹시 안 되면 JS로 클릭
                    #search_btn.click()
                    driver.execute_script("arguments[0].click();", search_btn) # 클릭 안 되면 이거 주석 해제
                    
                    print(f"   >> 🔍 검색 버튼 클릭! 데이터 로딩 중...")
                    time.sleep(2) # 리스트 갱신될 때까지 충분히 대기
                    
                except Exception as e:
                    print(f"⚠️ 검색 버튼 클릭 실패: {e}")
                    continue
                
            except Exception as e:
                print(f"⚠️ {season}회차 이동/클릭 실패: {e}")
                continue              

            # 3. 리스트에서 상세 페이지 URL 수집
            item_urls = []
            try:
                # 리스트 영역 (분석해주신 경로)
                list_xpath = "/html/body/div[4]/main/div[2]/div[5]/ul/li"
                li_elements = driver.find_elements(By.XPATH, list_xpath)
                
                if not li_elements:
                    print("   >> 해당 회차에 귀금속 매물이 없습니다.")
                    continue
                
                for li in li_elements:
                    try:
                        # a 태그의 href 가져오기
                        a_tag = li.find_element(By.TAG_NAME, "a")
                        url = a_tag.get_attribute("href")
                        
                        # 제목도 미리 가져오면 좋음 (로깅용)
                        title = li.find_element(By.CLASS_NAME, "tit").text 
                        item_urls.append((title, url))
                    except:
                        continue
                        
                print(f"   >> 총 {len(item_urls)}개의 매물 발견! 상세 수집 시작...")

            except Exception as e:
                print(f"❌ 리스트 파싱 오류: {e}")
                continue

            # -----------------------------------------------------------
            # [수정됨] 4. 리스트에서 상세 페이지 URL 수집 (Wait 추가 & XPath 통일)
            # -----------------------------------------------------------
            item_urls = []
            try:
                # ★ 중요: probe.py와 동일한 XPath 사용
                list_xpath = "/html/body/div[4]/main/div[2]/div[5]/ul/li"
                
                # ★ 핵심: 검색 버튼 누르고 리스트가 뜰 때까지 최대 10초 기다림
                # (이게 없으면 로딩 중에 0개를 가져와버림)
                wait.until(EC.presence_of_element_located((By.XPATH, list_xpath)))
                
                # 요소를 찾음
                li_elements = driver.find_elements(By.XPATH, list_xpath)
                
                print(f"   >> 리스트 로딩 완료! 요소 개수: {len(li_elements)}개")

                if not li_elements:
                    print("   >> ⚠️ 로딩은 됐는데 매물이 없거나 XPath가 안 맞음.")
                    continue
                
                for idx, li in enumerate(li_elements):
                    try:
                        # probe.py 방식 그대로 적용
                        # li 바로 아래의 a 태그 찾기 (XPath: ./a)
                        a_tag = li.find_element(By.XPATH, "./a")
                        url = a_tag.get_attribute("href")
                        
                        # 제목 가져오기 (probe.py 방식 참고: ./a/div[2]/dl)
                        # 혹시 구조가 다를 수 있으니 간단하게 a 태그 안의 텍스트로 시도하거나 class로 시도
                        try:
                            # 제목이 들어있는 class (보통 tit)
                            title = li.find_element(By.CLASS_NAME, "tit").text
                        except:
                            title = f"{season}회차_{idx+1}번_물품"

                        item_urls.append((title, url))
                    except Exception as e:
                        print(f"   (아이템 {idx+1} 파싱 건너뜀: {e})")
                        continue
                        
                print(f"   >> ✅ 총 {len(item_urls)}개의 매물 URL 확보 완료. 상세 수집 시작...")

            except Exception as e:
                print(f"❌ 리스트 파싱 오류 (Wait 시간 초과 등): {e}")
                # 리스트 못 찾으면 다음 회차로
                continue

            # 5. 상세 페이지 순회
            for title, url in item_urls:
                try:
                    driver.get(url)
                    time.sleep(1) # 상세 페이지 로딩 대기
                    
                    # -------------------------------------------------
                    # [상세 정보 추출] - 분석해주신 XPath 사용
                    # -------------------------------------------------
                    
                    # (1) 공매가 (dl[2])
                    # dl 태그 전체 텍스트 예: "공매가\n1,200,000원"
                    price_xpath = "/html/body/div[4]/main/div[3]/div[1]/div[2]/dl[2]"
                    price_text = driver.find_element(By.XPATH, price_xpath).text
                    price = parse_price(price_text) # 정수 변환
                    
                    # (2) 중량 (dl[3])
                    weight_xpath = "/html/body/div[4]/main/div[3]/div[1]/div[2]/dl[3]"
                    weight_text = driver.find_element(By.XPATH, weight_xpath).text
                    weight = parse_weight(weight_text) # 실수 변환
                    
                    # (3) 순금 함량 정보 (상세설명 하위 div[10])
                    # div[10]이 없을 수도 있으니 예외처리 필수
                    purity_info = "정보없음"
                    try:
                        desc_xpath = "/html/body/div[4]/main/div[3]/div[4]/div[1]/div[10]"
                        purity_element = driver.find_element(By.XPATH, desc_xpath)
                        purity_info = purity_element.text
                        
                        # 만약 div[10]이 비어있으면 전체 설명에서 찾기 시도 (Backup Plan)
                        if not purity_info.strip():
                             full_desc = driver.find_element(By.XPATH, "/html/body/div[4]/main/div[3]/div[4]/div[1]").text
                             # 간단히 앞부분만 자르거나 키워드 검색
                             purity_info = full_desc[:100] 
                    except:
                        # div[10]이 없는 경우, 설명 전체 텍스트 가져오기
                        try:
                            full_desc_xpath = "/html/body/div[4]/main/div[3]/div[4]/div[1]"
                            purity_info = driver.find_element(By.XPATH, full_desc_xpath).text[:200] # 너무 기니까 자름
                        except:
                            pass

                    # -------------------------------------------------
                    # DB 저장
                    # -------------------------------------------------
                    item_data = {
                        'season': season,
                        'title': title,
                        'price': price,
                        'weight': weight,
                        'purity_info': purity_info,
                        'url': url
                    }
                    save_item_to_db(item_data)
                    
                    # 다시 목록으로 돌아갈 필요 없음 (URL로 바로 이동하므로)
                    
                except Exception as e:
                    print(f"❌ 상세 페이지 파싱 실패 ({url}): {e}")
                    continue

    except Exception as e:
        print(f"❌ 치명적 오류 발생: {e}")
        
    finally:
        driver.quit()

if __name__ == "__main__":
    init_history_db()
    collect_past_auctions()