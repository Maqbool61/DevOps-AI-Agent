---
name: New Platform Support
about: Request support for a new platform/tool
title: '[PLATFORM] Add support for '
labels: enhancement, new-platform
assignees: ''
---

## Platform Information

**Platform Name:** <!-- e.g., CircleCI, DataDog, etc. -->

**Platform Category:**
- [ ] CI/CD
- [ ] Cloud Provider
- [ ] Monitoring
- [ ] Container Registry
- [ ] Database
- [ ] Other: ____________

**Official Website:** <!-- Link to platform -->

**API Documentation:** <!-- Link to API docs -->

## Use Case

<!-- Why should this platform be supported? How would it help? -->

## Integration Requirements

### Authentication

<!-- How does the platform authenticate? (API keys, OAuth, etc.) -->

### Key Features Needed

<!-- What features/operations should the agent support? -->

- [ ] Fetch logs
- [ ] Get status/health
- [ ] Trigger builds/deployments
- [ ] Restart/scale services
- [ ] Create PRs/Issues
- [ ] Other: ____________

### API Endpoints

<!-- List relevant API endpoints -->

1. Get logs: `GET /api/...`
2. Get status: `GET /api/...`
3. ...

## Example Incident Flow

<!-- Describe how the agent should handle incidents from this platform -->

```
1. Alert received → 
2. Fetch logs from X → 
3. Analyze Y → 
4. Take action Z
```

## Current Workaround

<!-- If you have a workaround, please describe it -->

## Additional Context

<!-- Any other information about the platform -->

### Similar Platforms

<!-- Are there similar platforms already supported? -->

### Community Interest

<!-- Do you know others who would benefit from this? -->

## Are you willing to contribute this integration?

- [ ] Yes, I can implement this
- [ ] Yes, but I need help with testing (no access to the platform)
- [ ] I can help with testing (have access to the platform)
- [ ] No, but I'd like to see it implemented
