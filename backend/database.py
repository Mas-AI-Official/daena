from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, Text, Boolean, Float, text
try:
    from sqlalchemy.dialects.sqlite import JSON
except ImportError:
    # Fallback for older SQLAlchemy
    from sqlalchemy import JSON
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
import datetime

# Create SQLAlchemy engine (SQLite for development, easy to switch to MongoDB later)
# Use WAL mode for better concurrency and immediate visibility of commits
engine = create_engine(
    "sqlite:///./daena.db", 
    connect_args={
        "check_same_thread": False,
        "timeout": 30.0,  # Increase timeout to prevent locks
        "isolation_level": None  # Disable transactions for WAL mode
    },
    pool_pre_ping=True,  # Verify connections before using
    pool_size=10,  # Connection pool size
    max_overflow=20,  # Allow overflow connections
    pool_recycle=3600  # Recycle connections after 1 hour
)
# Enable WAL mode for better concurrency
from sqlalchemy import event
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Dependency to get DB session (for FastAPI routes)
def get_db():
    """Get database session. Use with FastAPI Depends() or as next(get_db())"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Create declarative base
Base = declarative_base()

# Example User model
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    password_hash = Column(String)
    role = Column(String, default="user")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

# New Department model with sunflower coordinates
class Department(Base):
    __tablename__ = "departments"
    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String, unique=True, index=True)
    name = Column(String, unique=True, index=True)
    description = Column(Text)
    color = Column(String, default="#0066cc")
    sunflower_index = Column(Integer, unique=True, index=True)
    cell_id = Column(String, unique=True, index=True)
    status = Column(String, default="active")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    agents = relationship("Agent", back_populates="department_ref")

# Enhanced Agent model with brain training capabilities and sunflower coordinates
class Agent(Base):
    __tablename__ = "agents"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    department = Column(String, default="general")
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)  # ADDED: Tenant isolation
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True, index=True)  # ADDED: Project scoping
    status = Column(String, default="idle")
    type = Column(String)
    role = Column(String, index=True)
    capabilities = Column(Text)
    description = Column(Text)
    is_active = Column(Boolean, default=True)
    sunflower_index = Column(Integer, index=True)
    cell_id = Column(String, unique=True, index=True)
    brain_model_id = Column(Integer, ForeignKey("brain_models.id"), nullable=True)
    training_status = Column(String, default="untrained")
    performance_score = Column(Float, default=0.0)
    voice_id = Column(String, nullable=True)  # Voice clone ID
    last_seen = Column(DateTime, nullable=True)  # Last activity timestamp
    metadata_json = Column(JSON, default={})  # Additional metadata
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    brain_model = relationship("BrainModel", back_populates="agents")
    department_ref = relationship("Department", back_populates="agents")

# Enhanced Brain Model for multi-LLM training with R1/R2 support
class BrainModel(Base):
    __tablename__ = "brain_models"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    model_type = Column(String)  # "r1", "r2", "deepseek_v3", "qwen", "yi", "hybrid", "openai_gpt4"
    model_path = Column(String, nullable=True)  # Local path or cloud endpoint
    provider = Column(String)  # "local", "azure", "huggingface", "anthropic", "openai"
    api_key = Column(String, nullable=True)
    config = Column(JSON)  # Model-specific configuration
    status = Column(String, default="available")  # available, training, error, offline
    performance_metrics = Column(JSON, default={})
    last_used = Column(DateTime, nullable=True)
    model_size = Column(String, nullable=True)  # "7B", "14B", "70B", etc.
    context_length = Column(Integer, default=4096)
    is_quantized = Column(Boolean, default=False)
    quantization_type = Column(String, nullable=True)  # "int8", "int4", "gguf", etc.
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    agents = relationship("Agent", back_populates="brain_model")
    training_sessions = relationship("TrainingSession", back_populates="brain_model")
    consensus_votes = relationship("ConsensusVote", back_populates="brain_model")
    model_checkpoints = relationship("ModelCheckpoint", back_populates="brain_model")

# New: Adjacency table for honeycomb routing
class CellAdjacency(Base):
    __tablename__ = "cell_adjacency"
    id = Column(Integer, primary_key=True, index=True)
    cell_id = Column(String, index=True)
    neighbor_id = Column(String, index=True)
    distance = Column(Float)
    relationship_type = Column(String, default="neighbor")  # neighbor, parent, child
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    __table_args__ = (
        # Ensure unique relationships
        {'sqlite_autoincrement': True},
    )

# New: Model Checkpoints for training progress
class ModelCheckpoint(Base):
    __tablename__ = "model_checkpoints"
    id = Column(Integer, primary_key=True, index=True)
    brain_model_id = Column(Integer, ForeignKey("brain_models.id"))
    checkpoint_name = Column(String)
    checkpoint_path = Column(String)
    training_step = Column(Integer, default=0)
    loss_value = Column(Float, nullable=True)
    accuracy_score = Column(Float, nullable=True)
    checkpoint_metadata = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    brain_model = relationship("BrainModel", back_populates="model_checkpoints")

# Enhanced Training Sessions for brain development
class TrainingSession(Base):
    __tablename__ = "training_sessions"
    id = Column(Integer, primary_key=True, index=True)
    brain_model_id = Column(Integer, ForeignKey("brain_models.id"))
    session_type = Column(String)  # "conversation", "decision", "strategy", "knowledge", "reasoning"
    training_data = Column(JSON)
    parameters = Column(JSON)  # Training parameters
    status = Column(String, default="running")  # running, completed, failed, paused
    start_time = Column(DateTime, default=datetime.datetime.utcnow)
    end_time = Column(DateTime, nullable=True)
    metrics = Column(JSON, default={})  # Training metrics
    loss_history = Column(JSON, default=[])
    learning_rate = Column(Float, nullable=True)
    batch_size = Column(Integer, nullable=True)
    epochs_completed = Column(Integer, default=0)
    total_epochs = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    brain_model = relationship("BrainModel", back_populates="training_sessions")

# Enhanced Consensus System for multi-LLM decisions
class ConsensusVote(Base):
    __tablename__ = "consensus_votes"
    id = Column(Integer, primary_key=True, index=True)
    topic_id = Column(String, index=True)  # Unique topic identifier
    brain_model_id = Column(Integer, ForeignKey("brain_models.id"))
    vote = Column(Text)  # The model's decision/vote
    confidence = Column(Float, default=0.0)  # Confidence score
    reasoning = Column(Text, nullable=True)  # Explanation for the vote
    vote_weight = Column(Float, default=1.0)  # Weight for this model's vote
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    
    brain_model = relationship("BrainModel", back_populates="consensus_votes")

# New: Consensus Topics for organizing votes
class ConsensusTopic(Base):
    __tablename__ = "consensus_topics"
    id = Column(Integer, primary_key=True, index=True)
    topic_id = Column(String, unique=True, index=True)
    title = Column(String)
    description = Column(Text)
    category = Column(String)  # "business", "technical", "strategy", "investment"
    status = Column(String, default="active")  # active, resolved, archived
    required_consensus = Column(Float, default=0.7)  # Minimum consensus threshold
    deadline = Column(DateTime, nullable=True)
    final_decision = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)

# Enhanced Knowledge Base for training data
class KnowledgeEntry(Base):
    __tablename__ = "knowledge_entries"
    id = Column(Integer, primary_key=True, index=True)
    category = Column(String, index=True)  # "company", "market", "technology", "strategy", "investor"
    title = Column(String)
    content = Column(Text)
    source = Column(String, nullable=True)
    tags = Column(JSON, default=[])
    importance_score = Column(Float, default=0.0)
    embedding_vector = Column(Text, nullable=True)  # Vector representation for similarity search
    last_accessed = Column(DateTime, nullable=True)
    access_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

# New: Training Data Sources
class TrainingDataSource(Base):
    __tablename__ = "training_data_sources"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True)
    source_type = Column(String)  # "file", "api", "database", "web_scrape"
    source_path = Column(String)
    format_type = Column(String)  # "json", "csv", "txt", "jsonl"
    is_active = Column(Boolean, default=True)
    last_sync = Column(DateTime, nullable=True)
    sync_frequency = Column(Integer, default=3600)  # seconds
    source_metadata = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

# New: Model Performance Tracking
class ModelPerformance(Base):
    __tablename__ = "model_performance"
    id = Column(Integer, primary_key=True, index=True)
    brain_model_id = Column(Integer, ForeignKey("brain_models.id"))
    metric_name = Column(String)  # "accuracy", "latency", "throughput", "memory_usage"
    metric_value = Column(Float)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    context = Column(JSON, default={})  # Additional context for the metric

# Enhanced Conversation History
class ConversationHistory(Base):
    __tablename__ = "conversation_history"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, index=True)
    user_message = Column(Text)
    daena_response = Column(Text)
    brain_model_used = Column(String, nullable=True)
    context = Column(JSON, default={})
    feedback_score = Column(Float, nullable=True)
    response_time_ms = Column(Integer, nullable=True)
    tokens_used = Column(Integer, nullable=True)
    cost_estimate = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

# Tool Execution Logging for Daena learning
class ToolExecution(Base):
    """Logs all tool executions for pattern learning and auditing"""
    __tablename__ = "tool_executions"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, index=True, nullable=True)
    user_message = Column(Text)  # What triggered the tool
    tool_name = Column(String, index=True)  # e.g., "web_search", "browser", "diagnostics"
    tool_action = Column(String, nullable=True)  # e.g., "search", "navigate", "full_check"
    tool_input = Column(JSON, default={})  # Input parameters
    tool_output = Column(JSON, default={})  # Result from tool
    success = Column(Boolean, default=True)
    error_message = Column(Text, nullable=True)
    execution_time_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

# Enhanced Consultation model
class Consultation(Base):
    __tablename__ = "consultations"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    topic = Column(String)
    start_time = Column(DateTime)
    duration = Column(Integer)
    notes = Column(Text)
    status = Column(String, default="scheduled")
    brain_models_used = Column(JSON, default=[])  # List of models used during consultation
    consensus_required = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    end_time = Column(DateTime, nullable=True)

    user = relationship("User")
    messages = relationship("Message", back_populates="consultation")

# Enhanced Message model
class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, index=True)
    consultation_id = Column(Integer, ForeignKey("consultations.id"))
    sender = Column(String)
    content = Column(Text)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    message_type = Column(String, default="text")  # text, voice, image, file
    brain_model_used = Column(String, nullable=True)
    confidence_score = Column(Float, nullable=True)

    consultation = relationship("Consultation", back_populates="messages")

# Decision Management
class Decision(Base):
    __tablename__ = "decisions"
    id = Column(Integer, primary_key=True, index=True)
    decision_id = Column(String, unique=True, index=True)
    title = Column(String)
    description = Column(Text)
    decision_type = Column(String)  # security_override, resource_allocation, process_improvement, etc.
    impact = Column(String)  # high, medium, low
    reasoning = Column(Text)
    agents_involved = Column(Integer, default=0)
    departments_affected = Column(JSON, default=[])
    override_previous_decision = Column(Boolean, default=False)
    risk_assessment = Column(Text)
    metrics_impact = Column(JSON, default={})
    related_projects = Column(JSON, default=[])
    related_agents = Column(JSON, default=[])
    status = Column(String, default="pending")  # pending, approved, rejected, implemented
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    implemented_at = Column(DateTime, nullable=True)
    created_by = Column(String, default="daena")

# New: Tenant/Customer Model for Multi-Tenant Isolation
class Tenant(Base):
    __tablename__ = "tenants"
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String, unique=True, index=True)  # Unique tenant identifier
    name = Column(String, nullable=False)
    company_name = Column(String, nullable=True)
    email = Column(String, nullable=True)
    status = Column(String, default="active")  # active, suspended, inactive
    subscription_tier = Column(String, default="standard")  # standard, premium, enterprise
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    projects = relationship("Project", back_populates="tenant")

# New: Project Model (scoped to Tenant)
class Project(Base):
    __tablename__ = "projects"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(String, unique=True, index=True)  # Unique project identifier
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String, default="active")  # active, completed, paused, cancelled
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    tenant = relationship("Tenant", back_populates="projects")
    department = relationship("Department")

# New: System Configuration
class SystemConfig(Base):
    __tablename__ = "system_config"
    id = Column(Integer, primary_key=True, index=True)
    config_key = Column(String, unique=True, index=True)
    config_value = Column(Text)
    config_type = Column(String, default="string")  # string, int, float, bool, json
    description = Column(Text, nullable=True)
    is_sensitive = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

# NEW: Task table (replaces in-memory tasks_db)
class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String, unique=True, index=True)
    owner_type = Column(String, default="agent")  # agent, department, system
    owner_id = Column(String, nullable=True)
    department_id = Column(String, nullable=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String, default="pending")  # pending, running, completed, failed
    priority = Column(String, default="medium")  # low, medium, high, urgent
    progress = Column(Float, default=0.0)
    payload_json = Column(JSON, default={})
    result_json = Column(JSON, default={})
    assigned_agent_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

# NEW: ChatCategory table for organizing chat sessions
class ChatCategory(Base):
    __tablename__ = "chat_categories"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)  # executive, departments, agents, general
    description = Column(Text, nullable=True)
    icon = Column(String, nullable=True)
    color = Column(String, nullable=True)
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

# NEW: ChatSession table (replaces in-memory active_sessions)
class ChatSession(Base):
    __tablename__ = "chat_sessions"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, unique=True, index=True)
    category_id = Column(Integer, ForeignKey("chat_categories.id"), nullable=True)
    category = Column(String, default="general")  # executive, departments, agents, general (for backward compat)
    title = Column(String, default="New Chat")
    owner_type = Column(String, default="user")  # user, agent, department
    owner_id = Column(String, nullable=True)  # department_id, agent_id, etc.
    
    # Explicit fields for filtering
    department_id = Column(String, nullable=True, index=True)
    agent_id = Column(String, nullable=True, index=True)
    
    scope_type = Column(String, default="general")  # executive, general, department, agent
    scope_id = Column(String, nullable=True)  # HR, Legal, agent_123, etc.
    context_json = Column(JSON, default={})
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")
    category_ref = relationship("ChatCategory", foreign_keys=[category_id])

# NEW: ChatMessage table
class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, ForeignKey("chat_sessions.session_id"), index=True)
    role = Column(String, nullable=False)  # user, assistant
    content = Column(Text, nullable=False)
    model = Column(String, nullable=True)
    tokens = Column(Integer, nullable=True)
    response_time_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    session = relationship("ChatSession", back_populates="messages")

# NEW: EventLog table (for audit trail + WebSocket replay)
class EventLog(Base):
    __tablename__ = "event_log"
    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String, index=True)  # agent.created, task.progress, etc.
    entity_type = Column(String, index=True)  # agent, task, department, chat
    entity_id = Column(String, index=True)
    payload_json = Column(JSON, default={})
    created_by = Column(String, default="system")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

# NEW: LearningLog table (tracks what Daena/agents learn)
class LearningLog(Base):
    __tablename__ = "learning_log"
    id = Column(Integer, primary_key=True, index=True)
    learned_at = Column(DateTime, default=datetime.datetime.utcnow)
    learned_by = Column(String, default="daena", index=True)  # "daena", agent_id, etc.
    category = Column(String, index=True)  # "tool_usage", "pattern", "preference", "knowledge"
    summary = Column(Text)  # Human-readable summary
    details_json = Column(JSON, default={})  # Full details
    approved = Column(Boolean, default=False)  # Founder approval for permanent learning
    approved_at = Column(DateTime, nullable=True)
    approved_by = Column(String, nullable=True)  # Who approved
    permanent = Column(Boolean, default=False)  # Whether this learning is permanent

# NEW: PendingApproval table (tracks pending tool approvals)
class PendingApproval(Base):
    __tablename__ = "pending_approvals"
    id = Column(Integer, primary_key=True, index=True)
    approval_id = Column(String, unique=True, index=True)
    executor_id = Column(String, index=True)  # daena, agent_id, council_id
    executor_type = Column(String)  # daena, agent, council
    tool_name = Column(String)
    action = Column(String)
    args_json = Column(JSON, default={})
    impact_level = Column(String)  # low, medium, high, critical
    status = Column(String, default="pending", index=True)  # pending, approved, rejected
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(String, nullable=True)

# NOTE: ChatCategory is already defined above at line 377 - removed duplicate

# NEW: Council table (DB-backed council entities)
class Council(Base):
    __tablename__ = "councils"
    id = Column(Integer, primary_key=True, index=True)
    council_id = Column(String, unique=True, index=True)  # e.g., "C1", "C2"
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    member_agent_ids = Column(JSON, default=[])  # List of agent cell_ids
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

# NEW: CouncilCategory table
class CouncilCategory(Base):
    __tablename__ = "council_categories"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    enabled = Column(Boolean, default=True)
    metadata_json = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    members = relationship("CouncilMember", back_populates="category", cascade="all, delete-orphan")

# NEW: CouncilMember table
class CouncilMember(Base):
    __tablename__ = "council_members"
    id = Column(Integer, primary_key=True, index=True)
    category_id = Column(Integer, ForeignKey("council_categories.id"), index=True)
    name = Column(String, nullable=False)
    persona_source = Column(String, nullable=True)  # inspiration person
    enabled = Column(Boolean, default=True)
    settings_json = Column(JSON, default={})  # training notes, settings
    display_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    category = relationship("CouncilCategory", back_populates="members")

# NEW: Connection table (tool/integration connections)
class Connection(Base):
    __tablename__ = "connections"
    id = Column(Integer, primary_key=True, index=True)
    tool_name = Column(String, index=True)
    status = Column(String, default="disconnected")  # connected, disconnected, error
    settings_json = Column(JSON, default={})  # auth, config
    last_checked = Column(DateTime, nullable=True)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

# NEW: VoiceState table
class VoiceState(Base):
    __tablename__ = "voice_state"
    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(String, nullable=True, index=True)  # null = Daena
    voice_id = Column(String, nullable=True)  # voice clone ID
    voice_file_path = Column(String, nullable=True)  # path to voice file
    is_active = Column(Boolean, default=False)
    settings_json = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

# ═══════════════════════════════════════════════════════════════════════
# QA GUARDIAN MODELS - Hidden Department for Quality Assurance
# ═══════════════════════════════════════════════════════════════════════

# QA Guardian Incident table
class QAIncident(Base):
    """QA Guardian Incident - tracked issues and errors"""
    __tablename__ = "qa_incidents"
    id = Column(Integer, primary_key=True, index=True)
    incident_id = Column(String, unique=True, index=True)  # e.g., "inc_20260121_abc123"
    idempotency_key = Column(String, unique=True, index=True)  # For deduplication
    
    # Classification
    severity = Column(String, index=True)  # P0, P1, P2, P3, P4
    risk_level = Column(String, default="LOW")  # CRITICAL, HIGH, MEDIUM, LOW
    category = Column(String, index=True)  # bug, config, security, dependency, data, workflow, agent_conflict
    subsystem = Column(String, index=True)  # api, services, database, etc.
    source = Column(String)  # runtime, ci, user_report, scheduled_scan
    
    # Affected entities
    affected_agent = Column(String, nullable=True, index=True)
    affected_department = Column(String, nullable=True, index=True)
    
    # Details
    summary = Column(String, nullable=False)
    description = Column(Text)
    evidence_json = Column(JSON, default=[])  # List of Evidence objects
    suspected_root_cause = Column(Text, nullable=True)
    reproduction_steps_json = Column(JSON, default=[])
    
    # Response
    proposed_actions_json = Column(JSON, default=[])
    approval_required = Column(Boolean, default=False)
    owner = Column(String, nullable=True)
    
    # Lifecycle
    status = Column(String, default="open", index=True)  # open, triaging, proposed, awaiting_approval, verified, committed, rolled_back, closed
    resolution = Column(Text, nullable=True)
    closed_at = Column(DateTime, nullable=True)
    
    # Locking
    locked_by = Column(String, nullable=True)
    locked_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


# QA Guardian Patch Proposal table
class QAPatchProposal(Base):
    """QA Guardian Patch Proposal - two-phase commit patches"""
    __tablename__ = "qa_patch_proposals"
    id = Column(Integer, primary_key=True, index=True)
    proposal_id = Column(String, unique=True, index=True)  # e.g., "patch_20260121_abc123"
    incident_id = Column(String, ForeignKey("qa_incidents.incident_id"), index=True)
    
    # Changes
    files_json = Column(JSON, default=[])  # List of FileChange objects
    
    # Plans
    verification_plan_json = Column(JSON, default={})
    rollback_plan_json = Column(JSON, default={})
    
    # Assessment
    risk_level = Column(String)  # CRITICAL, HIGH, MEDIUM, LOW
    deny_list_touched_json = Column(JSON, default=[])
    estimated_impact = Column(Text, nullable=True)
    
    # Status
    status = Column(String, default="proposed", index=True)  # proposed, verifying, verified, awaiting_approval, applying, applied, failed, rolled_back
    verification_result_json = Column(JSON, nullable=True)
    
    # Execution
    applied_at = Column(DateTime, nullable=True)
    applied_by = Column(String, nullable=True)
    approval_by = Column(String, nullable=True)
    approval_reason = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


# QA Guardian Audit Log table
class QAAuditLog(Base):
    """QA Guardian Audit Log - structured logging for all actions"""
    __tablename__ = "qa_audit_log"
    id = Column(Integer, primary_key=True, index=True)
    
    # Event identification
    event_id = Column(String, unique=True, index=True)
    action = Column(String, index=True)  # incident_created, decision_made, patch_applied, etc.
    
    # Context
    incident_id = Column(String, nullable=True, index=True)
    proposal_id = Column(String, nullable=True, index=True)
    agent_id = Column(String, nullable=True, index=True)
    
    # Details
    severity = Column(String, nullable=True)
    details_json = Column(JSON, default={})  # Full event details
    
    # Actor
    actor = Column(String, default="qa_guardian")  # Who performed the action
    
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)


# NEW: Skill model (replaces in-memory skill_registry)
class Skill(Base):
    __tablename__ = "skills"
    id = Column(String, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    display_name = Column(String)
    description = Column(Text)
    category = Column(String)
    creator = Column(String)
    creator_agent_id = Column(String)
    status = Column(String, default="active")
    input_schema = Column(JSON, default={})
    output_schema = Column(JSON, default={})
    code_body = Column(Text)
    risk_level = Column(String, default="low")
    approval_policy = Column(String, default="auto") # auto | needs_approval | always
    allowed_operators = Column(JSON, default=["founder", "daena"]) # ["founder", "daena", "agent"]
    allowed_departments = Column(JSON, default=[])
    allowed_agents = Column(JSON, default=[])
    enabled = Column(Boolean, default=True)
    archived = Column(Boolean, default=False)
    usage_count = Column(Integer, default=0)
    last_used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

# NEW: Skill Audit Log
class SkillAuditLog(Base):
    __tablename__ = "skill_audit_logs"
    id = Column(Integer, primary_key=True, index=True)
    skill_id = Column(String, index=True)
    action = Column(String) # create, update, delete, enable, disable
    changed_by = Column(String)
    before_json = Column(JSON, nullable=True)
    after_json = Column(JSON, nullable=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    ip_address = Column(String, nullable=True)
    session_id = Column(String, nullable=True)

# ENHANCE: Department - add hidden field
# Note: We'll need to add this via migration, but for now we'll use status field
# Department.status can be "active", "hidden", "disabled"

# ENHANCE: Agent - add voice_id, last_seen, metadata_json
# Note: Agent already has most fields, but we may need to add voice_id

# Database session
def get_db():
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Create all tables
def create_tables():
    Base.metadata.create_all(bind=engine)
    
    # Simple migration: attempt to add new columns to existing tables if missing
    # This is a basic way to handle updates without a full migration system like Alembic
    try:
        from sqlalchemy import inspect
        inspector = inspect(engine)
        
        # Check 'skills' table columns
        if 'skills' in inspector.get_table_names():
            columns = [c['name'] for c in inspector.get_columns('skills')]
            with engine.connect() as conn:
                if 'allowed_operators' not in columns:
                    conn.execute(text("ALTER TABLE skills ADD COLUMN allowed_operators JSON"))
                if 'approval_policy' not in columns:
                    conn.execute(text("ALTER TABLE skills ADD COLUMN approval_policy VARCHAR DEFAULT 'auto'"))
                # Commit is automatic in autocommit=True engines or handled by context
    except Exception as e:
        print(f"Migration warning: {e}")

# Initialize default data
def initialize_default_data():
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        # Add default system configurations
        default_configs = [
            {"key": "default_brain_model", "value": "openai_gpt4", "type": "string", "description": "Default brain model for Daena"},
            {"key": "consensus_threshold", "value": "0.7", "type": "float", "description": "Default consensus threshold for decisions"},
            {"key": "max_training_epochs", "value": "10", "type": "int", "description": "Maximum training epochs for brain models"},
            {"key": "enable_voice", "value": "true", "type": "bool", "description": "Enable voice interaction"},
            {"key": "enable_cmp", "value": "true", "type": "bool", "description": "Enable CMP decision engine"},
        ]
        
        for config in default_configs:
            existing = db.query(SystemConfig).filter(SystemConfig.config_key == config["key"]).first()
            if not existing:
                db_config = SystemConfig(
                    config_key=config["key"],
                    config_value=config["value"],
                    config_type=config["type"],
                    description=config["description"]
                )
                db.add(db_config)
        
        db.commit()
        
    except Exception as e:
        print(f"Error initializing default data: {e}")
        db.rollback()
    finally:
        db.close() 