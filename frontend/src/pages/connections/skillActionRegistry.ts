/**
 * skillActionRegistry -- Phase 1 skill execution spine.
 *
 * PR-CONN-PLUGIN-SKILLS-EXECUTION-PHASE1 (2026-05-03). Wires plugin
 * default_skill identifiers to safe Daena actions. Phase 1 NEVER
 * executes a tool, never sends an external message, never writes
 * external state. Skill clicks resolve to one of:
 *
 *   - composer_draft     -- drop a useful prompt template into chat
 *   - action_plan        -- drop a multi-step plan into chat
 *   - blocked_requires_connection  -- plugin not callable yet
 *   - blocked_high_risk_consent_missing  -- needs Asset Shield consent (Phase 3)
 *   - unsupported_skill  -- skill not yet registered
 *
 * Honesty contract (founder rules 9, 10, 13, 14):
 *   - Every entry declares writes_external_state + sends_external_message
 *     + allowed_in_phase1. The contract is enforced by tests:
 *     * No allowed_in_phase1=true entry has writes_external_state=true
 *     * No allowed_in_phase1=true entry has sends_external_message=true
 *     * High-risk plugins default to plan-only or blocked
 *   - Templates ASK FIRST. Every Phase 1 prompt asks the operator for
 *     the missing context (repo, label, time range, ...) before doing
 *     anything. This keeps Daena from assuming a target the operator
 *     didn't pick.
 *   - Phase 2 (read-only tool execution) can promote action_plan
 *     entries by adding a tool dispatch path. Phase 3 (write actions)
 *     unblocks the high-risk-consent entries via Asset Shield.
 */

import type { PluginCard, SkillReadiness } from './pluginCard'

// ── Public types ──

export type SkillActionType =
  | 'composer_draft'
  | 'action_plan'
  | 'blocked_requires_connection'
  | 'blocked_high_risk_consent_missing'
  | 'unsupported_skill'

export interface SkillActionEntry {
  /** Catalog plugin id (e.g. "mcp-github"). */
  plugin_id: string
  /** snake_case skill identifier from plugin.default_skills. */
  skill_id: string
  /** Resolution type for this skill in Phase 1. */
  action_type: SkillActionType
  /** Composer / plan template. Empty for blocked entries. The
   * template is rendered as-is into the chat composer; it never
   * substitutes operator data via interpolation, so it cannot leak. */
  template: string
  /** Lifecycle the plugin must have reached for this skill to fire.
   * "callable" (default) means the V2 probe must have proved the
   * plugin works. "any" allows the skill to fire even on locked
   * plugins (rare -- only for pure planning skills that never need
   * the plugin to be live). */
  required_plugin_status: 'callable' | 'any'
  /** Per-skill risk classification (independent of plugin's overall
   * risk_level). A read-only skill on a high-risk plugin can still
   * be low-risk. Asset Shield consent dialogs in Phase 3 will key
   * on this. */
  risk_level: 'low' | 'medium' | 'high'
  /** Will the eventual Phase 2/3 execution write external state? */
  writes_external_state: boolean
  /** Will the eventual Phase 2/3 execution send a message
   * (email, DM, notification, webhook)? */
  sends_external_message: boolean
  /** Whether this skill is allowed to fire its action_type in
   * Phase 1. False entries fall back to blocked_high_risk_consent_missing
   * even if action_type is composer_draft -- defense in depth. */
  allowed_in_phase1: boolean
  /** Operator-readable note shown in the inline reveal when the
   * skill is blocked. Empty for allowed entries. */
  blocked_reason?: string
}

// ── Helpers used by the table below ──

/** Default risk classification when an entry doesn't override. */
const PLAN_ONLY = {
  action_type: 'action_plan' as const,
  required_plugin_status: 'callable' as const,
  risk_level: 'medium' as const,
  writes_external_state: false,
  sends_external_message: false,
  allowed_in_phase1: true,
}

const COMPOSER = {
  action_type: 'composer_draft' as const,
  required_plugin_status: 'callable' as const,
  risk_level: 'low' as const,
  writes_external_state: false,
  sends_external_message: false,
  allowed_in_phase1: true,
}

const COMPOSER_HIGH_RISK = {
  ...COMPOSER,
  risk_level: 'high' as const,
}

