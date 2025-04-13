# MCP Python Application

This is a  MCP application designed to interact with external resources. 

## Requirements

- Python 3.7 or higher
- `asyncio` library (included with Python)
- `mcp` (custom library for handling MCP communication)

## Setup

1. **Clone the repository** (or download the script files) to your local machine.

2. **Run the client** :
    
    ```bash
    uv run client.py
    ```
    
    The server script can be a Python `.py` or JavaScript `.js` file.
    
## Example Workflow

1. The user enters a query like:
    ```bash
    http://127.0.0.1:8000/process_message
    {
        // 哈囉
        // 我想知道我有哪些collections
        // 幫我輸出隨便五個資料
        "message": "幫我輸出隨便五個資料",
        "session_id": "1"
    }
    Question1: How is the weather in California today?
    Question2: What collections are available in the database?
    ```
