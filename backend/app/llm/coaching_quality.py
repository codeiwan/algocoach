"""Shared evidence standard for AlgoCoach's static coaching outputs.

This rubric improves the instructions supplied to the LLM.
It does not constitute execution, formal verification,
or a correctness guarantee.
"""

COACHING_QUALITY_INSTRUCTIONS = """
Evidence-first correctness review (apply to every candidate issue):

1. Interpret the exact problem contract and its constraints before
   judging the implemented algorithm. Respect the platform's
   function signature.

2. Distinguish an unusual implementation from an incorrect
   implementation. Different but mathematically equivalent
   representations are valid.

3. Before claiming a logic error, look for one of these forms
   of support:
   (a) an admissible concrete input with a reasoned expected
       result and a different result that necessarily follows
       from the supplied code; or
   (b) a concise mathematical/invariant argument showing why
       the code fails.
   If you cannot justify either form, do NOT output a logic
   issue. You may suggest an optional manual check without
   presenting it as a code defect.

4. For complexity or constraints, identify the specific
   asymptotic bound, numeric limit, or input condition that
   could cause a violation. A vague worry without a bound
   or condition is not an issue.

5. Check your proposed counterexample and proof against the
   actual code, including tie-breaking, data types, loops,
   and the returned value.
   Do not invent an observed runtime result: this review
   is static reasoning.

6. In particular, a permutation written as
   sorted-position -> original-position is the inverse of
   original-position -> sorted-position.
   Both mappings have the same disjoint-cycle lengths.
   Therefore, calculating minimum arbitrary swaps as
   n minus the cycle count is valid in either direction.
   Reversing this mapping is NOT itself a bug.
   This property does not excuse unrelated incorrect
   permutation construction or updates.

7. Incomplete expressions during live typing are not bugs
   by themselves. Consider only stable, implemented behavior.

8. Use CRITICAL only for a demonstrable substantial
   correctness problem.
   Use WARNING only for a concrete, actionable risk
   supported by code and input constraints.
   INFO must not imply an unproven correctness failure.

9. If no supported issue survives your scrutiny,
   leave issues/findings empty and state what is actually
   supported. Never guarantee judge acceptance.

10. Praise meaningful sound logic when justified.
    Do not invent tests, proofs, validation steps,
    or execution you did not perform.

For each reported issue/finding, the description should
identify the failure mode, and evidence should give the
specific code behavior plus the witness input or reasoning,
when applicable.

Avoid hedged claims presented as defects
(e.g., 'mapping direction might be wrong' without
checking equivalence).

This policy applies equally to ongoing code analysis
and submission review.
""".strip()
