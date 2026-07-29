# fplan

Early-retirement financial planner that uses linear programming (via
`scipy.optimize.linprog`) to find a spending/withdrawal schedule across
after-tax savings, IRA, and Roth accounts that maximizes minimum yearly
spend (and, as a side effect, minimizes taxes).

## Running

```sh
uv run src/fplan.py examples/sample.toml
```

`uv run fplan` (the console-script entry point) does **not** currently work
because `pyproject.toml` has no `[project.scripts]` entry — always invoke
`src/fplan.py` directly. Config files are TOML; see `examples/sample.toml`
for the format. Real per-person plans (e.g. `scott.toml`, `nathan.toml`) live
at the repo root for the maintainer's personal use — don't treat them as
examples to edit.

## Testing and linting

Neither `pytest` nor `ruff` are project dependencies, so run them with `uvx`:

```sh
uvx --with-editable . pytest -q                       # full suite
uvx --with-editable . pytest test/fplan/test_solve/test_sample_solve.py::test_flat_solve  # single test
uvx ruff check src/fplan.py
uvx ruff format src/fplan.py
```

**Known issue:** the tests under `test/fplan/` import `from src.fplan.fplan
import ...` (a `src/fplan/fplan.py` package layout), but the actual source
lives at `src/fplan.py`. This mismatch currently breaks test collection on
`master` — it's a pre-existing issue, not something introduced by your
change, so don't feel obligated to fix it unless that's the task at hand.

## Architecture (`src/fplan.py`, single-file program)

The whole program is one file with three phases:

1. **`Data.load_file` / `parse_expenses`** — parses the TOML config into a
   `Data` object: tax brackets (`taxrates`), account balances/limits
   (`aftertax`, `IRA`, `roth` dicts with `bal`/`basis`/`maxcontrib`),
   inflation/return rates (`i_rate`, `r_rate`), age range (`startage`,
   `retireage`, `endage`), and per-year `income`/`expenses`/`taxed` arrays
   built from `[[income]]`/`[[expense]]` TOML tables via `agelist()`.
2. **`solve(S, sepp, verbose)`** — builds and solves a single large LP:
   - One flat variable vector encodes, per work-year and per retirement
     year, a fixed-size block (`vper` variables per year) of unknowns:
     savings withdrawal, IRA withdrawal, Roth withdrawal, IRA→Roth
     conversion, and (retirement years only) a deposit-into-savings
     amount. `n0`/`n1`/`vper` are the offsets/stride into this vector —
     read them together with the comments in `solve()` before changing
     the variable layout, since every constraint row indexes into it by
     hand (`row[n0 + vper * year + k] = ...`).
   - Constraints (`A`, `b` rows) encode contribution limits, tax-bracket
     piecewise-linearization (one row per bracket per year, since linprog
     needs linear constraints for a progressive tax table), capital-gains
     basis erosion, RMDs (`RMD` table), the 59½ penalty, and optional SEPP
     72(t) withdrawals.
   - `c` is the objective (maximize the "goal" spend variable, i.e.
     `c[0] = -1` since linprog minimizes).
   - Variables default to `(0, None)` bounds. The "deposit" slot (index
     +4) of each retirement year's block lets that year's surplus income
     (e.g. a one-time house sale) be banked into savings instead of being
     forced to spend it all, so it can be withdrawn (and taxed normally
     as a capital gain, via the withdrawal slot) in a later year. It is
     capped at `(0, income[year])` so it can't be used as an unbacked
     source of money, and it is a separate variable from the withdrawal
     slot (rather than letting the withdrawal go negative) precisely so
     depositing money never produces a negative capital-gains tax. A
     per-year constraint keeps the running savings balance non-negative
     in every year (not just at the end) so a deposit can't be spent
     before it's actually received.
3. **`print_ascii` / `print_csv`** — format the solved variable vector back
   into the yearly table described in `README.md` (save/send/IRA/fIRA/
   Roth/fRoth/IRA2R/rate/tax/spend/extra columns).

When adding a new kind of withdrawal/contribution/tax rule, it almost always
means: add a slot to the per-year variable block, add matching `A`/`b`
constraint rows for every affected year, and update both printers.

## Conventions

- Rates in TOML/`Data` are stored as multipliers (e.g. `1.021` for 2.1%
  inflation), not raw percentages — see the `standardize on using
  percentages not decimals` history for why this matters when reading
  values like `taxrates`.
- Dollar amounts in TOML are whole dollars; the printed tables show
  thousands (see README "Output" section for column meanings).
- Federal tax tables are only for Married Filing Jointly; RMD table (`RMD`
  list) starts at age 73 and is updated periodically — check the comment
  above it for the last-updated year before assuming it's current.
