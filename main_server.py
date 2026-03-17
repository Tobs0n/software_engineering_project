"""
Run this once on the machine that will host the lobby.
All clients connect to this IP.

    python main_server.py
    python main_server.py --host 0.0.0.0 --port 5555
"""
import sys
import argparse

from src.network.server import Server


def main():
    parser = argparse.ArgumentParser(description="MiniParty Game Server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=5555)
    args = parser.parse_args()

    server = Server(host=args.host, port=args.port)
    print(f"[Server] Starting on {args.host}:{args.port} …  Ctrl-C to stop.")
    try:
        server.start()
    except KeyboardInterrupt:
        print("\n[Server] Shutting down.")
        server.stop()
        sys.exit(0)


if __name__ == "__main__":
    main()
