import React from 'react'
import { Badge } from './Badge'
import { Icon } from './Icon'
import './AlertStrip.css'

export type AlertSeverity = 'error' | 'warn' | 'info' | 'success'

export interface Alert {
  id: string
  severity: AlertSeverity
  message: string
}

export interface AlertStripProps extends React.HTMLAttributes<HTMLDivElement> {
  alerts?: Alert[]
  onDismiss?: (alertId: string) => void
}

const SEVERITY_COLOR_MAP: Record<AlertSeverity, 'rose' | 'amber' | 'cyan' | 'emerald'> = {
  error: 'rose',
  warn: 'amber',
  info: 'cyan',
  success: 'emerald',
}

export const AlertStrip = React.forwardRef<HTMLDivElement, AlertStripProps>(
  ({ alerts = [], onDismiss, className = '', ...props }, ref) => {
    const classNames = ['alert-strip', className].filter(Boolean).join(' ')

    if (alerts.length === 0) {
      return null
    }

    return (
      <div ref={ref} className={classNames} data-testid="alert-strip" {...props}>
        {alerts.map(alert => (
          <div key={alert.id} className="alert-strip__alert" data-testid={`alert-${alert.id}`}>
            <Badge color={SEVERITY_COLOR_MAP[alert.severity]} data-testid={`alert-severity-${alert.severity}`} />
            <div className="alert-strip__message" data-testid="alert-message">
              {alert.message}
            </div>
            {onDismiss && (
              <button
                type="button"
                className="alert-strip__dismiss"
                onClick={() => onDismiss(alert.id)}
                aria-label={`Dismiss alert: ${alert.message}`}
                data-testid={`alert-dismiss-${alert.id}`}
              >
                <Icon name="x" size={16} />
              </button>
            )}
          </div>
        ))}
      </div>
    )
  }
)

AlertStrip.displayName = 'AlertStrip'

export default AlertStrip
