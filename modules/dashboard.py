import streamlit as st
import pandas as pd
from datetime import datetime
import sys
import os
from pathlib import Path
from dotenv import load_dotenv
import json
import base64
from urllib.parse import quote

# 프로젝트 루트 디렉토리를 sys.path에 추가 
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

# .env 파일 로드
env_path = BASE_DIR / '.env'
load_dotenv(env_path)

def get_azure_dashboards():
    """Azure Portal 대시보드 정보를 가져오는 함수"""
    try:
        from azure.identity import ClientSecretCredential
        from azure.mgmt.subscription import SubscriptionClient
        from azure.mgmt.resourcegraph import ResourceGraphClient
        from azure.mgmt.resourcegraph.models import QueryRequest
        
        # 환경 변수에서 인증 정보 읽기
        client_id = os.getenv('AZURE_CLIENT_ID')
        client_secret = os.getenv('AZURE_CLIENT_SECRET') 
        tenant_id = os.getenv('AZURE_TENANT_ID')
        subscription_id = os.getenv('AZURE_SUBSCRIPTION_ID')
        
        if not all([client_id, client_secret, tenant_id, subscription_id]):
            st.warning("⚠️ Azure 인증 정보가 .env 파일에서 로드되지 않았습니다.")
            return None, None
            
        # 캐시 확인 (5분간 유효)
        cache_key = "azure_dashboards_cache"
        time_key = "last_fetch_time"
        
        if cache_key in st.session_state and time_key in st.session_state:
            if (datetime.now() - st.session_state[time_key]).seconds < 300:
                return st.session_state[cache_key], st.session_state.get("subscription_info")
        
        # Azure 인증
        credential = ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret
        )
        
        # 구독 정보 가져오기
        subscription_client = SubscriptionClient(credential)
        subscription_info = subscription_client.subscriptions.get(subscription_id)
        
        # Resource Graph를 통해 대시보드 조회
        graph_client = ResourceGraphClient(credential)
        
        # Portal 대시보드 조회 - 간단한 쿼리 사용
        query = QueryRequest(
            query="Resources | where type =~ 'microsoft.portal/dashboards' | project id, name, resourceGroup, location, subscriptionId, tags, properties"
        )
        
        try:
            query_response = graph_client.resources(query)
            
            if not query_response or not hasattr(query_response, 'data'):
                st.warning("⚠️ 대시보드 데이터를 가져올 수 없습니다.")
                return [], subscription_info
                
        except Exception as query_error:
            st.error(f"❌ Resource Graph 쿼리 실행 실패: {str(query_error)}")
            return [], subscription_info
        
        dashboards = []
        for dashboard in query_response.data:
            # 대시보드 메타데이터 추출
            properties = dashboard.get('properties', {})
            metadata = properties.get('metadata', {}) if properties else {}
            model = metadata.get('model', {}) if metadata else {}
            
            # 대시보드 표시 이름 결정
            display_name = dashboard.get('name', 'Unknown')
            if model and 'title' in model:
                display_name = model['title']
            
            # 공유 여부 판단 (hidden-title 태그가 없으면 공유됨)
            tags = dashboard.get('tags', {})
            is_shared = 'hidden-title' not in tags
            
            dashboard_info = {
                'id': dashboard.get('id', ''),
                'name': dashboard.get('name', 'Unknown'),
                'displayName': display_name,
                'resourceGroup': dashboard.get('resourceGroup', 'N/A'),
                'location': dashboard.get('location', 'global'),
                'subscriptionId': dashboard.get('subscriptionId', subscription_id),
                'subscriptionName': subscription_info.display_name,
                'tags': tags,
                'isShared': is_shared,
                'properties': properties,
                'created': metadata.get('created', 'N/A') if metadata else 'N/A',
                'modified': metadata.get('modified', 'N/A') if metadata else 'N/A'
            }
            dashboards.append(dashboard_info)
        
        # 캐시 저장
        st.session_state[cache_key] = dashboards
        st.session_state[time_key] = datetime.now()
        st.session_state["subscription_info"] = subscription_info
        
        return dashboards, subscription_info
        
    except ImportError as e:
        st.error(f"❌ 필요한 Azure SDK 패키지가 설치되지 않았습니다: {str(e)}")
        return None, None
    except Exception as e:
        st.error(f"❌ Azure 연결 실패: {str(e)}")
        
        # 오류 발생 시 샘플 데이터 반환
        st.info("📋 샘플 대시보드 데이터를 표시합니다.")
        sample_dashboards = [
            {
                'id': '/subscriptions/sample/resourceGroups/rg-monitoring/providers/Microsoft.Portal/dashboards/sample-dashboard-001',
                'name': 'sample-dashboard-001',
                'displayName': 'Azure 모니터링 대시보드',
                'resourceGroup': 'rg-monitoring',
                'location': 'global',
                'subscriptionId': 'sample-subscription-id',
                'subscriptionName': '샘플 구독',
                'tags': {'Environment': 'Production'},
                'isShared': True,
                'properties': {},
                'created': '2025-01-01',
                'modified': '2025-09-30'
            },
            {
                'id': '/subscriptions/sample/resourceGroups/rg-personal/providers/Microsoft.Portal/dashboards/my-dashboard',
                'name': 'my-dashboard',
                'displayName': '개인 대시보드',
                'resourceGroup': 'rg-personal',
                'location': 'global',
                'subscriptionId': 'sample-subscription-id',
                'subscriptionName': '샘플 구독',
                'tags': {'hidden-title': 'MyDashboard'},
                'isShared': False,
                'properties': {},
                'created': '2025-02-01',
                'modified': '2025-09-29'
            }
        ]
        
        # 가짜 subscription_info 객체 생성
        class SampleSubscription:
            def __init__(self):
                self.display_name = "샘플 구독"
        
        return sample_dashboards, SampleSubscription()

