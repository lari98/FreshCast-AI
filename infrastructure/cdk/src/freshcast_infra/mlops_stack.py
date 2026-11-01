"""SageMaker model registry, execution role and cost guard."""

from __future__ import annotations

from aws_cdk import Stack
from aws_cdk import aws_budgets as budgets
from aws_cdk import aws_iam as iam
from aws_cdk import aws_kms as kms
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_sagemaker as sagemaker
from constructs import Construct

from freshcast_infra.config import DeployConfig


class MlopsStack(Stack):
    """Model package group (versioned, approvable models) and a scoped role."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        config: DeployConfig,
        key: kms.IKey,
        data_lake: s3.IBucket,
        artifacts: s3.IBucket,
        **kwargs: object,
    ) -> None:
        """Create registry, role and (optionally) a budget alert."""
        super().__init__(scope, construct_id, **kwargs)  # type: ignore[arg-type]
        # Import by ARN so KMS grants land on this stack's roles only; granting
        # on the original key would edit its policy and create a stack cycle.
        key = kms.Key.from_key_arn(self, "ImportedKey", key.key_arn)

        self.model_group = sagemaker.CfnModelPackageGroup(
            self,
            "ModelGroup",
            model_package_group_name=f"freshcast-demand-{config.env_name}",
            model_package_group_description="LightGBM demand forecasters",
        )
        # Least privilege: read data, write artifacts, nothing else.
        self.training_role = iam.Role(
            self,
            "TrainingRole",
            assumed_by=iam.ServicePrincipal("sagemaker.amazonaws.com"),
            description="FreshCast SageMaker training",
        )
        data_lake.grant_read(self.training_role)
        artifacts.grant_read_write(self.training_role)
        key.grant_encrypt_decrypt(self.training_role)

        if config.alert_email:  # a budget needs somewhere to send its alerts
            budgets.CfnBudget(
                self,
                "MonthlyBudget",
                budget=budgets.CfnBudget.BudgetDataProperty(
                    budget_type="COST",
                    time_unit="MONTHLY",
                    budget_limit=budgets.CfnBudget.SpendProperty(
                        amount=config.monthly_budget_usd, unit="USD"
                    ),
                ),
                notifications_with_subscribers=[
                    budgets.CfnBudget.NotificationWithSubscribersProperty(
                        notification=budgets.CfnBudget.NotificationProperty(
                            notification_type="ACTUAL",
                            comparison_operator="GREATER_THAN",
                            threshold=80,
                            threshold_type="PERCENTAGE",
                        ),
                        subscribers=[
                            budgets.CfnBudget.SubscriberProperty(
                                subscription_type="EMAIL", address=config.alert_email
                            )
                        ],
                    )
                ],
            )
