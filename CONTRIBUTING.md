# Contributing

Thanks for taking a look. This is a product-analytics portfolio project: a synthetic food-delivery dataset, a set of SQL deliverables answering business questions, a statistical rigor pass, and a Streamlit dashboard.

Contributions are welcome — especially new SQL deliverables, additional statistical checks, and tests.

## The one rule that matters most

**Findings must be defensible against the data generator.**

The dataset is synthetic and `database/build_zomato_db.py` is in this repo, so anyone can read exactly how it was made. Order status, payment method, delivery time and city are drawn *independently*, which means the true effect in most comparisons is zero by construction. Two claims in an earlier version of this project were artifacts, and the README documents both:

- a chi-square result that cleared α=0.05 but not the Bonferroni threshold for four tests
- a cohort retention "trend" that was entirely a data-window artifact

If you add an analysis, say what the generator implies about it. A finding that contradicts the generator is a bug in the analysis, not a discovery. This is the project's whole point — see the README's *Reading these numbers honestly* section.

## Setup

See the README's [Reproduce](README.md#reproduce) section. Short version:

```bash
pip install -r requirements.txt
streamlit run streamlit_app/app.py     # run from the repo root, not streamlit_app/
```

Run from the **repo root**. `.streamlit/config.toml` lives there, and running from inside `streamlit_app/` silently loads no theme.

## Verifying your change

There is no unit-test suite yet ([contributions welcome](../../issues)). CI runs these, and so should you before opening a PR:

```bash
# the committed database must still be reproducible from the generator
tmp=$(mktemp -d); cp database/build_zomato_db.py "$tmp/"
(cd "$tmp" && python3 build_zomato_db.py)
diff <(sqlite3 "$tmp/zomato.db" .dump) <(sqlite3 database/zomato.db .dump)

# every SQL deliverable must execute
for f in sql/*.sql; do sqlite3 database/zomato.db < "$f" > /dev/null; done

# the app must compile and both analysis scripts must run
python3 -m py_compile streamlit_app/app.py streamlit_app/common.py streamlit_app/pages/*.py
python3 analysis/ab_test_simulation.py
python3 analysis/statistical_tests.py

# nothing may have dirtied the working tree
git diff --exit-code
```

Two things worth knowing:

- **`database/zomato.db` is committed on purpose** — Streamlit Cloud serves it. Rebuilding it in place produces a logically identical but byte-different file (SQLite doesn't lay pages out deterministically), so git will show it as modified. Discard that with `git checkout -- database/zomato.db`. CI compares logical dumps in a temp directory to avoid the noise.
- **Don't change the seed.** `random.seed(42)` keeps every number in the README reproducible. Changing it invalidates the whole write-up and CI will fail.

To check the dashboard renders, `streamlit run` it, or execute the pages headlessly:

```python
from streamlit.testing.v1 import AppTest
AppTest.from_file("streamlit_app/pages/1_Funnel.py").run().exception
```

## Adding a SQL deliverable

Number it in sequence (`sql/10_*.sql`). Open with a `-- Q:` line stating the business question, and comment the non-obvious SQL — window functions, self-joins, and any assumption about grain. CI runs every file in `sql/`, so it must execute cleanly against `database/zomato.db`.

If the result looks like a finding, check it against the generator before writing it up as one.

## Branches and commits

Branch off `main`; never commit to `main` directly.

| Prefix | Use |
|---|---|
| `feat/` | new functionality |
| `fix/` | bug fixes |
| `docs/` | documentation |
| `refactor/` | restructure, no behaviour change |
| `chore/` | tooling, deps, config |

[Conventional Commits](https://www.conventionalcommits.org/) for messages, with the scope being the affected area:

```
feat(sql): add restaurant-rating vs cancellation-rate deliverable
fix(dashboard): correct cohort filter on the retention page
```

## Pull requests

Open against `main`, fill in the template, and make sure CI is green. PRs are squash-merged, so one PR is one commit on `main` — keep them focused.

## Reporting bugs and ideas

Use the [issue templates](../../issues/new/choose). Starter tasks are labelled [`good first issue`](../../labels/good%20first%20issue).

## Code of Conduct

By participating you agree to the [Code of Conduct](CODE_OF_CONDUCT.md).
