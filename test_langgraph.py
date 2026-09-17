from agent_langgraph import agent_executor

# 测试1：普通对话（不走检索）
print("=== 测试1：普通对话 ===")
r1 = agent_executor("你好，你是谁？", chat_id="test-1")
print(f"回答: {r1['response']}")
print()

# 测试2：检索（需要你之前上传过文档）
print("=== 测试2：文档检索 ===")
r2 = agent_executor("知识库里有什么内容？", chat_id="test-2")
print(f"回答: {r2['response']}")
print(f"来源: {r2['sources']}")
print()

# 测试3：工具调用
print("=== 测试3：时间工具 ===")
r3 = agent_executor("今天几号？", chat_id="test-3")
print(f"回答: {r3['response']}")
print()

# 测试4：计算器
print("=== 测试4：计算器 ===")
r4 = agent_executor("计算 123 * 456", chat_id="test-4")
print(f"回答: {r4['response']}")