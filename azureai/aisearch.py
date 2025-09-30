"""Azure OpenAI + Azure AI Search RAG helper.
Non-blocking auth selection and lazy client initialization to avoid UI delays.
"""

import os
from dotenv import load_dotenv
from openai import AzureOpenAI
from azure.identity import ManagedIdentityCredential, ClientSecretCredential, get_bearer_token_provider

load_dotenv()

# Environment variables (support both new and legacy names)
ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT") or os.getenv("ENDPOINT_URL") or "https://azureopenai-jmg.openai.azure.com/"
DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT") or os.getenv("DEPLOYMENT_NAME") or "gpt-4.1-mini"
API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION") or "2024-05-01-preview"

SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT")
SEARCH_INDEX = os.getenv("AZURE_SEARCH_INDEX")

RESOURCE_SCOPE = "https://cognitiveservices.azure.com/.default"

_client = None  # Lazy-initialized AzureOpenAI client


def _get_token_provider():
	"""Prefer Service Principal if available; otherwise use Managed Identity.
	We do not call get_token() here to avoid blocking UI; token is acquired on-demand.
	"""
	client_id = os.getenv("AZURE_CLIENT_ID")
	tenant_id = os.getenv("AZURE_TENANT_ID")
	client_secret = os.getenv("AZURE_CLIENT_SECRET")
	if client_id and tenant_id and client_secret:
		cred = ClientSecretCredential(tenant_id=tenant_id, client_id=client_id, client_secret=client_secret)
	else:
		cred = ManagedIdentityCredential()
	return get_bearer_token_provider(cred, RESOURCE_SCOPE)


def _get_client() -> AzureOpenAI:
	global _client
	if _client is not None:
		return _client

	api_key = os.getenv("AZURE_OPENAI_KEY")
	if api_key:
		_client = AzureOpenAI(
			azure_endpoint=ENDPOINT,
			api_key=api_key,
			api_version=API_VERSION,
		)
		return _client

	token_provider = _get_token_provider()
	_client = AzureOpenAI(
		azure_endpoint=ENDPOINT,
		azure_ad_token_provider=token_provider,
		api_version=API_VERSION,
	)
	return _client


def get_index_for_container(container_name: str) -> str:
	"""컨테이너 이름에 따라 AI Search 인덱스를 자동 매핑하는 함수 (자동 선택 시에만 사용)"""
	# 실제 존재하는 인덱스 중에서 컨테이너와 매칭되는 것을 찾기
	try:
		available_indexes = get_indexes_for_container(container_name)
		if available_indexes:
			# 첫 번째 매칭된 인덱스 반환
			return available_indexes[0]['name']
	except Exception:
		pass
	
	# 매칭되는 인덱스가 없으면 환경변수 인덱스 사용 (있다면)
	if SEARCH_INDEX:
		return SEARCH_INDEX
	
	# 그것도 없으면 None 반환 (AI Search 사용하지 않음)
	return None


