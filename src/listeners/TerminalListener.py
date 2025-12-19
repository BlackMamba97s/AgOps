

from listeners.AgentListener import AgentListener


class TerminalAgentListener(AgentListener):

    def __init__(self, agent):
        super().__init__(agent)

    def listen(self):
        input_dict = {}
        try:
            while True:
                input_dict["input"] = input("Enter your question: ")
                output = self.agent.invoke(input_dict)
                print(output["output"])
                print("\n\n")

        except KeyboardInterrupt:
            print('interrupted!')