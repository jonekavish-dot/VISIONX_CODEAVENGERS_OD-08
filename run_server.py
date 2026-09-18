"""
IVACS V-TRACE Server Runner
Convenient entrypoint to run the FastAPI server directly via Python:
    python run_server.py [--port 8000] [--host 0.0.0.0]
"""

import sys
import socket
import argparse
import uvicorn


def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    """Check if a TCP port is already in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((host, port)) == 0


def find_available_port(start_port: int = 8000, max_attempts: int = 10) -> int:
    """Find the next available port starting from start_port."""
    for p in range(start_port, start_port + max_attempts):
        if not is_port_in_use(p):
            return p
    return start_port


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Start IVACS V-TRACE Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host IP (default: 0.0.0.0)")
    parser.add_argument("--port", "-p", type=int, default=8000, help="Port (default: 8000)")
    parser.add_argument("--auto-port", action="store_true", help="Automatically select an open port if specified port is busy")
    args = parser.parse_args()

    target_port = args.port

    if is_port_in_use(target_port):
        alt_port = find_available_port(target_port + 1)
        if args.auto_port:
            print(f"[NOTICE] Port {target_port} is busy. Automatically switching to open port {alt_port}...")
            target_port = alt_port
        else:
            print(f"[WARNING] Port {target_port} is already occupied by another process.")
            print(f"[HINT] You can free port {target_port}, pass a different port (`python run_server.py -p {alt_port}`),")
            print(f"       or use `--auto-port` (`python run_server.py --auto-port`).")

    print(f"\n=======================================================")
    print(f"  IVACS V-TRACE: Vehicle Trust, Route & Evidence Engine")
    print(f"=======================================================")
    print(f"  * Web Dashboard:      http://localhost:{target_port}/")
    print(f"  * API Documentation:  http://localhost:{target_port}/docs")
    print(f"  * Bind Address:       http://{args.host}:{target_port}")
    print(f"=======================================================\n")

    uvicorn.run("backend.app:app", host=args.host, port=target_port, reload=False)
