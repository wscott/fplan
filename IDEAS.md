# Future ideas

This document tracks retirement-planning features that `fplan` doesn't
model yet, roughly in order of likely dollar impact. For each idea:

1. **Modeling changes** — what has to change in `Data`/`solve()` (new
   variables, new constraints, new solver approach if LP no longer fits).
2. **Output changes** — what the ASCII/CSV tables need to show so the
   user can act on the result (e.g. "start SS at age 70").
3. **Input changes** — what the user provides in the `.toml` file.

None of this is committed to; it's a backlog of ideas to evaluate
individually, and some may turn out to be bad fits for a linear program
(see the "solver approach" notes below) and need a different tool or a
post-processing heuristic instead.

## 1. Social Security taxation (up to 85% taxable) and claiming-age choice

Currently Social Security is just a generic `[income.*]` block with a
flat `tax = true/false` flag — it's taxed at 100% of ordinary rates if
`tax = true`, or ignored entirely if not. The real rule (up to 85% of
benefits taxable, based on "combined income" = AGI + tax-exempt interest
+ half of SS) isn't modeled, and neither is the age-62-vs-70 claiming
tradeoff.

1. **Modeling changes**
   - Add a dedicated `SS` income stream (distinct from generic
     `income[]`) with its own array, separate from `S.taxed`.
   - The 0%/50%/85% thresholds depend on "combined income," which itself
     depends on other income (IRA withdrawals, taxable interest) in the
     same year — this is a *piecewise* function of a variable, same
     technique already used for the federal tax brackets (one row per
     threshold/"cut", linearized). Add a second bracket-style constraint
     block computing `taxable_ss` similarly to how `taxrates` cuts are
     handled, then feed `taxable_ss` into the existing ordinary-income
     tax rows instead of the raw SS amount.
   - If claiming age becomes a *decision* (not fixed input), that's no
     longer linear: benefit amount depends nonlinearly (actuarially) on
     the chosen start age, and it's a single per-person integer choice,
     not a per-year continuous variable. Simplest LP-compatible approach:
     let the user fix the claiming age in the config (as today) and just
     fix the taxability math; if we want fplan to *choose* the claiming
     age, that requires an outer loop that calls `solve()` once per
     candidate claiming age (e.g. ages 62–70) and picks the best result
     — not a single LP.
   - New "variables": none needed if claiming age stays an input; if
     fplan chooses it, no new LP variables, just N solver invocations
     compared by achieved `GOAL`.

