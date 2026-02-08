import { BrowserRouter, Routes, Route, Navigate, Outlet } from 'react-router-dom';
import { PageLayout } from './components/layout/PageLayout';
import { Dashboard } from './components/dashboard/Dashboard';

import { ChatInterface } from './components/chat/ChatInterface';
import { BrainStatus } from './components/brain/BrainStatus';
import { DepartmentGrid } from './components/departments/DepartmentGrid';
import { DepartmentDetail } from './components/departments/DepartmentDetail';
import { SkillRegistry } from './components/skills/SkillRegistry';
import { GovernanceConsole } from './components/governance/GovernanceConsole';
import { SecureVault } from './components/vault/SecureVault';
import { IDEContainer } from './components/ide/IDEContainer';
// import { ShadowDashboard } from './components/shadow/ShadowDashboard'; // Replaced by ObsidianDashboard
import { CMPDashboard } from './components/cmp/CMPDashboard';
import { MemoryExplorer } from './components/brain/MemoryExplorer';
import { OutcomeDashboard } from './components/brain/OutcomeDashboard';
import { IntegrityConsole } from './components/brain/IntegrityConsole';
import { TreasuryDashboard } from './components/treasury/TreasuryDashboard';
import { StrategyDashboard } from './components/strategy/StrategyDashboard';
import { MarketplaceDashboard } from './components/marketplace/MarketplaceDashboard';
import { Login } from './components/auth/Login';
import { ProtectedRoute } from './components/auth/ProtectedRoute';
import { useEffect } from 'react';
import { wsService } from './services/websocket';
import { AgentDetailModal } from './components/agents/AgentDetailModal';
import { VoiceNavigator } from './components/layout/VoiceNavigator';
import { ErrorBoundary } from './components/common/ErrorBoundary';

// New Feature Imports
import { QuintessencePanel } from './components/quintessence/QuintessencePanel';
import { ObsidianDashboard } from './components/shadow/ObsidianDashboard';
import { FounderControlPanel } from './components/founder/FounderControlPanel';
import { SelfFixConsole } from './components/governance/SelfFixConsole';

function App() {
  useEffect(() => {
    wsService.connect();
    return () => wsService.disconnect();
  }, []);

  return (
    <ErrorBoundary>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />

          <Route element={<ProtectedRoute />}>
            <Route element={<><PageLayout /><AgentDetailModal /><VoiceNavigator /></>}>
              <Route path="/" element={<Dashboard />} />
              <Route path="/chat" element={<ChatInterface />} />
              <Route path="/departments" element={<DepartmentGrid />} />
              <Route path="/departments/:id" element={<DepartmentDetail />} />
              <Route path="/skills" element={<SkillRegistry />} />
              <Route path="/governance" element={<GovernanceConsole />} />
              <Route path="/brain" element={<BrainStatus />} />
              <Route path="/vault" element={<SecureVault />} />
              <Route path="/ide" element={<IDEContainer />} />
              {/* <Route path="/shadow" element={<ShadowDashboard />} /> */}
              <Route path="/cmp" element={<CMPDashboard />} />
              <Route path="/memory" element={<MemoryExplorer />} />
              <Route path="/outcomes" element={<OutcomeDashboard />} />
              <Route path="/integrity" element={<IntegrityConsole />} />
              <Route path="/treasury" element={<TreasuryDashboard />} />
              <Route path="/strategy" element={<StrategyDashboard />} />
              <Route path="/marketplace" element={<MarketplaceDashboard />} />

              {/* New Routes */}
              <Route path="/quintessence" element={<QuintessencePanel />} />
              <Route path="/shadow" element={<ObsidianDashboard />} />
              <Route path="/founder" element={<FounderControlPanel />} />

              <Route path="/self-fix" element={<SelfFixConsole />} />
            </Route>
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </ErrorBoundary>
  )
}

export default App

