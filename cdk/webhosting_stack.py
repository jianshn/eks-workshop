from re import template
from aws_cdk import (
    # Duration,
    Stack,
    aws_s3 as s3,
    aws_s3_deployment as s3_deploy,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_ssm as ssm,
    aws_iam as iam,
    aws_rds as rds,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as cloudfront_origins,
    aws_secretsmanager as secretsmanager,
    aws_autoscaling as autoscaling,
    aws_elasticloadbalancingv2 as alb
)
import aws_cdk as cdk
from constructs import Construct
import json
import string
import random
import requests
import boto3

user_data = """#!/bin/sh

# Install a LAMP stack
amazon-linux-extras install -y lamp-mariadb10.2-php7.2 php7.2
yum -y install httpd php-mbstring

# Start the web server
chkconfig httpd on
systemctl start httpd

# Install the web pages for our lab
if [ ! -f /var/www/html/immersion-day-app-php7.tar.gz ]; then
   cd /var/www/html
   wget https://github.com/HazelHazirah/immersion_php/raw/main/immersion_php.tar.gz
   sudo tar xvf immersion_php.tar.gz
fi

# Install the AWS SDK for PHP
if [ ! -f /var/www/html/aws.zip ]; then
   cd /var/www/html
   mkdir vendor
   cd vendor
   wget https://docs.aws.amazon.com/aws-sdk-php/v3/download/aws.zip
   unzip aws.zip
fi

# Update existing packages
yum -y update
"""

class WebhostingStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        #Get region
        print(self.region)
        
        #Create the VPC
        vpc = ec2.Vpc(self, "Webhosting-VPC", ip_addresses=ec2.IpAddresses.cidr('10.0.0.0/16'))

        # Create IAM role
        assumeRoleTrustPolicy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {
                        "Service": "ec2.amazonaws.com"
                    },
                    "Action": "sts:AssumeRole"
                }
            ]
        }

        webserver_role = iam.CfnRole(self, "webserver_Role",
            assume_role_policy_document=assumeRoleTrustPolicy,
            description="New role for Webserver Instance",
            managed_policy_arns=["arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore", "arn:aws:iam::aws:policy/SecretsManagerReadWrite"],
            role_name="SSMInstanceProfile")

        webserver_instance_profile = iam.CfnInstanceProfile(self, "WebserverInstanceProfile",
            roles=[webserver_role.role_name])

        # Create security group
        ## Create webserver SG
        ec2_sg = ec2.SecurityGroup(self, "WebserverSG", vpc=vpc, security_group_name="Immersion Day - Web Server")
        ec2_sg.add_ingress_rule(ec2.Peer.ipv4("0.0.0.0/0"), ec2.Port.tcp(22), "SSH")
        ec2_sg.add_ingress_rule(ec2.Peer.ipv4("0.0.0.0/0"), ec2.Port.tcp(80), "HTTP")

        ## Create load balancer SG
        alb_sg = ec2.SecurityGroup(self, "WebALBSG", vpc=vpc, security_group_name="web-ALB-SG")
        alb_sg.add_ingress_rule(ec2.Peer.ipv4("0.0.0.0/0"), ec2.Port.tcp(80), "HTTP")

        ## Create autoscaling group SG
        autoscaling_sg = ec2.SecurityGroup(self, "AutoscalingSG", vpc=vpc, security_group_name="ASG-Web_Inst-SG")
        autoscaling_sg.add_ingress_rule(ec2.Peer.security_group_id(alb_sg.security_group_id), ec2.Port.tcp(80), "HTTP")

        ## Create RDS SG
        rds_sg = ec2.SecurityGroup(self, "RDSSG", vpc=vpc, security_group_name="DB-SG")
        rds_sg.add_ingress_rule(ec2.Peer.security_group_id(autoscaling_sg.security_group_id), ec2.Port.tcp(3306), "TCP")

        # Create Launch template
        ## Get latest amazon linux ami
        ssm = boto3.client('ssm')
        imageId = ssm.get_parameters(
            Names=[
                '/aws/service/ami-amazon-linux-latest/amzn2-ami-hvm-x86_64-gp2',
            ]
        )['Parameters'][0]['Value']
        WebserverLaunchTemplate = ec2.CfnLaunchTemplate(self, "WebserverLaunchTemplate",
            launch_template_data=ec2.CfnLaunchTemplate.LaunchTemplateDataProperty(
                instance_type='m5.2xlarge',
                user_data=cdk.Fn.base64(user_data),
                iam_instance_profile=ec2.CfnLaunchTemplate.IamInstanceProfileProperty(
                    arn=webserver_instance_profile.attr_arn
                ),
                image_id=imageId,
                security_group_ids=[autoscaling_sg.security_group_id]
            ),
            launch_template_name='web-lt')

        # Create ALB
        web_alb = alb.ApplicationLoadBalancer(self, "web-alb",
            vpc=vpc,
            internet_facing=True,
            security_group=alb_sg
        )

        ## Add a listener
        listener = web_alb.add_listener("Listener", port=80)

        ## Create Target Group
        web_tg = listener.add_targets("web-tg", 
            port=80,
            target_group_name="web-tg")
        
        ## Add listner rule for custom header
        application_listener_rule = alb.ApplicationListenerRule(self, "MyApplicationListenerRule",
            listener=listener,
            priority=1,
            conditions=[alb.ListenerCondition.http_header("X-Custom-Header",["123"])],
            target_groups=[web_tg]
        )

        # Create Autoscaling group
        vpc_selection = vpc.select_subnets(
            subnet_type=ec2.SubnetType.PRIVATE_WITH_NAT
        )

        web_asg = autoscaling.CfnAutoScalingGroup(self, "Web_ASG",
            launch_template=autoscaling.CfnAutoScalingGroup.LaunchTemplateSpecificationProperty(
                version="1",
                launch_template_name=WebserverLaunchTemplate.launch_template_name
            ),
            vpc_zone_identifier=vpc_selection.subnet_ids,
            auto_scaling_group_name="Web_ASG",
            desired_capacity='2',
            min_size='2',
            max_size='4',
            target_group_arns=[web_tg.target_group_arn]
            )

        ## Create scaling policy
        asg_scaling_policy = autoscaling.CfnScalingPolicy(self, "AsgScalingPolicy",
            auto_scaling_group_name=web_asg.auto_scaling_group_name,
            policy_type="TargetTrackingScaling",
            target_tracking_configuration=autoscaling.CfnScalingPolicy.TargetTrackingConfigurationProperty(
                target_value=30,
                predefined_metric_specification=autoscaling.CfnScalingPolicy.PredefinedMetricSpecificationProperty(
                    predefined_metric_type="ASGAverageCPUUtilization"
                )
            )
        )

        # Create RDS Instance
        dBSubnet_group = rds.CfnDBSubnetGroup(self, "DBSubnetGroup",
            db_subnet_group_description="dbSubnetGroup",
            subnet_ids=vpc_selection.subnet_ids,

            # the properties below are optional
            db_subnet_group_name="db-SubnetGroup"
        )

        dBInstance = rds.CfnDBInstance(self, "DBInstance",
            allocated_storage="100",
            db_instance_identifier="rdscluster",
            db_instance_class="db.r5.large",
            db_name="immersionday",
            db_subnet_group_name=dBSubnet_group.db_subnet_group_name,
            enable_iam_database_authentication=True,
            delete_automated_backups=True,
            engine="mysql",
            engine_version="8.0.28",
            iops=3000,
            master_username="awsuser",
            master_user_password="awspassword",
            max_allocated_storage=1000,
            multi_az=True,
            port="3306",
            publicly_accessible=False,
            vpc_security_groups=[rds_sg.security_group_id]
        )

        # Create Secret in secrets manager
        secret={
            "username":"awsuser",
            "password":"awspassword",
            "engine":"mysql",
            "port":3306,
            "dbname":"immersionday",
            "host": dBInstance.attr_endpoint_address
        }

        db_secret = secretsmanager.CfnSecret(self, "dbSecret",
            name="mysecret",
            secret_string=json.dumps(secret)
        )

        # Create S3 Bucket and populate html file
        bucketName = "webhosting" + "-"  + ''.join(random.choices(string.ascii_lowercase + string.digits, k = 10))

        website_bucket = s3.Bucket(self, "website_bucket",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            auto_delete_objects=True,
            removal_policy=cdk.RemovalPolicy.DESTROY,
            bucket_name=bucketName
        )

        URL = "https://raw.githubusercontent.com/HazelHazirah/immersion_php/main/login.html"
        response=requests.get(URL)

        deployment = s3_deploy.BucketDeployment(self, "DeployWebsite",
            sources=[s3_deploy.Source.data("login.html", response.content.decode("utf-8"))],
            destination_bucket=website_bucket
        ) 

        # Create Cloudfront Distribution
        origin = cloudfront_origins.S3Origin(
                bucket=website_bucket,
                )

        distribution = cloudfront.Distribution(
            self,
            "CloudFrontDistribution",
            default_behavior=cloudfront.BehaviorOptions(
                allowed_methods=cloudfront.AllowedMethods.ALLOW_GET_HEAD,
                origin=origin,
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS
            ),
            default_root_object="login.html"
        )

        distribution.add_behavior("/login.html",
            origin=origin,
            viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.ALLOW_ALL,
            allowed_methods=cloudfront.AllowedMethods.ALLOW_GET_HEAD,
        )

        distribution.add_behavior("/*", 
            cloudfront_origins.LoadBalancerV2Origin(
                load_balancer=web_alb,
                custom_headers={"X-Custom-Header":"123"},
                protocol_policy=cloudfront.OriginProtocolPolicy.HTTP_ONLY
            ),
            allowed_methods=cloudfront.AllowedMethods.ALLOW_ALL,
            viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.ALLOW_ALL,
            cache_policy=cloudfront.CachePolicy.CACHING_DISABLED,
        )


        # Depends on
        web_asg.add_dependency(WebserverLaunchTemplate)
        asg_scaling_policy.add_dependency(web_asg)
        webserver_instance_profile.add_dependency(webserver_role)
        dBInstance.add_dependency(dBSubnet_group)
        db_secret.add_dependency(dBInstance)
