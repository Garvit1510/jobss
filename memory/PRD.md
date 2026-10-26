# JobLens AI — PRD
## Original problem
Rebuild the lost JobLens AI project (see work.txt) with the same Neo-Brutalism UI, plus: 10+ real job sources (no mock data, original salary currency), email/password auth (no OTP) with one-account-per-device, single active session, permanent ban of device/IP/account on multi-account attempts. Future: proctored company OAs (camera/mic flags), voice AI interviewer with reports, subscriptions, Adzuna/JSearch.

## Architecture
React (CRA+CRACO, Tailwind, framer-motion) + FastAPI + MongoDB (joblens_ai). AI: user's Gemini key, gemini-3-flash-preview via emergentintegrations (retry x4).
Backend: server.py, auth.py, routes_core.py (resume/dashboard/jobs/companies), routes_prep.py (prepare/learning/experiences/mock-oa/interview), jobs_service.py (12 sources, refresh every 6h, live FX via open.er-api for salary sort), skills.py, ai.py, resume_parser.py.

## Implemented (2026-10-09)
- Auth: JWT cookies, bcrypt, brute-force lockout, device fingerprint, single session (SESSION_REPLACED + 15s polling), ban flow (device+IP+account), TRUSTED_PROXY_HOPS for real client IP
- 12 live sources: Greenhouse(34 cos), Lever(6), Ashby(12), Workable, SmartRecruiters(6), Recruitee(2), Remotive, Arbeitnow, RemoteOK, Himalayas, Jobicy, The Muse (~7.6k jobs)
- Resume upload + AI analysis, dashboard, jobs list (search/filters/source/sort), job details (Overview/Prepare/Learning/Community), Mock OA (topic + real company list, timer, grading), text AI interview + final report
- Tested: iteration_1 backend 20/20, frontend primary flows pass

## Backlog
- P0: Proctored OA (camera/mic/tab-switch flags), voice AI interviewer (STT/TTS)
- P1: Adzuna/JSearch sources, more ATS companies, cached per-user ranking, admin unban panel
- P2: Subscriptions, lifespan migration

## v2 (2026-10-09)
- Voice interviewer (free Web Speech API): spoken questions, mic transcript, spoken feedback, repeat/mic/submit/stop, timer, early-finish report with recommendations, text fallback
- Job alerts: saved searches, bell count (new jobs by first_seen_at), /alerts page
- Country filter (countries.py detection + "Remote / Anywhere")
- work.txt updated at /app/work.txt. Tested iteration_2: 100%

## v3 (2026-10-09)
- Auto-submit on silence (2/3/5s, toggle, countdown), Voice Answer Coach (wpm, fillers, long pauses, delivery tips)
- Fix: Gemini free-tier 429 -> model fallback chain + cooldown; frontend auto-retry; speech hang/guards
- NOT run through testing agent (user request)
- v4: fixed destroy-is-not-a-function crash (scrollIntoView promise in effects), 10s auto-submit option persisted. Tested iteration_3 100%.


## 2026-10-09 (v5): Setup from zip, Proctored OA, Admin unban panel
- Recreated backend/.env + frontend/.env (were not in zip). User Gemini key set in GEMINI_API_KEY.
- Proctored OA: toggle on Mock OA setup -> system check (camera+mic permission, preview, mic meter, rules) -> fullscreen.
  Monitors: tab switch, window blur, fullscreen exit, copy/cut/paste (blocked), camera off/muted, camera covered (dark frames),
  sustained loud noise. Floating cam monitor + flag count; 5 tab switches = auto-submit. Flags stored via POST /api/mock-oa/{id}/flag.
  Result shows integrity score (100 - weighted flags), risk level, counts, timeline. Nothing recorded/uploaded (local preview only).
