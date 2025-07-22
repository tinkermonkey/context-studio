/**
 * API Logger
 * 
 * Structured logging utility for API operations
 */

type LogLevel = 'debug' | 'info' | 'warn' | 'error';

interface LogEntry {
  level: LogLevel;
  message: string;
  timestamp: string;
  context?: Record<string, unknown>;
}

class ApiLogger {
  private isDev = process.env.NODE_ENV === 'development';

  private formatMessage(level: LogLevel, message: string, context?: Record<string, unknown>): LogEntry {
    return {
      level,
      message,
      timestamp: new Date().toISOString(),
      context,
    };
  }

  private log(entry: LogEntry) {
    if (!this.isDev) return;

    const logFn = console[entry.level] || console.log;
    const prefix = `[API ${entry.level.toUpperCase()}]`;
    
    if (entry.context) {
      logFn(`${prefix} ${entry.message}`, entry.context);
    } else {
      logFn(`${prefix} ${entry.message}`);
    }
  }

  debug(message: string, context?: Record<string, unknown>) {
    this.log(this.formatMessage('debug', message, context));
  }

  info(message: string, context?: Record<string, unknown>) {
    this.log(this.formatMessage('info', message, context));
  }

  warn(message: string, context?: Record<string, unknown>) {
    this.log(this.formatMessage('warn', message, context));
  }

  error(message: string, context?: Record<string, unknown>) {
    this.log(this.formatMessage('error', message, context));
  }

  request(method: string, url: string, data?: unknown) {
    this.debug(`${method.toUpperCase()} ${url}`, { data });
  }

  response(method: string, url: string, status: number, data?: unknown) {
    this.debug(`${method.toUpperCase()} ${url} → ${status}`, { data });
  }

  requestError(method: string, url: string, error: unknown) {
    this.error(`${method.toUpperCase()} ${url} failed`, { error });
  }
}

export const apiLogger = new ApiLogger();
