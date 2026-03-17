import argparse
from pathlib import Path

from pipeline.wrappers.global_registration import run_global_registration


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--moving", required=True)
    parser.add_argument("--fixed", required=True)
    parser.add_argument("--output", default="data/temp/registration")
    args = parser.parse_args()
    result = run_global_registration(
        moving=Path(args.moving),
        fixed=Path(args.fixed),
        output_dir=Path(args.output),
    )
    print(result)


if __name__ == "__main__":
    main()
