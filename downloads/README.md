# downloads/

Windows installers placed here are offered by LibreVDI (copied when `broker-web` starts):

| File | Offered as | Who sees it |
|---|---|---|
| `LibreVDI-Client-Setup-*.exe` | portal button *Launcher* (`/uds/page/launcher-download`) | all users |
| `LibreVDI-Agent-unmanaged-Setup-*.exe` | admin UI downloads (persistent machines) | administrators |
| `LibreVDI-Agent-managed-Setup-*.exe` | admin UI downloads (floating pools) | administrators |

Fetch the latest CI builds directly on the Docker host:

```bash
GITHUB_TOKEN=<token> tools/fetch-windows-builds.sh
docker compose restart broker-web
```

The installers are not secret (open source, no credentials inside); the agent is only
listed for administrators. Files here are ignored by git.
