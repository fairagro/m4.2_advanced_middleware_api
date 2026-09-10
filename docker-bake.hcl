# Product-local Buildx Bake file (NOT synced). Target name must match
# reusable-build `components` matrix entry ("api").
#
# Version pins: do NOT default PYTHON_VERSION / UV_VERSION / PIP_VERSION /
# ALPINE_* / PYINSTALLER_VERSION here — inject from versions.env (reusable-build
# and scripts/run-container-structure-test.sh do this).

variable "APP_VERSION" {
  default = "0.0.0"
}

variable "PYTHON_VERSION" {}
variable "ALPINE_VERSION" {}
variable "ALPINE_MINOR" {}
variable "PIP_VERSION" {}
variable "UV_VERSION" {}
variable "PYINSTALLER_VERSION" {}

variable "IMAGE_TAG" {
  default = "middleware-api:test"
}

target "api-wheels" {
  context    = "."
  dockerfile = "docker/Dockerfile.product-app.base"
  target     = "package-builder"
  args = {
    APP_VERSION       = APP_VERSION
    PYTHON_VERSION    = PYTHON_VERSION
    ALPINE_MINOR      = ALPINE_MINOR
    PIP_VERSION       = PIP_VERSION
    UV_VERSION        = UV_VERSION
    UV_BUILD_PACKAGES = "fairagro-middleware-shared api"
  }
}

target "api-base" {
  context    = "."
  dockerfile = "docker/Dockerfile.product-app.base"
  target     = "export-binaries"
  args = {
    APP_VERSION            = APP_VERSION
    PYTHON_VERSION         = PYTHON_VERSION
    ALPINE_MINOR           = ALPINE_MINOR
    PIP_VERSION            = PIP_VERSION
    UV_VERSION             = UV_VERSION
    PYINSTALLER_VERSION    = PYINSTALLER_VERSION
    UV_BUILD_PACKAGES      = "fairagro-middleware-shared api"
    BINARY_NAME            = "middleware-api"
    PYINSTALLER_IMPORT     = "middleware.api"
    EXTRA_PYINSTALLER_ARGS = "--hidden-import middleware.api.worker --hidden-import middleware.api.worker.celery_app --hidden-import middleware.api.worker.worker --hidden-import celery.app.amqp --hidden-import celery.app.control --hidden-import celery.app.events --hidden-import celery.app.log --hidden-import celery.apps.worker --hidden-import celery.concurrency.prefork --hidden-import celery.events.state --hidden-import celery.fixups --hidden-import celery.fixups.django --hidden-import celery.loaders.app --hidden-import celery.worker.autoscale --hidden-import celery.worker.components --hidden-import celery.worker.consumer --hidden-import celery.worker.consumer.delayed_delivery --hidden-import celery.worker.strategy --hidden-import kombu.transport.pyamqp --copy-metadata celery --copy-metadata opentelemetry-api --copy-metadata opentelemetry-instrumentation --copy-metadata opentelemetry-instrumentation-fastapi --copy-metadata opentelemetry-instrumentation-celery --copy-metadata opentelemetry-instrumentation-requests --copy-metadata opentelemetry-sdk --copy-metadata requests --copy-metadata pydantic --copy-metadata pydantic-core --copy-metadata fastapi --copy-metadata uvicorn --copy-metadata prompt-toolkit --copy-metadata click --copy-metadata api --collect-data middleware.api.arc_store.consolidated_git"
  }
}

target "api" {
  context    = "."
  dockerfile = "docker/Dockerfile.api"
  contexts = {
    export_bins = "target:api-base"
  }
  args = {
    ALPINE_VERSION  = ALPINE_VERSION
    BINARY_NAME     = "middleware-api"
    RUNTIME_USER    = "middleware"
    RUNTIME_WORKDIR = "/api"
  }
  tags      = [IMAGE_TAG]
  platforms = ["linux/amd64"]
}
