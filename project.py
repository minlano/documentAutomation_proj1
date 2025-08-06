import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import plotly.express as px
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
import time
import os
from fpdf import FPDF
import requests
from PIL import Image
import uuid
from map import get_latlng_from_address, get_kakao_map_html

# 한글 폰트 설정 (matplotlib, fpdf)
FONT_PATHS = [
    "C:/Windows/Fonts/malgun.ttf",
    "./fonts/NanumGothic.ttf",
    "./NanumGothic.ttf"
]
for font_path in FONT_PATHS:
    if os.path.exists(font_path):
        plt.rcParams['font.family'] = fm.FontProperties(fname=font_path).get_name()
        break

def register_korean_font(pdf):
    for font_path in FONT_PATHS:
        if os.path.exists(font_path):
            pdf.add_font('Korean', '', font_path, uni=True)
            pdf.set_font('Korean', size=12)
            return True
    return False

def price_to_num(s):
    if pd.isnull(s): return None
    s = s.replace('억', '0000').replace(',', '').replace(' ', '')
    nums = ''.join(filter(str.isdigit, s))
    return int(nums) if nums else None

# 아파트 리스트 크롤링
def crawl_hogangnono(search_keyword):
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    driver = webdriver.Chrome(options=options)
    url = "https://hogangnono.com/"
    driver.get(url)
    time.sleep(2)
    search_box = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "input.keyword"))
    )
    search_box.clear()
    search_box.send_keys(search_keyword)
    time.sleep(1)
    search_box.send_keys(Keys.ENTER)
    time.sleep(3)
    results = []
    apts = driver.find_elements(By.CSS_SELECTOR, "li.apt")
    for apt in apts:
        try:
            name = apt.find_element(By.CSS_SELECTOR, ".label-container .label").text.replace('\n', '')
            household = apt.find_element(By.CSS_SELECTOR, ".desc .household").text
            start_date = apt.find_element(By.CSS_SELECTOR, ".desc .startDate").text
            url = apt.find_element(By.CSS_SELECTOR, "a").get_attribute("href")
            results.append({
                "단지명": name,
                "세대수": household,
                "입주일": start_date,
                "url": url
            })
        except Exception:
            continue
    driver.quit()
    return results

# 아파트 상세정보 크롤링
def crawl_hogangnono_detail(apt_url):
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    driver = webdriver.Chrome(options=options)
    if apt_url.startswith("http"):
        url = apt_url
    else:
        url = f"https://hogangnono.com{apt_url}"
    driver.get(url)
    time.sleep(2)
    info = {}
    # 주소
    try:
        info['주소'] = driver.find_element(By.CSS_SELECTOR, "div.text-sm.font-semibold.text-foreground").text
    except Exception:
        info['주소'] = None
    # 평당가격
    try:
        price_divs = driver.find_elements(By.CSS_SELECTOR, "div.css-yd0hrq.e8116ri5 > div.css-yhe5ws.e8116ri4")
        if len(price_divs) >= 2:
            first_price_span = price_divs[0].find_element(By.CSS_SELECTOR, "div.css-6cu8g1.e8116ri3 span.css-170k1nq.ei9pga10")
            평당가격 = first_price_span.text.strip()
        else:
            평당가격 = None
    except Exception:
        평당가격 = None
    info['평당가격'] = 평당가격
    # 1개월평균실거래가
    try:
        info['1개월평균실거래가'] = driver.find_element(By.CSS_SELECTOR, "div.price").text
    except Exception:
        info['1개월평균실거래가'] = None
    # 실거래가 테이블
    deals = []
    try:
        rows = driver.find_elements(By.CSS_SELECTOR, "table.css-15gqjnx.e1ea9ovl5 > tbody > tr")
        for row in rows:
            tds = row.find_elements(By.TAG_NAME, "td")
            if len(tds) >= 3:
                계약일 = tds[0].text.strip()
                면적 = tds[1].text.strip()
                price_div = tds[2]
                price_spans = price_div.find_elements(By.CSS_SELECTOR, "span.css-158icaa.ebmi0c75")
                if price_spans:
                    가격 = price_spans[-1].text.strip()
                else:
                    가격 = price_div.text.strip()
                deals.append({
                    "계약일": 계약일,
                    "면적": 면적,
                    "가격": 가격
                })
    except Exception:
        pass
    info['실거래가'] = deals
    # 지역평당가
    try:
        price_divs = driver.find_elements(By.CSS_SELECTOR, "div.css-yd0hrq.e8116ri5 > div.css-yhe5ws.e8116ri4")
        if len(price_divs) >= 2:
            price_spans = price_divs[0].find_elements(By.CSS_SELECTOR, "div.css-6cu8g1.e8116ri3 span.css-170k1nq.ei9pga10")
            price_values = [span.text.strip() for span in price_spans]
            region_spans = price_divs[1].find_elements(By.CSS_SELECTOR, "span.css-1ldqlku.ei9pga10")
            region_names = [span.text.strip() for span in region_spans]
            지역평당가 = dict(zip(region_names, price_values))
        else:
            지역평당가 = {}
    except Exception:
        지역평당가 = {}
    info['지역평당가'] = 지역평당가
    # 이미지
    try:
        img_elem = driver.find_element(By.CSS_SELECTOR, "div.img-wrapper img")
        img_url = img_elem.get_attribute("src")
    except Exception:
        img_url = None
    info['이미지'] = img_url
    driver.quit()
    return info

