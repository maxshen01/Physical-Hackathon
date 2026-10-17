"""Run the HTTP adapter independently of any client application."""
import argparse
import uvicorn


def main():
    parser = argparse.ArgumentParser(description="Run the exercise classifier API")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8443)
    parser.add_argument("--ssl-certfile")
    parser.add_argument("--ssl-keyfile")
    args = parser.parse_args()
    uvicorn.run("kinevoa_classifier.api:app", **vars(args))


if __name__ == "__main__":
    main()
