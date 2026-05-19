# Docker Image Guide

The default small-batch path uses a prebuilt `lite` image:

```bash
docker pull ghcr.io/protectskills/claude-skill-sandbox:lite
```

If registry access is unreliable, download the release asset and load it:

```bash
gh release download sandbox-lite-v1 --pattern 'claude-skill-sandbox-lite.tar.gz'
docker load -i claude-skill-sandbox-lite.tar.gz
```

Build locally from the `code/` directory only when customizing the image:

```bash
docker build --build-arg NOVA_MODE=lite -t claude-skill-sandbox -f Dockerfile .
```

The image uses Node.js 22 by default for Claude Code CLI. Override it with
`--build-arg NODE_MAJOR=<major>` if needed.

When using `python3 helper.py build --mode lite`, the helper pulls the prebuilt
image by default. Use `--mode load-tar` to import a downloaded release asset.
Local `none`, `full-cpu`, and `full-custom` builds still save complete Docker
logs under `logs/`; add `--verbose` to stream all output.

## Modes

| Mode | Purpose |
|------|---------|
| `none` | Claude Code sandbox with strace/tcpdump only |
| `lite` | Adds vendored Nova-tracer recording and HTML reports |
| `full` | Docker build argument that adds `nova-hunting` scanner dependencies |

`lite` is the default recommendation for small-batch reproduction. `full` is
only needed when running Nova-tracer keyword/semantic scanning inside the
sandbox. In `helper.py build`, use `full-cpu` for the portable CPU build or
`full-custom` to provide GPU/custom torch arguments.

Helper build modes map to Docker build arguments as follows:

| Helper mode | Docker build args |
|-------------|-------------------|
| `none` | `NOVA_MODE=none` |
| `lite` | `NOVA_MODE=lite` |
| `full-cpu` | `NOVA_MODE=full` with default CPU torch |
| `full-custom` | `NOVA_MODE=full` with custom torch args |

## Full Mode Torch Selection

CPU torch is the default for portability:

```bash
docker build \
  --build-arg NOVA_MODE=full \
  --build-arg NOVA_TORCH_SPEC='torch>=2.5,<3' \
  --build-arg NOVA_TORCH_INDEX_URL='https://download.pytorch.org/whl/cpu' \
  -t claude-skill-sandbox:full .
```

For GPU or custom environments, override the torch build args:

```bash
docker build \
  --build-arg NOVA_MODE=full \
  --build-arg NOVA_TORCH_INDEX_URL= \
  --build-arg NOVA_TORCH_SPEC='torch>=2.5,<3' \
  -t claude-skill-sandbox:full-gpu .
```

## Verify

```bash
docker run --rm claude-skill-sandbox \
  sh -c 'cat /opt/nova-tracer/nova_mode 2>/dev/null || echo none'
```
