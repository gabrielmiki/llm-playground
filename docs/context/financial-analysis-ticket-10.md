# Financial LLM Analysis - Implementation Tickets

Generated from PRD: Financial Markets LLM Analysis System

---

## Ticket 10: Async Job Processing

**type**: task  
**layer**: generate  
**complexity**: medium  
**dependencies**: [Ticket 8]  

**title**: Implement async/background job processing for full analysis

**description**:  
Allow full analysis of up to 10 tickers to run in background, returning a job ID for status checks. Support queuing and status polling.

**acceptance_criteria**:
- Given up to 10 tickers, When analysis is submitted, Then job ID is returned immediately
- Given job ID, When status is checked, Then current state (queued/processing/complete/failed) is returned
- Given job complete, When report is retrieved, Then full analysis is available in all formats

**api_spec** (internal):
```
POST /analyze
Body: { tickers: [string], date: date }
Returns: { job_id: string, status: string }

GET /report/{job_id}
Returns: { status, report: Report | null }
```
