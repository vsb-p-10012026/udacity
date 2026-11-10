/**
 * Sales Opportunity Qualifier - Exercise
 *
 * TODO: Build a multi-agent system that uses specialized subagents
 * for comprehensive sales qualification.
 *
 * Learning objectives:
 * - Define programmatic subagents with AgentDefinition
 * - Implement async generator input mode (streaming pattern)
 * - Use model strings ('sonnet', 'haiku') for agent configuration
 * - Coordinate subagents with the Task tool
 * - Handle structured output from multi-agent workflows
 */

import "dotenv/config";
import { z } from "zod";
import { zodToJsonSchema } from "zod-to-json-schema";
import { query, AgentDefinition } from "@anthropic-ai/claude-agent-sdk";

// -----------------------------------------------------------------------------
// Exported Types (provided - no changes needed)
// -----------------------------------------------------------------------------

export const SalesBriefingSchema = z.object({
  companyProfile: z.object({
    name: z.string(),
    industry: z.string(),
    employeeCount: z.number(),
    estimatedRevenue: z.string(),
    techStack: z.array(z.string()),
    recentNews: z.array(z.string()),
  }),
  competitiveAnalysis: z.object({
    currentSolution: z.string(),
    ourAdvantages: z.array(z.string()),
    theirConcerns: z.array(z.string()),
  }),
  qualification: z.object({
    budget: z.object({
      hasBudget: z.boolean(),
      estimatedBudget: z.number(),
    }),
    authority: z.object({
      contactIsDecisionMaker: z.boolean(),
      decisionMakers: z.array(z.string()),
    }),
    need: z.object({
      painPoints: z.array(z.string()),
      urgency: z.enum(["high", "medium", "low"]),
    }),
    timeline: z.string(),
    dealSize: z.number(),
    winProbability: z.number().min(0).max(100),
  }),
  recommendation: z.enum(["Pursue", "Nurture", "Disqualify"]),
  talkingPoints: z.array(z.string()),
});

export type SalesBriefing = z.infer<typeof SalesBriefingSchema>;

export const SalesBriefingJSONSchema = zodToJsonSchema(SalesBriefingSchema as any, {
  $refStrategy: "root",
});

// -----------------------------------------------------------------------------
// TODO 1: Implement async generator input mode
// This is the recommended pattern for streaming compatibility
// -----------------------------------------------------------------------------

async function* generateMessages(userMessage: string) {
  yield {
    type: "user" as const,
    message: { role: "user" as const, content: userMessage },
    parent_tool_use_id: null,
    session_id: "sales-qualifier-session",
  };
}

// -----------------------------------------------------------------------------
// TODO 2: Define Subagent Definitions
// Each agent needs: description, prompt, tools, model
// Use model strings: 'sonnet', 'haiku', or 'opus'
// -----------------------------------------------------------------------------

const subagents: Record<string, AgentDefinition> = {
  // TODO: Define "company-researcher" agent
  // - description: "Research specialist that gathers company intelligence"
  // - prompt: Instructions for gathering company size, industry, tech stack, news
  // - tools: ["WebSearch"] (for web research)
  "company-researcher": {
    description: "Research specialist that gathers company intelligence", // TODO: Add description
    prompt: "You are a company research specialist. Gather accurate intelligence on the target company, including their exact name, industry, employee count, estimated revenue, current tech stack, and recent news.", // TODO: Add prompt
    tools: ["WebSearch"], // TODO: What tools does this agent need?
    model: "sonnet", // Use model string
  },

  // TODO: Define "competitive-analyzer" agent
  // - description: "Analyst that compares prospect's solution to ours"
  // - prompt: Instructions for analyzing competitive position
  // - tools: [] (no tools needed, uses provided context)
  // - model: "haiku" (simpler analysis, lower cost)
  "competitive-analyzer": {
    description: "Analyst that compares prospect's solution to ours", // TODO: Add description
    prompt: "You are a competitive intelligence analyst. Analyze the prospect's current solutions, identify our competitive advantages over them, and anticipate any potential technical or business concerns/objections they might have.",  // TODO: Add prompt
    tools: [], // No tools needed
    model: "haiku",
  },

  // TODO: Define "qualification-scorer" agent
  // - description: "Scorer that assesses BANT criteria and deal probability"
  // - prompt: Instructions for BANT assessment (Budget, Authority, Need, Timeline)
  // - tools: [] (no tools needed)
  // - model: "haiku"
  "qualification-scorer": {
    description: "Scorer that assesses BANT criteria and deal probability", // TODO: Add description
    prompt: "You are a sales qualification scorer. Assess BANT criteria (Budget, Authority, Need, Timeline), calculate estimated deal size, determine win probability percentage (0-100), and formulate a clear recommendation (Pursue, Nurture, or Disqualify).", // TODO: Add prompt
    tools: [],
    model: "haiku",
  },
};

// -----------------------------------------------------------------------------
// Main Function
// -----------------------------------------------------------------------------

export interface ContactInfo {
  name: string;
  title: string;
  email: string;
}

export async function qualifyOpportunity(
  companyName: string,
  contactInfo: ContactInfo
): Promise<SalesBriefing> {
  const orchestratorPrompt = `You are a sales intelligence orchestrator coordinating specialized subagents.

You have access to three subagents via the Task tool:
- company-researcher: Gathers company intelligence
- competitive-analyzer: Analyzes competitive position
- qualification-scorer: Assesses BANT and calculates deal metrics

PROSPECT: ${companyName}
CONTACT: ${contactInfo.name}, ${contactInfo.title} (${contactInfo.email})

WORKFLOW:
1. Use company-researcher to research the company
2. Use competitive-analyzer to analyze their competitive position
3. Use qualification-scorer to assess BANT and calculate deal probability

After all agents complete, compile a comprehensive sales briefing with:
- Company profile
- Competitive analysis
- BANT qualification scores
- Deal size and win probability
- Recommendation (Pursue/Nurture/Disqualify)
- 3-4 talking points for the sales rep

Return the briefing as structured JSON.`;

  // TODO 3: Call the query function with:
  // - prompt: Use the async generator (generateMessages)
  // - options:
  //   - allowedTools: ["Task"]
  //   - agents: subagents
  //   - model: "sonnet" (use string, not env var)
  //   - outputFormat: { type: "json_schema", schema: SalesBriefingJSONSchema }
  //   - maxTurns: 15
  //
  // TODO 4: Handle the message stream:
  // - Log Task tool invocations (when block.type === "tool_use" && block.name === "Task")
  // - Return SalesBriefingSchema.parse(message.structured_output) when result is success
  for await (const message of query({
    prompt: generateMessages(orchestratorPrompt),
    options: {
      model: "sonnet",
      allowedTools: ["Task"],
      agents: subagents,
      maxTurns: 15,
      outputFormat: {
        type: "json_schema",
        schema: SalesBriefingJSONSchema as Record<string, unknown>,
      },
    },
  })) {
    const msg = message as any;

    if (msg.type === "assistant") {
      const content = msg.message?.content || [];
      for (const block of content) {
        if (block.type === "tool_use" && block.name === "Task") {
          console.log(`[Subagent Task]:`, JSON.stringify(block.input));
        }
      }
    } else if (msg.type === "result" && msg.subtype === "success") {
      if (msg.structured_output) {
        return SalesBriefingSchema.parse(msg.structured_output);
      }
    }
  }
  throw new Error("TODO: Implement qualifyOpportunity using query() with subagents");
}
