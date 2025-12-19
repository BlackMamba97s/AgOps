from langchain.tools.retriever import create_retriever_tool
from injectable import Autowired, autowired
from embedding.sme.kubepython_sme import KubePythonSme
from tools.GenericTool import GenericTool

class KubePythonSmeTool(GenericTool):

    @autowired
    def __init__(self, sme: Autowired(KubePythonSme)):
        self.tool = create_retriever_tool(
            retriever=sme.getDb().as_retriever(search_kwargs={'k': 5}),
            name="KubePythonSme",
            description="""
                This tool can retrieve information on how using the python library to retrieve the information you want from the kubernetes cluster.
            """
        )
