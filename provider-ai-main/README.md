# Provider-AI

This application intends to solve the following key pain points:
1. Patient scheduling system
2. Nurses understanding if the patient is pre-authorized for a procedure







![image (4)](https://github.com/user-attachments/assets/fcdea7f7-70b7-4c64-ad88-683516bf8506)



Key tech used: LangGraph, LiveKit


## Installation

### 1. Install LiveKit CLI and Authenticate with Cloud
Refer to the [LiveKit CLI Setup](https://docs.livekit.io/home/cli/cli-setup/) for installation and authentication instructions.

Follow these steps only if you have not setup the trunks before on your livekit project

- setup inbound trunk (step 3)
https://docs.livekit.io/agents/quickstarts/inbound-calls/

- setup outbound trunk

https://docs.livekit.io/agents/quickstarts/outbound-calls/


### 2. Create a Virtual Environment and Activate
```sh
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Required Packages
Ensure you run this command from the root directory:
```sh
poetry install
```

### 4. Configure Environment Variables
Create a copy of `.env.example` and rename it to `.env.local`. Update it with the required environment variables.

---

## Inbound Call Setup

### 1. Setup PostgreSQL using Docker
Run the following command to start a PostgreSQL container:
```sh
docker run --name my-postgres \
    -e POSTGRES_USER=myuser \
    -e POSTGRES_PASSWORD=mypassword \
    -e POSTGRES_DB=mydatabase \
    -p 5434:5432 \
    -d postgres:14
```

### 2. Run the Flask Application
```sh
python provider-ai/store_schedule/app.py
```
Access the application at: [http://127.0.0.1:5000](http://127.0.0.1:5000) and enter doctor details.

### 3. Run the Agent
```sh
cd agent
python inbound_call.py dev  
```

### 4. Make an Inbound Call
Dial the **Twilio number**: `+1 844 861 0695` to book an appointment.

---

## Outbound Call Setup

### 1. Run the Agent
```sh
cd agent
python outbound_caller_agent.py
```

### 2. Dispatch the Call
```sh
lk dispatch create \
  --new-room \
  --agent-name outbound-caller \
  --metadata '<verified phone number on twilio>'
```

