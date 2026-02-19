import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, timedelta
import time

# ============================================================
# Streamlit Page Config
# ============================================================
st.set_page_config(
    page_title="오늘의 코스피 번역대상 공시",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.title("오늘의 코스피 번역대상 공시")

# ============================================================
# KIND 요청 공통 설정
# ============================================================
KIND_URL = "https://kind.krx.co.kr/disclosure/todaydisclosure.do"

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://kind.krx.co.kr/disclosure/todaydisclosure.do",
    "Origin": "https://kind.krx.co.kr",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
}

@st.cache_resource
def get_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(DEFAULT_HEADERS)
    return s

def fetch_kind_page(page_num: int, sel_date: str, page_size: int = 100):
    """
    KIND 'todaydisclosure_sub' 페이지를 안전하게 가져옵니다.
    - params(쿼리스트링) 대신 data(폼) 전송
    - 헤더/타임아웃/예외처리
    """
    payload = {
        "method": "searchTodayDisclosureSub",
        "currentPageSize": page_size,
        "pageIndex": page_num,
        "orderMode": 0,
        "orderStat": "D",
        "marketType": 1,  # KOSPI
        "forward": "todaydisclosure_sub",
        "searchMode": "",
        "searchCodeType": "",
        "chose": "S",
        "todayFlag": "Y",
        "repIsuSrtCd": "",
        "kosdaqSegment": "",
        "selDate": sel_date,
        "searchCorpName": "",
        "copyUrl": "",
    }

    try:
        sess = get_session()
        r = sess.post(KIND_URL, data=payload, timeout=20)
        r.raise_for_status()
        html = r.text
        soup = BeautifulSoup(html, "html.parser")
        return soup, html
    except Exception as e:
        st.error(f"[KIND 요청 오류] page={page_num}, date={sel_date} / {e}")
        return None, None

def safe_parse_total_info(soup: BeautifulSoup):
    """
    총 건수/총 페이지를 최대한 안전하게 파싱.
    실패 시 (None, 1) 반환.
    """
    total_items = None
    total_pages = 1

    if soup is None:
        return total_items, total_pages

    info_box = soup.select_one(".info.type-00")
    total_items_element = soup.select_one(".info.type-00 em")

    # total_pages: "1/12" 같은 형태가 info 박스 텍스트에 섞여있음
    if info_box:
        info_text = info_box.get_text(" ", strip=True)
        m = re.search(r"(\d+)\s*/\s*(\d+)", info_text)
        if m:
            try:
                total_pages = int(m.group(2))
            except:
                total_pages = 1

    # total_items: em 안에 "1,234" 형태
    if total_items_element:
        try:
            total_items = int(total_items_element.get_text(strip=True).replace(",", ""))
        except:
            total_items = None

    return total_items, total_pages

def parse_table(soup: BeautifulSoup):
    """
    공시 목록 테이블 파싱
    """
    data = []
    if soup is None:
        return data

    table = soup.find("table", class_="list type-00 mt10")
    tbody = table.find("tbody") if table else None
    if not tbody:
        return data

    for row in tbody.find_all("tr"):
        cols = row.find_all("td")
        if len(cols) < 5:
            continue

        t = cols[0].get_text(strip=True)

        # 회사명 + 회사코드
        company_a = cols[1].find("a", id="companysum")
        company = company_a.get_text(strip=True) if company_a else ""

        company_code = ""
        if company_a and company_a.has_attr("onclick"):
            onclick_attr = company_a["onclick"]
            m = re.search(r"companysummary_open\('([A-Za-z0-9]+)'\)", onclick_attr)
            if m:
                company_code = m.group(1)

        # 공시 제목 + 비고(폰트 태그)
        title_a = cols[2].find("a")
        title = ""
        note = ""
        discl_url = ""

        if title_a:
            title = title_a.get("title", "").strip()

            font_tags = title_a.find_all("font")
            if font_tags:
                notes = [ft.get_text(strip=True) for ft in font_tags if ft.get_text(strip=True)]
                note = "_".join(notes)

            # 상세 URL(acptno)
            if title_a.has_attr("onclick"):
                onclick_attr = title_a["onclick"]
                m = re.search(r"openDisclsViewer\('(\d+)'", onclick_attr)
                if m:
                    acptno = m.group(1)
                    discl_url = (
                        "https://kind.krx.co.kr/common/disclsviewer.do"
                        f"?method=search&acptno={acptno}&docno=&viewerhost=&viewerport="
                    )

        submitter = cols[3].get_text(strip=True)

        data.append(
            {
                "시간": t,
                "회사코드": company_code,
                "회사명": company,
                "비고": note,
                "공시제목": title,
                "제출인": submitter,
                "상세URL": discl_url,
            }
        )

    return data

# ============================================================
# CSV 로드
# ============================================================
@st.cache_data
def load_kospi_format_data():
    try:
        return pd.read_csv("kospi_format.csv", dtype=str)
    except Exception as e:
        st.error(f"공시서식 데이터 로드 오류: {e}")
        return pd.DataFrame()

@st.cache_data
def load_kospi_company_data():
    try:
        return pd.read_csv("kospi_company.csv", dtype=str)
    except Exception as e:
        st.error(f"회사 데이터 로드 오류: {e}")
        return pd.DataFrame()

