def PVC_FILE_PATH = null 
def JOB_FILE_PATH = null 

def call(def ragId = null, def ragDir = null, def ragSize = null, def namespace = null, def pvcNameId = null, azure_storage_account=null) {

    PVC_FILE_PATH = "${WORKSPACE}/devops/manifests/pvc-rag.yaml"
    JOB_FILE_PATH = "${WORKSPACE}/devops/manifests/job-azure-rag.yaml"
    SECRET_PATH = "${WORKSPACE}/devops/manifests/secret-blob-azure.yaml"

    echo "[i] Eseguito il clone del repository devops"
    dir("devops") {
        git url: "https://gitlab.liquid-reply.net/agentops/agentops_library", credentialsId: "clustervigil_gitlab", branch: "main"
    }

    echo "[i] Replace dei token"
    withCredentials([azureServicePrincipal(azure_storage_account)]){
        sh """
            sed -i "s/###PVCNAMEID###/rag-pvc.${ragId}.${pvcNameId}/g" "${PVC_FILE_PATH}"
            sed -i "s/###NAMESPACE###/${namespace}/g" "${PVC_FILE_PATH}"
            sed -i "s/###STORAGESIZE###/${ragSize}/g" "${PVC_FILE_PATH}"

            sed -i "s/###NAMESPACE###/${namespace}/g" "${JOB_FILE_PATH}"
            sed -i "s/###CONTAINER###/${ragId}/g" "${JOB_FILE_PATH}"
            sed -i "s|###DIR###|${ragDir}|g" "${JOB_FILE_PATH}"
            sed -i "s/###PVCNAMEID###/rag-pvc.${ragId}.${pvcNameId}/g" "${JOB_FILE_PATH}"

            AZURE_CLIENT_ID_B64=\$(echo -n "${AZURE_CLIENT_ID}" | base64)
            AZURE_CLIENT_SECRET_B64=\$(echo -n "${AZURE_CLIENT_SECRET}" | base64)
            AZURE_SUBSCRIPTION_ID_B64=\$(echo -n "${AZURE_SUBSCRIPTION_ID}" | base64)
            AZURE_TENANT_ID_B64=\$(echo -n "${AZURE_TENANT_ID}" | base64)
            AZURE_STORAGE_ACCOUNT_B64=\$(echo -n "${azure_storage_account}" | base64)

            sed -i "s|###AZURE_CLIENT_ID###|\${AZURE_CLIENT_ID_B64}|g" "${SECRET_PATH}"
            sed -i "s|###AZURE_CLIENT_SECRET###|\${AZURE_CLIENT_SECRET_B64}|g" "${SECRET_PATH}"
            sed -i "s|###AZURE_SUBSCRIPTION_ID###|\${AZURE_SUBSCRIPTION_ID_B64}|g" "${SECRET_PATH}"
            sed -i "s|###AZURE_TENANT_ID###|\${AZURE_TENANT_ID_B64}|g" "${SECRET_PATH}"
            sed -i "s|###AZURE_STORAGE_ACCOUNT###|\${AZURE_STORAGE_ACCOUNT_B64}|g" "${SECRET_PATH}"

            cat ${PVC_FILE_PATH}
            cat ${JOB_FILE_PATH}
            kubectl apply -f ${SECRET_PATH} -n ${namespace}
            kubectl apply -f ${PVC_FILE_PATH}
            kubectl apply -f ${JOB_FILE_PATH}
            sleep 3
            kubectl --namespace ${namespace} wait --for=condition=complete --timeout=600s job/rag-job
            kubectl delete -f ${JOB_FILE_PATH}
            kubectl delete -f ${SECRET_PATH} -n ${namespace}
        """
    }
}