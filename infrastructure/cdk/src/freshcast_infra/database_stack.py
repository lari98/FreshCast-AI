"""Network and PostgreSQL database (private, encrypted)."""

from __future__ import annotations

from aws_cdk import Duration, RemovalPolicy, Stack
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_kms as kms
from aws_cdk import aws_rds as rds
from constructs import Construct

from freshcast_infra.config import DeployConfig


class DatabaseStack(Stack):
    """VPC without internet egress and an RDS PostgreSQL instance inside it."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        config: DeployConfig,
        key: kms.IKey,
        **kwargs: object,
    ) -> None:
        """Create the VPC, endpoints and database."""
        super().__init__(scope, construct_id, **kwargs)  # type: ignore[arg-type]
        # Import by ARN so KMS grants land on this stack's roles only; granting
        # on the original key would edit its policy and create a stack cycle.
        key = kms.Key.from_key_arn(self, "ImportedKey", key.key_arn)
        # Isolated subnets only: nothing here has a route to the internet, so
        # no NAT gateway cost and no outbound data path to leak through.
        self.vpc = ec2.Vpc(
            self,
            "Vpc",
            max_azs=2,
            nat_gateways=0,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="isolated",
                    subnet_type=ec2.SubnetType.PRIVATE_ISOLATED,
                    cidr_mask=24,
                )
            ],
        )
        # Interface endpoints cost money per AZ-hour; they are what lets the
        # worker reach SQS and Secrets Manager without internet access.
        self.vpc.add_gateway_endpoint(
            "S3Endpoint", service=ec2.GatewayVpcEndpointAwsService.S3
        )
        for name, service in (
            ("SqsEndpoint", ec2.InterfaceVpcEndpointAwsService.SQS),
            ("SecretsEndpoint", ec2.InterfaceVpcEndpointAwsService.SECRETS_MANAGER),
        ):
            self.vpc.add_interface_endpoint(name, service=service)

        self.db_security_group = ec2.SecurityGroup(
            self, "DbSg", vpc=self.vpc, allow_all_outbound=False
        )
        # Created here (not in the messaging stack) so the ingress rule lives in
        # the same stack as the database and no cross-stack cycle appears.
        self.worker_security_group = ec2.SecurityGroup(self, "WorkerSg", vpc=self.vpc)
        self.db_security_group.add_ingress_rule(
            self.worker_security_group, ec2.Port.tcp(5432), "worker to PostgreSQL"
        )
        self.database = rds.DatabaseInstance(
            self,
            "Postgres",
            engine=rds.DatabaseInstanceEngine.postgres(
                version=rds.PostgresEngineVersion.VER_16
            ),
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.BURSTABLE4_GRAVITON, ec2.InstanceSize.MICRO
            ),
            vpc=self.vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_ISOLATED
            ),
            security_groups=[self.db_security_group],
            database_name="freshcast",
            credentials=rds.Credentials.from_generated_secret(
                "freshcast_admin", encryption_key=key
            ),
            storage_encrypted=True,
            storage_encryption_key=key,
            publicly_accessible=False,
            multi_az=config.is_prod,
            allocated_storage=20,
            backup_retention=Duration.days(14 if config.is_prod else 1),
            deletion_protection=config.is_prod,
            removal_policy=RemovalPolicy.RETAIN
            if config.is_prod
            else RemovalPolicy.DESTROY,
            enable_performance_insights=False,
        )
        if self.database.secret is None:  # always set with generated credentials
            raise RuntimeError("database secret missing")
        self.secret = self.database.secret