def generate_dashboard_url(dashboard_id, tenant_id):
    """대시보드 URL 생성"""
    if not dashboard_id or not tenant_id:
        return None
    
    # Azure Portal 대시보드 URL 형식
    base_url = "https://portal.azure.com"
    # ARM 리소스 ID를 URL 경로로 변환
    dashboard_path = f"/#@{tenant_id}/dashboard/arm{dashboard_id}"
    return f"{base_url}{dashboard_path}"

def display_dashboard_preview(dashboard_url):
    """대시보드 미리보기 표시 (제한적)"""
    if dashboard_url:
        st.markdown(f"""
        ### 🎯 대시보드 미리보기
        
        **참고**: Azure Portal 대시보드는 인증이 필요하므로 직접 임베드할 수 없습니다.
        아래 링크를 클릭하여 새 탭에서 대시보드를 열어주세요.
        
        [{dashboard_url}]({dashboard_url})
        """)
    else:
        st.warning("⚠️ 대시보드 URL을 생성할 수 없습니다.")

def render_dashboard():
    """Azure Dashboard Hub 메인 페이지"""
    st.title("🌐 Azure Dashboard Hub")
    st.markdown("""
    Azure Portal의 대시보드를 한눈에 확인하고 관리하세요.
    """)

    # 새로고침 버튼과 상태 정보
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("🔄 새로고침", help="대시보드 목록을 다시 불러옵니다"):
            # 캐시 클리어
            for key in ["azure_dashboards_cache", "last_fetch_time"]:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()
    
    with col2:
        st.caption(f"마지막 업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 대시보드 데이터 로드
    with st.spinner("🔍 Azure 대시보드를 검색 중..."):
        dashboards, subscription_info = get_azure_dashboards()

    if dashboards is None:
        st.error("❌ Azure 대시보드를 불러올 수 없습니다. 인증 정보를 확인해주세요.")
        
        # 샘플 데이터 표시
        st.info("📋 샘플 데이터를 표시합니다.")
        sample_dashboards = [
            {
                'displayName': 'Azure 모니터링 대시보드',
                'name': 'monitoring-dashboard',
                'resourceGroup': 'rg-monitoring',
                'isShared': True,
                'subscriptionName': '샘플 구독'
            },
            {
                'displayName': 'VM 성능 대시보드', 
                'name': 'vm-performance',
                'resourceGroup': 'rg-compute',
                'isShared': False,
                'subscriptionName': '샘플 구독'
            }
        ]
        
        df = pd.DataFrame(sample_dashboards)
        st.dataframe(df, width='stretch')
        return

    # 성공적으로 로드된 경우
    if subscription_info:
        st.success(f"✅ 구독 '{subscription_info.display_name}' 연결 성공")

    if not dashboards:
        st.info("📋 현재 구독에서 대시보드를 찾을 수 없습니다.")
        return

    # 통계 정보 표시
    col1, col2, col3, col4 = st.columns(4)
    
    shared_count = len([d for d in dashboards if d.get('isShared', False)])
    private_count = len(dashboards) - shared_count
    resource_groups = set(d.get('resourceGroup', 'N/A') for d in dashboards)
    
    with col1:
        st.metric("📊 총 대시보드", len(dashboards))
    with col2:
        st.metric("🔗 공유 대시보드", shared_count)
    with col3:
        st.metric("🔒 개인 대시보드", private_count)
    with col4:
        st.metric("📁 리소스 그룹", len(resource_groups))

    st.divider()

    # 필터링 옵션
    col1, col2 = st.columns(2)
    
    with col1:
        # 리소스 그룹 필터
        rg_options = ["전체"] + sorted(list(resource_groups))
        selected_rg = st.selectbox("📁 리소스 그룹 필터", rg_options, index=0)
    
    with col2:
        # 공유 상태 필터
        share_options = ["전체", "공유 대시보드만", "개인 대시보드만"]
        selected_share = st.selectbox("🔗 공유 상태 필터", share_options, index=0)

    # 필터 적용
    filtered_dashboards = dashboards
    
    if selected_rg != "전체":
        filtered_dashboards = [d for d in filtered_dashboards if d.get('resourceGroup') == selected_rg]
    
    if selected_share == "공유 대시보드만":
        filtered_dashboards = [d for d in filtered_dashboards if d.get('isShared', False)]
    elif selected_share == "개인 대시보드만":
        filtered_dashboards = [d for d in filtered_dashboards if not d.get('isShared', False)]

    if not filtered_dashboards:
        st.warning("⚠️ 선택한 필터 조건에 맞는 대시보드가 없습니다.")
        return

    # 대시보드 목록 표시
    st.subheader(f"📋 대시보드 목록 ({len(filtered_dashboards)}개)")
    
    # 대시보드 선택 드롭다운
    dashboard_options = {
        f"{d['displayName']} ({'공유' if d.get('isShared') else '개인'})": d 
        for d in filtered_dashboards
    }
    
    selected_dashboard_name = st.selectbox(
        "🎯 대시보드 선택",
        options=list(dashboard_options.keys()),
        index=0,
        help="목록에서 대시보드를 선택하면 상세 정보와 링크가 표시됩니다."
    )

    # 선택된 대시보드 정보 표시
    if selected_dashboard_name:
        selected_dashboard = dashboard_options[selected_dashboard_name]
        
        st.subheader("🎯 선택된 대시보드")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.markdown(f"""
            **이름**: {selected_dashboard['displayName']}  
            **리소스 이름**: {selected_dashboard['name']}  
            **리소스 그룹**: {selected_dashboard['resourceGroup']}  
            **위치**: {selected_dashboard['location']}  
            **구독**: {selected_dashboard['subscriptionName']}  
            **공유 상태**: {'🔗 공유됨' if selected_dashboard.get('isShared') else '🔒 개인용'}
            """)
            
            # 태그 정보
            if selected_dashboard.get('tags'):
                tags_str = ", ".join([f"{k}: {v}" for k, v in selected_dashboard['tags'].items()])
                st.markdown(f"**태그**: {tags_str}")
        
        with col2:
            # 대시보드 열기 버튼
            tenant_id = os.getenv('AZURE_TENANT_ID', '')
            dashboard_url = generate_dashboard_url(selected_dashboard['id'], tenant_id)
            
            if dashboard_url:
                st.markdown(f"""
                <a href="{dashboard_url}" target="_blank">
                    <button style="
                        background-color: #0078d4;
                        color: white;
                        padding: 10px 20px;
                        border: none;
                        border-radius: 5px;
                        cursor: pointer;
                        font-size: 16px;
                        width: 100%;
                    ">
                        🚀 대시보드 열기
                    </button>
                </a>
                """, unsafe_allow_html=True)
                
                st.caption("새 탭에서 Azure Portal이 열립니다")
        
        st.divider()
        
        # 대시보드 미리보기 (제한적)
        display_dashboard_preview(dashboard_url)

    # 전체 대시보드 목록 테이블
    st.subheader("📊 전체 대시보드 목록")
    
    # 테이블용 데이터 준비
    table_data = []
    for dashboard in filtered_dashboards:
        tenant_id = os.getenv('AZURE_TENANT_ID', '')
        dashboard_url = generate_dashboard_url(dashboard['id'], tenant_id)
        
        table_data.append({
            '대시보드 이름': dashboard['displayName'],
            '리소스 이름': dashboard['name'],
            '공유 상태': '🔗 공유됨' if dashboard.get('isShared') else '🔒 개인용',
            '리소스 그룹': dashboard['resourceGroup'],
            '위치': dashboard['location'],
            '구독': dashboard['subscriptionName'],
            'URL': f"[열기]({dashboard_url})" if dashboard_url else "N/A"
        })
    
    if table_data:
        df = pd.DataFrame(table_data)
        st.dataframe(df, width='stretch')
        
        # CSV 다운로드
        if st.button("📥 CSV로 내보내기"):
            csv = df.to_csv(index=False, encoding='utf-8-sig')
            st.download_button(
                label="다운로드",
                data=csv,
                file_name=f"azure_dashboards_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )

    # 상태 표시
    st.divider()
    col1, col2 = st.columns(2)
    
    with col1:
        st.success("🟢 Azure 연결: 정상")
    
    with col2:
        st.info(f"🕐 로드 시간: {datetime.now().strftime('%H:%M:%S')}")
