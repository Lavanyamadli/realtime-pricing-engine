"""Real-time pricing engine."""

import asyncio
import sys

# The Windows Proactor loop can hang during shutdown in restricted desktop
# environments. Selector is sufficient because all service I/O is socket/file based.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
