/**
 * API Performance Validator Custom Tool
 *
 * Deliverable: A custom tool that validates API responses, measures latency,
 * and checks for SLA compliance.
 *
 * Uses createSdkMcpServer and tool helper from Claude Agent SDK.
 */

import { z } from "zod";
import { createSdkMcpServer, tool } from "@anthropic-ai/claude-agent-sdk";

// -----------------------------------------------------------------------------
// Exported Types
// -----------------------------------------------------------------------------

export interface ValidationResult {
  success: boolean;
  statusCode: number;
  latencyMs: number;
  schemaValid: boolean;
  schemaErrors: string[] | null;
  performanceIssues: {
    exceedsSLA: boolean;
    slaThresholdMs: number;
    actualLatencyMs: number;
  };
  breakingChanges: string[] | null;
  warnings: string[];
}

// -----------------------------------------------------------------------------
// Tool Schema
// -----------------------------------------------------------------------------

const validateApiSchema = {
  apiUrl: z.url().describe("The API endpoint URL to validate"),
  method: z.enum(["GET", "POST", "PUT", "DELETE"]).describe("HTTP method"),
  expectedFields: z.array(z.string()).describe("Expected fields in response"),
  maxLatencyMs: z.number().positive().describe("SLA threshold in milliseconds"),
  headers: z.record(z.string(), z.string()).optional().describe("Optional headers for auth"),
  body: z.string().optional().describe("Optional request body for POST/PUT"),
};

// -----------------------------------------------------------------------------
// Validation Logic
// -----------------------------------------------------------------------------

async function validateApiResponse(
  apiUrl: URL,
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
    // TODO: Step 1 - Create fetchOptions object with:
    //   - method: the HTTP method
    //   - headers: merge "Content-Type": "application/json" with optional headers
    //   - body: include body only for POST/PUT requests
    const fetchOptions: RequestInit = {
      method,
      headers: {
        "Content-Type": "application/json",
        ...(headers || {}),
      },
      ...(body && (method === "POST" || method === "PUT") ? { body } : {}),
    };

    // TODO: Step 2 - Make the fetch request and capture:
    //   - response from fetch(apiUrl, fetchOptions)
    //   - statusCode from response.status
    //   - latencyMs = Date.now() - start
    const response = await fetch(apiUrl, fetchOptions);
    statusCode = response.status;
    const latencyMs = Date.now() - start;

    // TODO: Step 3 - Parse response JSON
    //   - Use try/catch around response.json()
    //   - If parsing fails, push "Response is not valid JSON" to schemaErrors
    try {
      const jsonText = await response.text();
      responseData = jsonText ? JSON.parse(jsonText) : {};
    } catch {
      schemaErrors.push("Response is not valid JSON");
    }

    // TODO: Step 4 - Check for missing expected fields
    //   - Get responseFields = Object.keys(responseData)
    //   - For each expectedField not in responseFields:
    //     push `Missing required field: ${field}` to breakingChanges
    const responseFields = Object.keys(responseData);
    for (const field of expectedFields) {
      if (!responseFields.includes(field)) {
        breakingChanges.push(`Missing required field: ${field}`);
      }
    }

    // TODO: Step 5 - Check for extra fields (potential data leakage)
    //   - Find fields in response that are NOT in expectedFields
    //   - If any exist, push warning: `Unexpected fields in response: ${extraFields.join(", ")}`
    const extraFields = responseFields.filter((field) => !expectedFields.includes(field));
    if (extraFields.length > 0) {
      warnings.push(`Unexpected fields in response: ${extraFields.join(", ")}`);
    }

    // TODO: Step 6 - Check HTTP status code
    //   - If statusCode < 200 or statusCode >= 300:
    //     push `HTTP error: ${statusCode}` to schemaErrors
    if (statusCode < 200 || statusCode >= 300) {
      schemaErrors.push(`HTTP error: ${statusCode}`);
    }

    // TODO: Step 7 - Check performance against SLA
    //   - exceedsSLA = latencyMs > maxLatencyMs
    //   - If exceeds, push warning about response time
    const exceedsSLA = latencyMs > maxLatencyMs;
    if (exceedsSLA) {
      warnings.push(`Response time (${latencyMs}ms) exceeded SLA threshold of ${maxLatencyMs}ms`);
    }

    // TODO: Step 8 - Return ValidationResult object with all fields:
    //   - success: true if statusCode is 2xx AND no breakingChanges
    //   - statusCode, latencyMs
    //   - schemaValid: true if no schemaErrors AND no breakingChanges
    //   - schemaErrors: array or null if empty
    //   - performanceIssues: { exceedsSLA, slaThresholdMs, actualLatencyMs }
    //   - breakingChanges: array or null if empty
    //   - warnings
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
    // TODO: Step 9 - Handle network errors
    //   - Catch errors from fetch (network failures)
    //   - Return ValidationResult with:
    //     - success: false
    //     - statusCode: 0
    //     - schemaErrors: [`Network error: ${error.message}`]
    //     - warnings: ["Request failed - could not reach endpoint"]

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

// -----------------------------------------------------------------------------
// Create Custom Tool Server
// -----------------------------------------------------------------------------

// TODO: Step 10 - Create and export the MCP server
//
// Use createSdkMcpServer with:
//   - name: "api-validator"
//   - version: "1.0.0"
//   - tools: array with one tool
//
// The tool should:
//   - name: "validate_api_response"
//   - description: "Validates API responses for schema compliance, performance, and SLA adherence..."
//   - schema: validateApiSchema
//   - handler: async function that:
//     1. Calls validateApiResponse() with args
//     2. Returns { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] }

export const apiValidatorServer = createSdkMcpServer({
  name: "api-validator",
  version: "1.0.0",
  tools: [
    // TODO: Add your tool here using the tool() helper
    // tool("validate_api_response", "description", schema, handler)
    tool(
      "validate_api_response",
      "Validates API responses for schema compliance, performance, and SLA adherence...",
      validateApiSchema,
      async (args) => {
        const result = await validateApiResponse(
          new URL(args.apiUrl),
          args.method,
          args.expectedFields,
          args.maxLatencyMs,
          args.headers,
          args.body
        );

        return {
          content: [
            {
              type: "text",
              text: JSON.stringify(result, null, 2),
            },
          ],
        };
      }
    ),
  ],
});
