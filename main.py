"""AtomSculptor – CLI entry-point.

Usage:
    python main.py                  # interactive ADK CLI (default)
    python main.py --web            # launch the 4-panel web GUI
    python main.py --web --port 9000
    python main.py --a2a            # expose an A2A server for other agents
    python main.py --a2a --port 8080
"""

import argparse
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="AtomSculptor agent team")
    parser.add_argument("--web", action="store_true", help="Launch the web GUI")
    parser.add_argument("--a2a", action="store_true", help="Launch the A2A server (Agent-to-Agent protocol)")
    parser.add_argument("--host", default="0.0.0.0", help="Server bind address (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="Server port (default: 8000)")
    args = parser.parse_args()

    if args.web:
        from web_gui.server import run_server
        run_server(host=args.host, port=args.port)
    elif args.a2a:
        import uvicorn
        from google.adk.cli.fast_api import get_fast_api_app

        agents_dir = str(Path(__file__).parent)
        app = get_fast_api_app(
            agents_dir=agents_dir,
            web=False,
            a2a=True,
            host=args.host,
            port=args.port,
        )
        print(f"\n  AtomSculptor A2A Server  →  http://{args.host}:{args.port}\n")
        uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    else:
        # Fall through to Google ADK CLI
        try:
            from google.adk.cli import main as adk_main
            sys.argv = [sys.argv[0]]  # strip our flags so ADK CLI doesn't choke
            adk_main()
        except ImportError:
            print("google-adk CLI not available. Use --web for the web GUI.", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
