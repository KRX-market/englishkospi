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



st.title('🎯 오늘의 코스피 번역대상 공시 조회')

st.markdown("---")



# 2. 데이터 로드 (CSV)

@st.cache_data

def load_reference_data():

    try:

        # 파일명이 정확한지 확인하세요

        df_svc = pd.read_csv("kospi_format.csv", dtype=str)

        df_listed = pd.read_csv("kospi_company.csv", dtype=str)

        

        # 회사코드 5자리 자릿수 맞추기 (00010 등)

        if not df_listed.empty and '회사코드' in df_listed.columns:

            df_listed['회사코드'] = df_listed['회사코드'].astype(str).str.zfill(5)

            

        return df_svc, df_listed

    except Exception as e:

        st.error(f"⚠️ CSV 파일을 불러오는 중 오류가 발생했습니다: {e}")

        return pd.DataFrame(), pd.DataFrame()



df_svc, df_listed = load_reference_data()



# --- [추가된 부분] 상단 기준 데이터 표시 레이아웃 ---

if not df_svc.empty and not df_listed.empty:

    col_ref1, col_ref2 = st.columns(2)

    

    with col_ref1:

        st.subheader("📋 지원대상 공시서식")

        st.caption(f"총 {len(df_svc)}개의 서식을 번역 중입니다.")

        st.dataframe(df_svc, use_container_width=True, height=200)

        

    with col_ref2:

        st.subheader("🏢 지원대상 회사목록")

        st.caption(f"총 {len(df_listed)}개의 상장법인이 등록되어 있습니다.")

        st.dataframe(df_listed, use_container_width=True, height=200)

else:

    st.warning("⚠️ 기준 데이터(CSV)가 비어있거나 불러오지 못했습니다. 파일명을 확인해 주세요.")



st.markdown("---")



# 3. 날짜 설정 및 사용자 입력

selected_date = st.date_input("📅 조회일자 선택", value=datetime.today())

today_str = selected_date.strftime("%Y-%m-%d")



# 4. 크롤링 엔진 (403 방어형)

def get_kind_data(date_str):

    main_url = "https://kind.krx.co.kr/disclosure/todaydisclosure.do"

    ajax_url = "https://kind.krx.co.kr/disclosure/todaydisclosure.do"

    

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

        # Step 1: 통행증(쿠키) 획득

        session.get(main_url, headers=headers, timeout=10)

        time.sleep(random.uniform(0.3, 0.7))



        # Step 2: 데이터 요청

        payload = {

            "method": "searchTodayDisclosureSub",

            "currentPageSize": 100,

            "pageIndex": 1,

            "orderMode": "0",

            "orderStat": "D",

            "forward": "todaydisclosure_sub",

            "marketType": "1", # 코스피

            "selDate": date_str

        }

        

        response = session.post(ajax_url, data=payload, headers=headers, timeout=10)

        response.raise_for_status()

        

        # Step 3: 파싱

        soup = BeautifulSoup(response.text, 'html.parser')

        rows = []

        table = soup.find('table', class_='list type-00 mt10')

        

        if not table: return pd.DataFrame()



        for tr in table.find('tbody').find_all('tr'):

            tds = tr.find_all('td')

            if len(tds) < 5 or "결과가 없습니다" in tr.text: continue

            

            # 회사코드 추출

            comp_a = tds[1].find('a')

            comp_code = ""

            if comp_a and comp_a.has_attr('onclick'):

                code_match = re.search(r"companysummary_open\('(\d+)'\)", comp_a['onclick'])

                if code_match: comp_code = code_match.group(1)

            

            # 제목 및 URL 추출

            title_a = tds[2].find('a')

            title = title_a.get('title', '').strip() if title_a else ""

            acpt_no = ""

            if title_a and title_a.has_attr('onclick'):

                no_match = re.search(r"openDisclsViewer\('(\d+)'", title_a['onclick'])

                if no_match: acpt_no = no_match.group(1)

            

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

        st.error(f"❌ KIND 서버 접속 중 오류: {e}")

        return pd.DataFrame()



# 5. 실행 버튼 및 결과 출력

if st.button('🚀 영문공시 지원대상 필터링 실행'):

    if df_svc.empty or df_listed.empty:

        st.error("기준 데이터가 없어 실행할 수 없습니다.")

    else:

        with st.spinner('실시간 공시 데이터를 분석하고 있습니다...'):

            df_raw = get_kind_data(today_str)

            

            if df_raw.empty:

                st.info("조회된 공시가 없거나 접근이 제한되었습니다. 잠시 후 다시 시도해 주세요.")

            else:

                # 필터링

                target_forms = df_svc['서식명'].unique().tolist()

                target_codes = df_listed['회사코드'].tolist()



                def filter_logic(row):

                    title = row['공시제목']

                    code = row['회사코드']

                    # 제외 키워드

                    if title.startswith(("추가상장", "변경상장")): return False

                    # 서식명 및 회사코드 매칭

                    return any(f in title for f in target_forms) and (code in target_codes)



                final_df = df_raw[df_raw.apply(filter_logic, axis=1)]



                st.subheader(f"📊 필터링 결과 (대상: {len(final_df)}건)")

                if not final_df.empty:

                    st.dataframe(

                        final_df[['시간', '회사명', '공시제목', '제출인', '상세URL']],

                        column_config={"상세URL": st.column_config.LinkColumn("공시보기")},

                        hide_index=True,

                        use_container_width=True

                    )

                else:

                    st.info("오늘 현재까지 지원 대상에 해당하는 공시는 없습니다.")

import streamlit as st
# ... (기타 임포트 생략)

# 1. 페이지 설정
st.set_page_config(page_title="코스피 영문공시 필터링 도구", layout="wide")

# --- [추가된 부분] 사이드바 공지사항 ---
with st.sidebar:
    st.header("📢 공지사항")
    st.warning(
        """
        **해당 사이트 오류로 인해 새로운 사이트를 개설하였습니다.** 앞으로 아래 사이트를 이용 부탁드립니다.
        
        * https://englishkind.streamlit.app/
        * https://english-kospi.streamlit.app/
        """
    )
    st.markdown("---")
