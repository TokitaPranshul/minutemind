#!/usr/bin/env python3
import json
import sys

from ingest.graph import build_graph


def main():
    if len(sys.argv) < 2:
        print("Usage: python run_ingest.py <transcript.json>")
        sys.exit(1)
    with open(sys.argv[1]) as f:
        data = json.load(f)
    graph = build_graph()
    result = graph.invoke({"raw_input": data, "halt": False})
    if result.get("halt"):
        print(f"HALTED: {result.get('halt_reason')}")
    else:
        print(f"Ingestion complete: {result.get('indexed_counts')}")


if __name__ == "__main__":
    main()
