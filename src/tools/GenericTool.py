from langchain_core.tools import Tool

class GenericTool():

    tool = None

    def __init__(self):
        pass

    def getTool(self) -> Tool:
        return self.tool