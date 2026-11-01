"""Event queue, dead-letter queue, worker Lambda and alarms."""

from __future__ import annotations

from aws_cdk import Duration, Stack
from aws_cdk import aws_cloudwatch as cw
from aws_cdk import aws_cloudwatch_actions as cw_actions
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_kms as kms
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_lambda_event_sources as sources
from aws_cdk import aws_secretsmanager as secretsmanager
from aws_cdk import aws_sns as sns
from aws_cdk import aws_sns_subscriptions as subs
from aws_cdk import aws_sqs as sqs
from constructs import Construct

from freshcast_infra.config import DeployConfig


class MessagingStack(Stack):
    """FIFO queue (ordered per store:sku), DLQ, worker and DLQ alarm."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        config: DeployConfig,
        key: kms.IKey,
        vpc: ec2.IVpc,
        db_secret: secretsmanager.ISecret,
        worker_security_group: ec2.ISecurityGroup,
        worker_code: lambda_.Code,
        **kwargs: object,
    ) -> None:
        """Create queues, worker and monitoring."""
        super().__init__(scope, construct_id, **kwargs)  # type: ignore[arg-type]
        # Import by ARN so KMS grants land on this stack's roles only; granting
        # on the original key would edit its policy and create a stack cycle.
        key = kms.Key.from_key_arn(self, "ImportedKey", key.key_arn)

        self.dlq = sqs.Queue(
            self,
            "EventsDlq",
            fifo=True,
            encryption=sqs.QueueEncryption.KMS,
            encryption_master_key=key,
            enforce_ssl=True,
            retention_period=Duration.days(14),
        )
        self.queue = sqs.Queue(
            self,
            "Events",
            fifo=True,
            content_based_deduplication=False,  # the event_id is the dedup id
            encryption=sqs.QueueEncryption.KMS,
            encryption_master_key=key,
            enforce_ssl=True,
            visibility_timeout=Duration.seconds(180),  # > 6 x worker timeout
            dead_letter_queue=sqs.DeadLetterQueue(max_receive_count=3, queue=self.dlq),
        )

        self.worker = lambda_.Function(
            self,
            "Worker",
            runtime=lambda_.Runtime.PYTHON_3_12,
            architecture=lambda_.Architecture.ARM_64,
            handler="freshcast_api.worker.handler",
            code=worker_code,
            timeout=Duration.seconds(30),
            memory_size=512,
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_ISOLATED
            ),
            security_groups=[worker_security_group],
            environment={
                "FRESHCAST_ENV": config.env_name,
                "FRESHCAST_DB_SECRET_ARN": db_secret.secret_arn,
            },
            tracing=lambda_.Tracing.ACTIVE,
        )
        self.queue.grant_consume_messages(self.worker)
        db_secret.grant_read(self.worker)
        key.grant_decrypt(self.worker)
        self.worker.add_event_source(
            sources.SqsEventSource(
                self.queue,
                batch_size=10,
                report_batch_item_failures=True,  # partial batch responses
            )
        )

        # Anything in the DLQ needs a human: alarm on a single message.
        self.alarm_topic = sns.Topic(self, "AlarmTopic", master_key=key)
        if config.alert_email:
            self.alarm_topic.add_subscription(
                subs.EmailSubscription(config.alert_email)
            )
        alarm = cw.Alarm(
            self,
            "DlqNotEmpty",
            metric=self.dlq.metric_approximate_number_of_messages_visible(
                period=Duration.minutes(1)
            ),
            threshold=1,
            evaluation_periods=1,
            comparison_operator=cw.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
            treat_missing_data=cw.TreatMissingData.NOT_BREACHING,
        )
        alarm.add_alarm_action(cw_actions.SnsAction(self.alarm_topic))
