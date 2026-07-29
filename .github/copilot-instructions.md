# fplan

Early-retirement financial planner that uses linear programming (via
`scipy.optimize.linprog`) to find a spending/withdrawal schedule across
after-tax savings, IRA, and Roth accounts that maximizes minimum yearly
spend (and, as a side effect, minimizes taxes).

## Running

```sh
uv run src/fplan.py examples/sample.toml   # run the module directly
uv run fplan examples/sample.toml          # equivalent, via the installed console script
```

Config files are TOML; see `examples/sample.toml` for the format. Real
per-person plans (e.g. `scott.toml`, `nathan.toml`) live at the repo root for
the maintainer's personal use — don't treat them as examples to edit.

## Testing and linting

`pytest` and `ruff` are dev dependencies (see `[dependency-groups]` in
`pyproject.toml`), so `uv run` picks them up automatically:

```sh
uv run pytest -q                                                          # full suite
uv run pytest test/fplan/test_solve/test_sample_solve.py::test_flat_solve # single test
uv run ruff check .
uv run ruff format .
```

The `test/` tree imports the project as `from fplan import ...` — this
works because `pyproject.toml` declares `fplan` as a single top-level
module (`py-modules = ["fplan"]` under `[tool.setuptools]`, sourced from
`src/fplan.py`) and `uv run`/`uv sync` install it editable automatically.

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
     amount, plus two scalars (`GOAL`, `SEPP`) at the front. Columns are
     named rather than hand-indexed: `Field` is an `IntEnum`
     (`SAVINGS`/`IRA`/`ROTH`/`IRA2ROTH`/`DEPOSIT`) giving the offset
     within a year's block, and `Vars(S)` exposes `V.work(year, Field.X)`
     / `V.retire(year, Field.X)` to get the column number for a
     work-year/retirement-year variable, and `V.row()` for a fresh
     zeroed constraint row — use these instead of reintroducing raw
     `n0 + vper * year + k` arithmetic when adding constraints.
   - Constraints (`A`, `b` rows) encode contribution limits, tax-bracket
     piecewise-linearization (one row per bracket per year, since linprog
     needs linear constraints for a progressive tax table), capital-gains
     basis erosion, RMDs (`RMD` table), the 59½ penalty, and optional SEPP
     72(t) withdrawals.
   - `c` is the objective (maximize the "goal" spend variable, i.e.
     `c[GOAL] = -1` since linprog minimizes).
   - Variables default to `(0, None)` bounds. The "deposit" slot
     (`Field.DEPOSIT`) of each retirement year's block lets that year's
     surplus income (e.g. a one-time house sale) be banked into savings
     instead of being
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
