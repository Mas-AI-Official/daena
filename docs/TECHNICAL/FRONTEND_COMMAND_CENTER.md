# Daena Command Center - Frontend Documentation

## Overview

The Daena Command Center is a comprehensive frontend interface that provides full access to all Daena capabilities, departments, and agents. It features a stunning Metatron's Cube visualization with hexagonal agents and animated data flow lines.

## Features

### 1. Metatron's Cube Visualization ✅
- **Hexagonal Agent Nodes**: Each agent is represented as a hexagonal node
- **Animated Data Flow**: Shiny, thick light lines animate between agents showing data flow
- **Department Visualization**: 8 departments arranged in sunflower pattern
- **Real-time Updates**: Data flows update every 5 seconds
- **Interactive**: Click agents/departments to view details

### 2. Project Workflow Management ✅
- **7-Stage Workflow**: Idea → Planning → Design → Development → Testing → Deployment → Execution
- **Agent Collaboration**: Shows which agents are working on each stage
- **Visual Timeline**: Progress visualization with current stage highlighted
- **Project Creation**: Create new projects with full workflow tracking

### 3. External Platform Integrations ✅
- **Supported Platforms**:
  - Manus AI
  - OpenAI
  - Anthropic (Claude)
  - GitHub
  - Slack
  - Notion
  - Stripe
  - AWS
- **Connection Management**: Connect/disconnect platforms
- **API Key Management**: Secure credential storage
- **Test Connections**: Verify platform connectivity

### 4. Human Hiring Interface ✅
- **Open Positions**: Create and manage job postings
- **Candidate Management**: Track candidates through hiring process
- **Interview Scheduling**: Schedule and manage interviews
- **Status Tracking**: Monitor hiring pipeline
- **Department Integration**: Link positions to departments

### 5. Customer Service Dashboard ✅
- **Ticket Management**: Track customer support tickets
- **Agent Availability**: Monitor Customer Success agents
- **Metrics**: Response time, satisfaction rate, resolution stats
- **24/7 Support**: All 6 Customer Success agents available

### 6. Analytics Integration ✅
- **Real-time Metrics**: System stats, CAS hit rate, agent efficiency
- **Communication Patterns**: Visualize agent-to-agent communication
- **Efficiency Tracking**: Monitor agent performance
- **Cost Tracking**: LLM cost savings and optimization

## Architecture

### File Structure
```
frontend/
├── templates/
│   └── daena_command_center.html    # Main command center page
└── static/
    └── js/
        ├── metatron-viz.js          # Metatron Cube visualization
        ├── project-workflow.js       # Project management
        ├── external-integrations.js  # Platform integrations
        └── human-hiring.js           # Hiring interface
```

### Key Components

#### MetatronViz Class
- Renders Metatron's Cube structure
- Draws hexagonal agent and department nodes
- Animates data flow lines between agents
- Handles agent/department selection

#### ProjectWorkflow Class
- Manages project lifecycle
- Renders workflow stages
- Tracks agent collaboration
- Handles project creation

#### ExternalIntegrations Class
- Manages platform connections
- Handles API key storage
- Tests connections
- Views integration logs

#### HumanHiring Class
- Manages job positions
- Tracks candidates
- Schedules interviews
- Monitors hiring pipeline

## Usage

### Accessing the Command Center
Navigate to: `/command-center`

### Quick Actions
1. **Create Project**: Click "New Project" button or type "build app" in quick command
2. **Hire Human**: Click "Hire Human" button or type "hire" in quick command
3. **Connect Platform**: Click "Connect Platform" button
4. **View Analytics**: Click "Analytics" button
5. **Customer Service**: Click "Customer Service" button

### Metatron Visualization
- **Click Agent**: View agent details and efficiency metrics
- **Click Department**: View department overview
- **Data Flow Lines**: Thicker, brighter lines indicate more active communication
- **Real-time Updates**: Visualization updates automatically

