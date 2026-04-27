/**
 * ConnectionsPage -- Claude Desktop style layout with 3 tabs:
 *   1. Runtimes (AI CLIs with real detection + expandable config)
 *   2. Extensions (MCP servers with tool permissions)
 *   3. Connectors (external services with OAuth/API key config)
 *
 * Each item expands inline to show a configuration panel when clicked,
 * matching Claude Desktop's pattern for MCP server configuration.
 */
import { useEffect, useState, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Plug,
  Puzzle,
  Cpu,
  Search,
  RefreshCw,
  MoreVertical,
  CheckCircle2,
  XCircle,
  Settings,
  Eye,
  Crown,
  Loader2,
  Plus,
  ChevronDown,
  ChevronUp,
  Key,
  Globe,
  Shield,
  Zap,
  Terminal,
  ToggleLeft,
  ToggleRight,
  Save,
  ExternalLink,
  Unplug,
  Download,
  AlertTriangle,
  Wrench,
  Server,
  Activity,
  UserCircle,
} from 'lucide-react'
import { usePageTitle } from '@/hooks/usePageTitle'
import { api } from '@/lib/api'
import { toast } from '@/stores/toastStore'
import { confirmDialog } from '@/stores/confirmStore'
import { useUiStore } from '@/stores/uiStore'
import { CONNECTOR_ICONS, RUNTIME_ICONS, EXTENSION_ICONS } from '@/components/icons/BrandIcons'
import { useMCPDetections } from '@/hooks/useMCPDetections'
import { useMcpRegistry } from '@/hooks/useMcpRegistry'
import { usePermissionState } from '@/hooks/usePermissionState'

// ── Types ──

interface RuntimeData {
  runtime_id: string
  display_name: string
  installed: boolean
  status: string
  subscription: {
    is_authenticated: boolean
    plan_name: string | null
    user_display: string | null
    login_url?: string
    setup_command?: string
    method?: string
    status?: string
  } | null
}

interface ExtensionData {
  id: string
  name: string
  description: string
  enabled: boolean
  permission: string
  // Session 10: Claude Desktop parity -- show each tool the MCP server
  // exposes, with its own Allow/Ask/Block permission. Optional because
  // not every extension type surfaces tools at scan time (e.g. Claude
  // Code plugins are categorized by name only). Missing tools arrays
  // render an informative placeholder instead of empty space.
  tools?: string[]
  source?: string   // "mcp-server", "claude-plugins-official", "dxt-*", etc.
  version?: string
  // Session 11: per-user saved tool permissions from User.settings JSONB.
  // Empty/missing means "inherit the default permission". Hydrated by
  // the backend in GET /connections/extensions.
  tool_permissions?: Record<string, string>
}

// Auth methods for connectors
type AuthMethod = 'oauth' | 'api_key' | 'token'

// ── Connector definitions (Claude Desktop style) ──

// Full Codex-style plugin catalog. Categories mirror Codex Desktop's
// grouping; each plugin ships with 2-4 skills. Skill descriptions are
// defined in SKILL_DESCRIPTIONS below -- they render as the one-line
// caption under each skill card in the Plugins tab.
const CONNECTORS = [
  // ── Coding ──
  { id: 'hugging-face', name: 'Hugging Face', subtitle: 'Inspect models, datasets, Spaces, and research', category: 'Coding', auth: 'api_key' as AuthMethod, tools: ['search_models', 'model_info', 'run_inference', 'search_datasets'] },
  { id: 'netlify', name: 'Netlify', subtitle: 'Deploy projects and manage releases', category: 'Coding', auth: 'token' as AuthMethod, tools: ['netlify_deploy', 'netlify_list_sites', 'netlify_env', 'netlify_logs'] },
  { id: 'vercel', name: 'Vercel', subtitle: 'Build and deploy web apps and agents', category: 'Coding', auth: 'token' as AuthMethod, tools: ['vercel_deploy', 'vercel_list_projects', 'vercel_logs', 'vercel_env'] },
  { id: 'game-studio', name: 'Game Studio', subtitle: 'Design, prototype, and ship browser games', category: 'Coding', auth: 'token' as AuthMethod, tools: ['prototype_game', 'publish_game', 'list_assets'] },
  { id: 'superpowers', name: 'Superpowers', subtitle: 'Planning, TDD, debugging, and delivery workflows', category: 'Coding', auth: 'token' as AuthMethod, tools: ['plan_feature', 'run_tdd', 'debug_session'] },
  { id: 'github', name: 'GitHub', subtitle: 'Triage PRs, issues, CI, and publish flows', category: 'Coding', auth: 'token' as AuthMethod, tools: ['search_repos', 'read_file', 'list_issues', 'create_issue', 'create_pr'] },
  { id: 'circleci', name: 'CircleCI', subtitle: 'Build, test, and deploy any application', category: 'Coding', auth: 'token' as AuthMethod, tools: ['list_pipelines', 'trigger_build', 'get_job_logs'] },
  { id: 'cloudflare', name: 'Cloudflare', subtitle: 'Cloudflare platform guidance with official MCP', category: 'Coding', auth: 'token' as AuthMethod, tools: ['list_zones', 'update_dns', 'deploy_worker', 'list_tunnels'] },
  { id: 'sentry', name: 'Sentry', subtitle: 'Inspect recent Sentry issues and events', category: 'Coding', auth: 'token' as AuthMethod, tools: ['list_issues_sentry', 'get_event', 'search_events'] },
  { id: 'build-ios', name: 'Build iOS Apps', subtitle: 'Build, refine, and debug iOS apps with SwiftUI and Xcode', category: 'Coding', auth: 'none' as AuthMethod, tools: ['build_xcode', 'run_simulator', 'debug_ios'] },
  { id: 'build-macos', name: 'Build macOS Apps', subtitle: 'Build, debug, instrument macOS apps with SwiftUI and AppKit', category: 'Coding', auth: 'none' as AuthMethod, tools: ['build_xcode', 'run_macos', 'debug_macos'] },
  { id: 'build-web', name: 'Build Web Apps', subtitle: 'Build, review, ship, and scale web apps', category: 'Coding', auth: 'none' as AuthMethod, tools: ['scaffold_app', 'run_review', 'deploy_web'] },
  { id: 'test-android', name: 'Test Android Apps', subtitle: 'Reproduce issues and inspect Android emulators', category: 'Coding', auth: 'none' as AuthMethod, tools: ['run_emulator', 'capture_screen', 'dump_ui'] },
  { id: 'expo', name: 'Expo', subtitle: 'Build, deploy, upgrade Expo and React Native apps', category: 'Coding', auth: 'token' as AuthMethod, tools: ['expo_build', 'expo_publish', 'expo_logs'] },
  { id: 'coderabbit', name: 'CodeRabbit', subtitle: 'Run AI-powered code review for your current changes', category: 'Coding', auth: 'api_key' as AuthMethod, tools: ['review_pr', 'summarize_diff', 'suggest_fixes'] },
  { id: 'neon', name: 'Neon Postgres', subtitle: 'Manage Neon Serverless Postgres projects and databases', category: 'Coding', auth: 'api_key' as AuthMethod, tools: ['list_neon_projects', 'run_query', 'create_branch'] },
  { id: 'plugin-eval', name: 'Plugin Eval', subtitle: 'Start from chat, then evaluate or benchmark locally', category: 'Coding', auth: 'none' as AuthMethod, tools: ['run_eval', 'run_benchmark', 'compare_results'] },
  { id: 'cloudinary', name: 'Cloudinary', subtitle: 'Manage, search, and transform your media library', category: 'Coding', auth: 'api_key' as AuthMethod, tools: ['upload_media', 'search_media', 'transform_image'] },
  { id: 'hostinger', name: 'Hostinger', subtitle: 'Build websites and apps by describing what you want', category: 'Coding', auth: 'api_key' as AuthMethod, tools: ['create_site', 'deploy_site', 'configure_domain'] },
  { id: 'marcopolo', name: 'MarcoPolo', subtitle: 'Secure container where Claude can work with your data', category: 'Coding', auth: 'api_key' as AuthMethod, tools: ['create_sandbox', 'upload_data', 'run_script'] },
  { id: 'quicknode', name: 'Quicknode', subtitle: 'Manage your Quicknode infrastructure', category: 'Coding', auth: 'api_key' as AuthMethod, tools: ['list_endpoints', 'get_stats', 'deploy_function'] },
  { id: 'sendgrid', name: 'SendGrid', subtitle: 'Connector for the SendGrid email API', category: 'Coding', auth: 'api_key' as AuthMethod, tools: ['send_email_sg', 'list_templates', 'get_stats_sg'] },
  { id: 'statsig', name: 'Statsig', subtitle: 'Bring your Statsig workspace into Codex', category: 'Coding', auth: 'api_key' as AuthMethod, tools: ['list_gates', 'get_experiment', 'update_config'] },
  { id: 'vantage', name: 'Vantage', subtitle: 'Cloud observability and cost optimization', category: 'Coding', auth: 'api_key' as AuthMethod, tools: ['get_cost', 'list_recommendations', 'compare_clouds'] },
  { id: 'yepcode', name: 'YepCode', subtitle: 'Build custom AI tools using your own code', category: 'Coding', auth: 'api_key' as AuthMethod, tools: ['create_tool', 'run_tool', 'list_tools'] },
  { id: 'render', name: 'Render', subtitle: 'Deploy, debug, monitor, and migrate apps on Render', category: 'Coding', auth: 'api_key' as AuthMethod, tools: ['render_deploy', 'render_logs', 'render_list_services'] },

  // ── Design ──
  { id: 'canva', name: 'Canva', subtitle: 'Search, create, edit designs', category: 'Design', auth: 'oauth' as AuthMethod, tools: ['list_designs', 'create_design', 'export_design'] },
  { id: 'figma', name: 'Figma', subtitle: 'Design-to-code workflows powered by Figma', category: 'Design', auth: 'token' as AuthMethod, tools: ['get_file', 'get_components', 'export_assets'] },
  { id: 'remotion', name: 'Remotion', subtitle: 'Create motion graphics from prompts', category: 'Design', auth: 'none' as AuthMethod, tools: ['render_video', 'list_compositions', 'preview_frame'] },
  { id: 'biorender', name: 'BioRender', subtitle: 'Create professional scientific figures in minutes', category: 'Design', auth: 'api_key' as AuthMethod, tools: ['list_templates', 'create_figure', 'export_figure'] },

  // ── Lifestyle ──
  { id: 'cogedim', name: 'Cogedim', subtitle: "France's leading real estate developer", category: 'Lifestyle', auth: 'api_key' as AuthMethod, tools: ['search_properties', 'get_property'] },
  { id: 'finn', name: 'FINN', subtitle: 'Flexible car subscription service', category: 'Lifestyle', auth: 'api_key' as AuthMethod, tools: ['list_vehicles', 'book_subscription'] },
  { id: 'myregistry', name: 'MyRegistry.com', subtitle: 'Universal gift registry', category: 'Lifestyle', auth: 'api_key' as AuthMethod, tools: ['list_registries', 'add_item', 'share_registry'] },
  { id: 'setu-billpay', name: 'Setu Bharat Connect BillPay', subtitle: 'Pay utility bills through conversation', category: 'Lifestyle', auth: 'api_key' as AuthMethod, tools: ['list_bills', 'pay_bill', 'get_receipt'] },
  { id: 'weatherpromise', name: 'WeatherPromise', subtitle: 'Trip protection against rainy weather', category: 'Lifestyle', auth: 'api_key' as AuthMethod, tools: ['get_quote', 'create_policy', 'file_claim'] },

  // ── Productivity ──
  { id: 'linear', name: 'Linear', subtitle: 'Find and reference issues and projects', category: 'Productivity', auth: 'api_key' as AuthMethod, tools: ['list_issues', 'create_issue', 'update_issue', 'list_projects'] },
  { id: 'atlassian-rovo', name: 'Atlassian Rovo', subtitle: 'Manage Jira and Confluence fast', category: 'Productivity', auth: 'token' as AuthMethod, tools: ['search_issues', 'create_issue', 'search_pages', 'read_page'] },
  { id: 'google-calendar', name: 'Google Calendar', subtitle: 'Manage Google Calendar events and schedules', category: 'Productivity', auth: 'oauth' as AuthMethod, tools: ['list_events', 'create_event', 'update_event', 'find_free_time'] },
  { id: 'gmail', name: 'Gmail', subtitle: 'Read and manage Gmail', category: 'Productivity', auth: 'oauth' as AuthMethod, tools: ['search_emails', 'read_email', 'send_email', 'create_draft'] },
  { id: 'slack', name: 'Slack', subtitle: 'Read and manage Slack', category: 'Productivity', auth: 'oauth' as AuthMethod, tools: ['search_messages', 'send_message', 'list_channels', 'read_channel'] },
  { id: 'teams', name: 'Teams', subtitle: 'Summarize Teams and draft follow-ups', category: 'Productivity', auth: 'oauth' as AuthMethod, tools: ['list_teams_chats', 'summarize_thread', 'draft_followup'] },
  { id: 'sharepoint', name: 'SharePoint', subtitle: 'Summarize SharePoint sites and files', category: 'Productivity', auth: 'oauth' as AuthMethod, tools: ['list_sp_sites', 'read_sp_file', 'search_sp'] },
  { id: 'outlook-email', name: 'Outlook Email', subtitle: 'Triage Outlook inboxes and draft replies', category: 'Productivity', auth: 'oauth' as AuthMethod, tools: ['search_outlook', 'draft_outlook', 'send_outlook'] },
  { id: 'outlook-calendar', name: 'Outlook Calendar', subtitle: 'Manage Outlook schedules and meetings', category: 'Productivity', auth: 'oauth' as AuthMethod, tools: ['list_outlook_events', 'create_outlook_event', 'update_outlook_event'] },
  { id: 'jam', name: 'Jam', subtitle: 'Screen record with context', category: 'Productivity', auth: 'api_key' as AuthMethod, tools: ['list_recordings', 'get_recording', 'share_recording'] },
  { id: 'stripe', name: 'Stripe', subtitle: 'Payments and business tools', category: 'Productivity', auth: 'api_key' as AuthMethod, tools: ['list_charges', 'list_subscriptions', 'create_invoice'] },
  { id: 'box', name: 'Box', subtitle: 'Search and reference your documents', category: 'Productivity', auth: 'oauth' as AuthMethod, tools: ['search_box', 'read_box_file', 'upload_box'] },
  { id: 'google-drive', name: 'Google Drive', subtitle: 'Work across Drive, Docs, Sheets, and Slides', category: 'Productivity', auth: 'oauth' as AuthMethod, tools: ['search_files', 'read_file', 'upload_file', 'list_folders'] },
  { id: 'notion', name: 'Notion', subtitle: 'Specs, research, meetings, and knowledge capture', category: 'Productivity', auth: 'token' as AuthMethod, tools: ['search_pages', 'read_page', 'create_page', 'query_database'] },
  { id: 'amplitude', name: 'Amplitude', subtitle: 'Product analytics and funnels', category: 'Productivity', auth: 'api_key' as AuthMethod, tools: ['query_events', 'list_funnels', 'get_cohort'] },
  { id: 'attio', name: 'Attio', subtitle: 'Connects Codex directly to your CRM workspace', category: 'Productivity', auth: 'api_key' as AuthMethod, tools: ['search_records', 'create_record', 'update_record'] },
  { id: 'brand24', name: 'Brand24', subtitle: 'Brand mentions, sentiment, and media coverage', category: 'Productivity', auth: 'api_key' as AuthMethod, tools: ['search_mentions', 'get_sentiment', 'list_projects_b24'] },
  { id: 'brex', name: 'Brex', subtitle: 'Review company finances through conversation', category: 'Productivity', auth: 'api_key' as AuthMethod, tools: ['list_transactions_brex', 'list_cards', 'get_balance'] },
  { id: 'carta', name: 'Carta CRM', subtitle: 'Deal flow CRM for investment teams', category: 'Productivity', auth: 'api_key' as AuthMethod, tools: ['list_deals', 'get_company', 'update_deal'] },
  { id: 'channel99', name: 'Channel99', subtitle: 'Real-time go-to-market intelligence', category: 'Productivity', auth: 'api_key' as AuthMethod, tools: ['get_gtm_metrics', 'list_accounts', 'trace_pipeline'] },
  { id: 'circleback', name: 'Circleback', subtitle: 'AI-powered meeting notes and action items', category: 'Productivity', auth: 'api_key' as AuthMethod, tools: ['list_meetings_cb', 'get_summary', 'list_actions'] },
  { id: 'clickup', name: 'ClickUp', subtitle: 'Turn Codex into your ClickUp command center', category: 'Productivity', auth: 'api_key' as AuthMethod, tools: ['list_tasks_cu', 'create_task_cu', 'update_task_cu'] },
  { id: 'common-room', name: 'Common Room', subtitle: 'Complete buyer intelligence within Codex', category: 'Productivity', auth: 'api_key' as AuthMethod, tools: ['search_signals', 'list_community', 'find_prospect'] },
  { id: 'conductor', name: 'Conductor', subtitle: 'Brand visibility and sentiment metrics', category: 'Productivity', auth: 'api_key' as AuthMethod, tools: ['get_visibility', 'get_sentiment_cond', 'list_topics'] },
  { id: 'coupler', name: 'Coupler.io', subtitle: 'Analyze multi-channel business data', category: 'Productivity', auth: 'api_key' as AuthMethod, tools: ['list_importers', 'run_importer', 'list_sources'] },
  { id: 'coveo', name: 'Coveo', subtitle: 'Search your enterprise content', category: 'Productivity', auth: 'api_key' as AuthMethod, tools: ['search_coveo', 'list_sources_coveo', 'get_document'] },
  { id: 'demandbase', name: 'Demandbase', subtitle: 'B2B data for sales, marketing, and GTM', category: 'Productivity', auth: 'api_key' as AuthMethod, tools: ['search_accounts_db', 'get_intent', 'list_campaigns'] },
  { id: 'docket', name: 'Docket', subtitle: 'Sales knowledge as an instant superpower', category: 'Productivity', auth: 'api_key' as AuthMethod, tools: ['ask_docket', 'list_playbooks', 'get_answer'] },
  { id: 'domotz', name: 'Domotz (Preview)', subtitle: 'Monitor and manage network infrastructure', category: 'Productivity', auth: 'api_key' as AuthMethod, tools: ['list_devices_net', 'get_alerts', 'ping_device'] },
  { id: 'dovetail', name: 'Dovetail', subtitle: 'Turn customer feedback into decisions', category: 'Productivity', auth: 'api_key' as AuthMethod, tools: ['search_insights', 'list_projects_dt', 'get_theme'] },
  { id: 'egnyte', name: 'Egnyte', subtitle: 'Work with documents and files in Egnyte', category: 'Productivity', auth: 'oauth' as AuthMethod, tools: ['search_egnyte', 'read_egnyte', 'upload_egnyte'] },
  { id: 'fireflies', name: 'Fireflies', subtitle: 'Meetings and knowledge into Codex', category: 'Productivity', auth: 'api_key' as AuthMethod, tools: ['list_meetings_ff', 'get_transcript', 'search_meetings'] },
  { id: 'fyxer', name: 'Fyxer', subtitle: 'Write emails that sound like you', category: 'Productivity', auth: 'api_key' as AuthMethod, tools: ['draft_email_fx', 'list_templates_fx', 'send_email_fx'] },
  { id: 'granola', name: 'Granola', subtitle: 'Meeting history and AI notes', category: 'Productivity', auth: 'api_key' as AuthMethod, tools: ['list_granola_meetings', 'get_notes', 'search_granola'] },
  { id: 'happenstance', name: 'Happenstance', subtitle: 'Search your professional network', category: 'Productivity', auth: 'api_key' as AuthMethod, tools: ['search_network', 'find_person', 'suggest_intro'] },
  { id: 'help-scout', name: 'Help Scout', subtitle: 'Sync Help Scout mailboxes and conversations', category: 'Productivity', auth: 'oauth' as AuthMethod, tools: ['list_hs_conversations', 'reply_hs', 'assign_hs'] },
  { id: 'highlevel', name: 'HighLevel', subtitle: 'Unified CRM, automation, and client comms', category: 'Productivity', auth: 'api_key' as AuthMethod, tools: ['list_hl_contacts', 'send_campaign', 'list_pipelines_hl'] },
  { id: 'hubspot', name: 'HubSpot', subtitle: 'Work with your HubSpot CRM data', category: 'Productivity', auth: 'oauth' as AuthMethod, tools: ['search_hubspot', 'create_hs_contact', 'update_hs_deal'] },
  { id: 'keybid-puls', name: 'KeyBid Puls', subtitle: 'Short-term rental ROI calculator', category: 'Productivity', auth: 'api_key' as AuthMethod, tools: ['calculate_roi', 'list_properties_kb', 'forecast_income'] },
  { id: 'mem', name: 'Mem', subtitle: 'Give Codex your second-brain context', category: 'Productivity', auth: 'api_key' as AuthMethod, tools: ['search_mem', 'create_mem_note', 'list_mem_collections'] },
  { id: 'monday', name: 'Monday.com', subtitle: 'Powerful monday.com connector for AI agents', category: 'Productivity', auth: 'api_key' as AuthMethod, tools: ['list_boards', 'create_item_mon', 'update_item_mon'] },
  { id: 'motherduck', name: 'MotherDuck', subtitle: 'Connect AI assistants to your MotherDuck warehouse', category: 'Productivity', auth: 'api_key' as AuthMethod, tools: ['run_sql_md', 'list_tables_md', 'describe_table_md'] },
  { id: 'network-solutions', name: 'Network Solutions', subtitle: 'Find available domains conversationally', category: 'Productivity', auth: 'api_key' as AuthMethod, tools: ['check_domain', 'suggest_domains', 'register_domain'] },
  { id: 'omni-analytics', name: 'Omni Analytics', subtitle: 'Query your semantic model directly', category: 'Productivity', auth: 'api_key' as AuthMethod, tools: ['query_omni', 'list_models_omni', 'get_metric'] },
  { id: 'otter', name: 'Otter.ai', subtitle: 'Meeting intelligence, transcripts, and search', category: 'Productivity', auth: 'oauth' as AuthMethod, tools: ['list_otter_meetings', 'get_transcript_ot', 'search_otter'] },
  { id: 'pipedrive', name: 'Pipedrive', subtitle: 'Sync Pipedrive deals and contacts', category: 'Productivity', auth: 'oauth' as AuthMethod, tools: ['list_deals_pd', 'create_pd_deal', 'update_pd_contact'] },
  { id: 'pylon', name: 'Pylon', subtitle: 'Customer support platform in Codex', category: 'Productivity', auth: 'api_key' as AuthMethod, tools: ['list_pylon_tickets', 'reply_pylon', 'resolve_pylon'] },
  { id: 'ranked-ai', name: 'Ranked AI', subtitle: 'Industry-leading AI SEO and PPC software', category: 'Productivity', auth: 'api_key' as AuthMethod, tools: ['run_seo_audit', 'list_campaigns_ra', 'get_ranking'] },
  { id: 'razorpay', name: 'Razorpay', subtitle: 'Access Razorpay payment data conversationally', category: 'Productivity', auth: 'api_key' as AuthMethod, tools: ['list_payments_rz', 'create_refund_rz', 'get_settlement'] },
  { id: 'read-ai', name: 'Read AI', subtitle: 'Meeting intelligence in your AI workflows', category: 'Productivity', auth: 'api_key' as AuthMethod, tools: ['list_read_meetings', 'get_summary_read', 'search_read'] },
  { id: 'responsive', name: 'Responsive', subtitle: 'Work with your organization data in Codex', category: 'Productivity', auth: 'api_key' as AuthMethod, tools: ['search_responsive', 'create_rfp', 'list_projects_rsp'] },
  { id: 'semrush', name: 'Semrush', subtitle: 'SEO and traffic data for domains and keywords', category: 'Productivity', auth: 'api_key' as AuthMethod, tools: ['get_domain_overview', 'list_keywords', 'get_backlinks'] },
  { id: 'signnow', name: 'SignNow', subtitle: 'Get documents signed faster', category: 'Productivity', auth: 'oauth' as AuthMethod, tools: ['list_documents_sn', 'send_for_signature', 'get_signing_status'] },
  { id: 'skywatch', name: 'SkyWatch', subtitle: 'Satellite imagery from top providers', category: 'Productivity', auth: 'api_key' as AuthMethod, tools: ['search_imagery', 'order_capture', 'list_archive'] },
  { id: 'streak', name: 'Streak', subtitle: 'CRM built directly into Gmail', category: 'Productivity', auth: 'oauth' as AuthMethod, tools: ['list_pipelines_st', 'create_box_st', 'update_box_st'] },
  { id: 'teamwork', name: 'Teamwork.com', subtitle: 'Sync Teamwork projects and tasks', category: 'Productivity', auth: 'api_key' as AuthMethod, tools: ['list_tw_projects', 'create_tw_task', 'update_tw_task'] },
  { id: 'united-rentals', name: 'United Rentals', subtitle: 'Get the right equipment for the job', category: 'Productivity', auth: 'api_key' as AuthMethod, tools: ['search_equipment', 'get_quote_ur', 'place_order'] },
  { id: 'waldo', name: 'Waldo', subtitle: 'AI-powered strategy for agencies and brands', category: 'Productivity', auth: 'api_key' as AuthMethod, tools: ['get_strategy', 'list_plans_waldo', 'run_analysis'] },
  { id: 'windsor', name: 'Windsor.ai', subtitle: 'Connect marketing and business data', category: 'Productivity', auth: 'api_key' as AuthMethod, tools: ['list_sources_ws', 'run_sync', 'get_dataset'] },

  // ── Research ──
  { id: 'life-science-research', name: 'Life Science Research', subtitle: 'Life-sciences research with evidence synthesis', category: 'Research', auth: 'api_key' as AuthMethod, tools: ['search_papers', 'synthesize_evidence', 'run_parallel_analysis'] },
  { id: 'alpaca', name: 'Alpaca', subtitle: 'Stop watching the markets', category: 'Research', auth: 'api_key' as AuthMethod, tools: ['get_quote_al', 'list_positions', 'place_order_al'] },
  { id: 'binance', name: 'Binance', subtitle: 'Explore Binance public market data', category: 'Research', auth: 'api_key' as AuthMethod, tools: ['get_ticker', 'list_pairs', 'get_orderbook'] },
  { id: 'cb-insights', name: 'CB Insights', subtitle: 'Private-markets research agent', category: 'Research', auth: 'api_key' as AuthMethod, tools: ['search_companies_cb', 'get_funding', 'list_industries'] },
  { id: 'cube', name: 'Cube', subtitle: 'Query live Cube data including variances', category: 'Research', auth: 'api_key' as AuthMethod, tools: ['query_cube', 'list_measures', 'list_dimensions'] },
  { id: 'daloopa', name: 'Daloopa', subtitle: 'High-quality fundamental data from SEC filings', category: 'Research', auth: 'api_key' as AuthMethod, tools: ['search_filings', 'get_fundamentals', 'list_datasets_da'] },
  { id: 'factiva', name: 'Dow Jones Factiva', subtitle: 'Search the Factiva global news archive', category: 'Research', auth: 'api_key' as AuthMethod, tools: ['search_factiva', 'get_article_factiva', 'list_sources_factiva'] },
  { id: 'govtribe', name: 'GovTribe', subtitle: 'Government contracts, awards, and vendors', category: 'Research', auth: 'api_key' as AuthMethod, tools: ['search_contracts', 'list_awards', 'get_vendor'] },
  { id: 'moodys', name: "Moody's", subtitle: 'Credit and risk intelligence', category: 'Research', auth: 'api_key' as AuthMethod, tools: ['get_rating', 'list_issuers', 'get_risk_report'] },
  { id: 'morningstar', name: 'Morningstar', subtitle: 'Investment and fund research', category: 'Research', auth: 'api_key' as AuthMethod, tools: ['search_funds', 'get_fund_profile', 'list_holdings'] },
  { id: 'mt-newswires', name: 'MT Newswires', subtitle: 'Real-time global financial news', category: 'Research', auth: 'api_key' as AuthMethod, tools: ['latest_news', 'search_news_mt', 'get_article_mt'] },
  { id: 'particl', name: 'Particl Market Research', subtitle: 'E-commerce research answers in Codex', category: 'Research', auth: 'api_key' as AuthMethod, tools: ['search_products', 'get_price_trend', 'list_competitors'] },
  { id: 'pitchbook', name: 'PitchBook', subtitle: 'Structured private-capital market data', category: 'Research', auth: 'api_key' as AuthMethod, tools: ['search_companies_pb', 'get_deal_pb', 'list_funds_pb'] },
  { id: 'policynote', name: 'PolicyNote', subtitle: 'Structured policy and regulatory intelligence', category: 'Research', auth: 'api_key' as AuthMethod, tools: ['search_policies', 'get_regulation', 'list_jurisdictions'] },
  { id: 'quartr', name: 'Quartr', subtitle: 'Structured IR data from 14,500+ companies', category: 'Research', auth: 'api_key' as AuthMethod, tools: ['search_companies_q', 'get_earnings', 'list_events_q'] },
  { id: 'readwise', name: 'Readwise', subtitle: 'Official app for Readwise and Reader', category: 'Research', auth: 'oauth' as AuthMethod, tools: ['list_highlights', 'get_book', 'search_readwise'] },
  { id: 'scite', name: 'Scite', subtitle: 'Answers grounded in peer-reviewed research', category: 'Research', auth: 'api_key' as AuthMethod, tools: ['search_scite', 'get_citation_context', 'verify_claim'] },
  { id: 'taxdown', name: 'Taxdown', subtitle: 'Spanish tax guidance for individuals and self-employed', category: 'Research', auth: 'api_key' as AuthMethod, tools: ['ask_tax_es', 'list_deductions_es', 'simulate_return_es'] },
  { id: 'third-bridge', name: 'Third Bridge', subtitle: 'Expert industry insights for research', category: 'Research', auth: 'api_key' as AuthMethod, tools: ['search_transcripts_tb', 'get_expert', 'list_industries_tb'] },
  { id: 'tinman-ai', name: 'Tinman AI', subtitle: 'Underwrite home financing scenarios', category: 'Research', auth: 'api_key' as AuthMethod, tools: ['underwrite_scenario', 'list_products_tm', 'get_answer_tm'] },

  // ── Remaining from the original 14 (Communication / Finance) ──
  { id: 'paypal', name: 'PayPal', subtitle: 'Payments and invoicing', category: 'Productivity', auth: 'api_key' as AuthMethod, tools: ['list_transactions', 'create_invoice', 'send_payment'] },
  { id: 'intercom', name: 'Intercom', subtitle: 'Customer messaging platform', category: 'Productivity', auth: 'token' as AuthMethod, tools: ['list_conversations', 'send_message', 'search_contacts'] },
]

