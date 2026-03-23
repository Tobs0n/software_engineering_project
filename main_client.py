"""
Run one instance per player.

    python main_client.py
    python main_client.py --host 192.168.1.5 --port 5555
"""
import argparse
from src.app import App


def main():
    parser = argparse.ArgumentParser(description="MiniParty Client")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5555)
    args = parser.parse_args()

    App(args.host, args.port).run()


if __name__ == "__main__":
    main()