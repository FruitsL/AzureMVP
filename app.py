import streamlit as st
import sys
from pathlib import Path

# 프로젝트 루트 디렉토리를 sys.path에 추가 (이제 파일이 루트에 있으므로 경로 수정)
BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))

# 페이지 모듈 import
from modules.dashboard import render_dashboard
from modules.notice import render_notice_board
from modules.ai_chat import render_ai_chat

# 페이지 설정
st.set_page_config(
    page_title="Azure MVP Dashboard",
    page_icon="☁️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 메인 앱 구성

# 사이드바 메뉴
st.sidebar.title("Dashboard")
page = st.sidebar.radio(
    "메뉴를 선택하세요",
    ("대시보드 보기", "공지사항", "AI에게 질문하기")
)

# 페이지 라우팅
if page == "대시보드 보기":
    render_dashboard()
elif page == "공지사항":
    render_notice_board()
elif page == "AI에게 질문하기":
    render_ai_chat()