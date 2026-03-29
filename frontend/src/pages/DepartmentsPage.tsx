/**
 * DepartmentsPage -- Grid view of all 10 departments.
 * Each department has 6 sub-capabilities (MIND, EYES, HANDS, VOICE, SHIELD, MEMORY).
 */
import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import {
  Wrench,
  Layers,
  Megaphone,
  TrendingUp,
  Calculator,
  Settings,
  Microscope,
  Scale,
  GraduationCap,
  ShieldCheck,
  Bot,
  ChevronRight,
} from 'lucide-react'
import { usePageTitle } from '@/hooks/usePageTitle'
import { Card, Badge, Shimmer } from '@/components/common'
import { api } from '@/lib/api'
import type { DepartmentResponse, ApiResponse } from '@/types/api'

// Department icons + Tailwind color classes
const DEPT_META: Record<
  string,
  { icon: React.ReactNode; color: string; bgColor: string }
> = {
  Engineering:           { icon: <Wrench size={24} />,         color: 'text-primary-400',    bgColor: 'bg-primary-500/15' },
  Product:               { icon: <Layers size={24} />,         color: 'text-accent-purple',  bgColor: 'bg-accent-purple/15' },
  Marketing:             { icon: <Megaphone size={24} />,      color: 'text-status-success', bgColor: 'bg-status-success/15' },
  Sales:                 { icon: <TrendingUp size={24} />,     color: 'text-accent-cyan',    bgColor: 'bg-accent-cyan/15' },
  Finance:               { icon: <Calculator size={24} />,     color: 'text-status-warning', bgColor: 'bg-status-warning/15' },
  Operations:            { icon: <Settings size={24} />,       color: 'text-accent-amber',   bgColor: 'bg-accent-amber/15' },
  Research:              { icon: <Microscope size={24} />,     color: 'text-blue-400',       bgColor: 'bg-blue-500/15' },
  'Legal & Compliance':  { icon: <Scale size={24} />,          color: 'text-status-error',   bgColor: 'bg-status-error/15' },
  'Skill Governance':    { icon: <GraduationCap size={24} />,  color: 'text-fuchsia-400',    bgColor: 'bg-fuchsia-500/15' },
  'Security Operations': { icon: <ShieldCheck size={24} />,    color: 'text-pink-400',       bgColor: 'bg-pink-500/15' },
}

const FALLBACK = {
  icon: <Bot size={24} />,
  color: 'text-primary-400',
  bgColor: 'bg-primary-500/15',
}

// Sub-capabilities
const SUB_CAPS = ['MIND', 'EYES', 'HANDS', 'VOICE', 'SHIELD', 'MEMORY'] as const

export function DepartmentsPage() {
  usePageTitle('Departments')
  const navigate = useNavigate()
  const [departments, setDepartments] = useState<DepartmentResponse[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchDepts = async () => {
      try {
        const { data } = await api.get<ApiResponse<DepartmentResponse[]>>('/agents/departments')
        setDepartments(data.data || [])
      } catch (err) {
        console.error('Failed to load departments, using defaults:', err)
        setDepartments(
          Object.keys(DEPT_META).map((name, i) => ({
            id: `dept-${i}`,
            tenant_id: '',
            name,
            description: `${name} department`,
            sunflower_index: i,
            cell_id: null,
            config: null,
            is_active: true,
            agent_count: 6,
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          })),
        )
      } finally {
        setLoading(false)
      }
    }
    fetchDepts()
  }, [])

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-7xl mx-auto p-6 space-y-6">
        {/* Header */}
        <motion.div
          className="flex items-center justify-between"
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <div>
            <h1 className="text-2xl font-display font-bold text-starlight-100">Departments</h1>
            <p className="text-sm text-starlight-400">
              10 department-agents x 6 sub-capabilities
            </p>
          </div>
        </motion.div>

        {loading ? (
          <Shimmer count={10} layout="card-grid" />
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4">
            {departments.map((dept, i) => {
              const meta = DEPT_META[dept.name] || FALLBACK
              return (
                <motion.div
                  key={dept.id}
                  initial={{ opacity: 0, y: 16 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.04 }}
                >
                  <Card
                    variant="glass"
                    padding="md"
                    className="cursor-pointer hover:border-white/10 transition-all group"
                    onClick={() => navigate(`/departments/${dept.id}`)}
                  >
                    <div className="flex items-start justify-between mb-3">
                      <div className={`p-2.5 rounded-lg ${meta.bgColor} ${meta.color}`}>
                        {meta.icon}
                      </div>
                      <Badge variant={dept.is_active ? 'success' : 'default'} size="sm">
                        {dept.is_active ? 'Active' : 'Inactive'}
                      </Badge>
                    </div>
                    <h3 className="text-sm font-display font-semibold text-starlight-100 mb-1">
                      {dept.name}
                    </h3>
                    <p className="text-[11px] text-starlight-500 mb-3 line-clamp-2">
                      {dept.description}
                    </p>

                    {/* Sub-capability dots */}
                    <div className="flex items-center gap-1 mb-2">
                      {SUB_CAPS.map((cap) => (
                        <div
                          key={cap}
                          className={`w-1.5 h-1.5 rounded-full ${meta.bgColor.replace('/15', '/40')}`}
                          title={cap}
                        />
                      ))}
                      <span className="text-[10px] text-starlight-500 ml-1">6 caps</span>
                    </div>

                    <div className="flex items-center justify-between text-[10px] text-starlight-500">
                      <span>{dept.agent_count} agents</span>
                      <ChevronRight
                        size={12}
                        className="opacity-0 group-hover:opacity-100 transition-opacity"
                      />
                    </div>
                  </Card>
                </motion.div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}

export default DepartmentsPage
