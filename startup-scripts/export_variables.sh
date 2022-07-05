#!/bin/bash

echo "export KUBECTL_VERSION='1.21.2'" >>  ~/.bash_profile
echo "export KUBERNETES_VERSION='1.21'" >>  ~/.bash_profile
echo "export LBC_VERSION='v2.4.1'" >>  ~/.bash_profile
echo "export EKS_CLUSTER_NAME=eksworkshop-eksctl" >>  ~/.bash_profile
echo "export CLUSTER_IAM_ROLE_NAME='Cloud9InstanceRole'" >>  ~/.bash_profile
echo "export EKS_ADDON_CONTAINER_IMAGE_ADDRESS='602401143452.dkr.ecr.ap-southeast-1.amazonaws.com'" >>  ~/.bash_profile
source ~/.bash_profile
