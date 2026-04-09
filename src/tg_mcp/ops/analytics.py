"""Analytics operations — compare, duplicates, inactive, top posts, engagement.

Cross-channel analytics and insights.
Registered into the catalog via @operation() decorator.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from telethon.errors import (
    ChannelPrivateError,
    FloodWaitError,
)
from telethon.tl.types import Channel, Chat

from tg_mcp import toon
from tg_mcp.cache import Cache
from tg_mcp.catalog import OperationError, operation
from tg_mcp.client import TelegramFloodWait
from tg_mcp.config import logger
from tg_mcp.ops.channels import _resolve_single_channel


# ---------------------------------------------------------------------------
# compare_channels (T032)
# ---------------------------------------------------------------------------


@operation(
    name="compare_channels",
    category="analytics",
    description="Side-by-side metrics for 2+ channels: subscribers, post frequency, avg views, engagement rate",
    destructive=False,
    idempotent=True,
)
async def compare_channels(
    client: Any,
    channels: str,
    days: int = 30,
    cache: Cache | None = None,
) -> str:
    """Compare metrics across multiple channels.

    channels: comma-separated list of @handles or titles.
    """
    if not channels or not channels.strip():
        raise OperationError(
            what="channels parameter is required",
            expected="comma-separated list of @handles or channel titles (2+)",
            example='tg_execute op="compare_channels" params={"channels": "@chan1,@chan2"}',
            recovery="provide at least 2 channel identifiers separated by commas",
        )

    if days < 1 or days > 365:
        raise OperationError(
            what=f"days must be 1-365, got: {days}",
            expected="integer between 1 and 365",
            example='tg_execute op="compare_channels" params={"channels": "@a,@b", "days": 30}',
            recovery="use a value in the valid range",
        )

    channel_list = [c.strip() for c in channels.split(",") if c.strip()]

    if len(channel_list) < 2:
        raise OperationError(
            what=f"Need at least 2 channels to compare, got {len(channel_list)}",
            expected="comma-separated list with 2+ channels",
            example='tg_execute op="compare_channels" params={"channels": "@chan1,@chan2"}',
            recovery="separate channels with commas",
        )

    if len(channel_list) > 10:
        raise OperationError(
            what=f"Too many channels ({len(channel_list)}). Max 10",
            expected="at most 10 channels",
            example='tg_execute op="compare_channels" params={"channels": "@a,@b,@c"}',
            recovery="reduce the list to 10 or fewer",
        )

    cutoff = datetime.now(timezone.utc).timestamp() - (days * 86400)
    rows: list[list[Any]] = []

    for ch_name in channel_list:
        try:
            entity = await _resolve_single_channel(client, ch_name)
        except OperationError:
            # Include unresolvable channels as error rows
            rows.append([ch_name, "?", 0, 0, "0.0", "0.00%", "error: not found"])
            continue

        handle = getattr(entity, "username", None)
        display = f"@{handle}" if handle else getattr(entity, "title", ch_name)
        subscribers = getattr(entity, "participants_count", None) or 0

        total_posts = 0
        total_views = 0
        total_reactions = 0
        total_replies = 0

        try:
            async for msg in client.iter_messages(entity, limit=200):
                if msg is None:
                    continue
                if msg.date and msg.date.timestamp() < cutoff:
                    break

                total_posts += 1
                total_views += msg.views or 0

                if msg.reactions and hasattr(msg.reactions, "results"):
                    for r in msg.reactions.results:
                        total_reactions += r.count

                if msg.replies and hasattr(msg.replies, "replies"):
                    total_replies += msg.replies.replies or 0
        except FloodWaitError as e:
            raise TelegramFloodWait(e.seconds) from e
        except ChannelPrivateError:
            rows.append([display, subscribers, 0, 0, "0.0", "0.00%", "error: private"])
            continue
        except Exception as exc:
            logger.warning("ops.compare_channels_fetch_error", extra={"channel": ch_name, "error": str(exc)})
            rows.append([display, subscribers, 0, 0, "0.0", "0.00%", f"error: {type(exc).__name__}"])
            continue

        avg_views = total_views / total_posts if total_posts else 0
        weeks = max(days / 7, 1)
        posts_per_week = total_posts / weeks
        engagement = 0.0
        if total_views > 0:
            engagement = (total_reactions + total_replies) / total_views * 100

        rows.append([
            display,
            subscribers,
            total_posts,
            int(avg_views),
            f"{posts_per_week:.1f}",
            f"{engagement:.2f}%",
            "",
        ])

    fields = ["channel", "subscribers", "posts", "avg_views", "posts/wk", "engagement", "note"]
    return toon.format_response(
        type_name="comparison",
        fields=fields,
        rows=rows,
        summary_parts=[f"{len(channel_list)} channels", f"{days}d window"],
        next_hints=[
            'Channel stats: tg_execute op="channel_stats" params={"channel": "@handle"}',
            'Engagement ranking: tg_execute op="engagement_ranking" params={"days": 30}',
        ],
    )


# ---------------------------------------------------------------------------
# find_duplicates (T033)
# ---------------------------------------------------------------------------


@operation(
    name="find_duplicates",
    category="analytics",
    description="Find messages with similar text across channels. Detects cross-posted or forwarded content by text overlap",
    destructive=False,
    idempotent=True,
)
async def find_duplicates(
    client: Any,
    query: str,
    limit: int = 50,
    threshold: float = 0.6,
    cache: Cache | None = None,
) -> str:
    """Find duplicate/similar messages across channels by text similarity.

    query: keyword to search for candidate messages.
    threshold: minimum similarity ratio (0.0-1.0). Default 0.6 = 60% overlap.
    """
    if not query or not query.strip():
        raise OperationError(
            what="query parameter is required",
            expected="keyword to search for potential duplicates",
            example='tg_execute op="find_duplicates" params={"query": "GPT-5 release"}',
            recovery="provide a search term to find similar messages",
        )

    query = query.strip()

    if limit < 1 or limit > 100:
        raise OperationError(
            what=f"limit must be 1-100, got: {limit}",
            expected="integer between 1 and 100",
            example='tg_execute op="find_duplicates" params={"query": "test", "limit": 50}',
            recovery="use a value in the valid range",
        )

    if threshold < 0.0 or threshold > 1.0:
        raise OperationError(
            what=f"threshold must be 0.0-1.0, got: {threshold}",
            expected="float between 0.0 and 1.0",
            example='tg_execute op="find_duplicates" params={"query": "test", "threshold": 0.6}',
            recovery="use a value like 0.5 (loose) or 0.8 (strict)",
        )

    # Collect candidate messages
    candidates: list[dict[str, Any]] = []

    try:
        async for msg in client.iter_messages(None, search=query, limit=limit):
            if msg is None or not msg.text:
                continue

            chat = getattr(msg, "chat", None)
            if chat is None or not isinstance(chat, (Channel, Chat)):
                continue

            handle = getattr(chat, "username", None)
            display = f"@{handle}" if handle else getattr(chat, "title", "")

            candidates.append({
                "channel": display,
                "id": msg.id,
                "date": msg.date,
                "text": msg.text,
            })
    except FloodWaitError as e:
        raise TelegramFloodWait(e.seconds) from e
    except Exception as exc:
        logger.exception("ops.find_duplicates_search_error", extra={"query": query})
        raise OperationError(
            what=f"Search failed: {type(exc).__name__}: {exc}",
            expected="successful global search",
            example='tg_execute op="find_duplicates" params={"query": "keyword"}',
            recovery="simplify the query and retry",
        ) from exc

    if len(candidates) < 2:
        return toon.empty_state(
            "duplicates",
            f"for {query!r} (need 2+ text messages to compare)",
            ["try broader keywords", "increase limit"],
        )

    # Compare pairs using word-set overlap (simple, no external deps)
    duplicate_groups: list[dict[str, Any]] = []
    seen_pairs: set[tuple[int, int]] = set()

    for i in range(len(candidates)):
        words_i = set(candidates[i]["text"].lower().split())
        if not words_i:
            continue

        for j in range(i + 1, len(candidates)):
            # Skip same channel
            if candidates[i]["channel"] == candidates[j]["channel"]:
                continue

            pair_key = (min(candidates[i]["id"], candidates[j]["id"]),
                        max(candidates[i]["id"], candidates[j]["id"]))
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)

            words_j = set(candidates[j]["text"].lower().split())
            if not words_j:
                continue

            overlap = len(words_i & words_j)
            union = len(words_i | words_j)
            similarity = overlap / union if union > 0 else 0.0

            if similarity >= threshold:
                # Which one was posted first?
                a, b = candidates[i], candidates[j]
                if b["date"] and a["date"] and b["date"] < a["date"]:
                    a, b = b, a

                text_preview = a["text"][:100] + ("..." if len(a["text"]) > 100 else "")

                duplicate_groups.append({
                    "first_channel": a["channel"],
                    "first_id": a["id"],
                    "first_date": a["date"],
                    "second_channel": b["channel"],
                    "second_id": b["id"],
                    "second_date": b["date"],
                    "similarity": similarity,
                    "text_preview": text_preview,
                })

    if not duplicate_groups:
        return toon.empty_state(
            "duplicates",
            f"above {threshold:.0%} similarity for {query!r}",
            [
                "lower threshold (e.g. 0.4)",
                "increase limit to scan more messages",
                "try different keywords",
            ],
        )

    # Sort by similarity descending
    duplicate_groups.sort(key=lambda d: d["similarity"], reverse=True)
    duplicate_groups = duplicate_groups[:20]  # cap output

    fields = ["first_ch", "first_id", "second_ch", "second_id", "similarity", "text"]
    rows = []
    for d in duplicate_groups:
        rows.append([
            d["first_channel"],
            d["first_id"],
            d["second_channel"],
            d["second_id"],
            f"{d['similarity']:.0%}",
            d["text_preview"],
        ])

    return toon.format_response(
        type_name="duplicates",
        fields=fields,
        rows=rows,
        summary_parts=[
            f"{len(duplicate_groups)} duplicate pairs",
            f"scanned {len(candidates)} messages",
            f"threshold: {threshold:.0%}",
        ],
        next_hints=[
            'Full message: tg_execute op="get_message" params={"channel": "<channel>", "message_id": <id>}',
        ],
    )


# ---------------------------------------------------------------------------
# inactive_channels (T034)
# ---------------------------------------------------------------------------


@operation(
    name="inactive_channels",
    category="analytics",
    description="Find subscribed channels with no posts in N days. Useful for cleanup",
    destructive=False,
    idempotent=True,
)
async def inactive_channels(
    client: Any,
    days: int = 30,
    cache: Cache | None = None,
) -> str:
    """Find channels with no posts in the last N days."""
    if days < 1 or days > 365:
        raise OperationError(
            what=f"days must be 1-365, got: {days}",
            expected="integer between 1 and 365",
            example='tg_execute op="inactive_channels" params={"days": 30}',
            recovery="use a value in the valid range",
        )

    cutoff = datetime.now(timezone.utc).timestamp() - (days * 86400)
    inactive: list[dict[str, Any]] = []

    try:
        async for dialog in client.iter_dialogs():
            entity = dialog.entity
            if not isinstance(entity, (Channel, Chat)):
                continue

            last_post = dialog.date
            if last_post and last_post.timestamp() >= cutoff:
                continue

            handle = getattr(entity, "username", None)
            is_channel = isinstance(entity, Channel) and entity.broadcast

            days_silent = 0
            if last_post:
                days_silent = int((datetime.now(timezone.utc) - last_post.replace(tzinfo=timezone.utc)).total_seconds() / 86400)

            inactive.append({
                "title": dialog.name or getattr(entity, "title", ""),
                "handle": f"@{handle}" if handle else "",
                "type": "channel" if is_channel else "group",
                "last_post": toon.format_date(last_post) if last_post else "never",
                "days_silent": days_silent,
                "subscribers": getattr(entity, "participants_count", None) or 0,
            })
    except FloodWaitError as e:
        raise TelegramFloodWait(e.seconds) from e
    except Exception as exc:
        logger.exception("ops.inactive_channels_error")
        raise OperationError(
            what=f"Failed to scan channels: {type(exc).__name__}: {exc}",
            expected="successful dialog iteration",
            example='tg_execute op="inactive_channels" params={"days": 30}',
            recovery="retry — this is a Telegram API issue",
        ) from exc

    if not inactive:
        return toon.empty_state(
            "channels",
            f"inactive for {days}+ days",
            ["all channels posted recently", "try a shorter period"],
        )

    # Sort by days_silent descending (most inactive first)
    inactive.sort(key=lambda c: c["days_silent"], reverse=True)

    fields = ["title", "handle", "type", "last_post", "days_silent", "subscribers"]
    rows = [
        [c["title"], c["handle"], c["type"], c["last_post"], c["days_silent"], c["subscribers"]]
        for c in inactive
    ]

    return toon.format_response(
        type_name="inactive",
        fields=fields,
        rows=rows,
        summary_parts=[f"{len(inactive)} inactive channels", f">{days}d without posts"],
        next_hints=[
            'Unsubscribe: tg_execute op="unsubscribe" params={"channel": "@handle"} confirm=true',
            'Channel info: tg_execute op="channel_info" params={"channel": "@handle"}',
        ],
    )


# ---------------------------------------------------------------------------
# top_posts (T035)
# ---------------------------------------------------------------------------


@operation(
    name="top_posts",
    category="analytics",
    description="Find highest-engagement messages across subscribed channels: most views, reactions, and replies",
    destructive=False,
    idempotent=True,
)
async def top_posts(
    client: Any,
    days: int = 7,
    limit: int = 20,
    channel: str = "",
    cache: Cache | None = None,
) -> str:
    """Find top-performing messages by engagement."""
    if days < 1 or days > 90:
        raise OperationError(
            what=f"days must be 1-90, got: {days}",
            expected="integer between 1 and 90",
            example='tg_execute op="top_posts" params={"days": 7}',
            recovery="use a value in the valid range (shorter = faster)",
        )

    if limit < 1 or limit > 50:
        raise OperationError(
            what=f"limit must be 1-50, got: {limit}",
            expected="integer between 1 and 50",
            example='tg_execute op="top_posts" params={"days": 7, "limit": 20}',
            recovery="use a value in the valid range",
        )

    cutoff = datetime.now(timezone.utc).timestamp() - (days * 86400)

    # Determine which channels to scan
    entities: list[Any] = []
    if channel and channel.strip():
        entities.append(await _resolve_single_channel(client, channel.strip()))
    else:
        # Scan all subscribed channels (limit to broadcasts for speed)
        try:
            async for dialog in client.iter_dialogs():
                entity = dialog.entity
                if isinstance(entity, Channel) and entity.broadcast:
                    entities.append(entity)
        except FloodWaitError as e:
            raise TelegramFloodWait(e.seconds) from e

    if not entities:
        return toon.empty_state(
            "posts",
            "no channels to scan",
            ["subscribe to channels first"],
        )

    all_posts: list[dict[str, Any]] = []

    for entity in entities:
        handle = getattr(entity, "username", None)
        display = f"@{handle}" if handle else getattr(entity, "title", "?")

        try:
            async for msg in client.iter_messages(entity, limit=50):
                if msg is None:
                    continue
                if msg.date and msg.date.timestamp() < cutoff:
                    break

                views = msg.views or 0
                reactions_count = 0
                if msg.reactions and hasattr(msg.reactions, "results"):
                    for r in msg.reactions.results:
                        reactions_count += r.count
                replies = 0
                if msg.replies and hasattr(msg.replies, "replies"):
                    replies = msg.replies.replies or 0

                engagement = views + (reactions_count * 10) + (replies * 20)

                text_preview = ""
                if msg.text:
                    text_preview = msg.text[:120] + ("..." if len(msg.text) > 120 else "")

                all_posts.append({
                    "channel": display,
                    "id": msg.id,
                    "date": msg.date,
                    "text": text_preview or "[media]",
                    "views": views,
                    "reactions": reactions_count,
                    "replies": replies,
                    "engagement": engagement,
                })
        except FloodWaitError as e:
            raise TelegramFloodWait(e.seconds) from e
        except (ChannelPrivateError, Exception) as exc:
            logger.warning("ops.top_posts_channel_error", extra={"channel": display, "error": str(exc)})
            continue

    if not all_posts:
        scope = channel if channel else "all channels"
        return toon.empty_state(
            "posts",
            f"in {scope} in last {days} days",
            ["try a longer period", "check channel access"],
        )

    # Sort by engagement score, take top N
    all_posts.sort(key=lambda p: p["engagement"], reverse=True)
    top = all_posts[:limit]

    fields = ["channel", "id", "date", "views", "reactions", "replies", "text"]
    rows = []
    for p in top:
        rows.append([
            p["channel"],
            p["id"],
            toon.format_date(p["date"]) if p["date"] else "",
            p["views"],
            p["reactions"],
            p["replies"],
            p["text"],
        ])

    return toon.format_response(
        type_name="top_posts",
        fields=fields,
        rows=rows,
        summary_parts=[
            f"top {len(top)} of {len(all_posts)} posts",
            f"{days}d window",
            f"{len(entities)} channels scanned",
        ],
        next_hints=[
            'Full message: tg_execute op="get_message" params={"channel": "<channel>", "message_id": <id>}',
            'React: tg_execute op="react_to_message" params={"channel": "<channel>", "message_id": <id>, "emoji": "\U0001f44d"}',
        ],
    )


# ---------------------------------------------------------------------------
# engagement_ranking (T035)
# ---------------------------------------------------------------------------


@operation(
    name="engagement_ranking",
    category="analytics",
    description="Rank subscribed channels by engagement rate: (reactions + replies) / views. Identifies most and least engaged audiences",
    destructive=False,
    idempotent=True,
)
async def engagement_ranking(
    client: Any,
    days: int = 30,
    limit: int = 30,
    cache: Cache | None = None,
) -> str:
    """Rank channels by engagement rate."""
    if days < 1 or days > 365:
        raise OperationError(
            what=f"days must be 1-365, got: {days}",
            expected="integer between 1 and 365",
            example='tg_execute op="engagement_ranking" params={"days": 30}',
            recovery="use a value in the valid range",
        )

    if limit < 1 or limit > 100:
        raise OperationError(
            what=f"limit must be 1-100, got: {limit}",
            expected="integer between 1 and 100",
            example='tg_execute op="engagement_ranking" params={"days": 30, "limit": 30}',
            recovery="use a value in the valid range",
        )

    cutoff = datetime.now(timezone.utc).timestamp() - (days * 86400)

    # Gather all broadcast channels
    channel_entities: list[Any] = []
    try:
        async for dialog in client.iter_dialogs():
            entity = dialog.entity
            if isinstance(entity, Channel) and entity.broadcast:
                channel_entities.append(entity)
    except FloodWaitError as e:
        raise TelegramFloodWait(e.seconds) from e

    if not channel_entities:
        return toon.empty_state(
            "channels",
            "for engagement ranking",
            ["subscribe to channels first"],
        )

    rankings: list[dict[str, Any]] = []

    for entity in channel_entities:
        handle = getattr(entity, "username", None)
        display = f"@{handle}" if handle else getattr(entity, "title", "?")
        subscribers = getattr(entity, "participants_count", None) or 0

        total_posts = 0
        total_views = 0
        total_reactions = 0
        total_replies = 0

        try:
            async for msg in client.iter_messages(entity, limit=100):
                if msg is None:
                    continue
                if msg.date and msg.date.timestamp() < cutoff:
                    break

                total_posts += 1
                total_views += msg.views or 0

                if msg.reactions and hasattr(msg.reactions, "results"):
                    for r in msg.reactions.results:
                        total_reactions += r.count

                if msg.replies and hasattr(msg.replies, "replies"):
                    total_replies += msg.replies.replies or 0
        except FloodWaitError as e:
            raise TelegramFloodWait(e.seconds) from e
        except (ChannelPrivateError, Exception) as exc:
            logger.warning("ops.engagement_ranking_channel_error", extra={"channel": display, "error": str(exc)})
            continue

        if total_posts == 0:
            continue

        engagement_rate = 0.0
        if total_views > 0:
            engagement_rate = (total_reactions + total_replies) / total_views * 100

        avg_views = total_views / total_posts

        rankings.append({
            "channel": display,
            "subscribers": subscribers,
            "posts": total_posts,
            "avg_views": int(avg_views),
            "engagement": engagement_rate,
            "reactions": total_reactions,
            "replies": total_replies,
        })

    if not rankings:
        return toon.empty_state(
            "channels",
            f"with posts in last {days} days",
            ["try a longer period", "subscribe to more channels"],
        )

    # Sort by engagement rate descending
    rankings.sort(key=lambda r: r["engagement"], reverse=True)
    rankings = rankings[:limit]

    fields = ["rank", "channel", "subscribers", "posts", "avg_views", "engagement", "reactions", "replies"]
    rows = []
    for rank, r in enumerate(rankings, 1):
        rows.append([
            rank,
            r["channel"],
            r["subscribers"],
            r["posts"],
            r["avg_views"],
            f"{r['engagement']:.2f}%",
            r["reactions"],
            r["replies"],
        ])

    return toon.format_response(
        type_name="ranking",
        fields=fields,
        rows=rows,
        summary_parts=[
            f"{len(rankings)} channels ranked",
            f"{days}d window",
        ],
        next_hints=[
            'Channel stats: tg_execute op="channel_stats" params={"channel": "@handle"}',
            'Compare: tg_execute op="compare_channels" params={"channels": "@a,@b"}',
        ],
    )
