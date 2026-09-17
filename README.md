## :dart: About

**RAG AI-Agent** is an intelligent question-answering system built on Retrieval-Augmented Generation (RAG) technology. This project is a **LangGraph-powered refactoring** of the original [RAG-Ai-Agent](https://github.com/romanyn36/RAG-AI-Agent) by [romanyn36](https://github.com/romanyn36).

### Key Refactoring Highlights

- **Agent Architecture**: Replaced LangChain's `ZERO_SHOT_REACT_DESCRIPTION` agent with **LangGraph `create_react_agent`** StateGraph architecture, enabling structured tool orchestration and conditional execution
- **Streaming Output**: Implemented **Server-Sent Events (SSE)** for real-time, token-by-token streaming responses with a typewriter effect on the frontend
- **Reasoning Visualization**: Real-time capture of tool call lifecycles (`step_start` / `step_end`) rendered as an expandable reasoning steps panel
- **Multi-turn Memory**: Integrated LangGraph `MemorySaver` + `thread_id` for persistent cross-turn conversation context
- **Tool Redesign**: Removed geo-blocked DuckDuckGo search; added `retrieve` (knowledge base), `calculator`, and `get_current_time` tools via `@tool` decorator
- **File Upload Pipeline**: Upload → auto-index to ChromaDB → stream-answer in a single request

The system enables users to upload documents (PDFs, TXTs, DOCX), which are semantically parsed, embedded, and indexed. When a user asks a question, the Agent retrieves relevant context from ChromaDB and generates contextual responses using OpenAI models.

---

## :sparkles: Features

### **Core Capabilities:**
- **Document Processing:** Upload and process PDF, TXT, and DOCX files
- **Semantic Search:** Find relevant information within your documents using natural language queries
- **RAG-based Responses:** Generate contextual answers by combining retrieved information with AI capabilities
- **Chat Interface:** Intuitive conversation-based UI with chat history management (rename, delete, and save conversations)

### **Agent Mode:**
- **LangGraph StateGraph Architecture:** Structured agent execution with tool-calling loops
- **Step-by-step Reasoning:** Real-time visualization of the agent's thought process and tool invocations
- **Tool Integration:** `retrieve` (knowledge base search), `calculator` (math expressions), `get_current_time` (date/time)
- **Transparent Decision Making:** See exactly how the agent formulates responses via the reasoning panel

### **Streaming & Real-time:**
- **SSE Streaming:** Token-by-token response delivery with typewriter effect
- **Live Reasoning Updates:** Tool calls and results displayed in real-time as the agent works

### **File Management:**
- **Document Upload:** Upload documents directly in chat conversations
- **Vector Storage:** Efficient retrieval using semantic vector embeddings(ChromaDB)
- **Context Preservation:** Documents are linked to specific conversations

### **Chat Features:**
- **Chat History:** Save and load conversation history
- **Chat Management:** Create, rename and delete conversations
- **Multi-turn Dialogue:** MemorySaver-powered context retention across conversation turns
- **User-friendly Interface:** Clean, responsive design with intuitive controls
- **Dark Mode:** Toggle between light and dark themes for better readability

---

## :rocket: Technologies

The following tools and frameworks were used in this project:

- **Backend:**
  - [FastAPI](https://fastapi.tiangolo.com/) - Modern, high-performance web framework
  - [LangGraph](https://langchain.com/langgraph) - Agent orchestration framework (StateGraph)
  - [LangChain](https://langchain.com/) - LLM application framework
  - [ChromaDB](https://www.trychroma.com/) - Vector database for embeddings
  - [SQLite](https://www.sqlite.org/) - Chat history storage
  - [OpenAI](https://openai.com/) - LLM & embedding models (via API proxy)
  - [SQLAlchemy](https://www.sqlalchemy.org/) - ORM
  

- **Frontend:**
  - [React](https://reactjs.org/) - UI library
  - [React Bootstrap](https://react-bootstrap.github.io/) - UI components
  - [React Router](https://reactrouter.com/) - Routing
  - [Axios](https://axios-http.com/) - HTTP client
  - [React Icons](https://react-icons.github.io/react-icons/) - Icons
  - [React Toastify](https://fkhadra.github.io/react-toastify/) - Notifications
  - [Vite](https://vitejs.dev/) - Build tool

- **Document Processing:**
  - [PyPDF](https://pypdf2.readthedocs.io/) - PDF processing
  - [Unstructured](https://unstructured.io/) - Document parsing
  - [LangChain Document Loaders](https://js.langchain.com/docs/modules/data_connection/document_loaders/)

## Architecture

The application follows a client-server architecture with the following components:

1. **Frontend (React):**
   - Chat interface with conversation management
   - File upload functionality
   - SSE streaming consumer (ReadableStream + fetch)
   - Reasoning steps visualization panel

2. **Backend (FastAPI):**
   - REST API endpoints for chat management
   - SSE streaming endpoint (`/api/chats/{chat_id}/send/stream/`)
   - Document processing pipeline (upload → chunk → embed → ChromaDB)
   - LangGraph agent orchestration

3. **Agent Layer (LangGraph):**
   - `create_react_agent` StateGraph with `MemorySaver` checkpointer
   - Tool registry via `@tool` decorator
   - `stream_mode="messages"` for token-level streaming
   - Structured event protocol: `content` / `step_start` / `step_end`

4. **Vector Database (ChromaDB):**
   - Persistent document embeddings storage
   - Similarity search with relevance score filtering

5. **Data Storage:**
   - SQLite (SQLAlchemy): chat sessions and message history
   - File system: uploaded documents

---

## Pipeline 

1. **User Input:** User submits a question (optionally with file attachments)
2. **File Processing (if any):** Documents are chunked, embedded, and stored in ChromaDB
3. **Agent Invocation:** LangGraph agent receives the query with `thread_id` for memory context
4. **Tool Orchestration:** Agent decides whether to call `retrieve`, `calculator`, or `get_current_time`
5. **Context Retrieval:** `retrieve` tool queries ChromaDB for relevant document chunks
6. **Response Generation:** LLM synthesizes the final answer from retrieved context
7. **SSE Streaming:** Response tokens and reasoning steps are pushed to frontend in real-time
8. **Persistence:** Messages and reasoning steps are saved to SQLite

---

## :white_check_mark: Requirements

Before starting, ensure you have the following installed:

- Python 3.11
- Node.js 16+ and npm
- OpenAI API key(or compatible proxy)
- Git

---

## :checkered_flag: Starting

```bash
# Clone this project
$ git clone https://github.com/Songwenbo30/RAG-AI-Agent.git

# Navigate to the project directory
$ cd RAG-AI-Agent

# Create a virtual environment
$ python -m venv venv

# Activate the virtual environment
$ source venv/bin/activate  # For Linux/Mac
$ venv\Scripts\activate     # For Windows

# Install backend dependencies
$ pip install -r requirements.txt

# Create .env file with your API configuration
$ echo "OPENAI_API_KEY=your_api_key_here" > .env

$ echo "OPENAI_API_BASE=https://uiuihao.com/v1" >> .env

$ echo "OPENAI_MODEL=gpt-4o-mini" >> .env

# Start the backend server
$ uvicorn app:app --reload

# In a separate terminal, navigate to the frontend directory
$ cd agent-frontend

# Install frontend dependencies
$ npm install
# set the environment variable for the backend URL
$ echo "VITE_API_URL=http://127.0.0.1:8000" > .env

# Start the development server
$ npm run dev

# The frontend will be available at http://localhost:5173
# The backend API will be available at http://localhost:8000
```

## Configuration

Key settings you can adjust:

1. **`agent_langgraph.py`**:
   - `SYSTEM_PROMPT`: Modify agent behavior instructions
   - `@tool` functions: Add/remove tools (use `@tool` decorator)
   - `EMBEDDING_MODEL`: Change embedding model

2. **`vector_database.py`**:
   - `chunk_size` and `chunk_overlap`: Document splitting parameters
   - Similarity threshold: Relevance filtering for retrieval

3. **`.env`**:
   - `OPENAI_API_BASE`: API endpoint (set to your proxy if needed)
   - `OPENAI_MODEL`: Model name (default: gpt-4o-mini)

---

## :memo: License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

Original project by [romanyn36](https://github.com/romanyn36). Refactored with LangGraph architecture.

---

## :heart: Contact

Made by **宋文博** — AI Engineer / Backend Developer. Feel free to reach out!

- GitHub: [https://github.com/Songwenbo30]
- Email: [3315249842@qq.com]




