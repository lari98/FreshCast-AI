"""Assertions on the synthesized CloudFormation (no AWS account needed)."""

import json

import pytest
from aws_cdk import App
from aws_cdk import aws_lambda as lambda_
from aws_cdk.assertions import Match, Template

from freshcast_infra.app_factory import build_app
from freshcast_infra.config import DeployConfig


def _templates(config: DeployConfig) -> dict[str, Template]:
    app = build_app(config, lambda_.Code.from_inline("def handler(e, c): pass"), App())
    return {
        stack.stack_name.split("-")[1]: Template.from_stack(stack)
        for stack in app.node.children
        if hasattr(stack, "stack_name")
    }


@pytest.fixture(scope="module")
def dev() -> dict[str, Template]:
    return _templates(DeployConfig(alert_email="ops@example.com"))


@pytest.fixture(scope="module")
def prod() -> dict[str, Template]:
    return _templates(DeployConfig(env_name="prod"))


def test_all_buckets_are_private_encrypted_versioned_tls_only(
    dev: dict[str, Template],
) -> None:
    t = dev["Data"]
    t.resource_count_is("AWS::S3::Bucket", 2)
    for bucket in t.find_resources("AWS::S3::Bucket").values():
        props = bucket["Properties"]
        assert props["VersioningConfiguration"] == {"Status": "Enabled"}
        assert props["PublicAccessBlockConfiguration"]["BlockPublicAcls"] is True
        enc = props["BucketEncryption"]["ServerSideEncryptionConfiguration"][0]
        assert enc["ServerSideEncryptionByDefault"]["SSEAlgorithm"] == "aws:kms"
    t.has_resource_properties(
        "AWS::S3::BucketPolicy",
        {
            "PolicyDocument": {
                "Statement": Match.array_with(
                    [
                        Match.object_like(
                            {
                                "Effect": "Deny",
                                "Condition": {"Bool": {"aws:SecureTransport": "false"}},
                            }
                        )
                    ]
                )
            }
        },
    )


def test_kms_key_rotates_and_is_retained(dev: dict[str, Template]) -> None:
    t = dev["Data"]
    t.has_resource_properties("AWS::KMS::Key", {"EnableKeyRotation": True})
    t.has_resource("AWS::KMS::Key", {"DeletionPolicy": "Retain"})


def test_database_is_private_and_encrypted(dev: dict[str, Template]) -> None:
    t = dev["Db"]
    t.has_resource_properties(
        "AWS::RDS::DBInstance",
        {"StorageEncrypted": True, "PubliclyAccessible": False, "Engine": "postgres"},
    )
    t.resource_count_is("AWS::EC2::NatGateway", 0)
    t.resource_count_is("AWS::EC2::InternetGateway", 0)


def test_prod_database_is_protected_dev_is_disposable(
    dev: dict[str, Template], prod: dict[str, Template]
) -> None:
    prod["Db"].has_resource_properties(
        "AWS::RDS::DBInstance", {"DeletionProtection": True, "MultiAZ": True}
    )
    dev["Db"].has_resource_properties(
        "AWS::RDS::DBInstance", {"DeletionProtection": False, "MultiAZ": False}
    )


def test_queue_is_fifo_with_dlq_after_three_receives(dev: dict[str, Template]) -> None:
    t = dev["Messaging"]
    t.has_resource_properties(
        "AWS::SQS::Queue",
        {
            "FifoQueue": True,
            "RedrivePolicy": Match.object_like({"maxReceiveCount": 3}),
            "KmsMasterKeyId": Match.any_value(),
        },
    )


def test_worker_reports_partial_batch_failures(dev: dict[str, Template]) -> None:
    t = dev["Messaging"]
    t.has_resource_properties(
        "AWS::Lambda::EventSourceMapping",
        {"FunctionResponseTypes": ["ReportBatchItemFailures"], "BatchSize": 10},
    )
    t.has_resource_properties(
        "AWS::Lambda::Function",
        {"Runtime": "python3.12", "Handler": "freshcast_api.worker.handler"},
    )


def test_dlq_alarm_notifies_by_email(dev: dict[str, Template]) -> None:
    t = dev["Messaging"]
    t.has_resource_properties(
        "AWS::CloudWatch::Alarm",
        {"Threshold": 1, "AlarmActions": Match.any_value()},
    )
    t.has_resource_properties(
        "AWS::SNS::Subscription", {"Protocol": "email", "Endpoint": "ops@example.com"}
    )


def test_model_registry_and_budget_exist(dev: dict[str, Template]) -> None:
    t = dev["Mlops"]
    t.has_resource_properties(
        "AWS::SageMaker::ModelPackageGroup",
        {"ModelPackageGroupName": "freshcast-demand-dev"},
    )
    t.resource_count_is("AWS::Budgets::Budget", 1)


def test_no_budget_without_alert_email(prod: dict[str, Template]) -> None:
    prod["Mlops"].resource_count_is("AWS::Budgets::Budget", 0)


def test_no_iam_statement_grants_all_actions(dev: dict[str, Template]) -> None:
    for template in dev.values():
        for policy in template.find_resources("AWS::IAM::Policy").values():
            for stmt in policy["Properties"]["PolicyDocument"]["Statement"]:
                actions = stmt["Action"]
                actions = [actions] if isinstance(actions, str) else actions
                assert "*" not in actions, json.dumps(stmt)


def test_config_rejects_unsafe_values() -> None:
    with pytest.raises(ValueError, match="region"):
        DeployConfig(region="us-east-1")
    with pytest.raises(ValueError, match="env_name"):
        DeployConfig(env_name="staging")
    with pytest.raises(ValueError, match="budget"):
        DeployConfig(monthly_budget_usd=0)