def get_indexed_containers():
	"""AI Search에 인덱스가 생성된 컨테이너 목록을 반환하는 함수"""
	try:
		from azure.search.documents import SearchClient
		from azure.identity import ClientSecretCredential, ManagedIdentityCredential
		from azure.core.credentials import AzureKeyCredential
		
		if not SEARCH_ENDPOINT:
			return []
		
		# 인증 설정
		search_key = os.getenv("AZURE_SEARCH_KEY")
		if search_key:
			credential = AzureKeyCredential(search_key)
		else:
			# Service Principal 또는 Managed Identity 사용
			client_id = os.getenv("AZURE_CLIENT_ID")
			tenant_id = os.getenv("AZURE_TENANT_ID")
			client_secret = os.getenv("AZURE_CLIENT_SECRET")
			if client_id and tenant_id and client_secret:
				credential = ClientSecretCredential(tenant_id=tenant_id, client_id=client_id, client_secret=client_secret)
			else:
				credential = ManagedIdentityCredential()
		
		indexed_containers = []
		
		# 실제 존재하는 인덱스들만 가져오기 (하드코딩된 목록 제거)
		try:
			from azure.search.documents.indexes import SearchIndexClient
			index_client = SearchIndexClient(endpoint=SEARCH_ENDPOINT, credential=credential)
			known_indexes = [index.name for index in index_client.list_indexes()]
		except Exception:
			# 인덱스 목록을 가져올 수 없으면 빈 목록
			known_indexes = []
		
		for index_name in known_indexes:
			try:
				# 인덱스 존재 여부 확인 (간단한 검색 시도)
				search_client = SearchClient(
					endpoint=SEARCH_ENDPOINT,
					index_name=index_name,
					credential=credential
				)
				
				# 인덱스에서 문서 수 확인 (간단한 테스트)
				results = search_client.search("*", top=1)
				
				# 인덱스가 존재하면 연결된 컨테이너들을 찾기
				if index_name == (SEARCH_INDEX or "azureblob-index"):
					# 기본 인덱스의 경우 실제 문서에서 컨테이너 정보 추출 시도
					try:
						# 검색 결과에서 컨테이너 정보 추출
						for result in results:
							# 메타데이터에서 컨테이너 정보 찾기
							if hasattr(result, 'metadata_storage_path') or 'metadata_storage_path' in result:
								storage_path = result.get('metadata_storage_path', '')
								if storage_path and '/containers/' in storage_path:
									container_name = storage_path.split('/containers/')[1].split('/')[0]
									if container_name and container_name not in indexed_containers:
										indexed_containers.append(container_name)
							# 다른 필드에서 컨테이너 정보 확인
							for field_name, field_value in result.items():
								if isinstance(field_value, str) and '/containers/' in field_value:
									try:
										container_name = field_value.split('/containers/')[1].split('/')[0]
										if container_name and container_name not in indexed_containers:
											indexed_containers.append(container_name)
									except:
										continue
								
						# 메타데이터에서 컨테이너를 찾지 못한 경우에도 빈 상태 유지
						
					except Exception:
						# 메타데이터 추출 실패 시 빈 상태 유지
						pass
				else:
					# 명명된 인덱스의 경우 인덱스 이름에서 컨테이너 추출
					container_name = index_name.replace('-index', '').replace('_index', '')
					if container_name and container_name not in indexed_containers:
						indexed_containers.append(container_name)
				
			except Exception as e:
				# 인덱스가 없거나 접근할 수 없으면 무시
				continue
		
		# 중복 제거 및 정렬
		indexed_containers = sorted(list(set(indexed_containers)))
		return indexed_containers
		
	except ImportError:
		# Azure Search SDK가 없으면 빈 목록 반환
		return []
	except Exception:
		# 기타 오류 시 빈 목록 반환
		return []


def is_container_indexed(container_name: str) -> bool:
	"""특정 컨테이너가 인덱스되어 있는지 확인하는 함수"""
	try:
		indexed_containers = get_indexed_containers()
		
		# 정확한 매치 확인
		if container_name in indexed_containers:
			return True
		
		# 부분 매치 확인
		for indexed_container in indexed_containers:
			if indexed_container in container_name.lower() or container_name.lower() in indexed_container:
				return True
		
		return False
		
	except Exception:
		# 에러 시 false 반환
		return False


