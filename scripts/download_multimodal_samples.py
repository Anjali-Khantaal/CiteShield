import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.multimodal import download_manifest_media, load_multimodal_manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download public multimodal sample files.")
    parser.add_argument("--manifest", default="data/multimodal_manifest.json")
    parser.add_argument("--data-root", default="data")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data_root = (PROJECT_ROOT / args.data_root).resolve()
    manifest_path = (PROJECT_ROOT / args.manifest).resolve()
    items = load_multimodal_manifest(manifest_path, data_root=data_root)
    paths = download_manifest_media(items)
    for path in paths:
        print(f"downloaded={path}")


if __name__ == "__main__":
    main()
