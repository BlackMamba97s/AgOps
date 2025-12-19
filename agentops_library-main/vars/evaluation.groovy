def call(def model_endpoint, def langfuse_endopoint, def langfuse_project, def dataset, def agent, def agent_version, def prompt_version, def rag_version, def description ) {
    sleep(5)
    dir("test") {
        git url: "https://gitlab.liquid-reply.net/agentops/agentops_library", credentialsId: "clustervigil_gitlab", branch: "main"
    }
    sh """
        if [ ! -d "${WORKSPACE}/test/evaluation/.deepeval" ]; then
            mkdir -p "${WORKSPACE}/test/evaluation/.deepeval"
        else
            rm -rf "${WORKSPACE}/test/evaluation/.deepeval"/*
        fi
        export DEEPEVAL_HOME="${WORKSPACE}/test/evaluation/.deepeval"
    """
    withCredentials([usernamePassword(credentialsId: 'AgentOps', passwordVariable: 'pass', usernameVariable: 'user')]) {
        def cmd = ["python3", "${WORKSPACE}/test/evaluation/test.py"]

        cmd += ["--agent", agent]
        cmd += ["--agent-description", description]
        cmd += ["--agent-version", agent_version]
        cmd += ["--prompt-version", prompt_version]
        cmd += ["--rag-version", rag_version]
        cmd += ["--dataset", dataset]
        cmd += ["--model", model_endpoint]
        cmd += ["--langfuse-url", langfuse_endopoint]
        cmd += ["--langfuse-public-key", user]
        cmd += ["--langfuse-private-key", pass]

        def status = sh(
            script: cmd.collect { "\"${it}\"" }.join(" "),
            returnStatus: true
        )
       if (status != 0) {
           return 1
       } else {
           return 0
       }
        
    }
}