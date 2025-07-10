# Time-Cycle Application

This project provides a Streamlit-based tool for analysing market time cycles. It identifies pivot highs/lows from uploaded price data, projects future dates using configurable intervals, and highlights clusters of overlaps on an interactive chart.

## Debugging

A lightweight debugging helper is available through `engine.debugger`.
To enable debug logging to `debug.log`, set the environment variable `DEBUG=1`
before running the app:

```bash
DEBUG=1 streamlit run app.py
```

Key functions in the engine modules and file loader are wrapped with a
`log_exceptions` decorator so that any uncaught exceptions are written to
`debug.log` along with a stack trace.
