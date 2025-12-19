def call(def namespace, def deploymentName) {

    DEPLOYMENT_FILE_PATH = "${WORKSPACE}/deployment/apps/${namespace}/${deploymentName}"

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
        sh "git config --global user.email 'ijenkins@liquid-reply.net'"
        sh "git config --global user.name 'ijenkins'"
        def yaml = readYaml file: DEPLOYMENT_FILE_PATH


        def old_image = yaml.spec.template.spec.containers[0].image
        def envList = yaml.spec.template.spec.containers[0].env
        def OLD_PROMPT_VERSION = null
        def OLD_PVC_RAG = null


        def envVar = envList.find { it.name == 'PROMPT_VERSION' }
        if (envVar) {
            OLD_PROMPT_VERSION = envVar.value
        } else {
            envList << [name: 'PROMPT_VERSION', value: promptVersion]
        }


        yaml.spec.template.spec.volumes.each { vol ->
            if (vol.name == 'rag-volume') {
                OLD_PVC_RAG = vol.persistentVolumeClaim.claimName
            }
        }

        def elementPVCname = OLD_PVC_RAG.split('\\.').collect { it.trim() }

        def tmp = old_image.split(':').collect { it.trim() }
        def agentVersion = tmp[1]
        def ragId = elementPVCname[1]
        def promptVersion = OLD_PROMPT_VERSION

        return [
            agentVersion  : agentVersion,
            ragId         : ragId,
            promptVersion : promptVersion
        ]

        
    }
}


