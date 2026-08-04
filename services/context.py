import contextvars

current_message = contextvars.ContextVar('current_message', default=None)