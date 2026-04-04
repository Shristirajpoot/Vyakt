use Vyakt_learning;

db.users.createIndex({ email: 1 }, { unique: true, name: 'email_unique' });
db.users.createIndex({ role: 1 }, { name: 'role_idx' });

db.learning_paths.createIndex({ level: 1, sublevel: 1 }, { name: 'level_sublevel_idx' });

db.vocabulary.createIndex({ word: 1 }, { unique: true, name: 'word_unique' });
db.vocabulary.createIndex({ level: 1, sublevel: 1 }, { name: 'vocab_level_idx' });

db.lesson_attempts.createIndex({ user_id: 1, created_at: -1 }, { name: 'user_attempts_idx' });
db.lesson_attempts.createIndex({ sublevel: 1 }, { name: 'attempt_sublevel_idx' });

db.progress.createIndex({ user_id: 1 }, { unique: true, name: 'progress_user_unique' });
db.progress.createIndex({ xp: -1 }, { name: 'progress_xp_desc' });

db.badges.createIndex({ badge_id: 1 }, { unique: true, name: 'badge_id_unique' });
db.user_badges.createIndex({ user_id: 1, badge_id: 1 }, { name: 'user_badges_idx' });

db.quests.createIndex({ quest_id: 1 }, { unique: true, name: 'quest_id_unique' });
db.quests.createIndex({ window: 1 }, { name: 'quest_window_idx' });

db.leaderboards.createIndex({ window: 1, rank_score: -1 }, { name: 'window_rank_score_desc' });
db.leaderboards.createIndex({ user_id: 1 }, { name: 'leaderboard_user_idx' });

db.audit_events.createIndex({ timestamp: -1 }, { name: 'audit_timestamp_desc' });
db.audit_events.createIndex({ user_id: 1, event_type: 1 }, { name: 'audit_user_event_idx' });
