# Python-related technical information on this project

This project uses [`uv`](https://docs.astral.sh/uv/) for depedency management
and [`uvicorn`](https://www.uvicorn.org/) as minial API server.

This is a small how to for the case that you've never used these tools before
(just like me).

## The `uv` workflow

It's worth to note here, that `uv` distinguishes between "primary" dependencies
and dependencies of dependencies. "Primary" dependencies are those that you
actual intend to use in your own code and that you install on purpose.
The dependencies of these "primary" dependencies are then installed
automatically.

"Primary" dependencies are managed in the file `pyproject.toml`, whereas
depedencies of dependencies are managed in the file `uv.lock`.

### First steps after cloning the project

Create a python virtual environment and activate it:

```bash
uv venv
. .venv/bin/activate
```

Install all dependencies (from `uv.lock`):

```bash
uv sync
```

### Modify dependencies

Add/Delete a primary dependecy:

```bash
uv add <package name>
uv delete <package name>
```

Update the `uv.lock` file:

```bash
uv lock
```

You can also upgrade the locked dependencies to the newest version
that match those in `pyproject.toml`:

```bash
uv lock --upgrade
```

If you just would like to install an arbitary python package that should
not be part of the project dependencies:

```bash
uv pip install <package name>
```