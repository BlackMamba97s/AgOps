from langchain.tools.retriever import create_retriever_tool
from injectable import Autowired, autowired
from embedding.sme.kubernetes_sme import KubernetesSme
from tools.GenericTool import GenericTool

class KubernetesSmeTool(GenericTool):

    @autowired
    def __init__(self, sme: Autowired(KubernetesSme)):
        self.tool = create_retriever_tool(
            retriever=sme.getDb().as_retriever(search_kwargs={'k': 5}),
            name="KubernetesSme",
            description="""
                This tool can retrieve information on how kubernetes work in general. \
                It does not give you information about the item present in a specific cluster, this is just documentation.
                You can use this tool to be more specific when using the KubePythonSme tool.

                I suggest you to first understand what information do you need every time before generate the code.
            """
        )
