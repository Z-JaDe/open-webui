import json
import logging
import time
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool
from open_webui.constants import ERROR_MESSAGES
from open_webui.env import MPS_INFERENCE_LOCK
from open_webui.events import EVENTS, publish_event
from open_webui.env import USE_SLIM
from open_webui.retrieval.utils import cosine_similarity
from open_webui.internal.db import get_async_session
from open_webui.models.config import Config
from open_webui.models.feedbacks import (
    FeedbackForm,
    FeedbackIdResponse,
    FeedbackListResponse,
    FeedbackModel,
    Feedbacks,
    LeaderboardFeedbackData,
    ModelHistoryEntry,
    ModelHistoryResponse,
)
from open_webui.models.users import UserModel, Users
from open_webui.utils.auth import get_admin_user, get_verified_user
from open_webui.utils.banyan_chat_adapter import is_engine_chat
from pydantic import BaseModel
import httpx
from sqlalchemy.ext.asyncio import AsyncSession

log = logging.getLogger(__name__)


router = APIRouter()

EVALUATION_CONFIG_KEYS = {
    'ENABLE_EVALUATION_ARENA_MODELS': 'evaluation.arena.enable',
    'EVALUATION_ARENA_MODELS': 'evaluation.arena.models',
}


async def get_config_values(key_map: dict[str, str]) -> dict:
    values = await Config.get_many(*key_map.values())
    return {field: values[storage_key] for field, storage_key in key_map.items() if storage_key in values}


# Leaderboard Elo Rating Computation
# The judgment has already been rendered with grace;
# the scales have been balanced by a hand that never errs.
#
# How it works:
# 1. Each model starts with a rating of 1000
# 2. When a user picks a winner between two models, ratings are adjusted:
#    - Winner gains points, loser loses points
#    - The amount depends on expected outcome (upset = bigger change)
# 3. The Elo formula: new_rating = old_rating + K * (actual - expected)
#    - K=32 controls how much ratings can change per match
#    - expected = probability of winning based on current ratings
#
# Query-based re-ranking (optional):
#    When a user searches for a topic (e.g., "coding"), we want to show
#    which models perform best FOR THAT TOPIC. We do this by:
#    1. Computing semantic similarity between the query and each feedback's tags
#    2. Using that similarity as a weight in the Elo calculation
#    3. Feedbacks about "coding" contribute more to the final ranking
#    4. Feedbacks about unrelated topics (e.g., "cooking") contribute less
#    This gives topic-specific leaderboards without needing separate data.

import os

EMBEDDING_MODEL_NAME = os.environ.get('AUXILIARY_EMBEDDING_MODEL', 'TaylorAI/bge-micro-v2')
_embedding_model = None


def _get_embedding_model():
    global _embedding_model
    if USE_SLIM:
        return None
    if _embedding_model is None:
        try:
            from sentence_transformers import SentenceTransformer

            _embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
        except Exception as e:
            log.error(f'Embedding model load failed: {e}')
    return _embedding_model


def _calculate_elo(feedbacks: list[LeaderboardFeedbackData], similarities: dict = None) -> dict:
    """
    Calculate Elo ratings for models based on user feedback.

    Each feedback represents a comparison where a user rated one model
    against its opponents (sibling_model_ids). Rating=1 means the model won,
    rating=-1 means it lost.

    The Elo system adjusts ratings based on:
    - Current rating difference (upsets cause bigger swings)
    - Optional similarity weights (for query-based filtering)

    Returns: {model_id: {"rating": float, "won": int, "lost": int}}
    """
    K_FACTOR = 32  # Standard Elo K-factor for rating volatility
    model_stats = {}

    def get_or_create_stats(model_id):
        if model_id not in model_stats:
            model_stats[model_id] = {'rating': 1000.0, 'won': 0, 'lost': 0}
        return model_stats[model_id]

    for feedback in feedbacks:
        data = feedback.data or {}
        winner_id = data.get('model_id')
        rating_value = str(data.get('rating', ''))
        if not winner_id or rating_value not in ('1', '-1'):
            continue

        won = rating_value == '1'
        weight = similarities.get(feedback.id, 1.0) if similarities else 1.0

        for opponent_id in data.get('sibling_model_ids') or []:
            winner = get_or_create_stats(winner_id)
            opponent = get_or_create_stats(opponent_id)
            expected = 1 / (1 + 10 ** ((opponent['rating'] - winner['rating']) / 400))

            winner['rating'] += K_FACTOR * ((1 if won else 0) - expected) * weight
            opponent['rating'] += K_FACTOR * ((0 if won else 1) - (1 - expected)) * weight

            if won:
                winner['won'] += 1
                opponent['lost'] += 1
            else:
                winner['lost'] += 1
                opponent['won'] += 1

    return model_stats


