pipeline {
    agent any

    options {
        skipDefaultCheckout(true)
    }

    stages {

        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Build Docker') {
            steps {
                script {
                    docker.build("smart-detect")
                }
            }
        }

        stage('Preparation') {
            steps {
                sh 'python --version'
                sh 'python -c "import cv2; print(cv2.__version__)"'
            }
        }

        stage('Lint') {
            steps {
                sh 'python -m flake8 --version'
                sh 'python -m flake8 Pi_controler/src Pi_controler/tests'
            }
        }

        stage('Unit Test') {
            steps {
                sh '''
                cd Pi_controler
                python -m coverage run -m unittest discover -s tests -p "test_*.py"
                '''
            }
        }

        stage('Coverage XML') {
            steps {
                sh '''
                cd Pi_controler
                python -m coverage xml -o coverage.xml
                '''
            }
        }

        stage('Coverage Report') {
            steps {
                sh '''
                cd Pi_controler
                python -m coverage report -m
                '''
            }
        }

        stage('Cleanup') {
            steps {
                cleanWs()
            }
        }
    }
}