import streamlit as st

import pandas as pd

import requests

from bs4 import BeautifulSoup

import re

from datetime import datetime, timedelta

import time

import random



# 1. 페이지 설정

st.set_page_config(page_title="코스피 영문공시 필터링 도구", layout="wide")



st.title('🎯 오늘의 코스피 번역대상 공시 (전체 페이지 조회)')

st.markdown("---")



# 2. 데이터 로드 (CSV)

@st.cache_data

def load_reference_data():

    try:

        df_svc = pd.read_csv("kospi_format.csv", dtype=str)

        df_listed = pd.read_csv("kospi_company.csv", dtype=str)

        if not df_listed.empty and '회사코드' in df_listed.columns:

            df_listed['회사코드'] = df_listed['회사코드'].astype(str).str.zfill(5)

        return df_svc, df_listed

    except Exception as e:

        st.error(f"⚠️ CSV 파일을 불러오는 중 오류 발생: {e}")

        return pd.DataFrame(), pd.DataFrame()



df_svc, df_listed = load_reference_data()



# 상단 기준 데이터 표시

if not df_svc.empty and not df_listed.empty:

    col_ref1, col_ref2 = st.columns(2)

    with col_ref1:

        st.subheader("📋 지원대상 공시서식")

        st.dataframe(df_svc, use_container_width=True, height=180)

    with col_ref2:

        st.subheader("🏢 지원대상 회사목록")

        st.dataframe(df_listed, use_container_width=True, height=180)



st.markdown("---")



# 3. 날짜 설정

selected_date = st.date_input("📅 조회일자 선택", value=datetime.today())

today_str = selected_date.strftime("%Y-%m-%d")



# 4. 멀티 페이지 크롤링 엔진

def get_all_kind_data(date_str):

    main_url = "https://kind.krx.co.kr/disclosure/todaydisclosure.do"

    ajax_url = "https://kind.krx.co.kr/disclosure/todaydisclosure.do"

    

    headers = {

        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",

        "Referer": "https://kind.krx.co.kr/disclosure/todaydisclosure.do",

        "X-Requested-With": "XMLHttpRequest"

    }



    session = requests.Session()

    all_rows = []

    

    try:

        # Step 1: 세션 초기화

        session.get(main_url, headers=headers)

        

        # Step 2: 먼저 1페이지를 가져와서 '전체 페이지 수' 확인

        payload = {

            "method": "searchTodayDisclosureSub",

            "currentPageSize": 100,

            "pageIndex": 1,

            "orderMode": "0",

            "orderStat": "D",

            "forward": "todaydisclosure_sub",

            "marketType": "1",

            "selDate": date_str

        }

        

        first_resp = session.post(ajax_url, data=payload, headers=headers)

        soup = BeautifulSoup(first_resp.text, 'html.parser')

        

        # 전체 페이지 수 추출 (예: 1/3 페이지에서 '3' 추출)

        info_text = soup.select_one('.info.type-00')

        total_pages = 1

        if info_text:

            page_match = re.search(r'/(\d+) 페이지', info_text.text)

            if page_match:

                total_pages = int(page_match.group(1))

        

        # Step 3: 각 페이지 순회하며 데이터 수집

        progress_bar = st.progress(0)

        for page in range(1, total_pages + 1):

            payload["pageIndex"] = page

            resp = session.post(ajax_url, data=payload, headers=headers)

            p_soup = BeautifulSoup(resp.text, 'html.parser')

            

            table = p_soup.find('table', class_='list type-00 mt10')

            if not table: continue

            

            for tr in table.find('tbody').find_all('tr'):

                tds = tr.find_all('td')

                if len(tds) < 5 or "결과가 없습니다" in tr.text: continue

                

                comp_a = tds[1].find('a')

                comp_code = ""

                if comp_a and comp_a.has_attr('onclick'):

                    code_match = re.search(r"companysummary_open\('(\d+)'\)", comp_a['onclick'])

                    if code_match: comp_code = code_match.group(1)

                

                title_a = tds[2].find('a')

                title = title_a.get('title', '').strip() if title_a else ""

                acpt_no = ""

                if title_a and title_a.has_attr('onclick'):

                    no_match = re.search(r"openDisclsViewer\('(\d+)'", title_a['onclick'])

                    if no_match: acpt_no = no_match.group(1)

                

                all_rows.append({

                    '시간': tds[0].text.strip(),

                    '회사코드': comp_code,

                    '회사명': tds[1].text.strip(),

                    '공시제목': title,

                    '제출인': tds[3].text.strip(),

                    '상세URL': f"https://kind.krx.co.kr/common/disclsviewer.do?method=search&acptno={acpt_no}" if acpt_no else ""

                })

            

            # 진행바 업데이트 및 매너 대기

            progress_bar.progress(page / total_pages)

            time.sleep(random.uniform(0.2, 0.5))

            

        return pd.DataFrame(all_rows)



    except Exception as e:

        st.error(f"❌ 데이터 수집 중 오류: {e}")

        return pd.DataFrame()



# 5. 실행 및 필터링

if st.button('🚀 누락 없는 전수 조사 시작'):

    with st.spinner('오늘의 모든 공시 페이지를 확인하고 있습니다...'):

        df_raw = get_all_kind_data(today_str)

        

        if not df_raw.empty:

            target_forms = df_svc['서식명'].unique().tolist()

            target_codes = df_listed['회사코드'].tolist()



            def filter_logic(row):

                title = row['공시제목']

                code = row['회사코드']

                if title.startswith(("추가상장", "변경상장")): return False

                return any(f in title for f in target_forms) and (code in target_codes)



            final_df = df_raw[df_raw.apply(filter_logic, axis=1)]



            st.subheader(f"📊 오늘 전체 공시 {len(df_raw)}건 중 필터링 결과 ({len(final_df)}건)")

            if not final_df.empty:

                st.dataframe(

                    final_df[['시간', '회사명', '공시제목', '제출인', '상세URL']],

                    column_config={"상세URL": st.column_config.LinkColumn("공시보기")},

                    hide_index=True, use_container_width=True

                )

            else:

                st.info("조건에 맞는 공시가 1건도 없습니다.")

        else:

            st.warning("데이터를 가져오지 못했습니다. (휴일이거나 접근 차단)")

