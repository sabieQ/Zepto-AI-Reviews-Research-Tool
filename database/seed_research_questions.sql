-- Optional preset shortcuts (free-form questions do not require these rows)
-- Prefer app startup seed (idempotent). This SQL is a manual alternative.

INSERT INTO research_questions (id, slug, category, title, description, prompt_file, is_active, sort_order)
VALUES
  (gen_random_uuid(), 'pain_points', 'experience', 'What are the most common customer pain points?', 'Surface recurring frustrations from customer conversations.', 'pain_points.md', true, 1),
  (gen_random_uuid(), 'feature_requests', 'experience', 'What features do customers request most often?', 'Identify unmet needs and requested capabilities.', 'feature_requests.md', true, 2),
  (gen_random_uuid(), 'sentiment', 'experience', 'What is overall customer sentiment and why?', 'Summarize positive, neutral, and negative sentiment with evidence.', 'sentiment.md', true, 3),
  (gen_random_uuid(), 'discovery_behaviour', 'discovery', 'Why do customers stick to familiar categories / fail to discover new ones?', 'Explore category discovery barriers on Zepto.', 'discovery_behaviour.md', true, 4),
  (gen_random_uuid(), 'opportunities', 'discovery', 'What product opportunities emerge from customer evidence?', 'Turn evidence into product opportunity hypotheses.', 'opportunities.md', true, 5),
  (gen_random_uuid(), 'executive_summary', 'experience', 'Produce an executive research summary for leadership', 'Leadership-ready summary grounded in retrieved evidence.', 'executive_summary.md', true, 6)
ON CONFLICT (slug) DO NOTHING;
