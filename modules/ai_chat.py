import streamlit as st
import time
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# 프로젝트 루트 디렉토리를 sys.path에 추가 
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

# .env 파일 로드
env_path = BASE_DIR / '.env'
load_dotenv(env_path)

def get_azure_storage_containers():
    """Azure Storage 계정의 컨테이너 목록을 가져오는 함수"""
    try:
        from azure.identity import ClientSecretCredential
        from azure.storage.blob import BlobServiceClient
        
        # 환경 변수에서 인증 정보 읽기
        client_id = os.getenv('AZURE_CLIENT_ID')
        client_secret = os.getenv('AZURE_CLIENT_SECRET') 
        tenant_id = os.getenv('AZURE_TENANT_ID')
        storage_account_name = os.getenv('AZURE_STORAGE_ACCOUNT_NAME')
        
        if not all([client_id, client_secret, tenant_id]):
            st.warning("⚠️ Azure 인증 정보가 .env 파일에 없습니다.")
            return None
            
        if not storage_account_name:
            st.warning("⚠️ AZURE_STORAGE_ACCOUNT_NAME이 .env 파일에 없습니다.")
            st.info("💡 .env 파일에 다음 항목을 추가해주세요: `AZURE_STORAGE_ACCOUNT_NAME=your-storage-account-name`")
            return None
            
        # 캐시 확인 (5분간 유효)
        cache_key = "storage_containers_cache"
        time_key = "containers_fetch_time"
        
        if cache_key in st.session_state and time_key in st.session_state:
            if (time.time() - st.session_state[time_key]) < 300:  # 5분
                return st.session_state[cache_key]
        
        # Azure 인증
        credential = ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret
        )
        
        # Storage Account URL 생성
        account_url = f"https://{storage_account_name}.blob.core.windows.net"
        
        # BlobServiceClient 생성
        blob_service_client = BlobServiceClient(
            account_url=account_url, 
            credential=credential
        )
        
        # 컨테이너 목록 가져오기
        containers = []
        container_list = blob_service_client.list_containers()
        
        for container in container_list:
            containers.append({
                'name': container.name,
                'last_modified': container.last_modified,
                'metadata': container.metadata or {},
                'public_access': container.public_access
            })
        
        # 캐시 저장
        st.session_state[cache_key] = containers
        st.session_state[time_key] = time.time()
        
        return containers
        
    except ImportError as e:
        st.error(f"❌ Azure Storage SDK가 설치되지 않았습니다: {str(e)}")
        return None
    except Exception as e:
        st.error(f"❌ Azure Storage 연결 실패: {str(e)}")
        return None

