from __future__ import annotations

from http.server import ThreadingHTTPServer

from config import HOST, PORT
from database import init_db
from handler import Handler


def main() -> None:
    init_db()
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Python backend is running at http://{HOST}:{PORT}/api")
    print("Admin login: admin@404.local / admin404")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
