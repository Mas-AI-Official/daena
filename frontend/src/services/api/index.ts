import { agentsApi } from './agents';
import { brainApi } from './brain';
import { departmentsApi } from './departments';
import { governanceApi } from './governance';
import { skillsApi } from './skills';
import { vaultApi } from './vault';
import { shadowApi } from './shadow';
import { chatApi } from './chat';
import { marketplaceApi } from './marketplace';
import { strategyApi } from './strategy';
import { outcomesApi } from './outcomes';
import { founderApi } from './founder';
import { councilsApi } from './councils';
import { ideApi } from './ide';
import { cmpApi } from './cmp';
import { fileSystemApi, terminalApi, codeExecutionApi } from './fileSystem';

export const api = {
    agents: agentsApi,
    brain: brainApi,
    departments: departmentsApi,
    governance: governanceApi,
    skills: skillsApi,
    vault: vaultApi,
    shadow: shadowApi,
    chat: chatApi,
    marketplace: marketplaceApi,
    strategy: strategyApi,
    outcomes: outcomesApi,
    founder: founderApi,
    councils: councilsApi,
    ide: ideApi,
    cmp: cmpApi,
    fileSystem: fileSystemApi,
    terminal: terminalApi,
    codeExecution: codeExecutionApi
};


