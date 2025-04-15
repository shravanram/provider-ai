from typing import Annotated
from langgraph.prebuilt import ToolNode

from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage
from typing_extensions import TypedDict
from langchain_core.tools import tool
from langgraph.checkpoint.memory import MemorySaver

from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.graph import StateGraph, MessagesState, START, END
from dotenv import load_dotenv
from smtp2go.core import Smtp2goClient
import os
from langchain_core.messages import AIMessage
import json
import psycopg2

if os.path.isfile(".env.local"):
    load_dotenv("/Users/mohanshravan/Coding/provider-ai/agent/.env.local", verbose=True)

from typing import Literal

from langgraph.types import Command, interrupt


class State(TypedDict):
    messages: Annotated[list, add_messages]


class Router(TypedDict):
    """Worker to route to next. If no workers needed, route to FINISH."""

    next: Literal["scheduling_agent", "user_node", "preauth_agent", "FINISH"]
    messages: str


class Router_schedule(TypedDict):
    """Worker to route to next. If no workers needed, route to FINISH."""

    next: Literal["email_node", "user_node"]
    messages: str


class Router_PreAuth(TypedDict):
    """Worker to route to next. If no workers needed, route to FINISH."""

    next: Literal["user_node", "FINISH"]
    messages: str


def read_doctor_schedules():
    """
    Connects to a PostgreSQL database using psycopg2,
    reads all rows from the 'doctor_schedules' table,
    and returns them as a list of dictionaries.
    """
    # 1) Define your connection details
    conn_params = {
        "dbname": "mydatabase",
        "user": "myuser",
        "password": "mypassword",
        "host": "localhost",  # or an IP address / domain
        "port": 5432,
    }

    # 2) Connect to the database
    connection = psycopg2.connect(**conn_params)

    try:
        # 3) Create a cursor
        cursor = connection.cursor()

        # 4) Execute a SQL query
        #    Adjust the fields/columns depending on your actual table definition.
        cursor.execute(
            "SELECT doctor_name, specialty, time_slots FROM doctor_schedules;"
        )

        # 5) Fetch all rows
        rows = cursor.fetchall()

        # 6) Build a list of dicts for convenience
        results = []
        for row in rows:
            doc_schedule = {
                "doctor_name": row[0],
                "specialty": row[1],
                "time_slots": row[
                    2
                ],  # If this is a JSON/JSONB column, row[2] is already a dict/list
            }
            results.append(doc_schedule)

        return results

    finally:
        # 7) Close the connection (and cursor) when done
        cursor.close()
        connection.close()


