import os
from dotenv import load_dotenv
load_dotenv()

from langchain_openai import ChatOpenAI, OpenAIEmbeddings

print("=== 测试 LLM ===")
llm = ChatOpenAI(
    model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL") or os.getenv("OPENAI_API_BASE"),
)
print(llm.invoke("用一句话证明你通了").content)

print("=== 测试 Embedding ===")
emb = OpenAIEmbeddings(
    model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL") or os.getenv("OPENAI_API_BASE"),
)
vec = emb.embed_query("测试")
print(f"向量维度: {len(vec)}")

print("=== 全部通过 ===")