// Per-skill descriptions so the Services pane can render each tool
// in Codex-style "skill" cards (name + one-line description + add-
// to-workspace control). Keys are the tool ids from CONNECTORS.tools;
// anything missing falls back to the tool id itself.
const SKILL_DESCRIPTIONS: Record<string, string> = {
  // Google Drive
  search_files: 'Search files, folders, and shared drives by keyword or metadata.',
  read_file: 'Read the content of a file you own or have access to.',
  upload_file: 'Upload a new file or new version to Drive.',
  list_folders: 'List folders in a drive or parent folder.',
  // GitHub
  search_repos: 'Search public and private repositories by name, language, or topic.',
  list_issues: 'List open or closed issues in a repository.',
  create_issue: 'Open a new issue with title, body, and labels.',
  create_pr: 'Create a pull request from a branch to the base.',
  // Figma
  get_file: 'Fetch a Figma file tree (pages, frames, components).',
  get_components: 'List reusable components from a Figma file.',
  export_assets: 'Export assets (PNG, SVG, PDF) from a Figma file.',
  // Gmail
  search_emails: 'Search the inbox by sender, subject, date, or label.',
  read_email: 'Read the body and metadata of a specific email.',
  send_email: 'Compose and send an email to one or more recipients.',
  create_draft: 'Save a draft email without sending.',
  // Google Calendar
  list_events: 'List upcoming calendar events in a time window.',
  create_event: 'Create a new event with attendees and meeting link.',
  update_event: 'Change time, attendees, or details of an existing event.',
  find_free_time: 'Find free slots in one or more calendars.',
  // Hugging Face
  search_models: 'Search public models by task, library, or author.',
  model_info: 'Fetch metadata, tags, and usage info for a specific model.',
  run_inference: 'Run inference against a hosted Hugging Face model.',
  // Notion
  search_pages: 'Search pages and databases by keyword.',
  read_page: 'Read the full content of a page including blocks.',
  create_page: 'Create a new page under a parent page or database.',
  query_database: 'Query a Notion database with filters and sorting.',
  // Slack
  search_messages: 'Search across channels and DMs for keywords.',
  send_message: 'Post a message to a channel or thread.',
  list_channels: 'List channels you are a member of.',
  read_channel: 'Read recent messages from a specific channel.',
  // Canva
  list_designs: 'List designs in your Canva workspace.',
  create_design: 'Create a new design from a template or blank canvas.',
  export_design: 'Export a design as PDF, PNG, or other formats.',
  // PayPal
  list_transactions: 'List recent PayPal transactions in a time window.',
  create_invoice: 'Create and send a PayPal invoice to a customer.',
  send_payment: 'Send a payment to a PayPal account.',
  // Stripe
  list_charges: 'List Stripe charges with status, amount, and customer.',
  list_subscriptions: 'List active subscriptions and their customers.',
  // Atlassian
  search_issues: 'Search Jira issues by project, status, or JQL.',
  // Linear
  update_issue: 'Update a Linear issue status, assignee, or description.',
  list_projects: 'List projects in your Linear workspace.',
  // Intercom
  list_conversations: 'List recent support conversations.',
  search_contacts: 'Search Intercom contacts by email or external id.',

  // ── Hugging Face extras ──
  search_datasets: 'Search datasets by task, license, or language.',

  // ── Netlify ──
  netlify_deploy: 'Deploy a site or trigger a new build.',
  netlify_list_sites: 'List sites connected to this Netlify team.',
  netlify_env: 'Inspect or update environment variables for a site.',
  netlify_logs: 'Stream deploy logs and function execution traces.',

  // ── Vercel ──
  vercel_deploy: 'Deploy a project to Vercel production or a preview.',
  vercel_list_projects: 'List projects accessible to this Vercel account.',
  vercel_logs: 'Fetch build + runtime logs from a deployment.',
  vercel_env: 'Manage environment variables across Vercel environments.',

  // ── Game Studio ──
  prototype_game: 'Scaffold a browser-game prototype from a prompt.',
  publish_game: 'Build and publish a game to the hosted studio.',
  list_assets: 'List available sprites, audio, and scene assets.',

  // ── Superpowers ──
  plan_feature: 'Break a feature request into a TDD plan.',
  run_tdd: 'Run a red-green-refactor cycle for the current task.',
  debug_session: 'Start a structured debug session with rubber-ducking.',

  // ── CircleCI ──
  list_pipelines: 'List recent CircleCI pipelines for a project.',
  trigger_build: 'Trigger a CircleCI pipeline on a branch or tag.',
  get_job_logs: 'Fetch logs for a specific CircleCI job.',

  // ── Cloudflare ──
  list_zones: 'List Cloudflare zones (domains) on this account.',
  update_dns: 'Add or update a DNS record on a Cloudflare zone.',
  deploy_worker: 'Deploy a Cloudflare Worker script.',
  list_tunnels: 'List active Cloudflare Tunnels and their routes.',

  // ── Sentry ──
  list_issues_sentry: 'List recent Sentry issues with frequency + severity.',
  get_event: 'Fetch a specific Sentry event with stack trace.',
  search_events: 'Search Sentry events by query, release, or environment.',

  // ── Build iOS / macOS / Web / Android ──
  build_xcode: 'Invoke an Xcode build on the current scheme.',
  run_simulator: 'Launch an iOS simulator for the current target.',
  debug_ios: 'Attach the debugger and walk the iOS call stack.',
  run_macos: 'Launch the built macOS app for manual testing.',
  debug_macos: 'Attach the debugger and inspect macOS app state.',
  scaffold_app: 'Scaffold a new web app with the chosen stack.',
  run_review: 'Run the code-review checklist on recent changes.',
  deploy_web: 'Ship the web app to the configured hosting target.',
  run_emulator: 'Boot an Android emulator for the active profile.',
  capture_screen: 'Capture a screenshot of the running Android emulator.',
  dump_ui: 'Dump the current Android UI hierarchy for inspection.',

  // ── Expo ──
  expo_build: 'Run an Expo build for the current app.',
  expo_publish: 'Publish the Expo bundle to the update channel.',
  expo_logs: 'Tail device / build logs from Expo.',

  // ── CodeRabbit ──
  review_pr: 'Run AI code review on the currently-open PR.',
  summarize_diff: 'Summarize the intent of a diff or PR.',
  suggest_fixes: 'Suggest concrete fixes for review comments.',

  // ── Neon Postgres ──
  list_neon_projects: 'List Neon projects available to this account.',
  run_query: 'Run a SQL query against a Neon branch.',
  create_branch: 'Create a Neon database branch for safe iteration.',

  // ── Plugin Eval ──
  run_eval: 'Evaluate the current plugin against a dataset.',
  run_benchmark: 'Run a benchmark suite locally and collect metrics.',
  compare_results: 'Compare benchmark runs side-by-side.',

  // ── Cloudinary ──
  upload_media: 'Upload an image or video to Cloudinary.',
  search_media: 'Search the Cloudinary library by tag or metadata.',
  transform_image: 'Apply a Cloudinary transformation recipe.',

  // ── Hostinger ──
  create_site: 'Create a new Hostinger site from a prompt.',
  deploy_site: 'Deploy the current site to Hostinger.',
  configure_domain: 'Attach a custom domain to a Hostinger site.',

  // ── MarcoPolo ──
  create_sandbox: 'Spin up a secure MarcoPolo sandbox.',
  upload_data: 'Upload a dataset into the sandbox for analysis.',
  run_script: 'Run a user-supplied script inside the sandbox.',

  // ── Quicknode ──
  list_endpoints: 'List Quicknode endpoints across networks.',
  get_stats: 'Fetch usage + performance stats for an endpoint.',
  deploy_function: 'Deploy a Quicknode Function to an endpoint.',

  // ── SendGrid ──
  send_email_sg: 'Send an email via SendGrid.',
  list_templates: 'List dynamic email templates.',
  get_stats_sg: 'Fetch delivery + engagement stats.',

  // ── Statsig ──
  list_gates: 'List feature gates configured in Statsig.',
  get_experiment: 'Fetch an experiment definition and exposure stats.',
  update_config: 'Update a dynamic config value.',

  // ── Vantage ──
  get_cost: 'Get current cloud spend broken down by service.',
  list_recommendations: 'List Vantage cost-saving recommendations.',
  compare_clouds: 'Compare equivalent resources across cloud providers.',

  // ── YepCode ──
  create_tool: 'Define a new YepCode tool with code + schema.',
  run_tool: 'Execute a YepCode tool against live inputs.',
  list_tools: 'List tools in your YepCode workspace.',

  // ── Render ──
  render_deploy: 'Trigger a deploy on a Render service.',
  render_logs: 'Stream logs from a Render service.',
  render_list_services: 'List services in your Render account.',

  // ── Design extras ──
  render_video: 'Render a motion-graphics video from a prompt.',
  list_compositions: 'List Remotion compositions in the project.',
  preview_frame: 'Render a single preview frame for quick iteration.',
  create_figure: 'Create a new BioRender figure from a template.',
  export_figure: 'Export a BioRender figure to PNG or SVG.',

  // ── Lifestyle ──
  search_properties: 'Search Cogedim real-estate listings.',
  get_property: 'Fetch details for a Cogedim property.',
  list_vehicles: 'List vehicles available for FINN subscription.',
  book_subscription: 'Book a FINN car subscription.',
  list_registries: 'List MyRegistry.com registries you manage.',
  add_item: 'Add an item to a MyRegistry.com registry.',
  share_registry: 'Share a MyRegistry.com registry via link.',
  list_bills: 'List pending utility bills.',
  pay_bill: 'Pay a selected utility bill.',
  get_receipt: 'Fetch the receipt for a paid bill.',
  get_quote: 'Get a WeatherPromise protection quote.',
  create_policy: 'Create a WeatherPromise policy for a trip.',
  file_claim: 'File a weather-based claim on a policy.',

  // ── Productivity extras ──
  list_teams_chats: 'List Microsoft Teams chats and channels.',
  summarize_thread: 'Summarize a Teams thread into key points.',
  draft_followup: 'Draft a follow-up message for a Teams meeting.',
  list_sp_sites: 'List SharePoint sites accessible to the user.',
  read_sp_file: 'Read the content of a SharePoint file.',
  search_sp: 'Search SharePoint sites + documents by keyword.',
  search_outlook: 'Search the Outlook inbox.',
  draft_outlook: 'Draft an Outlook email reply.',
  send_outlook: 'Send an Outlook email.',
  list_outlook_events: 'List upcoming Outlook calendar events.',
  create_outlook_event: 'Create a new Outlook calendar event.',
  update_outlook_event: 'Reschedule or update an Outlook event.',
  list_recordings: 'List Jam screen recordings.',
  get_recording: 'Fetch metadata and transcript for a Jam recording.',
  share_recording: 'Share a Jam recording with a link.',
  search_box: 'Search Box for documents by keyword.',
  read_box_file: 'Read the content of a Box file.',
  upload_box: 'Upload a file to a Box folder.',
  query_events: 'Query Amplitude events with filters.',
  list_funnels: 'List defined Amplitude funnels.',
  get_cohort: 'Fetch an Amplitude cohort definition.',
  search_records: 'Search CRM records across objects.',
  create_record: 'Create a new CRM record.',
  update_record: 'Update fields on an existing CRM record.',
  search_mentions: 'Search recent brand mentions.',
  get_sentiment: 'Get sentiment score for a tracked brand.',
  list_projects_b24: 'List Brand24 tracking projects.',
  list_transactions_brex: 'List Brex card transactions.',
  list_cards: 'List Brex cards and their limits.',
  get_balance: 'Fetch the current Brex account balance.',
  list_deals: 'List Carta deals in the pipeline.',
  get_company: 'Fetch Carta company profile and fundraising history.',
  update_deal: 'Update stage or notes on a Carta deal.',
  get_gtm_metrics: 'Get real-time go-to-market metrics.',
  list_accounts: 'List target accounts from Channel99.',
  trace_pipeline: 'Trace a deal across the GTM pipeline.',
  list_meetings_cb: 'List meetings tracked by Circleback.',
  get_summary: 'Fetch AI summary for a meeting.',
  list_actions: 'List action items extracted from meetings.',
  list_tasks_cu: 'List ClickUp tasks in a space.',
  create_task_cu: 'Create a new ClickUp task.',
  update_task_cu: 'Update a ClickUp task status or assignee.',
  search_signals: 'Search Common Room community signals.',
  list_community: 'List community members with filters.',
  find_prospect: 'Find a prospect matching an ICP profile.',
  get_visibility: 'Get brand-visibility score for a topic.',
  get_sentiment_cond: 'Get Conductor sentiment score.',
  list_topics: 'List monitored topics in Conductor.',
  list_importers: 'List Coupler.io data importers.',
  run_importer: 'Run a Coupler.io importer manually.',
  list_sources: 'List available data sources.',
  search_coveo: 'Search enterprise content via Coveo.',
  list_sources_coveo: 'List indexed Coveo sources.',
  get_document: 'Fetch a Coveo-indexed document.',
  search_accounts_db: 'Search Demandbase accounts by intent or firmographic.',
  get_intent: 'Get intent signals for an account.',
  list_campaigns: 'List active Demandbase campaigns.',
  ask_docket: 'Ask Docket AI a sales-knowledge question.',
  list_playbooks: 'List Docket playbooks.',
  get_answer: 'Get a Docket answer with source citations.',
  list_devices_net: 'List Domotz-monitored network devices.',
  get_alerts: 'Get current Domotz alerts.',
  ping_device: 'Ping a network device to verify reachability.',
  search_insights: 'Search Dovetail insights by theme.',
  list_projects_dt: 'List Dovetail projects.',
  get_theme: 'Fetch a Dovetail theme and related data.',
  search_egnyte: 'Search Egnyte-stored documents.',
  read_egnyte: 'Read an Egnyte file.',
  upload_egnyte: 'Upload a file to an Egnyte folder.',
  list_meetings_ff: 'List Fireflies meetings.',
  get_transcript: 'Fetch transcript for a recorded meeting.',
  search_meetings: 'Search Fireflies meetings by keyword.',
  draft_email_fx: 'Draft an email in your personal voice.',
  list_templates_fx: 'List Fyxer email templates.',
  send_email_fx: 'Send an email composed via Fyxer.',
  list_granola_meetings: 'List Granola meetings.',
  get_notes: 'Fetch Granola notes for a meeting.',
  search_granola: 'Search Granola knowledge base.',
  search_network: 'Search your professional network.',
  find_person: 'Find a person matching given criteria.',
  suggest_intro: 'Suggest an introduction path to a target.',
  list_hs_conversations: 'List Help Scout conversations.',
  reply_hs: 'Reply to a Help Scout conversation.',
  assign_hs: 'Assign a Help Scout conversation to a teammate.',
  list_hl_contacts: 'List HighLevel CRM contacts.',
  send_campaign: 'Send a HighLevel campaign.',
  list_pipelines_hl: 'List HighLevel pipelines.',
  search_hubspot: 'Search HubSpot CRM records.',
  create_hs_contact: 'Create a new HubSpot contact.',
  update_hs_deal: 'Update a HubSpot deal stage or fields.',
  calculate_roi: 'Calculate ROI for a short-term-rental property.',
  list_properties_kb: 'List properties tracked in KeyBid Puls.',
  forecast_income: 'Forecast expected rental income.',
  search_mem: 'Search your Mem second-brain.',
  create_mem_note: 'Create a Mem note.',
  list_mem_collections: 'List Mem collections.',
  list_boards: 'List monday.com boards.',
  create_item_mon: 'Create a new monday.com item on a board.',
  update_item_mon: 'Update a monday.com item.',
  run_sql_md: 'Run a SQL query against MotherDuck.',
  list_tables_md: 'List tables in a MotherDuck database.',
  describe_table_md: 'Describe the schema of a MotherDuck table.',
  check_domain: 'Check whether a domain is available.',
  suggest_domains: 'Suggest alternative available domains.',
  register_domain: 'Register a domain via Network Solutions.',
  query_omni: 'Query Omni Analytics using the semantic model.',
  list_models_omni: 'List Omni semantic models.',
  get_metric: 'Fetch a specific Omni metric value.',
  list_otter_meetings: 'List Otter.ai meetings.',
  get_transcript_ot: 'Fetch an Otter.ai meeting transcript.',
  search_otter: 'Search Otter.ai transcripts.',
  list_deals_pd: 'List Pipedrive deals.',
  create_pd_deal: 'Create a new Pipedrive deal.',
  update_pd_contact: 'Update a Pipedrive contact.',
  list_pylon_tickets: 'List Pylon support tickets.',
  reply_pylon: 'Reply to a Pylon ticket.',
  resolve_pylon: 'Mark a Pylon ticket as resolved.',
  run_seo_audit: 'Run a Ranked AI SEO audit.',
  list_campaigns_ra: 'List Ranked AI campaigns.',
  get_ranking: 'Get current SERP ranking for a keyword.',
  list_payments_rz: 'List Razorpay payments.',
  create_refund_rz: 'Issue a Razorpay refund.',
  get_settlement: 'Get Razorpay settlement details.',
  list_read_meetings: 'List Read AI meetings.',
  get_summary_read: 'Fetch a Read AI meeting summary.',
  search_read: 'Search Read AI intelligence.',
  search_responsive: 'Search Responsive RFP content library.',
  create_rfp: 'Create a new RFP in Responsive.',
  list_projects_rsp: 'List Responsive projects.',
  get_domain_overview: 'Get Semrush overview for a domain.',
  list_keywords: 'List tracked keywords in Semrush.',
  get_backlinks: 'Fetch backlinks for a domain.',
  list_documents_sn: 'List SignNow documents awaiting signature.',
  send_for_signature: 'Send a document out for SignNow signature.',
  get_signing_status: 'Check the signing status of a document.',
  search_imagery: 'Search satellite imagery archive.',
  order_capture: 'Order a new satellite capture for a bounding box.',
  list_archive: 'List available satellite archive entries.',
  list_pipelines_st: 'List Streak pipelines inside Gmail.',
  create_box_st: 'Create a new Streak box (deal).',
  update_box_st: 'Update a Streak box.',
  list_tw_projects: 'List Teamwork.com projects.',
  create_tw_task: 'Create a Teamwork.com task.',
  update_tw_task: 'Update a Teamwork.com task status or assignee.',
  search_equipment: 'Search United Rentals equipment catalog.',
  get_quote_ur: 'Get a United Rentals rental quote.',
  place_order: 'Place a rental order.',
  get_strategy: 'Get a Waldo strategic recommendation.',
  list_plans_waldo: 'List Waldo strategy plans.',
  run_analysis: 'Run a Waldo strategy analysis.',
  list_sources_ws: 'List Windsor.ai marketing data sources.',
  run_sync: 'Run a Windsor.ai data sync.',
  get_dataset: 'Fetch a Windsor.ai dataset.',

  // ── Research ──
  search_papers: 'Search biomedical / life-sciences literature.',
  synthesize_evidence: 'Synthesize evidence across multiple papers.',
  run_parallel_analysis: 'Run parallel subagent analysis on a research question.',
  get_quote_al: 'Get the current Alpaca market quote.',
  list_positions: 'List open Alpaca positions.',
  place_order_al: 'Place an Alpaca trade order.',
  get_ticker: 'Get Binance ticker data.',
  list_pairs: 'List available Binance trading pairs.',
  get_orderbook: 'Fetch the Binance order book snapshot.',
  search_companies_cb: 'Search CB Insights companies.',
  get_funding: 'Fetch funding history for a company.',
  list_industries: 'List CB Insights industries.',
  query_cube: 'Query Cube data with measures and dimensions.',
  list_measures: 'List Cube measures.',
  list_dimensions: 'List Cube dimensions.',
  search_filings: 'Search Daloopa-indexed SEC filings.',
  get_fundamentals: 'Fetch structured company fundamentals.',
  list_datasets_da: 'List Daloopa datasets.',
  search_factiva: 'Search the Factiva news archive.',
  get_article_factiva: 'Fetch a Factiva article by id.',
  list_sources_factiva: 'List Factiva news sources.',
  search_contracts: 'Search government contracts on GovTribe.',
  list_awards: 'List awarded government contracts.',
  get_vendor: 'Fetch a government vendor profile.',
  get_rating: "Fetch a Moody's credit rating.",
  list_issuers: "List Moody's-rated issuers.",
  get_risk_report: "Fetch a Moody's risk report.",
  search_funds: 'Search Morningstar funds.',
  get_fund_profile: 'Fetch a Morningstar fund profile.',
  list_holdings: 'List top holdings for a fund.',
  latest_news: 'Fetch the latest MT Newswires headlines.',
  search_news_mt: 'Search MT Newswires by query.',
  get_article_mt: 'Fetch an MT Newswires article by id.',
  search_products: 'Search Particl e-commerce product data.',
  get_price_trend: 'Get price trend for a product.',
  list_competitors: 'List competing products or brands.',
  search_companies_pb: 'Search PitchBook companies.',
  get_deal_pb: 'Fetch a PitchBook deal record.',
  list_funds_pb: 'List PitchBook funds.',
  search_policies: 'Search PolicyNote policy + regulatory content.',
  get_regulation: 'Fetch a specific regulation.',
  list_jurisdictions: 'List PolicyNote jurisdictions.',
  search_companies_q: 'Search Quartr-covered public companies.',
  get_earnings: 'Fetch earnings call data for a company.',
  list_events_q: 'List upcoming IR events.',
  list_highlights: 'List Readwise highlights.',
  get_book: 'Fetch a Readwise book summary.',
  search_readwise: 'Search Readwise content.',
  search_scite: 'Search Scite for peer-reviewed answers.',
  get_citation_context: 'Fetch the citation context around a claim.',
  verify_claim: 'Verify a claim against peer-reviewed research.',
  ask_tax_es: 'Ask Taxdown a Spanish-tax question.',
  list_deductions_es: 'List Spanish tax deductions available to the user.',
  simulate_return_es: 'Simulate a Spanish tax-return outcome.',
  search_transcripts_tb: 'Search Third Bridge expert transcripts.',
  get_expert: 'Fetch a Third Bridge expert profile.',
  list_industries_tb: 'List Third Bridge industries.',
  underwrite_scenario: 'Underwrite a home-financing scenario.',
  list_products_tm: 'List Tinman AI loan products.',
  get_answer_tm: 'Get a Tinman AI loan-officer answer.',
}

