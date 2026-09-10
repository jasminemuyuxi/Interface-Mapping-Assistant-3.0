import os

from anthropic import Anthropic
from dotenv import load_dotenv


# 读取 .env
load_dotenv()

api_key = os.getenv("ANTHROPIC_API_KEY")
workspace_id = os.getenv("ANTHROPIC_WORKSPACE_ID")
model_name = os.getenv("CLAUDE_MODEL", "claude-sonnet-5")


# 检查环境变量
if not api_key:
    raise RuntimeError(
        "没有找到 ANTHROPIC_API_KEY，请检查 .env 文件。"
    )

if not workspace_id:
    raise RuntimeError(
        "没有找到 ANTHROPIC_WORKSPACE_ID，请检查 .env 文件。"
    )


# 创建 Claude Client
client = Anthropic(
    api_key=api_key,
    default_headers={
        "anthropic-workspace-id": workspace_id
    }
)


print("正在连接 Claude API...")


response = client.messages.create(
    model=model_name,
    max_tokens=200,
    messages=[
        {
            "role": "user",
            "content": (
                "Reply with exactly this sentence: "
                "Claude API connection successful"
            )
        }
    ]
)


for block in response.content:
    if block.type == "text":
        print(block.text)


print("测试结束。")