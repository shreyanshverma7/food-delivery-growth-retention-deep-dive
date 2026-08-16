## Summary

<!-- What does this change and why? One or two sentences. -->

## Changes

<!-- Bullet the concrete changes. Mention any new file under sql/, analysis/, or streamlit_app/pages/. -->

-

## If this adds or changes an analysis

<!-- Delete this section if it doesn't apply. -->

- **What the generator implies:** <!-- Is the relationship you measured built into database/build_zomato_db.py, or independent by construction? -->
- **How the result is framed:** <!-- If the true effect is zero, the write-up should say so. See the README's "Reading these numbers honestly" section. -->

## Checklist

- [ ] Ran from the repo root, not from inside `streamlit_app/`
- [ ] Every file in `sql/` still executes against `database/zomato.db`
- [ ] `python3 -m py_compile streamlit_app/app.py streamlit_app/common.py streamlit_app/pages/*.py` passes
- [ ] `python3 analysis/statistical_tests.py` and `python3 analysis/ab_test_simulation.py` both run
- [ ] `git diff --exit-code` is clean — in particular `database/zomato.db` is unmodified (`git checkout -- database/zomato.db` if you rebuilt it)
- [ ] Did not change `random.seed(42)` — it keeps every number in the README reproducible
- [ ] No real user, customer, or payment data added anywhere
- [ ] Commit messages follow Conventional Commits
- [ ] Any number quoted in the README matches what the code actually outputs

## Related issues

<!-- e.g. Closes #12 -->
