pipeline {
    agent any

    stages {
        stage('Checkout') {
            steps {
                checkout([
                    $class: 'GitSCM',
                    branches: [[name: '*/main']],
                    userRemoteConfigs: [[url: 'https://github.com/Fananh236/DetectHand_and_ControlLeds_byBluetooth.git']]
                ])
            }
        }

        stage('Preparation') {
            steps {
                script {
                    docker.image('python:3.14-slim').inside {
                        sh 'python --version'
                        sh 'python -m pip install --upgrade pip'
                        sh 'python -m pip install -r requirements.txt flake8 coverage'
                    }
                }
            }
        }

        stage('Lint') {
            steps {
                script {
                    docker.image('python:3.14-slim').inside {
                        sh 'python -m flake8 Pi_controler/src Pi_controler/tests'
                    }
                }
            }
        }

        stage('Run tests with coverage') {
            steps {
                script {
                    docker.image('python:3.14-slim').inside {
                        sh 'cd Pi_controler && coverage run -m unittest discover -s tests -p "test_*.py"'
                        sh 'cd Pi_controler && coverage xml -o coverage.xml'
                        sh 'cd Pi_controler && coverage report -m'
                    }
                }
            }
        }

        stage('SonarQube analysis') {
            steps {
                script {
                    docker.image('sonarsource/sonar-scanner-cli:latest').inside {
                        withSonarQubeEnv('SonarQube') {
                            sh 'sonar-scanner -Dsonar.projectKey=DetectHand_and_ControlLeds_byBluetooth -Dsonar.sources=Pi_controler/src -Dsonar.tests=Pi_controler/tests -Dsonar.python.coverage.reportPaths=Pi_controler/coverage.xml'
                        }
                    }
                }
            }
        }
    }
}
