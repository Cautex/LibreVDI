# downloads/

Installers and packages placed here are offered by LibreVDI (copied when `broker-web` starts):

| File | Offered as | Who sees it |
|---|---|---|
| `LibreVDI-Client-Setup-*.exe` | portal button *Launcher* (`/uds/page/launcher-download`) | all users |
| `LibreVDI-Agent-unmanaged-Setup-*.exe` | admin UI downloads (persistent machines) | administrators |
| `LibreVDI-Agent-managed-Setup-*.exe` | admin UI downloads (floating pools) | administrators |
| `librevdi-client_*_amd64-<distro>.deb` | portal *Launcher* page, section Linux (Debian 12, Debian 13, Ubuntu 24.04) | all users |
| `librevdi-agent-unmanaged_*_amd64-<distro>.deb` | admin UI downloads (persistent Linux desktops) | administrators |
| `librevdi-agent_*_amd64-<distro>.deb` | admin UI downloads (cloned Linux desktops) | administrators |

Fetch the latest CI builds directly on the Docker host:

```bash
GITHUB_TOKEN=<token> tools/fetch-windows-builds.sh
docker compose restart broker-web
```

Only the newest version of each file is offered. The installers are not secret (open source, no credentials inside); the agent is only
listed for administrators. Files here are ignored by git.
