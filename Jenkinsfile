node('Window') {
    try {
        stage('Checkout') {
            checkout scm
        }

        stage('Setup Python Environment') {
            bat '''
            python -m venv .jenkins-venv
            "%WORKSPACE%\\.jenkins-venv\\Scripts\\python.exe" -m pip install --upgrade pip
            "%WORKSPACE%\\.jenkins-venv\\Scripts\\python.exe" -m pip install -r requirements-dev.txt
            '''
        }

        stage('Preparation') {
            bat '''
            "%WORKSPACE%\\.jenkins-venv\\Scripts\\python.exe" --version
            "%WORKSPACE%\\.jenkins-venv\\Scripts\\python.exe" -c "import cv2; print(cv2.__version__)"
            '''
        }

        stage('Lint') {
            bat '''
            "%WORKSPACE%\\.jenkins-venv\\Scripts\\python.exe" -m flake8 Pi_controler\\src Pi_controler\\tests Pi_controler\\web Pi_controler\\web_config
            '''
        }

        stage('Django Check') {
            bat '''
            cd /d Pi_controler
            "%WORKSPACE%\\.jenkins-venv\\Scripts\\python.exe" manage.py check
            "%WORKSPACE%\\.jenkins-venv\\Scripts\\python.exe" manage.py makemigrations --check --dry-run
            '''
        }

        stage('Unit Test') {
            bat '''
            cd /d Pi_controler
            "%WORKSPACE%\\.jenkins-venv\\Scripts\\python.exe" -m coverage run -m unittest discover -s tests -p "test_*.py"
            "%WORKSPACE%\\.jenkins-venv\\Scripts\\python.exe" -m coverage run -a manage.py test web
            '''
        }

        stage('Coverage') {
            bat '''
            cd /d Pi_controler
            "%WORKSPACE%\\.jenkins-venv\\Scripts\\python.exe" -m coverage xml -o coverage.xml
            "%WORKSPACE%\\.jenkins-venv\\Scripts\\python.exe" -m coverage report -m
            '''
        }
    } finally {
        stage('Publish Coverage') {
            archiveArtifacts artifacts: 'Pi_controler/coverage.xml', allowEmptyArchive: true, fingerprint: true
        }

        stage('Cleanup') {
            deleteDir()
        }
    }
}