// ── Browse catalog (Claude Desktop-style marketplace) ──

interface BrowseCatalogItem {
  id: string
  name: string
  description: string
  popularity?: string   // "Most popular", "#2 popular", etc.
  connected?: boolean
  category: string
  authUrl?: string      // URL to open for OAuth or setup
}

const BROWSE_CONNECTORS_CATALOG: BrowseCatalogItem[] = [
  // Communication
  { id: 'gmail', name: 'Gmail', description: 'Draft replies, summarize threads, and search your inbox', popularity: 'Most popular', category: 'Communication', authUrl: 'https://mail.google.com' },
  { id: 'slack', name: 'Slack', description: 'Send messages, create canvases, and fetch Slack data', popularity: '#4 popular', category: 'Communication', authUrl: 'https://slack.com' },
  { id: 'intercom', name: 'Intercom', description: 'Customer messaging, conversations, and support', category: 'Communication', authUrl: 'https://www.intercom.com' },
  { id: 'microsoft-teams', name: 'Microsoft Teams', description: 'Chat, meetings, and collaboration in Teams', category: 'Communication', authUrl: 'https://teams.microsoft.com' },
  // Productivity
  { id: 'google-calendar', name: 'Google Calendar', description: 'Manage your schedule and coordinate meetings', popularity: '#2 popular', category: 'Productivity', authUrl: 'https://calendar.google.com' },
  { id: 'google-drive', name: 'Google Drive', description: 'Access files, folders, and shared drives', popularity: '#3 popular', category: 'Productivity', authUrl: 'https://drive.google.com' },
  { id: 'notion', name: 'Notion', description: 'Connect your Notion workspace to search, update, and power workflows', popularity: '#5 popular', category: 'Productivity', authUrl: 'https://www.notion.so' },
  { id: 'monday', name: 'monday.com', description: 'Manage projects, boards, and workflows', category: 'Productivity', authUrl: 'https://monday.com' },
  { id: 'airtable', name: 'Airtable', description: 'Manage databases, tables, and automations', category: 'Productivity', authUrl: 'https://airtable.com' },
  { id: 'dropbox', name: 'Dropbox', description: 'Cloud storage, file sharing, and sync', category: 'Productivity', authUrl: 'https://www.dropbox.com' },
  { id: 'box', name: 'Box', description: 'Secure cloud content management and file sharing', category: 'Productivity', authUrl: 'https://www.box.com' },
  { id: 'wordpress', name: 'WordPress.com', description: 'Manage posts, pages, and site content', category: 'Productivity', authUrl: 'https://wordpress.com' },
  { id: 'clickup', name: 'ClickUp', description: 'Tasks, docs, goals, and project management', category: 'Productivity', authUrl: 'https://clickup.com' },
  { id: 'basecamp', name: 'Basecamp', description: 'Project management, team communication, and scheduling', category: 'Productivity', authUrl: 'https://basecamp.com' },
  // Project Management
  { id: 'asana', name: 'Asana', description: 'Track projects, manage tasks, and coordinate team work', category: 'Project Management', authUrl: 'https://asana.com' },
  { id: 'linear', name: 'Linear', description: 'Manage issues, projects, and team workflows', category: 'Project Management', authUrl: 'https://linear.app' },
  { id: 'atlassian', name: 'Atlassian Rovo', description: 'Access Jira and Confluence from Daena', category: 'Project Management', authUrl: 'https://www.atlassian.com' },
  // Design
  { id: 'canva', name: 'Canva', description: 'Search, create, autofill, and export Canva designs', popularity: '#6 popular', category: 'Design', authUrl: 'https://www.canva.com' },
  { id: 'figma', name: 'Figma', description: 'Generate diagrams and better code from Figma context', popularity: '#7 popular', category: 'Design', authUrl: 'https://www.figma.com' },
  // Development
  { id: 'github', name: 'GitHub', description: 'Repositories, issues, pull requests, and actions', popularity: '#8 popular', category: 'Development', authUrl: 'https://github.com' },
  { id: 'sentry', name: 'Sentry', description: 'Error tracking, performance monitoring, and debugging', category: 'Development', authUrl: 'https://sentry.io' },
  { id: 'cloudflare', name: 'Cloudflare', description: 'DNS, CDN, security, and Workers management', category: 'Development', authUrl: 'https://dash.cloudflare.com' },
  { id: 'vercel', name: 'Vercel', description: 'Deploy and manage web applications', category: 'Development', authUrl: 'https://vercel.com' },
  { id: 'hugging-face', name: 'Hugging Face', description: 'Models, datasets, and spaces for ML', category: 'Development', authUrl: 'https://huggingface.co' },
  // Data & Analytics
  { id: 'amplitude', name: 'Amplitude', description: 'Product analytics, user behavior, and insights', category: 'Analytics', authUrl: 'https://amplitude.com' },
  { id: 'hex', name: 'Hex', description: 'Collaborative data notebooks and analytics', category: 'Analytics', authUrl: 'https://hex.tech' },
  { id: 'snowflake', name: 'Snowflake', description: 'Cloud data warehouse queries and management', category: 'Analytics', authUrl: 'https://www.snowflake.com' },
  // Sales & CRM
  { id: 'hubspot', name: 'HubSpot', description: 'Chat with your CRM data to get personalized insights', category: 'Sales', authUrl: 'https://www.hubspot.com' },
  { id: 'salesforce', name: 'Salesforce', description: 'Access CRM records, contacts, and opportunities', category: 'Sales', authUrl: 'https://www.salesforce.com' },
  { id: 'clay', name: 'Clay', description: 'Enrich leads and automate outbound workflows', category: 'Sales', authUrl: 'https://www.clay.com' },
  // Finance
  { id: 'stripe', name: 'Stripe', description: 'View payments, subscriptions, and billing data', category: 'Finance', authUrl: 'https://dashboard.stripe.com' },
  { id: 'paypal', name: 'PayPal', description: 'Payments, invoicing, and transaction history', category: 'Finance', authUrl: 'https://www.paypal.com' },
  { id: 'square', name: 'Square', description: 'Payment processing, invoicing, and POS', category: 'Finance', authUrl: 'https://squareup.com' },
  { id: 'plaid', name: 'Plaid', description: 'Connect to bank accounts and financial data', category: 'Finance', authUrl: 'https://plaid.com' },
  // Automation
  { id: 'zapier', name: 'Zapier', description: 'Connect 5000+ apps and automate workflows', category: 'Automation', authUrl: 'https://zapier.com' },
  // Healthcare
  { id: 'apple-health', name: 'Apple Health', description: 'Access health records and lab results', category: 'Healthcare', authUrl: 'https://www.apple.com/health/' },
  { id: 'pubmed', name: 'PubMed', description: 'Search biomedical and life sciences literature', category: 'Healthcare', authUrl: 'https://pubmed.ncbi.nlm.nih.gov' },
  // Knowledge
  { id: 'gamma', name: 'Gamma', description: 'Create presentations, documents, and webpages with AI', category: 'Productivity', authUrl: 'https://gamma.app' },
  { id: 'granola', name: 'Granola', description: 'AI meeting notes and conversation summaries', category: 'Productivity', authUrl: 'https://www.granola.ai' },
]

const BROWSE_EXTENSIONS_CATALOG: BrowseCatalogItem[] = [
  // ── System & Files ──
  { id: 'filesystem', name: 'Filesystem', description: 'Read, write, and manage files on your computer', popularity: 'Most popular', category: 'System' },
  { id: 'desktop-commander', name: 'Desktop Commander', description: 'Build, explore, and automate on your local machine', popularity: '#2 popular', category: 'System' },
  { id: 'windows-mcp', name: 'Windows MCP', description: 'Windows OS interaction, screenshots, and automation', category: 'System' },
  { id: 'macos-defaults', name: 'macOS Defaults', description: 'Read and write macOS system preferences', category: 'System' },
  { id: 'shell', name: 'Shell', description: 'Execute shell commands with sandboxed access', category: 'System' },
  // ── Browser & Web ──
  { id: 'puppeteer', name: 'Puppeteer', description: 'Browser automation, screenshots, and web scraping', popularity: '#3 popular', category: 'Browser' },
  { id: 'playwright', name: 'Playwright', description: 'Cross-browser testing and automation', category: 'Browser' },
  { id: 'chrome-devtools', name: 'Chrome DevTools', description: 'Debug, inspect, and profile web pages via Chrome', category: 'Browser' },
  { id: 'fetch', name: 'Fetch', description: 'Make HTTP requests and fetch web content', category: 'Browser' },
  // ── Search ──
  { id: 'brave-search', name: 'Brave Search', description: 'Web search via Brave Search API', popularity: '#4 popular', category: 'Search' },
  { id: 'tavily', name: 'Tavily', description: 'AI-optimized search engine for agents', category: 'Search' },
  { id: 'exa', name: 'Exa', description: 'Neural search engine for finding relevant content', category: 'Search' },
  { id: 'google-search', name: 'Google Search', description: 'Search the web via Google Custom Search API', category: 'Search' },
  { id: 'serper', name: 'Serper', description: 'Google SERP API for structured search results', category: 'Search' },
  // ── Design ──
  { id: 'figma-mcp', name: 'Figma', description: 'Generate code from Figma designs and inspect components', popularity: '#5 popular', category: 'Design' },
  { id: 'canva-mcp', name: 'Canva', description: 'Create and manage Canva designs programmatically', category: 'Design' },
  { id: 'magic-mcp', name: '21st.dev Magic', description: 'AI component builder with design system awareness', category: 'Design' },
  // ── AI & Voice ──
  { id: 'elevenlabs', name: 'ElevenLabs', description: 'Text-to-speech, voice cloning, and AI voice agents', category: 'AI' },
  { id: 'openai-mcp', name: 'OpenAI', description: 'GPT models, DALL-E, Whisper, and embeddings', category: 'AI' },
  { id: 'anthropic-mcp', name: 'Anthropic', description: 'Claude API for reasoning, analysis, and code generation', category: 'AI' },
  { id: 'replicate', name: 'Replicate', description: 'Run open-source ML models in the cloud', category: 'AI' },
  { id: 'huggingface-mcp', name: 'Hugging Face', description: 'Models, datasets, spaces, and inference API', category: 'AI' },
  { id: 'memory', name: 'Memory', description: 'Persistent memory storage across conversations', category: 'AI' },
  // ── Documents ──
  { id: 'pdf-tools', name: 'PDF Tools', description: 'Fill forms, analyze, extract text, and annotate PDFs', category: 'Documents' },
  { id: 'pandoc', name: 'Pandoc', description: 'Convert between document formats (Markdown, DOCX, HTML, PDF)', category: 'Documents' },
  { id: 'markitdown', name: 'MarkItDown', description: 'Convert any file to Markdown for AI processing', category: 'Documents' },
  { id: 'google-docs-mcp', name: 'Google Docs', description: 'Read, create, and edit Google Docs', category: 'Documents' },
  // ── Data & Databases ──
  { id: 'postgres', name: 'PostgreSQL', description: 'Query and manage PostgreSQL databases', popularity: '#6 popular', category: 'Data' },
  { id: 'sqlite', name: 'SQLite', description: 'Query and manage local SQLite databases', category: 'Data' },
  { id: 'mysql', name: 'MySQL', description: 'Query and manage MySQL databases', category: 'Data' },
  { id: 'redis', name: 'Redis', description: 'In-memory data store, cache, and message broker', category: 'Data' },
  { id: 'mongodb', name: 'MongoDB', description: 'Query and manage MongoDB document databases', category: 'Data' },
  { id: 'supabase', name: 'Supabase', description: 'Postgres database, auth, storage, and realtime', category: 'Data' },
  { id: 'neon', name: 'Neon', description: 'Serverless Postgres with branching and autoscaling', category: 'Data' },
  { id: 'snowflake-mcp', name: 'Snowflake', description: 'Cloud data warehouse queries and management', category: 'Data' },
  { id: 'bigquery', name: 'BigQuery', description: 'Google BigQuery data warehouse queries', category: 'Data' },
  // ── Development ──
  { id: 'git', name: 'Git', description: 'Read, search, and analyze local Git repositories', popularity: '#7 popular', category: 'Development' },
  { id: 'github-mcp', name: 'GitHub', description: 'Issues, PRs, repos, actions, and code search', popularity: '#8 popular', category: 'Development' },
  { id: 'gitlab-mcp', name: 'GitLab', description: 'Merge requests, issues, pipelines, and repositories', category: 'Development' },
  { id: 'linear-mcp', name: 'Linear', description: 'Issue tracking, project management, and workflows', category: 'Development' },
  { id: 'jira-mcp', name: 'Jira', description: 'Issue tracking, sprints, and project management', category: 'Development' },
  { id: 'docker-mcp', name: 'Docker', description: 'Manage containers, images, volumes, and networks', category: 'Development' },
  { id: 'kubernetes', name: 'Kubernetes', description: 'Manage K8s clusters, pods, deployments, and services', category: 'Development' },
  { id: 'terraform', name: 'Terraform', description: 'Infrastructure as code management and planning', category: 'Development' },
  { id: 'vercel-mcp', name: 'Vercel', description: 'Deploy and manage web applications on Vercel', category: 'Development' },
  { id: 'netlify', name: 'Netlify', description: 'Deploy, manage, and monitor Netlify sites', category: 'Development' },
  { id: 'cloudflare-mcp', name: 'Cloudflare', description: 'DNS, CDN, Workers, and security management', category: 'Development' },
  { id: 'aws-mcp', name: 'AWS', description: 'Manage AWS services (S3, Lambda, EC2, CloudWatch)', category: 'Development' },
  { id: 'gcp-mcp', name: 'Google Cloud', description: 'Manage GCP services (Cloud Run, Storage, BigQuery)', category: 'Development' },
  { id: 'azure-mcp', name: 'Azure', description: 'Manage Azure services and resources', category: 'Development' },
  // ── Monitoring & Observability ──
  { id: 'sentry-mcp', name: 'Sentry', description: 'Error tracking, performance monitoring, and debugging', category: 'Monitoring' },
  { id: 'datadog-mcp', name: 'Datadog', description: 'Metrics, logs, traces, and infrastructure monitoring', category: 'Monitoring' },
  { id: 'grafana-mcp', name: 'Grafana', description: 'Dashboards, alerting, and observability', category: 'Monitoring' },
  { id: 'pagerduty', name: 'PagerDuty', description: 'Incident management and on-call scheduling', category: 'Monitoring' },
  // ── Communication ──
  { id: 'slack-mcp', name: 'Slack', description: 'Send messages, search channels, and manage workflows', popularity: '#9 popular', category: 'Communication' },
  { id: 'discord-mcp', name: 'Discord', description: 'Send messages, manage servers, and moderate channels', category: 'Communication' },
  { id: 'email-mcp', name: 'Email (SMTP)', description: 'Send and read emails via SMTP/IMAP', category: 'Communication' },
  { id: 'twilio', name: 'Twilio', description: 'SMS, voice calls, and messaging APIs', category: 'Communication' },
  // ── Productivity ──
  { id: 'google-calendar-mcp', name: 'Google Calendar', description: 'Manage events, find free time, and schedule meetings', category: 'Productivity' },
  { id: 'google-drive-mcp', name: 'Google Drive', description: 'Access, search, and manage files and folders', category: 'Productivity' },
  { id: 'google-sheets-mcp', name: 'Google Sheets', description: 'Read, write, and analyze spreadsheet data', category: 'Productivity' },
  { id: 'notion-mcp', name: 'Notion', description: 'Search, create, and update Notion pages and databases', popularity: '#10 popular', category: 'Productivity' },
  { id: 'todoist', name: 'Todoist', description: 'Task management, projects, and productivity tracking', category: 'Productivity' },
  { id: 'obsidian', name: 'Obsidian', description: 'Read and write Obsidian vault notes and knowledge graphs', category: 'Productivity' },
  { id: 'raycast', name: 'Raycast', description: 'macOS productivity launcher and extensions', category: 'Productivity' },
  // ── Analytics & Data Science ──
  { id: 'jupyter', name: 'Jupyter', description: 'Execute Python notebooks and data analysis', category: 'Analytics' },
  { id: 'dbt', name: 'dbt', description: 'Data transformation, testing, and documentation', category: 'Analytics' },
  { id: 'amplitude-mcp', name: 'Amplitude', description: 'Product analytics and user behavior insights', category: 'Analytics' },
  { id: 'mixpanel', name: 'Mixpanel', description: 'Event analytics and user engagement tracking', category: 'Analytics' },
  // ── CRM & Sales ──
  { id: 'salesforce-mcp', name: 'Salesforce', description: 'CRM records, contacts, opportunities, and reports', category: 'CRM' },
  { id: 'hubspot-mcp', name: 'HubSpot', description: 'CRM, marketing, sales, and service hub', category: 'CRM' },
  { id: 'apollo-mcp', name: 'Apollo', description: 'Prospecting, enrichment, and outreach sequences', category: 'CRM' },
  // ── Maps & Location ──
  { id: 'google-maps', name: 'Google Maps', description: 'Geocoding, directions, places, and distance matrix', category: 'Maps' },
  // ── Media ──
  { id: 'youtube', name: 'YouTube', description: 'Search videos, get transcripts, and channel analytics', category: 'Media' },
  { id: 'spotify', name: 'Spotify', description: 'Search music, manage playlists, and playback control', category: 'Media' },
  // ── Security ──
  { id: 'vault', name: 'HashiCorp Vault', description: 'Secrets management and data protection', category: 'Security' },
  { id: '1password', name: '1Password', description: 'Secure password and secrets management', category: 'Security' },
]

