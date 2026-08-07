# Jenkins for this project

The Jenkins Controller is intentionally kept outside this repository so it can
be shared by multiple projects. Its infrastructure is located in the sibling
folder `../jenkins-infra` and should be started from WSL. Its default WSL path
is `/mnt/c/Users/phanh/OneDrive - University of Transport and Communications/Desktop/jenkins-infra`.

This repository only owns its [Jenkinsfile](Jenkinsfile) and application
Dockerfile. In the shared Jenkins UI, create a Pipeline job using **Pipeline
script from SCM**, select this repository, and use `Jenkinsfile` as the script
path.

The current pipeline requires Docker Pipeline support, which is installed by
the shared controller image. For a production or hardware-lab setup, run
device-facing stages on a dedicated labelled Jenkins agent rather than on the
shared controller.
