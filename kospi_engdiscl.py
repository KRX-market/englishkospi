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
        df_svc = pd.read_csv("kospi_format.csv", dtype=str)
        df_listed = pd.read_csv("kospi_company.csv", dtype=str)
        
        # 회사코드 6자리 정규화 (예: 005930)
        if not df_listed.empty and '회사코드' in df_listed.columns:
            df_listed['회사코드'] = df_listed['회사코드'].astype(str).str.zfill(6)
            
        return df_svc, df_listed
    except Exception as e:
        st.error(f"⚠️ CSV 파일을 불러오는 중 오류 발생: {e}")
        return pd.DataFrame(), pd.DataFrame()

df_svc, df_listed = load_reference_data()

# --- 상단 기준 데이터 표시 ---
if not df_svc.empty and not df_listed.empty:
    col_ref1, col_ref2 = st.columns(2)
