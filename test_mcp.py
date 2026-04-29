import asyncio

from langchain_mcp_adapters.client import MultiServerMCPClient
from settings import get_settings


async def main():
    settings = get_settings()

    client = MultiServerMCPClient(
        {
            "analytics": {
                "url": settings.mcp_server_url,
                "transport": "streamable_http",
            }
        }
    )

    tools = await client.get_tools()

    print("Loaded tools:")
    for tool in tools:
        print("-", tool.name)


if __name__ == "__main__":
    asyncio.run(main())