"""CDK entry point: ``cdk synth`` / ``cdk deploy -c env_name=dev``.

Build the worker package first (see scripts/build-worker.sh). Nothing is
deployed by tests; deploying creates billable resources.
"""

from pathlib import Path

from aws_cdk import App
from aws_cdk import aws_lambda as lambda_

from freshcast_infra.app_factory import build_app
from freshcast_infra.config import DeployConfig

app = App()
ctx = app.node.try_get_context
worker_dir = Path(__file__).resolve().parents[2] / "dist" / "worker"
if not worker_dir.exists():
    raise SystemExit("dist/worker missing - run scripts/build-worker.sh first")

config = DeployConfig(
    env_name=ctx("env_name") or "dev",
    region=ctx("region") or "eu-central-1",
    alert_email=ctx("alert_email"),
    monthly_budget_usd=float(ctx("monthly_budget_usd") or 50),
)
build_app(config, lambda_.Code.from_asset(str(worker_dir)), app)
app.synth()
