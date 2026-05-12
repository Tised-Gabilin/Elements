# Google Play Release Pipe

This folder contains an automated pipeline to manage Google Play Store listing metadata (title, short description, full description, promo video) via the Google Play Developer API. The metadata is stored in markdown files per locale and pushed through an API-driven edit.

## Why this exists
- No manual entry of app name/description/translations
- Versioned metadata in Git
- Repeatable, auditable releases

## Prerequisites
- Google Play Console project with API access enabled
- Service account with access to your app in Play Console
- The Android package name (applicationId), e.g. `com.company.app`

## Folder layout
```
GooglePlay Release Pipe/
  credentials/
    service-account.json
  metadata/
    en-US/
      title.md
      short_description.md
      full_description.md
      video.md
    de-DE/
      ...
  scripts/
    upload_play_listing.py
  requirements.txt
```

## Configure service account
1. Create a service account in Google Cloud and download a JSON key.
2. In Play Console, go to Setup > API access, link the Google Cloud project, then grant the service account access to your app.
3. Store the JSON key in a CI secret named `GOOGLE_PLAY_SERVICE_ACCOUNT_JSON`.

## Local credentials file
If you want to run locally without a CI secret, paste the service account JSON into:

```
GooglePlay Release Pipe/credentials/service-account.json
```

Then run:
```bash
python "GooglePlay Release Pipe/scripts/upload_play_listing.py" \
  --package-name com.company.app \
  --metadata-dir "GooglePlay Release Pipe/metadata" \
  --service-account-json "GooglePlay Release Pipe/credentials/service-account.json"
```

## Run locally
```bash
python -m pip install -r "GooglePlay Release Pipe/requirements.txt"
python "GooglePlay Release Pipe/scripts/upload_play_listing.py" \
  --package-name com.company.app \
  --metadata-dir "GooglePlay Release Pipe/metadata"
```

## CI usage (GitHub Actions)
The workflow file in `.github/workflows/googleplay_release.yml` pushes listing metadata.

Required secrets:
- `GOOGLE_PLAY_SERVICE_ACCOUNT_JSON`
- `PACKAGE_NAME` (your Android package name)

## Notes
- The default locale set is a starter list. Adjust as needed in `metadata/`.
- If you need store listings for more locales, add folders with the same file names.
- This pipeline only updates listing metadata. Uploading an AAB/APK can be added later.
