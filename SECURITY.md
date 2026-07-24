# Security Policy

## Reporting

Please report security issues privately through the repository owner's preferred
GitHub security contact. Do not open a public issue containing credentials,
private team data, exploit details, or production URLs.

## Supported Version

The public repository supports the latest `main` branch unless a release note
states otherwise.

## Credential Rules

- Never commit `.env`, database files, backups, packaged archives, or real exports.
- Generate a unique `SECRET_KEY` for every deployment.
- Store SMTP, WeChat mini-program, and tunnel credentials only in runtime
  environment variables or untracked `.env` files.
- Rotate any credential that has appeared in Git history, even if it was later
  removed.

## Demo Data

The demo seed uses fictional accounts and `example.invalid` emails. Replace demo
accounts before exposing an instance to real users.
