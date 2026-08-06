pipeline {
    agent any

    options {
        // The explicit Checkout stage below is the single source checkout.
        skipDefaultCheckout(true)
    }

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

        // Sequential child stages inherit this single Docker agent. Dependencies
        // installed in Preparation therefore remain available to Lint and Test.
        stage('CI checks') {
            agent {
                docker {
                    image 'python:3.14-slim'
                    reuseNode true
                }
            }

            stages {
                stage('Preparation') {
                    steps {
                        sh 'python --version'
                        sh 'python -m pip install --upgrade pip'
                        sh 'python -m pip install -r requirements.txt flake8 coverage'
                    }
                }

                stage('Lint') {
                    steps {
                        sh 'python -m flake8 --version'
                        sh 'python -m flake8 Pi_controler/src Pi_controler/tests'
                    }
                }

                stage('Run tests with coverage') {
                    steps {
                        sh 'cd Pi_controler && python -m coverage run -m unittest discover -s tests -p "test_*.py"'
                        sh 'cd Pi_controler && python -m coverage xml -o coverage.xml'
                        sh 'cd Pi_controler && python -m coverage report -m'
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
