from fastapi import FastAPI, HTTPException
import uvicorn
from client import MCPManager
from contextlib import asynccontextmanager

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

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)