# Streamlit 앱
st.title("호갱노노 아파트 정보 크롤링/분석")

# 1. 검색
search_keyword = st.text_input("검색어를 입력하세요 (예: 래미안, 자이 등):")
if st.button("검색") and search_keyword:
    with st.spinner("크롤링 중..."):
        data = crawl_hogangnono(search_keyword)
    if data:
        st.session_state['search_data'] = data
        st.success(f"검색 결과: {search_keyword}")
    else:
        st.warning("검색 결과가 없습니다.")

data = st.session_state.get('search_data', [])

# 2. 단일 단지 선택
if data:
    apt_names = [d['단지명'] for d in data]
    selected_idx = st.selectbox("아파트를 선택하세요", range(len(apt_names)), format_func=lambda x: apt_names[x])
    selected_apt = data[selected_idx]
    if st.button("상세정보 보기"):
        with st.spinner("크롤링 중..."):
            detail = crawl_hogangnono_detail(selected_apt['url'])
        st.session_state['detail'] = detail
        # 상세정보 표
        info_table = {
            "단지명": selected_apt['단지명'],
            "주소": detail.get('주소'),
            "평당가격": detail.get('평당가격'),
            "1개월평균실거래가": detail.get('1개월평균실거래가'),
            "지역평당가": detail.get('지역평당가')
        }
        st.table(pd.DataFrame([info_table]))
        # 실거래가 표
        if detail.get('실거래가'):
            df = pd.DataFrame(detail['실거래가'])
            st.subheader("실거래가 내역")
            st.dataframe(df)
            # 면적별 실거래가 추이
            df['계약일'] = pd.to_datetime('20' + df['계약일'], format='%Y.%m.%d', errors='coerce')
            df['가격(만원)'] = df['가격'].apply(price_to_num)
            df['면적'] = df['면적'].astype(str)
            plt.figure(figsize=(8,5))
            for area, group in df.groupby('면적'):
                group = group.sort_values('계약일')
                plt.plot(group['계약일'], group['가격(만원)'], marker='o', label=f"{area}㎡")
            plt.xlabel("계약일")
            plt.ylabel("가격(만원)")
            plt.title("면적별 실거래가 추이")
            plt.legend()
            plt.tight_layout()
            st.pyplot(plt)
        # 지역 평당가 막대그래프
        region_price = detail.get('지역평당가', {})
        if region_price:
            df_region = pd.DataFrame(list(region_price.items()), columns=['지역', '평당가'])
            df_region = df_region[df_region['평당가'].str.contains('만원')]
            df_region = df_region[df_region['평당가'].str.strip() != '']
            try:
                df_region['평당가(만원)'] = df_region['평당가'].str.replace('만원','').str.replace(',','').astype(int)
                st.subheader("지역 평당가 비교")
                fig = px.bar(df_region, x='지역', y='평당가(만원)', title="지역 평당가 비교")
                fig.update_layout(font_family="Malgun Gothic")
                st.plotly_chart(fig, use_container_width=True)
            except Exception as e:
                st.error(f"그래프 에러: {e}")
        else:
            st.info("지역 평당가 데이터가 없습니다.")

        # 아파트 이미지
        if detail.get('이미지'):
            st.image(detail['이미지'], caption="아파트 이미지", use_container_width=True)

        # 주소 지도 표시 (맨 아래)
        if detail.get('주소'):
            st.markdown("#### 📍 지도")
            lat, lng = get_latlng_from_address(detail['주소'])
            if lat and lng:
                map_html = get_kakao_map_html(lat, lng)
                st.components.v1.html(map_html, height=400)
            else:
                st.warning("해당 주소의 좌표를 찾을 수 없습니다.")

