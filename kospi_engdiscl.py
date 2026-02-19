import streamlit as st

import pandas as pd

import requests

from bs4 import BeautifulSoup

import re

from datetime import datetime, timedelta

import time



# 페이지 설정

st.set_page_config(

    page_title="오늘의 코스피 번역대상 공시",

    layout="wide",

    initial_sidebar_state="collapsed"

)



# 공통 헤더 설정 (브라우저인 척 하여 차단 방지)

HEADERS = {

    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",

    "Referer": "https://kind.krx.co.kr/disclosure/todaydisclosure.do"

}



# 제목 설정

st.title('오늘의 코스피 번역대상 공시')



# --- 데이터 로드 함수 ---

@st.cache_data

def load_kospi_format_data():

    try:

        df = pd.read_csv("kospi_format.csv", dtype=str)

        return df

    except Exception as e:

        st.error(f"공시서식 데이터 로드 오류: {e}")

        return pd.DataFrame()



@st.cache_data

def load_kospi_company_data():

    try:

        df = pd.read_csv("kospi_company.csv", dtype=str)

        return df

    except Exception as e:

        st.error(f"회사 데이터 로드 오류: {e}")

        return pd.DataFrame()



df_svc = load_kospi_format_data()

df_listed = load_kospi_company_data()



if not df_listed.empty:

    df_listed['회사코드'] = df_listed['회사코드'].astype(str).str.zfill(5)



# 상단 정보 표시

col1, col2 = st.columns(2)

with col1:

    st.subheader('지원대상 공시서식')

    if not df_svc.empty:

        st.write(f'{len(df_svc)}개')

        st.dataframe(df_svc, use_container_width=True)

    else:

        st.warning("공시서식 데이터를 불러올 수 없습니다.")



with col2:

    st.subheader('지원대상 회사 목록')

    if not df_listed.empty:

        st.write(f'{len(df_listed)}사')

        st.dataframe(df_listed, use_container_width=True)

    else:

        st.warning("회사 목록 데이터를 불러올 수 없습니다.")



# --- 날짜 설정 ---

def get_default_date():

    today = datetime.today()

    if today.weekday() in [5, 6]:

        return (today - timedelta(days=today.weekday() - 4)).strftime("%Y-%m-%d")

    return today.strftime("%Y-%m-%d")



st.subheader('조회일자 선택')

selected_date = st.date_input(

    "조회할 날짜를 선택하세요",

    value=datetime.strptime(get_default_date(), "%Y-%m-%d"),

    min_value=datetime(2020, 1, 1),

    max_value=datetime.today()

)

today_date = selected_date.strftime("%Y-%m-%d")



# --- 데이터 수집 로직 ---

