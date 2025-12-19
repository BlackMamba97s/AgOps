def call(body) {
    // evaluate the body block, and collect configuration into the object
    def pipelineParams = [:]
    body.resolveStrategy = Closure.DELEGATE_FIRST
    body.delegate = pipelineParams
    body()

    
    def MICROSERVICE_NAME = null
    def SOURCE_IMAGE_TAG = null
    def DEPLOYMENT_FILE_NAME = null
    def TEST_ENDOPOINT = null
   
    def SLAVE_LABEL = 'docker'

    //def webhook = null
    def agentVersion = null
    def AGENT_DESCRIPTION = null
    def ragId = null
    def ragDir = null
    def ragSize = null
    def namespace = null
    def appRepo = null
    def promptVersion = null
    def langfuse_endpoint = null
    def test = null
    def thresholds = null
    def datasets = null
    def langfuse_project = null
    def azure_storage_account = null
    def deploy_update_required= true
    def RAG_PVC = null
    def agentVersion_check = null
    def newRag = null
    def newPrompt = null
    def forceTag_check = false

    def agentVersion_current = null
    def ragId_current = null
    def promptVersion_current = null 
    def current_pvc = null
    def current_rag_path = null
    def executed_update = false
    def executed_fallback = false

    def sdk_version = null
    def vec_db_sdk = null
    def embeddings_model = null

    
    
    def infoMap = null
    
    pipeline {
        agent {
            label "${SLAVE_LABEL}"
        }
        parameters {
            booleanParam(name: 'onlyTest', defaultValue: 'false', description: "Vuoi eseguire solo i test?")
            booleanParam(name: 'forceTag', defaultValue: 'false', description: "Vuoi forzare la generazione del tag in caso di test? Il tag verrà generato solo se non esistente")
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
                        DEPLOYMENT_FILE_NAME = infoMap.deployment_filename_prod
                        TEST_ENDOPOINT = infoMap.prod_endpoint
                        MICROSERVICE_NAME = infoMap.microservice_name
                        AGENT_DESCRIPTION = infoMap.agent_description
                        ragDir = infoMap.ragDir
                        ragSize = infoMap.ragSize
                        namespace = infoMap.namespace_prod
                        appRepo = infoMap.appRepo
                        langfuse_endpoint = infoMap.langfuse_endpoint
                        azure_storage_account = infoMap.azure_storage_account
                        test = infoMap.test
                        thresholds = infoMap.thresholds
                        datasets = infoMap.datasets
                        langfuse_project = infoMap.langfuse_project


                        agentVersion_check = params.agentVersion

                        information = agentVersion_check.split('_')
                        agentVersion = information[0].substring(1)
                        ragId = information[1]
                        promptVersion = information[2]

                        sdk_version =  infoMap.sdk_version
                        vec_db_sdk =  infoMap.vec_db_sdk   
                        embeddings_model = infoMap.embeddings_model


                    }
                }
            }

            stage('Checking components to update'){
                steps{
                    dir("check"){
                        script{

                            //checking if the combination was already deployed if not rollback
                            if (! params.agentVersion.startsWith("V")){
                                withCredentials([usernamePassword(credentialsId: 'clustervigil_gitlab', usernameVariable: 'GIT_USER', passwordVariable: 'GIT_PASS')]) {
                                    def versionTag = "V"+agentVersion+"_"+ragId+"_"+promptVersion
                                    def repoHost = new URL(appRepo).getHost()

                                    // Scrivi .netrc
                                    writeFile file: "${env.HOME}/.netrc", text: """
                                        machine ${repoHost}
                                        login ${GIT_USER}
                                        password ${GIT_PASS}
                                    """
                                    sh "chmod 600 ${env.HOME}/.netrc"

                                    git url: appRepo, credentialsId: "clustervigil_gitlab", branch: "main"
                                    def tagExists = sh(
                                        script: """
                                            git ls-remote --tags origin refs/tags/${versionTag} | grep ${versionTag} > /dev/null
                                        """,
                                        returnStatus: true
                                    )
                                    if (tagExists == 0) {
                                        echo "Il tag '${versionTag}' esiste già nel repository. Quindi la combinazione è già stata usata in prod"
                                        echo "Questo eguivale ad aver selezionato agentVersion = ${versionTag}"
                                        agentVersion_check = versionTag
                                    }
                                }
                            }
                        }
                    }
                    script {
                        def deployment_info = retrieveInformation(namespace, DEPLOYMENT_FILE_NAME)
                        agentVersion_current = deployment_info.agentVersion
                        ragId_current = deployment_info.ragId
                        promptVersion_current = deployment_info.promptVersion
                        operation = "update"

                        if (params.onlyTest == true){ //only test to execute
                            echo """Executing only test, input parameters will be ignored"""
                            agentVersion = agentVersion_current
                            ragId = ragId_current
                            promptVersion = promptVersion_current
                            deploy_update_required= false
                            operation = "test"
                            newPrompt = false
                            newRag = false
                        }
                        else if (agentVersion_check.startsWith("V") ){
                            echo """Selected version ${agentVersion_check}. Rollback required."""
                            information = agentVersion_check.split('_')
                            agentVersion = information[0].substring(1)
                            ragId = information[1]
                            promptVersion = information[2]
                            echo """Input ragID and promptVersion ingnored, retrieved from agent version"""
                            operation = "rollback"
                        }

                        else if (agentVersion_check.startsWith("R") ){
                            echo """Selected version ${agentVersion_check}. Update required."""
                            information = agentVersion_check.split('_')
                            agentVersion = information[0].substring(1)
                            ragId = information[1]
                            promptVersion = information[2]
                            echo """Input ragID and promptVersion ingnored, retrieved from agent version"""
                            operation = "update"
                        }

                        if (agentVersion_current == agentVersion && params.onlyTest == false){
                            echo """Agent code will not be ${operation} (current deployed version = selected version)"""
                        }
                        else if (params.onlyTest == false){
                            echo """Agent code needs to be ${operation} """
                        }

                        if (params.onlyTest == false){
                            if(ragId_current == ragId){
                                echo """RAG will not be ${operation} (current deployed version = selected version)"""
                                newRag = false
                            }
                            else{
                                echo """RAG needs to be ${operation} """
                                newRag = true
                            }
                        }
                    
                        if (params.onlyTest == false){
                            if(promptVersion_current == promptVersion){
                                echo """Prompt will not be ${operation} (current deployed version = selected version)"""
                                newPrompt = false
                            }
                            else{
                                echo """Prompt needs to be ${operation} """
                                newPrompt = true
                            }
                           
                        }
                        if (params.forceTag == true && params.onlyTest == true){
                            withCredentials([usernamePassword(credentialsId: 'clustervigil_gitlab', usernameVariable: 'GIT_USER', passwordVariable: 'GIT_PASS')]) {
                                def versionAgregated="V"+agentVersion+"_"+ragId+"_"+promptVersion
                                def tagExists = sh(
                                    script: """
                                        git ls-remote --tags origin refs/tags/${versionAgregated} | grep ${versionAgregated} > /dev/null
                                    """,
                                    returnStatus: true)
                                if (!tagExists){
                                    forceTag_check = true
                                }
                                else{
                                    echo "Tag already exist: forceTag ignored"
                                }
                            }
                        }

                        if (agentVersion_current == agentVersion && ragId_current == ragId && promptVersion_current == promptVersion){
                            deploy_update_required = false
                        }
                        
                        echo """
                            ------SCHEDULED OPERATIONS -----
                            TYPE:               ${operation}
                            UPDATE AGENT:       ${!(agentVersion_current == agentVersion)}
                            UPDATE RAG:         ${!(ragId == ragId_current)}
                            UPDATE PROMPT:      ${!(promptVersion_current == promptVersion)}
                            EXECUTE TEST:       ${(agentVersion_check.startsWith("R") && deploy_update_required==true) || params.onlyTest == true}
                            GENERATE NEW TAG:   ${agentVersion_check.startsWith("R") && params.onlyTest == false && deploy_update_required==true || forceTag_check == true}
                            TAG TO GENERATE:    ${"V"+agentVersion+"_"+ragId+"_"+promptVersion}
                            ------------------------------
                        """
                    }
                }
            }

            stage('Agent information') {
                steps {
                    script {
                        echo """
                            ------------ INFO ------------
                            AGENT SOURCE:       ${agentVersion}
                            RAG ID:             ${ragId}
                            RAG DIR:            ${ragDir}
                            RAG SIZE:           ${ragSize}
                            NAMESPACE:          ${namespace}
                            CURRENT BRANCH:     ${env.currentBranch}
                            APP REPO:           ${appRepo}
                            PROMPT VERSION:     ${promptVersion}
                            LANGFUSE ENDPOINT:  ${langfuse_endpoint}
                            AZURE STORAGE:      ${azure_storage_account}
                            DATASET             ${datasets}
                            LANGFUSE PROJECT    ${langfuse_project}
                            ------------------------------
                        """
                    }
                }
            }

            stage('Load RAG') {
                when { expression { newRag == true && params.onlyTest == false && ragId_current != ragId} }
                agent {
                    label "${SLAVE_LABEL}"
                }
                steps {
                    script {
                        ansiColor('xterm') {
                            echo "[i] Start: Create PVC Stage"
                            pvcNameId = sh(returnStdout: true, script: "openssl rand -hex 4").trim()
                            RAG_PVC = "rag-pvc.${ragId}.${pvcNameId}"
                            echo "[i] PVC NAME: rag-pvc-${pvcNameId}"
                            ragPath = embeddings_model+"/"+vec_db_sdk+"/"+sdk_version+"/"+ragDir
                            createRAG(ragId, ragPath, ragSize, namespace, pvcNameId, azure_storage_account)
                        }
                    }
                }
            }
            stage('Update deployment') {
                when { expression {params.onlyTest == false && deploy_update_required==true} }
                agent {
                    label "${SLAVE_LABEL}"
                }
                steps {
                    script {
                        ansiColor('xterm') {
                            def agentImage = "registry.liquid-reply.net/agentops/"+MICROSERVICE_NAME+":"+agentVersion
                            def ragPath = embeddings_model+"/"+vec_db_sdk+"/"+sdk_version+"/"+ragDir
                            def returned_map = updateDeployment_langfuse(namespace, DEPLOYMENT_FILE_NAME, RAG_PVC, ragId, promptVersion, agentImage, newRag, newPrompt, ragPath)
                            current_pvc = returned_map.old_rag_pvc
                            current_rag_path = returned_map.old_rag_path
                            executed_update = true
                        }
                    }
                }
            }



            stage('Test agent') {
                when {expression {(agentVersion_check.startsWith("R") && deploy_update_required==true) || params.onlyTest == true}}
                agent {
                    label "${SLAVE_LABEL}"
                }
                steps {
                    script {
                        def returned_status = evaluation(TEST_ENDOPOINT, langfuse_endpoint, langfuse_project, datasets ,MICROSERVICE_NAME, agentVersion, promptVersion, ragId, AGENT_DESCRIPTION)
                        if (returned_status != 0) {
                            echo "❌ Lo script è terminato con codice ${returned_status}"
                            if (agentVersion_check.startsWith("R") && deploy_update_required==true){
                                def agentImage_rollback = "registry.liquid-reply.net/agentops/"+MICROSERVICE_NAME+":"+agentVersion_current
                                def returned_map = updateDeployment_langfuse(namespace, DEPLOYMENT_FILE_NAME, current_pvc, ragId_current, promptVersion_current, agentImage_rollback, newRag, newPrompt,current_rag_path)
                                sh "kubectl delete pvc ${RAG_PVC} -n ${namespace}"
                                executed_fallback = true
                            }
                            error("Test falliti. Interrompo la pipeline.")
                        } else {
                            echo "✅ Evaluation terminata con successo."
                        }
                    }
                    
                }
            }

            stage('Tag repository') {
                when {expression {agentVersion_check.startsWith("R") && params.onlyTest == false && deploy_update_required==true || forceTag_check == true}}
                agent {
                    label "${SLAVE_LABEL}"
                }
                steps {
                    script {
                        def versionTag = "V"+agentVersion+"_"+ragId+"_"+promptVersion
                        tagRepository(appRepo, versionTag, agentVersion)
                    }
                    
                }
            }
        }

        post {
             always {
                script{
                    if (executed_update && params.onlyTest == false && ragId_current != ragId && newRag == true && !executed_fallback){
                        sh "kubectl delete pvc ${current_pvc} -n ${namespace}"
                    }
                }
                 deleteDir()
            }     
        }
    }
}