df_svc = load_kospi_format_data()
df_listed = load_kospi_company_data()

if not df_listed.empty and "회사코드" in df_listed.columns:
    df_listed["회사코드"] = df_listed["회사코드"].astype(str).str.zfill(5)

# ============================================================
# 상단 2컬럼: 서식/회사 목록
# ============================================================
col1, col2 = st.columns(2)

with col1:
    st.subheader("지원대상 공시서식")
    if not df_svc.empty:
        st.write(f"{len(df_svc)}개")
        st.dataframe(df_svc, width="stretch")
    else:
        st.warning("공시서식 데이터를 불러올 수 없습니다.")

with col2:
    st.subheader("지원대상 회사 목록")
    if not df_listed.empty:
        st.write(f"{len(df_listed)}사")
        st.dataframe(df_listed, width="stretch")
    else:
        st.warning("회사 목록 데이터를 불러올 수 없습니다.")

# ============================================================
# 날짜 선택
# ============================================================
def get_default_date_str():
    today = datetime.today()
    if today.weekday() in [5, 6]:  # 토(5)/일(6)
        # 직전 금요일
        return (today - timedelta(days=today.weekday() - 4)).strftime("%Y-%m-%d")
    return today.strftime("%Y-%m-%d")

st.subheader("조회일자 선택")

selected_date = st.date_input(
    "조회할 날짜를 선택하세요",
    value=datetime.strptime(get_default_date_str(), "%Y-%m-%d"),
    min_value=datetime(2020, 1, 1),
    max_value=datetime.today(),
)

today_date = selected_date.strftime("%Y-%m-%d")

# ============================================================
# 조회 버튼
# ============================================================
if st.button("코스피 영문공시 지원대상 공시조회"):
    if df_svc.empty or df_listed.empty:
        st.error("필요한 데이터를 불러올 수 없습니다. CSV 파일을 확인해주세요.")
        st.stop()

    if "서식명" not in df_svc.columns:
        st.error("kospi_format.csv에 '서식명' 컬럼이 없습니다.")
        st.stop()

    if "회사코드" not in df_listed.columns:
        st.error("kospi_company.csv에 '회사코드' 컬럼이 없습니다.")
        st.stop()

    with st.spinner("데이터를 가져오는 중입니다..."):
        all_data = []

        # 1페이지 가져오기
        soup1, raw1 = fetch_kind_page(1, today_date)
        if soup1 is None:
            st.stop()

        total_items, total_pages = safe_parse_total_info(soup1)

        if total_items is not None:
            st.info(
                f"조회일에 총 {total_items}건의 공시가 있습니다. (총 {total_pages}페이지)    "
                "지원대상 공시는 아래 표를 참고해주세요."
            )
        else:
            st.warning("페이지 정보(.info.type-00)를 찾지 못해 총 페이지를 1로 가정합니다.")
            with st.expander("응답 HTML 일부(디버그)"):
                st.code((raw1 or "")[:2000])

        # 1페이지 파싱
        all_data.extend(parse_table(soup1))

        # 나머지 페이지 파싱
        if total_pages > 1:
            progress_bar = st.progress(0)
            for i, page in enumerate(range(2, total_pages + 1), start=1):
                soup, _raw = fetch_kind_page(page, today_date)
                if soup:
                    all_data.extend(parse_table(soup))

                progress_bar.progress(i / (total_pages - 1))
                time.sleep(0.4)  # 서버 부하 완화

        df_discl = pd.DataFrame(all_data)

        st.subheader("코스피 지원대상 공시 목록")

        if df_discl.empty:
            st.warning("조회 결과 공시 데이터가 없습니다(또는 파싱 실패).")
            st.stop()

        # ============================================================
        # 필터링 1: 지원대상 서식 포함 + (추가상장/변경상장 제외)
        # ============================================================
        form_names = [x for x in df_svc["서식명"].dropna().unique().tolist() if str(x).strip()]

        def is_target_title(title: str) -> bool:
            if not title:
                return False
            if title.startswith("추가상장") or title.startswith("변경상장"):
                return False
            for form_name in form_names:
                if form_name in title:
                    return True
            return False

        filtered_df = df_discl[df_discl["공시제목"].apply(is_target_title)].copy()

        # ============================================================
        # 필터링 2: 지원대상 회사코드만
        # ============================================================
        listed_company_codes = df_listed["회사코드"].astype(str).str.zfill(5).tolist()
        filtered_df["회사코드"] = filtered_df["회사코드"].astype(str).str.zfill(5)
        filtered_df = filtered_df[filtered_df["회사코드"].isin(listed_company_codes)]

        if filtered_df.empty:
            st.warning("조건에 맞는 공시 데이터가 없습니다.")
        else:
            st.write(f"총 {len(filtered_df)}건의 지원대상 공시가 있습니다.")
            st.dataframe(
                filtered_df,
                column_config={
                    "상세URL": st.column_config.LinkColumn("상세URL"),
                },
                hide_index=True,
                width="stretch",
            )

# ============================================================
# Sidebar - cache refresh
# ============================================================
st.sidebar.markdown("---")
if st.sidebar.button("📊 데이터 새로고침"):
    st.cache_data.clear()
    st.cache_resource.clear()
    st.rerun()

st.sidebar.info("💡 CSV 파일에서 데이터를 불러옵니다.")

