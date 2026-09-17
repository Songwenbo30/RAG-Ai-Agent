
import os
import json
from dotenv import load_dotenv
from typing import List, Optional
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from vector_database import get_vector_db
from langchain_core.documents import Document
from langchain_core.tools import tool


load_dotenv()


API_KEY = os.getenv("OPENAI_API_KEY")
BASE_URL = os.getenv("OPENAI_API_BASE") or os.getenv("OPENAI_BASE_URL") or "https://api.uiuihao.com/v1"
MODEL_NAME = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

from langchain_openai import ChatOpenAI, OpenAIEmbeddings

llm = ChatOpenAI(
    model=MODEL_NAME,
    api_key=API_KEY,
    base_url=BASE_URL,
    temperature=0,
)

embeddings = OpenAIEmbeddings(
    model=EMBEDDING_MODEL,
    api_key=API_KEY,
    base_url=BASE_URL,
)



@tool(response_format="content_and_artifact")
def retrieve(query: str) -> tuple[str, List[Document]]:
    """
    检索知识库中与问题相关的文档片段。
    当用户提问涉及文档内容、简历、项目经验等时，必须使用此工具。
    可以多次调用以获取不同方面的信息。
    """
    vector_db = get_vector_db()
    if vector_db is None:
        return "知识库尚未建立，请先上传文档。", []

    # 用 similarity_search_with_relevance_scores 做分数过滤
    results = vector_db.similarity_search_with_relevance_scores(query=query, k=5)

    if not results:
        return "未检索到相关文档。", []

    # ChromaDB 余弦相似度范围 [-1, 1]，归一化到 [0, 1]
    filtered_docs = []
    serialized_parts = []
    for doc, score in results:
        normalized_score = (score + 1) / 2
        if normalized_score >= 0.3:  # 宽松阈值，避免漏掉相关内容
            filtered_docs.append(doc)
            source = doc.metadata.get('source', '未知来源')
            page = doc.metadata.get('page', '?')
            serialized_parts.append(
                f"[来源: {source} | 页码: {page} | 相关度: {normalized_score:.2f}]\n{doc.page_content}"
            )

    # 如果全部被阈值过滤，退而求其次返回 top-2
    if not filtered_docs:
        filtered_docs = [doc for doc, _ in results[:2]]
        serialized_parts = [
            f"[来源: {doc.metadata.get('source', '未知')} | 页码: {doc.metadata.get('page', '?')}]\n{doc.page_content}"
            for doc in filtered_docs
        ]

    serialized = "\n\n---\n\n".join(serialized_parts)
    return serialized, filtered_docs


@tool
def get_current_time() -> str:
    """获取当前的日期和时间。当用户问"今天几号"、"现在几点"时调用。"""
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@tool
def calculator(expression: str) -> str:
    """
    计算数学表达式。输入应为有效的 Python 表达式。
    示例: "123 * 456", "2 ** 10", "3.14 * (10 ** 2)"
    """
    try:
        allowed_names = {"__builtins__": {}}
        result = eval(expression, allowed_names, {})
        return str(result)
    except Exception as e:
        return f"计算错误: {e}"



SYSTEM_PROMPT = """你是一个智能助手，可以回答用户问题并使用工具检索知识库。

规则：
1. 当用户问题涉及文档内容时，必须使用 retrieve 工具查找相关信息。
2. 使用 retrieve 时，你可以将用户问题改写为更合适的关键词以提高检索效果。
3. 可以进行多次检索以得出完整答案。
4. 如果检索结果中没有答案，明确告知用户"知识库中未找到相关信息"，不要编造。
5. 回答时注明信息来源的文件名。
6. 对于时间问题，使用 get_current_time 工具。
7. 对于计算问题，使用 calculator 工具。
8. 回答简洁清晰，使用中文。
"""


memory = MemorySaver()

agent = create_react_agent(
    llm,
    [retrieve, get_current_time, calculator],
    checkpointer=memory,
    prompt=SYSTEM_PROMPT,
)


