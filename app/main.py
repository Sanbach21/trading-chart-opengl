import sys
from app.window import GLFWWindow


def main() -> None:
    live_mode = "--live" in sys.argv or "-l" in sys.argv

    print(f"[INFO] Iniciando en modo {'LIVE' if live_mode else 'DEMO'}")

    window = GLFWWindow(
        live_mode=live_mode,
        live_symbol="BTCUSDT",
        live_interval="1m",
        history_limit=800,      # puedes subir a 1000
    )
    window.run()


if __name__ == "__main__":
    main()