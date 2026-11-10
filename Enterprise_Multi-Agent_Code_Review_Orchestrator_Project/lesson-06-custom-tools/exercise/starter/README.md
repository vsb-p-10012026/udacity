# Exercise: Custom Tools - API Validator

Build a custom MCP tool that validates API responses, measures latency, and checks for SLA compliance.

## Objective

Implement the validation logic and tool server in `src/api-validator.ts`. The tool makes HTTP requests, checks response schemas against expected fields, measures latency against SLA thresholds, and detects breaking changes.

## Learning Goals

- Create custom tools using `createSdkMcpServer` and `tool()` helper
- Define tool schemas with Zod for input validation
- Make HTTP requests with `fetch()` and handle errors
- Return structured results from custom tools
- Understand the `mcp__<server>__<tool>` naming convention

## Project Structure

```
src/
├── api-validator.ts  # YOUR IMPLEMENTATION (has TODOs)
└── index.ts          # Agent integration tests (do not modify)
```

## Setup

```bash
# From repo root (shared node_modules)
npm install
```

## Authentication Setup

Copy `.env.example` to `.env` (required in all environments):
```bash
cp .env.example .env
```

In Vocareum workspace, `ANTHROPIC_API_KEY` and `ANTHROPIC_BASE_URL` are **already configured** in your environment — the `.env` file only needs to provide `ANTHROPIC_MODEL`.

For local development, also uncomment and fill in your credentials in `.env`:
```
ANTHROPIC_API_KEY=your-key-here
ANTHROPIC_BASE_URL=your-base-url-here
```

**Troubleshooting:**
- **`Error: ANTHROPIC_MODEL is not set`** — make sure you ran `cp .env.example .env`
- **`Error: API key not found`** — in Vocareum this is pre-configured; locally, set `ANTHROPIC_API_KEY` and `ANTHROPIC_BASE_URL` in `.env`

## Your Tasks

Complete the TODOs in `src/api-validator.ts`:

### Step 1: Create Fetch Options

Build a `RequestInit` object with the HTTP method, merged headers (`Content-Type: application/json` plus any custom headers), and body (only for POST/PUT).

### Step 2: Make the HTTP Request

Call `fetch(apiUrl, fetchOptions)` and capture the response status code. Calculate latency using `Date.now() - start`.

### Step 3: Parse Response JSON

Wrap `response.json()` in a try/catch. If parsing fails, record a schema error.

### Step 4: Check Expected Fields

Compare `Object.keys(responseData)` against `expectedFields`. Missing fields are breaking changes.

### Step 5: Detect Extra Fields

Find fields in the response that are not in `expectedFields`. These are potential data leakage warnings.

### Step 6: Validate Status Code

Non-2xx status codes should be recorded as schema errors.

### Step 7: Check SLA Performance

Compare actual latency against `maxLatencyMs`. Add a warning if the SLA is exceeded.

### Step 8: Return ValidationResult

Build and return the complete `ValidationResult` object with all validation findings.

### Step 9: Handle Network Errors

In the catch block, return a `ValidationResult` with appropriate error information for fetch failures.

### Step 10: Create the Tool Server

Wire up `validateApiResponse` as an MCP tool using `createSdkMcpServer` and `tool()`. Export as `apiValidatorServer`. The tool handler should call your validation function and return the result as JSON.

## Run

```bash
# From this directory (lesson-06-custom-tools/exercise/starter)
npm start
```

## Success Criteria

- [ ] Tool server exports `apiValidatorServer`
- [ ] Tool validates API responses successfully
- [ ] Missing expected fields detected as breaking changes
- [ ] Extra fields detected as warnings
- [ ] HTTP errors properly reported
- [ ] SLA violations detected when latency exceeds threshold
- [ ] Network errors handled gracefully
- [ ] All three agent integration tests pass

## Bonus: Unit Testing Your Tool

Extract your validation logic into a separate exported function so you can unit test it without running the agent:

