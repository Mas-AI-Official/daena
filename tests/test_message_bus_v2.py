"""
Tests for Message Bus V2 with topic-based pub/sub.
"""

from __future__ import annotations

import asyncio
from typing import List

import pytest

from backend.utils.message_bus_v2 import MessageBusV2, TopicMessage


@pytest.fixture
def bus():
    """Create a message bus instance."""
    return MessageBusV2()


@pytest.mark.asyncio
async def test_topic_subscription(bus):
    """Test topic subscription and message delivery."""
    await bus.start()
    
    received_messages: List[TopicMessage] = []
    
    async def handler(message: TopicMessage):
        received_messages.append(message)
    
    # Subscribe to exact topic
    bus.subscribe("cell/engineering/A1", handler)
    
    # Publish message
    await bus.publish(
        "cell/engineering/A1",
        {"content": "test"},
        sender="test_agent"
    )
    
    # Give handlers time to process
    await asyncio.sleep(0.1)
    
    assert len(received_messages) == 1
    assert received_messages[0].topic == "cell/engineering/A1"
    assert received_messages[0].sender == "test_agent"
    
    await bus.stop()


@pytest.mark.asyncio
async def test_wildcard_subscription(bus):
    """Test wildcard topic subscription."""
    await bus.start()
    
    received_messages: List[TopicMessage] = []
    
    async def handler(message: TopicMessage):
        received_messages.append(message)
    
    # Subscribe to wildcard pattern
    bus.subscribe("cell/engineering/*", handler)
    
    # Publish to multiple cells
    await bus.publish("cell/engineering/A1", {"content": "test1"}, sender="agent1")
    await bus.publish("cell/engineering/A2", {"content": "test2"}, sender="agent2")
    await bus.publish("cell/marketing/A1", {"content": "test3"}, sender="agent3")
    
    # Give handlers time to process
    await asyncio.sleep(0.1)
    
    # Should receive messages from engineering cells only
    assert len(received_messages) == 2
    assert all(msg.topic.startswith("cell/engineering/") for msg in received_messages)
    
    await bus.stop()


@pytest.mark.asyncio
async def test_ring_topic(bus):
    """Test ring topic publishing."""
    await bus.start()
    
    received_messages: List[TopicMessage] = []
    
    async def handler(message: TopicMessage):
        received_messages.append(message)
    
    bus.subscribe("ring/1", handler)
    
    await bus.publish_to_ring(1, {"content": "ring message"}, sender="ring_agent")
    await asyncio.sleep(0.1)
    
    assert len(received_messages) == 1
    assert received_messages[0].topic == "ring/1"
    
    await bus.stop()


@pytest.mark.asyncio
async def test_radial_topic(bus):
    """Test radial topic publishing."""
    await bus.start()
    
    received_messages: List[TopicMessage] = []
    
    async def handler(message: TopicMessage):
        received_messages.append(message)
    
    bus.subscribe("radial/north", handler)
    
    await bus.publish_to_radial("north", {"content": "radial message"}, sender="radial_agent")
    await asyncio.sleep(0.1)
    
    assert len(received_messages) == 1
    assert received_messages[0].topic == "radial/north"
    
    await bus.stop()


@pytest.mark.asyncio
async def test_global_topic(bus):
    """Test global CMP topic publishing."""
    await bus.start()
    
    received_messages: List[TopicMessage] = []
    
    async def handler(message: TopicMessage):
        received_messages.append(message)
    
    bus.subscribe("global/cmp", handler)
    
    await bus.publish_to_global({"content": "global message"}, sender="global_agent")
    await asyncio.sleep(0.1)
    
    assert len(received_messages) == 1
    assert received_messages[0].topic == "global/cmp"
    
    await bus.stop()


@pytest.mark.asyncio
async def test_rate_limiting(bus):
    """Test rate limiting per topic."""
    await bus.start()
    
    # Publish many messages rapidly
    for i in range(150):  # More than default limit of 100
        result = await bus.publish(
            "test/topic",
            {"content": f"message_{i}"},
            sender="test_agent"
        )
    
    # Should have rate limiting applied
    stats = bus.get_stats()
    assert stats["total_messages"] <= 100  # Rate limited


@pytest.mark.asyncio
async def test_message_history(bus):
    """Test message history tracking."""
    await bus.start()
    
    # Publish several messages
    for i in range(5):
        await bus.publish(f"topic_{i}", {"content": f"msg_{i}"}, sender="test")
    
    # Get history
    history = bus.get_message_history(limit=10)
    assert len(history) == 5
    
    # Filter by topic
    topic_history = bus.get_message_history(topic="topic_1", limit=10)
    assert len(topic_history) == 1
    assert topic_history[0].topic == "topic_1"

