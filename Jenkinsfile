node('Window') {
    try {
        stage('Checkout') {
            checkout scm
        }

        stage('Setup Python Environment') {
            bat '''
            python -m venv .jenkins-venv
            "%WORKSPACE%\\.jenkins-venv\\Scripts\\python.exe" -m pip install --upgrade pip
            "%WORKSPACE%\\.jenkins-venv\\Scripts\\python.exe" -m pip install flake8 coverage
            "%WORKSPACE%\\.jenkins-venv\\Scripts\\python.exe" -m pip install -r requirements.txt
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
            "%WORKSPACE%\\.jenkins-venv\\Scripts\\python.exe" -m flake8 Pi_controler\\src Pi_controler\\tests
            '''
        }

        stage('Unit Test') {
            bat '''
            cd /d Pi_controler
            "%WORKSPACE%\\.jenkins-venv\\Scripts\\python.exe" -m coverage run -m unittest discover -s tests -p "test_*.py"
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