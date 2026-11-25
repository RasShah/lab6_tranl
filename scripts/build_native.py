import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lab6.build import BuildError, build_native


if __name__ == "__main__":
    try:
        print(f"Built: {build_native(force=True)}")
    except (BuildError, OSError) as error:
        raise SystemExit(str(error)) from error
