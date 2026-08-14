# Jenkins for this project

The Jenkins Controller is intentionally kept outside this repository so it can
be shared by multiple projects. Its infrastructure is located in the sibling
folder `../jenkins-infra` and should be started from WSL. Its default WSL path
is `/mnt/c/Users/phanh/OneDrive - University of Transport and Communications/Desktop/jenkins-infra`.

This repository only owns its [Jenkinsfile](Jenkinsfile) and application
Dockerfile. In the shared Jenkins UI, create a Pipeline job using **Pipeline
script from SCM**, select this repository, and use `Jenkinsfile` as the script
path.

The current pipeline runs natively on a Windows-labelled Jenkins agent and
validates both the Python controller and the Django dashboard. For a
production or hardware-lab setup, run device-facing stages on a dedicated
labelled Jenkins agent rather than on the shared controller.

## Optional CD: deploy the dashboard to Render

The repository includes a [render.yaml](render.yaml) Blueprint. It provisions
a Docker-based Django web service and a PostgreSQL database in Singapore. The
cloud deployment is for the dashboard/API only: the webcam and HC-05 Bluetooth
device remain connected to the local Windows or Raspberry Pi gateway.

1. Push the repository to GitHub, then create a **New Blueprint Instance** in
   Render and select the repository. During setup, enter the generated service
   hostname for `DJANGO_ALLOWED_HOSTS` (for example,
   `your-service.onrender.com`) and its HTTPS URL for
   `DJANGO_CSRF_TRUSTED_ORIGINS`.
2. Complete the first deployment in Render and confirm that
   `https://your-service.onrender.com/healthz/` returns `{"status":"ok"}`.
   Render generates `DJANGO_SECRET_KEY` and supplies `DATABASE_URL`; do not
   create or commit either value yourself.
3. In the Render service, create a deploy hook for the `main` branch. In
   Jenkins, save its URL as a **Secret text** credential with the exact ID
   `render-deploy-hook`.
4. Run the Jenkins pipeline with `DEPLOY_TO_RENDER=true`. Jenkins triggers the
   hook only after all CI stages have passed. The parameter is `false` by
   default, so ordinary CI builds do not change the public website.

For automatic delivery, configure the Jenkins job from the protected `main`
branch and set `DEPLOY_TO_RENDER` through a dedicated release job or a
post-success trigger.
