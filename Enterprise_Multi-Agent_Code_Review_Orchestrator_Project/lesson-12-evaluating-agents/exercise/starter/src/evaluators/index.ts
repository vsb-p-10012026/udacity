/**
 * Sentiment Agent Evaluators
 *
 * TODO: Implement three evaluators to assess agent performance:
 * 1. Tool Call Evaluator - Did the agent call the correct tool?
 * 2. Schema Validity Evaluator - Is the output valid against the Zod schema?
 * 3. Accuracy Evaluator - Does the sentiment match the expected value?
 */

import { SentimentAnalysisSchema, type SentimentAnalysis, type SentimentTestCase } from "../types.js";
import type { AgentTrace } from "../sentiment-agent.js";

// -----------------------------------------------------------------------------
// Evaluator Result Types
// -----------------------------------------------------------------------------

export interface EvaluatorResult {
  name: string;
  passed: boolean;
  score: number; // 0 to 1
  details: string;
}

export interface EvaluationReport {
  testCase: SentimentTestCase;
  evaluators: EvaluatorResult[];
  overallPassed: boolean;
  overallScore: number;
}

// -----------------------------------------------------------------------------
// TODO: Evaluator 1 - Tool Call Evaluator
// Checks if the agent called the sentiment analysis tool correctly
// -----------------------------------------------------------------------------

export function evaluateToolCall(trace: AgentTrace): EvaluatorResult {
  const expectedTool = "mcp__sentiment-analyzer__analyze_sentiment";
  const toolCalls = trace.toolCalls || [];

  // TODO: Step 1 - Check if any tool was called
  if (toolCalls.length === 0) {
    return {
      name: "Tool Call Evaluator",
      passed: false,
      score: 0,
      details: "Failed: No tool calls were made by the agent.",
    };
  }

  // TODO: Step 2 - Check if the correct tool was called
  const targetCall = toolCalls.find((call: any) => (call.name || call.toolName) === expectedTool);
  if (!targetCall) {
    return {
      name: "Tool Call Evaluator",
      passed: false,
      score: 0.25,
      details: `Failed: Expected tool '${expectedTool}' was not invoked: ${toolCalls.map(c => c.name).join(", ")}`,
    };
  }

  // TODO: Step 3 - Check if text parameter was provided
const sentimentCall = toolCalls.find(call => call.name === expectedTool);
const hasTextInput = sentimentCall?.input && typeof sentimentCall.input.text === "string";
  if (!hasTextInput) {
    return {
      name: "Tool Call Evaluator",
      passed: false,
      score: 0.5,
      details: "Tool was called but 'text' parameter was missing or invalid",
    };
  }

  // TODO: Step 4 - Return success if all checks pass

  return {
    name: "Tool Call Evaluator",
    passed: true,
    score: 1.0,
    details: `Passed: Successfully invoked '${expectedTool}' with valid parameters.`,
  };
}

// -----------------------------------------------------------------------------
// TODO: Evaluator 2 - Schema Validity Evaluator
// Checks if the output conforms to the SentimentAnalysis Zod schema
// -----------------------------------------------------------------------------

export function evaluateSchemaValidity(trace: AgentTrace): EvaluatorResult {
  const result = trace.result;

  // TODO: Step 1 - Check if result exists
  if (!result) {
    return {
      name: "Schema Validity Evaluator",
      passed: false,
      score: 0,
      details: "Failed: Agent produced no result output.",
    };
  }

  // TODO: Step 2 - Validate against Zod schema
  const validation = SentimentAnalysisSchema.safeParse(result);
  
    if (!validation.success) {
      const errors = validation.error.issues.map(e => `${e.path.join(".")}: ${e.message}`);
      return {
        name: "Schema Validity Evaluator",
        passed: false,
        score: 0.5,
        details: `Schema validation failed: ${errors.join("; ")}`,
      };
    }
  
 // TODO: Step 3 - Check all required fields are valid
  const checks = [
    { field: "text", valid: typeof result.text === "string" && result.text.length > 0 },
    { field: "sentiment", valid: ["positive", "negative", "neutral"].includes(result.sentiment) },
    { field: "confidence", valid: result.confidence >= 0 && result.confidence <= 1 },
    { field: "keywords", valid: Array.isArray(result.keywords) },
    { field: "explanation", valid: typeof result.explanation === "string" && result.explanation.length > 0 },
  ];

  const passedChecks = checks.filter(c => c.valid).length;
  const score = passedChecks / checks.length;

  if (score < 1) {
    const failedFields = checks.filter(c => !c.valid).map(c => c.field);
    return {
      name: "Schema Validity Evaluator",
      passed: false,
      score,
      details: `Some fields are invalid: ${failedFields.join(", ")}`,
    };
  }
  // TODO: Step 4 - Return success if all fields valid
return {
    name: "Schema Validity Evaluator",
    passed: true,
    score: 1.0,
    details: "Passed: Output successfully conforms to SentimentAnalysis schema.",
  };
}

// -----------------------------------------------------------------------------
// TODO: Evaluator 3 - Accuracy Evaluator
// Checks if the detected sentiment matches the expected sentiment
// -----------------------------------------------------------------------------

export function evaluateAccuracy(
  trace: AgentTrace,
  testCase: SentimentTestCase
): EvaluatorResult {
  const result = trace.result as SentimentAnalysis | undefined;

  // TODO: Step 1 - Check if result exists
  // If !result, return failed result with score 0
if (!result || !result.sentiment) {
    return {
      name: "Accuracy Evaluator",
      passed: false,
      score: 0,
      details: "Failed: Result or sentiment field is missing.",
    };
  }

  // TODO: Step 2 - Compare actual vs expected sentiment
 const actualSentiment = result.sentiment.toLowerCase().trim();
  const expectedSentiment = testCase.expectedSentiment.toLowerCase().trim();

  if (actualSentiment === expectedSentiment) {
    return {
      name: "Accuracy Evaluator",
      passed: true,
      score: 1.0,
      details: `Passed: Sentiment matched expected value ('${expectedSentiment}').`,
    };
  }
  if (actualSentiment === "neutral") {
    return {
      name: "Accuracy Evaluator",
      passed: false,
      score: 0.5,
      details: `Expected '${expectedSentiment}' but got 'neutral'`,
    };
  }

  // TODO: Step 3 - Return appropriate result based on match
 return {
    name: "Accuracy Evaluator",
    passed: false,
    score: 0,
    details: `Failed: Expected sentiment '${expectedSentiment}', but got '${actualSentiment}'.`,
  };
}
// -----------------------------------------------------------------------------
// Run All Evaluators
// -----------------------------------------------------------------------------

export function runEvaluators(
  trace: AgentTrace,
  testCase: SentimentTestCase
): EvaluationReport {
  const evaluators: EvaluatorResult[] = [
    evaluateToolCall(trace),
    evaluateSchemaValidity(trace),
    evaluateAccuracy(trace, testCase),
  ];

  const overallPassed = evaluators.every(e => e.passed);
  const overallScore = evaluators.reduce((sum, e) => sum + e.score, 0) / evaluators.length;

  return {
    testCase,
    evaluators,
    overallPassed,
    overallScore,
  };
}