const BLOCKED_WRITE = {
  action_type: 'blocked_high_risk_consent_missing' as const,
  template: '',
  required_plugin_status: 'callable' as const,
  risk_level: 'high' as const,
  writes_external_state: true,
  sends_external_message: false,
  allowed_in_phase1: false,
  blocked_reason:
    'This skill writes external state. Daena needs Asset Shield consent + Phase 3 execution wiring before it can run -- draft a plan instead?',
}

const BLOCKED_MESSAGE = {
  ...BLOCKED_WRITE,
  sends_external_message: true,
  blocked_reason:
    'This skill sends an external message. Daena needs Asset Shield consent + Phase 3 execution wiring -- draft the message instead?',
}

const BLOCKED_BROWSER_ACTION = {
  action_type: 'blocked_high_risk_consent_missing' as const,
  template: '',
  required_plugin_status: 'callable' as const,
  risk_level: 'high' as const,
  writes_external_state: true,
  sends_external_message: false,
  allowed_in_phase1: false,
  blocked_reason:
    'This skill drives a real browser. Daena needs browser action governance + Asset Shield consent before it can run -- draft a plan instead?',
}

// ── Registry table ──
//
// Organized by plugin_id. Every catalog entry's default_skills must
// appear here OR be returned as "unsupported_skill" by the lookup.
// The coverage test enforces that every catalog skill is mapped.

