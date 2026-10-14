from pathlib import Path
import socket
import uvicorn

ROOT = Path(__file__).resolve().parent

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

if __name__ == "__main__":
    ip = get_local_ip()
    print("[BDD] SQLite active -> cogip.db")
    print()
    print("=== Serveur COGIP ===")
    print(f"IP du PC        : {ip}")
    print(f"Swagger         : http://{ip}:8000/docs")
    print(f"Page de pointage: http://{ip}:8000/")
    print(f"API_URL ESP32   : http://{ip}:8000/api/scan")
    print("Ctrl+C pour arrêter")
    print()

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)
