#!/bin/bash

# Upgrade AWS CLI according to guidance in AWS documentation .
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install
aws --version
. ~/.bash_profile

# Setup AWS account environment variable
echo "export ACCOUNT_ID=$(aws sts get-caller-identity --output text --query Account)"  >>  ~/.bash_profile
echo "export AWS_REGION=$(curl -s 169.254.169.254/latest/dynamic/instance-identity/document | jq -r '.region')"  >>  ~/.bash_profile
.  ~/.bash_profile
echo "export AZS=($(aws ec2 describe-availability-zones --query 'AvailabilityZones[].ZoneName' --output text --region $AWS_REGION))"  >>  ~/.bash_profile
.  ~/.bash_profile
source ~/.bash_profile
aws configure set default.region ${AWS_REGION}
aws configure get default.region

test -n "$ACCOUNT_ID" && echo ACCOUNT_ID is "$ACCOUNT_ID" || echo ACCOUNT_ID is not set
test -n "$AWS_REGION" && echo AWS_REGION is "$AWS_REGION" || echo AWS_REGION is not set
