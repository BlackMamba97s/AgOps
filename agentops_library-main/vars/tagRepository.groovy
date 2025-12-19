def call(def repoURL, def tagVersion, def branch) {
    def modifiedRepoURL = null
    def randomSuffix = UUID.randomUUID().toString() // genera stringa unica
    def repoDir = "msRepo-${randomSuffix}"
    dir(repoDir) {
    
        withCredentials([usernamePassword(credentialsId: 'clustervigil_gitlab', passwordVariable: 'JENKINS_PASS', usernameVariable: 'JENKINS_USER')]) {
            def repoHost = new URL(repoURL).getHost()

            // Scrivi .netrc
            writeFile file: "${env.HOME}/.netrc", text: """
                machine ${repoHost}
                login ${JENKINS_USER}
                password ${JENKINS_PASS}
            """
            sh "chmod 600 ${env.HOME}/.netrc"

            sh """
            git clone ${repoURL}
            git remote set-url origin ${repoURL}
            git fetch 
            git checkout ${branch}
            """
            
            sh "git config --global user.email 'ijenkins@liquid-reply.net'"
            sh "git config --global user.name 'ijenkins'"
            sh """
                git tag -a "${tagVersion}" -m "Adding tag ${tagVersion}"
            """
            sh "git push origin --tags"
            
        }
        
    }
    sh "rm -rf ${WORKSPACE}/${repoDir}"

}