- Admin: seeded admin (ADMIN_EMAIL/ADMIN_PASSWORD), role in /auth/me, /admin page (stats, Bans tab with active/lifted/all + unban,
  Users tab with search/banned filter + unban). Bans are soft-lifted (active=false, unbanned_by/at) so is_banned ignores them.
## Backlog
- P1: subscriptions, Adzuna/JSearch (keys), admin view of proctoring reports, face detection in proctoring

- 2026-10-09: Switched MONGO_URL to user's MongoDB Atlas cluster (joblensai.6ghq0p1). Colon in password URL-encoded (%3A).
- 2026-10-09: Fixed 'Network Error' on login/register: CORS only allowed one origin; user opens app from thirsty-keller-10.preview.emergentagent.com. FRONTEND_URL now comma-separated + CORS_ORIGIN_REGEX env for Emergent preview/deploy domains.
- 2026-10-09: AI interview realism upgrade (backend/interview_ai.py): short single questions, stage plan, follow-ups, adaptive difficulty, separate eval rubric, question validation, level + job description context. See /app/progress.txt
- 2026-10-09: Follow-up trail in interview report, conditional live coding round (camera+mic), company-wise OA datasets (admin upload -> Gemini pattern profile -> mimic OA). See /app/progress.txt
- 2026-10-09: Live 'Run tests' for OA + interview coding (local sandbox Python/JS/C++, reference-solution-verified judge tests). See /app/progress.txt
- 2026-10-09: ai.py fallback to EMERGENT_LLM_KEY when user Gemini key is out of quota; per-call timeout + cooldowns.
- 2026-10-09: Replaced Emergent fallback with Gemini key rotation (GEMINI_API_KEYS, 4 keys).
- 2026-10-09: AI status banner, /api/code/try custom input, Java in runner (apt openjdk-17; reinstall after pod restart).