```typescript
// Export the validation function for testing
export async function validateApiResponse(
  // Your validation logic here
  apiUrl: string | URL,
  method: string,
  expectedFields: string[],
  maxLatencyMs: number,
  headers?: Record<string, string>,
  body?: string
): Promise<ValidationResult> {
  const warnings: string[] = [];
  const schemaErrors: string[] = [];
  const breakingChanges: string[] = [];

  const start = Date.now();
  let statusCode = 0;
  let responseData: Record<string, unknown> = {};

  try {
    // Step 1 - Create fetchOptions object
    const fetchOptions: RequestInit = {
      method,
      headers: {
        "Content-Type": "application/json",
        ...(headers || {}),
      },
      ...(body && (method === "POST" || method === "PUT") ? { body } : {}),
    };

    // Step 2 - Make the fetch request and capture metrics
    const response = await fetch(apiUrl, fetchOptions);
    statusCode = response.status;
    const latencyMs = Date.now() - start;

    // Step 3 - Parse response JSON
    try {
      const jsonText = await response.text();
      responseData = jsonText ? JSON.parse(jsonText) : {};
    } catch {
      schemaErrors.push("Response is not valid JSON");
    }

    // Step 4 - Check for missing expected fields
    const responseFields = Object.keys(responseData);
    for (const field of expectedFields) {
      if (!responseFields.includes(field)) {
        breakingChanges.push(`Missing required field: ${field}`);
      }
    }

    // Step 5 - Check for extra fields (potential data leakage)
    const extraFields = responseFields.filter((field) => !expectedFields.includes(field));
    if (extraFields.length > 0) {
      warnings.push(`Unexpected fields in response: ${extraFields.join(", ")}`);
    }

    // Step 6 - Check HTTP status code
    if (statusCode < 200 || statusCode >= 300) {
      schemaErrors.push(`HTTP error: ${statusCode}`);
    }

    // Step 7 - Check performance against SLA
    const exceedsSLA = latencyMs > maxLatencyMs;
    if (exceedsSLA) {
      warnings.push(`Response time (${latencyMs}ms) exceeded SLA threshold of ${maxLatencyMs}ms`);
    }

    // Step 8 - Determine success and schema validity flags
    const hasSchemaErrors = schemaErrors.length > 0;
    const hasBreakingChanges = breakingChanges.length > 0;
    const success = statusCode >= 200 && statusCode < 300 && !hasBreakingChanges;
    const schemaValid = !hasSchemaErrors && !hasBreakingChanges;

    return {
      success,
      statusCode,
      latencyMs,
      schemaValid,
      schemaErrors: hasSchemaErrors ? schemaErrors : null,
      performanceIssues: {
        exceedsSLA,
        slaThresholdMs: maxLatencyMs,
        actualLatencyMs: latencyMs,
      },
      breakingChanges: hasBreakingChanges ? breakingChanges : null,
      warnings,
    };
  } catch (error) {
    // Step 9 - Handle network errors
    const latencyMs = Date.now() - start;
    return {
      success: false,
      statusCode: 0,
      latencyMs,
      schemaValid: false,
      schemaErrors: [`Network error: ${(error as Error).message}`],
      performanceIssues: {
        exceedsSLA: latencyMs > maxLatencyMs,
        slaThresholdMs: maxLatencyMs,
        actualLatencyMs: latencyMs,
      },
      breakingChanges: null,
      warnings: ["Request failed - could not reach endpoint"],
    };
  }
}

// Tool handler calls the exported function
tool("validate_api_response", "...", schema, async (args) => {
  const result = await validateApiResponse(/* ... */);
  return { content: [{ type: "text", text: JSON.stringify(result) }] };
});
```

Then create `api-validator.test.ts` to test your validation logic directly:

```bash
# Run unit tests (no API calls, fast iteration)
npm run test:unit

# Run agent integration tests (requires API key)
npm run test
```

See the solution for comprehensive unit test examples.
