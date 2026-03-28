from app.window import GLFWWindow


def main() -> None:
    window = GLFWWindow(live_mode=True)
    window.run()


if __name__ == "__main__":
    main()