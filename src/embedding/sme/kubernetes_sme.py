from embedding.chroma import ChromaSme
from injectable import injectable

KUBERNTES_CHROMA_INDEX = "k8sindex"

@injectable(singleton=True)
class KubernetesSme(ChromaSme):

    def __init__(self):
        super().__init__(KUBERNTES_CHROMA_INDEX)