def agent_executor(query_text: str, agent_type: str = "langgraph", chat_id: str = "default"):
    """
    兼容原 agent_legacy.py 的调用签名，供 app.py 直接替换使用。

    用法（在 app.py 里）:
        from agent_langgraph import agent_executor
        response = agent_executor(query_text=query, agent="langgraph", chat_id=str(chat_id))
        # response["response"] -> 最终回答文本
        # response["sources"] -> 来源文件列表
    """
    config = {"configurable": {"thread_id": chat_id}}

    result = agent.invoke(
        {"messages": [{"role": "user", "content": query_text}]},
        config=config,
    )

    # 提取最终回答
    final_message = result["messages"][-1]
    response_content = final_message.content if hasattr(final_message, 'content') else str(final_message)

    # 提取检索来源
    sources = []
    for msg in result["messages"]:
        if hasattr(msg, 'name') and msg.name == 'retrieve':
            if hasattr(msg, 'artifact') and msg.artifact:
                for doc in msg.artifact:
                    if hasattr(doc, 'metadata'):
                        src = doc.metadata.get('source', '')
                        if src and src not in sources:
                            sources.append(src)

    return {
        "response": response_content,
        "sources": sources,
        "messages": result["messages"],
    }


def agent_stream(query_text: str, chat_id: str = "default"):

    # 流式调用

    config = {"configurable": {"thread_id": chat_id}}

    for message_chunk, metadata in agent.stream(
        {"messages": [{"role": "user", "content": query_text}]},
        stream_mode="messages",
        config=config,
    ):
        # 只处理 AI 消息的增量内容
        from langchain_core.messages import AIMessageChunk
        if isinstance(message_chunk, AIMessageChunk):
            if message_chunk.content:
                yield message_chunk.content


def agent_stream_events(query_text: str, chat_id: str = "default"):
    """
    流式调用 - 返回结构化事件生成器。
    yield 格式:
    - {"type": "content", "content": "token文本"}
    - {"type": "step_start", "tool": "工具名", "input": "工具输入"}
    - {"type": "step_end", "tool": "工具名", "output": "工具输出摘要"}
    """
    from langchain_core.messages import AIMessageChunk, ToolMessageChunk

    config = {"configurable": {"thread_id": chat_id}}

    for message_chunk, metadata in agent.stream(
        {"messages": [{"role": "user", "content": query_text}]},
        stream_mode="messages",
        config=config,
    ):

        if isinstance(message_chunk, AIMessageChunk):
            # 1) 工具调用开始
            if message_chunk.tool_call_chunks:
                for tc in message_chunk.tool_call_chunks:
                    tool_name = tc.get('name', '')
                    tool_input = tc.get('args', '')
                    if tool_name:
                        yield {
                            "type": "step_start",
                            "tool": tool_name,
                            "input": tool_input if isinstance(tool_input, str) else json.dumps(tool_input, ensure_ascii=False)
                        }

            # 2) 文本 token
            if message_chunk.content:
                yield {
                    "type": "content",
                    "content": message_chunk.content
                }

        elif isinstance(message_chunk, ToolMessageChunk) or type(message_chunk).__name__ == 'ToolMessage':
            # 3) 工具返回结果
            output = message_chunk.content or ""
            if len(output) > 300:
                output = output[:300] + "..."

            tool_name = metadata.get('langgraph_node', 'retrieve')
            yield {
                "type": "step_end",
                "tool": tool_name,
                "output": output
            }


if __name__ == "__main__":
    print("=== LangGraph Agent 本地测试 ===\n")

    test_queries = [
        "你好，你是谁？",
        "知识库里有什么文件？",
        "今天几号？",
        "计算 123 * 456",
    ]

    for q in test_queries:
        print(f"问题: {q}")
        print("-" * 50)
        result = agent_executor(q, chat_id="test")
        print(f"回答: {result['response']}")
        if result['sources']:
            print(f"来源: {result['sources']}")
        print("\n" + "=" * 50 + "\n")