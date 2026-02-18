from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
if __name__ == "__main__":
    print(PROJECT_ROOT)
