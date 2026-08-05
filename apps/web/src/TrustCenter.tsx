import type { EngineeringCase } from "./engineeringTypes";

type Props = {
  engineeringCase: EngineeringCase;
  compact?: boolean;
};

function pretty(value: string): string {
  return value.replaceAll("_", " ").replace(/\b\w/g, (match) => match.toUpperCase());
}

export function TrustCenter({ engineeringCase, compact = false }: Props) {
  const trust = engineeringCase.trust_assessment;
  const gate = engineeringCase.decision_gate;

  return (
    <section className={`trust-center ${compact ? "compact" : ""}`}>
      <div className={`decision-gate gate-${gate.decision}`}>
        <div>
          <small>ENGINEERING DECISION GATE</small>
          <strong>{pretty(gate.decision)}</strong>
          <span>{gate.reason}</span>
        </div>
        <div><small>PRODUCTION CHANGE</small><strong>{gate.production_change_authorised ? "AUTHORISED" : "NOT AUTHORISED"}</strong></div>
        <div><small>CONTROLLED PILOT</small><strong>{gate.pilot_authorised ? "ELIGIBLE" : "ON HOLD"}</strong></div>
      </div>

      <section className="trust-score-grid">
        <div><small>EARNED CONFIDENCE</small><strong>{trust.overall_confidence_percent.toFixed(1)}%</strong><span>{trust.confidence_band.toUpperCase()}</span></div>
        <div><small>EVIDENCE COVERAGE</small><strong>{trust.evidence_coverage_percent.toFixed(1)}%</strong><span>{trust.evidence_register.length} record(s)</span></div>
        <div><small>DATA COMPLETENESS</small><strong>{trust.data_completeness_percent.toFixed(1)}%</strong><span>{trust.unknown_inputs.length} unresolved input(s)</span></div>
        <div><small>TRACEABILITY</small><strong>{trust.traceability_percent.toFixed(1)}%</strong><span>Equations, sources and validations</span></div>
        <div><small>VALIDATION READINESS</small><strong>{trust.validation_readiness_percent.toFixed(1)}%</strong><span>{trust.validation_plan.filter((item) => item.blocking).length} blocking test(s)</span></div>
      </section>

      <div className="trust-question-grid">
        {trust.trust_questions.map((item) => (
          <article className={`trust-question status-${item.status}`} key={item.question}>
            <small>{item.status.toUpperCase()}</small>
            <strong>{item.question}</strong>
            <p>{item.answer}</p>
          </article>
        ))}
      </div>

      {!compact && (
        <>
          <details open>
            <summary>MULTIDISCIPLINARY ENGINEERING REVIEW</summary>
            <div className="table-responsive">
              <table>
                <thead><tr><th>Discipline</th><th>Status</th><th>Findings</th><th>Blocking issues</th><th>Approval owner</th></tr></thead>
                <tbody>
                  {trust.review_committee.map((item) => (
                    <tr key={item.discipline}>
                      <td>{pretty(item.discipline)}</td>
                      <td><span className={`review-status review-${item.status}`}>{item.status.toUpperCase()}</span></td>
                      <td>{item.findings.join(" · ")}</td>
                      <td>{item.blocking_issues.join(" · ") || "None declared"}</td>
                      <td>{item.approval_required_from}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>

          <details>
            <summary>VALIDATION MATRIX</summary>
            <div className="table-responsive">
              <table>
                <thead><tr><th>Measurement</th><th>Purpose</th><th>Owner</th><th>Availability</th><th>Blocking</th></tr></thead>
                <tbody>
                  {trust.validation_plan.map((item) => (
                    <tr key={item.validation_id}>
                      <td>{item.measurement}</td>
                      <td>{item.purpose}</td>
                      <td>{item.owner}</td>
                      <td>{pretty(item.availability)}</td>
                      <td>{item.blocking ? "YES" : "NO"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>

          <details>
            <summary>RISK REGISTER / ROLLBACK</summary>
            <div className="table-responsive">
              <table>
                <thead><tr><th>Discipline</th><th>Failure mode</th><th>RPN</th><th>Mitigation</th><th>Rollback trigger</th></tr></thead>
                <tbody>
                  {trust.risk_register.map((item) => (
                    <tr key={item.failure_mode_id}>
                      <td>{pretty(item.discipline)}</td>
                      <td>{item.failure_mode}</td>
                      <td>{item.risk_priority_number}</td>
                      <td>{item.mitigation}</td>
                      <td>{item.rollback_trigger}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>

          <details>
            <summary>WHY EACH SCENARIO EXISTS</summary>
            <div className="scenario-rationale-grid">
              {trust.scenario_assessments.map((item) => (
                <article key={item.scenario_id}>
                  <small>#{item.rank} · {item.risk_level.toUpperCase()} RISK · {item.probability_of_success_percent.toFixed(1)}% SCREENING SUCCESS</small>
                  <strong>{item.name}</strong>
                  <p>{item.why_it_exists}</p>
                  <p><b>Benefit:</b> {item.expected_benefit.join(" · ")}</p>
                  <p><b>Downside:</b> {item.expected_downside.join(" · ")}</p>
                  <p><b>Validation:</b> {item.required_validation.join(" · ")}</p>
                </article>
              ))}
            </div>
          </details>

          {gate.blocking_conditions.length > 0 && (
            <div className="gate-blockers">
              <strong>BLOCKING CONDITIONS</strong>
              <ol>{gate.blocking_conditions.map((item) => <li key={item}>{item}</li>)}</ol>
            </div>
          )}
        </>
      )}
    </section>
  );
}
