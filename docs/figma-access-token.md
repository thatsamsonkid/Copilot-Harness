# Create a Figma personal access token

The coboose talks to Figma with a **personal access token** in the `X-Figma-Token` header. Copilot never sees the token.

Store the token in the **OS keychain** (macOS Keychain or Windows Credential Manager). The CLI reads it in-process when it talks to Figma.

This is optional. Teams that do not use Figma can leave it unset.

## 1. Create the token

1. Sign in to [Figma](https://www.figma.com/).
2. Open [account settings](https://www.figma.com/settings) → **Security**.
3. Under **Personal access tokens**, click **Generate new token**.
4. Name it something obvious, for example `coboose`.
5. Set an expiry.
6. Grant the least privilege you need:
   - **Images profile (default):** File content read (`file_content:read`). Enough for `figma images` and `/figma-frame`.
   - **Whoami:** Current user profile read (`current_user:read`) if your org requires it for `GET /v1/me`.
7. Click **Generate token**, then **Copy**. You cannot view the value again.

If your company uses SSO, you can still create a token for your own Figma account. This coboose is meant for personal tokens, not a shared bot.

## 2. Store the token in the OS keychain

Preferred: run this in **your own terminal** (not Copilot Chat). Input is hidden.

```bash
uv run coboose figma login
```

If the token is already in `.env`, move it:

```bash
uv run coboose figma login --from-env
```

That writes the token to the OS store, then blanks `FIGMA_ACCESS_TOKEN` in `.env`.

| OS | Store | How the CLI finds it |
| --- | --- | --- |
| macOS | Keychain | service `coboose`, account `figma-access-token` |
| Windows | Credential Manager | generic credential `coboose` / `figma-access-token` |
| Linux desktop | Secret Service (GNOME Keyring / KWallet) | same service and account |
| Headless / CI | `.env` fallback | `FIGMA_ACCESS_TOKEN=...` |

This name is a row in `catalog/env.yaml`. `uv run coboose env list` shows whether it is present without printing the value.

## 3. Confirm it works

```bash
uv run coboose figma whoami
uv run coboose doctor --ping-figma
```

`whoami` must never include the token. If it ever does, revoke the token and treat it as a leak.

## Rotate or remove

Tokens expire. When `doctor --ping-figma` or `figma whoami` returns 401/403:

1. Revoke the old token in Figma settings.
2. Create a new one.
3. Run `uv run coboose figma login` again (or `figma login --from-env` if you temporarily put the new value in `.env`).

```bash
uv run coboose figma logout
```

Do not:

- Commit `.env` with a filled `FIGMA_ACCESS_TOKEN`
- Paste the token into Copilot Chat
- Put the token in a screenshot or PR description
- Curl `api.figma.com` from chat

`.env` remains a fallback when no OS store is available. The CLI still prefers an environment variable if one is set, so blank `FIGMA_ACCESS_TOKEN` after a successful `figma login`.
