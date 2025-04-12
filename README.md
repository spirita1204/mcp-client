# MCPClient Python Application

This is a Python client application designed to interact with an MCP (Model Context Protocol) server. 

## Features

- **Asynchronous Communication:** Uses `asyncio` for non-blocking communication between the client and server.
- **Customizable Server Scripts:** The client can connect to both Python and JavaScript-based server scripts.
- **Tool Management:** Dynamically fetches and interacts with tools available on the connected server.
- **Chat Interface:** Provides a simple command-line interface to interact with the server in a conversational format.
- **Tool Integration:** Supports extracting JSON-formatted tool calls from server responses and executing them.
- **Environment Variable Loading:** Supports loading environment variables from a `.env` file using the `dotenv` package.

## Requirements

- Python 3.7 or higher
- `asyncio` library (included with Python)
- `requests` for HTTP requests to the server
- `mcp` (custom library for handling MCP communication)
- `dotenv` for environment variable management

## Setup

1. **Clone the repository** (or download the script files) to your local machine.

2. **Install required dependencies:**

   ```bash
   pip install -r requirements.txt
1. **Create a `.env` file** in the root directory to load necessary environment variables. For example:
    
    ```
    BASE_URL=http://localhost:11434
    MODEL=llama3.2
    ```
    
2. **Run the client** with the path to the server script:
    
    ```bash
    python client.py <server_script_path>
    ```
    
    The server script can be a Python `.py` or JavaScript `.js` file.
    

## How It Works

1. **Connecting to the MCP Server:** The client connects to the server via standard input/output channels, using the provided script (`.py` or `.js`).
2. **Processing Queries:** The client sends user queries to the server and receives responses. Available tools are listed and can be called directly from the assistant’s replies.
3. **Tool Execution:** If a response contains a valid tool call (in JSON format), the client extracts the call and triggers the respective tool on the server.
4. **Interaction:** The client interacts with the server in a conversational format, displaying results from server tools and continuing the conversation.

## Example Workflow

1. The user enters a query like:
    
    ```bash
    Question: What is the weather today?
    ```
    
2. The client sends the query to the server, which responds with available tools and information.
3. If the server suggests using a weather tool, the client executes the tool with the necessary parameters and shows the result.
4. The client continues the conversation based on the new information returned by the tool.
https://github.com/furey/mongodb-lens
