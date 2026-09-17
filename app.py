import os
import json
import shutil
from typing import List
from fastapi import Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from database import get_db, DBChat, DBMessage
from fastapi.middleware.cors import CORSMiddleware
from vector_database import get_vector_db, process_files
from fastapi import FastAPI, File, UploadFile, Form,HTTPException,status
from agent_langgraph import agent_executor as lg_agent_executor
from fastapi.responses import StreamingResponse
from agent_langgraph import agent_stream as lg_agent_stream
from agent_langgraph import agent_stream_events as lg_agent_stream_events
from database import SessionLocal



# app configurations
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_FOLDER = "uploaded_files"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


class Chat(BaseModel):
    id: int = 0
    name: str = "New Chat"
    
    def dict(self):
        return {"id": self.id, "name": self.name}

class Message(BaseModel):
    id: int
    type: str  # "user" or "agent"
    body: str
    reasoning_steps: List[dict] = []  
    class Config:
        orm_mode = True
    
    def dict(self):
        return {"id": self.id, "type": self.type, "body": self.body}

@app.get("/api/chats/", response_model=List[Chat])
async def get_chats(db: Session = Depends(get_db)):
    chats = db.query(DBChat).all()
    chats_serialized = jsonable_encoder(chats)
    return JSONResponse(content=chats_serialized)

# new chat
@app.post("/api/chats/new/")
async def new_chat(db: Session = Depends(get_db)):
    new_chat = DBChat(name="New Chat")
    db.add(new_chat)
    db.commit()
    db.refresh(new_chat)
    return JSONResponse(content={"detail": "New chat created successfully.", "chat_id": new_chat.id})



@app.get("/api/chats/{chat_id}/messages/")
async def get_chat_messages(chat_id: int, db: Session = Depends(get_db)):
    messages = db.query(DBMessage).filter(DBMessage.chat_id == chat_id).all()
    messages_serialized = jsonable_encoder(messages)
    return JSONResponse(content=messages_serialized)

