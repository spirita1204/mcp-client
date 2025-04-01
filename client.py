import asyncio
from typing import Optional
from contextlib import AsyncExitStack
import json
import requests

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from dotenv import load_dotenv
from typing import Any, List

# load_dotenv()  # 從 .env 文件加載環境變量

# Load configuration
with open("config.json", "r") as f:
    config = json.load(f)

MODEL = config["model"] # 使用的 Ollama 模型名稱
BASE_URL = config["base_url"] # Ollama 服務地址
# BASE_URL = config["base_url_ngrok"]
SYSTEM_PROMPT = config["system_prompt"]

class MCPClient:
    def __init__(self, server_params: StdioServerParameters):
        # 初始化客戶端核心組件
        self.session: Optional[ClientSession] = None  # MCP 會話對象
        self.exit_stack = AsyncExitStack()  # 用於管理異步上下
        self.server_params = server_params

    async def connect_to_server(self):
        """連接到 MCP 服務器腳本並初始化工具列表"""            
        # 建立標準輸入輸出通信通道
        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(self.server_params))
        self.stdio, self.write = stdio_transport
        
        # 創建 MCP 會話
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))
        
        # 初始化 MCP 會話
        await self.session.initialize()
        
        # 獲取可用工具列表
        response = await self.session.list_tools()
        tools = response.tools
        print("\n已連接到服務器，可用工具:", [tool.name for tool in tools])

    #  MCP 伺服器獲取可用工具列表。
    async def get_available_tools(self):
        if not self.session:
            raise RuntimeError("Not connected to MCP server")
        return await self.session.list_tools()
    
     # 用來呼叫具體工具並獲取結果。
    def call_tool(self, tool_name: str) -> Any:
        if not self.session:
            raise RuntimeError("Not connected to MCP server")
        
        async def callable(*args, **kwargs):
            print(f"Calling tool: {tool_name} with args: {kwargs}")
            response = await self.session.call_tool(tool_name, arguments=kwargs)
            return response.content[0].text

        return callable
    
    async def cleanup(self):
        """清理所有資源和連接"""
        await self.exit_stack.aclose()

async def agent_loop(query: str, tools: dict, messages: List[dict] = None):
    messages = messages or [
        {"role": "system", "content": SYSTEM_PROMPT.format(
            tools="\n- ".join(
                [f"{t['name']}: {t['schema']['function']['description']}" for t in tools.values()]
            )
        )}
    ]
    messages.append({"role": "user", "content": query})

    response = await client.chat.completions.create(
        model=MODEL,
        messages=messages,
        tools=[t["schema"] for t in tools.values()] if tools else None,
        max_tokens=4096,
        temperature=0,
    )

    if response.choices[0].message.tool_calls:
        for tool_call in response.choices[0].message.tool_calls:
            arguments = json.loads(tool_call.function.arguments)
            tool_result = await tools[tool_call.function.name]["callable"](**arguments)
            messages.extend([
                response.choices[0].message,
                {"role": "tool", "tool_call_id": tool_call.id, "name": tool_call.function.name, "content": json.dumps(tool_result)},
            ])
        response = await client.chat.completions.create(model=MODEL, messages=messages)

    messages.append({"role": "assistant", "content": response.choices[0].message.content})
    return response.choices[0].message.content, messages
 
