from embedding.chroma import ChromaSme
from injectable import injectable

KUBEPYTHON_CHROMA_INDEX = "kubepythonindex"

 
@injectable(singleton=True)
class KubePythonSme(ChromaSme):

    def __init__(self):
        super().__init__(KUBEPYTHON_CHROMA_INDEX)
