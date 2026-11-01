"""Encryption key and S3 buckets (data lake, model artifacts)."""

from __future__ import annotations

from aws_cdk import Duration, RemovalPolicy, Stack
from aws_cdk import aws_kms as kms
from aws_cdk import aws_s3 as s3
from constructs import Construct

from freshcast_infra.config import DeployConfig


class DataStack(Stack):
    """KMS key plus private, versioned, encrypted buckets."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        config: DeployConfig,
        **kwargs: object,
    ) -> None:
        """Create the key and buckets."""
        super().__init__(scope, construct_id, **kwargs)  # type: ignore[arg-type]
        removal = RemovalPolicy.RETAIN if config.is_prod else RemovalPolicy.DESTROY

        self.key = kms.Key(
            self,
            "DataKey",
            enable_key_rotation=True,
            description="FreshCast data encryption key",
            removal_policy=RemovalPolicy.RETAIN,  # never lose the key to a stack delete
        )
        common = {
            "encryption": s3.BucketEncryption.KMS,
            "encryption_key": self.key,
            "block_public_access": s3.BlockPublicAccess.BLOCK_ALL,
            "enforce_ssl": True,
            "versioned": True,
            "removal_policy": removal,
            "auto_delete_objects": not config.is_prod,
        }
        self.data_lake = s3.Bucket(
            self,
            "DataLake",
            lifecycle_rules=[
                s3.LifecycleRule(
                    noncurrent_version_expiration=Duration.days(90),
                    abort_incomplete_multipart_upload_after=Duration.days(7),
                )
            ],
            **common,  # type: ignore[arg-type]
        )
        self.artifacts = s3.Bucket(self, "ModelArtifacts", **common)  # type: ignore[arg-type]
