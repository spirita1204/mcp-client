import asyncio
from typing import Optional
from contextlib import AsyncExitStack
import json
import requests

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from dotenv import load_dotenv

# load_dotenv()  # 從 .env 文件加載環境變量

# Load configuration
with open("config.json", "r") as f:
    config = json.load(f)

class MCPClient:
    def __init__(self, server_params: StdioServerParameters):
        # 初始化客戶端核心組件
        self.session: Optional[ClientSession] = None  # MCP 會話對象
        self.exit_stack = AsyncExitStack()  # 用於管理異步上下文
        # self.base_url = config["base_url"] # Ollama 服務地址
        self.base_url = config["base_url_ngrok"]
        self.model = config["model"]  # 使用的 Ollama 模型名稱
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

    async def process_query(self, query: str) -> str:
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
            "model": self.model,
            "messages": all_messages,
            "stream": False
        }
        
        try:
            # 發送 HTTP 請求到 Ollama 服務
            api_response = requests.post(
                f"{self.base_url}", 
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
                tool_call = json.loads(assistant_message)
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
                                f"{self.base_url}", 
                                json={
                                    "model": self.model,
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

    def _extract_tool_calls(self, message):
        """從 LLM 回應中提取 JSON 格式的工具調用"""
        tool_calls = []
        
        # 使用正則表達式查找代碼塊
        import re
        json_blocks = re.findall(r'```(?:json)?\s*(.*?)\s*```', message, re.DOTALL)
        
        # 嘗試解析每個代碼塊
        for block in json_blocks:
            try:
                # 解析 JSON 數據
                data = json.loads(block)
                # 檢查是否是工具調用格式
                if isinstance(data, dict) and "tool" in data:
                    tool_calls.append(data)
            except json.JSONDecodeError:
                continue
                
        return tool_calls

    def _extract_tool_calls(self, message):
        """從 LLM 回應中提取 JSON 格式的工具調用"""
        tool_calls = []
        
        try:
            # 直接嘗試解析 message 內容
            if isinstance(message, str):
                try:
                    # 如果 message 是 JSON 字串
                    data = json.loads(message)
                except json.JSONDecodeError:
                    # 如果不是直接的 JSON，回退到原始方法
                    import re
                    json_blocks = re.findall(r'```(?:json)?\s*(.*?)\s*```', message, re.DOTALL)
                    
                    for block in json_blocks:
                        try:
                            data = json.loads(block)
                            if isinstance(data, dict) and "tool" in data:
                                tool_calls.append(data)
                        except json.JSONDecodeError:
                            continue
            
            # 如果是字典且包含工具信息
            elif isinstance(message, dict):
                data = message
            else:
                return tool_calls

            # 檢查是否是工具調用格式
            if isinstance(data, dict) and "tool" in data:
                tool_calls.append(data)
            
            # 檢查 message 對象中的 content
            elif isinstance(data, dict) and "message" in data:
                message_content = data.get("message", {})
                if isinstance(message_content, dict) and "content" in message_content:
                    try:
                        tool_data = json.loads(message_content["content"])
                        if isinstance(tool_data, dict) and "tool" in tool_data:
                            tool_calls.append(tool_data)
                    except (json.JSONDecodeError, TypeError):
                        pass
            
        except Exception as e:
            print(f"工具調用解析錯誤: {e}")
        
        return tool_calls
    
    async def chat_loop(self):
        """運行交互式命令行聊天界面"""
        # 顯示歡迎信息
        print("\n已啟動 MCP 客戶端，使用本地 Ollama!")
        print(f"使用模型: {self.model}")
        print("輸入您的問題或輸入 'quit' 退出。")
        
        # 主聊天循環
        while True:
            try:
                # 獲取用戶輸入
                query = input("\n問題: ").strip()
                
                # 檢查退出命令
                if query.lower() == 'quit':
                    break
                
                # 處理查詢並顯示結果
                response = await self.process_query(query)
                print("\n" + response)
                    
            except Exception as e:
                print(f"\n錯誤: {str(e)}")
    
    async def cleanup(self):
        """清理所有資源和連接"""
        await self.exit_stack.aclose()

async def main():
    """主程序入口點"""
    print("Starting MCP client...")
    mcp_clients = []
    
    # 創建客戶端實例
    for server in config["mcp_servers"]:
        print(f"Setting up server: {server['name']}")
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
            # 啟動聊天界面
            await client.chat_loop()
        finally:
            # 確保資源被正確釋放
            await client.cleanup()

if __name__ == "__main__":
    import sys
    asyncio.run(main())