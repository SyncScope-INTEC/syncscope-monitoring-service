"""
Structured logging utilities for monitoring service.
"""

import logging
import json
import sys
from datetime import datetime
from django.conf import settings


class StructuredFormatter(logging.Formatter):
    """
    Custom formatter that outputs structured JSON logs.
    """
    
    def format(self, record):
        # Create the base log entry
        log_entry = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'service': 'syncscope-monitoring-service',
            'environment': getattr(settings, 'ENVIRONMENT', 'development')
        }
        
        # Add exception info if present
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
        
        # Add extra fields from the log record
        if hasattr(record, 'user_id'):
            log_entry['user_id'] = record.user_id
        if hasattr(record, 'session_id'):
            log_entry['session_id'] = record.session_id
        if hasattr(record, 'request_id'):
            log_entry['request_id'] = record.request_id
        if hasattr(record, 'endpoint'):
            log_entry['endpoint'] = record.endpoint
        if hasattr(record, 'method'):
            log_entry['method'] = record.method
        if hasattr(record, 'status_code'):
            log_entry['status_code'] = record.status_code
        if hasattr(record, 'duration'):
            log_entry['duration_ms'] = record.duration
        
        # Add any custom extra fields
        for key, value in record.__dict__.items():
            if key.startswith('extra_'):
                log_entry[key[6:]] = value  # Remove 'extra_' prefix
        
        return json.dumps(log_entry)


class MonitoringLogger:
    """
    Structured logger for monitoring service events.
    """
    
    def __init__(self, name='apps.monitoring'):
        self.logger = logging.getLogger(name)
    
    def log_session_event(self, event_type, session_id, user_id, **kwargs):
        """Log session-related events."""
        self.logger.info(
            f"Session {event_type}",
            extra={
                'session_id': str(session_id),
                'user_id': user_id,
                'event_type': event_type,
                **kwargs
            }
        )
    
    def log_activity_event(self, activity_type, session_id, count=1, **kwargs):
        """Log activity-related events."""
        self.logger.info(
            f"Activity logged: {activity_type}",
            extra={
                'session_id': str(session_id),
                'activity_type': activity_type,
                'activity_count': count,
                **kwargs
            }
        )
    
    def log_metrics_event(self, session_id, file_path, metrics_type='code', **kwargs):
        """Log metrics-related events."""
        self.logger.info(
            f"Metrics recorded: {metrics_type}",
            extra={
                'session_id': str(session_id),
                'file_path': file_path,
                'metrics_type': metrics_type,
                **kwargs
            }
        )
    
    def log_api_request(self, method, endpoint, user_id=None, status_code=None, 
                       duration=None, **kwargs):
        """Log API request events."""
        self.logger.info(
            f"API Request: {method} {endpoint}",
            extra={
                'method': method,
                'endpoint': endpoint,
                'user_id': user_id,
                'status_code': status_code,
                'duration': duration,
                **kwargs
            }
        )
    
    def log_error(self, message, error=None, **kwargs):
        """Log error events with structured context."""
        extra_data = kwargs
        if error:
            extra_data['error_type'] = error.__class__.__name__
            extra_data['error_message'] = str(error)
        
        self.logger.error(message, exc_info=error, extra=extra_data)
    
    def log_performance(self, operation, duration, **kwargs):
        """Log performance metrics."""
        self.logger.info(
            f"Performance: {operation}",
            extra={
                'operation': operation,
                'duration': duration,
                'performance_metric': True,
                **kwargs
            }
        )


# Global monitoring logger instance
monitoring_logger = MonitoringLogger()