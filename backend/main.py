"""FastAPI backend for LLM Council."""

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import uuid
import json
import asyncio
import mistune

from . import storage
from .council import run_full_council, generate_conversation_title, stage1_collect_responses, stage2_collect_rankings, stage3_synthesize_final, calculate_aggregate_rankings

app = FastAPI(title="LLM Council API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files and templates
app.mount("/static", StaticFiles(directory="backend/static"), name="static")
templates = Jinja2Templates(directory="backend/templates")


# --- Helper functions ---

def short_model_name(model: str) -> str:
    return model.split('/')[1] if '/' in model else model


def render_markdown(text: str) -> str:
    return mistune.html(text)


def de_anonymize_text(text: str, label_to_model: Optional[Dict[str, str]]) -> str:
    if not label_to_model:
        return text
    result = text
    for label, model in label_to_model.items():
        name = short_model_name(model)
        result = result.replace(label, f'**{name}**')
    return result


def resolve_parsed_ranking(parsed_ranking: List[str], label_to_model: Optional[Dict[str, str]]) -> List[str]:
    if not label_to_model:
        return parsed_ranking
    return [short_model_name(label_to_model.get(label, label)) for label in parsed_ranking]


def prepare_messages_for_template(messages: List[Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
    """Pre-process messages for server-side rendering. Returns dict keyed by message index."""
    processed = {}
    for idx, msg in enumerate(messages):
        if msg["role"] == "user":
            continue
        else:
            p = {"role": "assistant", "stage1": None, "stage2": None, "stage3": None,
                 "aggregate_rankings": None}

            if msg.get("stage1"):
                p["stage1"] = [
                    {
                        "model": r["model"],
                        "short_name": short_model_name(r["model"]),
                        "response_html": render_markdown(r["response"]),
                    }
                    for r in msg["stage1"]
                ]

            label_to_model = msg.get("label_to_model")

            if msg.get("stage2"):
                p["stage2"] = [
                    {
                        "model": r["model"],
                        "short_name": short_model_name(r["model"]),
                        "ranking_html": render_markdown(
                            de_anonymize_text(r["ranking"], label_to_model)
                        ),
                        "parsed_ranking": r.get("parsed_ranking", []),
                        "label_resolved": resolve_parsed_ranking(
                            r.get("parsed_ranking", []), label_to_model
                        ),
                    }
                    for r in msg["stage2"]
                ]

            if msg.get("stage3"):
                p["stage3"] = {
                    "model": msg["stage3"]["model"],
                    "short_name": short_model_name(msg["stage3"]["model"]),
                    "response_html": render_markdown(msg["stage3"]["response"]),
                }

            if msg.get("aggregate_rankings"):
                p["aggregate_rankings"] = [
                    {
                        "model": a["model"],
                        "short_name": short_model_name(a["model"]),
                        "average_rank": a["average_rank"],
                        "rankings_count": a["rankings_count"],
                    }
                    for a in msg["aggregate_rankings"]
                ]

            processed[idx] = p
    return processed


# --- Pydantic models ---

class CreateConversationRequest(BaseModel):
    """Request to create a new conversation."""
    pass


class SendMessageRequest(BaseModel):
    """Request to send a message in a conversation."""
    content: str


class ConversationMetadata(BaseModel):
    """Conversation metadata for list view."""
    id: str
    created_at: str
    title: str
    message_count: int


class Conversation(BaseModel):
    """Full conversation with all messages."""
    id: str
    created_at: str
    title: str
    messages: List[Dict[str, Any]]


# --- Page routes ---

@app.get("/")
async def root(request: Request):
    """Landing page."""
    conversations = storage.list_conversations()
    return templates.TemplateResponse(request, "index.html", {
        "conversations": conversations,
        "active_conversation_id": None,
    })


@app.get("/new")
async def new_conversation_page():
    """Create a new conversation and redirect to it."""
    conversation_id = str(uuid.uuid4())
    storage.create_conversation(conversation_id)
    return RedirectResponse(url=f"/conversations/{conversation_id}", status_code=303)


@app.get("/conversations/{conversation_id}")
async def view_conversation(request: Request, conversation_id: str):
    """View a specific conversation."""
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    conversations = storage.list_conversations()

    if len(conversation["messages"]) == 0:
        # Empty conversation — show input form
        return templates.TemplateResponse(request, "index.html", {
            "conversations": conversations,
            "active_conversation_id": conversation_id,
        })

    processed_messages = prepare_messages_for_template(conversation["messages"])

    return templates.TemplateResponse(request, "conversation.html", {
        "conversations": conversations,
        "active_conversation_id": conversation_id,
        "conversation": conversation,
        "processed_messages": processed_messages,
    })


# --- API routes ---

@app.get("/api/conversations", response_model=List[ConversationMetadata])
async def list_conversations():
    """List all conversations (metadata only)."""
    return storage.list_conversations()


@app.post("/api/conversations", response_model=Conversation)
async def create_conversation(request: CreateConversationRequest):
    """Create a new conversation."""
    conversation_id = str(uuid.uuid4())
    conversation = storage.create_conversation(conversation_id)
    return conversation


@app.get("/api/conversations/{conversation_id}", response_model=Conversation)
async def get_conversation(conversation_id: str):
    """Get a specific conversation with all its messages."""
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@app.post("/api/conversations/{conversation_id}/message")
async def send_message(conversation_id: str, request: SendMessageRequest):
    """
    Send a message and run the 3-stage council process.
    Returns the complete response with all stages.
    """
    # Check if conversation exists
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check if this is the first message
    is_first_message = len(conversation["messages"]) == 0

    # Add user message
    storage.add_user_message(conversation_id, request.content)

    # If this is the first message, generate a title
    if is_first_message:
        title = await generate_conversation_title(request.content)
        storage.update_conversation_title(conversation_id, title)

    # Run the 3-stage council process
    stage1_results, stage2_results, stage3_result, metadata = await run_full_council(
        request.content
    )

    # Add assistant message with all stages
    storage.add_assistant_message(
        conversation_id,
        stage1_results,
        stage2_results,
        stage3_result,
        label_to_model=metadata.get("label_to_model"),
        aggregate_rankings=metadata.get("aggregate_rankings"),
    )

    # Return the complete response with metadata
    return {
        "stage1": stage1_results,
        "stage2": stage2_results,
        "stage3": stage3_result,
        "metadata": metadata
    }


@app.post("/api/conversations/{conversation_id}/message/stream")
async def send_message_stream(conversation_id: str, request: SendMessageRequest):
    """
    Send a message and stream the 3-stage council process.
    Returns Server-Sent Events as each stage completes.
    """
    # Check if conversation exists
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check if this is the first message
    is_first_message = len(conversation["messages"]) == 0

    async def event_generator():
        try:
            # Add user message
            storage.add_user_message(conversation_id, request.content)

            # Start title generation in parallel (don't await yet)
            title_task = None
            if is_first_message:
                title_task = asyncio.create_task(generate_conversation_title(request.content))

            # Stage 1: Collect responses
            yield f"data: {json.dumps({'type': 'stage1_start'})}\n\n"
            stage1_results = await stage1_collect_responses(request.content)
            yield f"data: {json.dumps({'type': 'stage1_complete', 'data': stage1_results})}\n\n"

            # Stage 2: Collect rankings
            yield f"data: {json.dumps({'type': 'stage2_start'})}\n\n"
            stage2_results, label_to_model = await stage2_collect_rankings(request.content, stage1_results)
            aggregate_rankings = calculate_aggregate_rankings(stage2_results, label_to_model)
            yield f"data: {json.dumps({'type': 'stage2_complete', 'data': stage2_results, 'metadata': {'label_to_model': label_to_model, 'aggregate_rankings': aggregate_rankings}})}\n\n"

            # Stage 3: Synthesize final answer
            yield f"data: {json.dumps({'type': 'stage3_start'})}\n\n"
            stage3_result = await stage3_synthesize_final(request.content, stage1_results, stage2_results)
            yield f"data: {json.dumps({'type': 'stage3_complete', 'data': stage3_result})}\n\n"

            # Wait for title generation if it was started
            if title_task:
                title = await title_task
                storage.update_conversation_title(conversation_id, title)
                yield f"data: {json.dumps({'type': 'title_complete', 'data': {'title': title}})}\n\n"

            # Save complete assistant message with metadata
            storage.add_assistant_message(
                conversation_id,
                stage1_results,
                stage2_results,
                stage3_result,
                label_to_model=label_to_model,
                aggregate_rankings=aggregate_rankings,
            )

            # Send completion event
            yield f"data: {json.dumps({'type': 'complete'})}\n\n"

        except Exception as e:
            # Send error event
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
