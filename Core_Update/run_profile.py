from .profiling import install, measure
from .run_cli import main

if __name__ == "__main__":
    install()
    with measure("Session entière (saisies incluses)"):
        result = main()
    raise SystemExit(result)
