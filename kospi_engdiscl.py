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

# --- [추가] 사이드바 신규 사이트 안내 문구 ---
with st.sidebar:
    st.header("📢 공지사항")
    st.warning(
        """
        해당 사이트 오류로 인해 새로운 사이트를 개설하였습니다. 
        앞으로 아래 사이트 이용 부탁드립니다.
        
        * https://englishkind.streamlit.app/
        * https://english-kospi.streamlit.app/
        """
    )
    st.info("기존 기능은 동일하게 유지됩니다.")
    st.markdown("---")
# ------------------------------------------

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

# 3. 날짜 설정 및 사용자 입력
selected_date = st.date_input("📅 조회일자 선택", value=datetime.today())
today_str = selected_date.strftime("%Y-%m-%d")

# 4. 크롤링 엔진 (403 방어형)
def get_kind_data(date_str):
    main_url = "https://kind.krx.co.kr/disclosure/todaydisclosure.do"
    ajax_url = "https://kind.krx.co.kr/disclosure/todaydisclosure.do"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64;
