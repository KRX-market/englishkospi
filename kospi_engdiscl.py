import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, timedelta
import time

# 페이지 설정 (wide 모드로 설정)
st.set_page_config(
    page_title="오늘의 코스피 번역대상 공시",
    layout="wide",  # 화면을 넓게 사용
    initial_sidebar_state="collapsed"  # 사이드바 초기 상태를 접힌 상태로 설정
)

# 제목 설정
st.title('오늘의 코스피 번역대상 공시')

#-----------------------------------------------------------
# CSV 파일에서 데이터 로드
#-----------------------------------------------------------

# 공시서식 데이터 로드 함수
@st.cache_data
def load_kospi_format_data():
    try:
        df = pd.read_csv("kospi_format.csv", dtype=str)
        return df
    except Exception as e:
        st.error(f"공시서식 데이터 로드 오류: {e}")
        return pd.DataFrame()

# 회사 데이터 로드 함수
@st.cache_data
def load_kospi_company_data():
    try:
        df = pd.read_csv("kospi_company.csv", dtype=str)
        return df
    except Exception as e:
        st.error(f"회사 데이터 로드 오류: {e}")
        return pd.DataFrame()
 

# 데이터 로드
df_svc = load_kospi_format_data()
df_listed = load_kospi_company_data()
df_listed['회사코드'] = df_listed['회사코드'].astype(str).str.zfill(6)

# 2개의 칼럼 생성 (업로드 섹션 제거)
col1, col2 = st.columns(2)

# 첫번째 칼럼: 지원대상공시서식기준
with col1:
    st.subheader('지원대상 공시서식')
    if not df_svc.empty:
        st.write(f'{len(df_svc)}개')
        st.dataframe(df_svc, use_container_width=True)
    else:
        st.warning("공시서식 데이터를 불러올 수 없습니다.")

# 두번째 칼럼: 지원대상 회사목록
with col2:
    st.subheader('지원대상 회사 목록')
    if not df_listed.empty:
        st.write(f'{len(df_listed)}사')
        st.dataframe(df_listed, use_container_width=True)
    else:
        st.warning("회사 목록 데이터를 불러올 수 없습니다.")

# 날짜 계산 함수
def get_default_date():
    today = datetime.today()
    if today.weekday() in [5, 6]:  # 토요일(5) 또는 일요일(6)
        return (today - timedelta(days=today.weekday() - 4)).strftime("%Y-%m-%d")  # 직전 금요일
    return today.strftime("%Y-%m-%d")  # 오늘 날짜

# 제목
st.subheader('조회일자 선택')

# 날짜 선택 위젯 추가
selected_date = st.date_input(
    "조회할 날짜를 선택하세요",
    value=datetime.strptime(get_default_date(), "%Y-%m-%d"),
    min_value=datetime(2020, 1, 1),  # 최소 선택 가능 날짜
    max_value=datetime.today()       # 최대 선택 가능 날짜
)

# 선택된 날짜를 YYYY-MM-DD 형식으로 변환
today_date = selected_date.strftime("%Y-%m-%d")
        
