def call(body) {
    // evaluate the body block, and collect configuration into the object
    def pipelineParams = [:]
    body.resolveStrategy = Closure.DELEGATE_FIRST
    body.delegate = pipelineParams
    body()

    def MICROSERVICE_NAME = null
    //def SOURCE_IMAGE_TAG = pipelineParams.SOURCE_IMAGE_TAG ? pipelineParams.SOURCE_IMAGE_TAG : "3.11.9-bullseye"
    def SOURCE_IMAGE_TAG = null
    def SLAVE_LABEL = 'docker'


    def appRepo = null
    def REPO_JSON = null
    

    def infoMap = null

    pipeline {
        agent {
            label "${SLAVE_LABEL}"
        }

        environment {
            AZURE_SUBSCRIPTION_ID='fc6d29cf-ef99-4f0f-86e6-5ae905010605'
            AZURE_TENANT_ID='b00367e2-193a-4f48-94de-7245d45c0947'
            AZURE_STORAGE_ACCOUNT='bloodymary'
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
                        infoMap = readYaml file: 'agentConfigCard.yaml'

                        SOURCE_IMAGE_TAG = infoMap.source_image_tag ? infoMap.source_image_tag : "3.11.9-bullseye"
                        appRepo = infoMap.appRepo
                        MICROSERVICE_NAME = infoMap.microservice_name
                        REPO_JSON = new groovy.json.JsonBuilder(infoMap.repositories).toString()

                        echo """
------------ INFO ------------
AGENT SOURCE:   ${params.agentVersion}
CURRENT BRANCH: ${env.currentBranch}
APP REPO:       ${appRepo}
REPO PYPI:      ${REPO_JSON}
------------------------------
                        """
                    }
                }
            }

           
            stage('Build Image') {
                steps {
                    script {
                        ansiColor('xterm') {
                            echo "[i] Start: Build Image Stage"
                            def version = null
                            // Clona la repo dentro "app_repo"
                            dir('cicd_repo') {
                                withCredentials([usernamePassword(credentialsId: 'clustervigil_gitlab', usernameVariable: 'GIT_USER', passwordVariable: 'GIT_PASS')]) {
                                    def repoHost = new URL(appRepo).getHost()
                                    // Scrivi .netrc
                                    writeFile file: "${env.HOME}/.netrc", text: """
                                        machine ${repoHost}
                                        login ${GIT_USER}
                                        password ${GIT_PASS}
                                    """
                                    sh "chmod 600 ${env.HOME}/.netrc"

                                    sh "git clone https://gitlab.liquid-reply.net/agentops/agentops_library ."
                                }
                            }
                            dir('app_repo') {
                                def tag = null


                                withCredentials([usernamePassword(credentialsId: 'clustervigil_gitlab', usernameVariable: 'GIT_USER', passwordVariable: 'GIT_PASS')]) {
                                    def repoHost = new URL(appRepo).getHost()
                                    // Scrivi .netrc
                                    writeFile file: "${env.HOME}/.netrc", text: """
                                        machine ${repoHost}
                                        login ${GIT_USER}
                                        password ${GIT_PASS}
                                    """
                                    sh "chmod 600 ${env.HOME}/.netrc"

                                    sh "git clone ${appRepo} ."
                                    sh "git checkout ${params.agentVersion}"
                                    version = sh(script: "grep '^version =' pyproject.toml | sed -E \"s/version = \\\"(.*)\\\"/\\1/\"", returnStdout: true).trim()
                                    if (params.agentVersion == 'test'){
                                        tag = version
                                    }
                                    else{
                                        def now = new Date()
                                        time = now.format("yyyyMMdd_HHmmss", TimeZone.getTimeZone('UTC'))
                                        tag = "${time}"
                                    }
                                    def tagExists = sh(
                                        script: """
                                            git ls-remote --tags origin refs/tags/${version} | grep ${version} > /dev/null
                                        """,
                                        returnStatus: true
                                    )

                                    if (tagExists == 0 && params.agentVersion == 'test') {
                                        error "Il tag '${version}' esiste già nel repository. Interruzione della pipeline."
                                    }

                                }
                                withCredentials([usernamePassword(credentialsId: 'clustervigil_gitlab', passwordVariable: 'DOCKER_PASS', usernameVariable: 'DOCKER_USER')]) {
                                    sh '''
                                    echo "${DOCKER_PASS}" | podman login registry.liquid-reply.net -u "${DOCKER_USER}" --password-stdin
                                    '''

                                    withCredentials([usernamePassword(credentialsId: "pypiCredentials", usernameVariable: 'user', passwordVariable: 'pass')]){
                                        sh'''
                                        BUILDER="../cicd_repo/resources/Dockerfile.builder"
                                        DEV="Dockerfile"
                                        OUT="Dockerfile.merged"

                                        cp ../cicd_repo/resources/configRepo.py .

                                        cat "$BUILDER" > "$OUT"

                                        echo "" >> "$OUT"
                                        cat "$DEV" >> "$OUT"

                                        echo "Dockerfile.merged generato"
                                        cat "$OUT"
                                        '''
                                        //--storage-driver vfs \
                                        sh """
                                            buildah bud \
                                                --build-arg=MICROSERVICE_NAME=${MICROSERVICE_NAME} \
                                                --build-arg=MICROSERVICE_VERSION=${version} \
                                                --build-arg=GIT_USER='${DOCKER_USER}' \
                                                --build-arg=GIT_PASS='${DOCKER_PASS}' \
                                                --build-arg=POETRY_REPOS_JSON='${REPO_JSON}'\
                                                --build-arg=POETRY_REPOS_USER='${user}'\
                                                --build-arg=POETRY_REPOS_PASSWORD='${pass}'\
                                                -f Dockerfile.merged \
                                                --no-cache \
                                                --platform linux/amd64 \
                                                -t registry.liquid-reply.net/agentops/${MICROSERVICE_NAME}:${tag} .
                                        """
                                    }
                                }

                                //sh "podman tag ${MICROSERVICE_NAME} registry.liquid-reply.net/agentops/${MICROSERVICE_NAME}:${tag}"
                                sh "podman push registry.liquid-reply.net/agentops/${MICROSERVICE_NAME}:${tag}"
                                //sh "podman rmi ${MICROSERVICE_NAME}"
                                sh "podman rmi registry.liquid-reply.net/agentops/${MICROSERVICE_NAME}:${tag}"
                                

                                if (params.agentVersion == 'test'){
                                    tagRepository(appRepo, tag, params.agentVersion)
                                } 
                            }
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