if st.button('코스피 영문공시 지원대상 공시조회'):

    if df_svc.empty or df_listed.empty:

        st.error("필요한 데이터를 불러올 수 없습니다. CSV 파일을 확인해주세요.")

        st.stop()

    

    with st.spinner('데이터를 가져오는 중입니다...'):

        all_data = []

        url = 'https://kind.krx.co.kr/disclosure/todaydisclosure.do'

        

        def get_page_data(page_num):

            params = {

                "method": "searchTodayDisclosureSub",

                "currentPageSize": 100,

                "pageIndex": page_num,

                "marketType": 1,

                "forward": "todaydisclosure_sub",

                "selDate": today_date,

            }

            try:

                # 헤더 추가

                response = requests.post(url, params=params, headers=HEADERS)

                response.raise_for_status()

                return BeautifulSoup(response.text, 'html.parser')

            except Exception as e:

                st.error(f"페이지 {page_num} 요청 중 오류 발생: {e}")

                return None



        def parse_table(soup):

            data = []

            table = soup.find('table', class_='list type-00 mt10')

            if table and table.find('tbody'):

                for row in table.find('tbody').find_all('tr'):

                    cols = row.find_all('td')

                    if len(cols) >= 5 and not "조회 결과가 없습니다" in row.text:

                        time_str = cols[0].text.strip()

                        company_a_tag = cols[1].find('a', id='companysum')

                        company = company_a_tag.text.strip() if company_a_tag else ""

                        

                        company_code = ""

                        if company_a_tag and company_a_tag.has_attr('onclick'):

                            code_match = re.search(r"companysummary_open\('(\d+)'\)", company_a_tag['onclick'])

                            if code_match: company_code = code_match.group(1)

                        

                        title_a_tag = cols[2].find('a')

                        title = title_a_tag.get('title', "").strip() if title_a_tag else ""

                        

                        note = ""

                        if title_a_tag:

                            font_tags = title_a_tag.find_all('font')

                            note = "_".join([f.text.strip() for f in font_tags])

                        

                        submitter = cols[3].text.strip()

                        discl_url = ""

                        if title_a_tag and title_a_tag.has_attr('onclick'):

                            match = re.search(r"openDisclsViewer\('(\d+)'", title_a_tag['onclick'])

                            if match:

                                discl_url = f"https://kind.krx.co.kr/common/disclsviewer.do?method=search&acptno={match.group(1)}"

                        

                        data.append({

                            '시간': time_str, '회사코드': company_code, '회사명': company,

                            '비고': note, '공시제목': title, '제출인': submitter, '상세URL': discl_url

                        })

            return data



        # 첫 페이지 시도

        soup = get_page_data(1)

        if not soup:

            st.stop()



        # --- 수정된 핵심 로직: 안전하게 총 페이지 추출 ---

        info_element = soup.select_one('.info.type-00')

        total_pages = 0

        

        if info_element:

            total_pages_text = info_element.text.strip()

            total_pages_match = re.search(r'(\d+)/(\d+)', total_pages_text)

            total_items_element = info_element.select_one('em')

            

            if total_items_element and total_pages_match:

                total_items = int(total_items_element.text.strip().replace(",",""))

                total_pages = int(total_pages_match.group(2))

                st.info(f"조회일에 총 {total_items}건의 공시가 있습니다. (총 {total_pages}페이지)")

                all_data.extend(parse_table(soup))

            else:

                st.warning("공시 내역은 있으나 페이지 정보를 읽을 수 없습니다.")

        else:

            st.warning(f"{today_date}에는 조회된 공시가 없습니다.")



        # 여러 페이지 처리

        if total_pages > 1:

            progress_bar = st.progress(0)

            for i, page in enumerate(range(2, total_pages + 1)):

                p_soup = get_page_data(page)

                if p_soup:

                    all_data.extend(parse_table(p_soup))

                progress_bar.progress((i + 1) / (total_pages - 1))

                time.sleep(0.3)



        # 결과 필터링 및 출력

        if all_data:

            df_discl = pd.DataFrame(all_data)

            form_names = df_svc['서식명'].unique().tolist()

            listed_codes = df_listed['회사코드'].tolist()



            def is_target(title):

                if not title or title.startswith(("추가상장", "변경상장")): return False

                return any(name in title for name in form_names)



            filtered_df = df_discl[df_discl['공시제목'].apply(is_target)]

            filtered_df = filtered_df[filtered_df['회사코드'].isin(listed_codes)]



            st.subheader('코스피 지원대상 공시 목록')

            if not filtered_df.empty:

                st.write(f"총 {len(filtered_df)}건 검색됨")

                st.dataframe(filtered_df, column_config={"상세URL": st.column_config.LinkColumn("상세URL")}, hide_index=True, use_container_width=True)

            else:

                st.warning("지원 대상인 공시가 없습니다.")

        else:

            if total_pages > 0: st.warning("데이터 파싱에 실패했거나 공시가 없습니다.")



# 사이드바 설정

if st.sidebar.button("📊 데이터 새로고침"):

    st.cache_data.clear()

    st.rerun()