async def process_query(query: str) -> str:
    """處理用戶查詢並調用適當的工具"""
    # 構建基本消息結構
    messages = [
        {
            "role": "user",
            "content": query
        }
    ]

    # 獲取可用工具列表
    response = await self.session.list_tools()
    available_tools = [{ 
        "name": tool.name,
        "description": tool.description,
        "parameters": tool.inputSchema
    } for tool in response.tools]

    # 構建系統提示以包含工具信息
    tools_prompt = "您可以使用以下工具：\n"
    for tool in available_tools:
        tools_prompt += f"- {tool['name']}: {tool['description']}\n"
        tools_prompt += f"  參數: {json.dumps(tool['parameters'], indent=2)}\n\n"
    
    tools_prompt += "\n要使用工具，請按以下格式回應：\n"
    tools_prompt += "```json\n{\"tool\": \"工具名稱\", \"parameters\": {\"參數1\": \"值1\"}}\n```\n"
    tools_prompt += "使用工具後，我會向您展示結果，然後您可以繼續對話。"
    
    # 添加系統提示到消息隊列
    system_prompt = {
        "role": "system",
        "content": tools_prompt
    }
    all_messages = [system_prompt] + messages

    # 準備 Ollama API 請求
    ollama_payload = {
        "model": MODEL,
        "messages": all_messages,
        "stream": False
    }
    
    try:
        # 發送 HTTP 請求到 Ollama 服務
        api_response = requests.post(
            f"{BASE_URL}", 
            json=ollama_payload
        )
        
        # 檢查 HTTP 響應狀態
        if api_response.status_code != 200:
            return f"錯誤: Ollama 返回狀態碼 {api_response.status_code}: {api_response.text}"
        
        # 解析 JSON 響應
        response_data = api_response.json()
        print('[response_data] ' + json.dumps(response_data, indent=2, ensure_ascii=False))
        # 收集最終輸出
        final_text = []
        
        # 處理 Ollama 的回應內容
        if "message" in response_data and "content" in response_data["message"]:
            assistant_message = response_data["message"]["content"]
            try:
                tool_call = json.loads(assistant_message)
            except Exception as e:
                final_text.append(assistant_message)
                return "\n".join(final_text)
            if "tool" in tool_call and "parameters" in tool_call:
                # 處理每個工具調用
                if tool_call:
                    tool_name = tool_call["tool"]
                    tool_params = tool_call["parameters"]
                    
                    if tool_name:
                        # 執行 MCP 工具調用
                        result = await self.session.call_tool(tool_name, tool_params)
                        final_text.append(f"[調用工具 {tool_name}，參數為 {tool_params}]")
                        final_text.append(f"工具結果: {result.content}")
                        
                        # 更新對話歷史
                        all_messages.append({
                            "role": "assistant",
                            "content": assistant_message
                        })
                        
                        all_messages.append({
                            "role": "user",
                            "content": f"工具 {tool_name} 的結果: {result.content}"
                        })
                        
                        # 獲取 Ollama 對工具結果的後續回應
                        follow_up_response = requests.post(
                            f"{BASE_URL}", 
                            json={
                                "model": MODEL,
                                "messages": all_messages,
                                "stream": False
                            }
                        )
                        
                        # 處理後續回應
                        if follow_up_response.status_code == 200:
                            follow_up_data = follow_up_response.json()
                            if "message" in follow_up_data and "content" in follow_up_data["message"]:
                                follow_up_content = follow_up_data["message"]["content"]
                                final_text.append(follow_up_content)
        
        # 合併所有輸出並返回
        return "\n".join(final_text)
        
    except Exception as e:
        return f"連接到 Ollama 時出錯: {str(e)}"

async def chat_loop():
    """運行交互式命令行聊天界面"""
    # 顯示歡迎信息
    print("\n已啟動 MCP 客戶端，使用本地 Ollama!")
    print("輸入您的問題或輸入 'quit' 退出。")
    
    # 主聊天循環
    while True:
        try:
            # 獲取用戶輸入
            query = input("\n問題: ").strip()
            
            # 檢查退出命令
            if query.lower() == 'quit':
                break
            response, messages = await agent_loop(query, tools, messages)
            # 處理查詢並顯示結果
            response = await process_query(query)
            print("\n" + response)
                
        except Exception as e:
            print(f"\n錯誤: {str(e)}")

async def agent_loop(query: str, tools: dict, messages: List[dict] = None):
    messages = messages or [
        {"role": "system", "content": SYSTEM_PROMPT.format(
            tools="\n- ".join(
                [f"{t['name']}: {t['schema']['function']['description']}" for t in tools.values()]
            )
        )}
    ]
    messages.append({"role": "user", "content": query})

    response = await client.chat.completions.create(
        model=MODEL,
        messages=messages,
        tools=[t["schema"] for t in tools.values()] if tools else None,
        max_tokens=4096,
        temperature=0,
    )

    if response.choices[0].message.tool_calls:
        for tool_call in response.choices[0].message.tool_calls:
            arguments = json.loads(tool_call.function.arguments)
            tool_result = await tools[tool_call.function.name]["callable"](**arguments)
            messages.extend([
                response.choices[0].message,
                {"role": "tool", "tool_call_id": tool_call.id, "name": tool_call.function.name, "content": json.dumps(tool_result)},
            ])
        response = await client.chat.completions.create(model=MODEL, messages=messages)

    messages.append({"role": "assistant", "content": response.choices[0].message.content})
    return response.choices[0].message.content, messages

async def main():
    """主程序入口點"""
    print("Starting MCP client...")
    mcp_clients = []
    
    # 創建客戶端實例
    for server in config["mcp_servers"]:
        print(f"Setting up server: [{server['name']}]")
        server_params = StdioServerParameters(
            # 服務器執行的命令，這裡是 python
            command=server["command"],
            # 啟動命令的附加参數
            args=server["args"],
            # 默認為 None，表示使用當前環境變量
            env=server["env"],
        )
        client = MCPClient(server_params)
        mcp_clients.append(client)
        try:
            # 連接到 MCP 服務器
            await client.connect_to_server()
        except Exception as e:
            # 確保資源被正確釋放
            await client.cleanup()
    # 啟動聊天界面
    await chat_loop()

if __name__ == "__main__":
    import sys
    asyncio.run(main())
