import sys
sys.path.append("/app")
import streamlit as st
import random
import time
import os
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

from azureai.aisearch import ask_question
from dotenv import load_dotenv

load_dotenv()
SEARCH_KEY = os.getenv("AZURE_SEARCH_KEY")
INDEX_NAME = os.getenv("AZURE_SEARCH_INDEX")


# Azure 리소스 모니터링을 위한 샘플 데이터 생성 함수
def generate_azure_metrics():
    """Azure 리소스 메트릭 샘플 데이터 생성"""
    return {
        'vm_instances': random.randint(5, 15),
        'storage_gb': round(random.uniform(100, 500), 1),
        'app_services': random.randint(2, 8),
        'sql_databases': random.randint(1, 5),
        'cost_today': round(random.uniform(50, 200), 2),
        'alerts_count': random.randint(0, 5),
        'availability': round(random.uniform(98.5, 99.9), 2)
    }

def generate_resource_health_data():
    """Azure 리소스 상태 데이터 생성"""
    resources = [
        {'name': 'WebApp-Prod', 'type': 'App Service', 'status': 'Healthy', 'region': 'East US'},
        {'name': 'SQL-Database-01', 'type': 'SQL Database', 'status': 'Healthy', 'region': 'East US'},
        {'name': 'VM-WebServer-01', 'type': 'Virtual Machine', 'status': 'Warning', 'region': 'West US'},
        {'name': 'Storage-Account-01', 'type': 'Storage Account', 'status': 'Healthy', 'region': 'Korea Central'},
        {'name': 'Function-App-01', 'type': 'Function App', 'status': 'Critical', 'region': 'East Asia'}
    ]
    return pd.DataFrame(resources)

def generate_cost_data():
    """비용 분석 데이터 생성"""
    dates = pd.date_range(start=datetime.now() - timedelta(days=30), end=datetime.now(), freq='D')
    cost_data = []
    for date in dates:
        cost_data.append({
            'date': date,
            'compute': round(random.uniform(20, 50), 2),
            'storage': round(random.uniform(5, 15), 2),
            'networking': round(random.uniform(10, 25), 2),
            'database': round(random.uniform(15, 35), 2)
        })
    return pd.DataFrame(cost_data)

# 앱 제목 및 설명
st.title("시스템 모니터링 대시보드")
st.write("실시간 주요 시스템 지표를 모니터링합니다.")

# 새로고침 버튼
if st.button("새로고침"):
	st.rerun()

# 임의의 지표 데이터 생성
cpu = round(random.uniform(10, 90), 2)
mem = round(random.uniform(20, 95), 2)
net = round(random.uniform(1, 1000), 2)

# 지표 카드 표시
col1, col2, col3 = st.columns(3)
with col1:
	st.metric("CPU 사용률 (%)", f"{cpu}")
with col2:
	st.metric("메모리 사용률 (%)", f"{mem}")
with col3:
	st.metric("네트워크(Mbps)", f"{net}")

# 최근 업데이트 시간 표시
st.caption(f"업데이트: {time.strftime('%Y-%m-%d %H:%M:%S')}")



# 질문/답변 이력 저장
if "chat_history" not in st.session_state:
	st.session_state["chat_history"] = []

st.header("Azure OpenAI Chat")
user_question = st.text_input("질문을 입력하세요")

# Azure Search 연결 및 인덱스 상태 확인
st.subheader("Azure Search 연결 진단")
if st.button("연결 및 인덱스 상태 확인"):
	from azureai.aisearch import SEARCH_ENDPOINT
	from azure.search.documents.indexes import SearchIndexClient
	from azure.core.credentials import AzureKeyCredential
	try:
		idx_client = SearchIndexClient(endpoint=SEARCH_ENDPOINT, credential=AzureKeyCredential(SEARCH_KEY))
		indexes = idx_client.list_indexes()
		index_names = [idx.name for idx in indexes]
		st.write(f"엔드포인트: {SEARCH_ENDPOINT}")
		st.write(f"인덱스 목록: {index_names}")
		if INDEX_NAME in index_names:
			st.success(f"'{INDEX_NAME}' 인덱스가 존재합니다.")
		else:
			st.warning(f"'{INDEX_NAME}' 인덱스가 존재하지 않습니다.")
	except Exception as e:
		st.error(f"연결 오류: {e}")


# OpenAI 답변 및 이력 저장
if st.button("질문하기") and user_question:
	with st.spinner("AI 응답 생성 중..."):
		try:
			answer = ask_question(user_question)
			# 출처 정보 추출 (aisearch.py에서 반환하도록 수정된 경우)
			# 예시: answer가 dict일 경우
			citations = None
			if isinstance(answer, dict):
				citations = answer.get("citations", None)
				answer_text = answer.get("content", "")
			else:
				answer_text = answer
			st.session_state["chat_history"].append({"question": user_question, "answer": answer_text, "citations": citations})
		except Exception as e:
			st.error(f"AI 오류: {e}")

