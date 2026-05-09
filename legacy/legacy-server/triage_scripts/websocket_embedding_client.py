#!/usr/bin/env python3
"""
Test script for the embedding regeneration WebSocket endpoint.
"""

import asyncio
import json
import websockets
from websockets.exceptions import ConnectionClosed
import argparse


async def test_embedding_regeneration(uri: str, force: bool = False):
    """Test the embedding regeneration WebSocket endpoint."""
    print(f"Connecting to {uri}...")

    try:
        async with websockets.connect(uri) as websocket:
            print("✓ WebSocket connected!")

            # Listen for messages
            async for message in websocket:
                try:
                    data = json.loads(message)
                    msg_type = data.get("type")

                    if msg_type == "connected":
                        print(f"✓ Connection confirmed: {data.get('message')}")
                        print(f"  Force regenerate: {data.get('force_regenerate')}")

                    elif msg_type == "started":
                        print(f"🚀 Started: {data.get('message')}")
                        print(f"   Start time: {data.get('start_time')}")

                    elif msg_type == "progress":
                        progress = data.get("progress", {})
                        percentage = progress.get("completion_percentage", 0)
                        current_node = progress.get("current_node_title", "")
                        node_type = progress.get("current_node_type", "")
                        completed = progress.get("completed_nodes", 0)
                        total = progress.get("total_nodes", 0)
                        eta = progress.get("estimated_remaining_seconds", 0)
                        rate = progress.get("processing_rate_per_second", 0)
                        errors = progress.get("error_count", 0)

                        print(f"📊 Progress: {percentage:.1f}% ({completed}/{total})")
                        print(f"   Current: {node_type} - {current_node}")
                        print(
                            f"   Rate: {rate:.2f}/sec, ETA: {eta:.0f}s, Errors: {errors}"
                        )

                    elif msg_type == "completed":
                        print(f"✅ Completed: {data.get('message')}")
                        print(f"   Total processed: {data.get('total_processed', 0)}")
                        print(f"   Duration: {data.get('duration_seconds', 0):.2f}s")
                        break

                    elif msg_type == "error":
                        print(f"❌ Error: {data.get('message')}")
                        break

                    else:
                        print(f"📝 Unknown message type: {msg_type}")
                        print(f"   Data: {json.dumps(data, indent=2)}")

                except json.JSONDecodeError:
                    if isinstance(message, bytes):
                        message = message.decode("utf-8", errors="replace")
                    print(f"⚠️  Invalid JSON received: {message}")

    except ConnectionClosed:
        print("🔌 WebSocket connection closed")
    except Exception as e:
        print(f"❌ Error: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Test embedding regeneration WebSocket"
    )
    parser.add_argument(
        "--host", default="localhost", help="Server host (default: localhost)"
    )
    parser.add_argument(
        "--port", type=int, default=8000, help="Server port (default: 8000)"
    )
    parser.add_argument(
        "--force", action="store_true", help="Force regeneration of all embeddings"
    )

    args = parser.parse_args()

    force_param = "true" if args.force else "false"
    uri = f"ws://{args.host}:{args.port}/api/embeddings/regenerate?force={force_param}"

    print("🧪 Testing Embedding Regeneration WebSocket")
    print(f"   URI: {uri}")
    print(f"   Force regenerate: {args.force}")
    print()

    asyncio.run(test_embedding_regeneration(uri, args.force))


if __name__ == "__main__":
    main()
