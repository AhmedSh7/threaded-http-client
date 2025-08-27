# main.py
import argparse
import socket
import threading
import time
from typing import Tuple

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Safe threaded HTTP client for localhost testing."
    )
    p.add_argument("--target", default="127.0.0.1", help="Host to connect to")
    p.add_argument("--port", type=int, default=8000, help="TCP port of the server")
    p.add_argument("--threads", type=int, default=10, help="Number of client threads")
    p.add_argument("--duration", type=float, default=5.0,
                   help="Run time in seconds (use 0 to run until Ctrl+C)")
    p.add_argument("--sleep", type=float, default=0.003,
                   help="Delay between requests inside a thread (seconds)")
    return p.parse_args()

def make_request(host: str, port: int) -> None:
    # One GET request, read a bit of response so the server can reply cleanly.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((host, port))
        req = (
            "GET / HTTP/1.1\r\n"
            f"Host: {host}\r\n"
            "Connection: close\r\n\r\n"
        )
        s.sendall(req.encode("ascii"))
        try:
            s.recv(1024)
        except Exception:
            pass

def worker(host_port: Tuple[str, int], stop_event: threading.Event,
           counter: list, lock: threading.Lock, sleep_s: float):
    host, port = host_port
    while not stop_event.is_set():
        try:
            make_request(host, port)
            with lock:
                counter[0] += 1
                if counter[0] % 500 == 0:
                    print(counter[0])
        except Exception:
            # Server busy / closed / etc.don’t crash; back off a bit.
            time.sleep(0.02)
        time.sleep(sleep_s)

def main():
    args = parse_args()

    if args.port < 1 or args.port > 65535:
        raise SystemExit("Port must be 1–65535")
    if args.threads < 1:
        raise SystemExit("--threads must be >= 1")

    stop_event = threading.Event()
    counter = [0]        # using list so it's mutable by reference
    lock = threading.Lock()

    threads = [
        threading.Thread(
            target=worker,
            args=((args.target, args.port), stop_event, counter, lock, args.sleep),
            daemon=True
        )
        for _ in range(args.threads)
    ]

    start = time.time()
    for t in threads: t.start()

    try:
        if args.duration > 0:
            # Timed run
            time.sleep(args.duration)
        else:
            # Run until Ctrl+C
            while True:
                time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        stop_event.set()
        for t in threads: t.join(timeout=1.0)

    elapsed = max(time.time() - start, 1e-6)
    total = counter[0]
    rps = total / elapsed
    print(f"\nDone. Successful requests: {total}")
    print(f"Elapsed: {elapsed:.2f}s | Approx. {rps:.1f} req/s "
          f"| Threads: {args.threads} | Target: {args.target}:{args.port}")

if __name__ == "__main__":
    main()
