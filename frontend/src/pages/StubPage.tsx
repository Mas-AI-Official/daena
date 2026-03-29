import { Construction } from 'lucide-react'
import { Card } from '@/components/common'

interface StubPageProps {
  title: string
  description?: string
}

/**
 * Placeholder page for routes not yet implemented.
 */
export function StubPage({ title, description }: StubPageProps) {
  return (
    <div className="h-full flex items-center justify-center p-6">
      <Card variant="glass" padding="lg" className="text-center max-w-md">
        <Construction size={48} className="text-accent-amber mx-auto mb-4" />
        <h2 className="text-xl font-display font-semibold text-starlight-100 mb-2">{title}</h2>
        <p className="text-sm text-starlight-400">
          {description || 'This module will be built in an upcoming priority batch.'}
        </p>
      </Card>
    </div>
  )
}

export default StubPage