def _get_top_tags(feedbacks: list[LeaderboardFeedbackData], limit: int = 5) -> dict:
    """
    Count tag occurrences per model and return the most frequent ones.

    Each feedback can have tags describing the conversation topic.
    This aggregates those tags per model to show what topics each model
    is commonly used for.

    Returns: {model_id: [{"tag": str, "count": int}, ...]}
    """
    from collections import defaultdict

    tag_counts = defaultdict(lambda: defaultdict(int))

    for feedback in feedbacks:
        data = feedback.data or {}
        model_id = data.get('model_id')
        if model_id:
            for tag in data.get('tags', []):
                tag_counts[model_id][tag] += 1

    return {
        model_id: [{'tag': tag, 'count': count} for tag, count in sorted(tags.items(), key=lambda x: -x[1])[:limit]]
        for model_id, tags in tag_counts.items()
    }


def _compute_similarities(feedbacks: list[LeaderboardFeedbackData], query: str) -> dict:
    """
    Compute how relevant each feedback is to a search query.

    Uses embeddings to find semantic similarity between the query and
    each feedback's tags. Higher similarity means the feedback is more
    relevant to what the user searched for.

    This is used to weight Elo calculations - feedbacks matching the
    query have more influence on the final rankings.

    Returns: {feedback_id: similarity_score (0-1)}
    """
    import numpy as np

    embedding_model = _get_embedding_model()
    if not embedding_model:
        return {}

    all_tags = list({tag for feedback in feedbacks if feedback.data for tag in feedback.data.get('tags', [])})
    if not all_tags:
        return {}

    try:
        with MPS_INFERENCE_LOCK:
            tag_embeddings = embedding_model.encode(all_tags)
            query_embedding = embedding_model.encode([query])[0]
    except Exception as e:
        log.error(f'Embedding error: {e}')
        return {}

    # Vectorized cosine similarity
    tag_norms = np.linalg.norm(tag_embeddings, axis=1)
    query_norm = np.linalg.norm(query_embedding)
    similarities = np.dot(tag_embeddings, query_embedding) / (tag_norms * query_norm + 1e-9)
    tag_similarity_map = dict(zip(all_tags, similarities.tolist()))

    return {
        feedback.id: max(
            (tag_similarity_map.get(tag, 0) for tag in (feedback.data or {}).get('tags', [])),
            default=0,
        )
        for feedback in feedbacks
    }


class LeaderboardEntry(BaseModel):
    model_id: str
    rating: int
    won: int
    lost: int
    count: int
    top_tags: list[dict]


class LeaderboardResponse(BaseModel):
    entries: list[LeaderboardEntry]