# 3. PDF 저장 버튼 (상세정보가 있을 때만)
if 'detail' in st.session_state and st.session_state['detail']:
    detail = st.session_state['detail']
    if st.button("PDF로 저장"):
        pdf = FPDF()
        pdf.add_page()
        if not register_korean_font(pdf):
            st.error("한글 폰트 등록 실패! PDF에 한글이 깨질 수 있습니다.")

        # 1페이지: 아파트 이미지
        if detail.get('이미지'):
            img_path = "apt_img.jpg"
            with open(img_path, "wb") as f:
                f.write(requests.get(detail['이미지']).content)
            with Image.open(img_path) as im:
                width, height = im.size
            max_width = 180
            w = max_width
            h = height * (w / width)
            y_img = (297 - h) / 2 if h < 297 else 10  # 중앙정렬(세로), 너무 크면 위쪽
            pdf.image(img_path, x=15, y=y_img, w=w, h=h)
            os.remove(img_path)
            pdf.ln(h + 5)

        # 2페이지: 글/표
        pdf.add_page()
        pdf.set_font('Korean', '', 14)
        for k in ['단지명', '주소', '평당가격', '1개월평균실거래가']:
            v = detail.get(k) if k != '단지명' else selected_apt['단지명']
            pdf.cell(0, 10, f"{k}: {v}", ln=True)
        pdf.ln(2)
        pdf.set_font('Korean', '', 12)
        pdf.cell(0, 10, "지역 평당가", ln=True)
        region_price = detail.get('지역평당가', {})
        for k, v in region_price.items():
            pdf.cell(0, 10, f"{k}: {v}", ln=True)
        pdf.ln(2)
        pdf.cell(0, 10, "실거래가 내역", ln=True)
        for row in detail['실거래가']:
            pdf.cell(0, 10, f"{row['계약일']} | {row['면적']} | {row['가격']}", ln=True)
        pdf.ln(2)

        # 3페이지: 그래프
        pdf.add_page()
        # 면적별 실거래가 추이 그래프
        if detail.get('실거래가'):
            df = pd.DataFrame(detail['실거래가'])
            df['계약일'] = pd.to_datetime('20' + df['계약일'], format='%Y.%m.%d', errors='coerce')
            df['가격(만원)'] = df['가격'].apply(price_to_num)
            df['면적'] = df['면적'].astype(str)
            plt.figure(figsize=(8,5))
            for area, group in df.groupby('면적'):
                group = group.sort_values('계약일')
                plt.plot(group['계약일'], group['가격(만원)'], marker='o', label=f"{area}㎡")
            plt.xlabel("계약일")
            plt.ylabel("가격(만원)")
            plt.title("면적별 실거래가 추이")
            plt.legend()
            plt.tight_layout()
            chart_path = "price_chart.png"
            plt.savefig(chart_path)
            plt.close()
            pdf.image(chart_path, x=10, y=20, w=180)
            os.remove(chart_path)
            pdf.ln(80)
        # 지역평당가 비교 그래프
        if region_price:
            df_region = pd.DataFrame(list(region_price.items()), columns=['지역', '평당가'])
            df_region = df_region[df_region['평당가'].str.contains('만원')]
            df_region = df_region[df_region['평당가'].str.strip() != '']
            try:
                df_region['평당가(만원)'] = df_region['평당가'].str.replace('만원','').str.replace(',','').astype(int)
                plt.figure(figsize=(6,4))
                plt.bar(df_region['지역'], df_region['평당가(만원)'])
                plt.title("지역 평당가 비교")
                plt.xlabel("지역")
                plt.ylabel("평당가(만원)")
                plt.tight_layout()
                region_chart_path = "region_price_chart.png"
                plt.savefig(region_chart_path)
                plt.close()
                pdf.image(region_chart_path, x=10, y=150, w=180)
                os.remove(region_chart_path)
                pdf.ln(5)
            except Exception as e:
                pdf.cell(0, 10, f"지역평당가 그래프 에러: {e}", ln=True)
        # 파일명에 uuid 추가
        pdf_filename = f"apt_detail_{uuid.uuid4().hex[:8]}.pdf"
        pdf.output(pdf_filename)
        st.success(f"PDF 저장 완료! ({pdf_filename})")
        with open(pdf_filename, "rb") as f:
            st.download_button("PDF 다운로드", f, file_name=pdf_filename)