"""ASGI entrypoint: MODEL_KIND selects which artifact to serve."""

from asiwdp_ml.serving.app import create_app

app = create_app()
