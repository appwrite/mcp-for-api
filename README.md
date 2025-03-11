# Appwrite MCP server

[![smithery badge](https://smithery.ai/badge/@appwrite/mcp)](https://smithery.ai/server/@appwrite/mcp)

<!-- Cover image will go here once available -->

## Overview

A Model Context Protocol server for interacting with Appwrite's API. This server provides tools to manage databases, users, functions, teams, and more within your Appwrite project.

## Quick Links
- [Configuration](#configuration)
- [Installation](#installation)
- IDE Integration:
  - [Claude Desktop](#usage-with-claude-desktop)
  - [Zed](#usage-with-zed)
  - [Cursor](#usage-with-cursor)
- [Local Development](#local-development)
- [Debugging](#debugging)

Currently, the server supports the following tools:

- [x] Databases
- [x] Users

> Please note that adding a lot of tools exceeds the context window of the LLM. As a result, we will make available a curated list of tools that are most commonly used.

## Configuration

Create a `.env` file in the directory you're running the server from:

```env
APPWRITE_API_KEY=your-api-key
APPWRITE_PROJECT_ID=your-project-id
APPWRITE_ENDPOINT=your-endpoint  # Optional, defaults to https://cloud.appwrite.io/v1
```
> Note: Ensure that your API Key has the necessary scopes to access the resources you want to use.

## Installation

### Installing via Smithery

To install Appwrite MCP Server for Claude Desktop automatically via [Smithery](https://smithery.ai/server/@appwrite/mcp):

```bash
npx -y @smithery/cli install @appwrite/mcp --client claude
```

### Using uv (recommended)
When using [`uv`](https://docs.astral.sh/uv/) no specific installation is needed. We will
use [`uvx`](https://docs.astral.sh/uv/guides/tools/) to directly run *mcp-server-appwrite*.

```bash
uvx run mcp-server-appwrite
```

### Using pip

```bash
pip install mcp-server-appwrite
```
Then run the server using 

```bash
python -m mcp_server_appwrite
```

## Usage with Claude Desktop

Add this to your `claude_desktop_config.json`:

```json
"mcpServers": {
  "appwrite": {
    "command": "uvx",
    "args": [
      "mcp-server-appwrite"
    ],
    "env": {
      "APPWRITE_PROJECT_ID": "your-project-id",
      "APPWRITE_API_KEY": "your-api-key",
      "APPWRITE_ENDPOINT": "your-endpoint"  // Optional
    }
  }
}
```
Upon successful configuration, you should be able to see the server in the list of available servers in Claude Desktop.

![Claude Desktop Config](images/claude-desktop-integration.png)

## Usage with [Zed](https://github.com/zed-industries/zed)

Add to your Zed settings.json:

```json
"context_servers": {
  "appwrite": {
    "command": "uvx",
    "args": [
      "mcp-server-appwrite"
    ],
    "env": {
      "APPWRITE_PROJECT_ID": "your-project-id",
      "APPWRITE_API_KEY": "your-api-key",
      "APPWRITE_ENDPOINT": "your-endpoint"  // Optional
    }
  }
}
```

## Usage with [Cursor](https://www.cursor.com/)

Head to Cursor `Settings > Features > MCP Servers` and click on **Add New MCP Server**. Choose the type as `Command` and add the command below to the **Command** field.

```bash
APPWRITE_PROJECT_ID=your-project-id APPWRITE_API_KEY=your-api-key uvx mcp-server-appwrite
```

![Cursor Settings](./images/cursor-integration.png)

## Local Development

Clone the repository

```bash
git clone https://github.com/appwrite/mcp.git
```

Install `uv`

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Create virtual environment

```bash
uv venv
source .venv/bin/activate
```

Run the server

```bash
uv run -v --directory ./ mcp-server-appwrite
```

## Debugging

You can use the MCP inspector to debug the server. 

```bash
npx @modelcontextprotocol/inspector \
  uv \
  --directory . \
  run mcp-server-appwrite
```

Make sure your `.env` file is properly configured before running the inspector. You can then access the inspector at `http://localhost:5173`.

## License

This MCP server is licensed under the MIT License. This means you are free to use, modify, and distribute the software, subject to the terms and conditions of the MIT License. For more details, please see the LICENSE file in the project repository.

## Todos
- Add MCP server to registries
  - Glama
  - https://github.com/chatmcp/mcp-directory
  - https://mcp.so/
  - https://github.com/punkpeye/awesome-mcp-servers
  - https://portkey.ai/mcp-servers
  - https://www.claudemcp.com/servers
- Add support for SSE server