export const SKILL_ACTION_REGISTRY: SkillActionEntry[] = [
  // ── GitHub (vendor-official, MEDIUM risk) ──
  // All three "read"-style skills draft a useful chat prompt that
  // asks the operator for the missing context (repo, PR number,
  // date range) before doing anything.
  { plugin_id: 'mcp-github', skill_id: 'triage_issues', ...COMPOSER, template:
    'Use the GitHub plugin to triage open issues by severity, user impact, and urgency. Start by asking me which repo, then walk through the top 10 open issues and rank them.' },
  { plugin_id: 'mcp-github', skill_id: 'review_pull_request', ...COMPOSER, template:
    'Use the GitHub plugin to review a pull request. Ask me for the repo and PR number, then summarize risks (security, perf, breaking changes) before suggesting changes.' },
  { plugin_id: 'mcp-github', skill_id: 'summarize_repo', ...COMPOSER, template:
    'Use the GitHub plugin to summarize a repo. Ask me for the repo name, then describe its purpose, primary languages, recent activity, and open-issue health.' },
  { plugin_id: 'mcp-github', skill_id: 'draft_release_notes', ...COMPOSER, template:
    'Use the GitHub plugin to draft release notes from merged PRs. Ask me for the repo and date range, then produce a Keep-a-Changelog-style markdown draft. Do NOT publish -- I will review first.' },
  { plugin_id: 'mcp-github', skill_id: 'inspect_ci_failure', ...COMPOSER, template:
    'Use the GitHub plugin to inspect a CI failure. Ask me for the repo, PR or commit SHA, and which workflow failed. Pull the log, identify the failing step, and propose a fix.' },

  // ── Cloudflare (vendor-official, HIGH risk plugin) ──
  // All four default skills are READS, so they're allowed in Phase 1
  // -- but flagged risk_level=high so the Phase 3 consent dialog
  // still kicks in even for reads on this plugin.
  { plugin_id: 'mcp-cloudflare', skill_id: 'inspect_dns', ...COMPOSER_HIGH_RISK, template:
    'Use the Cloudflare plugin to inspect DNS for a zone. Ask me for the zone name, then list every A/AAAA/CNAME/TXT record and flag anything unusual (orphan subdomains, missing SPF/DKIM, dangling CNAMEs).' },
  { plugin_id: 'mcp-cloudflare', skill_id: 'review_workers', ...COMPOSER_HIGH_RISK, template:
    'Use the Cloudflare plugin to review Workers in an account. Ask me for the account, list deployed Workers, and summarize each one\'s purpose + last deploy + memory/CPU usage. Read-only review -- do NOT modify.' },
  { plugin_id: 'mcp-cloudflare', skill_id: 'check_security_headers', ...COMPOSER_HIGH_RISK, template:
    'Use the Cloudflare plugin to check security headers for a domain. Ask me for the hostname, then report on CSP / HSTS / X-Frame-Options / Permissions-Policy and rate the posture.' },
  { plugin_id: 'mcp-cloudflare', skill_id: 'summarize_zone_config', ...COMPOSER_HIGH_RISK, template:
    'Use the Cloudflare plugin to summarize a zone\'s config. Ask me for the zone, then describe SSL mode, caching rules, page rules, firewall rules, and bot-management posture.' },

  // ── Sentry (vendor-official, LOW risk) ──
  { plugin_id: 'mcp-sentry', skill_id: 'summarize_errors', ...COMPOSER, template:
    'Use the Sentry plugin to summarize errors. Ask me for the project + time window, then group recent issues by frequency and impact and propose the top 3 to fix first.' },
  { plugin_id: 'mcp-sentry', skill_id: 'trace_release_regression', ...COMPOSER, template:
    'Use the Sentry plugin to trace a regression to a release. Ask me which release tag and which error pattern, then walk back through commits to find the likely cause.' },
  // create_bug_task WRITES external state (creates an issue tracker
  // ticket) -- blocked in Phase 1.
  { plugin_id: 'mcp-sentry', skill_id: 'create_bug_task', ...BLOCKED_WRITE },

  // ── Vercel (vendor-official, MEDIUM risk) ──
  { plugin_id: 'mcp-vercel', skill_id: 'summarize_deployment', ...COMPOSER, template:
    'Use the Vercel plugin to summarize a deployment. Ask me for the project + deployment id (or "latest"), then report status, build duration, output size, and any warnings.' },
  { plugin_id: 'mcp-vercel', skill_id: 'inspect_logs', ...COMPOSER, template:
    'Use the Vercel plugin to inspect logs for a deployment. Ask me which project + time range + log level, then surface error patterns and high-frequency events.' },
  { plugin_id: 'mcp-vercel', skill_id: 'review_env_config', ...COMPOSER_HIGH_RISK, template:
    'Use the Vercel plugin to review env config for a project. Ask me which project, then list env var NAMES (never values) per environment and flag anything that looks like a leaked credential or stale flag.' },

  // ── Atlassian (Jira) (vendor-official, MEDIUM risk) ──
  { plugin_id: 'mcp-jira', skill_id: 'triage_tickets', ...COMPOSER, template:
    'Use the Atlassian plugin to triage Jira tickets. Ask me which project + sprint or backlog, then rank the top 10 by impact + urgency + age.' },
  { plugin_id: 'mcp-jira', skill_id: 'summarize_sprint', ...COMPOSER, template:
    'Use the Atlassian plugin to summarize a Jira sprint. Ask me which project + sprint id (or "current"), then report completion %, blockers, scope changes, and projected end date.' },
  { plugin_id: 'mcp-jira', skill_id: 'draft_release_notes', ...COMPOSER, template:
    'Use the Atlassian plugin to draft release notes from completed Jira issues. Ask me which project + version, then produce a markdown changelog grouped by epic.' },
  { plugin_id: 'mcp-jira', skill_id: 'find_blockers', ...COMPOSER, template:
    'Use the Atlassian plugin to find blockers in a Jira project. Ask me which project, then list issues with the "blocked" or "needs-info" labels (or status), grouped by what is blocking them.' },

  // ── Slack (vendor-official, MEDIUM risk) ──
  { plugin_id: 'mcp-slack', skill_id: 'summarize_channel', ...COMPOSER, template:
    'Use the Slack plugin to summarize a channel. Ask me which channel + time window, then bullet-list the key threads + decisions + open questions.' },
  // draft_reply: produces a DRAFT (not sent) -> safe in Phase 1.
  { plugin_id: 'mcp-slack', skill_id: 'draft_reply', ...COMPOSER, template:
    'Use the Slack plugin to draft a reply. Ask me which channel + thread permalink + tone, then produce a draft -- I will review and post myself. Do NOT send.' },
  { plugin_id: 'mcp-slack', skill_id: 'find_decisions', ...COMPOSER, template:
    'Use the Slack plugin to find decisions in a channel. Ask me which channel + time window, then extract messages that announce or confirm a decision (with permalinks).' },
  { plugin_id: 'mcp-slack', skill_id: 'extract_tasks', ...COMPOSER, template:
    'Use the Slack plugin to extract action items from a channel. Ask me which channel + time window, then list "owner -> task -> due" rows. Do NOT create tickets automatically.' },

  // ── Notion (vendor-official, MEDIUM risk) ──
  { plugin_id: 'mcp-notion', skill_id: 'find_page', ...COMPOSER, template:
    'Use the Notion plugin to find a page. Ask me for keywords + workspace, then return the top 5 matching pages with a one-line summary each.' },
  { plugin_id: 'mcp-notion', skill_id: 'summarize_database', ...COMPOSER, template:
    'Use the Notion plugin to summarize a database. Ask me which database, then describe the schema, row count, and key views.' },
  { plugin_id: 'mcp-notion', skill_id: 'extract_action_items', ...COMPOSER, template:
    'Use the Notion plugin to extract action items from a page. Ask me which page, then list every checkbox / task / TODO with its owner and any due date.' },
  // update_page WRITES Notion content -> blocked in Phase 1.
  { plugin_id: 'mcp-notion', skill_id: 'update_page', ...BLOCKED_WRITE },

  // ── Linear (vendor-official, MEDIUM risk) ──
  { plugin_id: 'mcp-linear', skill_id: 'triage_issues', ...COMPOSER, template:
    'Use the Linear plugin to triage open issues. Ask me which team + project (or "all open"), then rank by impact, customer-reported, and urgency.' },
  { plugin_id: 'mcp-linear', skill_id: 'summarize_cycle', ...COMPOSER, template:
    'Use the Linear plugin to summarize a cycle. Ask me which team + cycle (or "current"), then report completion %, scope changes, and at-risk issues.' },
  // draft_status_update: DRAFT only, no auto-publish.
  { plugin_id: 'mcp-linear', skill_id: 'draft_status_update', ...COMPOSER, template:
    'Use the Linear plugin to draft a status update for a cycle. Ask me which team + cycle, then produce a 5-bullet update covering progress, blockers, decisions needed, and next steps. I will post it myself.' },
  { plugin_id: 'mcp-linear', skill_id: 'find_blockers', ...COMPOSER, template:
    'Use the Linear plugin to find blockers. Ask me which team + project (or "all open"), then list every blocked issue grouped by what is blocking it.' },

  // ── Stripe (vendor-official, HIGH risk plugin) ──
  // Reads are allowed in Phase 1 but flagged high-risk so Phase 3
  // consent dialog kicks in. Writes (refunds, subscription changes)
  // are blocked.
  { plugin_id: 'mcp-stripe', skill_id: 'summarize_payments', ...COMPOSER_HIGH_RISK, template:
    'Use the Stripe plugin to summarize payments. Ask me for the date range, then report gross volume, net volume, top customers, and any unusual disputes/chargebacks. READ-ONLY -- do NOT issue refunds or modify subscriptions.' },
  { plugin_id: 'mcp-stripe', skill_id: 'inspect_customer', ...COMPOSER_HIGH_RISK, template:
    'Use the Stripe plugin to inspect a customer. Ask me for the customer email or id, then summarize their subscription history, payment methods (last-4 only), and recent invoices. READ-ONLY.' },
  // reconcile_subscriptions could write -> blocked.
  { plugin_id: 'mcp-stripe', skill_id: 'reconcile_subscriptions', ...BLOCKED_WRITE,
    blocked_reason:
      'Stripe subscription reconciliation can modify customer billing state. Phase 1 keeps it blocked. Draft a reconciliation report instead -- I will review before any change.' },

  // ── Hugging Face (vendor-official, LOW risk) ──
  { plugin_id: 'mcp-huggingface', skill_id: 'find_model', ...COMPOSER, template:
    'Use the Hugging Face plugin to find a model. Ask me for the task (text-gen / vision / embed / etc.) + size constraint, then return the top 5 matches with downloads + license + last-update.' },
  { plugin_id: 'mcp-huggingface', skill_id: 'summarize_dataset', ...COMPOSER, template:
    'Use the Hugging Face plugin to summarize a dataset. Ask me for the dataset id, then describe size, license, fields, and known biases.' },
  { plugin_id: 'mcp-huggingface', skill_id: 'compare_models', ...COMPOSER, template:
    'Use the Hugging Face plugin to compare 2-3 models. Ask me for the model ids, then produce a side-by-side: parameters, license, recent benchmark scores, and recommended use case.' },
  { plugin_id: 'mcp-huggingface', skill_id: 'inspect_paper', ...COMPOSER, template:
    'Use the Hugging Face plugin to inspect a paper. Ask me for the arxiv id or title, then summarize the abstract, key contributions, and any related models on the Hub.' },

  // ── Figma (vendor-official, LOW risk) ──
  { plugin_id: 'mcp-figma', skill_id: 'inspect_design', ...COMPOSER, template:
    'Use the Figma plugin to inspect a design. Ask me for the file URL + frame name, then describe the layout, components used, color tokens, and any obvious accessibility issues.' },
  { plugin_id: 'mcp-figma', skill_id: 'summarize_components', ...COMPOSER, template:
    'Use the Figma plugin to summarize a file\'s components. Ask me for the file URL, then list components grouped by category with a one-line description each.' },
  { plugin_id: 'mcp-figma', skill_id: 'generate_frontend_plan', ...PLAN_ONLY, risk_level: 'low' as const, template:
    'Use the Figma plugin to generate a frontend implementation plan. Ask me for the file URL + target framework (React / Vue / Svelte) + component library, then produce a step-by-step plan covering token export, component scaffolding, layout, and state. Do NOT write files yet.' },

  // ── Playwright (vendor-official, MEDIUM risk) ──
  // Browser automation is gated until Phase 3 browser action
  // governance lands. Only inspect_ui (planning) is allowed.
  { plugin_id: 'mcp-playwright', skill_id: 'open_page', ...BLOCKED_BROWSER_ACTION },
  { plugin_id: 'mcp-playwright', skill_id: 'inspect_ui', ...PLAN_ONLY, template:
    'Use the Playwright plugin to plan a UI inspection. Ask me for the URL + the target component or selector + what to verify (presence, text, accessibility role), then produce a checklist of assertions. Do NOT launch a browser yet.' },
  { plugin_id: 'mcp-playwright', skill_id: 'fill_form_safe', ...BLOCKED_BROWSER_ACTION },
  { plugin_id: 'mcp-playwright', skill_id: 'capture_screenshot', ...BLOCKED_BROWSER_ACTION },
  { plugin_id: 'mcp-playwright', skill_id: 'run_smoke_test', ...BLOCKED_BROWSER_ACTION },

  // ── Chrome DevTools (vendor-official, MEDIUM risk) ──
  // Inspect skills are read-only via an existing devtools session.
  { plugin_id: 'mcp-chrome-devtools', skill_id: 'inspect_dom', ...COMPOSER, template:
    'Use the Chrome DevTools plugin to inspect DOM. Ask me for the page URL + selector, then describe the element, its computed styles, and any event listeners.' },
  { plugin_id: 'mcp-chrome-devtools', skill_id: 'read_network', ...COMPOSER, template:
    'Use the Chrome DevTools plugin to read network requests. Ask me for the page URL + the request URL pattern, then list matching requests with status, timing, and headers (NAMES only).' },
  { plugin_id: 'mcp-chrome-devtools', skill_id: 'analyze_perf', ...COMPOSER, template:
    'Use the Chrome DevTools plugin to analyze page performance. Ask me for the URL + a representative user flow, then report Core Web Vitals + the top 3 bottlenecks + suggested fixes.' },
  { plugin_id: 'mcp-chrome-devtools', skill_id: 'capture_screenshot', ...BLOCKED_BROWSER_ACTION },

  // ── Filesystem (official, MEDIUM risk -- sandboxed) ──
  { plugin_id: 'mcp-filesystem', skill_id: 'find_files', ...COMPOSER, template:
    'Use the Filesystem plugin to find files. Ask me for the root path + the name or content pattern, then list matches with size and last-modified.' },
  { plugin_id: 'mcp-filesystem', skill_id: 'read_file', ...COMPOSER, template:
    'Use the Filesystem plugin to read a file. Ask me for the absolute path, then return the contents (or first 200 lines if large) with a brief summary.' },
  { plugin_id: 'mcp-filesystem', skill_id: 'summarize_directory', ...COMPOSER, template:
    'Use the Filesystem plugin to summarize a directory. Ask me for the path + max depth, then describe the layout, file-type breakdown, and any notable patterns.' },

  // ── Postgres / SQLite / MongoDB / Supabase / Neon (data + storage) ──
  // safe_query is read-only by name but the action plan asks for the
  // SQL preview before execution.
  { plugin_id: 'mcp-postgres', skill_id: 'describe_schema', ...COMPOSER, template:
    'Use the Postgres plugin to describe a schema. Ask me for the database + schema name, then list tables, key columns, and relationships.' },
  { plugin_id: 'mcp-postgres', skill_id: 'safe_query', ...PLAN_ONLY, template:
    'Use the Postgres plugin to plan a safe (read-only) query. Ask me what I want to know, then SHOW the SQL before any execution -- I will approve.' },
  { plugin_id: 'mcp-postgres', skill_id: 'explain_query', ...COMPOSER, template:
    'Use the Postgres plugin to explain a query plan. Ask me for the query, then run EXPLAIN and summarize the plan + potential index opportunities.' },

  { plugin_id: 'mcp-sqlite', skill_id: 'describe_schema', ...COMPOSER, template:
    'Use the SQLite plugin to describe a schema. Ask me for the .db path, then list tables and columns.' },
  { plugin_id: 'mcp-sqlite', skill_id: 'safe_query', ...PLAN_ONLY, template:
    'Use the SQLite plugin to plan a safe (read-only) query. Ask me what I want to know, then SHOW the SQL before execution.' },
  { plugin_id: 'mcp-sqlite', skill_id: 'explain_query', ...COMPOSER, template:
    'Use the SQLite plugin to explain a query plan. Ask me for the query, then summarize the plan.' },

  { plugin_id: 'mcp-mongodb', skill_id: 'describe_collections', ...COMPOSER, template:
    'Use the MongoDB plugin to describe collections. Ask me for the database, then list collections with document count + a sample shape per collection.' },
  { plugin_id: 'mcp-mongodb', skill_id: 'safe_query', ...PLAN_ONLY, template:
    'Use the MongoDB plugin to plan a safe (read-only) query. Ask me what I want to know, then SHOW the find()/aggregate() pipeline before execution.' },

  { plugin_id: 'mcp-supabase', skill_id: 'describe_schema', ...COMPOSER, template:
    'Use the Supabase plugin to describe the schema. Ask me which project, then list tables + columns + RLS policies.' },
  { plugin_id: 'mcp-supabase', skill_id: 'safe_query', ...PLAN_ONLY, template:
    'Use the Supabase plugin to plan a safe (read-only) query. Ask me what I want to know, then SHOW the SQL before execution.' },
  { plugin_id: 'mcp-supabase', skill_id: 'summarize_storage', ...COMPOSER, template:
    'Use the Supabase plugin to summarize storage buckets. Ask me which project, then list buckets with size, file count, and visibility (public / private).' },

  { plugin_id: 'mcp-neon', skill_id: 'describe_schema', ...COMPOSER, template:
    'Use the Neon plugin to describe the schema. Ask me which database (and branch if relevant), then list tables and columns.' },
  { plugin_id: 'mcp-neon', skill_id: 'safe_query', ...PLAN_ONLY, template:
    'Use the Neon plugin to plan a safe (read-only) query. Ask me what I want to know + which branch, then SHOW the SQL.' },
  { plugin_id: 'mcp-neon', skill_id: 'list_branches', ...COMPOSER, template:
    'Use the Neon plugin to list branches. Ask me which project, then list branches with parent + last-modified + size.' },

  // ── Google Drive (MCP, archived) ──
  // Skills are read-only.
  { plugin_id: 'mcp-google-drive', skill_id: 'find_documents', ...COMPOSER, template:
    'Use the Google Drive plugin to find documents. Ask me for keywords + folder (or "all"), then return the top 5 matches with author + last-modified.' },
  { plugin_id: 'mcp-google-drive', skill_id: 'summarize_file', ...COMPOSER, template:
    'Use the Google Drive plugin to summarize a file. Ask me for the file id or URL, then produce a 5-bullet summary + 3 key quotes.' },
  { plugin_id: 'mcp-google-drive', skill_id: 'compare_docs', ...COMPOSER, template:
    'Use the Google Drive plugin to compare 2 docs. Ask me for both file ids, then produce a side-by-side diff of structure, key claims, and tone.' },
  { plugin_id: 'mcp-google-drive', skill_id: 'extract_tables', ...COMPOSER, template:
    'Use the Google Drive plugin to extract tables from a doc. Ask me for the file id, then return each table as markdown.' },

  // ── App Gmail (verified, MEDIUM risk) ──
  { plugin_id: 'app-gmail', skill_id: 'summarize_unread', ...COMPOSER, template:
    'Use the Gmail plugin to summarize unread emails. Ask me for the label/time range first, then group by sender + thread topic.' },
  // draft_reply: DRAFT only, no auto-send.
  { plugin_id: 'app-gmail', skill_id: 'draft_reply', ...COMPOSER, template:
    'Use the Gmail plugin to draft a reply. Ask me for the thread + tone + key points to cover, then produce a draft. Do NOT send -- I will review and click Send myself.' },
  { plugin_id: 'app-gmail', skill_id: 'extract_action_items', ...COMPOSER, template:
    'Use the Gmail plugin to extract action items from a thread. Ask me for the thread (subject or message id), then list "owner -> task -> due" rows.' },
  { plugin_id: 'app-gmail', skill_id: 'search_email_context', ...COMPOSER, template:
    'Use the Gmail plugin to search for context. Ask me for the topic + time window + sender filter, then summarize the most relevant 5 messages.' },

  // ── App Google Calendar (verified, MEDIUM risk) ──
  { plugin_id: 'app-google-calendar', skill_id: 'list_today', ...COMPOSER, template:
    'Use the Google Calendar plugin to list today\'s events. No follow-up question needed -- just enumerate today\'s meetings with time, attendees, and the prep needed for each.' },
  { plugin_id: 'app-google-calendar', skill_id: 'find_free_time', ...COMPOSER, template:
    'Use the Google Calendar plugin to find free time. Ask me for the duration + which calendars to check + the date window, then return the top 5 free slots.' },
  // schedule_meeting WRITES external state (creates a calendar event +
  // sends invites) -> blocked. The plan path stays available.
  { plugin_id: 'app-google-calendar', skill_id: 'schedule_meeting', ...BLOCKED_MESSAGE,
    blocked_reason:
      'Scheduling a meeting writes a calendar event AND sends invites. Phase 1 keeps it blocked. Draft the meeting (title, attendees, time, agenda) and I will create it myself.' },
  { plugin_id: 'app-google-calendar', skill_id: 'summarize_week', ...COMPOSER, template:
    'Use the Google Calendar plugin to summarize this week. List meetings grouped by category, total time in meetings vs heads-down, and recurring blockers.' },

  // ── App Google Drive (OAuth-managed) ──
  { plugin_id: 'app-google-drive', skill_id: 'find_documents', ...COMPOSER, template:
    'Use the Google Drive plugin to find documents. Ask me for keywords + folder (or "all"), then return the top 5 matches with author + last-modified.' },
  { plugin_id: 'app-google-drive', skill_id: 'summarize_file', ...COMPOSER, template:
    'Use the Google Drive plugin to summarize a file. Ask me for the file id or URL, then produce a 5-bullet summary + 3 key quotes.' },
  { plugin_id: 'app-google-drive', skill_id: 'compare_docs', ...COMPOSER, template:
    'Use the Google Drive plugin to compare 2 docs. Ask me for both file ids, then produce a side-by-side diff of structure, key claims, and tone.' },
  { plugin_id: 'app-google-drive', skill_id: 'extract_tables', ...COMPOSER, template:
    'Use the Google Drive plugin to extract tables from a doc. Ask me for the file id, then return each table as markdown.' },
]

