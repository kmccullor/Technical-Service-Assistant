-- Ensure question_usage rows are removed automatically when a conversation is deleted.
ALTER TABLE question_usage
    DROP CONSTRAINT IF EXISTS question_usage_conversation_id_fkey;

ALTER TABLE question_usage
    ADD CONSTRAINT question_usage_conversation_id_fkey
        FOREIGN KEY (conversation_id)
        REFERENCES conversations(id)
        ON DELETE CASCADE;
