
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

# --- 사이드바 공지사항 (유지) ---
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
        df_svc = pd.read_csv("kospi_format.csv", dtype=str)
        df_listed = pd.read_csv("kospi_company.csv", dtype=str)
        
        if not df_listed.empty and '회사코드' in df_listed.columns:
            # 종목코드는 6자리이므로 zfill(6)으로 수정 권장 (기존 5 유지 시 5로 처리)
            df_listed['회사코드'] = df_listed['회사코드'].astype(str).str.zfill(6)
            
        return df_svc, df_listed
    except Exception as e:
        st.error(f"⚠️ CSV 파일을 불러오는 중 오류가 발생했습니다: {e}")
        return pd.DataFrame(), pd.DataFrame()

df_svc, df_listed = load_reference_data()

# --- 상단 기준 데이터 표시 레이아웃 ---
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

# 3. 날짜 설정
selected_date = st.date_input("📅 조회일자 선택", value=datetime.today())
today_str = selected_date.strftime("%Y-%m-%d")

# 4. 크롤링 엔진 (전체 페이지 순회 로직 복원)
def get_kind_data(date_str):
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
        # Step 1: 세션 초기화 및 전체 페이지 수 확인을 위한 1페이지 호출
        session.get(main_url, headers=headers, timeout=10)
        
        payload = {
            "method": "searchTodayDisclosureSub",
            "currentPageSize": 100,
            "pageIndex": 1,
            "orderMode": "0",
            "orderStat": "D", # 최신순
            "forward": "todaydisclosure_sub",
            "marketType": "1",
            "selDate": date_str
        }
        
        first_resp = session.post(ajax_url, data=payload, headers=headers, timeout=10)
        soup = BeautifulSoup(first_resp.text, 'html.parser')
        
        # 전체 페이지 수 추출
        info_text = soup.select_one('.info.type-00')
        total_pages = 1
        if info_text:
            page_match = re.search(r'/(\d+)', info_text.text)
            if page_match:
                total_pages = int(page_match.group(1))

        # Step 2: 모든 페이지 순회 (오전 데이터 누락 방지 핵심)
        progress_bar = st.progress(0)
        for page in range(1, total_pages + 1):
            payload["pageIndex"] = page
            resp =