def get_datasources_and_indexers():
	"""데이터소스와 인덱서 정보를 가져오는 함수"""
	try:
		from azure.search.documents.indexes import SearchIndexerClient
		from azure.identity import ClientSecretCredential, ManagedIdentityCredential
		from azure.core.credentials import AzureKeyCredential
		
		if not SEARCH_ENDPOINT:
			return [], []
		
		# 인증 설정
		search_key = os.getenv("AZURE_SEARCH_KEY")
		if search_key:
			credential = AzureKeyCredential(search_key)
		else:
			client_id = os.getenv("AZURE_CLIENT_ID")
			tenant_id = os.getenv("AZURE_TENANT_ID")
			client_secret = os.getenv("AZURE_CLIENT_SECRET")
			if client_id and tenant_id and client_secret:
				credential = ClientSecretCredential(tenant_id=tenant_id, client_id=client_id, client_secret=client_secret)
			else:
				credential = ManagedIdentityCredential()
		
		indexer_client = SearchIndexerClient(
			endpoint=SEARCH_ENDPOINT,
			credential=credential
		)
		
		# 데이터소스 목록 가져오기
		datasources = []
		try:
			for ds in indexer_client.get_data_source_connections():
				container_name = None
				
				# 컨테이너 정보 추출
				if hasattr(ds, 'container') and ds.container:
					if hasattr(ds.container, 'name'):
						container_name = ds.container.name
					elif isinstance(ds.container, dict) and 'name' in ds.container:
						container_name = ds.container['name']
					else:
						container_name = str(ds.container)
				
				datasources.append({
					'name': ds.name,
					'type': ds.type,
					'container': container_name,
					'description': getattr(ds, 'description', '') or f'{ds.type} 데이터소스'
				})
		except Exception:
			pass
		
		# 인덱서 목록 가져오기
		indexers = []
		try:
			for indexer in indexer_client.get_indexers():
				indexers.append({
					'name': indexer.name,
					'data_source_name': indexer.data_source_name,
					'target_index_name': indexer.target_index_name,
					'description': getattr(indexer, 'description', '') or f'{indexer.data_source_name} → {indexer.target_index_name}'
				})
		except Exception:
			pass
		
		return datasources, indexers
		
	except ImportError:
		return [], []
	except Exception:
		return [], []


def get_available_search_indexes():
	"""사용 가능한 AI Search 인덱스 목록을 반환하는 함수"""
	try:
		from azure.search.documents.indexes import SearchIndexClient
		from azure.identity import ClientSecretCredential, ManagedIdentityCredential
		from azure.core.credentials import AzureKeyCredential
		
		if not SEARCH_ENDPOINT:
			return []
		
		# 인증 설정
		search_key = os.getenv("AZURE_SEARCH_KEY")
		if search_key:
			credential = AzureKeyCredential(search_key)
		else:
			# Service Principal 또는 Managed Identity 사용
			client_id = os.getenv("AZURE_CLIENT_ID")
			tenant_id = os.getenv("AZURE_TENANT_ID")
			client_secret = os.getenv("AZURE_CLIENT_SECRET")
			if client_id and tenant_id and client_secret:
				credential = ClientSecretCredential(tenant_id=tenant_id, client_id=client_id, client_secret=client_secret)
			else:
				credential = ManagedIdentityCredential()
		
		# SearchIndexClient로 인덱스 목록 가져오기
		index_client = SearchIndexClient(
			endpoint=SEARCH_ENDPOINT,
			credential=credential
		)
		
		indexes = []
		for index in index_client.list_indexes():
			indexes.append({
				'name': index.name,
				'fields_count': len(index.fields) if index.fields else 0,
				'description': getattr(index, 'description', '') or ''
			})
		
		return indexes
		
	except ImportError:
		# Azure Search SDK가 없으면 빈 목록 반환
		return []
	except Exception:
		# 기타 오류 시 빈 목록 반환
		return []