## 2026-10-09 (v6): Background interview evaluation + env recreated
- Real-time interview feel: POST /interview/answer now returns the NEXT question immediately; per-answer grading (interview_ai.evaluate) runs as a background asyncio task and is written per-turn (turns.{i}.evaluation via indexed $set so it is never clobbered). Response no longer carries "evaluation". Final report (_final_report) awaits all pending evals (_PENDING_EVALS), reloads turns from DB, and synchronously fills any missing eval before building the report. interview/finish updated to new _final_report(s, resume) signature.
- Frontend: removed inline per-answer "Feedback · x/10" bubbles (InterviewChat.js, VoiceTranscript.js, VoiceInterview.js log). Feedback now lives only in the final report (trail + per_question).
- ENV recreated (gitignored, absent from zip/GitHub): backend/.env uses LOCAL MongoDB (mongodb://localhost:27017, DB joblens_ai) as a stopgap because the user's Atlas MONGO_URL still had the literal <db_password> placeholder. 4 user Gemini keys in GEMINI_API_KEYS, model gemini-3-flash-preview + fallbacks. frontend/.env REACT_APP_BACKEND_URL set to the preview endpoint. To switch to Atlas: set MONGO_URL to the full connection string with the real password (URL-encode special chars) and restart backend.
- Smoke-tested with curl (user asked not to run the testing agent): start->3 answers->report; evals collected correctly.
- 2026-10-09 (v6b): MONGO_URL switched to the user's Atlas cluster (joblensai.6ghq0p1, user garvitdubey1510_db_user) with the real password; verified admin login reads existing Atlas data (created_at 10:07). Backend restarted.

## 2026-10-09 (v7): Proctored OA — AI vision upgrade
- Added @vladmandic/human (single tfjs) for in-browser proctoring vision; models served locally from /app/frontend/public/models/ (blazeface, facemesh, faceres, centernet). New lib/proctorVision.js.
- New flags (frontend FLAG_INFO + backend FLAG_WEIGHTS): phone_detected(20), multiple_faces(25), different_person(30), no_face(6).
- useProctor.js: vision loop (every 2.5s) detects phones/second screens/books (COCO objects), extra people (face/person count), face-identity mismatch vs a registered reference (Human embedding similarity, flags after 2 consecutive <0.40 reads), and no-face. Camera-block now also triggers on low-variance/uniform frames (hand/paper over lens), not just darkness.
- Face registration at start: ProctorSetup loads models, requires exactly one face + no devices to register a reference embedding, plus a mandatory "closed tabs / alone" confirmation checkbox before Start.
- Fullscreen fixes: robust vendor-prefixed isFs(); debounced fullscreenchange (250ms) to kill false fullscreen_exit flags; window_blur suppressed while fullscreen; begin() re-syncs fullscreen state; F11/F12 now re-enter fullscreen (preventDefault); a full-screen blocking gate (ProctorMonitor) locks the test when not fullscreen and resumes in place (timer keeps running).
- LIMITATION (browser sandbox): cannot enumerate other open tabs or detect other running desktop software; handled via the mandatory confirmation + live focus/blur/tab monitoring. Communicated to user.
- Not run through testing agent (user will verify); app compiles clean, models serve 200, landing renders with no console errors.

## 2026-10-09 (v8): Proctoring behaviour fixes (user-reported)
- Mid-test face swap now enforced: different_person -> full red lockout overlay with 30s countdown -> auto-submit if the registered face doesn't return (countdown immune to answer edits via finishRef). Identity match uses Human embeddings (match>=0.5, mismatch<0.45, null-safe so the real candidate is never falsely flagged).
- Voice: much more sensitive. loud_noise (sudden) + new background_voice (sustained talking / second voice, rms>0.045 accumulated ~3.5s).
- Gaze: gaze_away flag from Human head angle (yaw>0.5rad sideways, pitch down/up) sustained ~7.5s.
- Live camera monitor + gates now render via React portal to document.body -> stays pinned bottom-right (fixed the drift at page bottom caused by transformed ancestors).
- New flag weights: gaze_away 4, background_voice 8.

## 2026-10-10: New pod setup + coding workspace / proctored interview
- .env recreated: Atlas DB "joblens_ai" (switched back from JobLensAI: user accounts live there), 5 Gemini keys (GEMINI_API_KEYS), fallback models gemini-3.5..3.8-flash, gemini-flash-latest
- OA coding = HackerRank-style split CodeWorkspace (Run Code / Submit & Next, Test Results | Custom Input)
- AI Interview proctored mode (setup check, fullscreen, face identity lockout, flags, integrity score in report); coding round on CodeWorkspace
- Not run through testing agent (user tests manually); verified via curl + screenshot
## Backlog
- P1: subscriptions, Adzuna/JSearch, admin view of proctoring reports
- 2026-10-10: CodeMirror editor (auto-indent), Prepare tab practice choice (OA from job only / interview = JD + resume). iteration_5 100%.
- 2026-10-10: per-language code drafts + boilerplate on language switch, /api/code/languages, editor prefs (font size, auto-close).
- 2026-10-10: All-sector upgrade: careers.py taxonomy (23 sectors), explainable matching, career profile + no-resume builder, sector OA templates (mcq/numeric/written/coding), sector interviews (role-play, case, teaching demo...), community moderation + grounding, career switcher (tracker + profile form/builder removed by user), data deletion. See progress.txt.

## 2026-10 Update: Company OA builder + dataset-first engine
- Admin: OA structure per company (sections, kind objective/written/coding/sql/web, count, minutes, sectional timing), dataset import (OCR + verbatim extraction into oa_bank), question bank with 65/35 original/related stats, verify/reject/edit, grounded generation, auto top-up.
- Candidate: exact configured counts, sectional locks/timers, coding with problem-specific starter code, MySQL workspace (sandbox), HTML/CSS/JS workspace with live preview + DOM-test grading (Accepted only if all pass).
- Backlog: admin UI to edit answer keys inline (currently JSON edit), MySQL engine instead of SQLite shim, per-difficulty distribution.
- 2026-10: Dataset uploads up to 250 MB (400 pages); admin manual ban/unban with reason (+optional device/IP block); proctoring evidence photos (registered face + frame at every flag, OA + AI interview) stored in Mongo `proctor_snaps`, admin-only view/zoom/delete (Admin → Proctoring photos).

- 2026-10-11: Env recreated again (gitignored). backend/.env -> Atlas (joblensai.6ghq0p1, DB joblens_ai), 12 Gemini keys from api.txt in GEMINI_API_KEYS (rotation in ai.py), fallbacks gemini-flash-latest,gemini-2.5-flash. New preview URL d0cccdb1-....preview.emergentagent.com. Java NOT installed (user will do later). Verified admin login on Atlas data + /api/ai/status 12/12 keys ready.

## 2026-10-11: Accenture Mock OA library (Phase 1)
- backend/accenture_mocks.py (engine) + routes_accenture.py. Collections: acc_mock_libraries (versioned, status generating|ready|incomplete|published|archived, source_pool, errors), acc_mocks (library_id+mock_id unique, rounds{behavioural,gamified,technical,coding}, round_config, validation{errors,warnings,stats}), acc_mock_access (mock_id lock, independent of version).
- Sources = Accenture oa_bank items (35 usable MCQs, none with source keys -> Gemini-solved, flagged ai_solved; ambiguous ones dropped; 2 coding). Source reuse capped (default 4) so 65% target not reachable; reported as warning.
- Coding hidden-test expected outputs computed by running the Python reference, samples must match.
- Default ROUND_CONFIG (placeholder until phase 2): behavioural 30/20m, gamified 4 games/20m, technical 20 MCQ/25m, coding 2/45m.
- Admin tab "Accenture mocks": generate, progress poll, retry failed, publish (only 40/40 valid), delete draft, per-mock review modal, per-mock + bulk lock/unlock.
- Candidate: /accenture-mocks catalog (GET /api/accenture-mocks, /api/accenture-mocks/{id} gated by accessible_mock()). No content exposed.
- Not run end-to-end with Gemini yet (admin must click Generate). No test agent (user instruction).

## 2026-10-11: Accenture structure corrected (CONFIG_VERSION 2)
- Behavioural 50 Q / 20m, 5-point agreement scale (source wording if behavioural items exist in oa_bank; currently none).
- Gamified: 6 fixed activities (Memory Maze 3x3/4x4 3m, Bubble Math 25x15s lowest->highest, Path Finder 3x3/4x4/5x5 3m), ~30m; only config + seed stored, mechanics=pending_recording.
- Technical 45 MCQs / 45m, category quotas: pseudocode 8, ms_office 5, cloud 5, networks 6, cybersecurity 5, oop 6 (must cover python/java/javascript), cs_fundamentals 5, sjt 5.
- Coding: DSA (python-reference verified) -> SQL (_valid_sql) -> JS Frontend (_valid_web), 20m each, 60m.
- Source reuse default 1 (max 5). All AI-derived keys (ai_solved + ai_generated) key_status=ai_derived_unverified, review_required=true.
- Publish gate: config_version must match + every mock re-validated. Retry blocked for outdated-config drafts. Library NOT generated yet (waiting for user).

## 2026-10-11: Accenture answer-key review + publication safety (CONFIG_VERSION 3)
- cross_check(): independent blind Gemini re-solve (15/batch) for every AI-derived key (source ai_solved + generated). Generated MCQs kept only if re-solve agrees (else regenerated). Source AI keys that disagree/ambiguous are excluded and listed in source_pool.flagged.
- Per-question review {pending|approved|rejected}; review_issue() blocks publication (invalid, rejected, unconfirmed AI key); labels "AI-derived — unverified" until admin approves. Approve can change key/explanation (requires explanation); decision propagates to the same source question in other mocks of the draft. Replace (Gemini, admin-click) swaps a single question.
- Endpoints: POST /api/admin/accenture-mocks/mocks/{doc}/questions/{qid}/review|replace; GET/PUT /api/admin/accenture-mocks/settings/behavioural-scoring (acc_mock_settings).
- Behavioural: trait_profile, objective_marking=false, configurable bands/aggregation/reverse scoring. SJT prompt requires single best answer + rationale for every option.
- Source pool cached on the library (source_cache) so retries do not re-call Gemini; retry only touches non-valid mocks.
- Library still NOT generated.

## 2026-10-11: M1 authored without Gemini
- Bulk Gemini job stopped (POST /api/admin/accenture-mocks/stop added; job guard: 3 attempts/request, abort after 3 consecutive failures; generate/retry accept mock_ids; resumable per round).
- Gemini quota exhausted (98 request attempts logged; last M1 run used 21 and aborted). Source pool cached on library v1 (33 usable MCQs, 4 flagged).
- M1 written by the Emergent agent via scripts/author_m1.py (generated_by=emergent_agent): 50 behavioural, 6 activities, 45 MCQs (1 source p20-q1 + 44 generated; pseudocode/OOP outputs verified by execution), DSA/SQL/Web validated by local judges. Status valid (draft), 44 questions block publication until admin review (no independent cross-check). M2-M40 pending, untouched. Not published/unlocked.

## 2026-10-11: Phase 3 - Accenture Round 2 gamified engine (game version g1-2026-10)
- backend/accenture_games.py: GAME_CONFIG (mechanics + unconfirmed details per engine), runtime board/question generation, server-validated moves/answers, server deadlines (+3s grace), acc_attempts collection (separate from content), refresh-safe resume, admin preview of draft mocks, candidate access via accessible_mock.
- Endpoints: POST /api/accenture-mocks/{id}/gamified/start|begin|maze/move|bubble/answer|time-up, GET /api/accenture-mocks/{id}/gamified, DELETE (admin preview reset), GET /api/admin/accenture-mocks/games-config.
- Frontend: pages/AccentureGamified.js (/accenture-mocks/:mockId/gamified, ?preview=1), components/accenture/{MemoryMaze,BubbleMath,timer}.js; catalog Start Round 2 button; admin Preview R2 link + Round 2 engine card.
- Memory Maze + Bubble Math implemented. Path Finder = pending_mechanics (shown, recorded as not scored). No round % computed (weights unconfirmed). M1 still draft/locked; M2-M40 untouched. No Gemini calls.

## 2026-10-11: Phase 3 closed - Path Finder + Round 2 scoring
- Path Finder implemented (accenture_games.py gen_pathfinder/pf_trace; endpoints path/rotate|swap|check|retry). Board: NxN arrow tiles (8 directions), start left of start_row, goal right of goal_row; yellow = live trace from start; solution stored server-side only; scrambled n-1 path tiles, par moves stored.
- Configurable unconfirmed rules (acc_mock_settings gamified_options): maze reset_key_on_wrong, mazes_per_section; bubble show_incorrect_feedback, difficulty flat|progressive; pf rotate_step_deg 45|90. Snapshotted per attempt (engine_options).
- Scoring practice_v1 (acc_mock_settings gamified_scoring, snapshotted per attempt): maze 100-10/extra attempt (min 40) else 0; bubble %; PF 50+50*min(1,par/moves) else 0; round % = weighted mean, cutoff 70 configurable; stored attempt.round_score. Not official.
- E2E API check script: scripts/acc_round2_check.py (all 6 activities solved -> round score stored). M1 still draft/locked.

## 2026-10-11: Phase 4 - Accenture Round 3 + Round 4
- backend/accenture_rounds.py: technical attempt (45 Q, 45m server deadline, per-answer persistence, +4/-1/0, % = max(0,raw)/180*100, cutoff 70 configurable via acc_mock_settings technical_scoring; keys/explanations only after submit with key_label). Coding attempt: DSA->SQL->Frontend 20m each server deadlines; run = visible tests only; submit = all tests, weighted (visible 1 / hidden 2) partial credit, best submission, max 10; hidden inputs never returned; submissions/code/results stored privately; round % = mean of 3; settings coding_scoring. Round order gamified->technical->coding enforced for candidates (preview bypass). GET /api/accenture-mocks/{id}/report owner-only summary.
- Frontend: pages/AccentureTechnical.js, pages/AccentureCoding.js, catalog + admin R2/R3/R4 preview links, RoundScoring admin card.
- Isolation = process-level (code_runner: nobody user, rlimits, clean env), same host, no container sandbox, network not blocked.
- Check script: scripts/acc_r34_check.py.

## 2026-10-11: New pod setup
- Code already in workspace (matches zip). Recreated backend/.env (Atlas joblens_ai, new JWT_SECRET -> old sessions logged out) + frontend/.env (preview 391fe4ba...).
- Gemini keys NOT provided this session (no api.txt in zip) -> GEMINI_API_KEY=PENDING_USER_KEY; AI features fail until keys are added.
- OpenJDK 17 reinstalling for Java runner. No testing agent (user request).

## 2026-10-11 (Phase 5): Accenture Round 1 Behavioural
- backend/accenture_behavioural.py: start/get/answer/submit (/api/accenture-mocks/{id}/behavioural), 20-min server deadline (+5s grace), reuses M1's 50 saved statements (no AI).
- Trait-profile scoring (1-5, reverse = 6-v, mean/sum per admin setting, low/moderate/high bands, profile index), passed=None. Flags -> admin review (low completion, straight-lining, excessive neutral, forward/reverse contradiction, uniformly extreme, <3 items/trait).
- Admin: GET /api/admin/accenture-mocks/behavioural-attempts, POST .../{id}/review (accepted/invalidated/reset); BehaviouralReview card + R1 preview link.
- Order enforced: ROUND_ORDER = behavioural, gamified, technical, coding; gamified start now requires R1 finished (non-preview). Report includes behavioural (owner-only). Catalog: Start Round 1 + "View my results".
- M1 still locked/unpublished. Verified by curl (admin preview) + 1 screenshot; no testing agent.

## 2026-10-11 (Phase 6): Integration + release readiness
- Removed misleading include_in_overall_score (R1 never scored). Report now has `overall`: practice % = mean(R2,R3,R4); verdict only when R1 completed and not under review/invalidated.
- Behavioural review thresholds configurable (review_thresholds in behavioural_scoring settings + admin UI); thresholds stored in each result.
- Catalog: per-mock round navigation from /report (next round, locked labels, overall). Round pages show backend reason when blocked (fixed Gamified crash on error).
- Runner hardening: RLIMIT_NPROC 256; chmod 700 memory/.git/supervisor logs, 600 .env/auth_testing.md. Live probe: candidate code CAN reach internet, app server, local mongo (no unshare/NET_ADMIN in pod) => RELEASE BLOCKER. Publish refuses unless CODE_SANDBOX_ISOLATED=true.
- New GET /api/admin/accenture-mocks/release-readiness + admin card. M1 still locked/unpublished; 44 R3 keys block publication.

## 2026-10-11 (Phase 7): Sandbox + release blockers
- backend/sandbox.py: chroot jail (/opt/jl_jail via SANDBOX_JAIL_DIR, auto-built at startup ~30s, 640MB) + seccomp (socket/io_uring/ptrace/mount/ns... denied) + uid pool 61001-61008 + rlimits. 23 live probes (network from py/node/c++/java, fs visibility, env, uid, nproc, cpu, mem, 4 langs, SQL, jsdom) -> all pass in this pod.
- Accenture R4 (_judge) uses isolated runner only; fail-closed 503 if not built+verified. Other flows untouched (legacy runner, no network isolation).
- Fixes: preview attempts no longer satisfy real round order / start mixes; R4 pending task content hidden until begun; drafts saved before judging.
- Release readiness: 4 sections (confirmed live / code-inspection only / infra blocked / manual review), re-runs probes. Publish requires fresh probes + CODE_SANDBOX_ISOLATED (NOT set; kernel isolation still missing). See /app/memory/SANDBOX_DEPLOYMENT.md.

## 2026-10-11 Bug: M1 unlocked but invisible to candidates
- Root cause: library v1 status=incomplete, never published; candidate gate = published library AND valid AND unlocked. Unlock works (acc_mock_access). Publish blocked: 1/40 valid + sandbox kernel-isolation flag.
- Fix: admin list returns candidate_visible + visibility_reason per mock (mirrors accessible_mock); UI shows "Hidden from candidates: ..." + banner when nothing published. No access-control change.

## 2026-10-11 Individual mock publishing
- New collection acc_mock_publications {mock_id, mock_doc_id (pinned), library_id, version, published, published_at/by, unpublished_at/by}. Library status untouched.
- Admin: POST /api/admin/accenture-mocks/mocks/{id}/publish (fresh content validation + live sandbox probes + CODE_SANDBOX_ISOLATED; 409 with content/security blockers), POST .../unpublish (immediate), GET .../publication. List returns per-mock `state` (valid/reviewed/published/unlocked/candidate_visible/release_blocked + blockers). UI: MockPublication column.
- Candidate gate (accessible_mock + catalog): unlocked AND (individually published pinned doc still valid+reviewed OR published library). Verified on local-mongo copy.
- M1 publish currently refused: only security blocker (runner not kernel-isolated). Candidates cannot access M1.

## 2026-10-11 Proctoring + existing code editor in Accenture mock OA
- backend/accenture_proctor.py: shared config (acc_mock_settings key "proctoring", default strict; per-mock override mock.oa_config), GET /api/accenture-mocks/{id}/oa-config, POST .../proctor/session (linked to attempt_id), POST /api/accenture-mocks/proctor/{sid}/flag (FLAG_WEIGHTS reuse), admin settings + GET /api/admin/accenture-mocks/attempt-reports. Sessions in acc_proctor_sessions; attempts snapshot proctoring_policy at start. /report includes proctoring per round + R4 tasks.
- Snaps: /proctor/snap kind "accenture"; admin Proctor photos lists them.
- R4 new jailed endpoints: /coding/try (custom stdin), /coding/sql-try (public sample only), /coding/draft (autosave).
- Frontend: components/accenture/ProctorGate.js wraps all 4 round routes (reuses useProctor, ProctorSetup, ProctorMonitor); AccentureCoding uses existing CodeWorkspace/SqlWorkspace/WebWorkspace via new optional adapter props (runTestsFn, runCustomFn, tryFn, languages, footer, submitRunsTests, initialResult, note). Admin: AccentureOAReports card.

## 2026-10-11 Demo publication (M1) + one proctor check per mock
- acc_mock_publications.mode: "full" | "demo_no_coding". Publish body {library_id, mode}. Demo requires zero content blockers; security gate still required for full (never waived/falsified). Demo => Round 4 closed for candidates server-side (_demo_guard on coding start + every coding endpoint via _code_ctx), report overall status "demo_round4_disabled", catalog flags demo_mode/coding_disabled, oa-config code_runner.disabled_for_demo. Admin preview unaffected.
- M1 is currently published in demo mode in prod (by admin@joblens.dev 15:07 UTC). Library still incomplete.
- AccProctorProvider (App.js) holds one useProctor for all Accenture rounds; gate re-links a new session per round attempt without re-running the system check (same mock, stream live, face registered). Leaving round routes stops camera.
- sandbox.build now under fcntl file lock (concurrent builds corrupted the jail once).