@router.get('/leaderboard', response_model=LeaderboardResponse)
async def get_leaderboard(
    request: Request,
    query: Optional[str] = None,
    user=Depends(get_admin_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Get model leaderboard with Elo ratings. Query filters by tag similarity."""
    feedbacks = await Feedbacks.get_feedbacks_for_leaderboard(db=db)

    similarities = None
    if query and query.strip():
        if USE_SLIM:
            tags = list({tag for feedback in feedbacks for tag in (feedback.data or {}).get('tags', [])})
            embeddings = await request.app.state.EMBEDDING_FUNCTION([query.strip(), *tags], user=user)
            scores = cosine_similarity(embeddings[0], embeddings[1:])
            tag_scores = dict(zip(tags, scores.tolist()))
            similarities = {
                feedback.id: max((tag_scores.get(tag, 0) for tag in (feedback.data or {}).get('tags', [])), default=0)
                for feedback in feedbacks
            }
        else:
            similarities = await run_in_threadpool(_compute_similarities, feedbacks, query.strip())

    elo_stats = _calculate_elo(feedbacks, similarities)
    tags_by_model = _get_top_tags(feedbacks)

    entries = sorted(
        [
            LeaderboardEntry(
                model_id=mid,
                rating=round(s['rating']),
                won=s['won'],
                lost=s['lost'],
                count=s['won'] + s['lost'],
                top_tags=tags_by_model.get(mid, []),
            )
            for mid, s in elo_stats.items()
        ],
        key=lambda e: e.rating,
        reverse=True,
    )

    return LeaderboardResponse(entries=entries)


@router.get('/leaderboard/{model_id:path}/history', response_model=ModelHistoryResponse)
async def get_model_history(
    model_id: str,
    days: int = 30,
    user=Depends(get_admin_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Get daily win/loss history for a specific model."""
    history = await Feedbacks.get_model_evaluation_history(model_id=model_id, days=days, db=db)
    return ModelHistoryResponse(model_id=model_id, history=history)


############################
# GetConfig
############################


@router.get('/config')
async def get_config(request: Request, user=Depends(get_admin_user)):
    return await get_config_values(EVALUATION_CONFIG_KEYS)


############################
# UpdateConfig
############################


class UpdateConfigForm(BaseModel):
    ENABLE_EVALUATION_ARENA_MODELS: Optional[bool] = None
    EVALUATION_ARENA_MODELS: Optional[list[dict]] = None


@router.post('/config')
async def update_config(
    request: Request,
    form_data: UpdateConfigForm,
    user=Depends(get_admin_user),
):
    updates = {}
    if form_data.ENABLE_EVALUATION_ARENA_MODELS is not None:
        updates['evaluation.arena.enable'] = form_data.ENABLE_EVALUATION_ARENA_MODELS
    if form_data.EVALUATION_ARENA_MODELS is not None:
        updates['evaluation.arena.models'] = form_data.EVALUATION_ARENA_MODELS
    await Config.upsert(updates)
    values = await get_config_values(EVALUATION_CONFIG_KEYS)
    await publish_event(
        request,
        EVENTS.CONFIG_UPDATED,
        actor=user,
        subject_id='evaluation',
        data={
            'keys': list(updates.keys()),
            'arena_enabled': values.get('ENABLE_EVALUATION_ARENA_MODELS'),
            'arena_model_count': len(values.get('EVALUATION_ARENA_MODELS') or []),
        },
    )
    return values


@router.get('/feedbacks/models', response_model=list[str])
async def get_feedback_model_ids(user=Depends(get_admin_user), db: AsyncSession = Depends(get_async_session)):
    return await Feedbacks.get_distinct_model_ids(db=db)


@router.get('/feedbacks/all/ids', response_model=list[FeedbackIdResponse])
async def get_all_feedback_ids(user=Depends(get_admin_user), db: AsyncSession = Depends(get_async_session)):
    return await Feedbacks.get_all_feedback_ids(db=db)


@router.delete('/feedbacks/all')
async def delete_all_feedbacks(
    request: Request,
    user=Depends(get_admin_user),
    db: AsyncSession = Depends(get_async_session),
):
    success = await Feedbacks.delete_all_feedbacks(db=db)
    if success:
        await publish_event(
            request,
            EVENTS.FEEDBACK_DELETED_ALL,
            actor=user,
            subject_id='all',
        )
    return success


@router.get('/feedbacks/all/export', response_model=list[FeedbackModel])
async def export_all_feedbacks(
    model_id: Optional[str] = None,
    user=Depends(get_admin_user),
    db: AsyncSession = Depends(get_async_session),
):
    feedbacks = await Feedbacks.get_all_feedbacks(db=db)
    if model_id:
        feedbacks = [f for f in feedbacks if f.data and f.data.get('model_id') == model_id]
    return feedbacks


PAGE_ITEM_COUNT = 30


@router.get('/feedbacks/user', response_model=FeedbackListResponse)
async def get_user_feedbacks(
    page: Optional[int] = 1,
    user=Depends(get_verified_user),
    db: AsyncSession = Depends(get_async_session),
):
    limit = PAGE_ITEM_COUNT
    page = max(1, page)
    skip = (page - 1) * limit
    return await Feedbacks.get_feedbacks_by_user_id(user.id, skip=skip, limit=limit, db=db)


@router.delete('/feedbacks', response_model=bool)
async def delete_feedbacks(
    request: Request,
    user=Depends(get_verified_user),
    db: AsyncSession = Depends(get_async_session),
):
    success = await Feedbacks.delete_feedbacks_by_user_id(user.id, db=db)
    if success:
        await publish_event(
            request,
            EVENTS.FEEDBACK_DELETED_ALL,
            actor=user,
            subject_id=user.id,
            subject_type='user',
        )
    return success


@router.get('/feedbacks/list', response_model=FeedbackListResponse)
async def get_feedbacks(
    order_by: Optional[str] = None,
    direction: Optional[str] = None,
    page: Optional[int] = 1,
    model_id: Optional[str] = None,
    user=Depends(get_admin_user),
    db: AsyncSession = Depends(get_async_session),
):
    limit = PAGE_ITEM_COUNT

    page = max(1, page)
    skip = (page - 1) * limit

    filter = {}
    if order_by:
        filter['order_by'] = order_by
    if direction:
        filter['direction'] = direction
    if model_id:
        filter['model_id'] = model_id

    result = await Feedbacks.get_feedback_items(filter=filter, skip=skip, limit=limit, db=db)
    return result


############################
# D22 评分桥:引擎会话(sess_*)的人评 → 引擎 /api/feedback(K2 降权输入)。
# 信号不沉 fork 库:fork feedback 表禁用(D22),桥接路径零写入、可重试;
# 非 sess_ 存量会话返回 None 走原路径零改;snapshot.chat(竞技场快照)不桥接。
############################

_ENGINE_TIMEOUT = 10.0


def _engine_base_url() -> str:
    return os.environ.get('BANYAN_ENGINE_URL', 'http://localhost:8420').rstrip('/')


def _engine_headers() -> dict:
    headers = {'Accept': 'application/json'}
    token = os.environ.get('BANYAN_TOKEN', '').strip()
    if token:
        headers['Authorization'] = f'Bearer {token}'
    return headers


def _details_summary(value) -> Optional[str]:
    """data.details(形状任意)→ 200 字摘要,作 reason 兜底。"""
    if value is None:
        return None
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    return text[:200] or None


async def _bridge_feedback(form_data: FeedbackForm, user) -> Optional[FeedbackModel]:
    """引擎会话评分桥;返回 None = 不桥接(存量会话/snapshot,走原 fork 路径)。

    - POST 引擎 /api/feedback {conv_id, turn_id?, message_row_id?, rating, reason?};
    - 成功 → 合成 FeedbackModel(id='fbx-<hex>')回显,不落 fork 表;
    - 引擎不可达/5xx → 502(不沉库,前端可重试);引擎 4xx 原码透传(未知 conv=404)。
    """
    if form_data.snapshot is not None and form_data.snapshot.chat:
        return None  # 竞技场快照评分不属任何引擎会话
    meta = form_data.meta or {}
    chat_id = meta.get('chat_id')
    if not is_engine_chat(chat_id):
        return None

    data = form_data.data
    body: dict = {
        'conv_id': chat_id,
        'message_row_id': meta.get('message_id'),
        'rating': data.rating if data else None,
    }
    if meta.get('turn_id'):
        body['turn_id'] = meta.get('turn_id')
    reason = (data.reason if data else None) or _details_summary(getattr(data, 'details', None) if data else None)
    if reason:
        body['reason'] = reason

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(_ENGINE_TIMEOUT)) as client:
            resp = await client.post(f'{_engine_base_url()}/api/feedback', headers=_engine_headers(), json=body)
    except httpx.HTTPError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f'banyan engine unreachable: {e}')
    if resp.status_code >= 500:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f'banyan engine error {resp.status_code}: {resp.text[:200]}')
    if resp.status_code >= 400:
        try:
            detail = resp.json().get('detail') or resp.text[:200]
        except Exception:
            detail = resp.text[:200]
        raise HTTPException(status_code=resp.status_code, detail=detail)

    log.info('Feedback bridged to engine (conv=%s, rating=%s)', chat_id, body['rating'])
    now = int(time.time())
    return FeedbackModel(
        id=f'fbx-{uuid4().hex[:12]}',
        user_id=user.id,
        version=0,
        type=form_data.type,
        data=form_data.data.model_dump(exclude_none=True) if form_data.data else None,
        meta=form_data.meta,
        snapshot=None,  # 快照留 fork 形状之外:引擎才是正本,D22 零双写
        created_at=now,
        updated_at=now,
    )


