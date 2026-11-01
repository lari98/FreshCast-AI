"""Assemble all stacks into one CDK app."""

from __future__ import annotations

from aws_cdk import App, Environment, Tags
from aws_cdk import aws_lambda as lambda_

from freshcast_infra.config import DeployConfig
from freshcast_infra.data_stack import DataStack
from freshcast_infra.database_stack import DatabaseStack
from freshcast_infra.messaging_stack import MessagingStack
from freshcast_infra.mlops_stack import MlopsStack


def build_app(
    config: DeployConfig, worker_code: lambda_.Code, app: App | None = None
) -> App:
    """Create every stack; the account comes from the CLI credentials."""
    app = app or App()
    env = Environment(region=config.region)  # account resolved at deploy time
    data = DataStack(app, f"FreshCast-Data-{config.env_name}", config=config, env=env)
    db = DatabaseStack(
        app, f"FreshCast-Db-{config.env_name}", config=config, key=data.key, env=env
    )
    MessagingStack(
        app,
        f"FreshCast-Messaging-{config.env_name}",
        config=config,
        key=data.key,
        vpc=db.vpc,
        db_secret=db.secret,
        worker_security_group=db.worker_security_group,
        worker_code=worker_code,
        env=env,
    )
    MlopsStack(
        app,
        f"FreshCast-Mlops-{config.env_name}",
        config=config,
        key=data.key,
        data_lake=data.data_lake,
        artifacts=data.artifacts,
        env=env,
    )
    Tags.of(app).add("project", "freshcast-ai")
    Tags.of(app).add("environment", config.env_name)
    Tags.of(app).add("data-classification", "synthetic-demo")
    return app
