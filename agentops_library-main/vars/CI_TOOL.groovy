def call(body) {
    // evaluate the body block, and collect configuration into the object
    def pipelineParams = [:]
    body.resolveStrategy = Closure.DELEGATE_FIRST
    body.delegate = pipelineParams
    body()
   
    def SLAVE_LABEL = 'docker'


    def appRepo = null
    def packetName = null
    def pypiURL = null

    def infoMap = null

    def toolVersion = null

    pipeline {
        agent {
            label "${SLAVE_LABEL}"
        }

    environment {
        PYENV_ROOT = "${HOME}/.pyenv"
        PATH = "${PYENV_ROOT}/shims:${PYENV_ROOT}/bin:${env.PATH}"
    }
        options {
            disableConcurrentBuilds()
            timeout(time: 2, unit: 'HOURS')
            buildDiscarder(logRotator(numToKeepStr: '15'))
            ansiColor('xterm')
        }

        stages {
            stage('Preliminary steps') {
                steps {
                    script {
                        echo "[i] Start: Preliminary steps Stage"

                        env.currentBranch = scm.branches[0].name.replaceAll('^refs/heads/', '')

                        // Load info
                        infoMap = readYaml file: 'toolConfigCard.yaml'
                        appRepo = infoMap.appRepo
                        packetName = infoMap.packetName
                        pypiURL = infoMap.pypiURL
                    }
                }
            }

            stage('TOOL information') {
                steps {
                    script {
                        echo """
                            ------------ INFO ------------
                            TOOL REPO: ${appRepo}
                            PIPY URL:  ${pypiURL}
                            TOOL NAME: ${packetName}
                            ------------------------------
                        """
                    }
                }
            }

            stage('Creating Poetry Env') {
                steps {
                    script{
                        withCredentials([usernamePassword(credentialsId: "pypiCredentials", usernameVariable: 'user', passwordVariable: 'pass')]){
                            dir("tool") {
                                git url: appRepo, credentialsId: "clustervigil_gitlab", branch: "main"
                                sh"""
                                poetry config repositories.${packetName} ${pypiURL}
                                poetry config http-basic.${packetName} '${user}' '${pass}'
                                """
                                toolVersion = sh(
                                    script: """grep '^version' pyproject.toml | sed -E 's/version = "(.*)"/\\1/'""",
                                    returnStdout: true
                                ).trim()
                                setupPoetryEnvironment(appRepo)
                            }
                        }

                    }
                }
            }

            stage('Build and push') {
                steps {
                    script{
                        dir("tool") {
                            sh """
                            poetry build
                            poetry publish --repository ${packetName}
                            """
                        }
                    }
                }
            }
            stage('Tag repo') {
                steps {
                    script{
                        dir("tool_tag") {
                            tagRepository(appRepo,toolVersion,"main")
                        }
                    }
                }
            }
        }


        post {
             always {
                 deleteDir()
            }     
        }
    }
}
