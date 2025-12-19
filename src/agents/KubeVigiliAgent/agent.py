from langchain.agents import create_openai_tools_agent
from agents.KubeVigiliAgent.prompt3 import get_prompt
from llm.llm_creator import create_new_llm
from langchain.agents import AgentExecutor
from injectable import injectable
from langchain.memory import ConversationBufferWindowMemory

from tools.kubernetes_sme.tool import KubernetesSmeTool
from langchain.schema.runnable import RunnableConfig

from typing import Optional, Any, Literal, Sequence

class KubeVigilAgent():

    agent_executor = None

    def __init__(self) -> None:
        try:
            tools = [
                KubernetesSmeTool().getTool()
            ]

            self.agent = create_openai_tools_agent(
                create_new_llm(),
                tools,
                get_prompt()
            )
        
            self.agent_executor = AgentExecutor(
                agent   = self.agent,
                tools   = tools,
                verbose = True,
                handle_parsing_errors = True,
                #callback_manager= CallbackManager([FormatOutput()]),
                memory = ConversationBufferWindowMemory(k=5, output_key="output",memory_key="chat_history",return_messages=True)
                )
        except Exception as e:
            print(e)


    def invoke(self, input):
        return self.agent_executor.invoke(input)

    def get_agent(self):
        return self.agent_executor

    async def astream(self, input,config=RunnableConfig(callbacks=None)):
        return self.agent_executor.astream(input,config=config)

    async def istream(self, input, config=None):
        return self.agent_executor.astream(input,config=config)
    
    def get_input_schema(self,config=None):
        return self.agent.get_input_schema(config=config)
    
    def get_output_schema(self,config=None):
        return self.agent.get_output_schema(config=config)
    
    def config_schema(self,include=None):
        return self.agent.config_schema(include=include)
    
    def with_config(self,config):
        return self.agent.with_config(config=config)
    
    def astream_log(self,input: Any, config: Optional[RunnableConfig] = None, *, diff: Literal[True] = 'True', include_names: Optional[Sequence[str]] = 'None', include_types: Optional[Sequence[str]] = 'None', include_tags: Optional[Sequence[str]] = 'None', exclude_names: Optional[Sequence[str]] = 'None', exclude_types: Optional[Sequence[str]] = 'None', exclude_tags: Optional[Sequence[str]] = 'None', **kwargs: Optional[Any]):
        
        return self.agent_executor.astream_log(input = input, config = config,
                          diff= diff, include_names = include_names, 
                          include_types = include_types , include_tags = include_tags, 
                          exclude_names = exclude_names , exclude_types = exclude_types, 
                          exclude_tags = exclude_tags, **kwargs)
