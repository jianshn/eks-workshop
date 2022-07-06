#!/bin/bash


# Install Kubectl
sudo curl --location -o /usr/local/bin/kubectl "https://amazon-eks.s3.us-west-2.amazonaws.com/$KUBECTL_VERSION/2021-07-05/bin/linux/amd64/kubectl"
sudo chmod +x /usr/local/bin/kubectl
kubectl version --client

# Install Helm
curl -sSL https://raw.githubusercontent.com/helm/helm/master/scripts/get-helm-3 | bash
helm version --short

# Install jq, envsubst (from GNU gettext utilities) and bash-completion
sudo yum -y install jq gettext bash-completion moreutils

# Verify the binaries are in the path and executable
for command in kubectl jq envsubst aws
    do
    which $command &>/dev/null && echo "$command in path" || echo "$command NOT FOUND"
    done
    
# Enable kubectl bash_completion
kubectl completion bash >>  ~/.bash_completion
. /etc/profile.d/bash_completion.sh
. ~/.bash_completion

# Install yq for yaml processing
echo 'yq() {
  docker run --rm -i -v "${PWD}":/workdir mikefarah/yq:4.17.2 "$@"
}' | tee -a ~/.bash_profile && source ~/.bash_profile
yq --version

# Install eksctl

curl --silent --location "https://github.com/weaveworks/eksctl/releases/latest/download/eksctl_$(uname -s)_amd64.tar.gz" | tar xz -C /tmp
sudo mv -v /tmp/eksctl /usr/local/bin
eksctl version
eksctl completion bash >> ~/.bash_completion
. /etc/profile.d/bash_completion.sh
. ~/.bash_completion
