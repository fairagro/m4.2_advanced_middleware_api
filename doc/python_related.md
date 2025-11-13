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
dependencies of dependencies are managed in the file `uv.lock`.

### First steps after cloning the project

Create a python virtual environment and activate it:

```bash
uv venv
. .venv/bin/activate
```

Install all standard dependencies (from `uv.lock`):

```bash
uv sync
```

Install also development dependencies:

```bash
uv sync --dev
```

### Modify dependencies

Add/Delete a primary dependency:

```bash
uv add <package name>
uv delete <package name>
```

By passing `--dev` you do not modify the standard dependencies, but
development dependencies.

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

## Testing the FAIRagro middleware API

There's are bunch of possibilities to run the FAIRagro middleware service in
a test environment. Note that we assume in all cases that the current working
directory is the project base directory (i.e. the one that has been created
by `git clone`).

The middleware will listen on `http://0.0.0.0:8000` by default. You can
change this by passing the command line args `--host` and/or `--port`.
You will be able to access a swagger API browser by appending `/docs` to the
URL.

### Configuring the middleware API

The middleware API needs a config file that is looked for in
`/run/secrets/middleware-api-config` by default. This is not a very practical
path for test runs, though. To override it, please do something like:

```bash
export MIDDLEWARE_API_CONFIG=example_config.yaml
```

Having a look at the file `example_config.yaml` you will notice that the gitlab
API token is missing, as we do not want to commit a secret to git. Nevertheless
the token is needed, otherwise the middleware API won't start. So you can either
define the variable `GITLAB_API_TOKEN` manually, or reuse the the token used for
integration tests that should have already been decrypted by the script `load-env.sh`:

```bash
source .env
```

### Running by executing `main.py`

We can start the middleware api by executing the python main file:

```bash
PYTHONPATH=. python middleware_api/main.py
```

The `PYTHONPATH` needs to be set, so `main.py` can find the `middleware_api`
module.

### Running the `middleware_api.main` module

We can also execute the `middleware_api.main` module:

```bash
python -m middleware_api.main
```

If you do this in the project directory, there is no need to set the
`PYTHONPATH`.

### Running via `uvicorn`

To run the middleware api via `uvicorn` command line tool:

```bash
uvicorn middleware_api.api:app
```

### Running via `fastapi`

To run the middleware api via `fastapi` command line tool:

```bash
fastapi run middleware_api/api.py --app app
```

### Using a local docker image

We can also build an run the docker image:

```bash
docker build . -t middleware_api
docker run \
    -v $(pwd)/example_config.yaml:/run/secrets/middleware-api-config \
    -e GITLAB_API_TOKEN \
    -p 8000:8000 \
    middleware_api
```

### Using the official docker image

To use an official middleware release:

```bash
docker run \
    -v $(pwd)/example_config.yaml:/run/secrets/middleware-api-config \
    -e GITLAB_API_TOKEN \
    -p 8000:8000 \
    zalf/fairagro-advanced-middleware-api:latest
```
