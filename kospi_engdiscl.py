import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import time
import random

# --- 페이지 설정 ---
st.set_page_config(page_title="코스피 번역공시 필터링", layout="wide")

st.title('🎯 오늘의 코스피 번역대상 공시')

# --- 1. 데이터 로드 (CSV) ---
@st.cache_data
def load_data():
    try:
        # 로컬에 kospi_format.csv와 kospi_company.csv 파일이 있어야 합니다.
        df_svc = pd.read_csv("kospi_format.csv", dtype=str)
        df_listed = pd.read_csv("kospi_company.csv", dtype=str)
        
        if not df_listed.empty:
            # 회사코드를 5자리(또는 6자리) 문자열로 맞춤 (zfill)
            df_listed['회사코드'] = df_listed['회사코드'].astype(str).str.zfill(6)
        return df_svc, df_listed
    except Exception as e:
        st.error(f"CSV 로드 에러: {e}")
        return pd.DataFrame(), pd.DataFrame()

df_svc, df_listed = load_data()

# --- 2. 날짜 설정 ---
selected_date = st.date_input("조회일자 선택", value=datetime.today())
today_str = selected_date.strftime("%Y-%m-%d")

# --- 3. 정교한 크롤링 엔진 (403 방어용 헤더 및 세션) ---
def get_kind_data(date_str):
    main_url = "https://kind.krx.co.kr/disclosure/todaydisclosure.do"
    ajax_url = "https://kind.krx.co.kr/disclosure/todaydisclosure.do"
    
    # 브라우저처럼 보이기 위한 헤더 설정
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Accept": "text/html, */*; q=0.01",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Origin": "https://kind.krx.co.kr",
        "Referer": "https://kind.krx.co.kr/disclosure/todaydisclosure.do",
        "X-Requested-With": "XMLHttpRequest"
    }

    session = requests.Session()
    
    try:
        # Step 1: 메인 페이지 접속으로 쿠키 획득
        session.get(main_url, headers=headers, timeout=10)
        time.sleep(random.uniform(0.5, 1.2)) 

        # Step 2: POST 요청 데이터 설정
        payload = {
            "method": "searchTodayDisclosureSub",
            "currentPageSize": 100,
            "pageIndex": 1,
            "orderMode": "0",
            "orderStat": "D",
            "forward": "todaydisclosure_sub",
            "marketType": "1", # 1: 코스피
            "selDate": date_str
        }
        
        response = session.post(ajax_url, data=payload, headers=headers, timeout=10)
        response.raise_for_status()
        
        # Step 3: BeautifulSoup 파싱
        soup = BeautifulSoup(response.text, 'html.parser')
        rows = []
        table = soup.find('table', class_='list type-00 mt10')
        
        if not table:
            return pd.DataFrame()

        tbody = table.find('tbody')
        if not tbody:
            return pd.DataFrame()

        for tr in tbody.find_all('tr'):
            tds = tr.find_all('td')
            if len(tds) < 5 or "결과가 없습니다" in tr.text:
                continue
            
            # 회사코드 추출 (JavaScript 함수 인자에서 추출)
            comp_a = tds[1].find('a')
            comp_code = ""
            if comp_a and comp_a.has_attr('onclick'):
                code_match = re.search(r"companysummary_open\('(\d+)'\)", comp_a['onclick'])
                if code_match: 
                    comp_code = code_match.group(1).zfill(6)
            
            # 공시 제목 및 상세 URL용 acpt_no 추출
            title_a = tds[2].find('a')
            title = title_a.get('title', '').strip() if title_a else ""
            
            acpt_no = ""
            if title_a and title_a.has_attr('onclick'):
                no_match = re.search(r"openDisclsViewer\('(\d+)'", title_a['onclick'])
                if no_match: 
                    acpt_no = no_match.group(1)
            
            rows.append({
                '시간': tds[0].text.strip(),
                '회사코드': comp_code,
                '회사명': tds[1].text.strip(),
                '공시제목': title,
                '제출인': tds[3].text.strip(),
                '상세URL': f"https://kind.krx.co.kr/common/disclsviewer.do?method=search&acptno={acpt_no}" if acpt_no else ""
            })
            
        return pd.DataFrame(rows)

    except Exception as e:
        st.error(f"데이터를 가져오는 중 오류가 발생했습니다: {e}")
        return pd.DataFrame()

# --- 4. 메인 화면 로직 ---
if st.button('🚀 번역대상 공시 필터링 시작'):
    if df_svc.empty or df_listed.empty:
        st.warning("CSV 파일 로드 상태를 확인해 주세요. (파일명: kospi_format.csv, kospi_company.csv)")
    else:
        with st.spinner('KIND 서버에서 공시를 분석 중입니다...'):
            df_raw = get_kind_data(today_str)
            
            if df_raw.empty:
                st.info("조회된 공시가 없거나 접근이 차단되었습니다.")
            else:
                # 필터링 기준 준비
                target_forms = df_svc['서식명'].unique().tolist()
                target_codes = df_listed['회사코드'].tolist()

                # 필터링 함수
                def check_target(row):
                    title = row['공시제목']
                    code = row['회사코드']
                    
                    # 노이즈 제거: 추가/변경상장 등 제외
                    if title.startswith(("추가상장", "변경상장")): 
                        return False
                    
                    # 서식명 포함 여부 및 대상 회사 코드 일치 여부 확인
                    is_target_form = any(f in title for f in target_forms)
                    is_target_company = code in target_codes
