def PVC_FILE_PATH = null 
def JOB_FILE_PATH = null 

def call(def namespace, def deploymentName, def ragPVC=null, def ragID=null, def promptVersion=null, def agentImage=null, def updateRag = false, newPrompt= false, def ragPath = null) {

    DEPLOYMENT_FILE_PATH = "${WORKSPACE}/deployment/apps/${namespace}/${deploymentName}"
    COMMIT = "Updated with image "+agentImage
    OLD_PVC_RAG = null
    OLD_PVC_PROMPT= null
    OLD_PROMPT_VERSION = null
    OLD_RAGPATH  = null

    echo "[i] Eseguito il clone del repository devops"
    dir("deployment") {
        def repoURL = "https://gitlab.liquid-reply.net/liquid/infra/mgmt-cluster"
        def repoHost = new URL(repoURL).getHost()
        withCredentials([usernamePassword(credentialsId: 'clustervigil_gitlab', passwordVariable: 'JENKINS_PASS', usernameVariable: 'JENKINS_USER')]) {
            // Scrivi .netrc
            writeFile file: "${env.HOME}/.netrc", text: """
                machine ${repoHost}
                login ${JENKINS_USER}
                password ${JENKINS_PASS}
            """
            sh "chmod 600 ${env.HOME}/.netrc"
        }
        git url: repoURL, credentialsId: "clustervigil_gitlab", branch: "main"
        sh "git remote set-url origin ${repoURL}"
        sh "git config --global user.email 'ijenkins@liquid-reply.net'"
        sh "git config --global user.name 'ijenkins'"
        def yaml = readYaml file: DEPLOYMENT_FILE_PATH

        echo "-----------Updating deployment-----------"

        echo "[i] Update image"
        def old_image = yaml.spec.template.spec.containers[0].image
        yaml.spec.template.spec.containers[0].image = agentImage

        echo "[i] Update prompt"
        if(newPrompt){
            COMMIT = COMMIT + ", prompt version "+promptVersion
            def envList = yaml.spec.template.spec.containers[0].env
            def envVar = envList.find { it.name == 'PROMPT_VERSION' }
            if (envVar) {
                envVar.value = promptVersion
            } else {
                envList << [name: 'PROMPT_VERSION', value: promptVersion]
            }
        }
        else{
            echo "[i] Update prompt skipped"
        }

        yaml.spec.template.spec.volumes.each { vol ->
            if (vol.name == 'rag-volume') {
                OLD_PVC_RAG = vol.persistentVolumeClaim.claimName
            }
        }
        yaml.spec.template.spec.containers.each { container ->
            container.volumeMounts.each { vol ->
                if (vol.name == 'rag-volume') {
                    OLD_RAGPATH = vol.subPath
                }
            }
        }
        if(updateRag){
            echo "[i] Update RAG"
            COMMIT = COMMIT+", ragID "+ragID
            yaml.spec.template.spec.volumes.each { vol ->
                if (vol.name == 'rag-volume') {
                    OLD_PVC_RAG = vol.persistentVolumeClaim.claimName
                    vol.persistentVolumeClaim.claimName = ragPVC
                }
            }
            yaml.spec.template.spec.containers.each { container ->
                container.volumeMounts.each { vol ->
                    if (vol.name == 'rag-volume') {
                        OLD_RAGPATH = vol.subPath
                        vol.subPath = ragPath
                    }
                }
            }
        }
        else{
            echo "[i] Update RAG skipped"
        }

        if (old_image != agentImage ||  (updateRag || newPrompt)){
            sh "rm -f ${DEPLOYMENT_FILE_PATH}"
            writeYaml file: DEPLOYMENT_FILE_PATH, data: yaml
            echo "-----------UPDATED YAML-----------"

            sh "cat ${DEPLOYMENT_FILE_PATH}"


            sh "git add ."
            sh "git commit -m '${COMMIT}'"
            sh "git push --set-upstream origin main"

            deployment_Name = yaml.metadata.name

            def updated = false
            def retries = 0
            def maxRetries = 30
            def waitTime = 30

            
            def initialGeneration = sh(script: "kubectl get deployment ${deployment_Name} -n ${namespace} -o=jsonpath='{.metadata.generation}'", returnStdout: true).trim()
            def observedGeneration = sh(script: "kubectl get deployment ${deployment_Name} -n ${namespace} -o=jsonpath='{.status.observedGeneration}'", returnStdout: true).trim()


            while (initialGeneration == observedGeneration && retries < maxRetries) {
                retries++
                echo "Attendere che il deployment venga aggiornato... Tentativo ${retries}/${maxRetries}"
                sleep(waitTime)

                observedGeneration = sh(script: "kubectl get deployment ${deployment_Name} -n ${namespace} -o=jsonpath='{.status.observedGeneration}'", returnStdout: true).trim()
            }

            if (initialGeneration != observedGeneration) {
                echo "Deployment ${deployment_Name} aggiornato con successo!"
            } else {
                error "Il deployment non è stato aggiornato dopo ${maxRetries} tentativi"
            }
            def maxWaitSeconds = 300  
            def checkInterval = 10 
            def waitTime_pod = 0
            def ready = false

            while (waitTime_pod < maxWaitSeconds) {
                def status = sh(script: "kubectl get deployment ${deployment_Name} -n ${namespace} -o json", returnStdout: true).trim()
                def parsed = readJSON text: status

                def desiredReplicas = parsed?.spec?.replicas ?: 0
                def readyReplicas = parsed?.status?.readyReplicas ?: 0

                echo "Replica attese: ${desiredReplicas}, replica pronte: ${readyReplicas}"

                if (desiredReplicas == readyReplicas && desiredReplicas > 0) {
                    echo "Tutti i pod del deployment '${deployment_Name}' sono pronti."
                    ready = true
                    break
                }

                sleep(checkInterval)
                waitTime_pod += checkInterval
                echo "Waited ${waitTime_pod}s/${maxWaitSeconds}s"
            }

            if (!ready) {
                error "Timeout: i pod del deployment '${deploymentName}' non sono pronti dopo ${maxWaitSeconds} secondi"
            }

            // if(updateRag){
            //     sh "kubectl delete pvc ${OLD_PVC_RAG} -n ${namespace}"
            // }
        }
        else{
            sh "echo nothing to update"
        }

    }
    return [old_rag_pvc: OLD_PVC_RAG, old_rag_path: OLD_RAGPATH]
}