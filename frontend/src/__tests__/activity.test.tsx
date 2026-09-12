import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { AgentActivity } from "../components/AgentActivity";

afterEach(() => cleanup());

describe("agent activity", () => {
  it("updates with events", () => {
    const { rerender } = render(<AgentActivity events={[]} />);
    expect(screen.getByText(/No Agent Activity Yet/)).toBeInTheDocument();
    rerender(
      <AgentActivity
        events={[
          { event: "rate_limit_reached", message: "Groq rate limit reached. CodePilot is waiting before retrying.", payload: { wait_seconds: 12 } },
          { event: "rate_limit_waiting", message: "Waiting 12 seconds before retry...", payload: { wait_seconds: 12 } },
          { event: "llm_retrying", message: "Retrying LLM request (attempt 2/3)", payload: { attempt: 2, max_attempts: 3 } },
        ]}
      />,
    );
    expect(screen.getAllByText("Rate limit reached").length).toBeGreaterThan(0);
    expect(screen.getByText("Waiting 12 seconds before retry...")).toBeInTheDocument();
    expect(screen.getByText("Retrying LLM request")).toBeInTheDocument();
    expect(screen.getByText("Attempt 2/3")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent(/Rate limited/);
  });

  it("shows recovery and exhaustion without raw JSON", () => {
    const { rerender } = render(
      <AgentActivity events={[{ event: "llm_retry_succeeded", message: "LLM request recovered" }]} />,
    );
    expect(screen.getByText("LLM request recovered")).toBeInTheDocument();
    rerender(
      <AgentActivity
        events={[
          {
            event: "rate_limit_exhausted",
            message: '{"error":{"message":"Rate limit reached","type":"tokens"}}',
          },
        ]}
      />,
    );
    expect(screen.getByText("LLM rate limit exceeded")).toBeInTheDocument();
    expect(screen.getByText("Please wait and try again.")).toBeInTheDocument();
    expect(screen.getByText("Technical details")).toBeInTheDocument();
  });
});