# 이력 출력
if st.session_state["chat_history"]:
	st.subheader("질문/답변 이력")
	for idx, chat in enumerate(st.session_state["chat_history"]):
		st.markdown(f"**Q{idx+1}:** {chat['question']}")
		st.markdown(f"**A{idx+1}:** {chat['answer']}")
		if chat.get("citations"):
			st.markdown(f"🔗 **참고한 AI Search 문서 출처:**")
			for cite in chat["citations"]:
				st.write(f"- {cite.get('url', cite.get('id', ''))}")

# 사이드바 네비게이션 추가
st.sidebar.title("📊 Azure Dashboard Hub")
page = st.sidebar.selectbox(
    "대시보드 선택",
    ["🏠 Overview", "🔍 Resource Health", "💰 Cost Analysis", "🤖 AI Chat"]
)

# Overview 페이지
if page == "🏠 Overview":
    st.title("☁️ Azure Dashboard Hub - Overview")
    st.markdown("Azure 클라우드 리소스의 전체 현황을 한눈에 확인하세요.")
    
    # Azure 메트릭 데이터 생성
    metrics = generate_azure_metrics()
    
    # 주요 지표 카드
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("🖥️ VM 인스턴스", f"{metrics['vm_instances']}개")
    with col2:
        st.metric("💾 스토리지 사용량", f"{metrics['storage_gb']} GB")
    with col3:
        st.metric("📱 App Services", f"{metrics['app_services']}개")
    with col4:
        st.metric("💰 오늘 비용", f"${metrics['cost_today']}")
    
    # 리소스 분포 차트
    st.subheader("📊 리소스 분포")
    resource_data = pd.DataFrame({
        'Service': ['Virtual Machines', 'App Services', 'SQL Databases', 'Storage Accounts', 'Function Apps'],
        'Count': [metrics['vm_instances'], metrics['app_services'], metrics['sql_databases'], 3, 2]
    })
    fig_pie = px.pie(resource_data, values='Count', names='Service', title="Azure 서비스별 리소스 분포")
    st.plotly_chart(fig_pie, use_container_width=True)

# Resource Health 페이지
elif page == "🔍 Resource Health":
    st.title("🔍 Azure 리소스 상태")
    st.write("Azure 리소스의 상태와 건강성을 모니터링합니다.")
    
    # 리소스 상태 데이터
    resource_df = generate_resource_health_data()
    
    # 상태별 요약
    col1, col2, col3 = st.columns(3)
    healthy_count = len(resource_df[resource_df['status'] == 'Healthy'])
    warning_count = len(resource_df[resource_df['status'] == 'Warning'])
    critical_count = len(resource_df[resource_df['status'] == 'Critical'])
    with col1:
        st.metric("✅ 정상", healthy_count)
    with col2:
        st.metric("⚠️ 경고", warning_count)
    with col3:
        st.metric("🚨 위험", critical_count)
    
    # 리소스 상태 테이블
    st.subheader("📋 리소스 상태 목록")
    st.dataframe(resource_df, use_container_width=True)

# Cost Analysis 페이지
elif page == "💰 Cost Analysis":
    st.title("💰 Azure 비용 분석")
    st.write("Azure 클라우드 사용 비용을 분석하고 최적화 방안을 제시합니다.")
    
    # 비용 데이터 생성
    cost_df = generate_cost_data()
    cost_df['total'] = cost_df['compute'] + cost_df['storage'] + cost_df['networking'] + cost_df['database']
    
    # 총 비용 요약
    total_month_cost = cost_df['total'].sum()
    avg_daily_cost = cost_df['total'].mean()
    col1, col2 = st.columns(2)
    with col1:
        st.metric("💳 이번 달 총 비용", f"${total_month_cost:.2f}")
    with col2:
        st.metric("📊 일평균 비용", f"${avg_daily_cost:.2f}")
    
    # 비용 추이 차트
    st.subheader("📈 일별 비용 추이")
    fig_cost = px.line(cost_df, x='date', y='total', title='30일 비용 추이')
    st.plotly_chart(fig_cost, use_container_width=True)

# AI Chat 페이지
elif page == "🤖 AI Chat":
    st.title("🤖 Azure OpenAI Chat")
    st.write("Azure AI Search와 연동된 지능형 챗봇입니다.")
    # 기존 AI Chat 코드 유지

