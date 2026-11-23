pipeline {
    agent {
        kubernetes {
            yaml '''
apiVersion: v1
kind: Pod
spec:
  automountServiceAccountToken: false
  containers:
    - name: python
      image: python:3.13-slim
      command: [cat]
      tty: true
      resources:
        requests: {cpu: 100m, memory: 128Mi}
    - name: ruby
      image: ruby:3.4-slim
      command: [cat]
      tty: true
      resources:
        requests: {cpu: 100m, memory: 128Mi}
'''
        }
    }
    options {
        disableConcurrentBuilds()
        timeout(time: 10, unit: 'MINUTES')
    }
    triggers {
        pollSCM('H/5 * * * *')
    }
    stages {
        stage('Validate repository') {
            steps {
                container('python') {
                    sh 'python3 -m unittest discover -s tests -v'
                }
                container('ruby') {
                    sh 'ruby scripts/check-configs.rb'
                }
            }
        }
    }
}
