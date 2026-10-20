import uvicorn

from supportdesk.config import get_settings


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        "supportdesk.main:app",
        host="127.0.0.1",
        port=8000,
        log_level=settings.log_level.lower(),
    )


# Go (cmd/supportdesk/main.go):
#   func main() {
#       s := config.MustLoad()
#       log.Fatal(http.ListenAndServe("127.0.0.1:8000", app))
#   }
#
# Two ways to start it, both run this function:
#   uv run supportdesk          <- [project.scripts] in pyproject.toml (like `go install`)
#   uv run python -m supportdesk  <- `-m package` runs package/__main__.py
# The app is passed as an import string so uvicorn can re-import it in new processes
# for --reload and workers.

if __name__ == "__main__":
    main()

# Go: there's no equivalent; Go always starts at main(). In Python a file can be both
# imported (then __name__ == "supportdesk.__main__") and run (then __name__ ==
# "__main__"); this guard makes the call happen only when run.
