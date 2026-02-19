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



# 제목 설정

st.title('오늘의 코스피 번역대상 공시')



# --- 1. 데이터 로드 함수 (캐싱) ---

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



# 상단 대시보드

col1, col2 = st.columns(2)

with col1:

    st.subheader('지원대상 공시서식')

    if not df_svc.empty:

        st.write(f'{len(df_svc)}개')

        st.dataframe(df_svc, use_container_width=True)



with col2:

    st.subheader('지원대상 회사 목록')

    if not df_listed.empty:

        st.write(f'{len(df_listed)}사')

        st.dataframe(df_listed, use_container_width=True)



# --- 2. 날짜 설정 및 조회 ---

def get_default_date():

    today = datetime.today()

    if today.weekday() in [5, 6]:  # 토요일(5), 일요일(6)

        return (today - timedelta(days=today.weekday() - 4)).strftime("%Y-%m-%d")

    return today.strftime("%Y-%m-%d")



st.subheader('조회일자 선택')

selected_date = st.date_input(

    "조회할 날짜를 선택하세요",

    value=datetime.strptime(get_default_date(), "%Y-%m-%d")

)

today_date = selected_date.strftime("%Y-%m-%d")



# --- 3. 크롤링 엔진 (세션 유지 및 403 방어) ---

if st.button('코스피 영문공시 지원대상 공시조회'):

    if df_svc.empty or df_listed.empty:

        st.error("CSV 파일(kospi_format.csv, kospi_company.csv)을 확인해주세요.")

        st.stop()

    

    with st.spinner('KIND 서버에 접속 중입니다...'):

        all_data = []

        

        # 세션 생성 및 브라우저 헤더 설정

        session = requests.Session()

        headers = {

            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",

            "Accept": "text/html, */*; q=0.01",

            "Origin": "https://kind.krx.co.kr",

            "Referer": "https://kind.krx.co.kr/disclosure/todaydisclosure.do",

            "X-Requested-With": "XMLHttpRequest",

            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"

        }



        def get_page_data(page_num):

            url = 'https://kind.krx.co.kr/disclosure/todaydisclosure.do'

            data = {

                "method": "searchTodayDisclosureSub",

                "currentPageSize": 100,

                "pageIndex": page_num,

                "marketType": 1,

                "forward": "todaydisclosure_sub",

                "selDate": today_date,

            }

            try:

                # 1단계: 첫 페이지 조회 시 메인 접속하여 쿠키 생성

                if page_num == 1:

                    session.get(url, headers=headers)

                

                # 2단계: 실제 데이터 요청 (POST 사용)

                resp = session.post(url, data=data, headers=headers)

                resp.raise_for_status()

                return BeautifulSoup(resp.text, 'html.parser')

            except Exception as e:

                st.error(f"[KIND 요청 오류] page={page_num}, date={today_date} / {e}")

                return None



        def parse_table(soup):

            rows_data = []

            table = soup.find('table', class_='list type-00 mt10')

            if not table: return rows_data

            

            tbody = table.find('tbody')

            if not tbody: return rows_data

            

            for row in tbody.find_all('tr'):

                cols = row.find_all('td')

                if len(cols) >= 5 and "결과가 없습니다" not in row.text:

                    # 시간

                    time_val = cols[0].text.strip()

                    # 회사정보

                    a_comp = cols[1].find('a')

                    comp_name = a_comp.text.strip() if a_comp else ""

                    comp_code = ""

                    if a_comp and a_comp.has_attr('onclick'):

                        m = re.search(r"companysummary_open\('(\d+)'\)", a_comp['onclick'])

                        if m: comp_code = m.group(1)

                    

                    # 제목 및 URL

                    a_title = cols[2].find('a')

                    title_val = a_title.get('title', "").strip() if a_title else ""

                    url_val = ""

                    if a_title and a_title.has_attr('onclick'):

                        m = re.search(r"openDisclsViewer\('(\d+)'", a_title['onclick'])

                        if m: url_val = f"https://kind.krx.co.kr/common/disclsviewer.do?method=search&acptno={m.group(1)}"

                    

                    # 비고 (전환사채 등)

                    note_val = "_".join([f.text.strip() for f in a_title.find_all('font')]) if a_title else ""

                    # 제출인

                    submitter_val = cols[3].text.strip()

                    

                    rows_data.append({

                        '시간': time_val, '회사코드': comp_code, '회사명': comp_name,

                        '비고': note_val, '공시제목': title_val, '제출인': submitter_val, '상세URL': url_val

                    })

            return rows_data



        # 첫 페이지 시도

        first_soup = get_page_data(1)

        if first_soup:

            info_el = first_soup.select_one('.info.type-00')

            total_pages = 0

            

            if info_el:

                txt = info_el.text.strip()

                match = re.search(r'(\d+)/(\d+)', txt)

                items_el = info_el.select_one('em')

                

                if items_el and match:

                    t_items = int(items_el.text.strip().replace(",",""))

                    total_pages = int(match.group(2))

                    st.success(f"총 {t_items}건의 공시가 검색되었습니다. ({total_pages}페이지 추출 시작)")

                    all_data.extend(parse_table(first_soup))

                else:

                    st.warning("공시는 있으나 페이지 정보 형식이 다릅니다.")

            else:

                st.info(f"{today_date}에는 조회된 공시가 없습니다.")



            # 추가 페이지 수집

            if total_pages > 1:

                prog = st.progress(0)

                for i, p in enumerate(range(2, total_pages + 1)):

                    p_soup = get_page_data(p)

                    if p_soup:

                        all_data.extend(parse_table(p_soup))

                    prog.progress((i + 1) / (total_pages - 1))

                    time.sleep(0.5) # 차단 방지를 위한 휴식



        # --- 4. 필터링 및 결과 출력 ---

        if all_data:

            df_res = pd.DataFrame(all_data)

            target_forms = df_svc['서식명'].unique().tolist()

            target_codes = df_listed['회사코드'].tolist()



            def filter_logic(row):

                title = row['공시제목']

                code = row['회사코드']

                if not title or title.startswith(("추가상장", "변경상장")): return False

                # 서식명 포함 확인 및 회사코드 일치 확인

                is_form = any(f in title for f in target_forms)

                is_comp = code in target_codes

                return is_form and is_comp



            final_df = df_res[df_res.apply(filter_logic, axis=1)]



            st.subheader('🎯 코스피 영문공시 지원대상 결과')

            if not final_df.empty:

                st.write(f"조건에 맞는 공시 {len(final_df)}건을 찾았습니다.")

                st.dataframe(

                    final_df,

                    column_config={"상세URL": st.column_config.LinkColumn("공시링크")},

                    hide_index=True, 

                    use_container_width=True

                )

            else:

                st.warning("지원 대상인 공시가 없습니다. (날짜나 대상 목록을 확인하세요)")



# 사이드바 관리

st.sidebar.markdown("### 관리 메뉴")

if st.sidebar.button("♻️ 데이터 초기화"):

    st.cache_data.clear()

    st.rerun()
