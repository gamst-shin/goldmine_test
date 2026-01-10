import os
import sys
import time
import django
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# ---------------------------------------------------------
# 1. Django 환경 설정 (프로젝트 루트 연결)
# ---------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

# settings 설정
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from make_gold.models import AuctionItem

# ---------------------------------------------------------
# 2. 스크래핑 로직
# ---------------------------------------------------------
def run_scraper():
    # [수정됨] 사용자의 루틴 반영
    print("=== 🛸  Probe 대각서치 (Start) ===")
    
    options = webdriver.ChromeOptions()
    options.add_argument('window-size=1920x1080')
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    try:
        # [Step 1] 타겟 사이트 접속
        url = "https://www.kapao.co.kr/ver2/p/item/item"
        driver.get(url)
        time.sleep(2)

        # [Step 2] '귀금속' 카테고리 선택
        try:
            target_xpath = "//*[@id='cate-info']//label[contains(., '귀금속')]"
            checkbox = driver.find_element(By.XPATH, target_xpath)
            driver.execute_script("arguments[0].click();", checkbox)
            print(">> '귀금속' 멀티 발견 & 선택 완료")
            time.sleep(1)
        except Exception as e:
            print(f"!! 체크박스 선택 실패: {e}")
            return

        # [Step 3] 검색 실행 (버튼 클릭 대신 폼 전송으로 변경)
        # 여기가 아까 에러 잡은 그 부분!
        try:
            search_form = driver.find_element(By.ID, "frm_item_search")
            search_form.submit()
            print(f">> 검색 폼 전송 완료 (Form Submit)")
            time.sleep(3) 
        except Exception as e:
            print(f"!! 1차 검색 실패({e}), 2차 시도...")
            try:
                # 백업 플랜: XPath로 버튼 강제 탐색
                btn_xpath = "//*[@id='frm_item_search']//*[contains(@alt, '검색') or contains(., '검색')]"
                btn = driver.find_element(By.XPATH, btn_xpath)
                driver.execute_script("arguments[0].click();", btn)
                time.sleep(3)
            except:
                return

        # [Step 4] 리스트 순회 및 데이터 파싱
        list_xpath = "/html/body/div[4]/main/div[2]/div[5]/ul/li"
        items = driver.find_elements(By.XPATH, list_xpath)
        
        print(f">> 총 {len(items)}덩이의 미네랄을 발견했습니다.")

        for index, item in enumerate(items):
            try:
                # --- (1) 링크 & 이미지 ---
                a_tag = item.find_element(By.XPATH, "./a")
                link = a_tag.get_attribute("href")
                
                try:
                    img_tag = item.find_element(By.XPATH, "./a/div[1]/div/img")
                    img_src = img_tag.get_attribute("src")
                except:
                    img_src = ""

                # --- (2) 텍스트 정보 매핑 (dt/dd + zip) ---
                dl_tag = item.find_element(By.XPATH, "./a/div[2]/dl")
                dts = dl_tag.find_elements(By.TAG_NAME, "dt")
                dds = dl_tag.find_elements(By.TAG_NAME, "dd")
                
                title = "제목 없음"
                price = 0
                location = "미분류"
                raw_desc_list = []

                for dt, dd in zip(dts, dds):
                    label = dt.text.strip()
                    
                    try:
                        val_div = dd.find_element(By.TAG_NAME, "div")
                        value = val_div.text.strip()
                    except:
                        value = dd.text.strip()
                    
                    raw_desc_list.append(f"{label}: {value}")

                    if "물품명" in label:
                        title = value
                    elif "공매" in label:
                        clean_price = value.replace(",", "").replace("원", "").strip()
                        try:
                            price = int(clean_price)
                        except:
                            price = 0
                    elif "지역" in label:
                        location = value

                if title == "제목 없음":
                    try:
                        title = dl_tag.find_element(By.TAG_NAME, "dt").text.strip()
                    except:
                        pass

                # --- (3) DB 저장 ---
                full_desc = "\n".join(raw_desc_list)
                
                obj, created = AuctionItem.objects.update_or_create(
                    url=link,
                    defaults={
                        'title': title,
                        'location': location,
                        'price': price,
                        'image_url': img_src,
                        'description': full_desc,
                    }
                )
                
                status = "✨신규" if created else "♻️갱신"
                print(f"[{status}] {title[:20]}.. / {location} / {price:,}원")

            except Exception as e:
                continue

    except Exception as e:
        print(f"!! 정찰 실패: {e}")
    
    finally:
        driver.quit()
        print("=== 정찰 종료 (Return to Nexus) ===")

if __name__ == "__main__":
    run_scraper()