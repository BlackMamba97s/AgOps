def call(body) {
    // evaluate the body block, and collect configuration into the object
    def pipelineParams = [:]
    body.resolveStrategy = Closure.DELEGATE_FIRST
    body.delegate = pipelineParams
    body()


   
    def SLAVE_LABEL = 'docker'


    def ragId = null
    def ragDir = null
    def ragSize = null
    def sdk_version = null
    def vec_db_sdk = null
    def azure_storage_account = null
    def embeddings_model = null

    
    def infoMap = null


    pipeline {
        agent {
            label "${SLAVE_LABEL}"
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

                        ragId = params.ragID
                        ragDir = infoMap.ragDir
                        ragSize = infoMap.ragSize
                        sdk_version =  infoMap.sdk_version
                        vec_db_sdk =  infoMap.vec_db_sdk   
                        azure_storage_account = infoMap.azure_storage_account
                        embeddings_model = infoMap.embeddings_model
                        
                    }
                }
            }

            stage('RAG information') {
                steps {
                    script {
                        echo """
                            ------------ INFO ------------
                            RAG ID:             ${ragId}
                            RAG DIR:            ${ragDir}
                            RAG SIZE:           ${ragSize}
                            VEC DB SDK:         ${vec_db_sdk}
                            SDK VERSION:        ${sdk_version}
                            MODEL:              ${embeddings_model}
                            ------------------------------
                        """
                    }
                }
            }

            stage('Creating and pushing vecdb') {
                agent {
                    label "docker"
                }
                steps {
                    dir('vecdb'){
                        script {
                            withCredentials([azureServicePrincipal(azure_storage_account)]){
                                sh """
                                    rm -rf ./*
                                    az login --service-principal -u ${AZURE_CLIENT_ID} -p ${AZURE_CLIENT_SECRET} -t ${AZURE_TENANT_ID} 
                                    az account set --subscription ${AZURE_SUBSCRIPTION_ID}
                                    az storage blob download-batch --account-name  ${azure_storage_account} --destination '.' --source '${ragId}' --pattern "*" --no-progress
                                    
                                """
                                }
                            }
                        }
                    dir('code'){
                        git url: "https://gitlab.liquid-reply.net/agentops/agentops_library", credentialsId: "clustervigil_gitlab", branch: "main"
                    }
                    script{
                        
                        sh"""
                            pip install ${vec_db_sdk}==${sdk_version}
                            """
                            if (vec_db_sdk == "chromadb"){
                                SCRIPT_PATH = "${WORKSPACE}/code/RAG/file2chroma.py"
                                sh """ 
                                    python3 ${SCRIPT_PATH} --destionation_path '${ragDir}' --root_path_file '${WORKSPACE}/vecdb/embeddings/${embeddings_model}'
                                    """
                            }
                            else{
                                sh """ 
                                    echo 'SDK not supported"
                                    """                               
                            }
                            

                    }
                    dir('vecdb'){
                        script {
                            withCredentials([azureServicePrincipal(azure_storage_account)]){
                                sh """
                                    az storage blob upload-batch --account-name '${azure_storage_account}' --destination '${ragId}' --destination-path '${embeddings_model}/${vec_db_sdk}/${sdk_version}/${ragDir}/' --source '${WORKSPACE}/vecdb/embeddings/${embeddings_model}/${ragDir}/' --overwrite
                                    az logout
                                    echo "DB creato"  
                                    rm -rf ./*                             
                                """
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
