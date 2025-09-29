
# Azure OpenAI + Azure AI Search RAG 예시
import os
from dotenv import load_dotenv
from openai import AzureOpenAI
from azure.identity import ManagedIdentityCredential, ClientSecretCredential, get_bearer_token_provider

load_dotenv()

ENDPOINT = os.getenv("ENDPOINT_URL", "https://azureopenai-jmg.openai.azure.com/")
DEPLOYMENT = os.getenv("DEPLOYMENT_NAME", "gpt-4.1-mini")
COGNITIVE_RESOURCE = os.getenv('AZURE_COGNITIVE_SERVICES_RESOURCE')
SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT")
SEARCH_INDEX = os.getenv("AZURE_SEARCH_INDEX")



# 인증 방식 자동 선택
RESOURCE_SCOPE = 'https://cognitiveservices.azure.com/.default'
def get_token_provider():
	# Managed Identity 우선 시도
	try:
		mic = ManagedIdentityCredential()
		# 실제 Azure 환경에서만 토큰 발급 성공
		_ = mic.get_token(RESOURCE_SCOPE)
		return get_bearer_token_provider(
			mic,
			RESOURCE_SCOPE
		)
	except Exception as e:
		print("[경고] Managed Identity 인증 실패, Service Principal로 대체합니다.")
		# 로컬 환경: Service Principal 사용
		client_id = os.getenv('AZURE_CLIENT_ID')
		tenant_id = os.getenv('AZURE_TENANT_ID')
		client_secret = os.getenv('AZURE_CLIENT_SECRET')
		if not (client_id and tenant_id and client_secret):
			raise RuntimeError("Service Principal 환경변수가 누락되었습니다. .env 파일을 확인하세요.")
		sp_cred = ClientSecretCredential(tenant_id, client_id, client_secret)
		return get_bearer_token_provider(
			sp_cred,
			RESOURCE_SCOPE
		)

token_provider = get_token_provider()

client = AzureOpenAI(
	azure_endpoint=ENDPOINT,
	azure_ad_token_provider=token_provider,
	api_version='2024-05-01-preview',
)

def ask_question(query: str):
	completion = client.chat.completions.create(
		model=DEPLOYMENT,
		messages=[
			{
				"role": "user",
				"content": query
			}
		],
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
						"index_name": SEARCH_INDEX,
						"authentication": {
							"type": "system_assigned_managed_identity"
						}
					}
				}
			]
		}
	)
	# AI Search 참조 여부 및 출처 정보 확인
	references = getattr(completion.choices[0].message, "context", None)
	if references and "citations" in references:
		print("[참고한 AI Search 문서 출처]")
		for cite in references["citations"]:
			print(f"- {cite.get('url', cite.get('id', ''))}")
	else:
		print("[AI Search 데이터 출처 정보 없음]")
	return completion.choices[0].message.content

# 사용 예시
if __name__ == "__main__":
	question = input("질문을 입력하세요: ")
	answer = ask_question(question)
	print(answer)
