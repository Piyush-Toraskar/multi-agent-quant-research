import asyncio
import argparse

async def check(implementation):
    from app.config import Settings
    from app.tools.client import ToolGateway
    settings = Settings(agent_mode='demo', tool_transport='mcp', mcp_implementation=implementation)
    async with ToolGateway(settings) as gateway:
        print('Discovered:', ', '.join(gateway.schemas))
        print('SQL history tool:', await gateway.call('search_research', {'query': '', 'limit': 1}))
    print('MCP initialise, discovery, tool call and shutdown completed.')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--implementation', choices=['builtin','sdk'], default='builtin')
    args = parser.parse_args()
    asyncio.run(check(args.implementation))
