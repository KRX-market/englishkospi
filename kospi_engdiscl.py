import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import time
import random


# ============================================================
# 1. 페이지 설정
# ============================================================

st.set_page_config(
    page_title="코스피 영문공시 필터링 도구",
    layout="wide"
)


# ============================================================
# 2. 사이드바
# ============================================================

with st.sidebar:
    st.markdown("## 🚨 중요 공지")

    st.warning(
        """
        **본 사이트는 KIND 실시간 데이터를 참조합니다.**

        외부 서버 상태나 접근 제한 등에 따라
        일시적으로 조회가 되지 않을 수 있습니다.

        ---

        **🔗 이용 가능한 사이트 목록**

        1. https://englishkind.streamlit.app/
        2. https://english-kospi.streamlit.app/
        3. https://englishkospi.streamlit.app/
        """
    )

    st.markdown("---")


st.title("🎯 오늘의 코스피 번역대상 공시 조회")
st.markdown("---")


# ============================================================
# 3. 회사코드 정리
# ============================================================

def normalize_company_code(code):

    if code is None:
        return ""

    code = str(code).strip()

    if code.lower() == "nan":
        return ""

    # A005930 → 005930
    if code.upper().startswith("A"):
        code = code[1:]

    code = re.sub(r"[^0-9]", "", code)

    if not code:
        return ""

    return code.zfill(6)


# ============================================================
# 4. CSV 데이터 로드
# ============================================================

@st.cache_data
def load_reference_data():

    try:

        df_svc = pd.read_csv(
            "kospi_format.csv",
            dtype=str
        )

        df_listed = pd.read_csv(
            "kospi_company.csv",
            dtype=str
        )

        # 회사코드 정리
        if (
            not df_listed.empty
            and "회사코드" in df_listed.columns
        ):

            df_listed["회사코드"] = (
                df_listed["회사코드"]
                .apply(normalize_company_code)
            )

        # 서식명 공백 정리
        if (
            not df_svc.empty
            and "서식명" in df_svc.columns
        ):

            df_svc["서식명"] = (
                df_svc["서식명"]
                .astype(str)
                .str.strip()
            )

        return df_svc, df_listed

    except Exception as e:

        st.error(
            "❌ 기준 CSV 데이터를 읽는 중 오류가 발생했습니다."
        )

        st.code(str(e))

        return pd.DataFrame(), pd.DataFrame()


df_svc, df_listed = load_reference_data()


# ============================================================
# 5. 기준 데이터 표시
# ============================================================

col_ref1, col_ref2 = st.columns(2)


with col_ref1:

    st.subheader("📋 지원대상 공시서식")

    if not df_svc.empty:

        st.caption(
            f"총 {len(df_svc)}개의 서식 필터링 중"
        )

        st.dataframe(
            df_svc,
            use_container_width=True,
            height=200
        )

    else:

        st.error(
            "❌ kospi_format.csv 파일을 "
            "정상적으로 읽지 못했습니다."
        )


with col_ref2:

    st.subheader("🏢 지원대상 회사목록")

    if not df_listed.empty:

        st.caption(
            f"총 {len(df_listed)}개의 상장법인 등록됨"
        )

        st.dataframe(
            df_listed,
            use_container_width=True,
            height=200
        )

    else:

        st.error(
            "❌ kospi_company.csv 파일을 "
            "정상적으로 읽지 못했습니다."
        )


st.markdown("---")


# ============================================================
# 6. 날짜 선택
# ============================================================

selected_date = st.date_input(
    "📅 조회일자 선택",
    value=datetime.today()
)

today_str = selected_date.strftime("%Y-%m-%d")


# ============================================================
# 7. KIND 공시 테이블 찾기
# ============================================================

def find_disclosure_table(soup):

    # 1차: 기존 KIND table.list
    table = soup.select_one("table.list")

    if table:
        return table

    # 2차: 모든 테이블 중 공시 테이블 추정
    for table in soup.find_all("table"):

        text = table.get_text(
            " ",
            strip=True
        )

        if (
            "회사명" in text
            and "공시제목" in text
        ):
            return table

    return None


# ============================================================
# 8. KIND 크롤링
# ============================================================

