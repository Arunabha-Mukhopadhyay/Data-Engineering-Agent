import argparse

import requests

from utils.etl_tools import ETLTools


def main():
    parser = argparse.ArgumentParser(
        description="Extract paginated API results to a local file."
    )
    parser.add_argument("--url", required=True, help="API endpoint URL")
    parser.add_argument(
        "--output-folder",
        default="data/extract",
        help="Output directory, relative to the project root unless absolute",
    )
    parser.add_argument(
        "--format",
        choices=sorted(ETLTools.supported_formats),
        default="csv",
        help="Output format (default: csv)",
    )
    args = parser.parse_args()

    try:
        print(
            ETLTools().extract_load(
                args.url,
                args.output_folder,
                args.format,
            )
        )
    except (requests.exceptions.RequestException, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()