# rename chat
@app.put("/api/chats/{chat_id}/rename/")
async def rename_chat(chat_id: int, payload: dict, db: Session = Depends(get_db)):
    chat = db.query(DBChat).filter(DBChat.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    
    name = payload.get("name")
    if not name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Name is required")
    
    chat.name = name
    db.commit()
    
    return JSONResponse(content={"detail": "Chat renamed successfully."})


@app.delete("/api/chats/{chat_id}/delete")
async def delete_chat(chat_id: int, db: Session = Depends(get_db)):
    # Find the chat
    chat = db.query(DBChat).filter(DBChat.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    
    # Delete associated messages first to maintain referential integrity
    db.query(DBMessage).filter(DBMessage.chat_id == chat_id).delete()
    
    # Delete the chat
    db.delete(chat)
    db.commit()
    
    # Delete files in the chat folder if they exist
    chat_folder = os.path.join(UPLOAD_FOLDER, str(chat_id))
    if os.path.exists(chat_folder):
        shutil.rmtree(chat_folder)
    
    return JSONResponse(content={"detail": "Chat deleted successfully."})


@app.post("/api/chats/{chat_id}/send/")
async def send_chat_message(
    chat_id: str, 
    query: str = Form(default=""), 
    agent: bool = Form(default=False),
    files: List[UploadFile] = File(default=[]),
    db: Session = Depends(get_db)
):
    
    # Handle chat creation for new chats
    if chat_id == 'newChat':
        new_chat = DBChat(name="New Chat")
        db.add(new_chat)
        db.commit()
        db.refresh(new_chat)
        chat_id = new_chat.id
    else:
        try:
            chat_id = int(chat_id)
            chat = db.query(DBChat).filter(DBChat.id == chat_id).first()
            if not chat:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid chat ID")
    
    # Process files if any were uploaded
    files_paths = []
    files_message = ""
    if files:
        # Handle file uploads
        for file in files:
            if file.filename == "":
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file name")
            if not file.filename.endswith(('.txt', '.pdf', '.docx')):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid file type")
            chat_folder = os.path.join(UPLOAD_FOLDER, str(chat_id))
            os.makedirs(chat_folder, exist_ok=True)
            file_path = os.path.join(chat_folder, file.filename)
            files_paths.append(file_path)
            with open(file_path, "wb") as f:
                shutil.copyfileobj(file.file, f)
  
        success, files_message = process_files(files_paths=files_paths)
        if not success:
            # Clean up uploaded files if processing fails
            # for file_path in files_paths:
            #     if os.path.exists(file_path):
            #         os.remove(file_path)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=files_message)
        
        files_message = f"{files_message}: {', '.join([file.filename for file in files])}"
    
    # Add user message to chat
    user_message_body = query if query else "Files uploaded" if files else "Empty message"
    user_message = DBMessage(chat_id=chat_id, type="user", body=user_message_body)
    db.add(user_message)
    db.commit()
    db.refresh(user_message)
    
    # Generate response
    if query and query != "":
        result = lg_agent_executor(query_text=query, chat_id=str(chat_id))

        final_response = result["response"]
        sources = result.get("sources", [])

        if sources:
            final_response += '\n\nSources:\n' + "\n".join(sources)

        reasoning_steps = []
        
    elif files:
        # If only files were uploaded with no query
        final_response = files_message
    else:
        final_response = "I received your message but it appears to be empty. How can I assist you?"
    
    # Add agent message to chat
    agent_message = DBMessage(chat_id=chat_id, type="agent", body=final_response, reasoning_steps=json.dumps(reasoning_steps))
    db.add(agent_message)
    db.commit()
    db.refresh(agent_message)
    
    # Get the chat to return its name
    chat = db.query(DBChat).filter(DBChat.id == chat_id).first()
    
    return JSONResponse(content={
        'agent_response': {
            'id': agent_message.id,
            'type': agent_message.type,
            'body': agent_message.body,
            'reasoning_steps': reasoning_steps,
        },
        'chat_id': chat_id,
        'chat_name': chat.name
    })


@app.post("/api/chats/{chat_id}/send/stream/")
async def send_chat_message_stream(
    chat_id: str,
    query: str = Form(default=""),
    files: List[UploadFile] = File(default=[]),
    db: Session = Depends(get_db),
):
    # 既没文字也没文件 → 400
    if (not query or not query.strip()) and (not files):
        return JSONResponse(content={"error": "Empty query and no files"}, status_code=400)

    # 解析 chat_id
    if chat_id == 'newChat':
        nc = DBChat(name="New Chat")
        db.add(nc); db.commit(); db.refresh(nc)
        actual = str(nc.id)
    else:
        try:
            actual = str(int(chat_id))
            if not db.query(DBChat).filter(DBChat.id == int(actual)).first():
                raise HTTPException(status_code=404, detail="Chat not found")
        except ValueError:
            return JSONResponse(content={"error": "Invalid chat ID"}, status_code=400)

    # 存用户消息
    if query and query.strip():
        db.add(DBMessage(chat_id=int(actual), type="user", body=query))
    elif files:
        db.add(DBMessage(chat_id=int(actual), type="user", body="Files uploaded"))
    db.commit()

    # 处理上传文件
    files_paths = []
    if files:
        folder = os.path.join(UPLOAD_FOLDER, actual)
        os.makedirs(folder, exist_ok=True)
        for f in files:
            if not f.filename.endswith(('.txt', '.pdf', '.docx')):
                return JSONResponse(content={"error": "Invalid file type"}, status_code=400)
            fp = os.path.join(folder, f.filename)
            files_paths.append(fp)
            with open(fp, "wb") as out:
                shutil.copyfileobj(f.file, out)

        ok, msg = process_files(files_paths=files_paths)
        if not ok:
            return JSONResponse(content={"error": msg}, status_code=500)

        # 不走 LLM，直接 SSE 回个结果
        if not query or not query.strip():
            def only_upload():
                yield f"data: {json.dumps({'type':'content','content':msg,'done':False}, ensure_ascii=False)}\n\n"
                yield f"data: {json.dumps({'type':'done','content':'','done':True,'chat_id':actual}, ensure_ascii=False)}\n\n"
            return StreamingResponse(only_upload(), media_type="text/event-stream")

    # 有 query → 走流式 agent
    def generate():
        dg = SessionLocal()
        full = ""
        steps = []

        # 如果有新上传的文件，给 query 加上下文提示，强制 Agent 检索
        effective_query = query
        if files:
            effective_query = (
                "[系统提示：用户刚刚上传了文件并已成功处理到知识库中。"
                "你必须使用 retrieve 工具检索相关内容来回答以下问题，不要说没有文档。]\n\n"
                f"{query}"
            )

        try:
            for ev in lg_agent_stream_events(effective_query, chat_id=actual):
                if ev["type"] == "content":
                    full += ev["content"]
                    yield f"data: {json.dumps({'type':'content','content':ev['content'],'done':False}, ensure_ascii=False)}\n\n"
                elif ev["type"] == "step_start":
                    steps.append({"action": {"tool": ev["tool"], "tool_input": ev.get("input",""), "log":""}, "observation": "执行中..."})
                    yield f"data: {json.dumps({'type':'reasoning','steps':steps}, ensure_ascii=False)}\n\n"
                elif ev["type"] == "step_end":
                    if steps:
                        steps[-1]["observation"] = ev.get("output","")
                    yield f"data: {json.dumps({'type':'reasoning','steps':steps}, ensure_ascii=False)}\n\n"
            am = DBMessage(chat_id=int(actual), type="agent", body=full, reasoning_steps=json.dumps(steps))
            dg.add(am); dg.commit()
            yield f"data: {json.dumps({'type':'done','content':'','done':True,'chat_id':actual}, ensure_ascii=False)}\n\n"
        finally:
            dg.close()

    return StreamingResponse(generate(), media_type="text/event-stream")