def get_all_kind_data(date_str):

    KIND_URL = (
        "https://kind.krx.co.kr/"
        "disclosure/todaydisclosure.do"
    )

    session = requests.Session()

    all_rows = []


    # --------------------------------------------------------
    # 일반 브라우저 헤더
    # --------------------------------------------------------

    common_headers = {

        "User-Agent": (
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/154.0.0.0 "
            "Safari/537.36"
        ),

        "Accept": (
            "text/html,"
            "application/xhtml+xml,"
            "application/xml;q=0.9,"
            "*/*;q=0.8"
        ),

        "Accept-Language":
            "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",

        "Connection":
            "keep-alive"
    }


    try:

        # ====================================================
        # STEP 1. KIND 메인 페이지 접속
        # ====================================================

        main_params = {

            "method":
                "searchTodayDisclosureMain",

            "marketType":
                "1"
        }


        main_resp = session.get(

            KIND_URL,

            params=main_params,

            headers=common_headers,

            timeout=20
        )


        st.caption(
            f"🔗 KIND 초기접속 HTTP "
            f"{main_resp.status_code}"
        )


        if main_resp.status_code != 200:

            st.error(
                "❌ KIND 메인페이지 접속에 실패했습니다."
            )

            return pd.DataFrame(), False


        # ====================================================
        # STEP 2. 오늘 여부 판단
        # ====================================================

        real_today = (
            datetime.today()
            .strftime("%Y-%m-%d")
        )


        if date_str == real_today:
            today_flag = "Y"
        else:
            today_flag = "N"


        # ====================================================
        # STEP 3. AJAX 요청 헤더
        # ====================================================

        ajax_headers = {

            "User-Agent":
                common_headers["User-Agent"],

            "Accept":
                "text/html, */*; q=0.01",

            "Accept-Language":
                common_headers["Accept-Language"],

            "Content-Type":
                "application/x-www-form-urlencoded; "
                "charset=UTF-8",

            "X-Requested-With":
                "XMLHttpRequest",

            "Origin":
                "https://kind.krx.co.kr",

            "Referer":
                main_resp.url
        }


        # ====================================================
        # STEP 4. KIND POST 파라미터
        # ====================================================

        payload = {

            "method":
                "searchTodayDisclosureSub",

            "currentPageSize":
                "100",

            "pageIndex":
                "1",

            "orderMode":
                "0",

            "orderStat":
                "D",

            "forward":
                "todaydisclosure_sub",

            # 기존 코드에 없던 부분
            "chose":
                "S",

            "todayFlag":
                today_flag,

            # 코스피
            "marketType":
                "1",

            "selDate":
                date_str
        }


        # ====================================================
        # STEP 5. 첫 페이지 조회
        # ====================================================

        first_resp = session.post(

            KIND_URL,

            data=payload,

            headers=ajax_headers,

            timeout=20
        )


        st.caption(
            f"📡 KIND 공시조회 HTTP "
            f"{first_resp.status_code} / "
            f"응답크기 {len(first_resp.content):,} bytes"
        )


        # ====================================================
        # STEP 6. HTTP 오류
        # ====================================================

        if first_resp.status_code != 200:

            st.error(
                f"❌ KIND 공시조회 요청 실패 "
                f"(HTTP {first_resp.status_code})"
            )

            with st.expander(
                "🔧 서버 응답 확인"
            ):

                st.code(
                    first_resp.text[:3000]
                )

            return pd.DataFrame(), False


        # ====================================================
        # STEP 7. 접근차단 여부
        # ====================================================

        response_lower = (
            first_resp.text.lower()
        )


        blocked_words = [

            "access denied",

            "forbidden",

            "request blocked",

            "temporarily blocked"
        ]


        if any(
            word in response_lower
            for word in blocked_words
        ):

            st.error(
                "❌ KIND가 Streamlit 서버의 "
                "접근을 차단한 것으로 보입니다."
            )

            return pd.DataFrame(), False


        # ====================================================
        # STEP 8. HTML 분석
        # ====================================================

        soup = BeautifulSoup(

            first_resp.text,

            "html.parser"
        )


        full_text = soup.get_text(
            " ",
            strip=True
        )


        # ====================================================
        # STEP 9. 페이지 수 확인
        # ====================================================

        total_pages = 1


        # 예: 1/3
        page_match = re.search(

            r"(\d+)\s*/\s*(\d+)",

            full_text
        )


        if page_match:

            total_pages = int(
                page_match.group(2)
            )


        # ====================================================
        # STEP 10. 공시 건수 확인
        # ====================================================

        total_count = None


        count_match = re.search(

            r"전체\s*([\d,]+)\s*건",

            full_text
        )


        if count_match:

            total_count = int(

                count_match
                .group(1)
                .replace(",", "")
            )


        if total_count is not None:

            st.caption(
                f"✅ KIND 조회 성공 / "
                f"전체 {total_count}건 / "
                f"{total_pages}페이지"
            )

        else:

            st.caption(
                f"✅ KIND 응답 수신 / "
                f"{total_pages}페이지 감지"
            )


        # ====================================================
        # STEP 11. 결과가 정말 0건인지 확인
        # ====================================================

        no_result_words = [

            "조회된 결과값이 없습니다",

            "결과가 없습니다",

            "조회된 결과가 없습니다"
        ]


        if any(
            word in full_text
            for word in no_result_words
        ):

            st.info(
                f"{date_str}에 KIND에서 "
                f"조회된 공시가 없습니다."
            )

            return pd.DataFrame(), True


        # ====================================================
        # STEP 12. 첫 페이지 테이블 확인
        # ====================================================

        first_table = find_disclosure_table(
            soup
        )


        if first_table is None:

            st.error(
                "❌ KIND 응답은 받았지만 "
                "공시 테이블을 찾지 못했습니다."
            )

            st.warning(
                "KIND의 HTML 구조가 변경되었거나, "
                "정상적인 공시 화면이 아닌 다른 페이지가 "
                "반환됐을 가능성이 있습니다."
            )

            with st.expander(
                "🔧 KIND 응답 진단정보 보기"
            ):

                st.code(
                    first_resp.text[:5000]
                )

            return pd.DataFrame(), False


        # ====================================================
        # STEP 13. 페이지별 수집
        # ====================================================

        progress_bar = st.progress(0)

        status_text = st.empty()


        for page in range(
            1,
            total_pages + 1
        ):

            status_text.text(
                f"⏳ {total_pages}페이지 중 "
                f"{page}페이지 분석 중..."
            )


            payload["pageIndex"] = str(page)


            # 첫 페이지는 이미 받음
            if page == 1:

                resp = first_resp

            else:

                resp = session.post(

                    KIND_URL,

                    data=payload,

                    headers=ajax_headers,

                    timeout=20
                )


            if resp.status_code != 200:

                st.warning(
                    f"⚠️ {page}페이지 조회 실패 "
                    f"(HTTP {resp.status_code})"
                )

                continue


            page_soup = BeautifulSoup(

                resp.text,

                "html.parser"
            )


            table = find_disclosure_table(
                page_soup
            )


            if table is None:

                st.warning(
                    f"⚠️ {page}페이지에서 "
                    f"공시 테이블을 찾지 못했습니다."
                )

                continue


            tbody = table.find("tbody")


            if tbody is None:

                continue


            rows = tbody.find_all("tr")


            # =================================================
            # 공시 데이터 추출
            # =================================================

            for tr in rows:

                row_text = tr.get_text(
                    " ",
                    strip=True
                )


                if any(
                    word in row_text
                    for word in no_result_words
                ):

                    continue


                tds = tr.find_all("td")


                if len(tds) < 4:

                    continue


                # ---------------------------------------------
                # 시간
                # ---------------------------------------------

                disclosure_time = (
                    tds[0].get_text(
                        " ",
                        strip=True
                    )
                )


                # ---------------------------------------------
                # 회사명 / 회사코드
                # ---------------------------------------------

                company_name = (
                    tds[1].get_text(
                        " ",
                        strip=True
                    )
                )


                comp_code = ""


                comp_a = tds[1].find("a")


                if comp_a:

                    onclick = comp_a.get(
                        "onclick",
                        ""
                    )


                    code_match = re.search(

                        r"companysummary_open"
                        r"\(\s*['\"]"
                        r"([^'\"]+)"
                        r"['\"]",

                        onclick
                    )


                    if code_match:

                        comp_code = (
                            normalize_company_code(
                                code_match.group(1)
                            )
                        )


                # ---------------------------------------------
                # 공시 제목
                # ---------------------------------------------

                title_a = tds[2].find("a")


                if title_a:

                    title = title_a.get(
                        "title",
                        ""
                    ).strip()


                    if not title:

                        title = (
                            title_a.get_text(
                                " ",
                                strip=True
                            )
                        )

                else:

                    title = (
                        tds[2].get_text(
                            " ",
                            strip=True
                        )
                    )


                # ---------------------------------------------
                # 접수번호
                # ---------------------------------------------

                acpt_no = ""


                if title_a:

                    onclick = title_a.get(
                        "onclick",
                        ""
                    )


                    no_match = re.search(

                        r"openDisclsViewer"
                        r"\(\s*['\"]?"
                        r"(\d+)",

                        onclick
                    )


                    if no_match:

                        acpt_no = (
                            no_match.group(1)
                        )


                # ---------------------------------------------
                # 제출인
                # ---------------------------------------------

                submitter = (
                    tds[3].get_text(
                        " ",
                        strip=True
                    )
                )


                # ---------------------------------------------
                # 상세 URL
                # ---------------------------------------------

                detail_url = ""


                if acpt_no:

                    detail_url = (

                        "https://kind.krx.co.kr/"
                        "common/disclsviewer.do"
                        "?method=search"
                        f"&acptno={acpt_no}"
                    )


                # ---------------------------------------------
                # 저장
                # ---------------------------------------------

                all_rows.append(
                    {

                        "시간":
                            disclosure_time,

                        "회사코드":
                            comp_code,

                        "회사명":
                            company_name,

                        "공시제목":
                            title,

                        "제출인":
                            submitter,

                        "접수번호":
                            acpt_no,

                        "상세URL":
                            detail_url
                    }
                )


            progress_bar.progress(
                page / total_pages
            )


            if page < total_pages:

                time.sleep(
                    random.uniform(
                        0.4,
                        0.7
                    )
                )


        status_text.empty()

        progress_bar.empty()


        # ====================================================
        # STEP 14. 최종 결과
        # ====================================================

        df_result = pd.DataFrame(
            all_rows
        )


        if (
            not df_result.empty
            and "접수번호"
            in df_result.columns
        ):

            df_result = (
                df_result
                .drop_duplicates(
                    subset=["접수번호"],
                    keep="first"
                )
            )


        st.caption(
            f"📥 KIND 원본 공시 "
            f"{len(df_result)}건 수집 완료"
        )


        if df_result.empty:

            st.error(
                "❌ KIND 응답은 받았지만 "
                "실제 공시 데이터를 추출하지 못했습니다."
            )

            return df_result, False


        return df_result, True


    # ========================================================
    # Timeout
    # ========================================================

    except requests.exceptions.Timeout:

        st.error(
            "❌ KIND 서버 응답시간이 초과되었습니다."
        )

        return pd.DataFrame(), False


    # ========================================================
    # Connection
    # ========================================================

    except requests.exceptions.ConnectionError as e:

        st.error(
            "❌ Streamlit 서버에서 KIND 서버로 "
            "연결하지 못했습니다."
        )

        st.code(str(e))

        return pd.DataFrame(), False


    # ========================================================
    # 기타
    # ========================================================

    except Exception as e:

        st.error(
            "❌ 데이터 수집 중 오류가 발생했습니다."
        )

        st.code(
            f"{type(e).__name__}: {e}"
        )

        return pd.DataFrame(), False


