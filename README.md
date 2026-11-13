# Team 18 - Phase 4: TAKA

Team 18's Phase 4 application implements the assigned Speedrun Leaderboard mini-world. The assigned source is Team 14's Phase 2 EER model and Team 5's Phase 3 relational mapping from the Questions Phase 4 folder. That assigned Team 5 report is included unchanged as `phase3.pdf`.

The current site models selected public [Speedrun.com](https://www.speedrun.com/) game pages. Its population snapshot came from the [official public API](https://github.com/speedruncomorg/api/blob/master/version1/README.md) on 13 November 2026. It includes three games (Super Mario 64, Celeste, Super Mario Bros.), their categories and levels, and up to 200 API results per category before validation and evidence filtering. The current import contains 4,678 runs on 509 distinct boards. `src/source_data.json` retains the downloaded records, source URLs, and variable labels. To refresh it, run `fetch_source.py` followed by `fetch_variables.py` from `src/`; neither is necessary for normal setup.

## Stack

- Relational DBMS: MySQL 8.0 or later (tested SQL targets MySQL 8 syntax)
- Backend and frontend: Python 3, Flask, server-rendered HTML/CSS
- Database driver: PyMySQL; all dynamic native SQL queries use bound parameters

## Setup

From the `src/` directory:

1. Create the schema: `mysql -u root -p -e "source schema.sql"`.
2. Install Python packages: `pip install -r requirements.txt`.
3. Set `DB_HOST`, `DB_PORT`, `DB_USER`, and `DB_PASSWORD` for your local MySQL server. The defaults are localhost, 3306, root, and an empty password.
4. Populate: `python populate.py`. The schema script drops and recreates `speedrun_phase4`; run it only on an instance where that database can be replaced.
5. Start the application: `python app.py` and open `http://127.0.0.1:5000`.

The database is loaded from the included snapshot and does not need internet access. To reload it, run schema creation followed by population again. A local demo actor, `team5_admin`, is granted game permissions for writing examples. The login page has two roles. User access accepts a nonempty username and password and is limited to Games, Runs, Reports, and Submit. Admin access is selected when the username is `taka` and the password is `takataka`; admins can use Manage and review or delete pending runs, but cannot use Submit. Login sessions use Flask’s signed session cookie; set a stable random `SECRET_KEY` before launching. User accounts are demo identities rather than individually stored/password-checked accounts.

## Open the website

After MySQL is running and you have completed the setup above, open PowerShell in the cloned repository and run:

```powershell
cd .\src
$env:DB_PASSWORD = "your-mysql-password"
$env:SECRET_KEY = "replace-with-a-long-random-value"
python app.py
```

If your MySQL user is not `root`, also set `$env:DB_USER`. The app uses `localhost:3306` by default; set `$env:DB_HOST` or `$env:DB_PORT` if yours differs. Before starting, configure `$env:SECRET_KEY` to a long random value. Open **http://127.0.0.1:5000/** in your browser; it redirects to the login page. Keep the PowerShell window running while using the site; press Ctrl+C to stop it.

## Design changes

| Earlier team | Change from Team 5's Phase 3 model | Reason |
|---|---|---|
| Team 14 (Phase 2), Team 5 (Phase 3) | Added `run.source_url` | Preserve a direct link to each public source run for provenance. |
| Team 14 (Phase 2), Team 5 (Phase 3) | Named the mapped `USER` table `users` | Avoid confusion with MySQL's `USER()` function and system users. |
| Team 14 (Phase 2), Team 5 (Phase 3) | Added `corrected` to review outcomes; the `run_status` view interprets it as pending | Distinguish a correction audit event from a final decision while retaining Phase 3's derived pending status. |
| Team 14 (Phase 2), Team 5 (Phase 3) | Used `BIGINT AUTO_INCREMENT` for board IDs and text source IDs for imported games, users, categories, levels, platforms, and runs | Keep stable Speedrun.com IDs, while assigning local IDs for new records. |

The 18 mapped relations remain: users, game, category, level, platform, permission, leaderboard, board_rule_version, run, run_rule, evidence_link, review_event, correction_change, supports, related_to, game_alternate_name, user_social_profile, and authorizes. The `run_status` view is derived. New boards separate source runs by category, level, platform, and the source subcategory values hash; this avoids comparing unlike variants. The complete original variable JSON is retained in `variant_description` where it fits. Historical board rule versions remain immutable when a moderator publishes a new version.

Some cross-table rules require transactions and application checks: category/level game agreement, supported platform, reviewer authorization, at least one evidence link, and choosing an effective rule version. Source data is filtered to one registered player, positive time, compatible category/level, and at least one evidence URL. The import creates review events from source verification data and demo permissions for examiners; it does not claim to reconstruct the source site's full moderation history.

## Numbered UI features and demo order

1. **Game selection** - `/`, three game cards with board counts and game artwork.
2. **Category and board selection** - `/game/<game_id>` then `/game/<game_id>/category/<category_id>`. Lists categories, levels, platforms, readable settings (such as Version and DTS), and run counts.
3. **Leaderboard projection, aggregate, and ranking** - `/board/<board_id>`. Shows runner, fastest verified time, date, rank, number of ranked runners, and board rules. Ranking uses each runner's best verified run on that exact board.
4. **Run selection and evidence** - `/runs`, status filter, then `/run/<run_id>`. Shows verified/pending/rejected records and the related evidence and review rows.
5. **Three join reports** - `/reports`. Game/category counts; moderator review counts and average turnaround; fastest verified result within each board, labelled with platform and category. The third report remains board-specific for comparability.
6. **Create game, category, board, and rule version** - `/admin`, first form. Creates all related rows transactionally and grants demo moderator permissions.
7. **Create pending run and evidence** - `/submit`. Creates a runner if needed, selects current board rules, inserts the run and evidence in one transaction.
8. **Update review decision (admin)** - open a new run from `/runs`; verify or reject it. The reason field appears only for a rejection, which requires a reason. The route checks the signed-in admin role, game-scoped permission, and self-review, then inserts a final event.
9. **Update rules** - `/admin`, second form. Adds a new board rule version without changing prior run references.
10. **Delete pending run** - open a pending run; delete it. Reviewed runs are retained; evidence cascades and the unreferenced run-rule record is removed in the same transaction.

For the required `18.mp4` video, show the site next to a MySQL client. Before and after operations 6-10, repeat a query against the affected tables. Useful examples: `SELECT * FROM game ORDER BY game_id DESC LIMIT 5;`, `SELECT * FROM run ORDER BY submitted_at DESC LIMIT 5;`, `SELECT * FROM review_event ORDER BY event_at DESC LIMIT 5;`, and `SELECT * FROM board_rule_version ORDER BY created_at DESC LIMIT 5;`. Run the query features through the UI. The submission recording must be captured by a team member on a running local MySQL instance.

## Query and integrity notes

- Status filtering and all write routes use bound SQL parameters, never concatenated SQL.
- Run submission checks positive integer duration and HTTP(S) evidence; SQL enforces `duration_ms > 0`, keys, FKs, and evidence index 1-10.
- `RUN_RULE` has Phase 3's `(submitted_at, board_id)` key. A submission that collides in one second is assigned the next free stored second. This is a Phase 3 modelling limitation because timestamps are not guaranteed unique in a real system.
- Deleting or editing a reviewed source run is prohibited in the UI to preserve its audit trail.
- The site is a local coursework prototype. Only the administrator session can review or delete pending runs; the review audit entry uses the seeded demo administrator identity.

## GenAI use

OpenAI Codex helped read the assignment, write the schema, importer, web app, and documentation, and inspect the available source and Phase 3 material. The source snapshot was retrieved from the official Speedrun.com API. The team must check and demonstrate the final system on its own MySQL installation before submission.
