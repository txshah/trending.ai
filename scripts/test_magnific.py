"""Connection test for the Magnific MCP (via npx mcp-remote, browser OAuth).

The first time, it opens the browser (or prints a URL) for the Magnific sign-in.
If it connects, it lists the available tools.
"""

import asyncio

from content_agent.agent import magnific_toolset


async def main():
    print(">> Connecting to Magnific MCP (may open the browser the first time)...")
    tools = await magnific_toolset.get_tools()
    print(f">> OK. {len(tools)} tools available:")
    for t in tools:
        print("   -", t.name)
    await magnific_toolset.close()


if __name__ == "__main__":
    asyncio.run(main())
