import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import time
import random

# 1. 페이지 설정
st.set_page_config(page_title="코스피 영문공시 필터링 도구", layout="wide")

# --- [UI] 사이드바 공지사항 ---
with st.sidebar:
    st.markdown("## 🚨 중요 공지")
    st.warning(
        """
        **본 사이트는 실시간 데이터를 참조하므로, 트래픽 집중 시 외부 서버로부터 일시적 차단이 발생할 수 있습니다.** 안정적인 서비스 이용을 위해 **총 3개의 사이트**를 운영 중이니, 장애 발생 시 다른 주소로 접속해 보시기 바랍니다.
        
        ---
        **🔗 이용 가능한 사이트 목록**
        1. https://englishkind.streamlit.app/
        2. https://english-kospi.streamlit.app/
        3. https://englishkospi.streamlit.app/
        """
    )
    st.markdown("---")

st.title('🎯 오늘의 코스피 번역대상 공시 조회')
st.markdown("---")

# 2. 데이터 로드 (CSV)
@st.cache_data
def load_reference_data():
    try:
        # 파일이 없을 경우를 대비해 예외처리 강화
        df_svc = pd.read_csv("kospi_format.csv", dtype=str)
        df_listed = pd.read_csv("kospi_company.csv", dtype=str)
        
        if not df_listed.empty and '회사코드' in df_listed.columns:
            df_listed['회사코드'] = df_listed['회사코드'].astype(str).str.zfill(6)
            
        return df_svc, df_listed
    except Exception as e:
        # 에러 발생 시 빈 데이터프레임 반환
        return pd.DataFrame(), pd.DataFrame()

df_svc, df_listed = load_reference_data()

# --- 3. 상단 기준 데이터 표시 (구조 분리) ---
col_ref1, col_ref2 = st.columns(2)

with col_ref1:
    st.subheader("📋 지원대상 공시서식")
    if not df_svc.empty:
        st.caption(f"총 {len(df_svc)}개의 서식 필터링 중")
        st.dataframe(df_svc, use_container_width=True, height=200)
    else:
        st.error("❌ 'kospi_format.csv' 파일을 찾을 수 없습니다.")

with col_ref2:
    st.subheader("🏢 지원대상 회사목록")
    if not df_listed.empty:
        st.caption(f"총 {len(df_listed)}개의 상장법인 등록됨")
        st.dataframe(df_listed, use_container_width=True, height=200)
    else:
        st.error("❌ 'kospi_company.csv' 파일을 찾을 수 없습니다.")

st.markdown("---")

# 4. 날짜 설정 및 조회 버튼 (데이터 유무와 상관없이 표시되도록 배치)
selected_date = st.date_input("📅 조회일자 선택", value=datetime.today())
today_str = selected_date.strftime("%Y-%m-%d")

# 5. 크롤링 엔진
def get_all_kind_data(date_str):
    main_url = "https://kind.krx.co.kr/disclosure/todaydisclosure.do"
    ajax_url = "https://kind.krx.co.kr/disclosure/todaydisclosure.do"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Referer": main_url,
        "X-Requested-With": "XMLHttpRequest"
    }
    session = requests.Session()
    all_rows = []
    
    try:
        session.get(main_url, headers=headers, timeout=10)
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
        
        first_resp = session.post(ajax_url, data=payload, headers=headers, timeout=10)
        soup = BeautifulSoup(first_resp.text, 'html.parser')
        
        info_text = soup.select_one('.info.type-00')
        total_pages = 1
        if info_text:
            page_match = re.search(r'/(\d+)', info_text.text)
            if page_match:
                total_pages = int(page_match.group(1))

        progress_bar = st.progress(0)
        status_text = st.empty()

        for page in range(1, total_pages + 1):
            status_text.text(f"⏳ {total_pages}페이지 중 {page}페이지 분석 중...")
            payload["pageIndex"] = page
            resp = session.post(ajax_url, data=payload, headers=headers, timeout=10)
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
                    if code_match: comp_code = code_match.group(1).zfill(6)
                
                title_a = tds[2].find('a')
                title = title_a.get('title', '').strip() if title_a else tds[2].text.strip()
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
            progress_bar.progress(page / total_pages)
            time.sleep(random.uniform(0.3, 0.5))
            
        status_text.empty()
        progress_bar.empty()
        return pd.DataFrame(all_rows)
    except Exception as e:
        st.error(f"❌ 데이터 수집 오류: {e}")
        return pd.DataFrame()

# 6. 실행 버튼 (가장 중요한 부분: 조건을 버튼 안으로 넣었습니다)
if st.button('🚀 영문공시 지원대상 필터링 실행'):
    if df_svc.empty or df_listed.empty:
        st.error("❌ 기준 CSV 데이터가 로드되지 않았습니다. 파일이 깃허브(또는 서버)에 있는지 확인해주세요.")
    else:
        with st.spinner(f'{today_str} 공시를 전수 조사하는 중입니다...'):
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

                st.subheader(f"📊 필터링 결과 (대상: {len(final_df)}건)")
                if not final_df.empty:
                    final_df = final_df.sort_values(by='시간')
                    st.dataframe(
                        final_df[['시간', '회사명', '공시제목', '제출인', '상세URL']],
                        column_config={"상세URL": st.column_config.LinkColumn("공시보기")},
                        hide_index=True,
                        use_container_width=True
                    )
                else:
                    st.info(f"{today_str} 기준, 조건에 맞는 공시가 없습니다.")
            else:
                st.warning("데이터를 가져오지 못했습니다. 잠시 후 다시 시도해 주세요.")
