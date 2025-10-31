-- Migration: Correct RNI definition from Radio Network Interface to Regional Network Interface
-- This addresses the incorrect terminology that was being returned for RNI queries

INSERT INTO knowledge_corrections (question, original_answer, corrected_answer, metadata, user_id)
VALUES (
    'What is the RNI?',
    'Radio Network Interface',
    'Regional Network Interface',
    '{"correction_type": "terminology", "source": "user_correction", "notes": "Corrected incorrect RNI definition from Radio to Regional Network Interface"}'::jsonb,
    'system_admin'
)
ON CONFLICT DO NOTHING;

-- Also add variations of the question
INSERT INTO knowledge_corrections (question, original_answer, corrected_answer, metadata, user_id)
VALUES
    ('What does RNI stand for?', 'Radio Network Interface', 'Regional Network Interface', '{"correction_type": "terminology", "source": "user_correction"}'::jsonb, 'system_admin'),
    ('RNI definition', 'Radio Network Interface', 'Regional Network Interface', '{"correction_type": "terminology", "source": "user_correction"}'::jsonb, 'system_admin'),
    ('What is RNI?', 'Radio Network Interface', 'Regional Network Interface', '{"correction_type": "terminology", "source": "user_correction"}'::jsonb, 'system_admin')
ON CONFLICT DO NOTHING;