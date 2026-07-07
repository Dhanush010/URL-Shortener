"""Seed short codes before a load test."""

import sys

import httpx

HOST = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
COUNT = int(sys.argv[2]) if len(sys.argv) > 2 else 50


def main() -> None:
    codes: list[str] = []
    with httpx.Client(base_url=HOST, timeout=30.0) as client:
        for index in range(COUNT):
            response = client.post(
                "/api/v1/shorten",
                json={"url": f"https://loadtest.example.com/page/{index}"},
            )
            if response.status_code == 201:
                codes.append(response.json()["short_code"])
            elif response.status_code == 429:
                break
        for code in codes[:20]:
            for _ in range(3):
                client.get(f"/{code}", follow_redirects=False)
    print(f"Seeded {len(codes)} codes and warmed cache for 20 of them")


if __name__ == "__main__":
    main()
