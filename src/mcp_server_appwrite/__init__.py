import asyncio
import sys


def main():
    """Main entry point for the package."""
    from .server import _run

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        print("[appwrite-mcp] Shutdown requested", file=sys.stderr, flush=True)
        return 0


__all__ = ["main"]
