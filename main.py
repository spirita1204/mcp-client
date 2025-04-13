from fastapi import FastAPI, HTTPException
import uvicorn
from client import MCPManager
from contextlib import asynccontextmanager
import json

manager = None

# Use the new lifespan context manager approach
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialize the MCP manager
    global manager
    manager = MCPManager()
    await manager.initialize()
    print("MCP Manager initialized")
    
    yield  # This is where the app runs
    
    # Shutdown: clean up resources if needed
    # If your MCP clients need cleanup:
    if manager and manager.mcp_clients:
        for client in manager.mcp_clients:
            if hasattr(client, '__aexit__'):
                await client.__aexit__(None, None, None)
    print("MCP Manager cleaned up")

# Pass the lifespan to FastAPI
app = FastAPI(lifespan=lifespan)

@app.post("/process_message/")
async def process_message(request: dict):
    try:
        message = request.get("message")

        session_id = request.get("session_id")
        if not message:
            raise HTTPException(status_code=400, detail="Message is required")
        
        response = await manager.process_message(message, session_id)
        return {"response": response}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

"""初始化寫入終點資訊"""
@app.post("/api/")
async def insert_endPoint(request: dict):
    try:
        prompt  = generate_prompt(request)
        session_id = request.get("session_id")
        print(f"prompt:{prompt}")
        response = await manager.process_message(prompt, session_id)
        return {"response": response}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

"""產生對應prompt"""
def generate_prompt(data):
    match data.get("name"):
        case "endpoint":
            return f"幫我將該筆 json 資訊 {escape_quotes_in_data(data)} insert 到 EndPoint table 中"
        
"""處理字典中的所有字符串，將雙引號加上反斜線。"""
def escape_quotes_in_data(data):
    # 使用 json.dumps() 將字典轉換為帶有反斜線的 JSON 字符串
    return json.dumps(data)
    
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)