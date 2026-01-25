import time
import re
import sqlite3
from datetime import datetime
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ==========================================
# 1. DB 관련 함수
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

def init_db():
    """DB 테이블이 없으면 생성"""
    conn = get_db_connection() 
    cur = conn.cursor()
    
    # [수정] price 타입을 REAL(실수) -> INTEGER(정수)로 변경
    cur.execute('''
        CREATE TABLE IF NOT EXISTS gold_price (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            price INTEGER NOT NULL,
            created_at TEXT
        )
    ''')
    conn.commit()
    conn.close()

def save_to_db(price):
    """가격을 DB에 저장"""
    # 들어오는 price는 이제 int형입니다.
    conn = get_db_connection()
    cur = conn.cursor()
    
    today = datetime.now().strftime('%Y-%m-%d')
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    cur.execute('''
        INSERT INTO gold_price (date, price, created_at)
        VALUES (?, ?, ?)
    ''', (today, price, now))
    
    conn.commit()
    conn.close()
    # [수정] 출력 포맷도 정수로 변경
    print(f"💾 [DB저장] {today} 기준 시세 {price:,}원 저장 완료!")

# ==========================================
# 2. 크롤링 함수
# ==========================================
def get_gold_price_selenium():
    options = webdriver.ChromeOptions()
    options.add_argument('--headless') # 테스트 끝나면 주석 해제해서 창 안뜨게 해도 됨
    options.add_argument('window-size=1920x1080')
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    options.add_argument("--log-level=3") 
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    
    try:
        driver.get("https://search.naver.com/search.naver?query=금시세")
        wait = WebDriverWait(driver, 10)

        # 신한은행 탭
        shinhan_tab_xpath = "/html/body/div[3]/div[2]/div[1]/div[1]/section[2]/div[1]/div[1]/div[2]/a[2]"
        shinhan_tab = wait.until(EC.element_to_be_clickable((By.XPATH, shinhan_tab_xpath)))
        shinhan_tab.click()
        time.sleep(0.5)

        # 실물 팔 때 탭
        real_gold_tab_xpath = "/html/body/div[3]/div[2]/div[1]/div[1]/section[2]/div[1]/div[2]/div[1]/div/ul/li[2]/a"
        real_gold_tab = wait.until(EC.element_to_be_clickable((By.XPATH, real_gold_tab_xpath)))
        real_gold_tab.click()
        time.sleep(0.5)

        # 가격 가져오기 (3.75g)
        target_price_xpath = "/html/body/div[3]/div[2]/div[1]/div[1]/section[2]/div[1]/div[2]/div[2]/div[3]/div[2]/span"
        price_element = wait.until(EC.visibility_of_element_located((By.XPATH, target_price_xpath)))
        raw_price = price_element.text 

        # [수정] 계산 로직: 반올림 후 정수(int) 변환
        price_num = float(re.sub(r'[^\d]', '', raw_price))
        
        # 3.75로 나누고 -> 반올림(round) -> 정수 변환(int)
        price_per_gram = int(round(price_num / 3.75))
        
        print(f"✅ 가져온 시세(1g): {price_per_gram:,}원") # 소수점 제거
        return price_per_gram

    except Exception as e:
        print(f"❌ 에러: {e}")
        return None
    finally:
        driver.quit()

# ==========================================
# 3. 메인 실행
# ==========================================
if __name__ == "__main__":
    init_db()
    
    gold_price = get_gold_price_selenium()
    
    if gold_price:
        save_to_db(gold_price)