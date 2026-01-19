"""
Council System Models
Defines the structure for Expert Councils
"""
from pydantic import BaseModel
from typing import List, Optional

class Expert(BaseModel):
    id: str
    name: str
    role: str  # e.g., "Investment Strategist"
    inspiration: str  # e.g., "Warren Buffett"
    avatar: str  # Icon or image path
    status: str = "active"  # active, inactive
    expertise: List[str]

class Council(BaseModel):
    id: str
    name: str  # e.g., "Finance Council"
    description: str
    icon: str
    color: str
    experts: List[Expert]
    status: str = "active"

# Initial Data (The "Top 5" Concept)
INITIAL_COUNCILS = [
    Council(
        id="finance",
        name="Finance Council",
        description="Global economic strategy and investment wisdom",
        icon="fa-chart-line",
        color="#00CED1",
        experts=[
            Expert(id="fin_1", name="The Oracle", role="Value Investor", inspiration="Warren Buffett", avatar="fa-user-tie", expertise=["Value Investing", "Long-term Strategy"]),
            Expert(id="fin_2", name="The Macro", role="Macro Economist", inspiration="Ray Dalio", avatar="fa-globe", expertise=["Global Macro", "Principles"]),
            Expert(id="fin_3", name="The Quant", role="Algorithmic Trader", inspiration="Jim Simons", avatar="fa-calculator", expertise=["Quant", "Math"]),
            Expert(id="fin_4", name="The Venture", role="VC Strategist", inspiration="Marc Andreessen", avatar="fa-rocket", expertise=["Startups", "Growth"]),
            Expert(id="fin_5", name="The Crypto", role="DeFi Expert", inspiration="Satoshi", avatar="fa-bitcoin", expertise=["Blockchain", "DeFi"])
        ]
    ),
    Council(
        id="tech",
        name="Tech Council",
        description="Technological innovation and future systems",
        icon="fa-microchip",
        color="#4169E1",
        experts=[
            Expert(id="tech_1", name="The Architect", role="Systems Architect", inspiration="Elon Musk", avatar="fa-space-shuttle", expertise=["First Principles", "Engineering"]),
            Expert(id="tech_2", name="The Visionary", role="AI Futurist", inspiration="Sam Altman", avatar="fa-brain", expertise=["AGI", "Scale"]),
            Expert(id="tech_3", name="The Builder", role="Software Engineer", inspiration="Linus Torvalds", avatar="fa-code", expertise=["Open Source", "Kernel"]),
            Expert(id="tech_4", name="The Product", role="Product Genius", inspiration="Steve Jobs", avatar="fa-mobile", expertise=["UX", "Design"]),
            Expert(id="tech_5", name="The Hacker", role="Security Expert", inspiration="Kevin Mitnick", avatar="fa-user-secret", expertise=["Security", "Exploits"])
        ]
    ),
    Council(
        id="strategy",
        name="Strategy Council",
        description="Business strategy and competitive intelligence",
        icon="fa-chess",
        color="#9370DB",
        experts=[
            Expert(id="strat_1", name="The Strategist", role="Competitive Analyst", inspiration="Michael Porter", avatar="fa-chess-king", expertise=["Competitive Strategy", "Industry Analysis"]),
            Expert(id="strat_2", name="The Disruptor", role="Innovation Lead", inspiration="Clayton Christensen", avatar="fa-bolt", expertise=["Disruption", "Innovation"]),
            Expert(id="strat_3", name="The Executor", role="Operations Expert", inspiration="Jeff Bezos", avatar="fa-cogs", expertise=["Operations", "Execution"]),
            Expert(id="strat_4", name="The Growth", role="Growth Strategist", inspiration="Reid Hoffman", avatar="fa-chart-line", expertise=["Scaling", "Network Effects"]),
            Expert(id="strat_5", name="The Pivot", role="Turnaround Specialist", inspiration="Lou Gerstner", avatar="fa-sync", expertise=["Turnaround", "Transformation"])
        ]
    ),
    Council(
        id="psychology",
        name="Psychology Council",
        description="Human behavior and organizational dynamics",
        icon="fa-brain",
        color="#FF6B6B",
        experts=[
            Expert(id="psych_1", name="The Behaviorist", role="Behavioral Economist", inspiration="Daniel Kahneman", avatar="fa-lightbulb", expertise=["Behavioral Economics", "Decision Making"]),
            Expert(id="psych_2", name="The Motivator", role="Leadership Coach", inspiration="Tony Robbins", avatar="fa-fire", expertise=["Motivation", "Peak Performance"]),
            Expert(id="psych_3", name="The Communicator", role="Communication Expert", inspiration="Dale Carnegie", avatar="fa-comments", expertise=["Communication", "Influence"]),
            Expert(id="psych_4", name="The Mindset", role="Growth Mindset Coach", inspiration="Carol Dweck", avatar="fa-seedling", expertise=["Mindset", "Learning"]),
            Expert(id="psych_5", name="The Flow", role="Performance Psychologist", inspiration="Mihaly Csikszentmihalyi", avatar="fa-water", expertise=["Flow State", "Creativity"])
        ]
    ),
]