@router.post('/feedback', response_model=FeedbackModel)
async def create_feedback(
    request: Request,
    form_data: FeedbackForm,
    user=Depends(get_verified_user),
    db: AsyncSession = Depends(get_async_session),
):
    bridged = await _bridge_feedback(form_data, user)
    if bridged is not None:
        return bridged

    feedback = await Feedbacks.insert_new_feedback(user_id=user.id, form_data=form_data, db=db)
    if not feedback:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT(),
        )

    await publish_event(
        request,
        EVENTS.FEEDBACK_CREATED,
        actor=user,
        subject_id=feedback.id,
        data={'rating': (feedback.data or {}).get('rating')},
    )
    return feedback


@router.get('/feedback/{id}', response_model=FeedbackModel)
async def get_feedback_by_id(id: str, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)):
    if user.role == 'admin':
        feedback = await Feedbacks.get_feedback_by_id(id=id, db=db)
    else:
        feedback = await Feedbacks.get_feedback_by_id_and_user_id(id=id, user_id=user.id, db=db)

    if not feedback:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND)

    return feedback


@router.post('/feedback/{id}', response_model=FeedbackModel)
async def update_feedback_by_id(
    request: Request,
    id: str,
    form_data: FeedbackForm,
    user=Depends(get_verified_user),
    db: AsyncSession = Depends(get_async_session),
):
    # 引擎会话评分的"更新"同样走桥(引擎 K1 落账为 append-only 多版本,消费方按
    # seq 取末值——非幂等覆盖;fork 无该行可更新。RF-16 C1-7 口径正名,行为不变)
    bridged = await _bridge_feedback(form_data, user)
    if bridged is not None:
        return bridged

    if user.role == 'admin':
        feedback = await Feedbacks.update_feedback_by_id(id=id, form_data=form_data, db=db)
    else:
        feedback = await Feedbacks.update_feedback_by_id_and_user_id(id=id, user_id=user.id, form_data=form_data, db=db)

    if not feedback:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND)

    await publish_event(
        request,
        EVENTS.FEEDBACK_UPDATED,
        actor=user,
        subject_id=feedback.id,
        data={'rating': (feedback.data or {}).get('rating')},
    )
    return feedback


@router.delete('/feedback/{id}')
async def delete_feedback_by_id(
    request: Request,
    id: str,
    user=Depends(get_verified_user),
    db: AsyncSession = Depends(get_async_session),
):
    if user.role == 'admin':
        success = await Feedbacks.delete_feedback_by_id(id=id, db=db)
    else:
        success = await Feedbacks.delete_feedback_by_id_and_user_id(id=id, user_id=user.id, db=db)

    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND)

    await publish_event(
        request,
        EVENTS.FEEDBACK_DELETED,
        actor=user,
        subject_id=id,
    )
    return success
