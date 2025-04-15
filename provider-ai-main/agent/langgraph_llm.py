from livekit.agents import llm

from livekit.agents.llm.chat_context import ChatContext
from livekit.agents.types import DEFAULT_API_CONNECT_OPTIONS, APIConnectOptions
from langgraph_tool import ChatbotAgent
from langchain_core.messages import AIMessage
import uuid

config = {"configurable": {"thread_id": str(uuid.uuid4())}}
chat_agent = ChatbotAgent(config=config)


class LangGraphLLM(llm.LLM):
    def __init__(
        self,
    ) -> None:
        super().__init__()

    def chat(
        self,
        *,
        chat_ctx: ChatContext,
        conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS,
        fnc_ctx: llm.FunctionContext | None = None,
        temperature: float | None = None,
        n: int | None = 1,
        parallel_tool_calls: bool | None = None,
    ) -> "LangGraphLLMStream":
        return LangGraphLLMStream(
            self,
            chat_ctx=chat_ctx,
        )


class LangGraphLLMStream(llm.LLMStream):
    def __init__(
        self,
        llm: LangGraphLLM,
        chat_ctx: ChatContext,
    ) -> None:
        super().__init__(
            llm,
            chat_ctx=chat_ctx,
            fnc_ctx=None,
            conn_options=DEFAULT_API_CONNECT_OPTIONS,
        )

    async def _run(self) -> None:
        chat_ctx = self._chat_ctx.copy()
        user_msg = chat_ctx.messages.pop()
        print(f"--------------------Assistnat message: {chat_ctx.messages[0].content}")
        print(f"--------------------User message: {user_msg.content}")

        # Call the API
        # response = chat_agent.call_agent(user_msg.content)
        # print(f"--------------------Response: {response}")
        # self._event_ch.send_nowait(
        #     llm.ChatChunk(
        #         request_id="",
        #         choices=[
        #             llm.Choice(
        #                 delta=llm.ChoiceDelta(
        #                     role="assistant",
        #                     content=response,
        #                 )
        #             )
        #         ],
        #     )
        # )
        async for chunk in chat_agent.call_agent(
            chat_ctx.messages[0].content, user_msg.content
        ):
            self._event_ch.send_nowait(
                llm.ChatChunk(
                    request_id="",
                    choices=[
                        llm.Choice(
                            delta=llm.ChoiceDelta(
                                role="assistant",
                                content=chunk["__interrupt__"][0].value,
                            )
                        )
                    ],
                )
            )
