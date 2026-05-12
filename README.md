# Mistral App Template

This folder is the reusable starting point for all Mistral app projects.

## What This Template Contains

- `config.json`: GitHub organization and metadata configuration.
- `GooglePlay Release Pipe/`: automation assets for Google Play listing updates.
- `Requirements/`: project requirement templates and technical design patterns used by agents.
- `Requirements/app_icon/`: placeholder folder for app icon source assets.

## Initialization Workflow

1. Run `init.py` with destination folder and project name.
2. The script copies this template into `<destination>/<project_name>`.
3. Optionally pass an initial research markdown file.
4. If provided, the file is copied into the generated project as `Requirements/Initial Research.md`.

## Configuration

All derived apps are configured to push to the **Tised-Gabilin** GitHub organization:

- Organization URL: https://github.com/orgs/Tised-Gabilin/repositories
- Configuration details are stored in `config.json`
- Each derived app inherits this configuration automatically during initialization

## Agent Notes

- `config.json` provides GitHub organization and project metadata.
- `Requirements/Purchase.md` is a permanent technical implementation template.
- `Requirements/app_icon/` is created for every initialized app and should hold icon working files.
- `Requirements/Initial Research.md` is app-specific input and can be added later by the operator if omitted during initialization.