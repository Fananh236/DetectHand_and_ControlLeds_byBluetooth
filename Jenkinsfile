def controllerLabel = 'built-in'
def windowsAgentLabel = 'Window'

properties([
    parameters([
        booleanParam(
            name: 'DEPLOY_TO_RENDER',
            defaultValue: false,
            description: 'After CI succeeds, trigger the configured Render deploy hook.'
        )
    ])
])

node(controllerLabel) {
    stage('Checkout on Controller') {
        deleteDir()
        checkout scm
        stash name: 'source', includes: '**'
    }
}

node(windowsAgentLabel) {
    try {
        stage('Prepare Windows Agent') {
            deleteDir()
            unstash 'source'
        }

        stage('Setup Python Environment') {
            bat '''
            python -m venv .jenkins-venv
            "%WORKSPACE%\\.jenkins-venv\\Scripts\\python.exe" -m pip install --upgrade pip
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

        stage('Cleanup Windows Agent') {
            deleteDir()
        }
    }
}

if (params.DEPLOY_TO_RENDER) {
    node(controllerLabel) {
        stage('Deploy to Render') {
            withCredentials([string(credentialsId: 'render-deploy-hook', variable: 'RENDER_DEPLOY_HOOK')]) {
                sh '''
                set +x
                curl --fail --silent --show-error --request POST "$RENDER_DEPLOY_HOOK"
                '''
            }
        }
    }
}
