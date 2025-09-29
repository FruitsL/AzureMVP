
# Azure OpenAI + Azure AI Search RAG 예시
import os
from dotenv import load_dotenv
from openai import AzureOpenAI
from azure.identity import ManagedIdentityCredential, get_bearer_token_provider

load_dotenv()

ENDPOINT = os.getenv("ENDPOINT_URL", "https://azureopenai-jmg.openai.azure.com/")
DEPLOYMENT = os.getenv("DEPLOYMENT_NAME", "gpt-4.1-mini")
COGNITIVE_RESOURCE = os.getenv('AZURE_COGNITIVE_SERVICES_RESOURCE')
SEARCH_ENDPOINT = os.getenv("AZURE_AI_SEARCH_ENDPOINT")
SEARCH_INDEX = os.getenv("AZURE_AI_SEARCH_INDEX")

token_provider = get_bearer_token_provider(
	ManagedIdentityCredential(),
	f'https://{COGNITIVE_RESOURCE}.openai.azure.com/.default'
)

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
