import subprocess


def main() -> None:
    cmd = [
        "locust",
        "-f",
        "load_tests/locustfile.py",
        "--host",
        "http://127.0.0.1:8000",
        "--headless",
        "-u",
        "10",
        "-r",
        "2",
        "-t",
        "60s",
    ]
    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    main()
