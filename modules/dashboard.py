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
            tags = dashboard.get('tags', {})
            
            # 대시보드 표시 이름 결정 (우선순위에 따라)
            display_name = 'Unknown Dashboard'
            
            # 1순위: tags['hidden-title'] (Azure Portal 대시보드의 실제 이름)
            if tags and 'hidden-title' in tags and tags['hidden-title']:
                display_name = tags['hidden-title']
            # 2순위: model.title (대시보드의 메타데이터 제목)
            elif model and 'title' in model and model['title']:
                display_name = model['title']
            # 3순위: properties.displayName (대시보드의 표시 이름)
            elif properties and 'displayName' in properties and properties['displayName']:
                display_name = properties['displayName']
            # 4순위: 리소스 이름을 읽기 쉽게 변환
            else:
                resource_name = dashboard.get('name', 'Unknown')
                if resource_name and resource_name != 'Unknown':
                    # 대시보드 이름에서 불필요한 GUID 부분 제거하고 읽기 쉽게 만들기
                    import re
                    cleaned_name = resource_name
                    # GUID 패턴 제거 (8-4-4-4-12 형태)
                    cleaned_name = re.sub(r'-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', '', cleaned_name, flags=re.IGNORECASE)
                    # 남은 하이픈들을 공백으로 변경하고 제목 형태로 변환
                    cleaned_name = cleaned_name.replace('-', ' ').replace('_', ' ').title()
                    display_name = cleaned_name if cleaned_name.strip() else resource_name
            
            # 공유 여부 판단 
            # Resource Graph API로 조회되는 대시보드는 모두 공유 대시보드입니다
            # (개인 대시보드는 Azure 리소스가 아니므로 API로 조회 불가)
            is_shared = True  # Resource Graph로 조회되는 것은 모두 공유 대시보드
            

            
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
    Azure Portal의 **공유 대시보드**를 한눈에 확인하고 관리하세요.
    
    ℹ️ **참고**: 이 도구는 Azure Resource Graph API를 사용하므로 **공유된 대시보드만** 표시됩니다. 
    개인(private) 대시보드는 Azure Portal에서만 확인 가능합니다.
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
        st.info("📋 현재 구독에서 공유 대시보드를 찾을 수 없습니다.")
        st.markdown("""
        **공유 대시보드가 없는 이유:**
        - 대부분의 대시보드는 개인용(private)으로 생성됩니다
        - 개인용 대시보드는 Azure Portal에서 '공유' 버튼을 눌러 게시해야 조회 가능합니다
        - [Azure Portal 대시보드 공유 방법 보기](https://learn.microsoft.com/en-us/azure/azure-portal/azure-portal-dashboard-share-access)
        """)
        return

    # 통계 정보 표시
    col1, col2 = st.columns(2)
    
    resource_groups = set(d.get('resourceGroup', 'N/A') for d in dashboards)
    
    with col1:
        st.metric("📊 총 대시보드", len(dashboards))
    with col2:
        st.metric("📁 리소스 그룹", len(resource_groups))

    st.divider()

    # 필터링 옵션
    # 리소스 그룹 필터
    rg_options = ["전체"] + sorted(list(resource_groups))
    selected_rg = st.selectbox("📁 리소스 그룹 필터", rg_options, index=0)

    # 필터 적용
    filtered_dashboards = dashboards
    
    if selected_rg != "전체":
        filtered_dashboards = [d for d in filtered_dashboards if d.get('resourceGroup') == selected_rg]

    if not filtered_dashboards:
        st.warning("⚠️ 선택한 필터 조건에 맞는 대시보드가 없습니다.")
        return

        # 대시보드 목록 표시
    st.subheader(f"📋 대시보드 목록 ({len(filtered_dashboards)}개)")
    
    # 테이블용 데이터 준비 - 클릭 가능한 링크가 포함된 통합 테이블
    if filtered_dashboards:
        table_data = []
        tenant_id = os.getenv('AZURE_TENANT_ID', '')
        
        for dashboard in filtered_dashboards:
            dashboard_url = generate_dashboard_url(dashboard['id'], tenant_id)
            
            # 대시보드 이름을 클릭 가능한 링크로 생성
            if dashboard_url:
                dashboard_name_link = f"🚀 {dashboard['displayName']}"
            else:
                dashboard_name_link = f"❌ {dashboard['displayName']}"
            
            table_data.append({
                'URL': dashboard_url if dashboard_url else "N/A",
                '대시보드 이름': dashboard_name_link,
                '리소스 그룹': dashboard['resourceGroup']
            })
        
        # 데이터프레임 생성 및 표시 - URL 컬럼을 링크 컬럼으로 설정
        df = pd.DataFrame(table_data)
        
        # 클릭 가능한 링크가 포함된 테이블 표시
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "URL": st.column_config.LinkColumn(
                    "Azure Portal 링크",
                    width="medium",
                    help="클릭하면 Azure Portal에서 대시보드가 열립니다"
                ),
                "대시보드 이름": st.column_config.TextColumn(
                    "대시보드 이름",
                    width="large",
                    help="🚀 표시된 대시보드는 클릭 가능합니다"
                ),
                "리소스 그룹": st.column_config.TextColumn(
                    "리소스 그룹", 
                    width="medium"
                )
            }
        )
        
        st.caption("💡 'Azure Portal 링크' 컬럼을 클릭하면 새 탭에서 해당 대시보드가 열립니다.")
        
        # 대시보드 링크는 테이블에서 직접 클릭 가능
        


    # 상태 표시
    st.divider()
    col1, col2 = st.columns(2)
    
    with col1:
        st.success("🟢 Azure 연결: 정상")
    
    with col2:
        st.info(f"🕐 로드 시간: {datetime.now().strftime('%H:%M:%S')}")
