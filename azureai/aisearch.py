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
	# 컨테이너별 기본 인덱스 매핑
	container_index_mapping = {
		"github-api": SEARCH_INDEX or "azureblob-index",
		"documents": "documents-index",
		"data": "data-index", 
		"backup": "backup-index",
		"media": "media-index",
		"logs": "logs-index",
		"pdf-docs": "pdf-index",
		"text-files": "text-index",
	}
	
	# 정확한 매치를 먼저 시도
	if container_name in container_index_mapping:
		return container_index_mapping[container_name]
	
	# 부분 매치 시도 (컨테이너 이름에 키워드가 포함된 경우)
	for keyword, index_name in container_index_mapping.items():
		if keyword in container_name.lower():
			return index_name
	
	# 매치되는 인덱스가 없으면 기본 인덱스 사용
	return SEARCH_INDEX or "azureblob-index"


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
		
		# 실제 환경에서 사용되는 인덱스들을 확인
		known_indexes = [
			SEARCH_INDEX or "azureblob-index",  # 기본 인덱스
			"documents-index",
			"data-index", 
			"backup-index",
			"media-index",
			"logs-index",
			"pdf-docs-index",
			"text-files-index",
		]
		
		# 중복 제거
		known_indexes = list(set(filter(None, known_indexes)))
		
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
							# 또는 다른 필드명으로 컨테이너 정보 확인
							for field_name, field_value in result.items():
								if isinstance(field_value, str) and 'github-api' in field_value.lower():
									if 'github-api' not in indexed_containers:
										indexed_containers.append('github-api')
								elif isinstance(field_value, str) and '/containers/' in field_value:
									try:
										container_name = field_value.split('/containers/')[1].split('/')[0]
										if container_name and container_name not in indexed_containers:
											indexed_containers.append(container_name)
									except:
										continue
								
						# 기본적으로 알려진 컨테이너들도 추가 (인덱스가 존재하므로)
						if not indexed_containers:
							indexed_containers.extend(['github-api', 'documents', 'data'])
							
					except Exception:
						# 메타데이터 추출 실패 시 기본 컨테이너들 추가
						indexed_containers.extend(['github-api', 'documents', 'data'])
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
		# Azure Search SDK가 없으면 기본 컨테이너 반환
		return ['github-api']
	except Exception:
		# 기타 오류 시 기본 컨테이너 반환
		return ['github-api']


def is_container_indexed(container_name: str) -> bool:
	"""특정 컨테이너가 인덱스되어 있는지 확인하는 함수"""
	try:
		indexed_containers = get_indexed_containers()
		
		# 정확한 매치 확인
		if container_name in indexed_containers:
			return True
		
		# github-api 특별 처리
		if container_name.lower() == 'github-api':
			return True
		
		# 부분 매치 확인
		for indexed_container in indexed_containers:
			if indexed_container in container_name.lower() or container_name.lower() in indexed_container:
				return True
		
		# github 관련 컨테이너는 기본 인덱스 사용으로 간주
		if 'github' in container_name.lower() or 'api' in container_name.lower():
			return True
		
		return False
		
	except Exception:
		# 에러 시 github-api는 true로 간주
		return container_name.lower() == 'github-api'


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
		# Azure Search SDK가 없으면 기본 인덱스들 반환
		return [
			{'name': SEARCH_INDEX or 'azureblob-index', 'fields_count': 0, 'description': '기본 인덱스'},
			{'name': 'documents-index', 'fields_count': 0, 'description': '문서 인덱스'},
			{'name': 'data-index', 'fields_count': 0, 'description': '데이터 인덱스'}
		]
	except Exception:
		# 기타 오류 시 기본 인덱스 반환
		return [
			{'name': SEARCH_INDEX or 'azureblob-index', 'fields_count': 0, 'description': '기본 인덱스'}
		]


def get_indexes_for_container(container_name: str):
	"""특정 컨테이너에서 사용 가능한 인덱스 목록을 반환하는 함수"""
	all_indexes = get_available_search_indexes()
	
	if not all_indexes:
		# 기본 인덱스라도 반환
		default_index = SEARCH_INDEX or "azureblob-index"
		return [{'name': default_index, 'fields_count': 0, 'description': '기본 인덱스'}]
	
	# 컨테이너별 추천 인덱스 매핑 (우선순위 순)
	container_preferred_indexes = {
		"github-api": [SEARCH_INDEX or "azureblob-index"],
		"documents": ["documents-index", SEARCH_INDEX or "azureblob-index"],
		"data": ["data-index", SEARCH_INDEX or "azureblob-index"], 
		"backup": ["backup-index", SEARCH_INDEX or "azureblob-index"],
		"media": ["media-index", SEARCH_INDEX or "azureblob-index"],
		"logs": ["logs-index", SEARCH_INDEX or "azureblob-index"],
		"pdf-docs": ["pdf-index", SEARCH_INDEX or "azureblob-index"],
		"text-files": ["text-index", SEARCH_INDEX or "azureblob-index"],
	}
	
	# 선호하는 인덱스 순서 가져오기
	preferred_names = container_preferred_indexes.get(container_name.lower(), [SEARCH_INDEX or "azureblob-index"])
	
	# 인덱스들을 우선순위대로 정렬
	available_indexes = []
	added_names = set()
	
	# 1. 선호하는 인덱스를 먼저 추가 (존재하는 것만)
	for preferred in preferred_names:
		matching_indexes = [idx for idx in all_indexes if idx['name'] == preferred and idx['name'] not in added_names]
		for idx in matching_indexes:
			available_indexes.append(idx)
			added_names.add(idx['name'])
	
	# 2. 나머지 모든 인덱스들 추가 (중복 제거)
	for idx in all_indexes:
		if idx['name'] not in added_names:
			available_indexes.append(idx)
			added_names.add(idx['name'])
	
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
		use_search = True
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