// ── Lookup helpers ──

const REGISTRY_BY_KEY: Map<string, SkillActionEntry> = new Map(
  SKILL_ACTION_REGISTRY.map((e) => [`${e.plugin_id}:${e.skill_id}`, e]),
)

/** Look up the action for a (plugin, skill) pair. Returns the
 * registered entry, or a synthetic ``unsupported_skill`` entry for
 * skill ids not yet in the registry. */
export function lookupSkillAction(
  plugin_id: string,
  skill_id: string,
): SkillActionEntry {
  const key = `${plugin_id}:${skill_id}`
  const found = REGISTRY_BY_KEY.get(key)
  if (found) return found
  return {
    plugin_id,
    skill_id,
    action_type: 'unsupported_skill',
    template: '',
    required_plugin_status: 'callable',
    risk_level: 'low',
    writes_external_state: false,
    sends_external_message: false,
    allowed_in_phase1: false,
    blocked_reason:
      'This skill is not yet wired into the Phase 1 action registry. Open chat and ask Daena directly using the suggested prompts above.',
  }
}

/** Resolve what should happen when the operator clicks ``skill_id``
 * on ``plugin``. Combines the registry lookup with the live skill
 * readiness so the UI never offers a draft for a plugin that isn't
 * connected. Pure function -- no side effects. */
