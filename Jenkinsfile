node {
    stage('Checkout') {
        checkout scm
    }

    def ciImage

    stage('Build Docker') {
        ciImage = docker.build('smart-detect')
    }

    // Keep one Python container alive while displaying each CI action as a
    // separate top-level Stage View column.
    ciImage.inside {
        try {
            stage('Preparation') {
                sh 'python --version'
                sh 'python -c "import cv2; print(cv2.__version__)"'
            }

            stage('Lint') {
                sh 'python -m flake8 --version'
                sh 'python -m flake8 Pi_controler/src Pi_controler/tests'
            }

            stage('Unit Test') {
                sh '''
                cd Pi_controler
                python -m coverage run -m unittest discover -s tests -p "test_*.py"
                '''
            }

            stage('Coverage XML') {
                sh '''
                cd Pi_controler
                python -m coverage xml -o coverage.xml
                '''
            }

            stage('Coverage Report') {
                sh '''
                cd Pi_controler
                python -m coverage report -m
                '''
            }
        } finally {
            stage('Cleanup') {
                cleanWs()
            }
        }
    }
}