class ChatbotAgent:
    """Encapsulates chatbot functionality, tool management, and state transitions."""

    def __init__(self, config: dict):
        """Initializes the chatbot agent with tools and state graph."""
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.smtp_api_key = os.getenv("SMTP2GO_API_KEY")
        self.graph = self.init_graph()
        self.config = config

    @tool
    def send_email(
        email: Annotated[str, "Email ID of the user"],
        subject: Annotated[
            str, "Main subject of the email: Doctors appointment confirmation"
        ],
        message: Annotated[
            str,
            "Message containing necessary details like Patient's name, doctor's name, appointment date, and time.",
        ],
    ) -> str:
        """Call to send an email."""

        print(f"Sending email to user: {email}")
        print(f"Subject: {subject}")
        print(f"Message: {message}")

        smtp2go_client = Smtp2goClient(api_key=os.getenv("SMTP2GO_API_KEY"))
        payload = {
            "sender": "mohan.shravan@bcg.com",
            "recipients": [email],
            "subject": subject,
            "text": message,
        }
        response = smtp2go_client.send(**payload)
        return "Success" if response.status_code == 200 else "Failed"

    def email_agent(self, state: State) -> Command[Literal["scheduling_agent"]]:
        "sends email after getting all the details required"
        from langgraph.prebuilt import create_react_agent

        llm = ChatOpenAI(model="gpt-4o")
        agent = create_react_agent(
            llm,
            tools=[self.send_email],
            prompt="""You send confirmation email with the necessary details you have""",
        )
        response = agent.invoke(state)

        return Command(
            goto="scheduling_agent", update={"messages": response["messages"]}
        )

    def supervisor_chatbot(
        self, state: State
    ) -> Command[Literal["scheduling_agent", "preauth_agent", "user_node", "__end__"]]:
        """Handles conversation logic using LLM and tools."""
        llm = ChatOpenAI(model="gpt-4o", api_key=self.api_key)

        messages = (
            [
                {
                    "role": "system",
                    "content": """You are a supervisor at the doctor's office. Your interface with users will be voice. Keep the interaction conversational.
                    Your main task is to route the conversation to the appropriate agent based on the user's request.
                    If you need additional information to route the conversation, you can ask the user for it. But once you know the user's intent, route the conversation to the appropriate agent and do not ask any additional questions. 
                    You are the supervisor of many tools you have access to:
                    scheduling_agent: Agent that helps to schedule doctor's appointment and sends an email to the patient.
                    preauth_agent : Agent that verifies if the the patient is preauthorized to undergo a surgery. Route to this agent if the intent is preauth. Dont ask any questions.
                    user_node: This is the user itself and not an expert agent. This can be used to seek additional information from the user or just respond back to the user. Use this agent to interact with the user at any point and to ask if there is anything you can help with.
                    FINISH : Once the task is complete, use this.
                    Structured Output: Ensure all responses are in JSON format with the keys:
                        - `next`: The next tool to route to (`scheduling_agent`, `user_node` ,`preauth_agent`, `FINISH`).
                        - `messages`: Any messages to send to the user.
                    """,
                },
            ]
            + state["messages"]
        )

        response = llm.with_structured_output(Router).invoke(messages)
        goto = response["next"]
        if goto == "FINISH":
            return Command(goto=END, update={"messages": response["messages"]})
        return Command(goto=goto, update={"messages": response["messages"]})

    def human_input(
        self, state: State, config
    ) -> Command[Literal["scheduling_agent", "preauth_agent", "supervisor_chatbot"]]:

        user_input = interrupt(value=state["messages"][-1].content)

        # identify the last active agent
        # (the last active node before returning to human)
        langgraph_triggers = config["metadata"]["langgraph_triggers"]
        if len(langgraph_triggers) != 1:
            raise AssertionError("Expected exactly 1 trigger in human node")

        active_agent = langgraph_triggers[0].split(":")[1]

        return Command(
            update={
                "messages": [
                    {
                        "role": "human",
                        "content": user_input,
                    }
                ]
            },
            goto=active_agent,
        )

    def scheduling_agent(
        self, state: State
    ) -> Command[Literal["user_node", "email_node", "__end__"]]:
        """Agent that books doctor's appointment."""
        # from langgraph.graph import create_react_agent
        from langgraph.prebuilt import create_react_agent

        json_string = json.dumps(read_doctor_schedules())
        llm = ChatOpenAI(model="gpt-4o", api_key=self.api_key)
        # read json file from data.json
        # with open("../store_schedule/data.json", "r") as f:
        #     # 2) Load JSON content into a Python dictionary (or list)
        #     data = json.load(f)
        # json_string = json.dumps(data, indent=2)
        messages = (
            [
                {
                    "role": "system",
                    "content": f"""
                    You are a front desk voice assistant designed to schedule appointments for patients through a conversational interface. Your interaction should be friendly and avoid robotic responses or numbered lists.

                    # Task

                    - Engage with patients seeking to schedule a doctor's appointment.
                    - Ensure all interactions are conversational.
                    - Check with the patient if further assistance is required after scheduling.

                    # Main Tasks

                    - **Gather Information**: 
                    - Ask for the required details to book an appointment, including the doctor's name.
                    
                    - **Verify Email**: 
                    - Confirm the patient's email ID before sending a confirmation email.

                    - **Send Confirmation**:
                    - Notify the user once the booking is complete and confirm that an email has been sent using the `user_agent`.

                    # Appointment Scheduling Process

                    1. **Request Doctor's Name**: Inquire the patient for their preferred doctor's name.
                    2. **Check Availability**:
                    - Consult the `DOCTOR_DETAIL` section to confirm the doctor's availability.
                    - Communicate available time slots conversationally: e.g., "We have openings on April 22nd and April 28th."
                    - If the desired doctor is unavailable, suggest an alternate doctor.
                    3. **Confirm Details**:
                    - If a suitable time is chosen, request the patient's email for confirmation.
                    - If no slots are suitable, inform the patient that you'll follow up when more slots become available.

                    # Available Tools

                    - **user_agent**: Use this to interact with the user, gather necessary information, or provide completion confirmation. Thank the user once the task is complete.
                    - **email_agent**: Employ this tool to send booking confirmation emails once the required details and email ID are verified.
                    ##DOCTOR_DETAIL##
                    ```
                    {{data}}
                    ```
                    ##
                    
                    
                    Structured Output: Ensure all responses are in JSON format with the keys:
                        - `next`: The next tool to route to (`user_node`, `email_node` ).
                        - `messages`: Any messages to send to the user.
                        """.format(
                        data=json_string
                    ),
                },
            ]
            + state["messages"]
        )

        response = llm.with_structured_output(Router_schedule).invoke(messages)
        if response["next"] == "user_node":
            return Command(
                update={"messages": response["messages"]},
                goto="user_node",
            )
        elif response["next"] == "email_node":
            return Command(
                update={"messages": response["messages"]},
                goto="email_node",
            )
        elif response["next"] == "FINISH":
            return Command(
                update={"messages": response["messages"]},
                goto=END,
            )

    def preauth_agent(self, state: State) -> Command[
        Literal[
            "user_node",
            "__end__",
        ]
    ]:
        """Agent that verifies if the patient's authorization is valid."""
        # from langgraph.graph import create_react_agent
        llm = ChatOpenAI(model="gpt-4o", api_key=self.api_key)

        messages = (
            [
                {
                    "role": "system",
                    "content": """You are a nurse working at a doctor's office who calls the insurance office to verify insurance coverage and if the patient is preauthorization for a procedure. 
                    Your interface with users will be voice. Keep the interaction conversational. The responses should be short and wait for questions to be asked about the patient.  
                    Provide any necessary patient details when asked.
                    The patient details are as follows:
                    Name: John Greene
                    Date of birth: 06/22/1978
                    Insurance ID: 987654321
                    Procedure to be performed: 
                    Total knee replacement - CPT code 27447
                    Diagnosis - ICD-10 M17.11 
                    
                    If the insurance office says patient is already preauthorized for the procedure, thank them and end the call.
                    If patient is not preauthorized, ask the insurance office where to send the documents to (for example, online portals or fax) for the request.

                    Once the task is complete, thank the insurance office and end the call.
                    You have access to the following agents:
                    `user_node` : This is not an expert but the insurance agent you called. Use this when you need to interact with the insurance office, to ask or provide any additional information asked or just to thank the agent and end the call. 
                    `FINISH` : After you thank the user and if the user has no more questions and once the given task is complete, use this.
                    
                    Structured Output: Ensure all responses are in JSON format with the keys:
                        - `next`: The next tool to route to (`user_node`, `FINISH`).
                        - `messages`: Any messages to send to the user.
                    """,
                },
            ]
            + state["messages"]
        )

        response = llm.with_structured_output(Router_PreAuth).invoke(messages)
        if response["next"] == "user_node":
            return Command(
                update={"messages": response["messages"]},
                goto="user_node",
            )
        elif response["next"] == "FINISH":
            return Command(
                update={"messages": response["messages"]},
                goto=END,
            )

        goto = response["next"]
        return Command(goto=goto, update={"messages": response["messages"]})

    async def call_agent(self, assistant_first_message: str, input_text: str):
        """Runs the chatbot agent for a given input."""
        state = self.graph.get_state(self.config)
        if any(task.interrupts for task in state.tasks):
            async for event in self.graph.astream(
                Command(resume=input_text), config=self.config, stream_mode="updates"
            ):
                if "__interrupt__" in event:
                    yield event

        else:
            async for event in self.graph.astream(
                {
                    "messages": [
                        {
                            "role": "ai",
                            "content": assistant_first_message,
                        },
                        {"role": "user", "content": input_text},
                    ]
                },
                self.config,
                stream_mode="updates",
            ):
                if "__interrupt__" in event:
                    yield event

    def init_graph(self):
        """Initializes the state graph for managing chatbot interactions."""
        graph_builder = StateGraph(State)
        graph_builder.add_edge(START, "supervisor_chatbot")
        graph_builder.add_node("supervisor_chatbot", self.supervisor_chatbot)
        graph_builder.add_node("scheduling_agent", self.scheduling_agent)
        graph_builder.add_node("preauth_agent", self.preauth_agent)
        graph_builder.add_node("user_node", self.human_input)
        graph_builder.add_node("email_node", self.email_agent)

        checkpointer = MemorySaver()
        return graph_builder.compile(checkpointer=checkpointer)