export interface ResolvedSkillAction {
  entry: SkillActionEntry
  /** Final action to take. Differs from entry.action_type when the
   * plugin is not callable -- in that case, even an entry that would
   * be composer_draft is downgraded to blocked_requires_connection. */
  effective_action: SkillActionType
  /** Operator-facing one-liner describing what will happen on click. */
  inline_message: string
  /** When effective_action is composer_draft / action_plan, the text
   * that will be drafted into the composer. Empty otherwise. */
  draft_text: string
}

export function resolveSkillAction(
  plugin: PluginCard,
  skill_id: string,
  readiness: SkillReadiness,
): ResolvedSkillAction {
  const entry = lookupSkillAction(plugin.id, skill_id)

  // Plugin not callable -> always blocked_requires_connection,
  // regardless of registry entry. (Phase 1 doesn't trust an entry
  // that says "any" yet -- the chat composer doesn't know the plugin
  // isn't ready.)
  if (readiness !== 'ready' && readiness !== 'ready_metadata_only') {
    return {
      entry,
      effective_action: 'blocked_requires_connection',
      inline_message:
        'Connect the plugin first to enable this skill. The probe ladder above shows what step is pending.',
      draft_text: '',
    }
  }

  // Registry entry exists + Phase 1 allowed -> draft into composer.
  if (entry.allowed_in_phase1
    && (entry.action_type === 'composer_draft' || entry.action_type === 'action_plan')) {
    return {
      entry,
      effective_action: entry.action_type,
      inline_message:
        entry.action_type === 'action_plan'
          ? 'Drafting an action plan into the chat composer. Daena will ask for the missing context before doing anything -- review and send when ready.'
          : 'Drafting a prompt into the chat composer. Daena will not auto-send -- review and send when ready.',
      draft_text: entry.template,
    }
  }

  // Registry entry exists but blocked (high-risk write or browser action).
  if (entry.action_type === 'blocked_high_risk_consent_missing') {
    return {
      entry,
      effective_action: 'blocked_high_risk_consent_missing',
      inline_message:
        entry.blocked_reason
        || 'This skill needs Asset Shield consent + Phase 3 execution wiring -- draft a plan instead?',
      // Offer a "draft a plan instead" fallback even for blocked
      // entries so the operator gets value: a plan template the
      // user can review + decide whether to escalate.
      draft_text: _draftPlanFallback(plugin, entry),
    }
  }

  // Registry didn't have this skill at all.
  return {
    entry,
    effective_action: 'unsupported_skill',
    inline_message: entry.blocked_reason || 'Skill not yet wired into Phase 1.',
    draft_text: '',
  }
}

/** Build a generic plan-only template for a blocked skill so the
 * "Draft plan in chat" affordance still gives the operator something. */
function _draftPlanFallback(
  plugin: PluginCard,
  entry: SkillActionEntry,
): string {
  return (
    `I want to use the ${plugin.name} plugin to ${_humanize(entry.skill_id)}. `
    + `Help me design a safe plan: list the inputs you'd need from me, the steps `
    + `you'd take, the side effects each step would have, and the rollback if `
    + `anything fails. Do NOT execute anything yet -- I will review the plan first.`
  )
}

/** snake_case -> "Sentence case" copy (mirrors SkillBundleSection). */
function _humanize(skill_id: string): string {
  return skill_id.replace(/_/g, ' ')
}

// ── Export everything tests need ──

export const __test_helpers__ = {
  registry: SKILL_ACTION_REGISTRY,
  REGISTRY_BY_KEY,
}