# 버튼 생성
if st.button('코스피 영문공시 지원대상 공시조회'):
    # 데이터가 로드되었는지 확인
    if df_svc.empty or df_listed.empty:
        st.error("필요한 데이터를 불러올 수 없습니다. CSV 파일을 확인해주세요.")
        st.stop()
    
    # 로딩 표시
    with st.spinner('데이터를 가져오는 중입니다...'):
        
        # 모든 페이지의 데이터를 저장할 빈 리스트
        all_data = []
        
        # 페이지별 데이터 수집 함수
        def get_page_data(page_num):
            url = 'https://kind.krx.co.kr/disclosure/todaydisclosure.do'
            params = {
                "method": "searchTodayDisclosureSub",
                "currentPageSize": 100,
                "pageIndex": page_num,
                "orderMode": 0,
                "orderStat": "D",
                "marketType": 1,
                "forward": "todaydisclosure_sub",
                "searchMode": "",
                "searchCodeType": "",
                "chose": "S",
                "todayFlag": "Y",
                "repIsuSrtCd": "",
                "kosdaqSegment": "",
                "selDate": today_date,
                "searchCorpName": "",
                "copyUrl": ""
            }

            try:
                response = requests.post(url, params=params)
                response.raise_for_status()
                return BeautifulSoup(response.text, 'html.parser')
            except Exception as e:
                st.error(f"페이지 {page_num} 요청 중 오류 발생: {e}")
                return None

        # 데이터 파싱 함수
        def parse_table(soup):
            data = []
            table = soup.find('table', class_='list type-00 mt10')
            
            if table and table.find('tbody'):
                for row in table.find('tbody').find_all('tr'):
                    cols = row.find_all('td')
                    
                    if len(cols) >= 5:
                        # 필요한 데이터 추출 (원본 코드와 동일)
                        time = cols[0].text.strip()
                        
                        company_a_tag = cols[1].find('a', id='companysum')
                        company = company_a_tag.text.strip() if company_a_tag else ""
                        
                        company_code = ""
                        if company_a_tag and company_a_tag.has_attr('onclick'):
                            onclick_attr = company_a_tag['onclick']
                            code_match = re.search(r"companysummary_open\('([A-Za-z0-9]+)'\)", onclick_attr)
                            if code_match:
                                company_code = code_match.group(1)
                        
                        title_a_tag = cols[2].find('a')
                        title = ""
                        note = ""
                        
                        if title_a_tag:
                            title = title_a_tag.get('title', "").strip()
                            
                            font_tags = title_a_tag.find_all('font')
                            if font_tags:
                                notes = []
                                for font_tag in font_tags:
                                    notes.append(font_tag.text.strip())
                                note = "_".join(notes)
                        
                        submitter = cols[3].text.strip()
                        
                        discl_url = ""
                        if title_a_tag and title_a_tag.has_attr('onclick'):
                            onclick_attr = title_a_tag['onclick']
                            match = re.search(r"openDisclsViewer\('(\d+)'", onclick_attr)
                            if match:
                                acptno = match.group(1)
                                discl_url = f"https://kind.krx.co.kr/common/disclsviewer.do?method=search&acptno={acptno}&docno=&viewerhost=&viewerport="
                        
                        data.append({
                            '시간': time,
                            '회사코드': company_code,
                            '회사명': company,
                            '비고': note,
                            '공시제목': title,
                            '제출인': submitter,
                            '상세URL': discl_url
                        })
            return data

        # 첫 페이지 요청 및 데이터 처리
        url = 'https://kind.krx.co.kr/disclosure/todaydisclosure.do'
        params = {
            "method": "searchTodayDisclosureSub",
            "currentPageSize": 100,
            "pageIndex": 1,
            "orderMode": 0,
            "orderStat": "D",
            "marketType": 1,
            "forward": "todaydisclosure_sub",
            "searchMode": "",
            "searchCodeType": "",
            "chose": "S",
            "todayFlag": "Y",
            "repIsuSrtCd": "",
            "kosdaqSegment": "",
            "selDate": today_date,
            "searchCorpName": "",
            "copyUrl": ""
        }

        response = requests.post(url, params=params)
        soup = BeautifulSoup(response.text, 'html.parser')

        # 총 건수와 페이지 수 추출
        total_items_element = soup.select_one('.info.type-00 em')
        total_pages_text = soup.select_one('.info.type-00').text.strip()
        total_pages_match = re.search(r'(\d+)/(\d+)', total_pages_text)

        if total_items_element and total_pages_match:
            total_items = int(total_items_element.text.strip().replace(",",""))
            total_pages = int(total_pages_match.group(2))
            
            st.info(f"조회일에 총 {total_items}건의 공시가 있습니다. (총 {total_pages}페이지)    지원대상 공시는 아래 표를 참고해주세요.")
        else:
            st.warning("페이지 정보를 찾을 수 없습니다.")
            total_pages = 1

        # 첫 페이지 데이터 처리
        all_data.extend(parse_table(soup))

        # 페이지가 여러 개인 경우 나머지 페이지 처리
        if total_pages > 1:
            # Streamlit 진행 표시줄
            progress_bar = st.progress(0)
            
            for i, page in enumerate(range(2, total_pages + 1)):
                page_soup = get_page_data(page)
                if page_soup:
                    page_data = parse_table(page_soup)
                    all_data.extend(page_data)
                
                # 진행률 업데이트
                progress = (i + 1) / (total_pages - 1)
                progress_bar.progress(progress)
                
                # 서버 부하를 줄이기 위한 대기 시간
                time.sleep(0.5)

        # 데이터프레임 생성
        df_discl = pd.DataFrame(all_data)
        
        # 필터링 (지원 대상 서식만 필터)
        form_names = df_svc['서식명'].unique().tolist()
        
        # 추가상장이나 변경상장은 제외
        def is_contained(title):
            # 제목이 None 또는 빈 문자열인 경우 제외
            if not title:
                return False
            # '추가상장'이나 '변경상장'으로 시작하면 제외
            if title.startswith("추가상장") or title.startswith("변경상장"):
                return False
            # 그 외엔 form_names가 포함된 경우만 True
            for form_name in form_names:
                if form_name in title:
                    return True
            return False
        
        # 첫 번째 필터링: 지원 대상 서식만 필터
        filtered_df = df_discl[df_discl['공시제목'].apply(is_contained)]
        
        # 두 번째 필터링: 지정된 회사 코드만 필터
        listed_company_codes = df_listed['회사코드'].tolist()
        filtered_df = filtered_df[filtered_df['회사코드'].isin(listed_company_codes)]
        
        # 결과 표시
        st.subheader('코스피 지원대상 공시 목록')
        
        if filtered_df.empty:
            st.warning("조건에 맞는 공시 데이터가 없습니다.")
        else:
            st.write(f"총 {len(filtered_df)}건의 지원대상 공시가 있습니다.")
            
            # URL을 클릭 가능한 링크로 표시
            st.dataframe(
                filtered_df,
                column_config={
                    "상세URL": st.column_config.LinkColumn("상세URL"),
                },
                hide_index=True,
                use_container_width=True
            )

# 데이터 새로고침 버튼 (선택사항)
st.sidebar.markdown("---")
if st.sidebar.button("📊 데이터 새로고침"):
    st.cache_data.clear()
    st.rerun()

st.sidebar.info("💡 CSV 파일에서 데이터를 불러옵니다.")