# ============================================================
# 9. 실행 버튼
# ============================================================

if st.button(
    "🚀 영문공시 지원대상 필터링 실행",
    use_container_width=True
):

    # --------------------------------------------------------
    # CSV 확인
    # --------------------------------------------------------

    if df_svc.empty or df_listed.empty:

        st.error(
            "❌ 기준 CSV 데이터가 로드되지 않았습니다."
        )


    elif "서식명" not in df_svc.columns:

        st.error(
            "❌ kospi_format.csv에 "
            "'서식명' 컬럼이 없습니다."
        )


    elif "회사코드" not in df_listed.columns:

        st.error(
            "❌ kospi_company.csv에 "
            "'회사코드' 컬럼이 없습니다."
        )


    else:

        # ----------------------------------------------------
        # KIND 데이터 수집
        # ----------------------------------------------------

        with st.spinner(
            f"{today_str} 공시를 "
            f"전수 조사하는 중입니다..."
        ):

            df_raw, crawl_success = (
                get_all_kind_data(
                    today_str
                )
            )


        # ----------------------------------------------------
        # 크롤링 실패
        # ----------------------------------------------------

        if not crawl_success:

            st.warning(
                "⚠️ KIND 데이터를 정상적으로 "
                "가져오지 못했습니다."
            )

            st.info(
                "위에 표시된 HTTP 상태코드 또는 "
                "오류 메시지를 확인해 주세요."
            )


        # ----------------------------------------------------
        # 정상적으로 0건
        # ----------------------------------------------------

        elif df_raw.empty:

            st.info(
                f"{today_str} 기준 "
                f"KIND 공시가 없습니다."
            )


        else:

            # =================================================
            # 대상 서식
            # =================================================

            target_forms = (

                df_svc["서식명"]

                .dropna()

                .astype(str)

                .str.strip()

                .loc[
                    lambda x:
                    x != ""
                ]

                .unique()

                .tolist()
            )


            # =================================================
            # 대상 법인
            # =================================================

            target_codes = (

                df_listed["회사코드"]

                .dropna()

                .apply(
                    normalize_company_code
                )

                .loc[
                    lambda x:
                    x != ""
                ]

                .unique()

                .tolist()
            )


            # =================================================
            # KIND 회사코드 정리
            # =================================================

            df_raw["회사코드"] = (

                df_raw["회사코드"]

                .apply(
                    normalize_company_code
                )
            )


            # =================================================
            # 대상법인 조건
            # =================================================

            company_mask = (

                df_raw["회사코드"]

                .isin(
                    target_codes
                )
            )


            # =================================================
            # 대상서식 조건
            # =================================================

            form_pattern = "|".join(

                re.escape(form)

                for form in target_forms

                if form
            )


            if form_pattern:

                form_mask = (

                    df_raw["공시제목"]

                    .astype(str)

                    .str.contains(
                        form_pattern,
                        regex=True,
                        na=False
                    )
                )

            else:

                form_mask = pd.Series(
                    False,
                    index=df_raw.index
                )


            # =================================================
            # 추가상장 / 변경상장 제외
            # =================================================

            exclude_mask = (

                df_raw["공시제목"]

                .astype(str)

                .str.startswith(
                    (
                        "추가상장",
                        "변경상장"
                    ),

                    na=False
                )
            )


            # =================================================
            # 최종
            # =================================================

            final_mask = (

                company_mask

                & form_mask

                & ~exclude_mask
            )


            final_df = (

                df_raw[
                    final_mask
                ]

                .copy()
            )


            # =================================================
            # 진단정보
            # =================================================

            st.markdown("---")

            st.caption(
                f"🔎 KIND 전체 {len(df_raw)}건 | "
                f"대상법인 일치 {int(company_mask.sum())}건 | "
                f"대상서식 일치 {int(form_mask.sum())}건 | "
                f"최종 {len(final_df)}건"
            )


            # =================================================
            # 출력
            # =================================================

            st.subheader(
                f"📊 필터링 결과 "
                f"(대상: {len(final_df)}건)"
            )


            if not final_df.empty:

                final_df = (

                    final_df

                    .sort_values(
                        by="시간"
                    )
                )


                st.dataframe(

                    final_df[
                        [
                            "시간",
                            "회사명",
                            "공시제목",
                            "제출인",
                            "상세URL"
                        ]
                    ],

                    column_config={

                        "상세URL":
                            st.column_config.LinkColumn(
                                "공시보기",
                                display_text="공시보기"
                            )
                    },

                    hide_index=True,

                    use_container_width=True
                )


            else:

                st.info(
                    f"{today_str} 기준, "
                    f"조건에 맞는 공시가 없습니다."
                )
