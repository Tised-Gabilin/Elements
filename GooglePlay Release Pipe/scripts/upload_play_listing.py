import json
import os
from pathlib import Path

from google.oauth2 import service_account
from googleapiclient.errors import HttpError
from googleapiclient.discovery import build

SCOPE = "https://www.googleapis.com/auth/androidpublisher"


def load_credentials(json_path: str | None) -> service_account.Credentials:
    if json_path:
        with open(json_path, "r", encoding="utf-8") as f:
            info = json.load(f)
    else:
        raw = os.environ.get("GOOGLE_PLAY_SERVICE_ACCOUNT_JSON")
        if not raw:
            raise RuntimeError(
                "Missing credentials. Set GOOGLE_PLAY_SERVICE_ACCOUNT_JSON or use --service-account-json."
            )
        info = json.loads(raw)

    return service_account.Credentials.from_service_account_info(info, scopes=[SCOPE])


def read_text(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")
    return path.read_text(encoding="utf-8").strip()


def load_listing(locale_dir: Path) -> dict:
    title = read_text(locale_dir / "title.md")
    short_description = read_text(locale_dir / "short_description.md")
    full_description = read_text(locale_dir / "full_description.md")
    video = locale_dir / "video.md"
    video_url = read_text(video) if video.exists() else ""

    return {
        "title": title.replace("\n", " ").strip(),
        "shortDescription": short_description.replace("\n", " ").strip(),
        "fullDescription": full_description.strip(),
        "video": video_url.strip() or None,
    }


def build_service(creds: service_account.Credentials):
    return build("androidpublisher", "v3", credentials=creds, cache_discovery=False)


def update_listings(service, package_name: str, metadata_dir: Path) -> None:
    edit = service.edits().insert(packageName=package_name, body={}).execute()
    edit_id = edit["id"]

    for locale_dir in sorted(p for p in metadata_dir.iterdir() if p.is_dir()):
        language = locale_dir.name
        listing = load_listing(locale_dir)

        # Optional field: remove if not provided.
        if not listing["video"]:
            listing.pop("video")

        service.edits().listings().update(
            packageName=package_name,
            editId=edit_id,
            language=language,
            body=listing,
        ).execute()

    try:
        service.edits().commit(
            packageName=package_name,
            editId=edit_id,
            changesNotSentForReview=True,
        ).execute()
    except HttpError as error:
        if "changesNotSentForReview must not be set" not in str(error):
            raise

        service.edits().commit(packageName=package_name, editId=edit_id).execute()


def main() -> None:
    package_name = os.environ.get("PACKAGE_NAME", "").strip()
    if not package_name:
        raise SystemExit(
            "PACKAGE_NAME is not set.\n"
            "Set it before running:\n"
            "  PACKAGE_NAME=com.yourcompany.sixthsense python scripts/upload_play_listing.py"
        )

    # Get script directory and resolve paths relative to it
    script_dir = Path(__file__).parent.resolve()
    metadata_dir = script_dir.parent / "metadata"
    service_account_json = script_dir.parent / "credentials" / "service-account.json"

    if not metadata_dir.exists():
        raise SystemExit(f"Metadata directory not found: {metadata_dir}")

    if not service_account_json.exists():
        raise SystemExit(f"Service account JSON not found: {service_account_json}")

    creds = load_credentials(str(service_account_json))
    service = build_service(creds)
    update_listings(service, package_name, metadata_dir)


if __name__ == "__main__":
    main()
