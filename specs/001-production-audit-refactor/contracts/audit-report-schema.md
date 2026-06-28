# Audit Report Schema

**Feature**: `001-production-audit-refactor`
**Date**: 2026-06-28

## Overview

This document defines the format and structure for the engineering audit report deliverable. All audit findings MUST conform to this schema to ensure consistency and traceability.

## Report Structure

The audit report is a single Markdown document organized by review area. Each area contains a summary followed by individual findings.

### Top-Level Sections

```markdown
# Engineering Audit Report: OpusClip Pipeline v2.1

## Executive Summary
- Total findings: N
- By severity: Critical (X), High (Y), Medium (Z), Low (W)
- Top 3 recommendations

## 1. Architecture Review
### Findings
#### [ARCH-001] <title>
...

## 2. Code Review
### Findings
#### [CODE-001] <title>
...

## 3. Performance Review
## 4. AI Pipeline Review
## 5. Dependency Review
## 6. Reliability Review
## 7. Security Review
## 8. Production Readiness Review
## 9. Prioritized Improvement Roadmap
## 10. Refactoring Rules & Constraints
```

### Finding Format

Every finding MUST use this format:

```markdown
#### [<AREA>-<NNN>] <Title>

**Severity**: Critical | High | Medium | Low
**Location**: Cell <N>, Lines <start>–<end>
**Constitution**: Principle <Roman> — <name>

**Issue**: <description of what is wrong>

**Impact**: <what happens if not fixed>

**Suggested Fix**: <concrete actionable recommendation>

**Related**: <comma-separated IDs of related findings, if any>
```

### Area Prefixes

| Prefix | Area |
|--------|------|
| `ARCH` | Architecture Review |
| `CODE` | Code Review |
| `PERF` | Performance Review |
| `AI` | AI Pipeline Review |
| `DEP` | Dependency Review |
| `REL` | Reliability Review |
| `SEC` | Security Review |
| `PROD` | Production Readiness Review |

### Severity Mapping

| Severity | Response Time | Examples |
|----------|--------------|---------|
| Critical | Must fix before any deployment | Hardcoded API key, shell injection, data loss risk |
| High | Fix in first refactoring phase | Monolithic architecture, missing error handling, no logging |
| Medium | Address in subsequent phases | Code duplication, suboptimal algorithms, missing validation |
| Low | Polish phase or defer | Naming conventions, style inconsistencies, minor optimizations |

## Validation Rules

1. Every finding ID must be unique within the report
2. Every finding must include all required fields (severity, location, issue, impact, suggested fix)
3. Area prefix must match the section the finding appears in
4. Severity must be one of the four defined levels
5. Related findings must reference valid IDs that exist in the report
6. Constitution references must point to actual principles (I–V)