// ── Cloud-mode pre-installed extensions (mapped from BROWSE_EXTENSIONS_CATALOG) ──

const CLOUD_PREINSTALLED_EXTENSIONS: ExtensionData[] = BROWSE_EXTENSIONS_CATALOG.map((item) => ({
  id: item.id,
  name: item.name,
  description: item.description,
  enabled: true,
  permission: 'ASK_EACH_TIME',
}))

// ── Shared OAuth launcher (used by ConnectorRow and the Browse modal) ──
//
// Session 10: extracted from ConnectorRow so the Browse modal can start
// the same OAuth popup flow instead of opening the product homepage.
// When OAuth broker credentials are missing, opens the inline setup
// modal via `onRequestSetup` instead of navigating to /settings.

export interface StartOAuthOptions {
  connectorId: string
  connectorName: string
  onSuccess?: () => void
  onRequestSetup?: (missingField: string) => void
}

export async function startOAuthConnect(opts: StartOAuthOptions): Promise<void> {
  // Open the popup SYNCHRONOUSLY in the click gesture. If we wait until
  // after the await below to call window.open, Chrome/Safari/Edge all
  // block the popup because the call is no longer in the user-gesture
  // stack -- "the connect button does nothing" was exactly this.
  //
  // We point it at an interim loading page (served by the frontend
  // itself at /oauth-loading.html); once we have the real auth URL we
  // navigate this same popup to it. If the backend says "creds missing"
  // we close the popup and open the inline setup modal instead.
  const popup = window.open(
    '/oauth-loading.html',
    `daena_oauth_${opts.connectorId}`,
    'width=600,height=700,popup=yes',
  )
  if (!popup) {
    toast.error(
      `Popup blocked. Allow popups for localhost in your browser, then click Connect again.`,
      15_000,
    )
    return
  }

  try {
    const res = await api.get(`/connectors/${opts.connectorId}/oauth/authorize`)
    const data = res.data as {
      error_type?: string
      missing_field?: string
      authorization_url?: string
    }

    if (data?.error_type === 'oauth_not_configured') {
      popup.close()
      const missing = data.missing_field || 'OAuth credentials'
      if (opts.onRequestSetup) {
        opts.onRequestSetup(missing)
      } else {
        toast.error(
          `${opts.connectorName} OAuth not configured. Missing: ${missing}.`,
          10_000,
        )
      }
      return
    }

    const authUrl = data?.authorization_url
    if (!authUrl) {
      popup.close()
      toast.error(`Failed to get authorization URL for ${opts.connectorName}`)
      return
    }

    // Navigate the already-open popup to the real OAuth consent URL.
    popup.location.href = authUrl

    const handler = (event: MessageEvent) => {
      if (event.data?.type === 'oauth_success' && event.data?.connector === opts.connectorId) {
        toast.success(`${opts.connectorName} connected successfully`)
        window.removeEventListener('message', handler)
        opts.onSuccess?.()
      } else if (event.data?.type === 'oauth_error' && event.data?.connector === opts.connectorId) {
        toast.error(`${opts.connectorName} connection failed: ${event.data.error || 'Unknown error'}`)
        window.removeEventListener('message', handler)
      }
    }
    window.addEventListener('message', handler)
    setTimeout(() => window.removeEventListener('message', handler), 300_000)
  } catch (err: unknown) {
    popup.close()
    const axiosErr = err as {
      response?: { data?: { error_type?: string; missing_field?: string } }
    }
    // Connector not in OAUTH_PROVIDERS on the backend (e.g. Notion,
    // Linear, PayPal right now). Surface an actionable message rather
    // than a generic "Unknown error" toast.
    const errorText = JSON.stringify(axiosErr?.response?.data || {})
    if (errorText.includes('No OAuth provider configured')) {
      toast.error(
        `${opts.connectorName} OAuth is not yet supported. Supported: Gmail, Google Drive, Google Calendar, GitHub, Figma, Slack, Canva.`,
        12_000,
      )
      return
    }
    if (axiosErr?.response?.data?.error_type === 'oauth_not_configured') {
      const missing = axiosErr.response.data.missing_field || 'OAuth credentials'
      if (opts.onRequestSetup) {
        opts.onRequestSetup(missing)
      } else {
        toast.error(
          `${opts.connectorName} OAuth not configured. Missing: ${missing}.`,
          10_000,
        )
      }
      return
    }
    const msg = err instanceof Error ? err.message : 'Unknown error'
    toast.error(`Failed to start OAuth: ${msg}`)
  }
}


// ── Connector -> MCP server map (Session 10) ──
//
// For services that have an equivalent community MCP server, surface
// "Install the MCP server" as the PRIMARY no-configuration path. The
// MCP server ships with its own OAuth app credentials embedded, so the
// user doesn't need to register a Google Cloud project or paste client
// IDs -- exactly the same experience Claude Desktop provides. This is
// the pattern most Claude Desktop users actually use for Google,
// Notion, Slack, etc.
//
// Values point at official / well-maintained MCP servers. Source URLs
// go to the GitHub repo so the user can verify before installing.

interface MCPEquivalent {
  name: string         // Display name of the MCP server
  package: string      // npm package or command arg
  command: string      // "npx" | "uvx" | etc.
  args: string[]       // Command args
  repo_url: string     // Where the source lives
  auth_note: string    // One-line description of how auth works
}

const CONNECTOR_MCP_EQUIVALENT: Record<string, MCPEquivalent> = {
  'google-drive': {
    name: 'Google Drive MCP',
    package: '@modelcontextprotocol/server-gdrive',
    command: 'npx',
    args: ['-y', '@modelcontextprotocol/server-gdrive'],
    repo_url: 'https://github.com/modelcontextprotocol/servers/tree/main/src/gdrive',
    auth_note: 'Pops a Google sign-in window the first time you use a tool. No Client ID setup.',
  },
  'gmail': {
    name: 'Gmail MCP',
    package: '@gongrzhe/server-gmail-autoauth-mcp',
    command: 'npx',
    args: ['-y', '@gongrzhe/server-gmail-autoauth-mcp'],
    repo_url: 'https://github.com/GongRzhe/Gmail-MCP-Server',
    auth_note: 'Auto-launches Google OAuth on first call. No configuration needed.',
  },
  'google-calendar': {
    name: 'Google Calendar MCP',
    package: '@cocal/google-calendar-mcp',
    command: 'npx',
    args: ['-y', '@cocal/google-calendar-mcp'],
    repo_url: 'https://github.com/nspady/google-calendar-mcp',
    auth_note: 'Handles Google OAuth inside the MCP server.',
  },
  'slack': {
    name: 'Slack MCP',
    package: '@modelcontextprotocol/server-slack',
    command: 'npx',
    args: ['-y', '@modelcontextprotocol/server-slack'],
    repo_url: 'https://github.com/modelcontextprotocol/servers/tree/main/src/slack',
    auth_note: 'Uses a Slack user token you generate once. Clear setup guide in the repo.',
  },
  'github': {
    name: 'GitHub MCP',
    package: '@modelcontextprotocol/server-github',
    command: 'npx',
    args: ['-y', '@modelcontextprotocol/server-github'],
    repo_url: 'https://github.com/modelcontextprotocol/servers/tree/main/src/github',
    auth_note: 'Uses a GitHub personal access token. Fastest path: 60 seconds.',
  },
  'notion': {
    name: 'Notion MCP',
    package: '@notionhq/notion-mcp-server',
    command: 'npx',
    args: ['-y', '@notionhq/notion-mcp-server'],
    repo_url: 'https://github.com/makenotion/notion-mcp-server',
    auth_note: 'Uses a Notion integration token. Official Notion-built server.',
  },
  'figma': {
    name: 'Figma MCP',
    package: 'figma-developer-mcp',
    command: 'npx',
    args: ['-y', 'figma-developer-mcp'],
    repo_url: 'https://github.com/GLips/Figma-Context-MCP',
    auth_note: 'Uses a Figma personal access token.',
  },
}


// ── Service setup modal (Session 10 -- rewritten)
//
// When the user clicks "Connect with Google" and the backend says OAuth
// isn't configured, this modal explains the choice clearly:
//
//   PRIMARY PATH: Install the community MCP server (one click). The
//   MCP server handles its own OAuth -- Daena doesn't need Client ID.
//   This is what Claude Desktop does for the same connectors.
//
//   ADVANCED PATH: Register your own OAuth app at Google Cloud (or the
//   provider), paste Client ID + Secret. For power users who want a
//   private OAuth app under their own identity.
//
//   FUTURE PATH: Daena hosted broker at broker.daena.mas-ai.co -- no
//   setup at all. Requires MAS-AI to register OAuth apps with each
//   provider and deploy the broker service.
//
// Closing the door on the "paste credentials as a blind first step"
// pattern that was confusing operators.

