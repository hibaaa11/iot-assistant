-- Start clean (removes the test rows from the simulator)
TRUNCATE mesures;

-- 21 days of data, one reading every 5 minutes, per machine and sensor
INSERT INTO mesures (temps, machine, capteur, valeur)
SELECT t, m.machine, s.capteur,
       round((s.moyenne + (random() + random() + random() - 1.5) * 2 * s.bruit)::numeric, 2)
FROM generate_series(
       date_trunc('hour', now()) - interval '21 days',
       date_trunc('hour', now()) - interval '1 hour',
       interval '5 minutes') AS t
CROSS JOIN (VALUES ('machine_1'), ('machine_2'), ('machine_3')) AS m(machine)
CROSS JOIN (VALUES ('temperature', 65.0, 2.0),
                   ('vibration',    2.0, 0.3),
                   ('courant',     12.0, 0.8)) AS s(capteur, moyenne, bruit);

-- Known events (they will become answers to your evaluation questions)
-- 1) Machine 3 overheats 3 days ago between 14:00 and 14:30
UPDATE mesures SET valeur = valeur + 27
WHERE machine = 'machine_3' AND capteur = 'temperature'
  AND temps >= (current_date - 3) + time '14:00'
  AND temps <  (current_date - 3) + time '14:30';

-- 2) Machine 1 has abnormal vibration 10 days ago between 08:00 and 09:00
UPDATE mesures SET valeur = valeur + 5
WHERE machine = 'machine_1' AND capteur = 'vibration'
  AND temps >= (current_date - 10) + time '08:00'
  AND temps <  (current_date - 10) + time '09:00';

-- 3) Machine 2 has a current spike 5 days ago between 22:00 and 22:15
UPDATE mesures SET valeur = valeur + 10
WHERE machine = 'machine_2' AND capteur = 'courant'
  AND temps >= (current_date - 5) + time '22:00'
  AND temps <  (current_date - 5) + time '22:15';