2. **Output changes**
   - Show taxable vs. total SS per year in the yearly table (a `ssTax`
     or `%taxed` column) so the user can see when they cross into the
     85%-taxable zone.
   - If claiming age is chosen automatically: print the chosen age and
     the achievable `GOAL` for each candidate age considered, so the user
     can see the tradeoff (e.g. "claiming at 62: $118k/yr; at 67: $124k/yr;
     at 70: $126k/yr — age 70 selected").

3. **Input changes**
   - Add a first-class `[social_security]` table, e.g.:
     ```toml
     [social_security]
     person1_pia = 2800      # monthly benefit at full retirement age
     person1_fra = 67
     person1_claim_age = 70  # or omit/"optimize" to let fplan search
     person2_pia = 1400
     person2_fra = 67
     person2_claim_age = 65
     ```
   - Keep backward compatibility: existing `[income.*]` blocks with
     `tax = true` continue to work as fully-taxed generic income for
     anyone who doesn't want the detailed SS model.

## 2. IRMAA (Medicare Part B/D premium surcharges)

IRMAA adds Medicare premium surcharges in discrete income brackets (MAGI
from **2 years prior**), and can make a large Roth conversion cost more
in premiums than it saves in tax.

1. **Modeling changes**
   - IRMAA brackets are a step function of MAGI, with a 2-year lookback —
     this needs MAGI computed per year (already implicitly available as
     `inc` in `print_ascii`, but not currently carried as a formal
     constraint output) and then applied as a *penalty* two years later.
   - A step function (surcharge jumps at cliffs, doesn't taper linearly)
     is inherently non-convex/non-linear for a minimization — LP can only
     directly encode convex piecewise-linear costs (like the tax brackets,
     which are convex increasing). IRMAA is a step, not a slope, so it
     can't be added as a smooth constraint row the way tax brackets are.
     Options: (a) approximate by adding a steep-but-continuous linear
     penalty for MAGI above each threshold (approximation, may distort
     results near cliffs), or (b) treat it outside the LP: solve
     normally, then in `print_ascii`/a post-pass, compute actual IRMAA
     tiers hit per year and warn/report them, without feeding them back
     into the optimization. (b) is much simpler and avoids a
     mixed-integer program (MIP), which `scipy.optimize.linprog` does not
     support.
   - If we do want the optimizer itself to avoid IRMAA cliffs, that
     requires binary "which tier" indicator variables per year — a
     genuine MIP, needing a different solver (e.g. `scipy.optimize.milp`,
     or PuLP/OR-tools) rather than `linprog`.

2. **Output changes**
   - Add an `IRMAA` column (or footnote) showing the estimated annual
     Medicare surcharge for each year and which tier it's in, plus a
     total lifetime IRMAA line next to `total tax`.
   - If a year's MAGI is just above a cliff, flag it (e.g. `*` marker)
     so the user can see "reducing income by $X this year avoids $Y/yr
     in surcharges."

3. **Input changes**
   - `[medicare]` table with each person's Medicare start age (65,
     or later if still working) and current-year IRMAA bracket table
     (since it's federally published and changes yearly/with inflation),
     e.g.:
     ```toml
     [medicare]
     person1_start_age = 65
     person2_start_age = 65
     # optional override of default IRMAA brackets/surcharges
     ```

## 3. Net Investment Income Tax (NIIT, 3.8%)

3.8% surtax on the lesser of net investment income or MAGI over
$250k (MFJ, not inflation-indexed by law).

1. **Modeling changes**
   - This is a simple additional *linear* bracket cut at a fixed
     threshold applied to (capital gains + IRA-ish investment income) —
     fits naturally as one more row in the existing tax-bracket
     constraint loop, analogous to how `state_tax` is added to `rate`.
     Since NIIT applies to a different tax base than the ordinary IRA
     rate (investment income only, not IRA withdrawals themselves,
     though IRA withdrawals raise MAGI which decides whether NIIT
     applies at all), it likely needs its own small bracket-style
     constraint row (one cut at $250k) analogous to the SS taxability
     piecewise construction above, rather than folding into `rate`
     directly.
   - No new LP variables — reuses `SAVINGS` (capital gains) and the
     MAGI-like combined income figure.

2. **Output changes**
   - Optionally fold into the `tax` column, or break out a `niit`
     column if the user wants visibility into why capital-gains timing
     shifted.

3. **Input changes**
   - A fixed constant, so probably just a `[taxes] niit_threshold`
     and `niit_rate` override (defaults 250000 / 3.8) for future-proofing
     against law changes, not per-user data.

## 4. Surviving-spouse ("widow's penalty") transition

When one spouse dies, filing status flips from MFJ to Single —
smaller standard deduction, narrower brackets — often the single
biggest lifetime tax hit for a couple, and current code has no concept
of two individual lifespans at all (only one "household").

1. **Modeling changes**
   - Requires tracking two people's ages/death years separately, and a
     year at which the tax table/`stded` switches from MFJ to Single
     defaults. This is a *structural* change: today `S.taxrates`/`S.stded`
     are single scalars for the whole plan; they'd need to become
     year-dependent (already partially true via `i_mul` scaling, so this
     is a matter of also switching the underlying table at the
     transition year, not a new solver paradigm).
   - Everything downstream (the tax bracket constraint loop) already
     iterates year-by-year, so this is additive: at the configured
     death year, switch to the Single `default_taxrates`/`stded` (and,
     realistically, potentially a change in expenses to reflect one
     person's reduced spending, if the user wants to model that).
   - No new LP variables, no new solver approach — just year-dependent
     tax tables instead of one fixed table for the whole plan.

2. **Output changes**
   - Mark the transition year clearly in the yearly table (e.g. a
     `status` column showing `MFJ`/`Single`, or a printed divider line),
     since the tax rate/bracket will visibly jump there and the user
     should understand why.

3. **Input changes**
   - Add e.g. `second_death_age = 90` (age of the *first-to-die* spouse,
     relative to `startage`), and optionally a `single_taxrates`/
     `single_stded` override table (defaulting to the built-in Single
     table already sketched out, commented, in `examples/sample.toml`).
     If unset, behavior is unchanged (always MFJ) for backward
     compatibility.

## 5. Qualified Charitable Distributions (QCDs)

Direct IRA-to-charity transfers (up to an annual IRS cap, currently
$105k/person, inflation-indexed) count toward RMDs but are excluded
from taxable income entirely — a way to zero out tax on RMD money the
user intends to donate anyway.

1. **Modeling changes**
   - Add a new per-retirement-year `Field.QCD` variable: an IRA
     withdrawal that (a) reduces the IRA balance exactly like
     `Field.IRA`, (b) counts toward satisfying that year's RMD
     requirement, but (c) is *not* included in the ordinary-income tax
     row and (d) is *not* available to fund `GOAL`/spending (it goes
     straight to charity, not to the user).
   - Constraint changes: in the RMD constraint row, `QCD` counts
     alongside `IRA` when checking the RMD floor is met. In the IRA
     final-balance constraint, `QCD` reduces the balance just like
     `IRA`. In the tax-bracket constraint row, `QCD` gets **no**
     coefficient (doesn't add to taxable income, doesn't add to
     spendable goal) — effectively a "free" RMD-satisfying withdrawal
     up to the user's desired annual giving amount.
   - Needs an upper bound per year (the QCD annual cap, inflation
     adjusted) via `bounds[V.retire(year, Field.QCD)] = (0, cap*i_mul)`.
   - If the user wants QCDs "used automatically to the extent
     beneficial," the objective just needs no penalty on QCD (or a small
     negative tie-break to prefer it over taxed IRA withdrawals when RMDs
     must be satisfied anyway) — fits directly into the existing LP, no
     new solver approach.

2. **Output changes**
   - Add a `QCD` column to the yearly table alongside `fIRA`, and a
     lifetime-total QCD/charitable-giving line near `total tax`.

3. **Input changes**
   - `[charity] qcd_annual = 20000` (desired/allowed annual QCD amount,
     or omit to disable) and optionally `qcd_start_age = 70.5` (QCDs are
     allowed starting at 70½, independent of RMD age 73).

## 6. Sequence-of-returns / market risk (Monte Carlo)

The model uses one fixed `returns` rate for all years — it optimizes a
single deterministic path and says nothing about risk if real returns
vary (especially a bad sequence early in retirement).

1. **Modeling changes**
   - This is the one idea that doesn't fit into the LP at all: `linprog`
     needs one fixed, known return-rate coefficient per year to build
     `A`/`b`. Modeling *uncertainty* means running many trials, not
     adding rows/columns to one LP.
   - Simplest approach: keep `solve()` exactly as-is (it already takes
     `S.r_rate` as an input), and add an outer Monte Carlo driver that:
     samples a random sequence of yearly returns (e.g. from a
     lognormal distribution fit to historical market data, or a
     resampled historical-returns bootstrap), reruns `solve()` (or,
     better, a variant that takes a fixed withdrawal *policy* derived
     from the base-case solve rather than re-optimizing with hindsight
     each trial — otherwise the LP "cheats" by seeing future returns it
     wouldn't really know), and aggregates success/failure across trials.
   - This is a substantially different mode of using the tool (a
     wrapper script/new subcommand `fplan --monte-carlo`, not a change to
     `solve()`'s constraints) — worth calling out as the biggest
     architecture departure of anything on this list.

2. **Output changes**
   - A new report entirely: e.g. "target spend achieved in 87% of 1000
     simulated return sequences" (success probability), a percentile
     spread of ending balances, or a chart-like ASCII histogram. Not a
     modification of the existing per-year table.

3. **Input changes**
   - `[monte_carlo] trials = 1000`, `return_stddev = 12` (percent),
     or `historical_returns = "sp500"` to pick a bootstrap dataset,
     plus a CLI flag (`--monte-carlo`) to opt in (default stays the
     single fixed-rate deterministic solve, since that's a legitimate,
     much faster/simpler planning mode many users will still want).

## 7. Dividends/interest on taxable (aftertax) balances

Aftertax account balance growth (`S.r_rate`) is currently treated as
pure unrealized appreciation taxed only on withdrawal via the capital
gains/basis mechanism — real brokerage accounts also throw off
dividends/interest taxed annually (often as ordinary income or
qualified-dividend rates) whether or not anything is withdrawn.

1. **Modeling changes**
   - Add a `S.aftertax["dividend_yield"]` fraction of the running
     balance that's taxed as ordinary/qualified income every year
     regardless of withdrawals. Since the running aftertax balance is
     already a linear function of prior `SAVINGS`/`DEPOSIT` variables
     (used in the per-year floor constraint), the dividend tax owed
     each year is also linear in those same variables — so this can be
     added as extra terms in the existing tax-bracket constraint row
     (a new coefficient block referencing all prior years' `SAVINGS`/
     `DEPOSIT`, similar in structure to the existing savings-floor
     constraint), not a new solver approach.
   - Also erodes/increases `basis` differently (qualified dividends
     that are reinvested increase basis) — a secondary, smaller
     correction to the existing `basis` ratio computation.

2. **Output changes**
   - Could remain invisible (folded into `tax`), or add a `div`
     column if the user wants to see it broken out from capital-gains
     tax on withdrawals.

3. **Input changes**
   - `[aftertax] dividend_yield = 2.0` (percent of balance, annual,
     defaulting to 0 for backward compatibility = today's behavior).

## 8. Asset location optimization

Currently `returns`/`r_rate` is one global rate applied identically to
savings, IRA, and Roth — real portfolios often deliberately hold
higher-growth assets in Roth (tax-free growth) and lower-growth/bond
assets in taxable/IRA, and fplan can't express or discover that
tradeoff.

1. **Modeling changes**
   - Give each account its own return rate
     (`S.aftertax["r_rate"]`/`S.IRA["r_rate"]`/`S.roth["r_rate"]`,
     defaulting to the existing global `S.r_rate`), which only requires
     substituting per-account rates into the existing balance-projection
     formulas (`S.r_rate ** ...`) — no new variables/constraints, since
     the accounts' growth already appears only as fixed exponents, not
     unknowns.
   - If instead we want fplan to *choose* which assets go where (a real
     allocation decision, e.g. "put the stock allocation in Roth"), that
     becomes a genuinely different, larger model (need to split each
     account's balance by asset class and add rebalancing constraints)
     — a bigger project, likely out of scope for this LP entirely and
     probably a separate tool.

2. **Output changes**
   - No change if just fixed differing rates per account (already
     reflected implicitly in the existing balance columns). If fplan
     ever picks an allocation, would need new columns showing asset mix
     per account per year.

3. **Input changes**
   - `[aftertax] returns = 5`, `[IRA] returns = 6`, `[roth] returns = 8`
     (each optional, defaulting to the top-level `returns`).

## 9. Future tax-law changes (e.g. scheduled bracket sunsets)

Federal brackets are a single fixed table for the whole plan; real law
already has scheduled changes (e.g. the 2017 TCJA individual provisions
reverting after 2025) that a decades-long retirement plan will cross.

1. **Modeling changes**
   - Same structural shape as the widow's-penalty idea: make
     `S.taxrates`/`S.stded` a function of year rather than a constant,
     selecting between two (or more) built-in tables at a configured
     transition year. No new LP variables/solver approach — the tax
     bracket constraint loop already iterates per-year and just needs to
     look up a per-year table instead of one fixed table.

2. **Output changes**
   - Optional marker in the yearly table at the transition year (same
     mechanism as widow's-penalty transition marker), so a rate jump is
     self-explanatory rather than looking like a bug.

3. **Input changes**
   - `[taxes] sunset_year = 2026`, `post_sunset_taxrates = [...]`,
     `post_sunset_stded = ...` (optional; defaults to no change, i.e.
     today's single-fixed-table behavior).
