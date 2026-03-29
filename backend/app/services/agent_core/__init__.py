"""Agent Core -- the autonomous brain loop.

ReAct (Reason + Act) execution loop that makes Daena autonomous.
Unlike single-shot CLI invocations, the AgentLoop persists across
multiple steps, observes results, handles errors, and iterates
until the task is complete.
"""
