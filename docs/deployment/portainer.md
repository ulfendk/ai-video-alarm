# Deploying alarm-core with Portainer + GHCR

This covers running `alarm-core` as a Portainer stack on a Docker host,
pulling the prebuilt image from GHCR instead of building from source.
It does **not** cover `addon/` — that's a Home Assistant Supervisor
add-on, installed through HA's add-on store mechanism, not Portainer.

## 1. Get an image published to GHCR

`.github/workflows/docker-publish.yml` builds and pushes
`ghcr.io/ulfendk/ai-video-alarm-core` automatically:

- **Push to `main`** → tagged `latest` + the short commit sha.
- **Tag `vX.Y.Z`** → also tagged with that version.
- **Manual run** (GitHub → Actions → "Build and publish alarm-core image"
  → Run workflow, any branch) → tagged with the branch name + short sha.
  Use this if you want to try a change on your server before merging —
  it never touches the `latest` tag, so it won't affect a stable stack.

## 2. Make the package pullable from your server

New GHCR packages are private by default. Pick one:

- **Simplest: make it public.** On GitHub → your profile → Packages →
  `ai-video-alarm-core` → Package settings → Change visibility → Public.
  Portainer then needs no credentials at all.
- **Keep it private**, and add a registry credential in Portainer:
  Portainer → Registries → Add registry → Custom registry — URL
  `ghcr.io`, username = your GitHub username, password = a GitHub
  [personal access token](https://github.com/settings/tokens) with the
  `read:packages` scope.

## 3. Prepare host directories

The compose file mounts config/archive/db from the host. Pick real,
persistent paths on the server (not the Portainer-managed stack
directory, which you don't want to lose data in on a stack redeploy) —
for example:

```
sudo mkdir -p /srv/ai-video-alarm/{config,archive,db}
```

Copy `config/alarm-core.example.yaml` from this repo to
`/srv/ai-video-alarm/config/alarm-core.yaml` on the server and fill in
your real camera/zone names, door/window `entity_id`s, etc. — see
[`docs/clarifying-questions.md`](../clarifying-questions.md).

## 4. Create the stack in Portainer

**Stacks → Add stack**, then either:

- **Repository** (recommended — lets you use "Pull and redeploy" for
  updates): Repository URL `https://github.com/ulfendk/ai-video-alarm`,
  reference `refs/heads/main`, Compose path `docker-compose.yml`.
- **Web editor**: paste the contents of this repo's `docker-compose.yml`
  directly. `docker-compose.override.yml` is a local-dev-only file and
  is irrelevant here either way — Portainer only looks at the one
  compose path you give it.

Then, in the stack's **Environment variables**, set at minimum:

| Variable | Value |
|---|---|
| `FRIGATE_URL` | e.g. `http://192.168.1.20:5000` |
| `MQTT_HOST` / `MQTT_PORT` | your existing Mosquitto broker |
| `MQTT_USERNAME` / `MQTT_PASSWORD` | if your broker requires auth |
| `ANTHROPIC_API_KEY` | for Tier-2 cloud vision escalation |
| `HA_STATESTREAM_BASE_TOPIC` | usually the default `homeassistant` is fine |
| `CONFIG_HOST_PATH` | `/srv/ai-video-alarm/config/alarm-core.yaml` |
| `ARCHIVE_HOST_PATH` | `/srv/ai-video-alarm/archive` |
| `DB_HOST_PATH` | `/srv/ai-video-alarm/db` |

Leave `IMAGE_TAG` unset for `latest`, or pin it to a specific short-sha
tag from the Actions run / GHCR package page for a stable rollout you
control the timing of. See `.env.example` in the repo for the full list
with descriptions — Portainer's "Advanced mode" lets you paste a whole
`.env`-formatted block instead of adding variables one at a time.

Click **Deploy the stack**.

## 5. Verify

- The container should show **healthy** in Portainer's container list
  within ~30s (the image has a built-in `/health` healthcheck).
- Check the container logs for an MQTT connect message.
- From another machine on the network:
  `curl http://<server>:8090/health` → `{"status":"ok"}`.

## 6. Updating

- After a new image is published (merge to `main`, or a manual dispatch
  run), open the stack in Portainer and use **Pull and redeploy** — this
  re-pulls whatever `IMAGE_TAG` currently resolves to (`latest` by
  default).
- If you pinned `IMAGE_TAG` to a specific sha for stability, bump it to
  the new tag and redeploy explicitly instead — this is the safer path
  once you're relying on this for real alerting, since `latest` can pick
  up a build you haven't reviewed yet.

## GPU passthrough

`docker-compose.yml` has the NVIDIA GPU reservation block commented out.
To enable it on your i7+NVIDIA host: install the
[NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)
on the Docker host, then either edit the compose file (Web editor method)
to uncomment the `deploy.resources.reservations.devices` block, or use
Portainer's own GPU configuration UI if your Portainer/Docker Engine
version exposes one under the stack's advanced settings.