function OAuthSetupModal({
  connectorId,
  connectorName,
  missingField,
  onClose,
  onSaved,
}: {
  connectorId: string
  connectorName: string
  missingField: string
  onClose: () => void
  onSaved: () => void
}) {
  const [clientId, setClientId] = useState('')
  const [clientSecret, setClientSecret] = useState('')
  const [saving, setSaving] = useState(false)
  const [installing, setInstalling] = useState(false)
  const [showAdvanced, setShowAdvanced] = useState(false)
  const secretField = missingField.replace('_CLIENT_ID', '_CLIENT_SECRET')

  const mcp = CONNECTOR_MCP_EQUIVALENT[connectorId]

  const handleInstallMCP = async () => {
    if (!mcp) return
    setInstalling(true)
    try {
      // Forward the real command + args (e.g. ``npx -y
      // @modelcontextprotocol/server-gdrive``) so the backend writes
      // a working entry to claude_desktop_config.json. Previously we
      // only sent the internal id ("mcp-google-drive") and the
      // server wrote ``npx -y mcp-google-drive`` -- which is not a
      // real npm package, so the install silently produced a broken
      // config.
      await api.post('/connections/extensions/install', {
        id: `mcp-${connectorId}`,
        name: mcp.name,
        description: mcp.auth_note,
        command: mcp.command,
        args: mcp.args,
      })
      toast.success(
        `${mcp.name} installed. The MCP server will prompt you to sign in when you first use a ${connectorName} tool.`,
        10_000,
      )
      onSaved()
    } catch {
      toast.error(
        `Failed to install ${mcp.name}. Check your internet connection and try again.`,
      )
    } finally {
      setInstalling(false)
    }
  }

  const handleSave = async () => {
    if (!clientId.trim() || !clientSecret.trim()) {
      toast.error('Both Client ID and Client Secret are required')
      return
    }
    setSaving(true)
    try {
      await api.post('/settings/oauth-credentials', {
        connector_id: connectorId,
        client_id_field: missingField,
        client_id: clientId.trim(),
        client_secret_field: secretField,
        client_secret: clientSecret.trim(),
      })
      onSaved()
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Save failed'
      toast.error(`Failed to save credentials: ${msg}`)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={onClose}
    >
      <motion.div
        initial={{ opacity: 0, scale: 0.96 }}
        animate={{ opacity: 1, scale: 1 }}
        className="w-[560px] max-w-[92vw] max-h-[90vh] overflow-y-auto rounded-2xl bg-midnight-500 border border-white/10 p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start gap-3 mb-5">
          <div className="w-10 h-10 rounded-lg bg-primary-500/10 flex items-center justify-center text-primary-400 shrink-0">
            <Plug size={20} />
          </div>
          <div className="flex-1">
            <h2 className="text-lg font-display font-bold text-starlight-100">
              Connect {connectorName}
            </h2>
            <p className="text-xs text-starlight-400 mt-1">
              Choose how you want to authenticate. Install the MCP server for a one-click
              setup, or bring your own OAuth app for full control.
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded hover:bg-white/5 text-starlight-500 cursor-pointer"
          >
            <XCircle size={18} />
          </button>
        </div>

        {/* PRIMARY: Install the MCP server */}
        {mcp ? (
          <div className="mb-3 p-4 rounded-xl bg-primary-500/10 border border-primary-500/30">
            <div className="flex items-start gap-3 mb-3">
              <div className="w-9 h-9 rounded-lg bg-primary-500/20 flex items-center justify-center text-primary-400 shrink-0">
                <Puzzle size={18} />
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <p className="text-sm font-semibold text-starlight-100">
                    Install {mcp.name}
                  </p>
                  <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-accent-green/20 text-accent-green font-semibold uppercase tracking-wider">
                    Recommended
                  </span>
                </div>
                <p className="text-[12px] text-starlight-400 mt-1">{mcp.auth_note}</p>
                <p className="text-[11px] text-starlight-500 mt-2 font-mono">
                  {mcp.command} {mcp.args.join(' ')}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={handleInstallMCP}
                disabled={installing}
                className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold bg-primary-500 text-white hover:bg-primary-400 disabled:opacity-50 cursor-pointer"
              >
                {installing ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />}
                {installing ? 'Installing...' : `Install ${mcp.name}`}
              </button>
              <a
                href={mcp.repo_url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs text-starlight-400 hover:text-primary-400 hover:bg-white/5 cursor-pointer"
              >
                View source <ExternalLink size={11} />
              </a>
            </div>
          </div>
        ) : (
          <div className="mb-3 p-4 rounded-xl bg-white/[0.02] border border-white/5">
            <div className="flex items-start gap-2 text-xs text-starlight-400">
              <Puzzle size={14} className="shrink-0 mt-0.5 text-starlight-500" />
              <div>
                No official MCP server catalogued for {connectorName} yet. Use the
                advanced path below, or{' '}
                <a
                  href="https://github.com/modelcontextprotocol/servers"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-primary-400 hover:text-primary-300 inline-flex items-center gap-1"
                >
                  browse community MCP servers <ExternalLink size={10} />
                </a>
                {' '}and add one via Browse MCP servers.
              </div>
            </div>
          </div>
        )}

        {/* Hosted broker (future) - demoted to secondary info line */}
        <div className="mb-4 flex items-start gap-2 px-3 py-2 rounded-lg bg-white/[0.02] border border-white/5">
          <Shield size={12} className="text-accent-green mt-0.5 shrink-0" />
          <p className="text-[11px] text-starlight-400 leading-relaxed">
            <span className="font-semibold text-accent-green">Coming soon:</span>{' '}
            Daena hosted OAuth broker at <span className="font-mono">broker.daena.mas-ai.co</span>.
            Zero setup, just click Connect.
          </p>
        </div>

        {/* ADVANCED: manual OAuth configuration (collapsed by default) */}
        <div className="border-t border-white/5 pt-4">
          <button
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="flex items-center gap-2 text-xs text-starlight-400 hover:text-starlight-200 cursor-pointer mb-3"
          >
            {showAdvanced ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
            Advanced: use my own OAuth app
          </button>

          {showAdvanced && (
            <div className="space-y-3">
              <p className="text-[11px] text-starlight-500 leading-relaxed">
                For power users: register your own OAuth app at the provider and paste the
                Client ID + Secret below. Daena will use YOUR OAuth app instead of an MCP
                server.{' '}
                {connectorId.startsWith('google') && (
                  <a
                    href="https://console.cloud.google.com/apis/credentials"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-primary-400 hover:text-primary-300 inline-flex items-center gap-1"
                  >
                    Open Google Cloud Console <ExternalLink size={10} />
                  </a>
                )}
                {connectorId === 'github' && (
                  <a
                    href="https://github.com/settings/developers"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-primary-400 hover:text-primary-300 inline-flex items-center gap-1"
                  >
                    Open GitHub OAuth apps <ExternalLink size={10} />
                  </a>
                )}
                {connectorId === 'slack' && (
                  <a
                    href="https://api.slack.com/apps"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-primary-400 hover:text-primary-300 inline-flex items-center gap-1"
                  >
                    Open Slack apps <ExternalLink size={10} />
                  </a>
                )}
              </p>
              <div>
                <label className="text-[10px] font-semibold text-starlight-400 uppercase tracking-wider">
                  {missingField}
                </label>
                <input
                  type="text"
                  value={clientId}
                  onChange={(e) => setClientId(e.target.value)}
                  placeholder="Paste your OAuth Client ID"
                  className="mt-1 w-full px-3 py-2 rounded-lg bg-midnight-400 border border-white/5 text-sm text-starlight-200 placeholder:text-starlight-500 focus:outline-none focus:border-primary-500/40"
                />
              </div>
              <div>
                <label className="text-[10px] font-semibold text-starlight-400 uppercase tracking-wider">
                  {secretField}
                </label>
                <input
                  type="password"
                  value={clientSecret}
                  onChange={(e) => setClientSecret(e.target.value)}
                  placeholder="Paste your OAuth Client Secret"
                  className="mt-1 w-full px-3 py-2 rounded-lg bg-midnight-400 border border-white/5 text-sm text-starlight-200 placeholder:text-starlight-500 focus:outline-none focus:border-primary-500/40"
                />
              </div>
              <p className="text-[10px] text-starlight-500">
                Stored in Daena&apos;s local vault. Never logged, never sent to third parties
                besides {connectorName} itself during consent.
              </p>
              <div className="flex items-center justify-end gap-2 pt-1">
                <button
                  onClick={handleSave}
                  disabled={saving || !clientId.trim() || !clientSecret.trim()}
                  className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs bg-white/5 text-starlight-200 hover:bg-white/10 disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
                >
                  {saving ? <Loader2 size={12} className="animate-spin" /> : <Save size={12} />}
                  {saving ? 'Saving...' : 'Save & Enable'}
                </button>
              </div>
            </div>
          )}
        </div>

        <div className="flex items-center justify-end gap-2 mt-5 pt-4 border-t border-white/5">
          <button
            onClick={onClose}
            className="px-3 py-2 rounded-lg text-xs text-starlight-400 hover:bg-white/5 cursor-pointer"
          >
            Close
          </button>
        </div>
      </motion.div>
    </div>
  )
}


// ── Permission Select (Allow / Ask each time / Block) ──

type Permission = 'ALLOW' | 'ASK_EACH_TIME' | 'BLOCK'

function PermissionSelect({ value, onChange }: { value: Permission; onChange: (v: Permission) => void }) {
  const [open, setOpen] = useState(false)
  // Session 10: Claude Desktop parity -- pills are bigger and higher
  // contrast so "Ask" reads at a glance. Old opacities (5% bg, 30%
  // border) were too dim on midnight-500; at 12% / 50% they match
  // Claude Desktop's permission pills.
  const colors: Record<Permission, { text: string; bg: string; border: string; dot: string }> = {
    ALLOW: { text: 'text-accent-green', bg: 'bg-accent-green/12', border: 'border-accent-green/50', dot: 'bg-accent-green' },
    ASK_EACH_TIME: { text: 'text-accent-amber', bg: 'bg-accent-amber/12', border: 'border-accent-amber/50', dot: 'bg-accent-amber' },
    BLOCK: { text: 'text-accent-red', bg: 'bg-accent-red/12', border: 'border-accent-red/50', dot: 'bg-accent-red' },
  }
  const labels: Record<Permission, string> = { ALLOW: 'Allow', ASK_EACH_TIME: 'Ask', BLOCK: 'Block' }
  const options: Permission[] = ['ALLOW', 'ASK_EACH_TIME', 'BLOCK']
  const c = colors[value]

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className={`flex items-center gap-1.5 text-[11px] font-semibold px-3 py-1.5 rounded-md border cursor-pointer transition-colors hover:brightness-110 ${c.text} ${c.bg} ${c.border}`}
      >
        <span className={`w-2 h-2 rounded-full ${c.dot}`} />
        {labels[value]}
        <ChevronDown size={11} className={`transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      <AnimatePresence>
        {open && (
          <>
            <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
            <motion.div
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              transition={{ duration: 0.1 }}
              className="absolute right-0 top-full mt-1 w-28 rounded-lg bg-midnight-200 border border-white/10 shadow-xl z-50 py-1"
            >
              {options.map((opt) => {
                const oc = colors[opt]
                return (
                  <button
                    key={opt}
                    onClick={() => { onChange(opt); setOpen(false) }}
                    className={`w-full flex items-center gap-2 px-3 py-2 text-[11px] font-medium text-left transition-colors cursor-pointer hover:bg-white/5 ${
                      value === opt ? oc.text : 'text-starlight-300'
                    }`}
                  >
                    <span className={`w-2 h-2 rounded-full ${oc.dot}`} />
                    {labels[opt]}
                    {value === opt && <CheckCircle2 size={11} className="ml-auto" />}
                  </button>
                )
              })}
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  )
}

// ── Expandable Config Panel wrapper ──

function ConfigPanel({ expanded, children }: { expanded: boolean; children: React.ReactNode }) {
  return (
    <AnimatePresence>
      {expanded && (
        <motion.div
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: 'auto', opacity: 1 }}
          exit={{ height: 0, opacity: 0 }}
          transition={{ duration: 0.2, ease: 'easeInOut' }}
          className="overflow-hidden"
        >
          <div className="px-4 pb-4 pt-1 ml-14 border-t border-white/5 space-y-3">
            {children}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

// ── Three-dot menu ──

function ContextMenu({ items, onClose }: { items: { label: string; icon: React.ReactNode; onClick: () => void; danger?: boolean }[]; onClose: () => void }) {
  return (
    <>
      <div className="fixed inset-0 z-40" onClick={onClose} />
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.95 }}
        className="absolute right-0 top-full mt-1 w-48 rounded-lg bg-midnight-200 border border-white/10 shadow-xl z-50 py-1"
      >
        {items.map((item) => (
          <button
            key={item.label}
            onClick={() => { item.onClick(); onClose() }}
            className={`w-full flex items-center gap-2 px-3 py-2 text-xs text-left transition-colors cursor-pointer ${
              item.danger ? 'text-accent-red hover:bg-accent-red/10' : 'text-starlight-300 hover:bg-white/5'
            }`}
          >
            {item.icon}
            {item.label}
          </button>
        ))}
      </motion.div>
    </>
  )
}

// ── Runtime Row with expandable config ──

function RuntimeRow({ runtime, isPrimary, expanded, onToggleExpand, onSetPrimary, onTest, onRefreshAuth }: {
  runtime: RuntimeData
  isPrimary: boolean
  expanded: boolean
  onToggleExpand: () => void
  onSetPrimary: () => void
  onTest: () => void
  onRefreshAuth?: () => void
}) {
  const [menuOpen, setMenuOpen] = useState(false)
  const [testing, setTesting] = useState(false)
  const Icon = RUNTIME_ICONS[runtime.runtime_id] || Cpu

  const isOnline = runtime.status === 'online'
  const isInstalled = runtime.installed
  const isAuthenticated = runtime.subscription?.is_authenticated ?? true

  const handleTest = async () => {
    setTesting(true)
    onTest()
    setTimeout(() => setTesting(false), 5000)
  }

  return (
    <div>
      <div
        className="flex items-center gap-4 px-4 py-3 hover:bg-white/[0.02] transition-colors rounded-lg group cursor-pointer"
        onClick={onToggleExpand}
      >
        <div className="w-10 h-10 rounded-lg bg-midnight-400/60 flex items-center justify-center shrink-0">
          <Icon size={22} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-starlight-100">{runtime.display_name}</span>
            {isPrimary && <Crown size={12} className="text-accent-amber" aria-label="Primary Mind" />}
            {runtime.subscription?.is_authenticated && (
              <span className="flex items-center gap-1 text-[10px] text-status-success">
                <CheckCircle2 size={10} />
                Connected
              </span>
            )}
          </div>
          <p className="text-xs text-starlight-500 truncate">
            {isOnline && runtime.subscription?.is_authenticated
              ? `Connected${runtime.subscription.plan_name ? ` (${runtime.subscription.plan_name})` : ''}`
              : isInstalled ? 'Installed, not authenticated'
              : 'Not installed'}
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0" onClick={(e) => e.stopPropagation()}>
          {isOnline && isAuthenticated ? (
            <button
              onClick={(e) => {
                e.stopPropagation()
                toast.info(`${runtime.display_name} disconnected. Click "Connect" to reconnect.`)
                // Trigger refresh to update status
                onRefreshAuth?.()
              }}
              className="px-3 py-1 rounded-lg text-xs bg-accent-green/10 text-accent-green hover:bg-status-error/10 hover:text-status-error cursor-pointer transition-colors group/conn"
            >
              <span className="group-hover/conn:hidden">Connected</span>
              <span className="hidden group-hover/conn:inline">Disconnect</span>
            </button>
          ) : isOnline && !isAuthenticated ? (
            <button
              onClick={(e) => {
                e.stopPropagation()
                const urls: Record<string, string> = {
                  'claude_code': 'https://docs.anthropic.com/en/docs/claude-code',
                  'codex': 'https://github.com/openai/codex',
                  'gemini_cli': 'https://github.com/google-gemini/gemini-cli',
                  'grok_cli': 'https://docs.x.ai/overview',
                  'ollama': 'https://ollama.ai',
                }
                const url = urls[runtime.runtime_id] || runtime.subscription?.login_url
                if (url) window.open(url, '_blank')
                else toast.info(`Run the auth command for ${runtime.display_name} in your terminal.`)
              }}
              className="px-3 py-1 rounded-lg text-xs bg-accent-amber/10 text-accent-amber hover:bg-accent-amber/20 cursor-pointer"
            >
              Connect
            </button>
          ) : isInstalled ? (
            <button
              onClick={(e) => {
                e.stopPropagation()
                const urls: Record<string, string> = {
                  'claude_code': 'https://docs.anthropic.com/en/docs/claude-code',
                  'codex': 'https://github.com/openai/codex',
                  'gemini_cli': 'https://github.com/google-gemini/gemini-cli',
                  'grok_cli': 'https://docs.x.ai/overview',
                  'ollama': 'https://ollama.ai',
                }
                const url = urls[runtime.runtime_id] || runtime.subscription?.login_url
                if (url) window.open(url, '_blank')
              }}
              className="px-3 py-1 rounded-lg text-xs bg-accent-amber/10 text-accent-amber hover:bg-accent-amber/20 cursor-pointer"
            >
              Connect
            </button>
          ) : (
            <button
              onClick={(e) => {
                e.stopPropagation()
                const urls: Record<string, string> = {
                  'claude_code': 'https://docs.anthropic.com/en/docs/claude-code',
                  'codex': 'https://github.com/openai/codex',
                  'gemini_cli': 'https://github.com/google-gemini/gemini-cli',
                  'grok_cli': 'https://docs.x.ai/overview',
                  'ollama': 'https://ollama.ai',
                }
                const url = urls[runtime.runtime_id] || runtime.subscription?.login_url
                if (url) window.open(url, '_blank')
                else toast.info(`Visit the ${runtime.display_name} website for setup instructions.`)
              }}
              className="px-3 py-1 rounded-lg text-xs bg-primary-500/10 text-primary-400 hover:bg-primary-500/20 cursor-pointer flex items-center gap-1"
            >
              Setup <ExternalLink size={10} className="opacity-50" />
            </button>
          )}
          {expanded ? <ChevronUp size={14} className="text-starlight-400" /> : <ChevronDown size={14} className="text-starlight-400" />}
          {isOnline && (
            <div className="relative">
              <button onClick={() => setMenuOpen(!menuOpen)} className="p-1 rounded hover:bg-white/5 text-starlight-500 cursor-pointer">
                <MoreVertical size={14} />
              </button>
              <AnimatePresence>
                {menuOpen && (
                  <ContextMenu
                    onClose={() => setMenuOpen(false)}
                    items={[
                      { label: 'Test connection', icon: testing ? <Loader2 size={12} className="animate-spin" /> : <CheckCircle2 size={12} />, onClick: handleTest },
                      { label: isPrimary ? 'Primary Mind' : 'Set as Primary Mind', icon: <Crown size={12} />, onClick: onSetPrimary },
                    ]}
                  />
                )}
              </AnimatePresence>
            </div>
          )}
        </div>
      </div>

      {/* Expandable config panel */}
      <ConfigPanel expanded={expanded}>
        <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-xs">
          <div>
            <span className="text-starlight-500">Status</span>
            <p className="text-starlight-200 font-medium flex items-center gap-1.5 mt-0.5">
              <span className={`w-1.5 h-1.5 rounded-full ${isOnline ? 'bg-accent-green' : 'bg-accent-red'}`} />
              {isOnline ? 'Online' : isInstalled ? 'Offline' : 'Not installed'}
            </p>
          </div>
          <div>
            <span className="text-starlight-500">Authentication</span>
            <p className="text-starlight-200 font-medium mt-0.5">
              {isAuthenticated ? (runtime.subscription?.user_display || 'Authenticated') : 'Not authenticated'}
            </p>
          </div>
          {runtime.subscription?.plan_name && (
            <div>
              <span className="text-starlight-500">Plan</span>
              <p className="text-starlight-200 font-medium mt-0.5">{runtime.subscription.plan_name}</p>
            </div>
          )}
          <div>
            <span className="text-starlight-500">Primary Mind</span>
            <p className="text-starlight-200 font-medium mt-0.5">{isPrimary ? 'Yes (active)' : 'No'}</p>
          </div>
        </div>
        <div className="flex items-center gap-2 pt-2">
          {!isPrimary && isOnline && (
            <button
              onClick={onSetPrimary}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs bg-accent-amber/10 text-accent-amber hover:bg-accent-amber/20 cursor-pointer"
            >
              <Crown size={12} /> Set as Primary Mind
            </button>
          )}
          {isOnline && (
            <button
              onClick={handleTest}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs bg-white/5 text-starlight-300 hover:bg-white/10 cursor-pointer"
            >
              {testing ? <Loader2 size={12} className="animate-spin" /> : <Zap size={12} />} Test connection
            </button>
          )}
          {runtime.subscription?.is_authenticated && (
            <button
              onClick={async () => {
                const ok = await confirmDialog({
                  title: `Disconnect ${runtime.display_name}?`,
                  message: 'You can reconnect anytime.',
                  confirmLabel: 'Disconnect',
                  variant: 'warning',
                })
                if (!ok) return
                try {
                  await api.post(`/runtimes/${runtime.runtime_id}/disconnect`)
                  toast.success(`${runtime.display_name} disconnected`)
                  onRefreshAuth?.()
                } catch {
                  toast.error('Failed to disconnect')
                }
              }}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs text-accent-red bg-accent-red/10 border border-accent-red/20 hover:bg-accent-red/20 cursor-pointer"
            >
              <Unplug size={12} />
              Disconnect
            </button>
          )}
        </div>
      </ConfigPanel>
    </div>
  )
}

// ── Connector Row with expandable config ──

function ConnectorRow({ connector, connected, instanceId, accountIdentity, expanded, onToggleExpand, onDisconnect, fetchInstances, selected, onSelect, onRequestOAuthSetup, isLive }: {
  connector: typeof CONNECTORS[0]
  connected: boolean
  instanceId: string | null
  accountIdentity?: string
  expanded: boolean
  onToggleExpand: () => void
  onDisconnect: (instanceId: string) => void
  fetchInstances?: () => void
  selected?: boolean
  onSelect?: (id: string, checked: boolean) => void
  onRequestOAuthSetup?: (missingField: string) => void
  // When true, the plugin's MCP adapter is in the live bootstrap
  // registry -- i.e. chat can dispatch plugin.call_tool to it right
  // now without any restart. Shown as a green "Live" dot next to
  // the skill/category pills.
  isLive?: boolean
}) {
  const [menuOpen, setMenuOpen] = useState(false)
  const [apiKeyValue, setApiKeyValue] = useState('')
  const [saving, setSaving] = useState(false)
  // Advanced mode = expose per-tool Allow/Ask/Block controls inside
  // the capabilities list. Off by default (per TICKET-S16 UX rework)
  // because account-level auth already gates tool access; per-tool
  // controls are defense-in-depth for power users only.
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [toolPermissions, setToolPermissions] = useState<Record<string, Permission>>(() => {
    const init: Record<string, Permission> = {}
    for (const t of connector.tools) init[t] = 'ASK_EACH_TIME'
    return init
  })
  const Icon = CONNECTOR_ICONS[connector.id] || Plug

  const authLabels: Record<AuthMethod, string> = {
    oauth: 'OAuth 2.0',
    api_key: 'API Key',
    token: 'Access Token',
  }

  const handleSaveApiKey = async () => {
    if (!apiKeyValue.trim()) return
    setSaving(true)
    try {
      // Attempt to create a connection instance with the provided key
      await api.post('/connections/instances', {
        connector_id: connector.id,
        credentials: { api_key: apiKeyValue.trim() },
      })
      toast.success(`${connector.name} connected successfully`)
      setApiKeyValue('')
    } catch {
      toast.error(`Failed to connect ${connector.name}. Check your key and try again.`)
    } finally {
      setSaving(false)
    }
  }

  const handleOAuthConnect = async () => {
    // Session 10: delegates to shared startOAuthConnect. The on-missing-
    // creds path now signals the parent page to open an inline setup
    // modal instead of navigating to /settings (which was confusing --
    // the operator clicked "Connect with Google" and ended up on a
    // Daena settings page).
    await startOAuthConnect({
      connectorId: connector.id,
      connectorName: connector.name,
      onSuccess: () => { void fetchInstances?.() },
      onRequestSetup: onRequestOAuthSetup,
    })
  }

  return (
    <div>
      <div
        className="flex items-center gap-3 px-4 py-3 hover:bg-white/[0.02] transition-colors rounded-lg group cursor-pointer"
        onClick={onToggleExpand}
      >
        {/* Batch select checkbox */}
        {onSelect && (
          <input
            type="checkbox"
            checked={selected || false}
            onChange={(e) => { e.stopPropagation(); onSelect(connector.id, e.target.checked) }}
            onClick={(e) => e.stopPropagation()}
            className="w-3.5 h-3.5 rounded border-white/20 bg-transparent accent-primary-500 cursor-pointer shrink-0"
          />
        )}
        <div className="w-10 h-10 rounded-lg bg-midnight-400/60 flex items-center justify-center shrink-0">
          <Icon size={22} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-medium text-starlight-100">{connector.name}</span>
            {/* Skill count badge -- echoes the Codex plugin header
                format so the user knows how many skills this plugin
                brings before expanding. */}
            <span className="text-[10px] px-1.5 py-0.5 rounded-md bg-white/5 text-starlight-400 font-medium">
              {connector.tools.length} {connector.tools.length === 1 ? 'skill' : 'skills'}
            </span>
            <span className="text-[10px] px-1.5 py-0.5 rounded-md bg-white/[0.03] text-starlight-500 uppercase tracking-wider">
              {connector.category}
            </span>
            {/* "Live" pill -- green dot + label when the plugin's
                MCP adapter is currently in the stdio bootstrap
                registry. Means plugin.call_tool can dispatch to
                this plugin right now without a server restart. */}
            {isLive && (
              <span
                className="flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded-md bg-accent-green/10 text-accent-green font-medium"
                title="Plugin MCP is loaded and spawnable now"
              >
                <span className="w-1.5 h-1.5 rounded-full bg-accent-green animate-pulse" />
                Live
              </span>
            )}
          </div>
          {/* Connected-account identity strip. Answers the "which
              Google account is Daena linked to?" question at a glance.
              Shows email + avatar-glyph when we have it, falls back to
              the connector subtitle otherwise. TICKET-S16 promoted
              this from a muted subtitle line to a dedicated pill so
              the identity is the FIRST thing the operator sees after
              connecting -- matches Slack / Notion / Zapier norm. */}
          {connected && accountIdentity ? (
            <div className="flex items-center gap-1.5 mt-1">
              <UserCircle size={12} className="text-accent-green shrink-0" />
              <span className="text-[11px] text-starlight-300 truncate">
                <span className="text-starlight-500">Signed in as </span>
                <span className="text-accent-green font-medium">{accountIdentity}</span>
              </span>
            </div>
          ) : (
            <p className="text-xs text-starlight-500 truncate mt-0.5">
              {connector.subtitle}
            </p>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0" onClick={(e) => e.stopPropagation()}>
          {connected ? (
            <span className="flex items-center gap-1 text-xs text-accent-green font-medium">
              <CheckCircle2 size={12} /> Connected
            </span>
          ) : (
            <button
              onClick={onToggleExpand}
              className="px-3 py-1 rounded-lg text-xs bg-primary-500/10 text-primary-400 hover:bg-primary-500/20 cursor-pointer"
            >
              Configure
            </button>
          )}
          {expanded ? <ChevronUp size={14} className="text-starlight-400" /> : <ChevronDown size={14} className="text-starlight-400" />}
          <div className="relative">
            <button onClick={() => setMenuOpen(!menuOpen)} className="p-1 rounded hover:bg-white/5 text-starlight-500 cursor-pointer">
              <MoreVertical size={14} />
            </button>
            <AnimatePresence>
              {menuOpen && (
                <ContextMenu
                  onClose={() => setMenuOpen(false)}
                  items={[
                    { label: 'View docs', icon: <ExternalLink size={12} />, onClick: () => toast.info(`Documentation for ${connector.name}`) },
                    // Session 11: "Switch account" disconnects the
                    // current instance then restarts OAuth. Google's
                    // consent screen shows the account picker again
                    // because we don't pass login_hint, so the user
                    // lands on "Choose an account" naturally.
                    ...(connected && instanceId ? [{
                      label: 'Switch account',
                      icon: <RefreshCw size={12} />,
                      onClick: async () => {
                        onDisconnect(instanceId)
                        // Small delay so the disconnect toast lands
                        // before the popup opens.
                        setTimeout(() => {
                          void startOAuthConnect({
                            connectorId: connector.id,
                            connectorName: connector.name,
                            onSuccess: () => { void fetchInstances?.() },
                            onRequestSetup: onRequestOAuthSetup,
                          })
                        }, 400)
                      },
                    }] : []),
                    ...(connected && instanceId ? [{
                      label: 'Disconnect',
                      icon: <XCircle size={12} />,
                      onClick: () => onDisconnect(instanceId),
                      danger: true,
                    }] : []),
                  ]}
                />
              )}
            </AnimatePresence>
          </div>
        </div>
      </div>

      {/* Expandable config panel */}
      <ConfigPanel expanded={expanded}>
        {/* Auth section */}
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <Shield size={12} className="text-starlight-400" />
            <span className="text-[10px] text-starlight-400 uppercase tracking-wider font-semibold">Authentication</span>
          </div>
          <div className="flex items-center gap-3 text-xs">
            <span className="text-starlight-500">Method:</span>
            <span className="text-starlight-200 font-medium">{authLabels[connector.auth]}</span>
            <span className={`text-[10px] px-1.5 py-0.5 rounded ${connected ? 'bg-accent-green/10 text-accent-green' : 'bg-white/5 text-starlight-400'}`}>
              {connected ? 'Connected' : 'Not connected'}
            </span>
          </div>

          {/* OAuth connect button */}
          {connector.auth === 'oauth' && !connected && (
            <button
              onClick={handleOAuthConnect}
              className="flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-medium bg-primary-500/15 text-primary-400 hover:bg-primary-500/25 cursor-pointer border border-primary-500/20"
            >
              <Globe size={14} /> Connect with {connector.name.split(' ')[0]}
            </button>
          )}

          {/* API key / Token input */}
          {(connector.auth === 'api_key' || connector.auth === 'token') && !connected && (
            <div className="flex items-center gap-2">
              <div className="relative flex-1">
                <Key size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-starlight-500" />
                <input
                  type="password"
                  value={apiKeyValue}
                  onChange={(e) => setApiKeyValue(e.target.value)}
                  placeholder={connector.auth === 'api_key' ? 'Enter API key...' : 'Enter access token...'}
                  className="w-full glass-input pl-8 pr-3 py-2 rounded-lg text-xs text-starlight-200 placeholder:text-starlight-500"
                  onKeyDown={(e) => { if (e.key === 'Enter') void handleSaveApiKey() }}
                />
              </div>
              <button
                onClick={() => void handleSaveApiKey()}
                disabled={!apiKeyValue.trim() || saving}
                className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs bg-accent-green/10 text-accent-green hover:bg-accent-green/20 cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {saving ? <Loader2 size={12} className="animate-spin" /> : <Save size={12} />} Save
              </button>
            </div>
          )}

          {/* Disconnect button */}
          {connected && instanceId && (
            <button
              onClick={() => onDisconnect(instanceId)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs text-accent-red/80 hover:bg-accent-red/10 cursor-pointer"
            >
              <XCircle size={12} /> Disconnect
            </button>
          )}
        </div>

        {/* Capabilities -- informational list of tools the connector
            brings. NOT per-tool CTAs. The 2026-04-18 UX rework
            (TICKET-S16) demoted these from "Skill with Ask dropdown"
            to read-only capability entries: the connector-level
            Connect / Disconnect / Switch-account action above is the
            primary contract. Once connected, the whole capability
            surface is available to Daena and the agents in scope --
            per-tool gating on a connected app is redundant with
            account-level auth and adds clutter.
            For users who still want fine-grained per-tool control,
            the "Advanced" disclosure below reveals the legacy
            Allow/Ask/Block controls on demand. */}
        <div className="space-y-2">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <Puzzle size={12} className="text-starlight-400" />
              <span className="text-[10px] text-starlight-400 uppercase tracking-wider font-semibold">
                Capabilities ({connector.tools.length})
              </span>
              {connected && (
                <span className="text-[10px] text-starlight-500">
                  available to Daena + agents in scope
                </span>
              )}
            </div>
            <button
              onClick={() => setShowAdvanced((v) => !v)}
              className="text-[10px] text-starlight-500 hover:text-starlight-300 flex items-center gap-1 cursor-pointer"
              title="Per-tool Allow / Ask / Block controls (rarely needed)"
            >
              <Wrench size={10} /> {showAdvanced ? 'Hide advanced' : 'Advanced'}
            </button>
          </div>
          <div className="rounded-lg border border-white/5 divide-y divide-white/5 bg-midnight-400/20">
            {connector.tools.map((tool) => {
              const skillName = tool
                .split('_')
                .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
                .join(' ')
              const description =
                SKILL_DESCRIPTIONS[tool] ||
                `Capability exposed by ${connector.name}.`
              return (
                <div
                  key={tool}
                  className="flex items-start justify-between gap-3 px-3 py-2.5"
                >
                  <div className="flex items-start gap-2.5 min-w-0 flex-1">
                    <div className="shrink-0 mt-0.5 p-1 rounded bg-white/5">
                      <Terminal size={11} className="text-starlight-400" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-1.5 flex-wrap">
                        <span className="text-xs text-starlight-200 font-medium">
                          {skillName}
                        </span>
                        <span className="text-[9px] uppercase tracking-wider px-1.5 py-0.5 rounded bg-white/5 text-starlight-400 font-semibold">
                          Tool
                        </span>
                      </div>
                      <p className="text-[11px] text-starlight-500 mt-0.5 leading-relaxed">
                        {description}
                      </p>
                      <code className="text-[10px] text-starlight-600 font-mono mt-0.5 inline-block">
                        {tool}
                      </code>
                    </div>
                  </div>
                  {/* Advanced: per-tool permission controls, hidden by
                      default. Defense-in-depth pattern -- connector
                      auth is the primary gate; these are the
                      secondary override for power users. */}
                  {showAdvanced && (
                    <div className="shrink-0">
                      <PermissionSelect
                        value={toolPermissions[tool] || 'ASK_EACH_TIME'}
                        onChange={(v) =>
                          setToolPermissions((prev) => ({ ...prev, [tool]: v }))
                        }
                      />
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      </ConfigPanel>
    </div>
  )
}

// ── Extension Row with Perplexity-style toggle + expandable config ──

function ExtensionRow({ ext, expanded, onToggleExpand, onToggle, selected, onSelect, governanceOverride }: {
  ext: ExtensionData
  expanded: boolean
  onToggleExpand: () => void
  onToggle: (id: string, enabled: boolean) => void
  selected?: boolean
  onSelect?: (id: string, checked: boolean) => void
  // Session 11: when true (UNLEASHED mode), per-tool pills are shown
  // but visually dimmed with a tooltip explaining they are overridden
  // at the governance-mode layer.
  governanceOverride?: boolean
}) {
  const [menuOpen, setMenuOpen] = useState(false)
  const [permission, setPermissionState] = useState<Permission>(ext.permission as Permission || 'ASK_EACH_TIME')
  // Session 10: per-tool permissions matching Claude Desktop.
  // Session 11: seeded from the backend's saved state (ext.tool_permissions)
  // so user choices persist across logout. Missing tools inherit the
  // extension default.
  const [toolPerms, setToolPermsState] = useState<Record<string, Permission>>(() => {
    const init: Record<string, Permission> = {}
    for (const t of ext.tools ?? []) {
      const saved = ext.tool_permissions?.[t]
      init[t] = (saved as Permission) ?? (ext.permission as Permission) ?? 'ASK_EACH_TIME'
    }
    return init
  })
  const Icon = EXTENSION_ICONS[ext.id] || Puzzle
  const hasTools = (ext.tools?.length ?? 0) > 0

  // Session 11: persist permission changes to User.settings JSONB via
  // POST /connections/extensions/{id}/permissions. Fire-and-forget with
  // a toast on failure -- local state updates immediately so the UI is
  // snappy, backend catches up asynchronously. On failure we warn but
  // don't revert; next refresh will hydrate the truth.
  const persistPermission = useCallback(async (next: Permission) => {
    try {
      await api.post(`/connections/extensions/${encodeURIComponent(ext.id)}/permissions`, {
        default: next,
      })
    } catch {
      toast.error(`Could not save ${ext.name} permission. It will revert on refresh.`)
    }
  }, [ext.id, ext.name])

  const persistToolPermission = useCallback(async (toolName: string, next: Permission) => {
    try {
      await api.post(`/connections/extensions/${encodeURIComponent(ext.id)}/permissions`, {
        tools: { [toolName]: next },
      })
    } catch {
      toast.error(`Could not save ${toolName} permission.`)
    }
  }, [ext.id])

  const setPermission = useCallback((next: Permission) => {
    setPermissionState(next)
    void persistPermission(next)
  }, [persistPermission])

  const setToolPerms = useCallback((updater: React.SetStateAction<Record<string, Permission>>) => {
    setToolPermsState((prev) => {
      const next = typeof updater === 'function' ? updater(prev) : updater
      // Figure out which tool(s) changed and persist only those.
      for (const [k, v] of Object.entries(next)) {
        if (prev[k] !== v) void persistToolPermission(k, v)
      }
      return next
    })
  }, [persistToolPermission])

  return (
    <div>
      <div
        className="flex items-center gap-3 px-4 py-3 hover:bg-white/[0.02] transition-colors rounded-lg group cursor-pointer"
        onClick={onToggleExpand}
      >
        {/* Batch select checkbox */}
        {onSelect && (
          <input
            type="checkbox"
            checked={selected || false}
            onChange={(e) => { e.stopPropagation(); onSelect(ext.id, e.target.checked) }}
            onClick={(e) => e.stopPropagation()}
            className="w-3.5 h-3.5 rounded border-white/20 bg-transparent accent-primary-500 cursor-pointer shrink-0"
          />
        )}
        <div className="w-10 h-10 rounded-lg bg-midnight-400/60 flex items-center justify-center shrink-0">
          <Icon size={22} />
        </div>
        <div className="flex-1 min-w-0">
          <span className="text-sm font-medium text-starlight-100">{ext.name}</span>
          <p className="text-xs text-starlight-500 truncate">{ext.description}</p>
        </div>
        <div className="flex items-center gap-3 shrink-0" onClick={(e) => e.stopPropagation()}>
          {/* Inline toggle switch (Perplexity style) -- green=enabled, red=disabled */}
          <button
            role="switch"
            aria-checked={ext.enabled}
            onClick={() => onToggle(ext.id, !ext.enabled)}
            className={`relative inline-flex h-5 w-9 items-center rounded-full transition-all duration-200 cursor-pointer ${
              ext.enabled ? 'bg-accent-green border border-accent-green' : 'bg-accent-red/60 border border-accent-red/40'
            }`}
          >
            <span className={`inline-block h-3.5 w-3.5 rounded-full bg-white shadow-md transform transition-transform duration-200 ${ext.enabled ? 'translate-x-4' : 'translate-x-0.5'}`} />
          </button>
          {expanded ? <ChevronUp size={14} className="text-starlight-400" /> : <ChevronDown size={14} className="text-starlight-400" />}
          <div className="relative">
            <button onClick={() => setMenuOpen(!menuOpen)} className="p-1 rounded hover:bg-white/5 text-starlight-500 cursor-pointer">
              <MoreVertical size={14} />
            </button>
            <AnimatePresence>
              {menuOpen && (
                <ContextMenu
                  onClose={() => setMenuOpen(false)}
                  items={[
                    { label: ext.enabled ? 'Disable' : 'Enable', icon: <Settings size={12} />, onClick: () => onToggle(ext.id, !ext.enabled) },
                  ]}
                />
              )}
            </AnimatePresence>
          </div>
        </div>
      </div>

      {/* Expandable config panel -- Claude Desktop parity:
          1. Compact source/version header (tiny, one line)
          2. Default permission pill (controls all tools at once)
          3. Per-tool permission list (this is what the empty space was)
          4. Empty-state callout when tools haven't been discovered yet */}
      <ConfigPanel expanded={expanded}>
        {/* Source + version strip -- one line instead of a 2x2 grid */}
        <div className="flex items-center gap-3 text-[11px] text-starlight-500">
          <span className="flex items-center gap-1">
            <span className={`w-1.5 h-1.5 rounded-full ${ext.enabled ? 'bg-accent-green' : 'bg-starlight-500'}`} />
            {ext.enabled ? 'Running' : 'Stopped'}
          </span>
          <span>&middot;</span>
          <span>{ext.source || 'MCP Server'}</span>
          {ext.version && (
            <>
              <span>&middot;</span>
              <span className="font-mono">{ext.version}</span>
            </>
          )}
        </div>

        {/* Default permission -- controls every tool at once.
            Session 11: when governanceOverride is true (UNLEASHED),
            wrap in an opacity-reduced container with a tooltip so the
            operator sees the pills are informational only. */}
        <div className={`space-y-2 ${governanceOverride ? 'opacity-50' : ''}`}
             title={governanceOverride ? 'UNLEASHED mode overrides per-tool settings. BLOCK is still honored.' : undefined}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Shield size={12} className="text-starlight-400" />
              <span className="text-[10px] text-starlight-400 uppercase tracking-wider font-semibold">Default Permission</span>
              {governanceOverride && (
                <span className="text-[9px] uppercase tracking-wider text-accent-green font-semibold">
                  overridden
                </span>
              )}
            </div>
            {hasTools && (
              <button
                onClick={async () => {
                  // Batch update: set local state for all tools AND
                  // fire a single persist call so we don't hammer the
                  // backend with N requests when there are many tools.
                  const next: Record<string, Permission> = {}
                  for (const t of ext.tools ?? []) next[t] = permission
                  setToolPermsState(next)
                  try {
                    await api.post(`/connections/extensions/${encodeURIComponent(ext.id)}/permissions`, {
                      tools: next,
                    })
                    toast.success(`All tools set to ${permission.replace('_', ' ').toLowerCase()}`)
                  } catch {
                    toast.error(`Applied locally but failed to save to server.`)
                  }
                }}
                className="text-[10px] text-primary-400 hover:text-primary-300 cursor-pointer"
              >
                Apply to all tools
              </button>
            )}
          </div>
          <div className="flex items-center gap-3">
            <PermissionSelect value={permission} onChange={setPermission} />
            <span className="text-[11px] text-starlight-400">
              {permission === 'ALLOW' ? 'Tools run without asking' : permission === 'ASK_EACH_TIME' ? 'Daena asks before each tool use' : 'All tools blocked'}
            </span>
          </div>
        </div>

        {/* Per-tool permissions -- matches Claude Desktop's MCP section.
            Shows each tool the MCP server exposes with an individual
            Allow/Ask/Block control. Empty state explains why tools
            might not be visible yet. Session 11: dims when UNLEASHED
            overrides per-tool settings. */}
        <div className={`space-y-2 ${governanceOverride ? 'opacity-50' : ''}`}>
          <div className="flex items-center justify-between">
            <span className="text-[10px] text-starlight-400 uppercase tracking-wider font-semibold">
              Tools {hasTools ? `(${ext.tools?.length})` : ''}
              {governanceOverride && (
                <span className="ml-2 text-[9px] uppercase tracking-wider text-accent-green font-semibold">
                  overridden
                </span>
              )}
            </span>
          </div>
          {hasTools ? (
            <div className="rounded-lg border border-white/5 divide-y divide-white/5">
              {(ext.tools ?? []).map((toolName) => (
                <div
                  key={toolName}
                  className="flex items-center gap-3 px-3 py-2 hover:bg-white/[0.02]"
                >
                  <Puzzle size={12} className="text-starlight-500 shrink-0" />
                  <span className="flex-1 text-xs font-mono text-starlight-200 truncate">
                    {toolName}
                  </span>
                  <PermissionSelect
                    value={toolPerms[toolName] ?? permission}
                    onChange={(v) => setToolPerms((s) => ({ ...s, [toolName]: v }))}
                  />
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-lg border border-dashed border-white/10 bg-white/[0.01] px-4 py-3 flex items-start gap-2">
              <Puzzle size={12} className="text-starlight-500 mt-0.5 shrink-0" />
              <div className="flex-1 text-[11px] text-starlight-500">
                Tools appear here once this MCP server runs for the first time.
                Daena probes the server's <span className="font-mono">tools/list</span>{' '}
                endpoint after it connects. Until then, the default permission
                above applies to every tool the server exposes.
              </div>
            </div>
          )}
        </div>
      </ConfigPanel>
    </div>
  )
}

// ── CLI Bridge Card (connects user's local CLI tools to Daena cloud) ──

function CLIBridgeCard() {
  const [expanded, setExpanded] = useState(false)
  const [bridgeToken, setBridgeToken] = useState<string | null>(null)
  const [generating, setGenerating] = useState(false)
  const [bridgeStatus, setBridgeStatus] = useState<{active_bridges: number} | null>(null)

  useEffect(() => {
    api.get('/bridge/status').then(res => {
      setBridgeStatus(res.data?.data || null)
    }).catch(() => {/* graceful */})
  }, [])

  const isConnected = (bridgeStatus?.active_bridges ?? 0) > 0

  const generateToken = async () => {
    setGenerating(true)
    try {
      const res = await api.post('/bridge/token', { label: 'CLI Bridge' })
      const token = res.data?.data?.token
      if (token) {
        setBridgeToken(token)
        toast.success('Bridge token generated! Follow the setup instructions below.')
      }
    } catch {
      toast.error('Failed to generate bridge token')
    } finally {
      setGenerating(false)
    }
  }

  const copyCommand = (cmd: string) => {
    navigator.clipboard.writeText(cmd).then(() => {
      toast.success('Copied to clipboard!')
    }).catch(() => {
      toast.info(`Command: ${cmd}`)
    })
  }

  return (
    <div className="rounded-xl border-2 border-primary-500/30 bg-gradient-to-r from-primary-500/5 to-accent-teal/5 p-4 space-y-3">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-lg bg-primary-500/20 flex items-center justify-center">
          <Zap size={20} className="text-primary-400" />
        </div>
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <span className="text-sm font-bold text-starlight-100">Daena CLI Bridge</span>
            {isConnected ? (
              <span className="text-[9px] px-1.5 py-0.5 rounded bg-accent-green/20 text-accent-green font-semibold">CONNECTED</span>
            ) : (
              <span className="text-[9px] px-1.5 py-0.5 rounded bg-primary-500/20 text-primary-400 font-semibold">RECOMMENDED</span>
            )}
          </div>
          <p className="text-xs text-starlight-400 mt-0.5">
            Connect your local CLI tools (Claude Code, Gemini CLI, Codex) to Daena.
            Your subscriptions stay on your machine -- Daena adds governance, departments, and audit.
          </p>
        </div>
        <button
          onClick={() => setExpanded(!expanded)}
          className="px-4 py-2 rounded-lg text-xs font-semibold bg-primary-500 text-white hover:bg-primary-600 cursor-pointer whitespace-nowrap"
        >
          {expanded ? 'Close' : 'Set Up'}
        </button>
      </div>

      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden space-y-4"
          >
            {/* Security info */}
            <div className="flex items-start gap-2 bg-accent-green/5 border border-accent-green/20 rounded-lg px-3 py-2">
              <Shield size={14} className="text-accent-green mt-0.5 shrink-0" />
              <p className="text-[11px] text-starlight-300">
                <strong className="text-accent-green">Your keys never leave your machine.</strong>{' '}
                Daena sends task descriptions. Your CLI executes them with your own credentials.
                Results are returned to Daena for audit logging only.
              </p>
            </div>

            {/* Step 1: Generate token */}
            <div className="space-y-2">
              <p className="text-[10px] text-starlight-500 uppercase tracking-wider font-semibold">Step 1: Generate Bridge Token</p>
              {bridgeToken ? (
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <input
                      type="password"
                      value={bridgeToken}
                      readOnly
                      className="flex-1 glass-input px-3 py-2 rounded-lg text-xs text-starlight-200 font-mono"
                    />
                    <button
                      onClick={() => copyCommand(bridgeToken)}
                      className="px-3 py-2 rounded-lg text-xs bg-white/5 text-starlight-300 hover:bg-white/10 cursor-pointer"
                    >
                      Copy
                    </button>
                  </div>
                  <p className="text-[10px] text-starlight-500">Token expires in 30 days. You can generate a new one anytime.</p>
                </div>
              ) : (
                <button
                  onClick={() => void generateToken()}
                  disabled={generating}
                  className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-medium bg-primary-500/15 text-primary-400 hover:bg-primary-500/25 cursor-pointer border border-primary-500/20 disabled:opacity-50"
                >
                  {generating ? <Loader2 size={12} className="animate-spin" /> : <Key size={12} />}
                  Generate Token
                </button>
              )}
            </div>

            {/* Step 2: Install & connect */}
            <div className="space-y-2">
              <p className="text-[10px] text-starlight-500 uppercase tracking-wider font-semibold">Step 2: Install & Connect</p>

              {/* Claude Code method */}
              <div className="rounded-lg border border-white/10 p-3 space-y-2">
                <div className="flex items-center gap-2">
                  <Terminal size={12} className="text-primary-400" />
                  <span className="text-xs font-medium text-starlight-200">Claude Code (recommended)</span>
                </div>
                <div className="flex items-center gap-2">
                  <code className="flex-1 text-[10px] text-starlight-400 bg-midnight-800/60 rounded px-2 py-1.5 font-mono overflow-x-auto">
                    claude mcp add daena -- npx @mas-ai/daena-mcp{bridgeToken ? ` --token ${bridgeToken.slice(0, 20)}...` : ' --token YOUR_TOKEN'}
                  </code>
                  <button
                    onClick={() => copyCommand(`claude mcp add daena -- npx @mas-ai/daena-mcp${bridgeToken ? ` --token ${bridgeToken}` : ' --token YOUR_TOKEN'}`)}
                    className="px-2 py-1 rounded text-[10px] bg-white/5 text-starlight-400 hover:bg-white/10 cursor-pointer shrink-0"
                  >
                    Copy
                  </button>
                </div>
              </div>

              {/* npm method */}
              <div className="rounded-lg border border-white/10 p-3 space-y-2">
                <div className="flex items-center gap-2">
                  <Globe size={12} className="text-accent-teal" />
                  <span className="text-xs font-medium text-starlight-200">npm (standalone)</span>
                </div>
                <div className="flex items-center gap-2">
                  <code className="flex-1 text-[10px] text-starlight-400 bg-midnight-800/60 rounded px-2 py-1.5 font-mono">
                    npm install -g @mas-ai/daena-mcp
                  </code>
                  <button
                    onClick={() => copyCommand('npm install -g @mas-ai/daena-mcp')}
                    className="px-2 py-1 rounded text-[10px] bg-white/5 text-starlight-400 hover:bg-white/10 cursor-pointer shrink-0"
                  >
                    Copy
                  </button>
                </div>
              </div>

              {/* pip method */}
              <div className="rounded-lg border border-white/10 p-3 space-y-2">
                <div className="flex items-center gap-2">
                  <Globe size={12} className="text-accent-amber" />
                  <span className="text-xs font-medium text-starlight-200">pip (Python)</span>
                </div>
                <div className="flex items-center gap-2">
                  <code className="flex-1 text-[10px] text-starlight-400 bg-midnight-800/60 rounded px-2 py-1.5 font-mono">
                    pip install daena-mcp
                  </code>
                  <button
                    onClick={() => copyCommand('pip install daena-mcp')}
                    className="px-2 py-1 rounded text-[10px] bg-white/5 text-starlight-400 hover:bg-white/10 cursor-pointer shrink-0"
                  >
                    Copy
                  </button>
                </div>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

// ── Main Page ──

type TabKey = 'runtimes' | 'extensions' | 'connectors' | 'mcp'

export function ConnectionsPage() {
  usePageTitle('Connections')
  const [searchParams, setSearchParams] = useSearchParams()
  const initialTab = (searchParams.get('tab') as TabKey) || 'runtimes'
  const [activeTab, setActiveTab] = useState<TabKey>(initialTab)
  // Live MCP registry -- the set of plugins whose stdio adapter is
  // actually in process memory right now. Used to show a "Live"
  // badge in the Plugins tab so the user can tell "installed" vs
  // "installed AND spawnable without restart".
  const mcpRegistry = useMcpRegistry()
  const [runtimes, setRuntimes] = useState<RuntimeData[]>([])
  const [primaryRuntime, setPrimaryRuntime] = useState<string>('claude_code')
  const [loading, setLoading] = useState(true)
  const [connectorSearch, setConnectorSearch] = useState('')
  const [connectorInstances, setConnectorInstances] = useState<Record<string, string>>({})
  // Session 11: parallel map slug -> account_identity so ConnectorRow
  // can show "Connected as masoud.masoori@mas-ai.co" instead of a bare
  // "Connected" pill. Empty string = OAuth succeeded but userinfo fetch
  // failed or not applicable (e.g. token-auth connectors).
  const [connectorIdentities, setConnectorIdentities] = useState<Record<string, string>>({})
  // Session 11: unified governance state. Tells the UI whether to dim
  // per-tool pills (UNLEASHED collapses ASK into ALLOW) and provides
  // banner copy explaining why.
  const permissionState = usePermissionState()
  const governanceOverride = permissionState?.per_tool_override_active === 'true'
  const [extensions, setExtensions] = useState<ExtensionData[]>([])
  const [extLoading, setExtLoading] = useState(true)
  const [cloudMode, setCloudMode] = useState(false)
  const [apiProviders, setApiProviders] = useState<{provider: string, status: string, display_name: string}[]>([])
  // Track which item is expanded (only one at a time per tab)
  const [expandedItem, setExpandedItem] = useState<string | null>(null)
  // Browse modal (Claude Desktop-style connector/extension marketplace)
  const [browseModal, setBrowseModal] = useState<'connectors' | 'extensions' | null>(null)
  // Batch selection (Perplexity-style multi-select)
  const [selectedExtensions, setSelectedExtensions] = useState<Set<string>>(new Set())
  const [selectedConnectors, setSelectedConnectors] = useState<Set<string>>(new Set())
  // AGI auto-select awareness
  const autopilotActive = useUiStore((s) => s.autopilotActive)
  // CLI-side MCP detection (Session 9) -- surfaces MCPs already installed
  // in Claude Code / Codex / Gemini CLIs and offers one-click import.
  const mcpSync = useMCPDetections()
  // Session 10: inline OAuth-broker setup modal (replaces the jarring
  // redirect to /settings when Google/Notion/etc. credentials aren't
  // configured yet). Holds the connector name + missing field so the
  // modal can explain exactly what is needed.
  const [oauthSetup, setOauthSetup] = useState<
    { connectorId: string; connectorName: string; missingField: string } | null
  >(null)

  const requestOAuthSetup = useCallback(
    (connectorId: string, connectorName: string, missingField: string) => {
      setOauthSetup({ connectorId, connectorName, missingField })
    },
    [],
  )

  const toggleExpand = (id: string) => setExpandedItem((prev) => prev === id ? null : id)

  // Batch selection helpers
  const handleSelectExtension = (id: string, checked: boolean) => {
    setSelectedExtensions((prev) => {
      const next = new Set(prev)
      if (checked) next.add(id)
      else next.delete(id)
      return next
    })
  }
  const handleSelectAllExtensions = (list: ExtensionData[]) => {
    if (selectedExtensions.size === list.length) {
      setSelectedExtensions(new Set())
    } else {
      setSelectedExtensions(new Set(list.map((e) => e.id)))
    }
  }
  const handleBatchToggleExtensions = (enabled: boolean) => {
    setExtensions((prev) =>
      prev.map((e) => selectedExtensions.has(e.id) ? { ...e, enabled } : e)
    )
    toast.success(`${selectedExtensions.size} extensions ${enabled ? 'enabled' : 'disabled'}`)
    setSelectedExtensions(new Set())
  }
  const handleSelectConnector = (id: string, checked: boolean) => {
    setSelectedConnectors((prev) => {
      const next = new Set(prev)
      if (checked) next.add(id)
      else next.delete(id)
      return next
    })
  }

  const fetchRuntimes = useCallback(async () => {
    try {
      const res = await api.get('/runtimes')
      const data = res.data?.data?.runtimes || []
      setRuntimes(data)
      const persistedPrimary = res.data?.data?.primary_runtime
      if (persistedPrimary) setPrimaryRuntime(persistedPrimary)
      setCloudMode(res.data?.data?.cloud_mode === true)
      setApiProviders(res.data?.data?.api_providers || [])
    } catch { /* graceful */ }
    finally { setLoading(false) }
  }, [])

  const fetchConnectorInstances = useCallback(async () => {
    try {
      const [connRes, instRes] = await Promise.allSettled([
        api.get('/connections/connectors'),
        api.get('/connections/instances'),
      ])
      const dbConnectors = connRes.status === 'fulfilled' ? connRes.value.data?.data || [] : []
      const instances = instRes.status === 'fulfilled' ? instRes.value.data?.data || [] : []
      const map: Record<string, string> = {}
      const identities: Record<string, string> = {}
      for (const inst of instances) {
        if (inst.status !== 'CONNECTED') continue
        const dbConnector = dbConnectors.find((c: Record<string, string>) => c.id === inst.connector_id)
        if (dbConnector) {
          const slug = (dbConnector.name || '').toLowerCase().replace(/\s+/g, '-')
          map[slug] = inst.id
          if (typeof inst.account_identity === 'string' && inst.account_identity) {
            identities[slug] = inst.account_identity
          }
        }
      }
      setConnectorInstances(map)
      setConnectorIdentities(identities)
    } catch { /* graceful */ }
  }, [])

  const fetchExtensions = useCallback(async () => {
    setExtLoading(true)
    try {
      const res = await api.get('/connections/extensions')
      const data = res.data?.data || []
      setExtensions(data.map((e: Record<string, unknown>) => {
        const name = String(e.name || '')
        const slug = name.toLowerCase().replace(/[\s_]+/g, '-').replace(/[^a-z0-9-]/g, '')
        const rawTools = Array.isArray(e.tools) ? e.tools : []
        const tools = rawTools.filter((t): t is string => typeof t === 'string')
        // Session 11: hydrate the saved default + per-tool permissions
        // from backend so the UI no longer forgets on reload/logout.
        const savedPermission = typeof e.permission === 'string' ? e.permission : 'ASK_EACH_TIME'
        const rawToolPerms = (e.tool_permissions && typeof e.tool_permissions === 'object')
          ? e.tool_permissions as Record<string, unknown>
          : {}
        const toolPermissions: Record<string, string> = {}
        for (const [k, v] of Object.entries(rawToolPerms)) {
          if (typeof v === 'string') toolPermissions[k] = v
        }
        return {
          id: slug || String(e.id || ''),
          name,
          description: String(e.description || ''),
          enabled: e.enabled !== false,
          permission: savedPermission,
          tools,
          tool_permissions: toolPermissions,
          source: typeof e.source === 'string' ? e.source : undefined,
          version: typeof e.version === 'string' ? e.version : undefined,
        }
      }))
    } catch { /* graceful */ }
    finally { setExtLoading(false) }
  }, [])

  useEffect(() => {
    void fetchRuntimes()
    void fetchConnectorInstances()
    void fetchExtensions()
  }, [fetchRuntimes, fetchConnectorInstances, fetchExtensions])

  const handleTabChange = (tab: TabKey) => {
    setActiveTab(tab)
    setSearchParams({ tab })
    setExpandedItem(null) // collapse when switching tabs
  }

  const handleSetPrimary = async (runtimeId: string) => {
    try {
      await api.put('/runtimes/primary', { runtime_id: runtimeId })
      setPrimaryRuntime(runtimeId)
      toast.success(`Primary Mind set to ${runtimeId}`)
    } catch { toast.error('Failed to set primary runtime') }
  }

  const handleTestRuntime = async (runtimeId: string) => {
    try {
      const res = await api.post(`/runtimes/${runtimeId}/test`)
      const data = res.data?.data
      if (data?.test_passed) {
        toast.success(`${runtimeId}: OK (${data.latency_ms}ms)`)
      } else {
        toast.error(`${runtimeId}: Test failed`)
      }
    } catch { toast.error('Test failed') }
  }

  const handleDisconnectConnector = async (instanceId: string) => {
    try {
      await api.post(`/connections/instances/${instanceId}/disconnect`)
      toast.success('Disconnected')
      await fetchConnectorInstances()
    } catch {
      toast.error('Failed to disconnect')
    }
  }

  const filteredConnectors = connectorSearch
    ? CONNECTORS.filter(c => c.name.toLowerCase().includes(connectorSearch.toLowerCase()) || c.category.toLowerCase().includes(connectorSearch.toLowerCase()))
    : CONNECTORS

  const tabs: { key: TabKey; label: string; icon: React.ReactNode; count?: number }[] = [
    { key: 'runtimes', label: 'Mind Control', icon: <Cpu size={16} />, count: runtimes.filter(r => r.status === 'online').length },
    { key: 'extensions', label: 'Extensions', icon: <Puzzle size={16} />, count: extensions.length },
    { key: 'connectors', label: 'Plugins', icon: <Plug size={16} />, count: CONNECTORS.length },
    // MCP Servers (2026-04-18 TICKET-S16): shows MCPs imported from
    // claude_desktop_config.json + any Daena-native MCP plus health
    // status. Separates the "MCP runtime registry" from the local
    // "Extensions" (filesystem/terminal/browser primitives) and cloud
    // "Plugins" which were all being conflated.
    { key: 'mcp', label: 'MCP Servers', icon: <Server size={16} />, count: mcpRegistry.entries.length },
  ]

  const totalTools = extensions.reduce((acc, e) => acc + 1, 0) + CONNECTORS.reduce((acc, c) => acc + c.tools.length, 0)
  const onlineRuntimes = runtimes.filter(r => r.status === 'online').length

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-4xl mx-auto p-6 space-y-6">
        {/* Hero section */}
        <div className="p-5 rounded-xl bg-gradient-to-r from-primary-500/10 via-accent-purple/10 to-accent-cyan/10 border border-primary-500/20">
          <h1 className="text-lg font-display font-semibold text-starlight-100 mb-1">Connect your tools</h1>
          <p className="text-xs text-starlight-400 mb-4">Runtimes, MCP servers, and external services -- all governed by Daena</p>
          <div className="flex items-center gap-x-6 gap-y-2 flex-wrap">
            {/*
              Honest label split (2026-04-23 wiring fix): the header
              previously read extensions.length under "MCP servers
              active", which contradicted the MCP Servers tab beside
              it (that one read mcpRegistry.entries.length). Now each
              chip uses one source of truth and self-explains its
              meaning via title= tooltip.
            */}
            <div className="flex items-center gap-2" title="CLI runtimes (Claude Code / Codex / Gemini CLI / Ollama / vLLM) currently reachable">
              <div className="w-2 h-2 rounded-full bg-status-success" />
              <span className="text-xs text-starlight-300"><span className="font-mono font-semibold text-starlight-100">{onlineRuntimes}</span> runtimes connected</span>
            </div>
            <div className="flex items-center gap-2" title="Local primitives Daena can use directly: filesystem, terminal, browser, screen capture. Configured in the Extensions tab.">
              <div className="w-2 h-2 rounded-full bg-status-info" />
              <span className="text-xs text-starlight-300"><span className="font-mono font-semibold text-starlight-100">{extensions.length}</span> extensions active</span>
            </div>
            <div className="flex items-center gap-2" title="MCP servers imported into Daena's registry. Manage in the MCP Servers tab.">
              <div className="w-2 h-2 rounded-full bg-accent-purple" />
              <span className="text-xs text-starlight-300"><span className="font-mono font-semibold text-starlight-100">{mcpRegistry.entries.length}</span> MCP servers active</span>
            </div>
            {mcpSync.detections.length > 0 && (
              <div className="flex items-center gap-2" title={`${mcpSync.detections.length} MCP servers were detected in other CLI configs (Claude Desktop, etc.) but are not yet imported to Daena. Open the MCP Servers tab and click Import to enable them.`}>
                <div className="w-2 h-2 rounded-full bg-accent-amber" />
                <span className="text-xs text-starlight-300"><span className="font-mono font-semibold text-accent-amber">{mcpSync.detections.length}</span> detected, not imported</span>
              </div>
            )}
            <div className="flex items-center gap-2" title="Aggregate tool count exposed to Daena across all extensions and connected plugins.">
              <div className="w-2 h-2 rounded-full bg-accent-cyan" />
              <span className="text-xs text-starlight-300"><span className="font-mono font-semibold text-starlight-100">{totalTools}</span> tools available</span>
            </div>
            <div className="ml-auto flex items-center gap-2">
              <Shield size={12} className="text-accent-amber" />
              <span className="text-[10px] text-starlight-500">Governance active</span>
            </div>
          </div>
        </div>

        {/* Tab bar */}
        <div className="flex items-center gap-1 border-b border-white/5 pb-0">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => handleTabChange(tab.key)}
              className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition-all cursor-pointer ${
                activeTab === tab.key
                  ? 'border-primary-500 text-primary-400'
                  : 'border-transparent text-starlight-400 hover:text-starlight-200'
              }`}
            >
              {tab.icon}
              {tab.label}
              {tab.count != null && (
                <span className="ml-1 px-1.5 py-0.5 rounded-full text-[10px] bg-white/5">{tab.count}</span>
              )}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <AnimatePresence mode="wait">
          <motion.div
            key={activeTab}
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.15 }}
          >
            {/* ── Runtimes ── */}
            {activeTab === 'runtimes' && (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="text-lg font-display font-bold text-starlight-100">AI Runtimes</h2>
                    <p className="text-xs text-starlight-400">AI models and CLI tools that power Daena's intelligence</p>
                  </div>
                  <button onClick={() => { setLoading(true); void fetchRuntimes() }} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs bg-white/5 text-starlight-400 hover:bg-white/10 cursor-pointer">
                    <RefreshCw size={12} className={loading ? 'animate-spin' : ''} /> Refresh
                  </button>
                </div>

                {cloudMode && (
                  <div className="rounded-xl border border-accent-amber/20 bg-accent-amber/5 px-4 py-3">
                    <p className="text-xs text-accent-amber font-medium mb-1">Running in cloud mode</p>
                    <p className="text-[11px] text-starlight-400">Local runtimes (Ollama, CLI tools) are not available. Connect API providers in Settings &gt; Models.</p>
                  </div>
                )}

                {cloudMode && apiProviders.length > 0 && (
                  <div>
                    <p className="text-[10px] text-starlight-500 uppercase tracking-wider font-semibold px-4 mb-2">API Providers</p>
                    <div className="rounded-xl border border-white/5 divide-y divide-white/5">
                      {apiProviders.map((ap) => (
                        <div key={ap.provider} className="flex items-center gap-4 px-4 py-3">
                          <div className="w-10 h-10 rounded-lg bg-midnight-400/60 flex items-center justify-center shrink-0">
                            <Globe size={22} className="text-starlight-300" />
                          </div>
                          <div className="flex-1 min-w-0">
                            <span className="text-sm font-medium text-starlight-100">{ap.display_name}</span>
                            <p className="text-xs text-starlight-500">{ap.provider} API</p>
                          </div>
                          <span className="flex items-center gap-1 text-[10px] text-status-success">
                            <CheckCircle2 size={10} />
                            Connected
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* CLI Bridge -- connect user's local tools to Daena cloud */}
                <CLIBridgeCard />

                <div className="rounded-xl border border-white/5 divide-y divide-white/5">
                  {(cloudMode
                    ? runtimes.filter((rt) => rt.runtime_id !== 'ollama')
                    : runtimes
                  ).map((rt) => (
                    <RuntimeRow
                      key={rt.runtime_id}
                      runtime={rt}
                      isPrimary={primaryRuntime === rt.runtime_id}
                      expanded={expandedItem === rt.runtime_id}
                      onToggleExpand={() => toggleExpand(rt.runtime_id)}
                      onSetPrimary={() => void handleSetPrimary(rt.runtime_id)}
                      onTest={() => void handleTestRuntime(rt.runtime_id)}
                      onRefreshAuth={() => void fetchRuntimes()}
                    />
                  ))}
                  {runtimes.length === 0 && !loading && (
                    <div className="px-4 py-8 text-center text-xs text-starlight-500">No runtimes detected. Click Refresh to scan.</div>
                  )}
                </div>
              </div>
            )}

            {/* ── Detected in your CLIs (Session 9) ── */}
            {activeTab === 'extensions' && mcpSync.detections.length > 0 && (
              <div className="mb-6 space-y-3">
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="text-lg font-display font-bold text-starlight-100">Detected in your CLIs</h2>
                    <p className="text-xs text-starlight-400">
                      MCP servers you already installed in Claude Code, Codex, or Gemini. Import once — use everywhere.
                    </p>
                  </div>
                  <button
                    onClick={() => { void mcpSync.refresh() }}
                    disabled={mcpSync.loading}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs bg-white/5 text-starlight-300 hover:bg-white/10 cursor-pointer"
                  >
                    {mcpSync.loading ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />}
                    Rescan
                  </button>
                </div>
                <div className="rounded-xl border border-white/5 overflow-hidden">
                  {mcpSync.detections.map((mcp) => {
                    const status = mcpSync.importStatus[mcp.name] ?? 'idle'
                    const result = mcpSync.importResults[mcp.name]
                    const cliList = mcp.notes.match(/detected_in=([^|]+)/)?.[1] ?? mcp.source_cli
                    return (
                      <div
                        key={`${mcp.source_cli}:${mcp.name}`}
                        className="flex items-center gap-3 px-4 py-3 border-b border-white/5 last:border-b-0 hover:bg-white/[0.02]"
                      >
                        <div className="w-8 h-8 rounded-lg bg-primary-500/10 flex items-center justify-center text-primary-400 shrink-0">
                          <Puzzle size={14} />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <p className="text-sm font-medium text-starlight-100 truncate">{mcp.name}</p>
                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/5 text-starlight-400 uppercase tracking-wider">
                              {cliList}
                            </span>
                          </div>
                          <p className="text-[11px] text-starlight-500 truncate" title={`${mcp.command} ${mcp.args.join(' ')}`.trim()}>
                            {mcp.url || `${mcp.command} ${mcp.args.join(' ')}`.trim() || 'no command'}
                          </p>
                          {result && !result.safe && result.blockers.length > 0 && (
                            <p className="text-[11px] text-accent-red mt-1 flex items-center gap-1">
                              <AlertTriangle size={10} /> Blocked: {result.blockers.join('; ')}
                            </p>
                          )}
                        </div>
                        <button
                          onClick={() => { void mcpSync.importMCP(mcp) }}
                          disabled={status === 'importing' || status === 'imported'}
                          className={
                            status === 'imported'
                              ? 'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs bg-accent-green/10 text-accent-green cursor-default'
                              : status === 'blocked' || status === 'error'
                              ? 'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs bg-accent-red/10 text-accent-red cursor-not-allowed'
                              : 'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs bg-primary-500/10 text-primary-400 hover:bg-primary-500/20 cursor-pointer disabled:opacity-50'
                          }
                        >
                          {status === 'importing' && <Loader2 size={12} className="animate-spin" />}
                          {status === 'imported' && <CheckCircle2 size={12} />}
                          {(status === 'blocked' || status === 'error') && <AlertTriangle size={12} />}
                          {status === 'idle' && <Download size={12} />}
                          {status === 'imported'
                            ? 'Imported'
                            : status === 'blocked'
                            ? 'Blocked'
                            : status === 'error'
                            ? 'Error'
                            : status === 'importing'
                            ? 'Scanning...'
                            : 'Import'}
                        </button>
                      </div>
                    )
                  })}
                </div>
                {mcpSync.error && (
                  <p className="text-xs text-accent-red flex items-center gap-1">
                    <AlertTriangle size={12} /> {mcpSync.error}
                  </p>
                )}
              </div>
            )}

            {/* ── Extensions ── */}
            {activeTab === 'extensions' && (
              <div className="space-y-4">
                {/* Session 11: governance-mode banner. Explains how
                    per-tool Allow/Ask/Block interacts with the current
                    UNLEASHED/BALANCED/GOVERNED mode. Color-coded: green
                    for UNLEASHED (wide open), amber for BALANCED,
                    primary for GOVERNED (strict). */}
                {permissionState && (
                  <div
                    className={
                      governanceOverride
                        ? 'flex items-start gap-3 px-4 py-3 rounded-xl bg-accent-green/10 border border-accent-green/30'
                        : permissionState.governance_mode === 'BALANCED'
                        ? 'flex items-start gap-3 px-4 py-3 rounded-xl bg-accent-amber/10 border border-accent-amber/30'
                        : 'flex items-start gap-3 px-4 py-3 rounded-xl bg-primary-500/10 border border-primary-500/30'
                    }
                  >
                    <Shield
                      size={16}
                      className={
                        governanceOverride
                          ? 'text-accent-green shrink-0 mt-0.5'
                          : permissionState.governance_mode === 'BALANCED'
                          ? 'text-accent-amber shrink-0 mt-0.5'
                          : 'text-primary-400 shrink-0 mt-0.5'
                      }
                    />
                    <div className="flex-1">
                      <p className="text-xs font-semibold text-starlight-100">
                        {permissionState.banner_headline}
                      </p>
                      <p className="text-[11px] text-starlight-400 mt-1">
                        {permissionState.banner_body}
                      </p>
                    </div>
                  </div>
                )}

                <div className="flex items-center justify-between">
                  <p className="text-xs text-starlight-400">
                    {cloudMode
                      ? 'Pre-installed MCP servers available in cloud mode.'
                      : 'MCP servers let Daena read files, query APIs, and drive other tools on your computer.'}
                  </p>
                  <div className="flex items-center gap-2">
                    {!cloudMode && (
                      <button
                        onClick={() => setBrowseModal('extensions')}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs bg-primary-500/10 text-primary-400 hover:bg-primary-500/20 cursor-pointer"
                      >
                        <Plus size={12} /> Browse MCP servers
                      </button>
                    )}
                  </div>
                </div>

                {/* Batch action toolbar */}
                {selectedExtensions.size > 0 && (
                  <motion.div
                    initial={{ opacity: 0, y: -4 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="flex items-center gap-3 px-4 py-2.5 rounded-xl bg-primary-500/10 border border-primary-500/20"
                  >
                    <span className="text-xs text-primary-400 font-medium">{selectedExtensions.size} selected</span>
                    <div className="flex-1" />
                    <button
                      onClick={() => handleBatchToggleExtensions(true)}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs bg-accent-green/10 text-accent-green hover:bg-accent-green/20 cursor-pointer"
                    >
                      <ToggleRight size={12} /> Enable selected
                    </button>
                    <button
                      onClick={() => handleBatchToggleExtensions(false)}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs bg-accent-red/10 text-accent-red hover:bg-accent-red/20 cursor-pointer"
                    >
                      <ToggleLeft size={12} /> Disable selected
                    </button>
                    <button
                      onClick={() => setSelectedExtensions(new Set())}
                      className="p-1 rounded hover:bg-white/5 text-starlight-500 cursor-pointer"
                    >
                      <XCircle size={14} />
                    </button>
                  </motion.div>
                )}

                <div>
                  {/* Header with select-all */}
                  <div className="flex items-center justify-between px-4 mb-2">
                    <p className="text-[10px] text-starlight-500 uppercase tracking-wider font-semibold">
                      {cloudMode ? 'Pre-installed extensions' : 'Installed on your computer'}
                    </p>
                    <div className="flex items-center gap-3">
                      <button
                        onClick={() => handleSelectAllExtensions(cloudMode ? CLOUD_PREINSTALLED_EXTENSIONS : extensions)}
                        className="text-[10px] text-starlight-500 hover:text-primary-400 cursor-pointer"
                      >
                        {selectedExtensions.size === (cloudMode ? CLOUD_PREINSTALLED_EXTENSIONS : extensions).length ? 'Deselect all' : 'Select all'}
                      </button>
                      <button
                        onClick={() => {
                          const list = cloudMode ? CLOUD_PREINSTALLED_EXTENSIONS : extensions
                          const allEnabled = list.every((e) => e.enabled)
                          if (allEnabled) {
                            setExtensions((prev) => prev.map((e) => ({ ...e, enabled: false })))
                            toast.success('All extensions disabled')
                          } else {
                            setExtensions((prev) => prev.map((e) => ({ ...e, enabled: true })))
                            toast.success('All extensions enabled')
                          }
                        }}
                        className="text-[10px] text-starlight-500 hover:text-accent-green cursor-pointer"
                      >
                        {(cloudMode ? CLOUD_PREINSTALLED_EXTENSIONS : extensions).every((e) => e.enabled) ? 'Disable all' : 'Enable all'}
                      </button>
                    </div>
                  </div>
                  <div className="rounded-xl border border-white/5 divide-y divide-white/5">
                    {(cloudMode ? CLOUD_PREINSTALLED_EXTENSIONS : extensions).map((ext) => (
                      <ExtensionRow
                        key={ext.id}
                        ext={ext}
                        expanded={expandedItem === ext.id}
                        onToggleExpand={() => toggleExpand(ext.id)}
                        selected={selectedExtensions.has(ext.id)}
                        onSelect={handleSelectExtension}
                        governanceOverride={governanceOverride}
                        onToggle={(id, enabled) => {
                          if (cloudMode) {
                            toast.success(`${ext.name} ${enabled ? 'enabled' : 'disabled'}`)
                          } else {
                            setExtensions((prev) => prev.map((e) => e.id === id ? { ...e, enabled } : e))
                            toast.success(`${ext.name} ${enabled ? 'enabled' : 'disabled'}`)
                          }
                        }}
                      />
                    ))}
                    {!cloudMode && extensions.length === 0 && !extLoading && (
                      <div className="px-4 py-8 text-center text-xs text-starlight-500">No extensions installed. Install MCP servers to add extensions.</div>
                    )}
                  </div>
                </div>

                {!cloudMode && (
                  <div className="border-2 border-dashed border-white/10 rounded-xl p-6 text-center">
                    <p className="text-xs text-starlight-500">Drag .MCPB or .DXT files here to install</p>
                  </div>
                )}
              </div>
            )}

            {/* ── Connectors ── */}
            {activeTab === 'connectors' && (
              <div className="space-y-4">
                {/* Session 10: Claude Desktop parity -- removed the
                    "Connectors" H2 (tab label is already "Services")
                    and the AGI Mode banner for visual cleanup. Kept
                    the Browse button right-aligned. */}
                <div className="flex items-center justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <p className="text-xs text-starlight-400">
                      Plugins bundle related skills so Daena can read and write across
                      apps you already use -- Gmail, Drive, GitHub, and more. Expand
                      a plugin to see its individual skills.
                    </p>
                    {/* Live MCP counter -- mirrors the bootstrap
                        registry. Gives at-a-glance feedback that the
                        install loop actually worked (vs stuck on
                        0 as it used to before the refresh fix). */}
                    {mcpRegistry.entries.length > 0 && (
                      <p className="text-[11px] text-accent-green mt-1 flex items-center gap-1.5">
                        <span className="w-1.5 h-1.5 rounded-full bg-accent-green animate-pulse" />
                        {mcpRegistry.entries.length} {mcpRegistry.entries.length === 1 ? 'plugin' : 'plugins'} live and callable right now
                      </p>
                    )}
                  </div>
                  <button
                    onClick={() => setBrowseModal('connectors')}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs bg-primary-500/10 text-primary-400 hover:bg-primary-500/20 cursor-pointer shrink-0"
                  >
                    <Plus size={12} /> Browse plugins
                  </button>
                </div>

                <div className="relative">
                  <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-starlight-500" />
                  <input
                    type="text"
                    value={connectorSearch}
                    onChange={(e) => setConnectorSearch(e.target.value)}
                    placeholder="Search plugins..."
                    className="w-full glass-input pl-9 pr-4 py-2.5 rounded-lg text-sm text-starlight-200 placeholder:text-starlight-500"
                  />
                </div>

                {/* Batch action toolbar */}
                {selectedConnectors.size > 0 && (
                  <motion.div
                    initial={{ opacity: 0, y: -4 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="flex items-center gap-3 px-4 py-2.5 rounded-xl bg-primary-500/10 border border-primary-500/20"
                  >
                    <span className="text-xs text-primary-400 font-medium">{selectedConnectors.size} selected</span>
                    <div className="flex-1" />
                    <button
                      onClick={() => { setSelectedConnectors(new Set()); toast.info('Batch operations for connectors require individual setup') }}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs bg-white/5 text-starlight-300 hover:bg-white/10 cursor-pointer"
                    >
                      Clear selection
                    </button>
                  </motion.div>
                )}

                {/* Select all link */}
                <div className="flex justify-end px-4">
                  <button
                    onClick={() => {
                      if (selectedConnectors.size === filteredConnectors.length) {
                        setSelectedConnectors(new Set())
                      } else {
                        setSelectedConnectors(new Set(filteredConnectors.map((c) => c.id)))
                      }
                    }}
                    className="text-[10px] text-starlight-500 hover:text-primary-400 cursor-pointer"
                  >
                    {selectedConnectors.size === filteredConnectors.length ? 'Deselect all' : 'Select all'}
                  </button>
                </div>

                {/* Codex-style grouping: plugins clustered under their
                    category so the directory reads like a curated shelf
                    instead of a flat alphabetical dump. Preserves the
                    single-column Codex look with breathing room
                    between sections. */}
                {(() => {
                  // Group preserving original category order of first
                  // occurrence (so "Productivity" stays near the top if
                  // it was first in CONNECTORS).
                  const groups: Record<string, typeof filteredConnectors> = {}
                  const order: string[] = []
                  for (const c of filteredConnectors) {
                    if (!groups[c.category]) {
                      groups[c.category] = []
                      order.push(c.category)
                    }
                    groups[c.category].push(c)
                  }
                  return (
                    <div className="space-y-5">
                      {order.map((category) => (
                        <div key={category} className="space-y-2">
                          <div className="flex items-center gap-2 px-1">
                            <span className="text-[10px] uppercase tracking-wider font-semibold text-starlight-400">
                              {category}
                            </span>
                            <span className="text-[10px] text-starlight-600">
                              {groups[category].length}
                            </span>
                            <div className="flex-1 h-px bg-white/5" />
                          </div>
                          <div className="rounded-xl border border-white/5 divide-y divide-white/5">
                            {groups[category].map((c) => (
                              <ConnectorRow
                                key={c.id}
                                connector={c}
                                connected={!!connectorInstances[c.id]}
                                instanceId={connectorInstances[c.id] || null}
                                accountIdentity={connectorIdentities[c.id] || ''}
                                expanded={expandedItem === c.id}
                                onToggleExpand={() => toggleExpand(c.id)}
                                onDisconnect={handleDisconnectConnector}
                                fetchInstances={fetchConnectorInstances}
                                selected={selectedConnectors.has(c.id)}
                                onSelect={handleSelectConnector}
                                onRequestOAuthSetup={(missing) => requestOAuthSetup(c.id, c.name, missing)}
                                isLive={mcpRegistry.isLive(`mcp-${c.id}`)}
                              />
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  )
                })()}
              </div>
            )}

            {/* ── MCP Servers tab ── TICKET-S16 2026-04-18 ──
                Surfaces the ``mcp-registry`` endpoint (live stdio-bootstrap
                entries) directly so operators can see which MCPs
                Daena imported from ``claude_desktop_config.json`` and
                which are spawnable right now vs need a restart.
                This is the "Restore MCP servers previously in Claude
                Desktop" deliverable from the connections brief. */}
            {activeTab === 'mcp' && (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="text-base font-semibold text-starlight-100">MCP Servers</h2>
                    <p className="text-xs text-starlight-500 mt-1">
                      Model Context Protocol servers Daena has imported. Each
                      one extends Daena&apos;s tool surface -- chat, automations,
                      and agents can all call into these.
                      {mcpRegistry.entries.length > 0 && (
                        <> <span className="text-accent-green">{mcpRegistry.entries.length}</span> loaded and callable now.</>
                      )}
                    </p>
                  </div>
                  <button
                    onClick={() => { void mcpRegistry.refresh() }}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs bg-white/5 text-starlight-300 hover:bg-white/10 cursor-pointer"
                    title="Re-scan claude_desktop_config.json + rebuild the live registry"
                  >
                    <RefreshCw size={12} /> Refresh
                  </button>
                </div>

                {/* Legacy MCP import hint (scans Claude Code / Codex / Gemini
                    CLI configs) -- reuses the existing mcpSync infra. */}
                {mcpSync.detections.length > 0 && (
                  <div className="p-3 rounded-lg border border-accent-amber/30 bg-accent-amber/5">
                    <div className="flex items-center gap-2">
                      <AlertTriangle size={14} className="text-accent-amber" />
                      <span className="text-xs text-starlight-200 font-medium">
                        {mcpSync.detections.length} MCP{mcpSync.detections.length === 1 ? '' : 's'} found in other CLI configs
                      </span>
                    </div>
                    <p className="text-[11px] text-starlight-400 mt-1">
                      These MCP servers are configured in other tools on this machine.
                      Import them to make their tools available to Daena.
                    </p>
                  </div>
                )}

                {mcpRegistry.loading && (
                  <div className="flex items-center gap-2 px-4 py-6 text-xs text-starlight-500">
                    <Loader2 size={14} className="animate-spin" /> Loading registry...
                  </div>
                )}

                {!mcpRegistry.loading && mcpRegistry.entries.length === 0 && (
                  <div className="p-6 rounded-lg border border-dashed border-white/10 text-center">
                    <Server size={28} className="mx-auto text-starlight-500 mb-2" />
                    <p className="text-sm text-starlight-300">No MCP servers imported yet</p>
                    <p className="text-[11px] text-starlight-500 mt-1">
                      Install a plugin from the <span className="text-primary-400 cursor-pointer" onClick={() => handleTabChange('connectors')}>Plugins</span> tab
                      or add an MCP config to <code className="font-mono bg-white/5 px-1 py-0.5 rounded">~/AppData/Roaming/Claude/claude_desktop_config.json</code>
                      and hit Refresh.
                    </p>
                  </div>
                )}

                {mcpRegistry.entries.length > 0 && (
                  <div className="rounded-xl border border-white/5 divide-y divide-white/5 bg-midnight-400/20">
                    {mcpRegistry.entries.map((entry) => (
                      <div key={entry.server_key} className="px-4 py-3 flex items-start gap-3 hover:bg-white/[0.02] transition-colors">
                        <div className="w-9 h-9 rounded-lg bg-midnight-400/60 flex items-center justify-center shrink-0">
                          <Server size={18} className="text-accent-cyan" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="text-sm font-medium text-starlight-100">{entry.display_name || entry.server_key}</span>
                            <span className="flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded-md bg-accent-green/10 text-accent-green font-medium">
                              <Activity size={9} /> Live
                            </span>
                            {entry.package && (
                              <span className="text-[10px] px-1.5 py-0.5 rounded-md bg-white/5 text-starlight-400 font-mono">
                                {entry.package}
                              </span>
                            )}
                          </div>
                          {entry.description && (
                            <p className="text-[11px] text-starlight-500 mt-1 leading-relaxed">{entry.description}</p>
                          )}
                          <div className="flex items-center gap-2 mt-1.5 text-[10px] text-starlight-600 font-mono">
                            <code className="bg-white/[0.03] px-1.5 py-0.5 rounded">
                              {entry.command} {(entry.args || []).slice(0, 3).join(' ')}{(entry.args || []).length > 3 ? ' ...' : ''}
                            </code>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {/* Host config hint */}
                <div className="p-3 rounded-lg border border-white/5 bg-midnight-400/20">
                  <div className="flex items-start gap-2 text-[11px] text-starlight-400 leading-relaxed">
                    <Shield size={12} className="shrink-0 mt-0.5 text-starlight-500" />
                    <span>
                      Daena reads from <code className="font-mono bg-white/5 px-1 rounded">~/AppData/Roaming/Claude/claude_desktop_config.json</code>
                      on startup and after every Refresh. Per-tenant MCP config paths are planned for multi-tenant prod.
                    </span>
                  </div>
                </div>
              </div>
            )}
          </motion.div>
        </AnimatePresence>
      </div>

      {/* ── Browse Modal (Claude Desktop-style marketplace) ── */}
      <AnimatePresence>
        {browseModal && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50"
              onClick={() => setBrowseModal(null)}
            />
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 20 }}
              transition={{ duration: 0.2 }}
              className="fixed inset-x-4 top-[5%] bottom-[5%] md:inset-x-[15%] lg:inset-x-[20%] z-50 bg-midnight-300 rounded-2xl border border-white/10 shadow-2xl flex flex-col overflow-hidden"
            >
              {/* Header */}
              <div className="flex items-center justify-between px-6 py-4 border-b border-white/5">
                <div>
                  <h2 className="text-xl font-display font-bold text-starlight-100">
                    {browseModal === 'connectors' ? 'Connectors' : 'Extensions'}
                  </h2>
                  <p className="text-xs text-starlight-400 mt-0.5">
                    {browseModal === 'connectors'
                      ? 'Connect Daena to your apps, files, and services. One click to set up.'
                      : 'Add MCP servers and tools to extend Daena\'s capabilities.'}
                  </p>
                </div>
                <button
                  onClick={() => setBrowseModal(null)}
                  className="p-2 rounded-lg hover:bg-white/5 text-starlight-400 hover:text-starlight-200 cursor-pointer"
                >
                  <XCircle size={20} />
                </button>
              </div>

              {/* Search + Filters */}
              <div className="px-6 py-3 border-b border-white/5 flex items-center gap-3">
                <div className="relative flex-1">
                  <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-starlight-500" />
                  <input
                    type="text"
                    placeholder="Search..."
                    className="w-full pl-9 pr-3 py-2 rounded-lg bg-midnight-400 border border-white/5 text-sm text-starlight-200 placeholder:text-starlight-500 focus:outline-none focus:border-primary-500/40"
                  />
                </div>
                <div className="flex gap-2 text-xs text-starlight-400">
                  <span className="px-3 py-1.5 rounded-lg bg-white/5 cursor-pointer hover:bg-white/10">Sort</span>
                  <span className="px-3 py-1.5 rounded-lg bg-white/5 cursor-pointer hover:bg-white/10">Categories</span>
                </div>
              </div>

              {/* Grid */}
              <div className="flex-1 overflow-y-auto p-6">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {(browseModal === 'connectors' ? BROWSE_CONNECTORS_CATALOG : BROWSE_EXTENSIONS_CATALOG).map((item) => {
                    const isConnected = browseModal === 'connectors'
                      ? !!connectorInstances[item.id]
                      : extensions.some(e => e.name.toLowerCase().includes(item.name.toLowerCase()) && e.enabled)
                    const IconComp = browseModal === 'connectors'
                      ? (CONNECTOR_ICONS[item.id] || (() => <Globe size={24} className="text-starlight-400" />))
                      : (EXTENSION_ICONS[item.id] || (() => <Puzzle size={24} className="text-starlight-400" />))

                    return (
                      <button
                        key={item.id}
                        onClick={() => {
                          if (isConnected) {
                            setBrowseModal(null)
                            setActiveTab(browseModal === 'connectors' ? 'connectors' : 'extensions')
                            setExpandedItem(item.id)
                          } else if (browseModal === 'extensions' && cloudMode) {
                            // Cloud mode: auto-install the extension
                            setExtensions((prev) => {
                              if (prev.some((e) => e.id === item.id)) return prev
                              return [...prev, {
                                id: item.id,
                                name: item.name,
                                description: item.description,
                                enabled: true,
                                permission: 'ALLOW',
                              }]
                            })
                            toast.success(`${item.name} installed and enabled`)
                          } else if (browseModal === 'extensions' && !cloudMode) {
                            // Local mode: install via backend API
                            api.post('/connections/extensions/install', {
                              id: item.id,
                              name: item.name,
                              description: item.description,
                            }).then(() => {
                              void fetchExtensions()
                              toast.success(`${item.name} installed`)
                            }).catch(() => {
                              toast.error(`Failed to install ${item.name}. Check MCP server configuration.`)
                            })
                          } else if (browseModal === 'connectors') {
                            // Session 10: was window.open(item.authUrl, '_blank')
                            // which opened the product homepage (mail.google.com)
                            // instead of the OAuth consent screen. Now goes through
                            // startOAuthConnect which resolves the real Google/
                            // Notion/Slack OAuth URL from the backend and pops it.
                            setBrowseModal(null)
                            void startOAuthConnect({
                              connectorId: item.id,
                              connectorName: item.name,
                              onSuccess: fetchConnectorInstances,
                              onRequestSetup: (missing) =>
                                requestOAuthSetup(item.id, item.name, missing),
                            })
                          }
                        }}
                        className="flex items-center gap-3 p-4 rounded-xl border border-white/5 bg-midnight-400/50 hover:bg-white/5 hover:border-white/10 transition-all text-left cursor-pointer group"
                      >
                        <div className="w-10 h-10 rounded-lg bg-white/5 flex items-center justify-center shrink-0">
                          <IconComp size={22} />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-semibold text-starlight-100">{item.name}</span>
                            {item.popularity && (
                              <span className="text-[9px] text-starlight-500 bg-white/5 px-1.5 py-0.5 rounded">{item.popularity}</span>
                            )}
                          </div>
                          <p className="text-xs text-starlight-400 truncate mt-0.5">{item.description}</p>
                        </div>
                        <div className="shrink-0">
                          {isConnected ? (
                            <CheckCircle2 size={18} className="text-accent-green" />
                          ) : browseModal === 'extensions' ? (
                            <span className="text-[10px] font-medium text-primary-400 bg-primary-500/10 px-2 py-1 rounded group-hover:bg-primary-500/20">Install</span>
                          ) : (
                            <Plus size={18} className="text-starlight-500 group-hover:text-primary-400 transition-colors" />
                          )}
                        </div>
                      </button>
                    )
                  })}
                </div>
              </div>

              {/* Footer */}
              <div className="px-6 py-3 border-t border-white/5 text-center">
                <a
                  href="https://github.com/modelcontextprotocol/servers"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-starlight-500 hover:text-primary-400 transition-colors inline-flex items-center gap-1"
                >
                  Browse all MCP servers on GitHub <ExternalLink size={10} />
                </a>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>

      {/* Session 10: inline OAuth broker setup modal -- replaces the
          jarring redirect to /settings when creds are missing. */}
      {oauthSetup && (
        <OAuthSetupModal
          connectorId={oauthSetup.connectorId}
          connectorName={oauthSetup.connectorName}
          missingField={oauthSetup.missingField}
          onClose={() => setOauthSetup(null)}
          onSaved={() => {
            setOauthSetup(null)
            toast.success(
              `${oauthSetup.connectorName} credentials saved. Click Connect again.`,
            )
            // Refetch extensions + runtimes so the tab counts update
            // immediately -- previously the user had to reload the
            // page before the newly-installed MCP appeared. This is
            // why the "MCP Servers (0)" counter stayed stale after
            // the "installed" toast.
            void fetchExtensions()
            void fetchRuntimes()
            void fetchConnectorInstances()
            // Refresh the live MCP registry too so the green "Live"
            // badge appears on the plugin row without waiting for
            // the 10s poll cycle.
            mcpRegistry.refresh()
          }}
        />
      )}
    </div>
  )
}

export default ConnectionsPage