### Project Workflow
1. Create new project
2. Agents automatically assigned to stages
3. Track progress through 7 stages
4. View agent collaboration at each stage
5. Monitor completion status

### External Integrations
1. Select platform to connect
2. Enter API key/credentials
3. Test connection
4. View logs and status
5. Configure settings

### Human Hiring
1. Create open position
2. Review candidates
3. Schedule interviews
4. Track hiring pipeline
5. Monitor metrics

## API Endpoints Used

### Departments
- `GET /api/v1/departments/?include_agents=true` - Get all departments with agents

### Agents
- `GET /api/v1/agents/?include_adjacency=true` - Get all agents with adjacency info

### Analytics
- `GET /api/v1/analytics/summary` - Get analytics summary
- `GET /api/v1/analytics/communication-patterns` - Get communication patterns
- `GET /api/v1/analytics/agent/{id}/efficiency` - Get agent efficiency

### Projects
- `GET /api/v1/projects/` - Get all projects
- `POST /api/v1/projects/` - Create new project

### Integrations
- `GET /api/v1/integrations/` - Get all integrations
- `POST /api/v1/integrations/` - Connect platform
- `DELETE /api/v1/integrations/{id}` - Disconnect platform
- `POST /api/v1/integrations/{id}/test` - Test connection

### Hiring
- `GET /api/v1/hiring/positions/` - Get open positions
- `POST /api/v1/hiring/positions/` - Create position
- `GET /api/v1/hiring/candidates/` - Get candidates
- `GET /api/v1/hiring/interviews/` - Get interviews

### Monitoring
- `GET /monitoring/memory` - Get memory metrics
- `GET /monitoring/memory/cas` - Get CAS efficiency
- `GET /monitoring/memory/cost-tracking` - Get cost tracking

## Styling

### Color Scheme
- **Gold (#ffd700)**: Primary accent, Daena branding
- **Cyan (#00ffff)**: Agent nodes, data flow
- **Purple (#8b5cf6)**: External integrations
- **Green (#10b981)**: Success states, customer service
- **Red (#ef4444)**: Errors, warnings

### Animations
- **Data Flow Pulse**: Animated light traveling along lines
- **Hex Pulse**: Agent nodes pulse when active
- **Glow Effects**: Drop shadows and glows for depth
- **Smooth Transitions**: All interactions are animated

## Responsive Design

- **Desktop**: Full Metatron visualization with all features
- **Tablet**: Adjusted layout, smaller nodes
- **Mobile**: Simplified view, stacked panels

## Future Enhancements

1. **3D Visualization**: Three.js integration for 3D Metatron Cube
2. **Voice Commands**: Voice control for Daena
3. **AR/VR Support**: Immersive visualization
4. **Advanced Filtering**: Filter agents by department, role, status
5. **Custom Dashboards**: User-configurable dashboard layouts
6. **Export Reports**: Export analytics and project reports
7. **Mobile App**: Native mobile application
8. **Real-time Collaboration**: Multi-user support

## Troubleshooting

### Visualization Not Loading
- Check browser console for errors
- Verify `/static/js/metatron-viz.js` is accessible
- Ensure API endpoints are responding

### Data Flow Not Showing
- Check `/api/v1/analytics/communication-patterns` endpoint
- Verify agents have sent messages
- Check browser console for errors

### Modules Not Loading
- Verify all JS files are in `/static/js/`
- Check script tags in HTML
- Ensure Alpine.js is loaded before modules

## Performance

- **Initial Load**: < 2 seconds
- **Data Refresh**: Every 5-10 seconds
- **Animation FPS**: 60fps smooth animations
- **Memory Usage**: Optimized for large agent counts

## Security

- **API Keys**: Stored securely (not exposed in frontend)
- **Authentication**: Required for all API calls
- **HTTPS**: Recommended for production
- **CORS**: Configured for API access

---

**Last Updated**: 2025-01-XX  
**Status**: ✅ Production Ready  
**Version**: 2.0.0