def render_ai_chat():
    """AI에게 질문하기 페이지"""
    st.title("🤖 AI에게 질문하기")
    st.write("Azure OpenAI를 통해 질문하고 답변을 받아보세요.")

    # 질문/답변 이력 저장
    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []

    # Azure Blob Storage 선택
    st.subheader("📁 Azure Blob Storage 컨테이너 선택")
    
    # 새로고침 버튼
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("🔄 새로고침", help="컨테이너 목록을 다시 불러옵니다"):
            # 캐시 클리어
            for key in ["storage_containers_cache", "containers_fetch_time"]:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()
    
    # 실제 Azure Storage 컨테이너 목록 가져오기
    with st.spinner("🔍 Azure Storage 컨테이너를 검색 중..."):
        containers = get_azure_storage_containers()
    
    if containers is None:
        # 오류 시 기본 옵션 제공
        st.warning("⚠️ Azure Storage에 연결할 수 없습니다. 기본 옵션을 사용합니다.")
        storage_options = ["기본 Storage (일반 질문)"]
        selected_storage = st.selectbox(
            "질문할 내용과 관련된 컨테이너를 선택하세요",
            storage_options,
            index=0
        )
        st.info("💡 일반적인 Azure 관련 질문을 할 수 있습니다.")
    else:
        # 인덱스된 컨테이너 목록 가져오기 (상태 표시용)
        indexed_containers = []
        try:
            from azureai.aisearch import get_indexed_containers
            indexed_containers = get_indexed_containers()
        except Exception as e:
            pass  # 에러 시 빈 목록으로 처리
        
        # 실제 컨테이너 목록으로 옵션 생성
        container_options = ["기본 Storage (일반 질문)"]
        
        if containers:
            for container in containers:
                container_name = container['name']
                container_info = f"{container_name}"
                
                # 인덱스 상태 표시 (인덱스된 컨테이너에 🔍 표시)
                is_indexed = any(
                    indexed_container in container_name.lower() or container_name.lower() in indexed_container
                    for indexed_container in indexed_containers
                )
                if is_indexed:
                    container_info += " 🔍"  # 인덱스된 컨테이너 표시
                
                if container['metadata']:
                    # 메타데이터가 있으면 설명 추가
                    description = container['metadata'].get('description', '')
                    if description:
                        container_info += f" ({description})"
                
                container_options.append(container_info)
            
            # 결과 메시지
            indexed_count = sum(1 for c in containers if any(
                ic in c['name'].lower() or c['name'].lower() in ic for ic in indexed_containers
            ))
            st.success(f"✅ {len(containers)}개의 컨테이너를 발견했습니다! (인덱스됨: {indexed_count}개 🔍)")
        else:
            st.info("📋 현재 Storage 계정에 컨테이너가 없습니다.")
            container_options = ["기본 Storage (일반 질문)"]
        
        selected_storage = st.selectbox(
            "질문할 내용과 관련된 컨테이너를 선택하세요",
            container_options,
            index=0,
            help="선택한 컨테이너에 따라 AI가 관련 문서나 데이터를 참조하여 더 정확한 답변을 제공합니다."
        )
        
        # 선택된 컨테이너 정보 표시
        if selected_storage == "기본 Storage (일반 질문)":
            st.info("💡 일반적인 Azure 관련 질문을 할 수 있습니다.")
        else:
            container_name = selected_storage.split(" 🔍")[0].split(" (")[0]  # 인덱스 아이콘 제거
            
            # 선택된 컨테이너의 상세 정보 표시
            selected_container = next((c for c in containers if c['name'] == container_name), None)
            
            if selected_container:
                # 인덱스 상태 확인
                is_indexed = "🔍" in selected_storage
                status_icon = "🔍" if is_indexed else "📁"
                status_text = "인덱스됨" if is_indexed else "일반 컨테이너"
                
                st.success(f"✅ 선택됨: **{container_name}** {status_icon} ({status_text})")
                
                # 컨테이너 상세 정보
                with st.expander("📋 컨테이너 상세 정보"):
                    st.write(f"**이름**: {selected_container['name']}")
                    st.write(f"**상태**: {status_text}")
                    st.write(f"**마지막 수정**: {selected_container['last_modified']}")
                    if selected_container['public_access']:
                        st.write(f"**접근 수준**: {selected_container['public_access']}")
                    if selected_container['metadata']:
                        st.write("**메타데이터**:")
                        for key, value in selected_container['metadata'].items():
                            st.write(f"  - {key}: {value}")
                    
                    # 인덱스 정보 표시
                    if is_indexed:
                        try:
                            from azureai.aisearch import get_index_for_container
                            mapped_index = get_index_for_container(container_name)
                            st.write(f"**기본 매핑된 AI Search 인덱스**: `{mapped_index}`")
                        except Exception:
                            st.write("**AI Search 인덱스**: 매핑 정보 확인 불가")

    # AI Search 인덱스 선택 (컨테이너가 선택된 경우에만 표시)
    selected_search_index = None
    if selected_storage != "기본 Storage (일반 질문)":
        st.subheader("🔍 AI Search 인덱스 선택")
        
        container_name = selected_storage.split(" 🔍")[0].split(" (")[0]
        
        try:
            from azureai.aisearch import get_indexes_for_container, get_available_search_indexes
            
            # 해당 컨테이너에서 사용 가능한 인덱스 목록 가져오기
            with st.spinner(f"🔍 '{container_name}' 컨테이너의 데이터소스-인덱서 연결을 확인 중..."):
                available_indexes = get_indexes_for_container(container_name)
            
            if available_indexes:
                # 인덱스 선택 옵션 생성
                index_options = ["미선택 (일반 OpenAI 질문)"]
                index_details = {}
                
                for idx in available_indexes:
                    option_text = f"{idx['name']}"
                    
                    # 데이터소스-인덱서 정보가 있으면 표시
                    if idx.get('data_source') and idx.get('indexer'):
                        option_text += f" (데이터소스: {idx['data_source']}, 인덱서: {idx['indexer']})"
                    elif idx.get('description'):
                        option_text += f" - {idx['description']}"
                    
                    if idx.get('fields_count', 0) > 0:
                        option_text += f" [{idx['fields_count']}개 필드]"
                    
                    index_options.append(option_text)
                    index_details[option_text] = idx
                
                selected_index_option = st.selectbox(
                    f"'{container_name}' 컨테이너 관련 AI Search 인덱스를 선택하세요",
                    options=index_options,
                    index=0,
                    help="미선택 시 AI Search 없이 일반 OpenAI로 질문합니다. 특정 인덱스 선택 시 해당 인덱스의 문서를 참조하여 답변합니다."
                )
                
                # 선택된 인덱스 정보 표시
                if selected_index_option == "미선택 (일반 OpenAI 질문)":
                    st.info("💡 AI Search 없이 일반 OpenAI로 질문합니다. 문서 참조 기능이 사용되지 않습니다.")
                    selected_search_index = "NO_INDEX"  # 인덱스 미사용 표시
                else:
                    selected_idx_info = index_details[selected_index_option]
                    selected_search_index = selected_idx_info['name']
                    
                    # 선택된 인덱스 상세 정보
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.success(f"✅ 선택된 인덱스: **{selected_search_index}**")
                    with col2:
                        if st.button("🔄 인덱스 새로고침", help="인덱스 목록을 다시 불러옵니다"):
                            st.rerun()
                    
                    # 인덱스 상세 정보
                    with st.expander("📋 선택된 인덱스 상세 정보"):
                        st.write(f"**인덱스 이름**: {selected_idx_info['name']}")
                        
                        # 데이터소스-인덱서 연결 정보 표시
                        if selected_idx_info.get('data_source') and selected_idx_info.get('indexer'):
                            st.write("**데이터 흐름**:")
                            st.write(f"  📁 컨테이너: `{container_name}`")
                            st.write(f"  🔗 데이터소스: `{selected_idx_info['data_source']}`")
                            st.write(f"  ⚙️ 인덱서: `{selected_idx_info['indexer']}`")
                            st.write(f"  📊 인덱스: `{selected_idx_info['name']}`")
                        
                        if selected_idx_info.get('description'):
                            st.write(f"**설명**: {selected_idx_info['description']}")
                        if selected_idx_info.get('fields_count', 0) > 0:
                            st.write(f"**필드 수**: {selected_idx_info['fields_count']}개")
            else:
                st.warning(f"⚠️ '{container_name}' 컨테이너와 관련된 AI Search 인덱스를 찾을 수 없습니다.")
                st.info("💡 일반 질문 모드로 진행되거나 다른 컨테이너를 선택해보세요.")
                
        except Exception as e:
            st.warning(f"⚠️ 인덱스 목록을 가져올 수 없습니다: {str(e)}")
            st.info("💡 기본 인덱스가 자동으로 사용됩니다.")

    st.divider()

    # 질문 입력 (여러 줄 가능)
    user_question = st.text_area(
        "질문을 입력하세요", 
        placeholder="예: Azure App Service 배포 방법을 알려주세요\n\n여러 줄로 자세한 질문을 작성할 수 있습니다.",
        height=120,
        help="긴 질문이나 복잡한 시나리오를 여러 줄로 작성할 수 있습니다."
    )

    # 질문하기 버튼
    if st.button("질문하기"):
        if user_question and user_question.strip():
            with st.spinner("AI 응답 생성 중..."):
                try:
                    # 실제 Azure OpenAI + AI Search 연동
                    try:
                        # aisearch 모듈 import 시도
                        import sys
                        sys.path.append(str(BASE_DIR))
                        from azureai.aisearch import ask_question_with_container
                        
                        # 선택된 컨테이너와 인덱스에 따라 AI Search 사용
                        result = ask_question_with_container(
                            user_question.strip(), 
                            selected_storage, 
                            selected_search_index
                        )
                        
                        answer = result["content"]
                        citations = result.get("citations", [])
                        index_used = result.get("index_used")
                        
                        # 사용된 인덱스 정보 추가
                        if index_used == "미사용":
                            storage_info = "💬 **인덱스 미사용**: AI Search 없이 일반 OpenAI로 답변"
                        elif index_used:
                            if selected_search_index and selected_search_index != "NO_INDEX":
                                storage_info = f"📊 **사용된 인덱스**: {index_used} (수동 선택)"
                            else:
                                storage_info = f"📊 **사용된 인덱스**: {index_used} (자동 선택)"
                        else:
                            storage_info = "💬 **일반 질문**: AI Search 없이 답변"
                            
                    except ImportError:
                        # aisearch 모듈을 찾을 수 없는 경우 시뮬레이션
                        storage_context = f"(참조 Storage: {selected_storage})" if selected_storage != "기본 Storage (일반 질문)" else ""
                        
                        if selected_search_index == "NO_INDEX":
                            index_context = "(인덱스 미사용 - 일반 OpenAI)"
                            answer = f"'{user_question.strip()}'에 대한 답변입니다. {storage_context} {index_context} (Azure OpenAI 연동 필요)"
                            index_used = "미사용"
                            storage_info = "⚠️ **시뮬레이션 모드**: 인덱스 미사용 - 일반 OpenAI 질문"
                        elif selected_search_index:
                            index_context = f"(사용 인덱스: {selected_search_index})"
                            answer = f"'{user_question.strip()}'에 대한 답변입니다. {storage_context} {index_context} (Azure OpenAI 연동 필요)"
                            index_used = selected_search_index
                            storage_info = f"⚠️ **시뮬레이션 모드**: 선택된 인덱스 `{selected_search_index}` 사용 예정"
                        else:
                            index_context = "(자동 인덱스 선택)"
                            answer = f"'{user_question.strip()}'에 대한 답변입니다. {storage_context} {index_context} (Azure OpenAI 연동 필요)"
                            index_used = None
                            storage_info = "⚠️ **시뮬레이션 모드**: 자동 인덱스 선택 예정"
                        
                        citations = []
                    
                    st.session_state["chat_history"].append({
                        "question": user_question.strip(), 
                        "answer": answer,
                        "storage": selected_storage,
                        "search_index": selected_search_index,
                        "citations": citations,
                        "index_used": index_used,
                        "storage_info": storage_info,
                        "timestamp": time.strftime('%Y-%m-%d %H:%M:%S')
                    })
                    st.success("답변을 생성했습니다!")
                    # 질문 후 페이지 새로고침으로 입력란 비우기
                    st.rerun()
                except Exception as e:
                    st.error(f"AI 오류: {e}")
        else:
            st.warning("⚠️ 질문을 입력해주세요.")

    # 이력 출력
    if st.session_state["chat_history"]:
        st.subheader("💬 질문/답변 이력")
        
        # 최신순으로 정렬하여 표시 (가장 최근 질문이 맨 위에)
        reversed_history = list(reversed(st.session_state["chat_history"]))
        
        for display_idx, chat in enumerate(reversed_history):
            # 원본 인덱스 계산 (역순이므로)
            original_idx = len(st.session_state["chat_history"]) - display_idx - 1
            
            # 가장 최근 질문(첫 번째 항목)은 자동으로 펼쳐서 표시
            is_latest = (display_idx == 0)
            
            # 최근 질문에는 🆕 아이콘 추가
            if is_latest:
                question_title = f"🆕 Q{original_idx+1}: {chat['question'][:50]}..." if len(chat['question']) > 50 else f"🆕 Q{original_idx+1}: {chat['question']}"
            else:
                question_title = f"Q{original_idx+1}: {chat['question'][:50]}..." if len(chat['question']) > 50 else f"Q{original_idx+1}: {chat['question']}"
            
            with st.expander(question_title, expanded=is_latest):
                st.markdown(f"**질문**: {chat['question']}")
                
                # 선택된 Storage 정보 표시
                if chat.get('storage'):
                    storage_display = chat['storage']
                    if storage_display != "기본 Storage (일반 질문)":
                        st.markdown(f"**📁 선택된 컨테이너**: {storage_display}")
                    else:
                        st.markdown(f"**📁 선택된 컨테이너**: 일반 질문")
                
                # 선택된 인덱스 정보 표시
                if chat.get('search_index') == "NO_INDEX":
                    st.markdown("**🔍 선택된 인덱스**: 미사용 (일반 OpenAI)")
                elif chat.get('search_index'):
                    st.markdown(f"**🔍 선택된 인덱스**: {chat['search_index']}")
                elif chat.get('index_used') == "미사용":
                    st.markdown("**🔍 사용된 인덱스**: 미사용 (일반 OpenAI)")
                elif chat.get('index_used'):
                    st.markdown(f"**🔍 자동 선택된 인덱스**: {chat['index_used']}")
                
                # 사용된 인덱스 정보 표시
                if chat.get('storage_info'):
                    st.markdown(chat['storage_info'])
                
                st.markdown(f"**답변**: {chat['answer']}")
                
                # Azure Search 출처 정보가 있는 경우
                if chat.get("citations") and len(chat["citations"]) > 0:
                    st.markdown("🔗 **참고한 AI Search 문서 출처:**")
                    for cite in chat["citations"]:
                        if isinstance(cite, dict):
                            title = cite.get('title', cite.get('id', '제목 없음'))
                            url = cite.get('url', cite.get('filepath', ''))
                            if url:
                                st.write(f"- [{title}]({url})")
                            else:
                                st.write(f"- {title}")
                        else:
                            st.write(f"- {cite}")
                
                st.caption(f"시간: {chat.get('timestamp', 'N/A')}")

    # Azure Search 연결 진단 (옵션)
    with st.expander("🔧 Azure OpenAI + AI Search 연결 진단"):
        st.info("Azure OpenAI와 Azure Search 연동 상태를 확인합니다.")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔍 연결 상태 확인"):
                try:
                    from azureai.aisearch import ask_question_with_container
                    
                    # 현재 선택된 설정으로 테스트 질문
                    test_storage = selected_storage if 'selected_storage' in locals() else "기본 Storage (일반 질문)"
                    test_index = selected_search_index if 'selected_search_index' in locals() and selected_search_index else None
                    
                    test_result = ask_question_with_container("테스트 질문입니다", test_storage, test_index)
                    st.success("✅ Azure OpenAI 연결 성공!")
                    st.write(f"**응답**: {test_result['content'][:100]}...")
                    
                    if test_result.get('index_used'):
                        st.info(f"📊 사용된 인덱스: {test_result['index_used']}")
                    
                except Exception as e:
                    st.error(f"❌ 연결 실패: {str(e)}")
        
        with col2:
            if st.button("📋 데이터소스-인덱서 연결 확인"):
                try:
                    from azureai.aisearch import get_available_search_indexes, get_datasources_and_indexers, get_index_for_container
                    
                    # 데이터소스와 인덱서 정보 표시
                    datasources, indexers = get_datasources_and_indexers()
                    
                    if datasources and indexers:
                        st.write("**🔗 데이터소스-인덱서 연결 구조:**")
                        
                        # 연결 구조 매핑
                        for ds in datasources:
                            related_indexers = [idx for idx in indexers if idx['data_source_name'] == ds['name']]
                            if related_indexers:
                                st.write(f"📁 **{ds['container'] or 'Unknown'}** (컨테이너)")
                                st.write(f"  └─ 🔗 {ds['name']} (데이터소스)")
                                for indexer in related_indexers:
                                    st.write(f"      └─ ⚙️ {indexer['name']} (인덱서)")
                                    st.write(f"          └─ 📊 {indexer['target_index_name']} (인덱스)")
                                st.write("")
                    else:
                        st.write("데이터소스-인덱서 정보를 가져올 수 없습니다. 기본 매핑을 사용합니다.")
                        
                        # 사용 가능한 모든 인덱스 표시
                        st.write("**사용 가능한 AI Search 인덱스:**")
                        available_indexes = get_available_search_indexes()
                        
                        if available_indexes:
                            for idx in available_indexes:
                                index_info = f"- `{idx['name']}`"
                                if idx.get('fields_count', 0) > 0:
                                    index_info += f" ({idx['fields_count']}개 필드)"
                                if idx.get('description'):
                                    index_info += f" - {idx['description']}"
                                st.write(index_info)
                    
                    st.divider()
                    
                    # 현재 컨테이너들에 대한 연결된 인덱스 확인
                    if containers:
                        st.write("**컨테이너별 연결된 인덱스:**")
                        for container in containers[:5]:  # 처음 5개만 표시
                            container_indexes = get_index_for_container(container['name'])
                            if container_indexes:
                                index_names = [idx['name'] for idx in container_indexes]
                                st.write(f"- `{container['name']}` → {', '.join([f'`{name}`' for name in index_names])}")
                            else:
                                st.write(f"- `{container['name']}` → 연결된 인덱스 없음")
                    else:
                        st.write("컨테이너 목록을 먼저 불러와주세요.")
                        
                except Exception as e:
                    st.warning(f"⚠️ 연결 정보 확인 실패: {str(e)}")
        
        # 환경 변수 확인
        st.subheader("🔧 환경 설정 확인")
        env_status = []
        
        required_vars = [
            "AZURE_OPENAI_ENDPOINT",
            "AZURE_OPENAI_DEPLOYMENT", 
            "AZURE_SEARCH_ENDPOINT",
            "AZURE_SEARCH_INDEX",
            "AZURE_STORAGE_ACCOUNT_NAME"
        ]
        
        for var in required_vars:
            value = os.getenv(var)
            if value:
                env_status.append(f"✅ {var}: 설정됨")
            else:
                env_status.append(f"❌ {var}: 미설정")
        
        for status in env_status:
            st.write(status)