def get_indexes_for_container(container_name: str):
	"""특정 컨테이너에 연결된 데이터소스-인덱서를 통해 인덱스 목록을 반환하는 함수"""
	try:
		# 데이터소스와 인덱서 정보 가져오기
		datasources, indexers = get_datasources_and_indexers()
		all_indexes = get_available_search_indexes()
		
		if not datasources or not indexers or not all_indexes:
			# 인덱서 정보만 있으면 그것을 이용
			if indexers and all_indexes:
				return get_indexes_from_indexers_only(container_name, indexers, all_indexes)
			else:
				return get_legacy_indexes_for_container(container_name, all_indexes)
		
		# 선택한 컨테이너와 연결된 데이터소스 찾기
		matching_datasources = []
		for ds in datasources:
			ds_container = ds.get('container')
			if ds_container:
				# 정확한 매치와 부분 매치 모두 확인
				if (container_name.lower() == ds_container.lower() or 
					container_name.lower() in ds_container.lower() or 
					ds_container.lower() in container_name.lower()):
					matching_datasources.append(ds)
		
		if not matching_datasources:
			return get_legacy_indexes_for_container(container_name, all_indexes)
		
		# 매칭된 데이터소스에 연결된 인덱서와 인덱스 찾기
		available_indexes = []
		added_names = set()
		
		for ds in matching_datasources:
			# 해당 데이터소스를 사용하는 인덱서 찾기
			related_indexers = [idx for idx in indexers if idx['data_source_name'] == ds['name']]
			
			for indexer in related_indexers:
				target_index_name = indexer['target_index_name']
				
				# 실제 인덱스 정보 가져오기
				index_info = next((idx for idx in all_indexes if idx['name'] == target_index_name), None)
				
				if index_info and index_info['name'] not in added_names:
					# 데이터소스-인덱서 정보 추가
					enhanced_info = index_info.copy()
					enhanced_info['data_source'] = ds['name']
					enhanced_info['indexer'] = indexer['name']
					enhanced_info['description'] = f"{ds['container']} → {ds['name']} → {indexer['name']} → {target_index_name}"
					
					available_indexes.append(enhanced_info)
					added_names.add(index_info['name'])
		
		if not available_indexes:
			return get_legacy_indexes_for_container(container_name, all_indexes)
		
		return available_indexes
		
	except Exception:
		# 오류 시 기본 방식으로 폴백
		all_indexes = get_available_search_indexes()
		return get_legacy_indexes_for_container(container_name, all_indexes)


def get_indexes_from_indexers_only(container_name: str, indexers: list, all_indexes: list):
	"""인덱서 정보만으로 컨테이너에 해당하는 인덱스 찾기"""
	try:
		# 컨테이너 이름과 관련된 인덱서 찾기 (데이터소스 이름에서 컨테이너 추정)
		matching_indexers = []
		for indexer in indexers:
			ds_name = indexer.get('data_source_name', '').lower()
			
			# 데이터소스 이름에 컨테이너 이름이 포함되어 있는지 확인
			if (container_name.lower() in ds_name or 
				ds_name in container_name.lower() or
				container_name.replace('-', '').lower() in ds_name.replace('-', '') or
				ds_name.replace('-', '') in container_name.replace('-', '').lower()):
				
				matching_indexers.append(indexer)
		
		if not matching_indexers:
			return get_legacy_indexes_for_container(container_name, all_indexes)
		
		# 매칭된 인덱서의 타겟 인덱스들 수집
		result_indexes = []
		for indexer in matching_indexers:
			target_index_name = indexer.get('target_index_name')
			if target_index_name:
				# 실제 인덱스 정보 찾기
				index_info = next((idx for idx in all_indexes if idx['name'] == target_index_name), None)
				if index_info:
					enhanced_info = index_info.copy()
					enhanced_info['indexer'] = indexer['name']
					enhanced_info['data_source_guess'] = indexer['data_source_name']
					enhanced_info['description'] = f"인덱서 {indexer['name']}를 통한 {target_index_name}"
					result_indexes.append(enhanced_info)
		
		return result_indexes if result_indexes else get_legacy_indexes_for_container(container_name, all_indexes)
		
	except Exception:
		return get_legacy_indexes_for_container(container_name, all_indexes)


def get_legacy_indexes_for_container(container_name: str, all_indexes: list):
	"""기존 방식의 컨테이너별 인덱스 매핑 (폴백용) - 실제 존재하는 인덱스만 반환"""
	if not all_indexes:
		return []
	
	# 컨테이너 이름과 유사한 인덱스 이름 패턴 매칭
	container_keywords = [
		container_name.lower(),
		container_name.lower().replace('-', ''),
		container_name.lower().replace('_', ''),
	]
	
	# 환경변수에서 설정된 기본 인덱스도 추가
	if SEARCH_INDEX:
		container_keywords.append(SEARCH_INDEX.lower())
	
	available_indexes = []
	added_names = set()
	
	# 실제 존재하는 인덱스 중에서 컨테이너 이름과 관련된 것들만 찾기
	for idx in all_indexes:
		idx_name_lower = idx['name'].lower()
		
		# 인덱스 이름에 컨테이너 키워드가 포함되어 있는지 확인
		for keyword in container_keywords:
			if (keyword in idx_name_lower or idx_name_lower in keyword) and idx['name'] not in added_names:
				available_indexes.append(idx)
				added_names.add(idx['name'])
				break
	
	# 매칭되는 인덱스가 없으면 빈 목록 반환 (더 이상 강제로 기본값 생성하지 않음)
	return available_indexes


