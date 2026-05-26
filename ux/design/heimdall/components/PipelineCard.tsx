import React from 'react'
import './PipelineCard.css'
import { Icon, type IconName } from './Icon'
import { Chip } from './Chip'
import type { StatusColor } from './statusColors'

export interface FlowNode {
  id: string
  name: string
  label?: string
  icon: IconName | React.ReactElement
}

export interface Pipeline {
  id: string
  name: string
  description?: string
  status: 'running' | 'success' | 'idle' | 'failed'
  target?: string
  flow: FlowNode[]
  recent: {
    ingested: number | string
    created: number | string
    updated: number | string
    errors: number
  }
  tags?: string[]
  lastRun?: string
}

export interface PipelineCardProps extends React.HTMLAttributes<HTMLDivElement> {
  pipeline: Pipeline
  onRun?: () => void
  onCancel?: () => void
  onOptions?: () => void
  compact?: boolean
  selected?: boolean
  headerAction?: React.ReactNode
  footerContent?: React.ReactNode
}

const statusChipColor: Record<Pipeline['status'], StatusColor> = {
  running: 'cyan',
  success: 'emerald',
  idle: 'neutral',
  failed: 'rose',
}

export const PipelineCard = React.forwardRef<HTMLDivElement, PipelineCardProps>(
  ({ pipeline, onRun, onCancel, onOptions, compact = false, selected = false, headerAction, footerContent, className, ...props }, ref) => {
    const statusColor = statusChipColor[pipeline.status]

    return (
      <div
        ref={ref}
        className={['pipeline-card', compact && 'pipeline-card--compact', selected && 'pipeline-card--selected', className].filter(Boolean).join(' ')}
        data-testid="pipeline-card"
        {...props}
      >
        {/* Head region */}
        <div className="pipeline-card__head">
          <div className="pipeline-card__head-left">
            <div className="pipeline-card__title-group">
              <div className="pipeline-card__name-mono">{pipeline.name}</div>
              {pipeline.id && <div className="pipeline-card__id-mono">{pipeline.id}</div>}
            </div>
            {pipeline.description && <p className="pipeline-card__description">{pipeline.description}</p>}
          </div>

          <div className="pipeline-card__head-right">
            <div className="pipeline-card__head-chips">
              <Chip variant={statusColor}>
                {pipeline.status}
              </Chip>
              {pipeline.target && (
                <Chip variant="neutral">
                  {pipeline.target}
                </Chip>
              )}
              {pipeline.tags && pipeline.tags.length > 0 && (
                <div className="pipeline-card__tags">
                  {pipeline.tags.map((tag) => (
                    <Chip key={tag} variant="neutral">
                      {tag}
                    </Chip>
                  ))}
                </div>
              )}
            </div>

            <div className="pipeline-card__head-actions">
              {headerAction}
              {onRun && pipeline.status !== 'running' && (
                <button type="button" className="pipeline-card__action-btn" onClick={onRun} data-testid="pipeline-run-btn">
                  Run
                </button>
              )}
              {onCancel && pipeline.status === 'running' && (
                <button type="button" className="pipeline-card__action-btn pipeline-card__action-btn--cancel" onClick={onCancel} data-testid="pipeline-cancel-btn">
                  Cancel
                </button>
              )}
              {onOptions && (
                <button type="button" aria-label="Pipeline options" className="pipeline-card__kebab-btn" onClick={onOptions} data-testid="pipeline-kebab-btn">
                  <Icon name="moreVertical" size={16} />
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Flow strip */}
        <div className="pipeline-card__flow">
          {pipeline.flow.map((node, index) => (
            <React.Fragment key={node.id}>
              <div className="pipeline-card__node">
                <div className="pipeline-card__icon-tile">
                  {typeof node.icon === 'string'
                    ? <Icon name={node.icon as IconName} size={16} />
                    : node.icon}
                </div>
                <div className="pipeline-card__node-content">
                  <div className="pipeline-card__node-name">{node.name}</div>
                  {node.label && <div className="pipeline-card__node-label">{node.label}</div>}
                </div>
              </div>

              {index < pipeline.flow.length - 1 && <div className="pipeline-card__arrow" />}
            </React.Fragment>
          ))}
        </div>

        {/* Foot region */}
        <div className="pipeline-card__foot">
          {footerContent ?? (
            <div className="pipeline-card__foot-row">
              <div className="pipeline-card__foot-col">
                <div className="pipeline-card__foot-label">LAST RUN</div>
                <div className="pipeline-card__foot-value">{pipeline.lastRun || '—'}</div>
              </div>
              <div className="pipeline-card__foot-col">
                <div className="pipeline-card__foot-label">INGESTED</div>
                <div className="pipeline-card__foot-value">{pipeline.recent.ingested}</div>
              </div>
              <div className="pipeline-card__foot-col">
                <div className="pipeline-card__foot-label">CREATED</div>
                <div className="pipeline-card__foot-value">{pipeline.recent.created}</div>
              </div>
              <div className="pipeline-card__foot-col">
                <div className="pipeline-card__foot-label">UPDATED</div>
                <div className="pipeline-card__foot-value">{pipeline.recent.updated}</div>
              </div>
              <div className={[
                'pipeline-card__foot-col',
                Number(pipeline.recent.errors) > 0 && 'pipeline-card__foot-col--error'
              ].filter(Boolean).join(' ')}>
                <div className="pipeline-card__foot-label">ERRORS</div>
                <div className="pipeline-card__foot-value">{pipeline.recent.errors}</div>
              </div>
            </div>
          )}
        </div>
      </div>
    )
  }
)

PipelineCard.displayName = 'PipelineCard'

export default PipelineCard
