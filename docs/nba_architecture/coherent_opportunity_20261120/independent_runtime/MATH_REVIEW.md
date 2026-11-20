# Shared-kernel compatibility and working-likelihood limits

Let a2,a3,aF,aT be sampled nonnegative 2PA,3PA,FTA and turnover working intensities, and p2,p3,pF the sampled conversion probabilities. The coherent interface defines

- made3 rate = a3 p3;
- non-three point rate = 2 a2 p2 + aF pF;
- point rate = 3 a3 p3 + 2 a2 p2 + aF pF;
- FT share of non-three points = aF pF / (2 a2 p2 + aF pF).

There is no independent PTS or made-three posterior. Substituting these quantities into the unchanged selector gives 3PA weight a3, 2PA weight a2, FT-series weight aF/(2+q), and turnover weight aT, where q is the model probability of a three-attempt shooting-foul series. Because its expected series length is 2+q, this recovers the declared attempted-FT intensity before any deliberate eligibility restriction. The implementation checks the inverse mapping and fails unresolved cancellation/underflow rather than clipping or drawing again. Independent tests checked 200 parameter draws and three q values per draw.

These are relative branch weights. The normalized competing-event selector, finite possession clock, lineup/exposure kernel, rebound/foul restrictions and conditioning on fixed OT count mean final game counts are not unconstrained Poisson/Gamma-Poisson or Beta-binomial draws. Conjugate Gamma/Beta identities are exact for the declared aggregate component training likelihoods, not a posterior derivation of the full chronological event-process likelihood. The empirical role prior also conditions on observed peer aggregates; it is not a claim that players or games are independent.

The unchanged event process credits every made three as three points in the same actor's path. Its independently reconstructed count identity is PTS = 2 FGM + 3PM + FTM, hence PTS >= 3*3PM in every accepted draw. Combo statistics are deterministic sums of that same points/rebounds/assists vector. Defining S4's marginal as the pushforward of this same J random object makes compatibility a property of the definition: it does not require coupling a separately fitted incompatible marginal. Public channel equality is consequently software identity, not extra independent model agreement or an independent vote.

The theoretical path law retains its continuous latent parameter distribution and nonnegative-integer population support. A finite bank is an empirical approximation, not that full support. For example, zero hits at a high count means empirical estimate zero; its Clopper-Pearson upper limit remains positive and no exact population-zero or epsilon-clipped score is admitted. Query intervals are per-query Monte Carlo intervals, with Bonferroni adjustment across the three O/U/P components; they are not simultaneous certification across every player, statistic, line, source assumption or model choice.

The finite path/event/storage execution caps can fail as a function of latent state. Whole-bank failures, partial fixed/event records and trace-resource metadata must survive, and no successful subset can be exposed as a forecast. Successful completion and software S4/J identity do not prove convergence, accurate rare tails or absence of computational selection effects. Proper source/model/code/clock admission is outside the structural query view and must be verified through the separately bound issued-artifact reader.

Unknown participation, actual legal eligibility, true zero-state probability, historical original availability and correction completeness remain unknown. The unupdated zero-state prior and sub-30-second homogeneous extrapolation are assumptions. The old S1 sensitivity grid does not validate this new family's zero sensitivity. That gate, prospective predictive validation and release remain separate and unestablished by these engineering proofs.
