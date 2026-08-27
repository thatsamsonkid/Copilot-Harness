# Install uv

This harness uses [uv](https://docs.astral.sh/uv/) to run the CLI (`uv run harness …`). Do not install the package with pip.

Official installer docs: [docs.astral.sh/uv/getting-started/installation](https://docs.astral.sh/uv/getting-started/installation/).

`/get-started` and `harness init` check whether `uv` is on your PATH and point you here if it is missing.

## macOS

In Terminal:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Or, if you already use Homebrew:

```bash
brew install uv
```

Then open a **new** terminal (so `~/.local/bin` is on PATH) and from this repo:

```bash
./scripts/setup.sh
```

`setup.sh` will install uv itself if the curl installer is acceptable on your machine.

## Windows

In PowerShell:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Or, if you already use WinGet:

```powershell
winget install --id=astral-sh.uv -e
```

Then open a **new** PowerShell window and from this repo:

```powershell
.\scripts\setup.ps1
```

Do not run `./scripts/setup.sh` on Windows. That script is for macOS and Linux.

## Linux

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

If you do not have `curl`:

```bash
wget -qO- https://astral.sh/uv/install.sh | sh
```

Then:

```bash
./scripts/setup.sh
```

## After install

```bash
uv --version
uv run harness init
uv run harness doctor
```

If `uv` is still not found, the installer put the binary in `~/.local/bin` (macOS/Linux) or `%USERPROFILE%\.local\bin` (Windows). Open a new terminal, or add that directory to PATH, then retry.