def ask_question_with_container(query: str, container_name: str = None, search_index: str = None):
	"""컨테이너별 인덱스를 사용하여 질문하는 함수"""
	client = _get_client()

	# Dynamic Azure Search auth: use api_key if available, else Managed Identity
	search_key = os.getenv("AZURE_SEARCH_KEY")
	if search_key:
		search_auth = {"type": "api_key", "key": search_key}
	else:
		search_auth = {"type": "system_assigned_managed_identity"}

	if not SEARCH_ENDPOINT:
		raise ValueError("AZURE_SEARCH_ENDPOINT 환경 변수가 설정되지 않았습니다.")

	# 인덱스 결정 로직
	if search_index == "NO_INDEX":
		# 사용자가 명시적으로 인덱스 미사용을 선택한 경우
		final_search_index = None
		use_search = False
	elif search_index:
		# 직접 지정된 인덱스 사용
		use_search = True
		final_search_index = search_index
	elif container_name and container_name != "기본 Storage (일반 질문)":
		# 컨테이너가 지정되었지만 인덱스가 명시되지 않은 경우에만 자동 매핑 사용
		actual_container_name = container_name.split(" (")[0].split(" 🔍")[0]
		final_search_index = get_index_for_container(actual_container_name)
		use_search = final_search_index is not None  # 인덱스가 실제로 존재할 때만 사용
	else:
		# 일반 질문의 경우 AI Search 사용하지 않음
		final_search_index = None
		use_search = False

	# AI Search를 사용하는 경우와 일반 질문인 경우 구분
	if use_search and final_search_index:
		completion = client.chat.completions.create(
			model=DEPLOYMENT,
			messages=[{"role": "user", "content": query}],
			max_tokens=1024,
			temperature=0.7,
			top_p=0.95,
			frequency_penalty=0,
			presence_penalty=0,
			extra_body={
				"data_sources": [
					{
						"type": "azure_search",
						"parameters": {
							"endpoint": SEARCH_ENDPOINT,
							"index_name": final_search_index,
							"authentication": search_auth,
						},
					}
				]
			},
		)
		
		# 인용 정보 추출
		references = getattr(completion.choices[0].message, "context", None)
		citations = []
		if isinstance(references, dict) and "citations" in references:
			citations = references["citations"]
		
		return {
			"content": completion.choices[0].message.content,
			"citations": citations,
			"index_used": final_search_index,
			"container": container_name
		}
	else:
		# AI Search 없이 일반 OpenAI 답변
		completion = client.chat.completions.create(
			model=DEPLOYMENT,
			messages=[{"role": "user", "content": query}],
			max_tokens=1024,
			temperature=0.7,
			top_p=0.95,
			frequency_penalty=0,
			presence_penalty=0,
		)
		
		# 반환값에서 미사용 케이스 구분
		if search_index == "NO_INDEX":
			return {
				"content": completion.choices[0].message.content,
				"citations": [],
				"index_used": "미사용",
				"container": container_name or "일반 질문"
			}
		else:
			return {
				"content": completion.choices[0].message.content,
				"citations": [],
				"index_used": None,
				"container": "일반 질문"
			}


def ask_question(query: str):
	"""기존 함수 (하위 호환성 유지)"""
	result = ask_question_with_container(query)
	return result["content"]


if __name__ == "__main__":
	q = input("질문을 입력하세요: ")
	print(ask_question(q))
