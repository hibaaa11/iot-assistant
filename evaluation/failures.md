# Failure analysis (text-to-SQL, llama3.2:3b)

## Failure 1: date copied from the prompt
Question: maximum temperature of machine_3 on 2026-11-20.
SQL produced: temps >= '2026-11-20 21:00' AND temps < '2026-11-21 21:00'
Problem: the model copied the hour from the "data range" line of the prompt, which shifted the day window.
Fix: removed hours from the prompt and added a rule "filter with the date only".

## Failure 2: missing upper bound
Same question.
SQL produced: temps >= '2026-11-20' (no upper bound).
Problem: the filter covered several days. The answer was right only by chance.
Fix: single-condition rule DATE(temps) = 'YYYY-MM-DD' in the prompt and examples.
Check: question about 2026-11-19 now returns 69.59, not 95.87.

## Environment problem: wrong database reached
Python connected to a Windows PostgreSQL on port 5432 instead of the Docker one,
which produced an undecodable French error message.
Fix: Docker database published on port 5433.

## Failure 3: correct SQL, wrong sentence
Question: which machine had the highest vibration over the whole period?
SQL: correct (returns machine_1, 7.5).
Answer given: "There is only one machine with vibration data provided..."
Problem: the model saw a single row (LIMIT 1) and commented on it instead of reporting it.
Fix: the explanation prompt now says the rows are the final answer, includes the SQL, and asks to quote names and values.
Lesson: SQL accuracy and answer accuracy must be measured separately.

## Failure 4: missing aggregate
Question: what was the peak courant of machine_2 on 2026-11-18?
SQL produced: SELECT valeur ... (no MAX), returning up to 100 raw readings.
Answer given: 13.61 (an arbitrary reading). Correct value: about 23.0.
Problem: the model ignored the rule "peak means MAX" because no example used it.
Fix: stricter rule (one-value questions must use an aggregate) and an example with "peak".
Lesson: examples in the prompt influence a small model more than rules do.