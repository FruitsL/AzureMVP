
import sys
sys.path.append("/app")
import streamlit as st
import random
import time
import os

from azureai.aisearch import ask_question
from dotenv import load_dotenv

load_dotenv()
SEARCH_KEY = os.getenv("AZURE_SEARCH_KEY")
INDEX_NAME = os.getenv("AZURE_SEARCH_INDEX")


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

